import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class HealthState:
    """Singleton class tracking connection states and task health."""

    _instance: Optional["HealthState"] = None

    def __new__(cls) -> "HealthState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.start_time: float = time.time()
        self.mqtt_connected: bool = False
        self.tydom_connected: bool = False
        self.last_tydom_message_time: Optional[float] = None
        self.tasks_heartbeat: Dict[str, float] = {}

        # Timeout configuration. These are conservative startup defaults;
        # main.py overrides both at boot via set_timeouts_from_polling_interval()
        # so they scale with the Tydom polling interval.
        self.message_timeout: int = 600  # max age of last Tydom message (seconds)
        self.heartbeat_timeout: int = 600  # max age of a task heartbeat (seconds)

    def set_timeouts_from_polling_interval(self, polling_interval: int) -> None:
        """Derive the health timeouts from the Tydom polling interval.

        Both signals must tolerate at least one full polling cycle plus the
        latency of the response, otherwise a quiet-but-working installation
        (whose only guaranteed traffic is the periodic poll) would flap
        unhealthy. We use 2x the interval with a 600s floor.
        """
        self.heartbeat_timeout = max(600, polling_interval * 2)
        self.message_timeout = max(600, polling_interval * 2)

    def update_mqtt_status(self, connected: bool) -> None:
        """Update MQTT connection status."""
        self.mqtt_connected = connected
        logger.debug("Health: MQTT connected=%s", connected)

    def update_tydom_status(self, connected: bool) -> None:
        """Update Tydom WebSocket connection status."""
        self.tydom_connected = connected
        if connected:
            self.last_tydom_message_time = time.time()
        logger.debug("Health: Tydom connected=%s", connected)

    def update_tydom_message_time(self) -> None:
        """Update the timestamp of last received Tydom message."""
        self.last_tydom_message_time = time.time()

    def update_task_heartbeat(self, task_name: str) -> None:
        """Update heartbeat timestamp for a task."""
        self.tasks_heartbeat[task_name] = time.time()
        logger.debug("Health: Task %s heartbeat updated", task_name)

    def is_healthy(self) -> bool:
        """Check if the application is healthy."""
        now = time.time()

        # Check MQTT connection
        if not self.mqtt_connected:
            logger.debug("Health: Unhealthy - MQTT not connected")
            return False

        # Check Tydom connection
        if not self.tydom_connected:
            logger.debug("Health: Unhealthy - Tydom not connected")
            return False

        # Check if we've received messages recently
        if self.last_tydom_message_time is not None:
            time_since_message = now - self.last_tydom_message_time
            if time_since_message > self.message_timeout:
                logger.debug(
                    "Health: Unhealthy - No Tydom message for %d seconds",
                    int(time_since_message),
                )
                return False

        # Check task heartbeats
        for task_name, last_heartbeat in self.tasks_heartbeat.items():
            time_since_heartbeat = now - last_heartbeat
            if time_since_heartbeat > self.heartbeat_timeout:
                logger.debug(
                    "Health: Unhealthy - Task %s heartbeat timeout (%d seconds)",
                    task_name,
                    int(time_since_heartbeat),
                )
                return False

        return True

    def get_status_dict(self) -> dict:
        """Get a dictionary with current health status."""
        now = time.time()
        uptime = now - self.start_time

        tasks_status = {}
        for task_name, last_heartbeat in self.tasks_heartbeat.items():
            tasks_status[task_name] = {
                "last_heartbeat_seconds_ago": int(now - last_heartbeat),
                "healthy": (now - last_heartbeat) <= self.heartbeat_timeout,
            }

        message_age = None
        if self.last_tydom_message_time is not None:
            message_age = int(now - self.last_tydom_message_time)

        return {
            "healthy": self.is_healthy(),
            "uptime_seconds": int(uptime),
            "mqtt_connected": self.mqtt_connected,
            "tydom_connected": self.tydom_connected,
            "last_tydom_message_seconds_ago": message_age,
            "tasks": tasks_status,
        }

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None
