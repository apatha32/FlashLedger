"""
Groq LLM Client for FlashLedger
================================
Provides two async functions:

  generate_commentary(insights: dict) -> Optional[str]
      Synthesises LightGBM recommender output into a 2-3 sentence AI narrative.
      Used by the GET /api/v1/insights endpoint.

  chat(message: str, context: dict) -> str
      Answers a freeform user question with live market context injected.
      Used by the POST /api/v1/chat endpoint.

Both functions degrade gracefully when GROQ_API_KEY is not set.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.3-70b-versatile"

_COMMENTARY_SYSTEM = (
    "You are a quantitative trading analyst embedded in a real-time crypto order "
    "matching engine called FlashLedger. Synthesise microstructure signals into "
    "clear, professional market commentary. "
    "Rules: (1) 2-3 sentences maximum. (2) Ground every claim in the numbers "
    "provided. (3) Never give financial advice or recommend specific trades."
)

_CHAT_SYSTEM_PREFIX = (
    "You are FlashLedger AI — an intelligent assistant embedded in a real-time "
    "crypto order matching engine. You have access to live market microstructure "
    "data shown below. Be concise, analytical, and data-driven. "
    "Never give financial advice.\n\nLive market context:\n"
)


# ── Commentary ─────────────────────────────────────────────────────────────

async def generate_commentary(insights: Dict[str, Any]) -> Optional[str]:
    """
    Build a 2-3 sentence AI narrative from the LightGBM recommender output.

    Returns None if GROQ_API_KEY is not set or if the call fails.
    """
    if not GROQ_API_KEY:
        return None

    try:
        from groq import AsyncGroq  # lazy import so missing package is non-fatal

        fv = insights.get("feature_values", {})
        similar = insights.get("similar_conditions", [])
        sim_str = (
            ", ".join(f"{s['outcome']}({s['similarity']:.0%})" for s in similar)
            if similar
            else "no KNN matches available"
        )

        user_msg = (
            f"Signal: {insights.get('action', 'HOLD')} "
            f"@ {insights.get('confidence', 0.5):.0%} confidence | "
            f"Regime: {insights.get('regime', 'RANGING')} | "
            f"RSI(14): {insights.get('rsi', 50):.1f}\n"
            f"VWAP Δ: {fv.get('vwap_change', 0):+.3f}% | "
            f"Volume ratio: {fv.get('volume_ratio', 1):.2f}× avg | "
            f"Order imbalance: {fv.get('imbalance_norm', 0):+.3f} | "
            f"Volatility: {fv.get('volatility', 0):.3f}%\n"
            f"Historical KNN matches: {sim_str}\n\n"
            "Write 2-3 concise sentences of market commentary for a live trading dashboard."
        )

        client = AsyncGroq(api_key=GROQ_API_KEY)
        completion = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _COMMENTARY_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens=160,
            temperature=0.3,
        )
        return completion.choices[0].message.content.strip()

    except Exception as exc:
        logger.warning("Groq commentary failed: %s", exc)
        return None


# ── Chat ───────────────────────────────────────────────────────────────────

async def chat(message: str, context: Dict[str, Any]) -> str:
    """
    Answer a user question with live market context injected into the system prompt.

    Returns a fallback string when the API key is absent or the call fails.
    """
    if not GROQ_API_KEY:
        return (
            "Groq AI is not configured. "
            "Set the GROQ_API_KEY environment variable to enable the AI assistant."
        )

    try:
        from groq import AsyncGroq

        ctx_lines = "\n".join(f"  {k}: {v}" for k, v in context.items())
        system_prompt = _CHAT_SYSTEM_PREFIX + ctx_lines

        client = AsyncGroq(api_key=GROQ_API_KEY)
        completion = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": message},
            ],
            max_tokens=350,
            temperature=0.5,
        )
        return completion.choices[0].message.content.strip()

    except Exception as exc:
        logger.error("Groq chat failed: %s", exc)
        return f"AI temporarily unavailable — {exc}"
