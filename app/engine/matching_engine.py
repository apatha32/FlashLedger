"""
Matching Engine - Core order matching logic with price-time priority
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Callable
from uuid import uuid4

from app.engine.order_book import OrderBook, Order, Side, create_order


@dataclass
class Trade:
    """Represents an executed trade"""
    trade_id: str
    buy_order_id: str
    sell_order_id: str
    buyer_id: str
    seller_id: str
    price: float
    quantity: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
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


@dataclass
class MatchResult:
    """Result of order submission"""
    order: Order
    trades: List[Trade]
    status: str  # "matched", "partial", "resting", "rejected"
    latency_ms: float
    
    def to_dict(self) -> dict:
        return {
            "order_id": self.order.order_id,
            "order_status": self.status,
            "trades": [t.to_dict() for t in self.trades],
            "remaining_qty": self.order.remaining_qty,
            "latency_ms": round(self.latency_ms, 3)
        }


class MatchingEngine:
    """
    Order matching engine with price-time priority
    
    Matching Rules:
    - Buy orders match if buy_price >= best_ask_price
    - Sell orders match if sell_price <= best_bid_price
    - Trade executes at the resting (maker) order's price
    - Orders at same price are matched FIFO (time priority)
    """
    
    def __init__(self, symbol: str = "DEFAULT"):
        self.symbol = symbol
        self.order_book = OrderBook(symbol)
        self._trade_callbacks: List[Callable[[Trade], None]] = []
        
        # Metrics
        self.orders_processed = 0
        self.trades_executed = 0
        self.total_latency_ns = 0
    
    def register_trade_callback(self, callback: Callable[[Trade], None]) -> None:
        """Register callback for trade execution (for DB persistence)"""
        self._trade_callbacks.append(callback)
    
    def submit_order(self, user_id: str, side: str, price: float, quantity: float) -> MatchResult:
        """
        Submit an order to the matching engine
        
        Returns MatchResult with order status and any executed trades
        """
        start_time = time.perf_counter_ns()
        
        # Create order
        order = create_order(user_id, side, price, quantity)
        
        # Match order
        trades = self._match_order(order)
        
        # Calculate latency
        latency_ns = time.perf_counter_ns() - start_time
        latency_ms = latency_ns / 1_000_000
        
        # Update metrics
        self.orders_processed += 1
        self.total_latency_ns += latency_ns
        
        # Determine status
        if order.is_filled():
            status = "matched"
        elif trades:
            status = "partial"
        else:
            status = "resting"
        
        return MatchResult(
            order=order,
            trades=trades,
            status=status,
            latency_ms=latency_ms
        )
    
    def _match_order(self, incoming: Order) -> List[Trade]:
        """
        Core matching algorithm
        
        For buy orders: match against sell side if buy_price >= best_ask
        For sell orders: match against buy side if sell_price <= best_bid
        """
        trades = []
        
        if incoming.side == Side.BUY:
            trades = self._match_buy_order(incoming)
        else:
            trades = self._match_sell_order(incoming)
        
        # If order not fully filled, add to book
        if not incoming.is_filled():
            self.order_book.add_order(incoming)
        
        return trades
    
    def _match_buy_order(self, incoming: Order) -> List[Trade]:
        """Match incoming buy order against sell side"""
        trades = []
        
        while not incoming.is_filled():
            # Get best ask (lowest sell price)
            best_ask = self.order_book.get_best_ask()
            
            if not best_ask:
                break  # No sells available
            
            # Check if prices cross: buy_price >= sell_price
            if incoming.price < best_ask.price:
                break  # No match possible
            
            # Match with orders at this price level (FIFO)
            while not incoming.is_filled() and not best_ask.is_empty():
                resting = best_ask.peek_first()
                
                # Calculate fill quantity
                fill_qty = min(incoming.remaining_qty, resting.remaining_qty)
                
                # Execute trade at resting order's price
                trade = self._execute_trade(
                    buy_order=incoming,
                    sell_order=resting,
                    price=resting.price,
                    quantity=fill_qty
                )
                trades.append(trade)
                
                # Update orders
                incoming.fill(fill_qty)
                resting.fill(fill_qty)
                
                # Remove filled resting order
                if resting.is_filled():
                    best_ask.pop_first()
                    self.order_book._orders.pop(resting.order_id, None)
            
            # Clean up empty price level
            if best_ask.is_empty():
                self.order_book._sell_levels.pop(best_ask.price, None)
        
        return trades
    
    def _match_sell_order(self, incoming: Order) -> List[Trade]:
        """Match incoming sell order against buy side"""
        trades = []
        
        while not incoming.is_filled():
            # Get best bid (highest buy price)
            best_bid = self.order_book.get_best_bid()
            
            if not best_bid:
                break  # No buys available
            
            # Check if prices cross: sell_price <= buy_price
            if incoming.price > best_bid.price:
                break  # No match possible
            
            # Match with orders at this price level (FIFO)
            while not incoming.is_filled() and not best_bid.is_empty():
                resting = best_bid.peek_first()
                
                # Calculate fill quantity
                fill_qty = min(incoming.remaining_qty, resting.remaining_qty)
                
                # Execute trade at resting order's price
                trade = self._execute_trade(
                    buy_order=resting,
                    sell_order=incoming,
                    price=resting.price,
                    quantity=fill_qty
                )
                trades.append(trade)
                
                # Update orders
                incoming.fill(fill_qty)
                resting.fill(fill_qty)
                
                # Remove filled resting order
                if resting.is_filled():
                    best_bid.pop_first()
                    self.order_book._orders.pop(resting.order_id, None)
            
            # Clean up empty price level
            if best_bid.is_empty():
                self.order_book._buy_levels.pop(best_bid.price, None)
        
        return trades
    
    def _execute_trade(self, buy_order: Order, sell_order: Order, price: float, quantity: float) -> Trade:
        """Execute a trade between two orders"""
        trade = Trade(
            trade_id=str(uuid4()),
            buy_order_id=buy_order.order_id,
            sell_order_id=sell_order.order_id,
            buyer_id=buy_order.user_id,
            seller_id=sell_order.user_id,
            price=price,
            quantity=quantity
        )
        
        # Update metrics
        self.trades_executed += 1
        
        # Notify callbacks (for DB persistence)
        for callback in self._trade_callbacks:
            try:
                callback(trade)
            except Exception as e:
                print(f"Trade callback error: {e}")
        
        return trade
    
    def cancel_order(self, order_id: str) -> Optional[Order]:
        """Cancel an existing order"""
        return self.order_book.remove_order(order_id)
    
    def get_order_book(self, depth: int = 10) -> dict:
        """Get order book snapshot"""
        return self.order_book.get_snapshot(depth)
    
    def get_metrics(self) -> dict:
        """Get engine metrics"""
        avg_latency_ms = 0
        if self.orders_processed > 0:
            avg_latency_ms = (self.total_latency_ns / self.orders_processed) / 1_000_000
        
        return {
            "symbol": self.symbol,
            "orders_processed": self.orders_processed,
            "trades_executed": self.trades_executed,
            "avg_latency_ms": round(avg_latency_ms, 3),
            "spread": self.order_book.get_spread()
        }


# Global engine instance
_engine: Optional[MatchingEngine] = None


def get_engine() -> MatchingEngine:
    """Get global engine instance"""
    global _engine
    if _engine is None:
        _engine = MatchingEngine(symbol="FLASH")
    return _engine
