"""
Market Insight Recommender — Training Script
=============================================
Downloads 2 years of BTC-USD hourly OHLCV data from Yahoo Finance,
engineers features that are *identical* to those produced by the live
PySpark feature pipeline, and trains a LightGBM classifier.

Labels (forward 3-period return):
  BUY  (2) → forward return > +0.5 %
  SELL (0) → forward return < −0.5 %
  HOLD (1) → otherwise

Outputs:
  ml/recommender.pkl          — trained LightGBM model
  ml/rec_scaler.pkl           — StandardScaler for feature normalisation
  ml/rec_history.npz          — embeddings + labels for KNN similarity

Usage:
    python -m ml.train_recommender
"""

import os
import sys
import logging
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE = os.path.dirname(__file__)
MODEL_PATH   = os.path.join(BASE, "recommender.pkl")
SCALER_PATH  = os.path.join(BASE, "rec_scaler.pkl")
HISTORY_PATH = os.path.join(BASE, "rec_history.npz")

# Features must match ml/recommender.py _engineer_features()
FEATURES = [
    "vwap_change",      # 5-period VWAP momentum
    "volume_ratio",     # relative volume vs 20-period mean
    "imbalance_norm",   # order imbalance / velocity
    "velocity_change",  # 3-period velocity trend
    "volatility",       # 10-period rolling std of returns
    "rsi",              # RSI(14)
]


# ── Feature Engineering ────────────────────────────────────────────────────

def _rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain  = delta.clip(lower=0).rolling(period, min_periods=1).mean()
    loss  = (-delta.clip(upper=0)).rolling(period, min_periods=1).mean()
    return (100 - 100 / (1 + gain / (loss + 1e-8))).fillna(50.0)


def engineer_features(raw: pd.DataFrame) -> pd.DataFrame:
    """
    raw must have columns: vwap, trade_volume, order_imbalance, trade_velocity
    (exactly those in the market_features PostgreSQL table).
    """
    df = pd.DataFrame(index=raw.index)

    df["vwap_change"]    = raw["vwap"].pct_change(5).fillna(0)

    vol_mean             = raw["trade_volume"].rolling(20, min_periods=1).mean()
    df["volume_ratio"]   = (raw["trade_volume"] / (vol_mean + 1e-8)).fillna(1.0)

    vel                  = raw["trade_velocity"].replace(0, 1)
    df["imbalance_norm"] = (raw["order_imbalance"] / vel).fillna(0)

    df["velocity_change"] = raw["trade_velocity"].pct_change(3).fillna(0)

    returns              = raw["vwap"].pct_change()
    df["volatility"]     = returns.rolling(10, min_periods=1).std().fillna(0)

    df["rsi"]            = _rsi(raw["vwap"])

    return df.clip(-10, 10)


# ── Data Download ──────────────────────────────────────────────────────────

def download_btc() -> pd.DataFrame:
    """Download 2 years of BTC-USD hourly data and map to market_features schema."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        sys.exit(1)

    logger.info("Downloading BTC-USD 1h data (2 years) from Yahoo Finance …")
    raw = yf.download("BTC-USD", period="2y", interval="1h", progress=False, auto_adjust=True)

    # Flatten multi-index if present
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw = raw[["Open", "High", "Low", "Close", "Volume"]].dropna()
    logger.info("Downloaded %d hourly bars", len(raw))

    # Map to market_features columns
    mf = pd.DataFrame(index=raw.index)
    mf["vwap"]             = (raw["High"] + raw["Low"] + raw["Close"]) / 3
    mf["trade_volume"]     = raw["Volume"].clip(lower=0)
    # Approximate order imbalance: bullish candle → positive, bearish → negative
    mf["order_imbalance"]  = np.where(raw["Close"] >= raw["Open"],
                                       raw["Volume"], -raw["Volume"])
    rolling_vol            = raw["Volume"].rolling(24, min_periods=1).mean()
    mf["trade_velocity"]   = (raw["Volume"] / rolling_vol.clip(lower=1)).clip(0, 50)

    return mf


# ── Label Generation ───────────────────────────────────────────────────────

def build_labels(mf: pd.DataFrame, forward_periods: int = 3, threshold: float = 0.005):
    """Label each bar by its forward VWAP return."""
    fwd = mf["vwap"].pct_change(forward_periods).shift(-forward_periods)
    label = pd.cut(
        fwd,
        bins=[-np.inf, -threshold, threshold, np.inf],
        labels=[0, 1, 2],          # SELL=0, HOLD=1, BUY=2
    ).astype("float32")
    return label


# ── Training ───────────────────────────────────────────────────────────────

def train():
    try:
        import lightgbm as lgb
        import joblib
    except ImportError:
        logger.error("lightgbm / joblib not installed. Run: pip install lightgbm joblib")
        sys.exit(1)

    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    from sklearn.preprocessing import StandardScaler

    mf     = download_btc()
    feats  = engineer_features(mf)
    labels = build_labels(mf)

    valid  = feats.notna().all(axis=1) & labels.notna()
    X      = feats[valid].values
    y      = labels[valid].values.astype(int)

    counts = {0: int((y == 0).sum()), 1: int((y == 1).sum()), 2: int((y == 2).sum())}
    logger.info(
        "Dataset: %d samples — SELL=%d  HOLD=%d  BUY=%d",
        len(y), counts[0], counts[1], counts[2],
    )

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_tr, X_val, y_tr, y_val = train_test_split(
        X_scaled, y, test_size=0.2, shuffle=False,
    )

    model = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.04,
        max_depth=6,
        num_leaves=31,
        min_child_samples=30,
        subsample=0.8,
        colsample_bytree=0.8,
        class_weight="balanced",
        n_jobs=-1,
        verbose=-1,
    )

    model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(-1)],
    )

    y_pred = model.predict(X_val)
    acc    = accuracy_score(y_val, y_pred)
    logger.info("\n%s", classification_report(y_val, y_pred, target_names=["SELL", "HOLD", "BUY"]))
    logger.info("Validation accuracy: %.4f", acc)

    # Persist
    joblib.dump(model,  MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    # Save embeddings for KNN similarity search at inference time
    np.savez_compressed(HISTORY_PATH, embeddings=X_scaled, labels=y)

    logger.info("Saved model → %s", MODEL_PATH)
    logger.info("Saved scaler → %s", SCALER_PATH)
    logger.info("Saved history → %s  (%d vectors)", HISTORY_PATH, len(X_scaled))
    logger.info("Training complete. Accuracy: %.2f%%", acc * 100)


if __name__ == "__main__":
    train()
