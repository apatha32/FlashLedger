"""
LSTM Price Direction Training Script
=====================================
Loads historical market features from PostgreSQL, builds a sliding-window
dataset (window=20 time steps, target=next-step price direction), and trains
a 2-layer LSTM classifier with PyTorch.

Usage:
    python -m ml.train

Saves:
    ml/model.pt   — trained model weights + scaler params
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
import psycopg2

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Hyperparameters ────────────────────────────────────────────────────────

WINDOW_SIZE   = 20
HIDDEN_SIZE   = 128
NUM_LAYERS    = 2
DROPOUT       = 0.3
BATCH_SIZE    = 64
EPOCHS        = 50
LR            = 1e-3
DEVICE        = "cuda" if torch.cuda.is_available() else "cpu"
FEATURES      = ["trade_volume", "vwap", "order_imbalance", "trade_velocity"]
MODEL_PATH    = os.path.join(os.path.dirname(__file__), "model.pt")

# ── DB Connection ──────────────────────────────────────────────────────────

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://flashledger:flashledger@localhost:5432/flashledger",
)


def load_features_from_db() -> pd.DataFrame:
    """Load market_features from PostgreSQL, sorted chronologically."""
    conn_str = (
        DB_URL
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("sqlite+aiosqlite:///", "")
    )
    logger.info("Loading features from PostgreSQL ...")
    conn = psycopg2.connect(conn_str)
    df = pd.read_sql(
        "SELECT window_start, trade_volume, vwap, order_imbalance, trade_velocity "
        "FROM market_features ORDER BY window_start ASC",
        conn,
    )
    conn.close()
    logger.info("Loaded %d rows from DB", len(df))
    return df


def load_features_synthetic() -> pd.DataFrame:
    """
    Generate market_features-shaped data from BTC-USD yfinance hourly bars.
    Used when the PostgreSQL database is unavailable (local dev, HF Spaces).
    """
    import yfinance as yf
    logger.info("DB unavailable — downloading BTC-USD 2y hourly data from Yahoo Finance ...")
    raw = yf.download("BTC-USD", period="2y", interval="1h", progress=False)
    raw = raw.dropna()

    close  = raw["Close"].values.flatten().astype(float)
    volume = raw["Volume"].values.flatten().astype(float)
    high   = raw["High"].values.flatten().astype(float)
    low    = raw["Low"].values.flatten().astype(float)

    price_delta = np.diff(close, prepend=close[0])

    df = pd.DataFrame({
        "window_start":    raw.index,
        "vwap":            close,
        "trade_volume":    volume / 1e8,
        "order_imbalance": (volume / 1e8) * np.sign(price_delta),
        "trade_velocity":  (high - low) / np.where(close > 0, close, 1) * 10,
    })
    df = df.dropna().reset_index(drop=True)
    logger.info("Synthetic features ready: %d rows", len(df))
    return df


def load_features() -> pd.DataFrame:
    """Try PostgreSQL first; fall back to synthetic yfinance data."""
    if DB_URL.startswith("sqlite"):
        logger.info("SQLite URL detected — using synthetic yfinance data")
        return load_features_synthetic()
    try:
        return load_features_from_db()
    except Exception as exc:
        logger.warning("PostgreSQL unavailable (%s) — falling back to yfinance data", exc)
        return load_features_synthetic()


# ── Dataset ────────────────────────────────────────────────────────────────

class WindowDataset(Dataset):
    """Sliding-window dataset.  Label = 1 if next VWAP > current VWAP, else 0."""

    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


def build_windows(df: pd.DataFrame, scaler: StandardScaler, fit: bool = True):
    """Return (X windows, y labels) numpy arrays."""
    values = df[FEATURES].values
    if fit:
        values = scaler.fit_transform(values)
    else:
        values = scaler.transform(values)

    X, y = [], []
    vwap = df["vwap"].values
    for i in range(WINDOW_SIZE, len(values)):
        X.append(values[i - WINDOW_SIZE:i])
        # 1 = price went up, 0 = price stayed same or went down
        y.append(1 if vwap[i] > vwap[i - 1] else 0)

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)


# ── Model ──────────────────────────────────────────────────────────────────

class PriceLSTM(nn.Module):
    """2-layer LSTM for binary price-direction classification."""

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, 2)

    def forward(self, x):                     # x: (batch, seq, features)
        out, _ = self.lstm(x)                 # out: (batch, seq, hidden)
        out = self.dropout(out[:, -1, :])     # last time step
        return self.fc(out)                   # (batch, 2)


# ── Training Loop ──────────────────────────────────────────────────────────

def train():
    df = load_features()

    if len(df) < WINDOW_SIZE + 10:
        logger.error(
            "Not enough data to train (%d rows). Need at least %d.",
            len(df), WINDOW_SIZE + 10,
        )
        sys.exit(1)

    scaler = StandardScaler()
    X, y   = build_windows(df, scaler, fit=True)

    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, shuffle=False)

    train_loader = DataLoader(WindowDataset(X_tr, y_tr), batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(WindowDataset(X_val, y_val), batch_size=BATCH_SIZE)

    model     = PriceLSTM(len(FEATURES), HIDDEN_SIZE, NUM_LAYERS, DROPOUT).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    criterion = nn.CrossEntropyLoss()
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    best_val_acc = 0.0

    for epoch in range(1, EPOCHS + 1):
        # ── train ──
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        # ── validate ──
        model.eval()
        preds, targets = [], []
        with torch.no_grad():
            for xb, yb in val_loader:
                logits = model(xb.to(DEVICE))
                preds.extend(logits.argmax(1).cpu().numpy())
                targets.extend(yb.numpy())

        val_acc = accuracy_score(targets, preds)
        scheduler.step(1 - val_acc)

        if epoch % 10 == 0 or epoch == 1:
            logger.info(
                "Epoch %3d/%d  loss=%.4f  val_acc=%.4f",
                epoch, EPOCHS, train_loss / len(train_loader), val_acc,
            )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            # Save model + scaler params together
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "scaler_mean": scaler.mean_.tolist(),
                    "scaler_scale": scaler.scale_.tolist(),
                    "features": FEATURES,
                    "window_size": WINDOW_SIZE,
                    "hidden_size": HIDDEN_SIZE,
                    "num_layers": NUM_LAYERS,
                    "dropout": DROPOUT,
                    "val_acc": val_acc,
                },
                MODEL_PATH,
            )

    logger.info("Training complete. Best val accuracy: %.4f", best_val_acc)
    logger.info("Model saved to %s", MODEL_PATH)


if __name__ == "__main__":
    train()
