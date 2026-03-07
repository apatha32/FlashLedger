"""
API Routes for FlashLedger
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.matching_engine import get_engine, MatchResult, Trade
from app.db.database import get_db
from app.db import models

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


# ============ API Endpoints ============

@router.post("/order", response_model=OrderResponse)
async def submit_order(request: OrderRequest, db: AsyncSession = Depends(get_db)):
    """
    Submit a new order
    
    The order will be matched against the order book using price-time priority.
    If matched, trades will be executed and persisted to the database.
    """
    engine = get_engine()
    
    # Submit order to matching engine
    result: MatchResult = engine.submit_order(
        user_id=request.user_id,
        side=request.side,
        price=request.price,
        quantity=request.quantity
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
            timestamp=trade.timestamp
        )
        db.add(db_trade)
    
    if result.trades:
        await db.commit()
    
    return result.to_dict()


@router.get("/orderbook", response_model=OrderBookResponse)
async def get_orderbook(depth: int = 10):
    """
    Get current order book snapshot
    
    Returns bid and ask levels sorted by price.
    Bids: highest price first
    Asks: lowest price first
    """
    engine = get_engine()
    return engine.get_order_book(depth=depth)


@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(limit: int = 100, db: AsyncSession = Depends(get_db)):
    """
    Get recent executed trades from database
    """
    from sqlalchemy import select
    
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
            "timestamp": t.timestamp.isoformat()
        }
        for t in trades
    ]


@router.delete("/order/{order_id}")
async def cancel_order(order_id: str):
    """
    Cancel an existing order
    """
    engine = get_engine()
    order = engine.cancel_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order_id": order_id,
        "status": "cancelled"
    }


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Get matching engine metrics
    """
    engine = get_engine()
    return engine.get_metrics()


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "service": "flashledger"}
