#!/usr/bin/env python3
"""
Development wrapper for MCP server with auto-reload.

Usage:
    python mcp_dev_wrapper.py                    # Start with auto-reload
    python mcp_dev_wrapper.py --no-reload        # Start without reload (prod mode)
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("mcp-dev-wrapper")


def get_mtime(path: Path) -> float:
    """Get the latest modification time of all Python files in a directory."""
    latest_mtime = 0.0
    try:
        for py_file in path.rglob("*.py"):
            try:
                mtime = py_file.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
            except OSError:
                continue
    except Exception as e:
        logger.warning(f"Error checking mtime: {e}")
    return latest_mtime


def run_server():
    """Run the MCP server as a subprocess."""
    logger.info("🚀 Starting MCP server...")
    return subprocess.Popen(
        [sys.executable, "-m", "src.mcp_server.mcp_server"],
        cwd="/app",
        env={**os.environ, "PYTHONPATH": "/app"},
    )


def main():
    parser = argparse.ArgumentParser(description="MCP Development Wrapper")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    parser.add_argument("--watch", type=str, default="/app/src", help="Directory to watch")
    args = parser.parse_args()

    watch_path = Path(args.watch)
    if not watch_path.exists():
        logger.error(f"Watch path does not exist: {watch_path}")
        sys.exit(1)

    if args.no_reload:
        logger.info("Starting without auto-reload")
        process = run_server()
        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait()
        sys.exit(process.returncode)

    # Auto-reload mode
    logger.info(f"👁️  Watching {watch_path} for changes...")

    process = run_server()
    last_mtime = get_mtime(watch_path)
    check_interval = 0.5  # seconds

    try:
        while True:
            time.sleep(check_interval)

            # Check if process died
            if process.poll() is not None:
                logger.error("MCP server process exited unexpectedly!")
                sys.exit(1)

            # Check for file changes
            current_mtime = get_mtime(watch_path)
            if current_mtime > last_mtime:
                logger.info("📝 Changes detected, reloading...")

                # Graceful shutdown
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Force killing server...")
                    process.kill()
                    process.wait()

                # Restart
                process = run_server()
                last_mtime = current_mtime
                logger.info("✅ Server reloaded")

    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        logger.info("👋 Goodbye")


if __name__ == "__main__":
    main()
