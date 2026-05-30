"""
FlashLedger Demo Runner
========================
Simulates a realistic crypto order book with multiple agent types and
automatic regime transitions. Designed to make the frontend look alive
without requiring real users.

Agents
------
  mm_alpha / mm_beta   — Market makers posting resting bid/ask orders
  trend_{1-6}          — Trend followers that cross the spread aggressively
  noise_{1-4}          — Noise traders placing random small orders
  whale                — Large aggressive orders during regime transitions
  panic_seller         — Active only during flash-crash regime

Regimes (auto-cycle)
--------------------
  ranging      →  gentle random walk, balanced order flow
  bull         →  upward drift, aggressive buyers, whale buy pressure
  bear         →  downward drift, aggressive sellers
  high_vol     →  volatile price, wide spreads, erratic flow
  flash_crash  →  sharp 5-tick dump, then snaps back to ranging
"""

import asyncio
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

# ── Regime definitions ──────────────────────────────────────────────────────

SCENARIOS = {
    "ranging":     {"drift":  0.0000, "vol_mult": 1.0, "aggression": 0.30},
    "bull":        {"drift":  0.0018, "vol_mult": 1.5, "aggression": 0.65},
    "bear":        {"drift": -0.0018, "vol_mult": 1.5, "aggression": 0.65},
    "high_vol":    {"drift":  0.0000, "vol_mult": 2.8, "aggression": 0.50},
    "flash_crash": {"drift": -0.009,  "vol_mult": 4.5, "aggression": 0.85},
}

REGIME_TRANSITIONS = {
    "ranging":     ["ranging", "ranging", "bull", "bear", "high_vol"],
    "bull":        ["bull", "ranging", "ranging", "high_vol"],
    "bear":        ["bear", "ranging", "ranging", "high_vol"],
    "high_vol":    ["ranging", "bull", "bear"],
    "flash_crash": ["ranging", "ranging"],
}


# ── Demo Runner ─────────────────────────────────────────────────────────────

class DemoRunner:
    def __init__(self):
        self._task:            Optional[asyncio.Task] = None
        self._running:         bool  = False
        self.regime:           str   = "ranging"
        self.mid_price:        float = 100.0
        self.tick:             int   = 0
        self.regime_tick:      int   = 0
        self.regime_duration:  int   = 40

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    @property
    def status(self) -> dict:
        return {
            "running":   self._running,
            "regime":    self.regime,
            "mid_price": round(self.mid_price, 2),
            "tick":      self.tick,
            "regime_tick_remaining": max(0, self.regime_duration - self.regime_tick),
        }

    def start(self):
        if self._running:
            return
        self._running    = True
        self.mid_price   = 100.0
        self.tick        = 0
        self.regime      = "ranging"
        self.regime_tick = 0
        self._task       = asyncio.create_task(self._run())
        logger.info("Demo runner started")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Demo runner stopped")

    # ── Internal helpers ────────────────────────────────────────────────────

    def _submit(self, engine, user_id: str, side: str, price: float, qty: float):
        """Submit one order directly to the matching engine; return MatchResult or None."""
        try:
            price = max(0.01, round(price, 2))
            qty   = max(0.01, round(qty,   2))
            return engine.submit_order(user_id, side, price, qty)
        except Exception as exc:
            logger.debug("Demo order error (%s %s %.2f@%.2f): %s", user_id, side, qty, price, exc)
            return None

    async def _broadcast_all(self, engine, trade_results: list):
        """Push orderbook, metrics, and any trades to all WS clients."""
        from app.api.ws_manager import manager as ws_manager
        try:
            # Broadcast individual trade events (feeds TradeFeed + PriceChart)
            for result in trade_results:
                if result and result.trades:
                    await ws_manager.broadcast("trade_executed", result.to_dict())

            # Snapshot update every tick
            await ws_manager.broadcast("orderbook_update", engine.get_order_book(depth=15))
            await ws_manager.broadcast("metrics_update",   engine.get_metrics())
        except Exception as exc:
            logger.debug("Demo broadcast error: %s", exc)

    # ── Main simulation loop ─────────────────────────────────────────────────

    async def _run(self):
        from app.engine.matching_engine import get_engine

        engine        = get_engine()
        BASE_SPREAD   = 0.20     # baseline half-spread
        BASE_VOL      = 0.003    # per-tick volatility (fraction of price)
        TICK_INTERVAL = 0.4      # seconds between ticks

        try:
            while self._running:
                self.tick        += 1
                self.regime_tick += 1
                sc                = SCENARIOS[self.regime]
                results           = []

                # ── Price model: GBM with regime drift ─────────────────────
                drift = sc["drift"]
                vol   = BASE_VOL * sc["vol_mult"]
                self.mid_price *= (1 + random.gauss(drift, vol))
                self.mid_price  = max(40.0, min(300.0, self.mid_price))
                mid    = self.mid_price
                spread = BASE_SPREAD * sc["vol_mult"] * random.uniform(0.8, 1.2)
                bid    = mid - spread / 2
                ask    = mid + spread / 2

                # ── Market Maker α — tight resting orders ──────────────────
                mm_qty = round(random.uniform(2, 8), 2)
                results.append(self._submit(engine, "mm_alpha", "buy",  bid, mm_qty))
                results.append(self._submit(engine, "mm_alpha", "sell", ask, mm_qty))

                # ── Market Maker β — slightly wider ────────────────────────
                results.append(self._submit(engine, "mm_beta", "buy",  bid * 0.999,
                                            round(random.uniform(1, 4), 2)))
                results.append(self._submit(engine, "mm_beta", "sell", ask * 1.001,
                                            round(random.uniform(1, 4), 2)))

                # ── Trend follower: crosses spread based on regime ──────────
                if random.random() < sc["aggression"]:
                    if self.regime == "bull":
                        t_side = "buy"
                    elif self.regime == "bear":
                        t_side = "sell"
                    else:
                        t_side = random.choice(["buy", "sell"])

                    t_price = ask + 0.01 if t_side == "buy" else bid - 0.01
                    t_qty   = round(random.uniform(0.5, 4.0), 2)
                    trader  = f"trend_{random.randint(1, 6)}"
                    results.append(self._submit(engine, trader, t_side, t_price, t_qty))

                # ── Second aggressive order (high vol / flash crash) ────────
                if sc["aggression"] > 0.60 and random.random() < 0.4:
                    extra_side  = "sell" if self.regime in ("flash_crash", "bear") else "buy"
                    extra_price = bid - 0.05 if extra_side == "sell" else ask + 0.05
                    results.append(self._submit(engine, f"trend_{random.randint(7, 10)}",
                                                extra_side, extra_price,
                                                round(random.uniform(1, 6), 2)))

                # ── Noise traders ───────────────────────────────────────────
                if random.random() < 0.35:
                    n_side  = random.choice(["buy", "sell"])
                    n_price = mid + random.gauss(0, spread * 1.5)
                    results.append(self._submit(engine, f"noise_{random.randint(1, 4)}",
                                                n_side, n_price,
                                                round(random.uniform(0.1, 1.5), 2)))

                # ── Whale burst at regime start ─────────────────────────────
                if self.regime_tick <= 4:
                    for _ in range(random.randint(1, 3)):
                        w_side  = "buy" if self.regime == "bull" else "sell"
                        w_price = ask + 0.05 if w_side == "buy" else bid - 0.05
                        results.append(self._submit(engine, "whale", w_side, w_price,
                                                    round(random.uniform(8, 25), 2)))

                # ── Flash crash: panic dump ─────────────────────────────────
                if self.regime == "flash_crash" and self.regime_tick <= 5:
                    results.append(self._submit(engine, "panic_seller", "sell",
                                                bid - 1.5,
                                                round(random.uniform(15, 40), 2)))

                # ── Broadcast to all WebSocket clients ──────────────────────
                await self._broadcast_all(engine, results)

                # ── Regime transition ───────────────────────────────────────
                if self.regime_tick >= self.regime_duration:
                    self.regime          = random.choice(REGIME_TRANSITIONS[self.regime])
                    self.regime_tick     = 0
                    self.regime_duration = random.randint(20, 70)
                    logger.info("Demo → regime: %s  (duration: %d ticks)",
                                self.regime, self.regime_duration)

                await asyncio.sleep(TICK_INTERVAL)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Demo runner crashed: %s", exc)
            self._running = False


# ── Module-level singleton ───────────────────────────────────────────────────

_runner = DemoRunner()


def get_runner() -> DemoRunner:
    return _runner
