"""
AI-Powered Demo Runner (Groq / Llama 3.3)
==========================================
Calls Groq every ~4 seconds to analyse live market microstructure and
generate intelligent orders. Designed to run *alongside* the rule-based
demo runner — the rule-based bots provide market depth and price discovery,
while this agent places thoughtful directional trades on top.

The LLM receives: mid-price, spread, regime, VWAP change, order imbalance,
trade velocity and recent price delta, then returns a small JSON array of
orders. Each order is safety-clamped to ±2% of mid before submission.

This is an ADDITIONAL showcase feature. The primary USP of FlashLedger is
the ML training pipeline (PySpark features → LSTM/LightGBM training).
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AIRunner:
    def __init__(self):
        self._task:        Optional[asyncio.Task] = None
        self._running:     bool  = False
        self.tick:         int   = 0
        self.last_action:  Optional[str] = None
        self.last_reason:  Optional[str] = None

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    @property
    def status(self) -> dict:
        return {
            "running":     self._running,
            "tick":        self.tick,
            "last_action": self.last_action,
            "last_reason": self.last_reason,
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self.tick     = 0
        self._task    = asyncio.create_task(self._run())
        logger.info("AI demo runner started")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("AI demo runner stopped")

    # ── Groq order generation ───────────────────────────────────────────────

    async def _ask_groq(self, context: Dict[str, Any]) -> List[Dict]:
        """
        Ask Groq to analyse market context and return a list of orders.
        Returns [] on any failure so the runner degrades gracefully.
        """
        from app.ai.groq_client import GROQ_API_KEY
        if not GROQ_API_KEY:
            return []

        try:
            from groq import AsyncGroq

            prompt = (
                f"mid={context['mid']:.2f} | bid={context['bid']:.2f} | ask={context['ask']:.2f} | "
                f"spread={context['spread']:.3f} | vwap_Δ={context['vwap_change']:+.3f}% | "
                f"imbalance={context['imbalance']:+.2f} | velocity={context['velocity']:.2f}/s | "
                f"regime={context['regime']}\n\n"
                "Analyse the microstructure data above and generate 2–4 orders for a crypto "
                "order matching engine. Respond with ONLY a JSON array — no prose, no markdown:\n"
                '[{"side":"buy"|"sell","price":<float>,"quantity":<float>},...]\n'
                "Rules: price within ±1.5% of mid; quantity 0.1–8.0"
            )

            client = AsyncGroq(api_key=GROQ_API_KEY)
            resp   = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an autonomous trading agent embedded in a crypto order "
                            "matching engine. Given market microstructure data you generate "
                            "realistic, strategically sound orders. "
                            "Respond ONLY with a valid JSON array. No text outside the array."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
                temperature=0.35,
            )

            raw = resp.choices[0].message.content.strip()
            # Robustly extract the JSON array even if the LLM adds surrounding text
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if not match:
                return []
            orders = json.loads(match.group())
            return [
                o for o in orders
                if isinstance(o, dict)
                and o.get("side") in ("buy", "sell")
                and isinstance(o.get("price"), (int, float))
                and isinstance(o.get("quantity"), (int, float))
            ]

        except Exception as exc:
            logger.warning("Groq order generation failed: %s", exc)
            return []

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _submit(self, engine, side: str, price: float, qty: float):
        try:
            price = max(0.01, round(price, 2))
            qty   = max(0.01, round(qty,   2))
            return engine.submit_order("groq_agent", side, price, qty)
        except Exception as exc:
            logger.debug("AI submit error: %s", exc)
            return None

    # ── Main loop ───────────────────────────────────────────────────────────

    async def _run(self):
        from app.engine.matching_engine import get_engine
        from app.api.ws_manager import manager as ws_manager
        from app.demo.runner import get_runner as get_rule_runner

        engine        = get_engine()
        GROQ_INTERVAL = 4.0   # seconds — keeps well within free-tier rate limits

        try:
            while self._running:
                self.tick += 1

                # ── Snapshot current market state ───────────────────────────
                ob      = engine.get_order_book(depth=5)
                metrics = engine.get_metrics()

                bids = ob.get("bids", [])
                asks = ob.get("asks", [])
                if not bids or not asks:
                    await asyncio.sleep(GROQ_INTERVAL)
                    continue

                best_bid = bids[0]["price"]
                best_ask = asks[0]["price"]
                mid      = (best_bid + best_ask) / 2
                spread   = best_ask - best_bid

                # Borrow regime + price context from rule-based runner
                rule = get_rule_runner()
                regime      = rule.regime    if rule.running else "ranging"
                rule_mid    = rule.mid_price if rule.running else mid
                vwap_change = (mid - rule_mid) / max(rule_mid, 1e-8) * 100

                context = {
                    "mid":         mid,
                    "bid":         best_bid,
                    "ask":         best_ask,
                    "spread":      spread,
                    "vwap_change": round(vwap_change, 4),
                    "imbalance":   len(bids) - len(asks),
                    "velocity":    metrics.get("trades_executed", 0) / max(self.tick, 1),
                    "regime":      regime,
                }

                # ── Ask Groq for orders ─────────────────────────────────────
                raw_orders = await self._ask_groq(context)

                results = []
                action_parts = []

                for o in raw_orders:
                    side  = o["side"]
                    price = float(o["price"])
                    qty   = float(o["quantity"])

                    # Safety clamp — never deviate more than 2% from mid
                    price = max(mid * 0.98, min(mid * 1.02, price))
                    qty   = max(0.10, min(8.0, qty))

                    result = self._submit(engine, side, price, qty)
                    if result:
                        results.append(result)
                        action_parts.append(f"{side.upper()} {qty:.1f}@{price:.2f}")

                if action_parts:
                    self.last_action = " | ".join(action_parts)
                    self.last_reason = f"regime={regime} vwap_Δ={vwap_change:+.3f}%"
                    logger.info("Groq agent placed: %s", self.last_action)

                # ── Broadcast results ───────────────────────────────────────
                try:
                    for r in results:
                        if r and getattr(r, "trades", None):
                            await ws_manager.broadcast("trade_executed", r.to_dict())
                    await ws_manager.broadcast("orderbook_update", engine.get_order_book(depth=15))
                except Exception:
                    pass

                await asyncio.sleep(GROQ_INTERVAL)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("AI demo runner crashed: %s", exc)
            self._running = False


# ── Module-level singleton ───────────────────────────────────────────────────

_ai_runner = AIRunner()


def get_ai_runner() -> AIRunner:
    return _ai_runner
