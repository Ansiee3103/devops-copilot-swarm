"""
WebSocket API — Real-time deployment log streaming.

Provides live updates for active deployments via WebSocket connections.
"""

import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.security import decode_token
from backend.core.logger import get_logger
from backend.database import SessionLocal
from backend.repositories.deployment_repo import DeploymentRepository

router = APIRouter(tags=["WebSocket"])
logger = get_logger("websocket")

# ── Active connections manager ───────────────────────────

class ConnectionManager:
    """Manages WebSocket connections grouped by deployment_id."""

    def __init__(self):
        self.active: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, deployment_id: int):
        await websocket.accept()
        if deployment_id not in self.active:
            self.active[deployment_id] = []
        self.active[deployment_id].append(websocket)
        logger.info(
            f"🔌 WebSocket connected: deploy #{deployment_id} "
            f"({len(self.active[deployment_id])} clients)"
        )

    def disconnect(self, websocket: WebSocket, deployment_id: int):
        if deployment_id in self.active:
            self.active[deployment_id] = [
                ws for ws in self.active[deployment_id] if ws != websocket
            ]
            if not self.active[deployment_id]:
                del self.active[deployment_id]
        logger.info(f"🔌 WebSocket disconnected: deploy #{deployment_id}")

    async def broadcast(self, deployment_id: int, message: dict):
        """Send message to all clients watching a deployment."""
        if deployment_id not in self.active:
            return
        disconnected = []
        for ws in self.active[deployment_id]:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws, deployment_id)


manager = ConnectionManager()


@router.websocket("/ws/deployments/{deployment_id}")
async def websocket_deployment(
    websocket: WebSocket,
    deployment_id: int,
    token: str = None,
):
    """
    WebSocket endpoint for real-time deployment updates.

    Connect: ws://host/ws/deployments/{id}?token=JWT_TOKEN

    Messages sent:
      - {"type": "log",      "data": {"message": "..."}}
      - {"type": "status",   "data": {"status": "...", "risk_score": ...}}
      - {"type": "complete", "data": {"status": "healed"}}
      - {"type": "error",    "data": {"message": "..."}}
    """
    # Auth check
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(websocket, deployment_id)

    try:
        last_log_count = 0
        last_status    = None

        while True:
            try:
                db   = SessionLocal()
                repo = DeploymentRepository(db)
                dep  = repo.get_by_id(deployment_id)
                db.close()

                if not dep:
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": "Deployment not found"},
                    })
                    break

                logs     = json.loads(dep.logs or "[]")
                new_logs = logs[last_log_count:]

                # Send new log entries
                for log_msg in new_logs:
                    await websocket.send_json({
                        "type": "log",
                        "data": {"message": log_msg},
                    })
                last_log_count = len(logs)

                # Send status changes
                if dep.status != last_status:
                    await websocket.send_json({
                        "type": "status",
                        "data": {
                            "id":          dep.id,
                            "status":      dep.status,
                            "risk_score":  dep.risk_score or 0,
                            "is_safe":     dep.is_safe,
                            "is_critical": dep.is_critical,
                        },
                    })
                    last_status = dep.status

                # Pipeline complete
                if dep.status in [
                    "healed", "deployed", "blocked",
                    "failed", "rolled_back"
                ]:
                    await websocket.send_json({
                        "type": "complete",
                        "data": {"status": dep.status},
                    })
                    break

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                # Don't break the loop on a DB error, just wait and retry
                pass

            # Poll interval
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, deployment_id)


@router.websocket("/ws/events")
async def websocket_global_events(
    websocket: WebSocket,
    token: str = None,
):
    """
    Global event stream — all deployment events across all services.

    Connect: ws://host/ws/events?token=JWT_TOKEN
    """
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    logger.info("🔌 Global events WebSocket connected")

    try:
        # Subscribe to event bus
        from backend.services.event_bus import event_bus
        event_queue = asyncio.Queue()

        def on_event(event):
            # Thread-safe: put event in asyncio queue
            try:
                event_queue.put_nowait(event)
            except Exception:
                pass

        event_bus.on("*", on_event)

        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        event_queue.get(), timeout=30
                    )
                    await websocket.send_json(event)
                except asyncio.TimeoutError:
                    # Send heartbeat
                    await websocket.send_json({"type": "heartbeat"})
                except WebSocketDisconnect:
                    break
        finally:
            event_bus.off("*", on_event)

    except WebSocketDisconnect:
        pass
    finally:
        logger.info("🔌 Global events WebSocket disconnected")
