"""
LSTM Price Direction Inference
================================
Loads ml/model.pt and returns a (direction, confidence) prediction
given a pandas DataFrame of the last N feature rows.

Used by the FastAPI /api/v1/prediction endpoint.
"""

import os
import logging
from typing import Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pt")

# Module-level cache so we only load once per process
_model       = None
_scaler_mean  = None
_scaler_scale = None
_config       = None


def _load_model():
    """Lazy-load the model from disk. Thread-safe for read-only inference."""
    global _model, _scaler_mean, _scaler_scale, _config

    if _model is not None:
        return True

    if not os.path.exists(MODEL_PATH):
        logger.warning("model.pt not found at %s — run ml/train.py first", MODEL_PATH)
        return False

    try:
        import torch
        import torch.nn as nn

        checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)

        class PriceLSTM(nn.Module):
            def __init__(self, input_size, hidden_size, num_layers, dropout):
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

            def forward(self, x):
                out, _ = self.lstm(x)
                out = self.dropout(out[:, -1, :])
                return self.fc(out)

        features    = checkpoint["features"]
        hidden_size = checkpoint["hidden_size"]
        num_layers  = checkpoint["num_layers"]
        dropout     = checkpoint["dropout"]

        model = PriceLSTM(len(features), hidden_size, num_layers, dropout)
        model.load_state_dict(checkpoint["model_state"])
        model.eval()

        _model        = model
        _scaler_mean  = np.array(checkpoint["scaler_mean"])
        _scaler_scale = np.array(checkpoint["scaler_scale"])
        _config       = checkpoint
        logger.info(
            "LSTM model loaded (val_acc=%.4f, window=%d)",
            checkpoint.get("val_acc", 0),
            checkpoint.get("window_size", 20),
        )
        return True

    except Exception as exc:
        logger.error("Failed to load model: %s", exc)
        return False


def get_prediction(df: pd.DataFrame) -> Tuple[str, float]:
    """
    Given a DataFrame with columns [trade_volume, vwap, order_imbalance, trade_velocity]
    (at least 1 row, most recent last), return (direction, confidence).

    direction  : "up" or "down"
    confidence : float in [0, 1]
    """
    if not _load_model():
        raise RuntimeError("LSTM model unavailable — run ml/train.py")

    import torch
    import torch.nn.functional as F

    features = _config["features"]
    window   = _config.get("window_size", 20)

    # Align columns
    df = df[features].copy()

    # Normalise
    values = (df.values - _scaler_mean) / (_scaler_scale + 1e-8)

    # Pad / trim to window size
    if len(values) < window:
        pad = np.zeros((window - len(values), values.shape[1]))
        values = np.vstack([pad, values])
    else:
        values = values[-window:]

    tensor = torch.tensor(values, dtype=torch.float32).unsqueeze(0)  # (1, window, features)

    with torch.no_grad():
        logits = _model(tensor)
        probs  = F.softmax(logits, dim=1).squeeze()

    up_prob   = float(probs[1])
    down_prob = float(probs[0])
    direction = "up" if up_prob >= down_prob else "down"
    confidence = max(up_prob, down_prob)

    return direction, confidence
