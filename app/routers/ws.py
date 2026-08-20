import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
from app.logger import get_logger

logger = get_logger("websocket")
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connecte — {len(self.active_connections)} clients actifs")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket deconnecte — {len(self.active_connections)} clients actifs")

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead.append(connection)
        for d in dead:
            self.active_connections.remove(d)

manager = ConnectionManager()

@router.websocket("/ws/reviews")
async def websocket_reviews(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
