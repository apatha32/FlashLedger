"""
API Routes for FlashLedger
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.engine.matching_engine import get_engine, MatchResult, Trade
from app.db.database import get_db
from app.db import models
from app.kafka import producer as kafka
from app.api.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Request/Response Models ============

class OrderRequest(BaseModel):
    """Order submission request"""
    user_id: str = Field(..., description="User identifier")
    side: str = Field(..., pattern="^(buy|sell)$", description="Order side: buy or sell")
    price: float = Field(..., gt=0, description="Order price (must be positive)")
    quantity: float = Field(..., gt=0, description="Order quantity (must be positive)")


class TradeResponse(BaseModel):
    """Trade information"""
    trade_id: str
    buy_order_id: str
    sell_order_id: str
    buyer_id: str
    seller_id: str
    price: float
    quantity: float
    timestamp: str


class OrderResponse(BaseModel):
    """Order submission response"""
    order_id: str
    order_status: str
    trades: List[dict]
    remaining_qty: float
    latency_ms: float


class OrderBookLevel(BaseModel):
    """Single price level in order book"""
    price: float
    quantity: float
    orders: int


class OrderBookResponse(BaseModel):
    """Order book snapshot"""
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    bid_count: int
    ask_count: int


class MetricsResponse(BaseModel):
    """Engine metrics"""
    symbol: str
    orders_processed: int
    trades_executed: int
    avg_latency_ms: float
    spread: Optional[float]


class PredictionResponse(BaseModel):
    """ML model prediction"""
    direction: str       # "up" or "down"
    confidence: float    # 0.0 – 1.0
    model: str           # "lstm" or "heuristic"
    window_rows: int


class InsightsResponse(BaseModel):
    """Market insight recommendation from LightGBM recommender"""
    action: str                    # BUY / SELL / HOLD
    confidence: float
    regime: str                    # TRENDING_UP / TRENDING_DOWN / RANGING / HIGH_VOLATILITY
    probabilities: dict            # {sell, hold, buy}
    insights: List[str]            # natural-language bullets
    similar_conditions: List[dict] # KNN matches from training history
    rsi: float
    feature_values: dict
    ai_commentary: Optional[str] = None  # Groq LLM narrative


class ChatRequest(BaseModel):
    """Freeform question for the Groq AI assistant"""
    message: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    """AI assistant reply"""
    reply: str
    model: str


# ============ API Endpoints ============

@router.post("/order", response_model=OrderResponse)
async def submit_order(request: OrderRequest, db: AsyncSession = Depends(get_db)):
    """Submit a new order — matches against the book, persists trades, and broadcasts events."""
    engine = get_engine()

    # Publish raw order event to Kafka "orders" topic
    kafka.publish("orders", {
        "user_id": request.user_id,
        "side": request.side,
        "price": request.price,
        "quantity": request.quantity,
    })

    # Submit order to matching engine
    result: MatchResult = engine.submit_order(
        user_id=request.user_id,
        side=request.side,
        price=request.price,
        quantity=request.quantity,
    )

    # Persist trades to database
    for trade in result.trades:
        db_trade = models.Trade(
            trade_id=trade.trade_id,
            buy_order_id=trade.buy_order_id,
            sell_order_id=trade.sell_order_id,
            buyer_id=trade.buyer_id,
            seller_id=trade.seller_id,
            price=trade.price,
            quantity=trade.quantity,
            timestamp=trade.timestamp,
        )
        db.add(db_trade)

    if result.trades:
        await db.commit()

    response_dict = result.to_dict()

    # Broadcast to WebSocket clients
    await ws_manager.broadcast("trade_executed", response_dict)
    await ws_manager.broadcast("orderbook_update", engine.get_order_book(depth=15))

    return response_dict


@router.get("/orderbook", response_model=OrderBookResponse)
async def get_orderbook(depth: int = 10):
    """Get current order book snapshot (bids highest-first, asks lowest-first)."""
    engine = get_engine()
    return engine.get_order_book(depth=depth)


@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Get recent executed trades from database."""
    stmt = select(models.Trade).order_by(models.Trade.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    trades = result.scalars().all()
    return [
        {
            "trade_id": t.trade_id,
            "buy_order_id": t.buy_order_id,
            "sell_order_id": t.sell_order_id,
            "buyer_id": t.buyer_id,
            "seller_id": t.seller_id,
            "price": t.price,
            "quantity": t.quantity,
            "timestamp": t.timestamp.isoformat(),
        }
        for t in trades
    ]


@router.delete("/order/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an existing resting order."""
    engine = get_engine()
    order = engine.cancel_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order_id": order_id, "status": "cancelled"}


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get matching engine performance metrics."""
    engine = get_engine()
    return engine.get_metrics()


@router.get("/prediction", response_model=PredictionResponse)
async def get_prediction(db: AsyncSession = Depends(get_db)):
    """
    Return an LSTM price-direction prediction based on the last 20 feature windows.
    Falls back to a heuristic prediction if the model or sufficient data is unavailable.
    """
    try:
        from ml import predict as ml_predict
        stmt = (
            select(models.MarketFeature)
            .order_by(models.MarketFeature.window_start.desc())
            .limit(20)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        if len(rows) >= 5:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "trade_volume": r.trade_volume,
                    "vwap": r.vwap,
                    "order_imbalance": r.order_imbalance,
                    "trade_velocity": r.trade_velocity,
                }
                for r in reversed(rows)  # chronological order
            ])
            direction, confidence = ml_predict.get_prediction(df)
            return PredictionResponse(
                direction=direction,
                confidence=round(confidence, 4),
                model="lstm",
                window_rows=len(rows),
            )
    except Exception as exc:
        logger.warning("ML prediction failed, falling back to heuristic: %s", exc)

    # Heuristic fallback: use recent trade momentum
    try:
        stmt = select(models.Trade).order_by(models.Trade.timestamp.desc()).limit(20)
        result = await db.execute(stmt)
        recent = result.scalars().all()
        if len(recent) >= 2:
            prices = [t.price for t in reversed(recent)]
            momentum = (prices[-1] - prices[0]) / (prices[0] or 1)
            direction = "up" if momentum >= 0 else "down"
            confidence = min(0.5 + abs(momentum) * 10, 0.85)
            return PredictionResponse(
                direction=direction,
                confidence=round(confidence, 4),
                model="heuristic",
                window_rows=len(recent),
            )
    except Exception as exc:
        logger.warning("Heuristic prediction failed: %s", exc)

    return PredictionResponse(direction="up", confidence=0.5, model="heuristic", window_rows=0)


@router.get("/insights", response_model=InsightsResponse)
async def get_insights(db: AsyncSession = Depends(get_db)):
    """
    Market insight recommendation from the trained LightGBM recommender.
    Uses the last 50 rows of market_features; falls back to a heuristic
    derived from recent trades if the model or sufficient data is absent.
    """
    import pandas as pd

    # Try to load market_features rows
    try:
        stmt = (
            select(models.MarketFeature)
            .order_by(models.MarketFeature.window_start.desc())
            .limit(50)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
    except Exception:
        rows = []

    # Fall back to synthetic features derived from recent trades when Spark
    # pipeline hasn't produced market_features rows yet
    if len(rows) < 3:
        try:
            stmt2 = select(models.Trade).order_by(models.Trade.timestamp.desc()).limit(60)
            result2 = await db.execute(stmt2)
            trades = result2.scalars().all()
            if len(trades) < 3:
                raise ValueError("insufficient trade data")
            trade_df = pd.DataFrame(
                [{"price": t.price, "quantity": t.quantity, "timestamp": t.timestamp} for t in reversed(trades)]
            )
            trade_df["vwap"]            = trade_df["price"]
            trade_df["trade_volume"]    = trade_df["quantity"]
            trade_df["order_imbalance"] = trade_df["quantity"] * trade_df["price"].diff().fillna(0).apply(lambda x: 1 if x >= 0 else -1)
            trade_df["trade_velocity"]  = 1.0
            df = trade_df[["trade_volume", "vwap", "order_imbalance", "trade_velocity"]]
        except Exception as exc:
            logger.warning("Insights fallback failed: %s", exc)
            return InsightsResponse(
                action="HOLD", confidence=0.5, regime="RANGING",
                probabilities={"sell": 0.25, "hold": 0.5, "buy": 0.25},
                insights=["Insufficient market data — submit orders to generate signals."],
                similar_conditions=[], rsi=50.0,
                feature_values={"vwap_change": 0, "volume_ratio": 1, "imbalance_norm": 0,
                                "velocity_change": 0, "volatility": 0},
            )
    else:
        df = pd.DataFrame([r.to_dict() for r in reversed(rows)])

    try:
        from ml import recommender
        from app.ai import groq_client
        data = recommender.get_insights(df)
        data["ai_commentary"] = await groq_client.generate_commentary(data)
        return InsightsResponse(**data)
    except RuntimeError:
        # Model not yet trained — return heuristic regime + insights only
        logger.warning("Recommender model not found — returning heuristic insights")
        from ml import recommender as rec_mod
        # Still run feature engineering for natural-language insights even without model
        raw = rec_mod._engineer_features(df)
        regime  = rec_mod._classify_regime(raw)
        bullets = rec_mod._generate_insights(raw)
        rsi     = round(float(raw[0, 5]), 1)
        fv      = raw[0]
        return InsightsResponse(
            action="HOLD", confidence=0.5, regime=regime,
            probabilities={"sell": 0.33, "hold": 0.34, "buy": 0.33},
            insights=bullets or ["Train the recommender for ML-powered signals: python -m ml.train_recommender"],
            similar_conditions=[], rsi=rsi,
            feature_values={
                "vwap_change":     round(float(fv[0]) * 100, 3),
                "volume_ratio":    round(float(fv[1]), 2),
                "imbalance_norm":  round(float(fv[2]), 3),
                "velocity_change": round(float(fv[3]) * 100, 3),
                "volatility":      round(float(fv[4]) * 100, 3),
            },
        )
    except Exception as exc:
        logger.error("Insights endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail="Insights computation failed")


# ============ Demo Mode ============

@router.post("/demo/start")
async def demo_start():
    """Start the demo simulation (market makers + trend followers + regime changes)."""
    from app.demo.runner import get_runner
    runner = get_runner()
    runner.start()
    return {"status": "started", **runner.status}


@router.post("/demo/stop")
async def demo_stop():
    """Stop the demo simulation."""
    from app.demo.runner import get_runner
    runner = get_runner()
    runner.stop()
    return {"status": "stopped"}


@router.get("/demo/status")
async def demo_status():
    """Return the current demo runner state."""
    from app.demo.runner import get_runner
    return get_runner().status


@router.post("/demo/ai/start")
async def ai_demo_start():
    """Start the Groq AI trading agent (runs alongside the rule-based demo)."""
    from app.demo.ai_runner import get_ai_runner
    from app.ai.groq_client import GROQ_API_KEY
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="GROQ_API_KEY is not set. Add it to your .env file to enable AI demo.",
        )
    runner = get_ai_runner()
    runner.start()
    return {"status": "started", **runner.status}


@router.post("/demo/ai/stop")
async def ai_demo_stop():
    """Stop the Groq AI trading agent."""
    from app.demo.ai_runner import get_ai_runner
    runner = get_ai_runner()
    runner.stop()
    return {"status": "stopped"}


@router.get("/demo/ai/status")
async def ai_demo_status():
    """Return the current AI demo runner state."""
    from app.demo.ai_runner import get_ai_runner
    return get_ai_runner().status


# ============ Groq AI Chat ============

@router.post("/chat", response_model=ChatResponse)
async def ai_chat(request: ChatRequest):
    """
    Ask FlashLedger AI a question about the current market.
    Injects live orderbook, metrics, and latest ML signals as context.
    """
    from app.ai import groq_client

    engine = get_engine()
    metrics = engine.get_metrics()
    ob = engine.get_order_book(depth=3)

    best_bid = ob["bids"][0]["price"] if ob["bids"] else None
    best_ask = ob["asks"][0]["price"] if ob["asks"] else None

    context = {
        "symbol":           "FLASH/USD",
        "orders_processed": metrics["orders_processed"],
        "trades_executed":  metrics["trades_executed"],
        "avg_latency_ms":   metrics["avg_latency_ms"],
        "best_bid":         best_bid,
        "best_ask":         best_ask,
        "spread":           metrics.get("spread"),
    }

    reply = await groq_client.chat(request.message, context)
    return ChatResponse(reply=reply, model="llama-3.3-70b-versatile")


# ============ WebSocket ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time event stream for the frontend.
    Sends: orderbook_update, trade_executed, metrics_update
    Receives: ping → responds with pong
    """
    await ws_manager.connect(websocket)
    engine = get_engine()

    # Send initial state immediately
    await websocket.send_text(
        __import__("json").dumps({"type": "orderbook_update", "data": engine.get_order_book(depth=15)})
    )
    await websocket.send_text(
        __import__("json").dumps({"type": "metrics_update", "data": engine.get_metrics()})
    )

    try:
        while True:
            try:
                text = await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
                if text.strip() == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Heartbeat: push fresh metrics + order book every 3 s
                await websocket.send_text(
                    __import__("json").dumps({"type": "orderbook_update", "data": engine.get_order_book(depth=15)})
                )
                await websocket.send_text(
                    __import__("json").dumps({"type": "metrics_update", "data": engine.get_metrics()})
                )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "flashledger"}

