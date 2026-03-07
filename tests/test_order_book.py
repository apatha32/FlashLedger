"""
Unit tests for the Order Book
"""
import pytest
from app.engine.order_book import OrderBook, Order, Side, create_order


class TestOrderBook:
    """Tests for OrderBook data structure"""
    
    def setup_method(self):
        """Setup fresh order book for each test"""
        self.book = OrderBook(symbol="TEST")
    
    def test_create_order_book(self):
        """Test order book creation"""
        assert self.book.symbol == "TEST"
        assert self.book.get_best_bid() is None
        assert self.book.get_best_ask() is None
    
    def test_add_buy_order(self):
        """Test adding a buy order"""
        order = create_order("user1", "buy", 100.0, 10.0)
        self.book.add_order(order)
        
        best_bid = self.book.get_best_bid()
        assert best_bid is not None
        assert best_bid.price == 100.0
        assert best_bid.total_quantity() == 10.0
    
    def test_add_sell_order(self):
        """Test adding a sell order"""
        order = create_order("user1", "sell", 105.0, 20.0)
        self.book.add_order(order)
        
        best_ask = self.book.get_best_ask()
        assert best_ask is not None
        assert best_ask.price == 105.0
        assert best_ask.total_quantity() == 20.0
    
    def test_best_bid_max_heap(self):
        """Test that buy side returns highest price first"""
        self.book.add_order(create_order("user1", "buy", 99.0, 10.0))
        self.book.add_order(create_order("user2", "buy", 101.0, 10.0))
        self.book.add_order(create_order("user3", "buy", 100.0, 10.0))
        
        best_bid = self.book.get_best_bid()
        assert best_bid.price == 101.0
    
    def test_best_ask_min_heap(self):
        """Test that sell side returns lowest price first"""
        self.book.add_order(create_order("user1", "sell", 102.0, 10.0))
        self.book.add_order(create_order("user2", "sell", 100.0, 10.0))
        self.book.add_order(create_order("user3", "sell", 101.0, 10.0))
        
        best_ask = self.book.get_best_ask()
        assert best_ask.price == 100.0
    
    def test_fifo_at_same_price(self):
        """Test FIFO ordering at same price level"""
        order1 = create_order("user1", "buy", 100.0, 10.0)
        order2 = create_order("user2", "buy", 100.0, 20.0)
        
        self.book.add_order(order1)
        self.book.add_order(order2)
        
        best_bid = self.book.get_best_bid()
        assert best_bid.orders[0].user_id == "user1"  # First order is first
        assert best_bid.orders[1].user_id == "user2"  # Second order is second
    
    def test_remove_order(self):
        """Test order removal"""
        order = create_order("user1", "buy", 100.0, 10.0)
        self.book.add_order(order)
        
        removed = self.book.remove_order(order.order_id)
        assert removed is not None
        assert removed.order_id == order.order_id
        
        # Order should no longer be in book
        assert self.book.get_order(order.order_id) is None
    
    def test_spread(self):
        """Test bid-ask spread calculation"""
        self.book.add_order(create_order("user1", "buy", 99.0, 10.0))
        self.book.add_order(create_order("user2", "sell", 101.0, 10.0))
        
        spread = self.book.get_spread()
        assert spread == 2.0  # 101 - 99
    
    def test_snapshot(self):
        """Test order book snapshot"""
        self.book.add_order(create_order("user1", "buy", 99.0, 10.0))
        self.book.add_order(create_order("user2", "buy", 99.0, 20.0))
        self.book.add_order(create_order("user3", "sell", 101.0, 15.0))
        
        snapshot = self.book.get_snapshot(depth=10)
        
        assert snapshot["symbol"] == "TEST"
        assert len(snapshot["bids"]) == 1
        assert len(snapshot["asks"]) == 1
        assert snapshot["bids"][0]["price"] == 99.0
        assert snapshot["bids"][0]["quantity"] == 30.0  # 10 + 20
        assert snapshot["bids"][0]["orders"] == 2


class TestOrder:
    """Tests for Order class"""
    
    def test_create_order(self):
        """Test order creation"""
        order = create_order("user1", "buy", 100.0, 10.0)
        
        assert order.user_id == "user1"
        assert order.side == Side.BUY
        assert order.price == 100.0
        assert order.quantity == 10.0
        assert order.remaining_qty == 10.0
        assert not order.is_filled()
    
    def test_partial_fill(self):
        """Test partial fill"""
        order = create_order("user1", "buy", 100.0, 10.0)
        order.fill(4.0)
        
        assert order.remaining_qty == 6.0
        assert not order.is_filled()
    
    def test_full_fill(self):
        """Test complete fill"""
        order = create_order("user1", "buy", 100.0, 10.0)
        order.fill(10.0)
        
        assert order.remaining_qty == 0.0
        assert order.is_filled()
