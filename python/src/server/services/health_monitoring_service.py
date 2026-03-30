"""Health Monitoring Service

Continuously monitors Archon system health and alerts on issues.
Runs as a background task with configurable intervals.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

import httpx

from ..config.logfire_config import get_logger, safe_span
from .database import get_database_connector

logger = get_logger(__name__)


@dataclass
class HealthAlert:
    """Health alert with severity and details."""

    timestamp: datetime
    check_name: str
    severity: str  # "critical", "warning", "info"
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


class HealthMonitoringService:
    """Background service for continuous health monitoring."""

    def __init__(
        self,
        check_interval: int = 60,
        alert_threshold: int = 3,
        alert_callback: Callable | None = None,
    ):
        """Initialize health monitoring.

        Args:
            check_interval: Seconds between health checks
            alert_threshold: Number of consecutive failures before alerting
            alert_callback: Optional callback function for alerts (receives HealthAlert)
        """
        self.check_interval = check_interval
        self.alert_threshold = alert_threshold
        self.alert_callback = alert_callback

        self._running = False
        self._task: asyncio.Task | None = None
        self._failure_counts: dict[str, int] = {}
        self._alerts: list[HealthAlert] = []
        self._last_check: datetime | None = None

    async def start(self):
        """Start the health monitoring service."""
        if self._running:
            logger.warning("Health monitoring already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitoring service started")

    async def stop(self):
        """Stop the health monitoring service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring service stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._run_health_checks()
                self._last_check = datetime.now()
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

    async def _run_health_checks(self):
        """Run all health checks."""
        checks = [
            ("api", self._check_api),
            ("database", self._check_database),
            ("repos", self._check_repos),
            ("container", self._check_container),
        ]

        for check_name, check_func in checks:
            try:
                is_healthy, message, details = await check_func()

                if is_healthy:
                    # Reset failure count on success
                    if check_name in self._failure_counts:
                        if self._failure_counts[check_name] >= self.alert_threshold:
                            logger.info(f"Health restored: {check_name}")
                        del self._failure_counts[check_name]
                else:
                    # Increment failure count
                    self._failure_counts[check_name] = self._failure_counts.get(check_name, 0) + 1

                    # Alert if threshold reached
                    if self._failure_counts[check_name] == self.alert_threshold:
                        severity = "critical" if check_name in ["api", "database"] else "warning"
                        await self._create_alert(check_name, severity, message, details)

            except Exception as e:
                logger.error(f"Health check {check_name} failed: {e}")
                self._failure_counts[check_name] = self._failure_counts.get(check_name, 0) + 1

    async def _check_api(self) -> tuple[bool, str, dict]:
        """Check if API is responding."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:8181/health")
                if response.status_code == 200:
                    return True, "API healthy", response.json()
                else:
                    return False, f"API returned {response.status_code}", {}
        except Exception as e:
            return False, f"API connection failed: {e}", {"error": str(e)}

    async def _check_database(self) -> tuple[bool, str, dict]:
        """Check database connectivity."""
        try:
            db = get_database_connector()
            result = await db.fetch("SELECT COUNT(*) as count FROM archon_code_repos")
            repo_count = result[0]["count"] if result else 0
            return True, f"Database connected ({repo_count} repos)", {"repo_count": repo_count}
        except Exception as e:
            return False, f"Database error: {e}", {"error": str(e)}

    async def _check_repos(self) -> tuple[bool, str, dict]:
        """Check repository indexing status."""
        try:
            db = get_database_connector()
            repos = await db.fetch("SELECT name, entities_count FROM archon_code_repos")

            total_entities = sum(r["entities_count"] for r in repos)
            empty_repos = [r["name"] for r in repos if r["entities_count"] == 0]

            if empty_repos:
                return (
                    False,
                    f"{len(empty_repos)} repos have no entities: {', '.join(empty_repos)}",
                    {"empty_repos": empty_repos, "total_entities": total_entities},
                )

            return (
                True,
                f"{len(repos)} repos with {total_entities} entities",
                {"repo_count": len(repos), "total_entities": total_entities},
            )
        except Exception as e:
            return False, f"Failed to check repos: {e}", {"error": str(e)}

    async def _check_container(self) -> tuple[bool, str, dict]:
        """Check if container is responsive."""
        try:
            # Simple check - if we're running, container is up
            # Could add docker health check here
            return True, "Container running", {}
        except Exception as e:
            return False, f"Container check failed: {e}", {"error": str(e)}

    async def _create_alert(self, check_name: str, severity: str, message: str, details: dict):
        """Create and dispatch a health alert."""
        alert = HealthAlert(
            timestamp=datetime.now(), check_name=check_name, severity=severity, message=message, details=details
        )

        self._alerts.append(alert)

        # Log the alert
        log_func = logger.error if severity == "critical" else logger.warning
        log_func(f"HEALTH ALERT [{severity.upper()}] {check_name}: {message}")

        # Call alert callback if configured
        if self.alert_callback:
            try:
                await self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get current health monitoring status."""
        return {
            "running": self._running,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "failure_counts": self._failure_counts,
            "active_alerts": len([a for a in self._alerts if not a.acknowledged]),
            "total_alerts": len(self._alerts),
        }

    def get_alerts(
        self, acknowledged: bool | None = None, severity: str | None = None, limit: int = 100
    ) -> list[HealthAlert]:
        """Get filtered alerts."""
        alerts = self._alerts

        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]

    def acknowledge_alert(self, alert_index: int) -> bool:
        """Acknowledge an alert by index."""
        if 0 <= alert_index < len(self._alerts):
            self._alerts[alert_index].acknowledged = True
            return True
        return False


# Global service instance
_health_monitor: HealthMonitoringService | None = None


def get_health_monitor() -> HealthMonitoringService:
    """Get or create global health monitoring service."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitoringService()
    return _health_monitor


async def start_health_monitoring():
    """Start health monitoring on application startup."""
    monitor = get_health_monitor()
    await monitor.start()


async def stop_health_monitoring():
    """Stop health monitoring on application shutdown."""
    global _health_monitor
    if _health_monitor:
        await _health_monitor.stop()
