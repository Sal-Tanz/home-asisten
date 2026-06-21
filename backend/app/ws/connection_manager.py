from typing import List, Dict, Set
from fastapi import WebSocket
from collections import defaultdict


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.device_subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection and clean up subscriptions"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # Remove from all device subscriptions
        for device_id in list(self.device_subscriptions.keys()):
            if websocket in self.device_subscriptions[device_id]:
                self.device_subscriptions[device_id].remove(websocket)

            # Clean up empty subscription sets
            if not self.device_subscriptions[device_id]:
                del self.device_subscriptions[device_id]

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be closed, skip it
                pass

    def subscribe_device(self, device_id: str, websocket: WebSocket):
        """Subscribe a client to receive updates for a specific device"""
        self.device_subscriptions[device_id].add(websocket)

    def unsubscribe_device(self, device_id: str, websocket: WebSocket):
        """Unsubscribe a client from a device's updates"""
        if device_id in self.device_subscriptions:
            self.device_subscriptions[device_id].discard(websocket)

    async def send_to_device(self, device_id: str, message: dict):
        """Send a message to all clients subscribed to a specific device"""
        subscribers = self.device_subscriptions.get(device_id, set())

        for connection in subscribers:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be closed, skip it
                pass

    def get_active_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
