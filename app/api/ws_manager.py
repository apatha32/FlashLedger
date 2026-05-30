"""
WebSocket Connection Manager

Broadcasts real-time events (trades, order book snapshots, metrics)
to all connected frontend clients.
"""
import json
import logging
from typing import List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WS client connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WS client disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast a typed JSON event to all connected clients."""
        if not self.active_connections:
            return
        message = json.dumps({"type": event_type, "data": data})
        dead: List[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# Module-level singleton shared across the app
manager = ConnectionManager()
