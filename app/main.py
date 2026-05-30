"""
FlashLedger - Low Latency Order Matching Engine
Main application entry point
"""
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from app.api.routes import router
from app.db.database import init_db, engine
from app.db.models import Base
from app.kafka import producer as kafka

STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")


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
    kafka.flush()
    print("👋 FlashLedger shutting down...")


app = FastAPI(
    title="FlashLedger",
    description="Low Latency Order Matching Engine with Kafka Streaming + LSTM Prediction",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — open in production (same-origin from nginx/static serve) and dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}

# Serve pre-built React frontend when STATIC_DIR exists (production / HF Spaces)
if os.path.isdir(STATIC_DIR):
    _assets = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str = ""):
        """Serve the React SPA for every non-API route."""
        candidate = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {"status": "healthy", "service": "FlashLedger", "version": "2.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
