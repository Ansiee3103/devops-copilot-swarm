import importlib
import os
from typing import Dict, Callable
from backend.core.logger import get_logger

logger = get_logger("plugin_manager")

class Plugin:
    """Base class for all plugins"""
    name:        str = "base_plugin"
    version:     str = "1.0.0"
    description: str = ""

    def on_deploy_start(self, context: dict) -> dict:
        return context

    def on_deploy_complete(self, context: dict) -> dict:
        return context

    def on_deploy_blocked(self, context: dict) -> dict:
        return context

    def on_failure_detected(self, context: dict) -> dict:
        return context

    def on_healed(self, context: dict) -> dict:
        return context

class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self._load_builtin_plugins()

    def _load_builtin_plugins(self):
        """Load built-in plugins"""
        self.register(SlackNotificationPlugin())
        self.register(AuditLogPlugin())
        self.register(MetricsPlugin())
        logger.info(f"✅ {len(self.plugins)} plugins loaded")

    def register(self, plugin: Plugin):
        self.plugins[plugin.name] = plugin
        logger.info(f"🔌 Plugin registered: {plugin.name} v{plugin.version}")

    def unregister(self, name: str):
        if name in self.plugins:
            del self.plugins[name]
            logger.info(f"🔌 Plugin unregistered: {name}")

    def trigger(self, event: str, context: dict) -> dict:
        """Trigger all plugins for an event"""
        for name, plugin in self.plugins.items():
            try:
                handler = getattr(plugin, f"on_{event}", None)
                if handler:
                    context = handler(context) or context
            except Exception as e:
                logger.error(f"Plugin {name} error on {event}: {e}")
        return context

    def list_plugins(self) -> list:
        return [
            {
                "name":        p.name,
                "version":     p.version,
                "description": p.description
            }
            for p in self.plugins.values()
        ]

# ── Built-in Plugins ──────────────────────────────────────

class SlackNotificationPlugin(Plugin):
    name        = "slack_notifications"
    version     = "1.0.0"
    description = "Sends Slack notifications for deployment events"

    def on_deploy_blocked(self, context: dict) -> dict:
        logger.info(
            f"[Slack Plugin] Deployment blocked: "
            f"{context.get('service_name')}"
        )
        return context

    def on_healed(self, context: dict) -> dict:
        logger.info(
            f"[Slack Plugin] Service healed: "
            f"{context.get('service_name')}"
        )
        return context

class AuditLogPlugin(Plugin):
    name        = "audit_log"
    version     = "1.0.0"
    description = "Logs all deployment events to audit trail"

    def on_deploy_start(self, context: dict) -> dict:
        logger.info(
            f"[Audit] Deploy started: "
            f"{context.get('service_name')} "
            f"by {context.get('user', 'unknown')}"
        )
        return context

    def on_deploy_complete(self, context: dict) -> dict:
        logger.info(
            f"[Audit] Deploy complete: "
            f"{context.get('service_name')} "
            f"status={context.get('status')}"
        )
        return context

class MetricsPlugin(Plugin):
    name        = "metrics"
    version     = "1.0.0"
    description = "Tracks deployment metrics"

    def __init__(self):
        self.deploy_count  = 0
        self.blocked_count = 0
        self.healed_count  = 0

    def on_deploy_start(self, context: dict) -> dict:
        self.deploy_count += 1
        return context

    def on_deploy_blocked(self, context: dict) -> dict:
        self.blocked_count += 1
        return context

    def on_healed(self, context: dict) -> dict:
        self.healed_count += 1
        return context

plugin_manager = PluginManager()