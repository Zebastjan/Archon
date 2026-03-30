#!/usr/bin/env python3
"""Archon Health Monitor - Comprehensive system health checks.

This script monitors the Archon system and alerts if anything is wrong.
It checks:
- Server health (API responding)
- Database connectivity
- Entity counts per repo
- Recent indexing activity
- Git hooks status
- Container status

Usage:
    python scripts/health_monitor.py              # Run all checks
    python scripts/health_monitor.py --alert      # Alert on failures
    python scripts/health_monitor.py --watch    # Continuous monitoring

Exit codes:
    0 - All healthy
    1 - One or more issues detected
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx


@dataclass
class HealthCheck:
    """Result of a health check."""

    name: str
    status: str  # "healthy", "warning", "error"
    message: str
    details: dict[str, Any] | None = None


class ArchonHealthMonitor:
    """Monitor Archon system health."""

    def __init__(self, api_url: str = "http://localhost:8181"):
        self.api_url = api_url
        self.checks: list[HealthCheck] = []

    async def run_all_checks(self) -> list[HealthCheck]:
        """Run all health checks."""
        self.checks = []

        # Run checks
        self.checks.append(await self.check_server_health())
        self.checks.append(await self.check_database())
        self.checks.append(await self.check_repos())
        self.checks.append(await self.check_git_hooks())
        self.checks.append(await self.check_container())
        self.checks.append(await self.check_recent_activity())

        return self.checks

    async def check_server_health(self) -> HealthCheck:
        """Check if API server is responding."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    return HealthCheck(
                        name="API Server",
                        status="healthy",
                        message=f"Server responding on {self.api_url}",
                        details={
                            "status": data.get("status"),
                            "service": data.get("service"),
                        },
                    )
                else:
                    return HealthCheck(
                        name="API Server",
                        status="error",
                        message=f"Server returned status {response.status_code}",
                        details={"status_code": response.status_code},
                    )
        except Exception as e:
            return HealthCheck(
                name="API Server",
                status="error",
                message=f"Cannot connect to server: {e}",
                details={"error": str(e)},
            )

    async def check_database(self) -> HealthCheck:
        """Check database connectivity."""
        try:
            # Try to query the database via API
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_url}/api/code_repos")
                if response.status_code == 200:
                    repos = response.json()
                    return HealthCheck(
                        name="Database",
                        status="healthy",
                        message=f"Database connected, {len(repos)} repos",
                        details={"repo_count": len(repos)},
                    )
                else:
                    return HealthCheck(
                        name="Database",
                        status="error",
                        message=f"Database query failed: {response.status_code}",
                        details={"status_code": response.status_code},
                    )
        except Exception as e:
            return HealthCheck(
                name="Database",
                status="error",
                message=f"Database connection failed: {e}",
                details={"error": str(e)},
            )

    async def check_repos(self) -> HealthCheck:
        """Check repository entity counts."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_url}/api/code_repos")
                if response.status_code == 200:
                    repos = response.json()

                    total_entities = sum(r.get("entities_count", 0) for r in repos)

                    if total_entities == 0:
                        return HealthCheck(
                            name="Repositories",
                            status="warning",
                            message=f"{len(repos)} repos but 0 entities indexed",
                            details={"repos": len(repos), "total_entities": 0},
                        )

                    return HealthCheck(
                        name="Repositories",
                        status="healthy",
                        message=f"{len(repos)} repos with {total_entities} entities",
                        details={
                            "repo_count": len(repos),
                            "total_entities": total_entities,
                            "repos": [
                                {
                                    "name": r["name"],
                                    "entities": r.get("entities_count", 0),
                                }
                                for r in repos
                            ],
                        },
                    )
                else:
                    return HealthCheck(
                        name="Repositories",
                        status="error",
                        message="Failed to fetch repos",
                        details={"status_code": response.status_code},
                    )
        except Exception as e:
            return HealthCheck(
                name="Repositories",
                status="error",
                message=f"Failed to check repos: {e}",
                details={"error": str(e)},
            )

    async def check_git_hooks(self) -> HealthCheck:
        """Check if git hooks are configured."""
        try:
            # Check if post-commit hook exists and is executable
            result = subprocess.run(
                ["ls", "-la", ".git/hooks/post-commit"],
                capture_output=True,
                text=True,
                cwd="/home/zebastjan/dev/archon",
            )

            if result.returncode == 0 and "x" in result.stdout:
                return HealthCheck(
                    name="Git Hooks",
                    status="healthy",
                    message="post-commit hook configured and executable",
                    details={},
                )
            elif result.returncode == 0:
                return HealthCheck(
                    name="Git Hooks",
                    status="warning",
                    message="post-commit hook exists but not executable",
                    details={"output": result.stdout},
                )
            else:
                return HealthCheck(
                    name="Git Hooks",
                    status="error",
                    message="post-commit hook not found",
                    details={},
                )
        except Exception as e:
            return HealthCheck(
                name="Git Hooks",
                status="error",
                message=f"Failed to check git hooks: {e}",
                details={"error": str(e)},
            )

    async def check_container(self) -> HealthCheck:
        """Check if Docker container is running."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=archon", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
            )

            if "archon" in result.stdout:
                return HealthCheck(
                    name="Docker Container",
                    status="healthy",
                    message="Archon container is running",
                    details={},
                )
            else:
                return HealthCheck(
                    name="Docker Container",
                    status="error",
                    message="Archon container not running",
                    details={"output": result.stdout},
                )
        except Exception as e:
            return HealthCheck(
                name="Docker Container",
                status="error",
                message=f"Failed to check container: {e}",
                details={"error": str(e)},
            )

    async def check_recent_activity(self) -> HealthCheck:
        """Check for recent indexing activity."""
        try:
            # Check if there are any recent log entries
            result = subprocess.run(
                ["docker", "logs", "archon", "--since", "1h"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")

                # Count relevant log entries
                entity_count = sum(1 for line in lines if "entity" in line.lower())
                error_count = sum(1 for line in lines if "error" in line.lower())

                if error_count > 10:
                    return HealthCheck(
                        name="Recent Activity",
                        status="warning",
                        message=f"{error_count} errors in last hour",
                        details={"errors": error_count, "entities": entity_count},
                    )

                return HealthCheck(
                    name="Recent Activity",
                    status="healthy",
                    message=f"Active - {entity_count} entity operations, {error_count} errors",
                    details={"errors": error_count, "entities": entity_count},
                )
            else:
                return HealthCheck(
                    name="Recent Activity",
                    status="warning",
                    message="Cannot read container logs",
                    details={},
                )
        except Exception as e:
            return HealthCheck(
                name="Recent Activity",
                status="error",
                message=f"Failed to check activity: {e}",
                details={"error": str(e)},
            )

    def print_report(self) -> None:
        """Print health check report."""
        print("\n" + "=" * 70)
        print("  ARCHON HEALTH REPORT")
        print("=" * 70)
        print(f"  Time: {datetime.now().isoformat()}")
        print(f"  API: {self.api_url}")
        print("-" * 70)

        healthy = sum(1 for c in self.checks if c.status == "healthy")
        warnings = sum(1 for c in self.checks if c.status == "warning")
        errors = sum(1 for c in self.checks if c.status == "error")

        for check in self.checks:
            status_icon = {"healthy": "✓", "warning": "⚠", "error": "✗"}.get(
                check.status, "?"
            )

            print(f"\n  {status_icon} {check.name}: {check.status.upper()}")
            print(f"    {check.message}")

            if check.details:
                for key, value in check.details.items():
                    if isinstance(value, list) and len(value) > 0:
                        print(f"    {key}: {len(value)} items")
                    else:
                        print(f"    {key}: {value}")

        print("\n" + "-" * 70)
        print(f"  Summary: {healthy} healthy, {warnings} warnings, {errors} errors")
        print("=" * 70 + "\n")

        return errors == 0


async def main():
    parser = argparse.ArgumentParser(description="Archon Health Monitor")
    parser.add_argument("--alert", action="store_true", help="Send alerts on failures")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring")
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8181",
        help="API URL (default: http://localhost:8181)",
    )
    args = parser.parse_args()

    monitor = ArchonHealthMonitor(api_url=args.api_url)

    if args.watch:
        print(f"Starting continuous monitoring (interval: {args.interval}s)")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                await monitor.run_all_checks()
                monitor.print_report()

                # Check if there are errors
                errors = [c for c in monitor.checks if c.status == "error"]
                if errors and args.alert:
                    print("⚠ ALERT: Errors detected!")
                    for check in errors:
                        print(f"  - {check.name}: {check.message}")

                print(f"\nNext check in {args.interval} seconds...")
                time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
    else:
        await monitor.run_all_checks()
        healthy = monitor.print_report()

        if not healthy and args.alert:
            errors = [c for c in monitor.checks if c.status == "error"]
            print("\n⚠ ALERT: System has errors!")
            for check in errors:
                print(f"  - {check.name}: {check.message}")

        sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    asyncio.run(main())
