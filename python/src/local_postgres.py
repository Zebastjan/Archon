"""
Local PostgreSQL Management

Treats Postgres like SQLite - local data directory, no Docker, no system service.
Just a data directory managed by Archon.
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from src.server.config.yaml_config import get_config, ConfigError


class LocalPostgres:
    """Manages a local PostgreSQL instance."""
    
    def __init__(self):
        self.config = get_config().database
        self.data_dir = Path(self.config.data_dir).expanduser()
        self.pid_file = self.data_dir / "postmaster.pid"
        self.log_file = Path(get_config().paths.logs) / "postgres.log"
        
    def is_installed(self) -> bool:
        """Check if postgres binaries are available."""
        return shutil.which("initdb") is not None
    
    def is_initialized(self) -> bool:
        """Check if data directory is initialized."""
        return (self.data_dir / "PG_VERSION").exists()
    
    def is_running(self) -> bool:
        """Check if postgres is running."""
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file) as f:
                pid = int(f.readline().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ValueError, OSError, ProcessLookupError):
            return False
    
    def get_install_instructions(self) -> str:
        """Get OS-specific install instructions."""
        if sys.platform == "linux":
            return """
PostgreSQL is not installed. Install it with:

  Ubuntu/Debian:  sudo apt install postgresql postgresql-contrib
  Fedora:         sudo dnf install postgresql-server postgresql-contrib
  Arch:           sudo pacman -S postgresql

Then disable the system service (we manage it ourselves):
  sudo systemctl stop postgresql
  sudo systemctl disable postgresql
"""
        elif sys.platform == "darwin":
            return """
PostgreSQL is not installed. Install it with:

  Homebrew:       brew install postgresql@15
  MacPorts:       sudo port install postgresql15 +universal
"""
        else:
            return f"""
PostgreSQL is not installed for platform: {sys.platform}

Download from: https://www.postgresql.org/download/
"""
    
    def initdb(self) -> bool:
        """Initialize the database cluster."""
        if self.is_initialized():
            print(f"✓ Database already initialized at {self.data_dir}")
            return True
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Initializing PostgreSQL at {self.data_dir}...")
        result = subprocess.run(
            ["initdb", "-D", str(self.data_dir), "--encoding=UTF8", "--locale=en_US.UTF-8"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"✗ initdb failed: {result.stderr}")
            return False
        
        print(f"✓ Database initialized")
        return True
    
    def create_user(self) -> bool:
        """Create the archon user and database."""
        user = self.config.user
        dbname = self.config.name
        
        # Create user
        result = subprocess.run(
            ["createuser", "-h", str(self.data_dir), "-p", str(self.config.port), "-s", user],
            capture_output=True,
            text=True
        )
        if result.returncode != 0 and "already exists" not in result.stderr:
            print(f"Note: createuser: {result.stderr.strip()}")
        else:
            print(f"✓ User '{user}' ready")
        
        # Create database
        result = subprocess.run(
            ["createdb", "-h", str(self.data_dir), "-p", str(self.config.port), "-O", user, dbname],
            capture_output=True,
            text=True
        )
        if result.returncode != 0 and "already exists" not in result.stderr:
            print(f"Note: createdb: {result.stderr.strip()}")
        else:
            print(f"✓ Database '{dbname}' ready")
        
        return True
    
    def start(self, wait: bool = True) -> bool:
        """Start PostgreSQL."""
        if self.is_running():
            print(f"✓ PostgreSQL already running (PID {self._get_pid()})")
            return True
        
        if not self.is_initialized():
            if not self.initdb():
                return False
        
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Starting PostgreSQL on port {self.config.port}...")
        
        # Start postgres
        with open(self.log_file, "a") as log:
            result = subprocess.run(
                ["pg_ctl", "-D", str(self.data_dir), "-l", str(self.log_file), "start"],
                stdout=log,
                stderr=subprocess.STDOUT
            )
        
        if result.returncode != 0:
            print(f"✗ Failed to start PostgreSQL (see {self.log_file})")
            return False
        
        if wait:
            # Wait for it to be ready
            for i in range(30):
                if self.is_running():
                    time.sleep(0.5)
                    break
                time.sleep(0.1)
        
        print(f"✓ PostgreSQL started on port {self.config.port}")
        
        # Create user/db if needed
        self.create_user()
        
        return True
    
    def stop(self) -> bool:
        """Stop PostgreSQL."""
        if not self.is_running():
            print("PostgreSQL not running")
            return True
        
        print("Stopping PostgreSQL...")
        result = subprocess.run(
            ["pg_ctl", "-D", str(self.data_dir), "stop", "-m", "fast"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ PostgreSQL stopped")
            return True
        else:
            print(f"✗ Failed to stop: {result.stderr}")
            return False
    
    def status(self) -> dict:
        """Get status of PostgreSQL."""
        return {
            "installed": self.is_installed(),
            "initialized": self.is_initialized(),
            "running": self.is_running(),
            "data_dir": str(self.data_dir),
            "port": self.config.port,
            "pid": self._get_pid() if self.is_running() else None,
        }
    
    def _get_pid(self) -> int | None:
        """Get PID of running postgres."""
        try:
            with open(self.pid_file) as f:
                return int(f.readline().strip())
        except (FileNotFoundError, ValueError):
            return None
    
    def connect(self):
        """Connect using psql."""
        subprocess.run([
            "psql",
            "-h", str(self.data_dir),
            "-p", str(self.config.port),
            "-U", self.config.user,
            self.config.name
        ])


def main():
    """CLI for managing local PostgreSQL."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage local PostgreSQL")
    parser.add_argument("command", choices=["start", "stop", "status", "init", "psql"])
    args = parser.parse_args()
    
    pg = LocalPostgres()
    
    if not pg.is_installed():
        print(pg.get_install_instructions())
        sys.exit(1)
    
    if args.command == "start":
        if not pg.start():
            sys.exit(1)
    elif args.command == "stop":
        if not pg.stop():
            sys.exit(1)
    elif args.command == "status":
        status = pg.status()
        for key, value in status.items():
            print(f"  {key}: {value}")
    elif args.command == "init":
        if not pg.initdb():
            sys.exit(1)
    elif args.command == "psql":
        pg.connect()


if __name__ == "__main__":
    main()
