"""
Market Insight Recommender — Inference
=======================================
Lazy-loads the trained LightGBM model and produces:
  • action          — BUY / SELL / HOLD
  • confidence      — probability of the chosen action
  • regime          — TRENDING_UP / TRENDING_DOWN / RANGING / HIGH_VOLATILITY
  • probabilities   — {sell, hold, buy} probability breakdown
  • insights        — list of natural-language insight strings
  • similar_conditions — top-3 KNN matches from training history

Called by the FastAPI /api/v1/insights endpoint.
"""

import os
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BASE         = os.path.dirname(__file__)
MODEL_PATH   = os.path.join(BASE, "recommender.pkl")
SCALER_PATH  = os.path.join(BASE, "rec_scaler.pkl")
HISTORY_PATH = os.path.join(BASE, "rec_history.npz")

ACTIONS = {0: "SELL", 1: "HOLD", 2: "BUY"}

# Module-level cache
_model   = None
_scaler  = None
_history: Optional[Dict[str, np.ndarray]] = None


def _load() -> bool:
    global _model, _scaler, _history
    if _model is not None:
        return True
    if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
        logger.warning("Recommender artifacts missing — run ml/train_recommender.py")
        return False
    try:
        import joblib
        _model  = joblib.load(MODEL_PATH)
        _scaler = joblib.load(SCALER_PATH)
        if os.path.exists(HISTORY_PATH):
            data = np.load(HISTORY_PATH)
            _history = {
                "embeddings": data["embeddings"].astype(np.float32),
                "labels":     data["labels"].astype(np.int8),
            }
        logger.info("Recommender model loaded")
        return True
    except Exception as exc:
        logger.error("Failed to load recommender: %s", exc)
        return False


# ── Feature Engineering (mirrors train_recommender.py) ─────────────────────

def _rsi_scalar(prices: pd.Series) -> float:
    n = min(14, len(prices) - 1)
    if n < 2:
        return 50.0
    delta = prices.diff()
    gain  = delta.clip(lower=0).rolling(n, min_periods=1).mean().iloc[-1]
    loss  = (-delta.clip(upper=0)).rolling(n, min_periods=1).mean().iloc[-1]
    return float(100 - 100 / (1 + gain / (loss + 1e-8)))


def _engineer_features(df: pd.DataFrame) -> np.ndarray:
    """
    df columns: trade_volume, vwap, order_imbalance, trade_velocity
    Returns shape (1, 6) — same order as training FEATURES list.
    """
    vwap = df["vwap"]
    vol  = df["trade_volume"]
    imb  = df["order_imbalance"]
    vel  = df["trade_velocity"]

    window5 = min(5, len(df) - 1)
    vwap_change    = float(vwap.pct_change(window5).fillna(0).iloc[-1])

    vol_mean       = float(vol.rolling(min(20, len(vol)), min_periods=1).mean().iloc[-1])
    volume_ratio   = float(vol.iloc[-1]) / max(vol_mean, 1e-8)

    vel_val        = max(float(vel.iloc[-1]), 1e-8)
    imbalance_norm = float(imb.iloc[-1]) / vel_val

    window3        = min(3, len(df) - 1)
    velocity_change = float(vel.pct_change(window3).fillna(0).iloc[-1])

    returns        = vwap.pct_change()
    volatility     = float(returns.rolling(min(10, len(returns)), min_periods=1).std().fillna(0).iloc[-1])

    rsi            = _rsi_scalar(vwap)

    vec = np.array([[
        np.clip(vwap_change,     -10, 10),
        np.clip(volume_ratio,    -10, 10),
        np.clip(imbalance_norm,  -10, 10),
        np.clip(velocity_change, -10, 10),
        np.clip(volatility,        0, 10),
        np.clip(rsi,               0, 100),
    ]], dtype=np.float32)

    return vec


# ── KNN Similarity ──────────────────────────────────────────────────────────

def _find_similar(query_scaled: np.ndarray, top_k: int = 3) -> List[Dict[str, Any]]:
    if _history is None:
        return []
    embs = _history["embeddings"]
    labs = _history["labels"]

    q_norm = query_scaled / (np.linalg.norm(query_scaled) + 1e-8)
    h_norm = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8)
    sims   = (h_norm @ q_norm.T).ravel()
    top_idx = np.argsort(sims)[::-1][:top_k]

    return [
        {
            "rank":       int(i + 1),
            "similarity": round(float(sims[idx]), 4),
            "outcome":    ACTIONS[int(labs[idx])],
        }
        for i, idx in enumerate(top_idx)
    ]


# ── Natural Language Insights ──────────────────────────────────────────────

def _generate_insights(raw_features: np.ndarray) -> List[str]:
    vwap_change, volume_ratio, imbalance_norm, vel_change, volatility, rsi = raw_features[0]
    insights: List[str] = []

    # Momentum
    if vwap_change > 0.005:
        insights.append(f"VWAP rising +{vwap_change*100:.2f}% — sustained buying pressure detected.")
    elif vwap_change < -0.005:
        insights.append(f"VWAP declining {vwap_change*100:.2f}% — sellers dominating recent price action.")
    else:
        insights.append("VWAP consolidating in a narrow range — indecision in the market.")

    # Volume
    if volume_ratio > 1.8:
        insights.append(f"Volume is {volume_ratio:.1f}× the 20-period average — breakout conditions possible.")
    elif volume_ratio > 1.3:
        insights.append(f"Above-average volume ({volume_ratio:.1f}×) confirms current price movement.")
    elif volume_ratio < 0.5:
        insights.append("Volume well below average — low conviction, risk of false signals.")

    # Order imbalance
    if imbalance_norm > 0.4:
        insights.append("Strong buy-side aggression in order flow — positive imbalance signal.")
    elif imbalance_norm < -0.4:
        insights.append("Sell-side aggression dominant — negative order flow imbalance.")

    # RSI
    if rsi > 72:
        insights.append(f"RSI at {rsi:.0f} — overbought territory, elevated reversion risk.")
    elif rsi < 28:
        insights.append(f"RSI at {rsi:.0f} — oversold conditions, potential mean-reversion bounce.")
    elif 45 <= rsi <= 55:
        insights.append(f"RSI neutral at {rsi:.0f} — no strong directional bias from momentum.")

    # Volatility
    if volatility > 0.015:
        insights.append(f"Elevated volatility ({volatility*100:.2f}%) — consider tighter risk controls.")

    # Velocity
    if vel_change > 0.25:
        insights.append("Trade velocity accelerating — momentum regime forming.")
    elif vel_change < -0.25:
        insights.append("Trade velocity decelerating — activity cooling off.")

    return insights[:4]


# ── Regime Classification ──────────────────────────────────────────────────

def _classify_regime(raw_features: np.ndarray) -> str:
    vwap_change = raw_features[0, 0]
    volatility  = raw_features[0, 4]
    rsi         = raw_features[0, 5]

    if volatility > 0.02:
        return "HIGH_VOLATILITY"
    if vwap_change > 0.004:
        return "TRENDING_UP"
    if vwap_change < -0.004:
        return "TRENDING_DOWN"
    return "RANGING"


# ── Public API ──────────────────────────────────────────────────────────────

def get_insights(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Entry point for the FastAPI /insights endpoint.

    Parameters
    ----------
    df : DataFrame with columns [trade_volume, vwap, order_imbalance, trade_velocity],
         most-recent row last, ideally 20–50 rows.

    Returns
    -------
    dict with keys: action, confidence, regime, probabilities,
                    insights, similar_conditions, rsi, feature_values
    """
    if not _load():
        raise RuntimeError("Recommender model unavailable — run ml/train_recommender.py")

    raw_features   = _engineer_features(df)
    scaled_features = _scaler.transform(raw_features)

    proba      = _model.predict_proba(scaled_features)[0]   # [P(SELL), P(HOLD), P(BUY)]
    action_idx = int(np.argmax(proba))
    action     = ACTIONS[action_idx]
    confidence = float(proba[action_idx])

    return {
        "action":     action,
        "confidence": round(confidence, 4),
        "regime":     _classify_regime(raw_features),
        "probabilities": {
            "sell": round(float(proba[0]), 4),
            "hold": round(float(proba[1]), 4),
            "buy":  round(float(proba[2]), 4),
        },
        "insights":           _generate_insights(raw_features),
        "similar_conditions": _find_similar(scaled_features),
        "rsi":                round(float(raw_features[0, 5]), 1),
        "feature_values": {
            "vwap_change":    round(float(raw_features[0, 0]) * 100, 3),
            "volume_ratio":   round(float(raw_features[0, 1]), 2),
            "imbalance_norm": round(float(raw_features[0, 2]), 3),
            "velocity_change": round(float(raw_features[0, 3]) * 100, 3),
            "volatility":     round(float(raw_features[0, 4]) * 100, 3),
        },
    }
