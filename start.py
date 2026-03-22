#!/usr/bin/env python3
"""
Archon Startup Script - Local-First Unified Server

Usage:
    python start.py                    # Start everything
    python start.py --stop             # Stop everything  
    python start.py --status           # Check status
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PID_FILE = Path("/tmp/archon.pid")
POSTGRES_PID_FILE = Path("/tmp/archon_postgres.pid")


def check_postgres():
    """Check if PostgreSQL binaries are available."""
    import shutil
    
    if shutil.which("pg_ctl") is None:
        print("✗ PostgreSQL not installed")
        print()
        print("Install PostgreSQL:")
        print("  Ubuntu/Debian:  sudo apt install postgresql postgresql-contrib")
        print("  macOS:          brew install postgresql@15")
        print("  Arch:           sudo pacman -S postgresql")
        return False
    
    return True


def init_postgres():
    """Initialize PostgreSQL data directory if needed."""
    data_dir = Path.home() / ".local/share/archon/postgres"
    
    if (data_dir / "PG_VERSION").exists():
        return True
    
    print("Initializing PostgreSQL...")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    result = subprocess.run(
        ["pg_ctl", "-D", str(data_dir), "initdb"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"✗ Failed to initdb: {result.stderr}")
        return False
    
    # Configure for local use
    with open(data_dir / "postgresql.conf", "a") as f:
        f.write("\n# Archon configuration\n")
        f.write("port = 5433\n")
        f.write("unix_socket_directories = '/tmp'\n")
        f.write("listen_addresses = '127.0.0.1'\n")
    
    # Trust local connections
    with open(data_dir / "pg_hba.conf", "w") as f:
        f.write("# Trust all local connections\n")
        f.write("local   all             all                                     trust\n")
        f.write("host    all             all             127.0.0.1/32            trust\n")
        f.write("host    all             all             ::1/128                 trust\n")
    
    print("✓ PostgreSQL initialized")
    return True


def start_postgres():
    """Start PostgreSQL."""
    data_dir = Path.home() / ".local/share/archon/postgres"
    log_file = Path.home() / ".local/share/archon/logs/postgres.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if already running
    result = subprocess.run(
        ["pg_ctl", "-D", str(data_dir), "status"],
        capture_output=True,
        text=True
    )
    
    if "server is running" in result.stdout:
        print("✓ PostgreSQL already running")
        return True
    
    print("Starting PostgreSQL...")
    result = subprocess.run(
        ["pg_ctl", "-D", str(data_dir), "-l", str(log_file), "start"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"✗ Failed to start: {result.stderr}")
        return False
    
    # Wait for it to be ready
    for _ in range(30):
        time.sleep(0.5)
        result = subprocess.run(
            ["pg_isready", "-h", "127.0.0.1", "-p", "5433"],
            capture_output=True
        )
        if result.returncode == 0:
            print("✓ PostgreSQL running on port 5433")
            return True
    
    print("✗ PostgreSQL failed to start within timeout")
    return False


def stop_postgres():
    """Stop PostgreSQL."""
    data_dir = Path.home() / ".local/share/archon/postgres"
    
    result = subprocess.run(
        ["pg_ctl", "-D", str(data_dir), "stop", "-m", "fast"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ PostgreSQL stopped")
        return True
    else:
        print("✓ PostgreSQL not running or already stopped")
        return True


def run_migrations():
    """Run database migrations."""
    print("Running database migrations...")
    
    python_dir = Path(__file__).parent / "python"
    migration_script = """
import asyncio
import sys
sys.path.insert(0, '.')
from src.server.services.database import initialize_database
from src.server.database.migrations import migrate
async def main():
    await initialize_database()
    success = await migrate()
    sys.exit(0 if success else 1)
asyncio.run(main())
"""
    result = subprocess.run(
        ["python", "-c", migration_script],
        cwd=python_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ Migrations complete")
        return True
    else:
        print(f"⚠ Migrations had issues: {result.stderr}")
        return True  # Continue anyway


def create_database():
    """Create archon database and user."""
    # Check if database exists
    result = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "-c", "SELECT 1 FROM pg_database WHERE datname='archon'"],
        capture_output=True,
        text=True
    )
    
    if "1" in result.stdout:
        print("✓ Database 'archon' exists")
        return True
    
    print("Creating database 'archon'...")
    subprocess.run(
        ["createdb", "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "archon"],
        capture_output=True
    )
    
    # Create user
    subprocess.run(
        ["psql", "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "-c", "CREATE USER archon"],
        capture_output=True
    )
    
    print("✓ Database created")
    return True


def start_server():
    """Start the Archon unified server."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"✓ Archon server already running (PID {pid})")
            return True
        except ProcessLookupError:
            PID_FILE.unlink()
    
    print("Starting Archon server...")
    
    # Change to python directory
    python_dir = Path(__file__).parent / "python"
    
    # Start server with uv
    proc = subprocess.Popen(
        ["uv", "run", "python", "-m", "uvicorn", "src.unified_main:app", 
         "--host", "127.0.0.1", "--port", "8181"],
        cwd=python_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    
    PID_FILE.write_text(str(proc.pid))
    
    # Wait for server to be ready
    for _ in range(30):
        time.sleep(0.5)
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:8181/health", timeout=1)
            print(f"✓ Archon server running on http://127.0.0.1:8181")
            return True
        except:
            pass
    
    print("✗ Server failed to start")
    return False


def stop_server():
    """Stop the Archon server."""
    if not PID_FILE.exists():
        print("✓ Archon server not running")
        return True
    
    pid = int(PID_FILE.read_text().strip())
    
    try:
        os.kill(pid, signal.SIGTERM)
        print("✓ Archon server stopped")
    except ProcessLookupError:
        print("✓ Archon server already stopped")
    
    PID_FILE.unlink(missing_ok=True)
    return True


def get_status():
    """Get status of all services."""
    print("=" * 60)
    print("Archon Status")
    print("=" * 60)
    
    # PostgreSQL
    data_dir = Path.home() / ".local/share/archon/postgres"
    result = subprocess.run(
        ["pg_ctl", "-D", str(data_dir), "status"],
        capture_output=True,
        text=True
    )
    pg_status = "✓ running" if "server is running" in result.stdout else "✗ stopped"
    print(f"  PostgreSQL: {pg_status}")
    
    # Archon server
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"  Archon server: ✓ running (PID {pid})")
            print(f"  API URL: http://127.0.0.1:8181")
            print(f"  MCP URL: http://127.0.0.1:8181/mcp")
        except ProcessLookupError:
            print("  Archon server: ✗ stopped (stale PID file)")
            PID_FILE.unlink()
    else:
        print("  Archon server: ✗ stopped")


async def check_ollama():
    """Check Ollama status."""
    import sys
    sys.path.insert(0, "python")
    from src.server.services.ollama_service import get_ollama_service
    
    service = get_ollama_service()
    health = await service.health_check()
    
    if not health["healthy"]:
        print("✗ Ollama not available")
        print()
        print(service.get_install_instructions())
        return False
    
    print(f"✓ Ollama running at {health['url']}")
    print(f"  Models: {', '.join(health['models'][:5])}")
    
    if not health["embedding_available"]:
        print(f"  Pulling embedding model: {health['embedding_model']}...")
        if not await service.pull_model(health["embedding_model"]):
            return False
    
    if not health["chat_available"]:
        print(f"  Pulling chat model: {health['chat_model']}...")
        if not await service.pull_model(health["chat_model"]):
            return False
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Archon Server Manager")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    parser.add_argument("--status", action="store_true", help="Show status")
    args = parser.parse_args()
    
    if args.status:
        get_status()
        return 0
    
    if args.stop:
        print("Stopping Archon...")
        stop_server()
        stop_postgres()
        return 0
    
    # Start everything
    print("=" * 60)
    print("Starting Archon")
    print("=" * 60)
    
    # Check Ollama
    import asyncio
    if not asyncio.run(check_ollama()):
        return 1
    
    if not check_postgres():
        return 1
    
    if not init_postgres():
        return 1
    
    if not start_postgres():
        return 1
    
    create_database()
    run_migrations()
    
    if not start_server():
        return 1
    
    print()
    print("=" * 60)
    print("✓ Archon is running!")
    print("=" * 60)
    print()
    print("  API:    http://127.0.0.1:8181")
    print("  MCP:    http://127.0.0.1:8181/mcp")
    print()
    print("  Logs:   ~/.local/share/archon/logs/")
    print()
    print("  Commands:")
    print("    python start.py --status   # Check status")
    print("    python start.py --stop     # Stop server")
    print()


if __name__ == "__main__":
    sys.exit(main())
