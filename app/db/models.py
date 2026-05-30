"""
Database models for FlashLedger
Only executed trades are persisted (order book stays in memory)
"""
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Trade(Base):
    """
    Executed trade record
    
    Persisted to PostgreSQL for historical record keeping
    """
    __tablename__ = "trades"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    buy_order_id: Mapped[str] = mapped_column(String(36), index=True)
    sell_order_id: Mapped[str] = mapped_column(String(36), index=True)
    buyer_id: Mapped[str] = mapped_column(String(255), index=True)
    seller_id: Mapped[str] = mapped_column(String(255), index=True)
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_trades_timestamp_desc', timestamp.desc()),
        Index('idx_trades_buyer_seller', buyer_id, seller_id),
    )
    
    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "buy_order_id": self.buy_order_id,
            "sell_order_id": self.sell_order_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "price": self.price,
            "quantity": self.quantity,
            "timestamp": self.timestamp.isoformat()
        }


class MarketFeature(Base):
    """
    Computed market microstructure features written by the PySpark pipeline.
    Each row represents one 10-second feature window.
    """
    __tablename__ = "market_features"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    trade_volume: Mapped[float] = mapped_column(Float, default=0.0)
    vwap: Mapped[float] = mapped_column(Float, default=0.0)
    order_imbalance: Mapped[float] = mapped_column(Float, default=0.0)
    trade_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_mf_window_start_desc", window_start.desc()),
    )

    def to_dict(self) -> dict:
        return {
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "trade_volume": self.trade_volume,
            "vwap": self.vwap,
            "order_imbalance": self.order_imbalance,
            "trade_velocity": self.trade_velocity,
        }
