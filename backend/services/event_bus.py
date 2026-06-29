"""
Event Bus — Redis pub/sub event system for real-time deployment events.

Events flow:  Pipeline → EventBus → WebSocket / Plugins / Alerts
"""

import json
import threading
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict, List, Optional
from backend.core.logger import get_logger

logger = get_logger("event_bus")
IST    = timezone(timedelta(hours=5, minutes=30))

# ── Event Types ──────────────────────────────────────────
DEPLOY_STARTED        = "deploy.started"
DEPLOY_PHASE_CHANGE   = "deploy.phase_change"
DEPLOY_LOG            = "deploy.log"
DEPLOY_RISK_SCORED    = "deploy.risk_scored"
DEPLOY_APPROVED       = "deploy.approved"
DEPLOY_BLOCKED        = "deploy.blocked"
DEPLOY_COMPLETED      = "deploy.completed"
DEPLOY_FAILED         = "deploy.failed"
DEPLOY_ROLLBACK       = "deploy.rollback"
HEAL_STARTED          = "heal.started"
HEAL_COMPLETED        = "heal.completed"
ALERT_TRIGGERED       = "alert.triggered"
ANOMALY_DETECTED      = "anomaly.detected"
INCIDENT_CREATED      = "incident.created"
INCIDENT_RESOLVED     = "incident.resolved"


class EventBus:
    """
    In-process + Redis event bus.
    Supports both local subscribers and Redis pub/sub for multi-process.
    """

    CHANNEL_PREFIX = "devops_swarm:"

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._redis = None
        self._pubsub = None
        self._listener_thread = None
        self._running = False

    # ── Redis Connection ─────────────────────────────────

    def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is None:
            import time
            now = time.time()
            if getattr(self, "_last_redis_attempt", 0) + 60 > now:
                return None
            self._last_redis_attempt = now
            
            try:
                import redis
                from backend.core.config import settings
                self._redis = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=3,
                    decode_responses=True,
                )
                self._redis.ping()
                logger.info("✅ EventBus connected to Redis")
            except Exception as e:
                logger.warning(f"⚠️ Redis not available for EventBus: {e}")
                self._redis = None
        return self._redis

    # ── Publish ───────────────────────────────────────────

    def emit(
        self,
        event_type:    str,
        deployment_id: Optional[int] = None,
        data:          Optional[dict] = None,
    ):
        """
        Emit an event to all subscribers.

        Parameters
        ----------
        event_type    : One of the event type constants above.
        deployment_id : Associated deployment ID, if any.
        data          : Extra event payload.
        """
        event = {
            "type":          event_type,
            "deployment_id": deployment_id,
            "data":          data or {},
            "timestamp":     datetime.now(IST).isoformat(),
        }

        # Local subscribers
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"EventBus handler error ({event_type}): {e}")

        # Wildcard subscribers (listen to all events)
        for handler in self._subscribers.get("*", []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"EventBus wildcard handler error: {e}")

        # Redis pub/sub
        r = self._get_redis()
        if r:
            try:
                channel = f"{self.CHANNEL_PREFIX}{event_type}"
                r.publish(channel, json.dumps(event))
            except Exception as e:
                logger.warning(f"Redis publish failed: {e}")

        logger.debug(
            f"📡 Event: {event_type} "
            f"(deploy #{deployment_id or '-'})"
        )

    # ── Subscribe ─────────────────────────────────────────

    def on(self, event_type: str, handler: Callable):
        """
        Subscribe to an event type.

        Parameters
        ----------
        event_type : Event type to listen for, or '*' for all events.
        handler    : Callback function(event_dict).
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"📡 Subscriber added for: {event_type}")

    def off(self, event_type: str, handler: Callable):
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    # ── Redis Listener ────────────────────────────────────

    def start_redis_listener(self):
        """Start background thread listening to Redis events."""
        r = self._get_redis()
        if not r:
            return

        self._pubsub = r.pubsub()
        self._pubsub.psubscribe(f"{self.CHANNEL_PREFIX}*")
        self._running = True

        def _listen():
            while self._running:
                try:
                    message = self._pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1
                    )
                    if message and message["type"] == "pmessage":
                        event = json.loads(message["data"])
                        event_type = event.get("type", "unknown")
                        for handler in self._subscribers.get(event_type, []):
                            try:
                                handler(event)
                            except Exception as e:
                                logger.error(
                                    f"Redis listener handler error: {e}"
                                )
                except Exception as e:
                    logger.error(f"Redis listener error: {e}")

        self._listener_thread = threading.Thread(
            target=_listen, daemon=True, name="eventbus-redis-listener"
        )
        self._listener_thread.start()
        logger.info("✅ EventBus Redis listener started")

    def stop(self):
        """Stop the Redis listener."""
        self._running = False
        if self._pubsub:
            self._pubsub.unsubscribe()
        logger.info("EventBus stopped")

    # ── Deployment-Specific Helpers ───────────────────────

    def deploy_started(self, deployment_id: int, service_name: str, user: str = None):
        self.emit(DEPLOY_STARTED, deployment_id, {
            "service_name": service_name,
            "user":         user,
        })

    def deploy_phase(self, deployment_id: int, phase: str, status: str = "running"):
        self.emit(DEPLOY_PHASE_CHANGE, deployment_id, {
            "phase":  phase,
            "status": status,
        })

    def deploy_log(self, deployment_id: int, message: str):
        self.emit(DEPLOY_LOG, deployment_id, {"message": message})

    def deploy_risk_scored(
        self, deployment_id: int, risk_score: float,
        is_safe: bool, strategy: str = None
    ):
        self.emit(DEPLOY_RISK_SCORED, deployment_id, {
            "risk_score": risk_score,
            "is_safe":    is_safe,
            "strategy":   strategy,
        })

    def deploy_completed(self, deployment_id: int, status: str):
        self.emit(DEPLOY_COMPLETED, deployment_id, {"status": status})

    def deploy_failed(self, deployment_id: int, error: str):
        self.emit(DEPLOY_FAILED, deployment_id, {"error": error})

    def heal_started(self, deployment_id: int, service_name: str):
        self.emit(HEAL_STARTED, deployment_id, {
            "service_name": service_name,
        })

    def heal_completed(self, deployment_id: int, actions: list):
        self.emit(HEAL_COMPLETED, deployment_id, {"actions": actions})

    def incident_created(
        self, deployment_id: int, incident_id: int, severity: str
    ):
        self.emit(INCIDENT_CREATED, deployment_id, {
            "incident_id": incident_id,
            "severity":    severity,
        })


# ── Singleton ────────────────────────────────────────────
event_bus = EventBus()
