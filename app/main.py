"""
FlashLedger - Low Latency Order Matching Engine
Main application entry point
"""
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.routes import router
from app.db.database import init_db, engine
from app.db.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print("🚀 FlashLedger Starting...")
    await init_db()
    print("✅ Database initialized")
    print("✅ Matching engine ready")
    yield
    # Shutdown
    print("👋 FlashLedger shutting down...")


app = FastAPI(
    title="FlashLedger",
    description="Low Latency Order Matching Engine",
    version="1.0.0",
    lifespan=lifespan
)

# Include API routes
app.include_router(router, prefix="/api/v1")

# Root health check
@app.get("/")
async def root():
    return {"status": "healthy", "service": "FlashLedger"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
