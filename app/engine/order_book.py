"""
Order Book - In-memory data structure for buy and sell orders
Uses heap-based priority queues for O(1) best price lookup
"""
import heapq
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
from uuid import uuid4


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """Represents a trading order"""
    order_id: str
    user_id: str
    side: Side
    price: float
    quantity: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    remaining_qty: float = field(init=False)
    
    def __post_init__(self):
        self.remaining_qty = self.quantity
    
    def fill(self, qty: float) -> None:
        """Fill order with given quantity"""
        self.remaining_qty -= qty
    
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.remaining_qty <= 0
    
    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "side": self.side.value,
            "price": self.price,
            "quantity": self.quantity,
            "remaining_qty": self.remaining_qty,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class PriceLevel:
    """Orders at a specific price level (FIFO queue)"""
    price: float
    orders: List[Order] = field(default_factory=list)
    
    def add_order(self, order: Order) -> None:
        """Add order to this price level (time priority - FIFO)"""
        self.orders.append(order)
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """Remove order by ID"""
        for i, order in enumerate(self.orders):
            if order.order_id == order_id:
                return self.orders.pop(i)
        return None
    
    def peek_first(self) -> Optional[Order]:
        """Get first order without removing"""
        return self.orders[0] if self.orders else None
    
    def pop_first(self) -> Optional[Order]:
        """Remove and return first order"""
        return self.orders.pop(0) if self.orders else None
    
    def is_empty(self) -> bool:
        return len(self.orders) == 0
    
    def total_quantity(self) -> float:
        return sum(o.remaining_qty for o in self.orders)


class BuyHeapItem:
    """Wrapper for buy orders in max heap (negate price for max behavior)"""
    def __init__(self, price_level: PriceLevel):
        self.price_level = price_level
    
    def __lt__(self, other):
        # Higher price has higher priority for buys
        return self.price_level.price > other.price_level.price


class SellHeapItem:
    """Wrapper for sell orders in min heap"""
    def __init__(self, price_level: PriceLevel):
        self.price_level = price_level
    
    def __lt__(self, other):
        # Lower price has higher priority for sells
        return self.price_level.price < other.price_level.price


class OrderBook:
    """
    In-memory order book with heap-based price level management
    
    Buy side: Max heap (highest price first)
    Sell side: Min heap (lowest price first)
    """
    
    def __init__(self, symbol: str = "DEFAULT"):
        self.symbol = symbol
        self._lock = threading.RLock()
        
        # Heap storage
        self._buy_heap: List[BuyHeapItem] = []
        self._sell_heap: List[SellHeapItem] = []
        
        # Price level lookup for O(1) access
        self._buy_levels: Dict[float, PriceLevel] = {}
        self._sell_levels: Dict[float, PriceLevel] = {}
        
        # Order lookup
        self._orders: Dict[str, Order] = {}
    
    def add_order(self, order: Order) -> None:
        """Add order to the book"""
        with self._lock:
            self._orders[order.order_id] = order
            
            if order.side == Side.BUY:
                self._add_to_buy_side(order)
            else:
                self._add_to_sell_side(order)
    
    def _add_to_buy_side(self, order: Order) -> None:
        """Add order to buy side"""
        if order.price in self._buy_levels:
            self._buy_levels[order.price].add_order(order)
        else:
            level = PriceLevel(price=order.price)
            level.add_order(order)
            self._buy_levels[order.price] = level
            heapq.heappush(self._buy_heap, BuyHeapItem(level))
    
    def _add_to_sell_side(self, order: Order) -> None:
        """Add order to sell side"""
        if order.price in self._sell_levels:
            self._sell_levels[order.price].add_order(order)
        else:
            level = PriceLevel(price=order.price)
            level.add_order(order)
            self._sell_levels[order.price] = level
            heapq.heappush(self._sell_heap, SellHeapItem(level))
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """Remove order from book"""
        with self._lock:
            order = self._orders.pop(order_id, None)
            if not order:
                return None
            
            if order.side == Side.BUY:
                level = self._buy_levels.get(order.price)
                if level:
                    level.remove_order(order_id)
            else:
                level = self._sell_levels.get(order.price)
                if level:
                    level.remove_order(order_id)
            
            return order
    
    def get_best_bid(self) -> Optional[PriceLevel]:
        """Get best (highest) buy price level"""
        self._clean_empty_levels(self._buy_heap, self._buy_levels)
        if self._buy_heap:
            return self._buy_heap[0].price_level
        return None
    
    def get_best_ask(self) -> Optional[PriceLevel]:
        """Get best (lowest) sell price level"""
        self._clean_empty_levels(self._sell_heap, self._sell_levels)
        if self._sell_heap:
            return self._sell_heap[0].price_level
        return None
    
    def _clean_empty_levels(self, heap: list, levels: dict) -> None:
        """Remove empty price levels from heap"""
        while heap and heap[0].price_level.is_empty():
            item = heapq.heappop(heap)
            levels.pop(item.price_level.price, None)
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return self._orders.get(order_id)
    
    def get_snapshot(self, depth: int = 10) -> dict:
        """Get order book snapshot"""
        with self._lock:
            # Clean empty levels
            self._clean_empty_levels(self._buy_heap, self._buy_levels)
            self._clean_empty_levels(self._sell_heap, self._sell_levels)
            
            # Get bid levels (sorted by price descending)
            bids = []
            buy_prices = sorted(self._buy_levels.keys(), reverse=True)[:depth]
            for price in buy_prices:
                level = self._buy_levels[price]
                if not level.is_empty():
                    bids.append({
                        "price": price,
                        "quantity": level.total_quantity(),
                        "orders": len(level.orders)
                    })
            
            # Get ask levels (sorted by price ascending)
            asks = []
            sell_prices = sorted(self._sell_levels.keys())[:depth]
            for price in sell_prices:
                level = self._sell_levels[price]
                if not level.is_empty():
                    asks.append({
                        "price": price,
                        "quantity": level.total_quantity(),
                        "orders": len(level.orders)
                    })
            
            return {
                "symbol": self.symbol,
                "bids": bids,
                "asks": asks,
                "bid_count": len(self._buy_levels),
                "ask_count": len(self._sell_levels)
            }
    
    def get_spread(self) -> Optional[float]:
        """Get bid-ask spread"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return None


def create_order(user_id: str, side: str, price: float, quantity: float) -> Order:
    """Factory function to create orders"""
    return Order(
        order_id=str(uuid4()),
        user_id=user_id,
        side=Side(side.lower()),
        price=price,
        quantity=quantity
    )
