# FlashLedger

> Low Latency Order Matching Engine

A real-time order matching engine that replicates the core function of a stock exchange, built with **FastAPI** and **PostgreSQL**.

## MVP Features

- ✅ Accept buy and sell orders via REST API
- ✅ Maintain in-memory order book with heap-based priority queues
- ✅ Match orders using **price-time priority**
- ✅ Execute trades automatically
- ✅ Record trades in PostgreSQL
- ✅ Expose API endpoints for orders and order book
- ✅ Sub-5ms local latency target

## System Flow

```
User submits order → API receives → Engine checks book → Match occurs → Trade executed → Book updated → Trade stored
```

## Architecture

```
┌─────────────┐     ┌────────────────┐     ┌─────────────┐
│   FastAPI   │────▶│  Matching      │────▶│ Order Book  │
│   /order    │     │  Engine        │     │ (In-Memory) │
└─────────────┘     └────────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ PostgreSQL  │
                    │  (Trades)   │
                    └─────────────┘
```

## Core Concepts

### Order Book Structure

- **Buy Side**: Max heap (highest price first)
- **Sell Side**: Min heap (lowest price first)

### Matching Rules

Orders match when: `Buy Price >= Sell Price`

**Example:**
```
Buy order:  Price=100, Qty=10
Sell order: Price=99,  Qty=5

Match happens at price=99, quantity=5
Remaining buy: 5 units
```

### Partial Fills

```
Buy 10 → Sell 4 available
Trade executes for 4
Remaining buy: 6 (stays in book)
```

## Quick Start

### With Docker (Recommended)

```bash
# Start services
docker-compose up -d

# API available at http://localhost:8000
# Health check: http://localhost:8000/health
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL (or use Docker)
docker run -d --name postgres \
  -e POSTGRES_DB=flashledger \
  -e POSTGRES_USER=flashledger \
  -e POSTGRES_PASSWORD=flashledger \
  -p 5432:5432 \
  postgres:15-alpine

# Run the server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

### POST /api/v1/order

Submit a new order.

**Request:**
```json
{
  "user_id": "user1",
  "side": "buy",
  "price": 100,
  "quantity": 10
}
```

**Response:**
```json
{
  "order_id": "uuid",
  "order_status": "matched",
  "trades": [
    {
      "price": 99,
      "quantity": 5,
      "trade_id": "uuid"
    }
  ],
  "remaining_qty": 5,
  "latency_ms": 0.234
}
```

### GET /api/v1/orderbook

Get current order book state.

**Response:**
```json
{
  "symbol": "FLASH",
  "bids": [
    {"price": 99, "quantity": 100, "orders": 3}
  ],
  "asks": [
    {"price": 101, "quantity": 50, "orders": 2}
  ],
  "bid_count": 1,
  "ask_count": 1
}
```

### GET /api/v1/trades

Get recent executed trades.

**Response:**
```json
[
  {
    "trade_id": "uuid",
    "buy_order_id": "uuid",
    "sell_order_id": "uuid",
    "buyer_id": "user1",
    "seller_id": "user2",
    "price": 100,
    "quantity": 10,
    "timestamp": "2024-01-01T12:00:00"
  }
]
```

### DELETE /api/v1/order/{order_id}

Cancel an existing order.

### GET /api/v1/metrics

Get engine metrics.

## Project Structure

```
flashledger/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── engine/
│   │   ├── order_book.py    # Heap-based order book
│   │   └── matching_engine.py  # Price-time priority matching
│   ├── api/
│   │   └── routes.py        # REST endpoints
│   └── db/
│       ├── models.py        # Trade model
│       └── database.py      # PostgreSQL connection
├── tests/
│   ├── test_order_book.py
│   ├── test_matching_engine.py
│   └── load_test.py         # 10k order benchmark
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Testing

### Unit Tests

```bash
pytest tests/ -v
```

### Load Test (10k Orders)

```bash
# Start the server first
python tests/load_test.py --orders 10000 --concurrency 100
```

**Sample Output:**
```
Orders: 10000
Duration: 2.5 seconds
Orders/second: 4000
Median latency: 2.1 ms
P95 latency: 4.2 ms

✅ PASS: Median latency (2.1ms) < 5ms target
```

## Data Flow Example

1. **User A** submits: `BUY 10 @ $100`
2. Order rests in buy book (no match)
3. **User B** submits: `SELL 5 @ $99`
4. Match found: Buy $100 >= Sell $99
5. Trade executed: 5 units @ $99
6. User A's order: 5 remaining in book
7. User B's order: fully filled
8. Trade persisted to PostgreSQL

## MVP Success Criteria

| Criteria | Status |
|----------|--------|
| Order submission works | ✅ |
| Orders match correctly | ✅ |
| Partial fills work | ✅ |
| Order book updates correctly | ✅ |
| Trades persist in database | ✅ |
| < 5ms local latency | ✅ |

## Tech Stack

- **Framework**: FastAPI (Python 3.11)
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0 (async)
- **Container**: Docker Compose

## License

MIT
