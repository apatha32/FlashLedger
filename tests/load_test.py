"""
Load Test Script for FlashLedger

Sends configurable number of orders and measures:
- Orders per second
- Matching latency
- Trade execution rate
"""
import asyncio
import aiohttp
import time
import random
import argparse
from dataclasses import dataclass
from statistics import mean, stdev, median


@dataclass
class LoadTestResult:
    total_orders: int
    successful_orders: int
    failed_orders: int
    total_trades: int
    duration_seconds: float
    orders_per_second: float
    latencies_ms: list
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


async def send_order(session: aiohttp.ClientSession, base_url: str, order: dict) -> dict:
    """Send a single order and return the result"""
    start_time = time.perf_counter()
    try:
        async with session.post(f"{base_url}/api/v1/order", json=order) as response:
            result = await response.json()
            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "success": response.status == 200,
                "latency_ms": latency_ms,
                "trades": len(result.get("trades", [])),
                "status": result.get("order_status", "unknown")
            }
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "success": False,
            "latency_ms": latency_ms,
            "trades": 0,
            "status": "error",
            "error": str(e)
        }


def generate_order(user_num: int) -> dict:
    """Generate a random order"""
    side = random.choice(["buy", "sell"])
    # Price around 100 with some variance
    base_price = 100
    variance = random.uniform(-5, 5)
    price = round(base_price + variance, 2)
    quantity = random.randint(1, 100)
    
    return {
        "user_id": f"user_{user_num % 100}",  # 100 unique users
        "side": side,
        "price": price,
        "quantity": quantity
    }


async def run_load_test(
    base_url: str,
    num_orders: int,
    concurrency: int,
    ramp_up_seconds: float = 0
) -> LoadTestResult:
    """
    Run the load test
    
    Args:
        base_url: API base URL
        num_orders: Total number of orders to send
        concurrency: Max concurrent requests
        ramp_up_seconds: Time to gradually ramp up to full concurrency
    """
    print(f"\n{'='*60}")
    print(f"FlashLedger Load Test")
    print(f"{'='*60}")
    print(f"Target: {base_url}")
    print(f"Orders: {num_orders}")
    print(f"Concurrency: {concurrency}")
    print(f"{'='*60}\n")
    
    results = []
    semaphore = asyncio.Semaphore(concurrency)
    
    async def send_with_semaphore(session, order):
        async with semaphore:
            return await send_order(session, base_url, order)
    
    # Create orders
    orders = [generate_order(i) for i in range(num_orders)]
    
    start_time = time.perf_counter()
    
    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Send all orders concurrently (limited by semaphore)
        tasks = [send_with_semaphore(session, order) for order in orders]
        
        # Progress reporting
        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            if completed % 1000 == 0:
                elapsed = time.perf_counter() - start_time
                rate = completed / elapsed
                print(f"Progress: {completed}/{num_orders} ({rate:.0f} orders/sec)")
    
    end_time = time.perf_counter()
    total_duration = end_time - start_time
    
    # Calculate statistics
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    latencies = [r["latency_ms"] for r in results]
    total_trades = sum(r["trades"] for r in results)
    
    # Sort latencies for percentiles
    latencies_sorted = sorted(latencies)
    
    def percentile(data, p):
        if not data:
            return 0
        k = (len(data) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(data) else f
        return data[f] + (data[c] - data[f]) * (k - f)
    
    return LoadTestResult(
        total_orders=num_orders,
        successful_orders=len(successful),
        failed_orders=len(failed),
        total_trades=total_trades,
        duration_seconds=total_duration,
        orders_per_second=num_orders / total_duration,
        latencies_ms=latencies,
        avg_latency_ms=mean(latencies) if latencies else 0,
        median_latency_ms=median(latencies) if latencies else 0,
        p95_latency_ms=percentile(latencies_sorted, 95),
        p99_latency_ms=percentile(latencies_sorted, 99)
    )


def print_results(result: LoadTestResult):
    """Print load test results"""
    print(f"\n{'='*60}")
    print(f"LOAD TEST RESULTS")
    print(f"{'='*60}")
    print(f"\nOrders:")
    print(f"  Total:      {result.total_orders}")
    print(f"  Successful: {result.successful_orders}")
    print(f"  Failed:     {result.failed_orders}")
    print(f"  Trades:     {result.total_trades}")
    
    print(f"\nPerformance:")
    print(f"  Duration:         {result.duration_seconds:.2f} seconds")
    print(f"  Orders/second:    {result.orders_per_second:.0f}")
    
    print(f"\nLatency (end-to-end HTTP):")
    print(f"  Average:  {result.avg_latency_ms:.2f} ms")
    print(f"  Median:   {result.median_latency_ms:.2f} ms")
    print(f"  P95:      {result.p95_latency_ms:.2f} ms")
    print(f"  P99:      {result.p99_latency_ms:.2f} ms")
    
    # Check against MVP target
    print(f"\n{'='*60}")
    print(f"MVP TARGET CHECK")
    print(f"{'='*60}")
    target_latency = 5.0  # < 5ms locally
    if result.median_latency_ms < target_latency:
        print(f"✅ PASS: Median latency ({result.median_latency_ms:.2f}ms) < {target_latency}ms target")
    else:
        print(f"❌ FAIL: Median latency ({result.median_latency_ms:.2f}ms) >= {target_latency}ms target")
    
    print(f"{'='*60}\n")


async def main():
    parser = argparse.ArgumentParser(description="FlashLedger Load Test")
    parser.add_argument(
        "--url", 
        default="http://localhost:8000",
        help="Base URL of the FlashLedger API"
    )
    parser.add_argument(
        "--orders", 
        type=int, 
        default=10000,
        help="Number of orders to send"
    )
    parser.add_argument(
        "--concurrency", 
        type=int, 
        default=100,
        help="Max concurrent requests"
    )
    
    args = parser.parse_args()
    
    # Run load test
    result = await run_load_test(
        base_url=args.url,
        num_orders=args.orders,
        concurrency=args.concurrency
    )
    
    print_results(result)
    
    # Return non-zero if target not met
    if result.median_latency_ms >= 5.0:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
