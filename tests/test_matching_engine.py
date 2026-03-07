"""
Unit tests for the Matching Engine
"""
import pytest
from app.engine.matching_engine import MatchingEngine, Trade


class TestMatchingEngine:
    """Tests for MatchingEngine"""
    
    def setup_method(self):
        """Setup fresh engine for each test"""
        self.engine = MatchingEngine(symbol="TEST")
    
    def test_submit_resting_order(self):
        """Test submitting an order that rests in the book"""
        result = self.engine.submit_order("user1", "buy", 100.0, 10.0)
        
        assert result.status == "resting"
        assert len(result.trades) == 0
        assert result.order.remaining_qty == 10.0
    
    def test_basic_match(self):
        """Test basic order matching"""
        # Add sell order
        self.engine.submit_order("seller", "sell", 100.0, 10.0)
        
        # Submit matching buy order
        result = self.engine.submit_order("buyer", "buy", 100.0, 10.0)
        
        assert result.status == "matched"
        assert len(result.trades) == 1
        
        trade = result.trades[0]
        assert trade.price == 100.0
        assert trade.quantity == 10.0
        assert trade.buyer_id == "buyer"
        assert trade.seller_id == "seller"
    
    def test_partial_fill(self):
        """Test partial fill when quantities differ"""
        # Add sell order for 4 units
        self.engine.submit_order("seller", "sell", 100.0, 4.0)
        
        # Submit buy order for 10 units
        result = self.engine.submit_order("buyer", "buy", 100.0, 10.0)
        
        assert result.status == "partial"
        assert len(result.trades) == 1
        assert result.trades[0].quantity == 4.0
        assert result.order.remaining_qty == 6.0
    
    def test_price_crossing(self):
        """Test that buy >= sell triggers match"""
        # Sell at 99
        self.engine.submit_order("seller", "sell", 99.0, 5.0)
        
        # Buy at 100 (crosses sell)
        result = self.engine.submit_order("buyer", "buy", 100.0, 5.0)
        
        assert result.status == "matched"
        assert len(result.trades) == 1
        # Trade executes at resting order's price (99)
        assert result.trades[0].price == 99.0
    
    def test_no_crossing(self):
        """Test that buy < sell doesn't match"""
        # Sell at 101
        self.engine.submit_order("seller", "sell", 101.0, 10.0)
        
        # Buy at 100 (doesn't cross)
        result = self.engine.submit_order("buyer", "buy", 100.0, 10.0)
        
        assert result.status == "resting"
        assert len(result.trades) == 0
    
    def test_price_priority(self):
        """Test that better prices get matched first"""
        # Add two buy orders
        self.engine.submit_order("buyer1", "buy", 99.0, 10.0)
        self.engine.submit_order("buyer2", "buy", 100.0, 10.0)  # Better price
        
        # Sell at 99 - should match with buyer2 (100) first
        result = self.engine.submit_order("seller", "sell", 99.0, 10.0)
        
        assert result.status == "matched"
        assert result.trades[0].buyer_id == "buyer2"  # Higher price matched first
        assert result.trades[0].price == 100.0  # At resting order's price
    
    def test_time_priority(self):
        """Test that earlier orders at same price match first (FIFO)"""
        # Add two buy orders at same price
        self.engine.submit_order("buyer1", "buy", 100.0, 10.0)  # First
        self.engine.submit_order("buyer2", "buy", 100.0, 10.0)  # Second
        
        # Sell 10 - should match with buyer1 (first in line)
        result = self.engine.submit_order("seller", "sell", 100.0, 10.0)
        
        assert result.status == "matched"
        assert result.trades[0].buyer_id == "buyer1"
    
    def test_multiple_fills(self):
        """Test filling against multiple orders"""
        # Add multiple sell orders
        self.engine.submit_order("seller1", "sell", 100.0, 5.0)
        self.engine.submit_order("seller2", "sell", 100.0, 5.0)
        
        # Buy 10 - should fill against both
        result = self.engine.submit_order("buyer", "buy", 100.0, 10.0)
        
        assert result.status == "matched"
        assert len(result.trades) == 2
        assert result.trades[0].seller_id == "seller1"
        assert result.trades[1].seller_id == "seller2"
        total_qty = sum(t.quantity for t in result.trades)
        assert total_qty == 10.0
    
    def test_multiple_price_levels(self):
        """Test matching across multiple price levels"""
        # Add sells at different prices
        self.engine.submit_order("seller1", "sell", 100.0, 5.0)
        self.engine.submit_order("seller2", "sell", 101.0, 5.0)
        
        # Buy 10 at 101 - should match both levels
        result = self.engine.submit_order("buyer", "buy", 101.0, 10.0)
        
        assert result.status == "matched"
        assert len(result.trades) == 2
        # First trade at 100 (better ask price)
        assert result.trades[0].price == 100.0
        # Second trade at 101
        assert result.trades[1].price == 101.0
    
    def test_sell_matching(self):
        """Test sell order matching against buy side"""
        # Add buy order
        self.engine.submit_order("buyer", "buy", 100.0, 10.0)
        
        # Submit sell order
        result = self.engine.submit_order("seller", "sell", 100.0, 10.0)
        
        assert result.status == "matched"
        assert result.trades[0].buyer_id == "buyer"
        assert result.trades[0].seller_id == "seller"
    
    def test_cancel_order(self):
        """Test order cancellation"""
        # Submit order
        result = self.engine.submit_order("user", "buy", 100.0, 10.0)
        order_id = result.order.order_id
        
        # Cancel it
        cancelled = self.engine.cancel_order(order_id)
        assert cancelled is not None
        assert cancelled.order_id == order_id
        
        # Verify it's gone
        book = self.engine.get_order_book()
        assert len(book["bids"]) == 0
    
    def test_metrics(self):
        """Test engine metrics tracking"""
        # Submit some orders
        self.engine.submit_order("seller", "sell", 100.0, 10.0)
        self.engine.submit_order("buyer", "buy", 100.0, 10.0)
        
        metrics = self.engine.get_metrics()
        
        assert metrics["orders_processed"] == 2
        assert metrics["trades_executed"] == 1
        assert metrics["avg_latency_ms"] > 0
    
    def test_latency_tracking(self):
        """Test that latency is tracked per order"""
        result = self.engine.submit_order("user", "buy", 100.0, 10.0)
        
        assert result.latency_ms > 0
        assert result.latency_ms < 100  # Should be very fast


class TestPartialFillScenarios:
    """Tests for various partial fill scenarios"""
    
    def setup_method(self):
        self.engine = MatchingEngine(symbol="TEST")
    
    def test_large_order_multiple_fills(self):
        """Test large order filling against many small orders"""
        # Add 10 small sell orders
        for i in range(10):
            self.engine.submit_order(f"seller{i}", "sell", 100.0, 1.0)
        
        # Buy all 10 at once
        result = self.engine.submit_order("buyer", "buy", 100.0, 10.0)
        
        assert result.status == "matched"
        assert len(result.trades) == 10
        assert result.order.remaining_qty == 0.0
    
    def test_partial_then_complete(self):
        """Test order that gets filled over multiple incoming orders"""
        # Submit large buy order
        result1 = self.engine.submit_order("buyer", "buy", 100.0, 100.0)
        assert result1.status == "resting"
        
        # Fill partially with first sell
        result2 = self.engine.submit_order("seller1", "sell", 100.0, 40.0)
        assert result2.status == "matched"
        assert result2.trades[0].quantity == 40.0
        
        # Fill rest with second sell
        result3 = self.engine.submit_order("seller2", "sell", 100.0, 60.0)
        assert result3.status == "matched"
        assert result3.trades[0].quantity == 60.0


class TestEdgeCases:
    """Tests for edge cases"""
    
    def setup_method(self):
        self.engine = MatchingEngine(symbol="TEST")
    
    def test_zero_spread(self):
        """Test orders at same price create zero spread"""
        self.engine.submit_order("buyer", "buy", 100.0, 10.0)
        self.engine.submit_order("seller", "sell", 100.0, 10.0)
        
        # After match, book should be empty
        metrics = self.engine.get_metrics()
        assert metrics["spread"] is None  # No orders in book
    
    def test_empty_order_book(self):
        """Test operations on empty book"""
        book = self.engine.get_order_book()
        assert len(book["bids"]) == 0
        assert len(book["asks"]) == 0
        
        metrics = self.engine.get_metrics()
        assert metrics["spread"] is None
    
    def test_cancel_nonexistent(self):
        """Test cancelling non-existent order"""
        result = self.engine.cancel_order("fake-id")
        assert result is None
