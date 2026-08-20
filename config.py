"""Credential loading.

Local development reads a .env file, which is gitignored and never committed.
In production (Railway, Docker) there is no .env -- the platform injects real
environment variables and this module reads those instead. Same code path,
no branching on environment.
"""

import os

from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


def load_env_file(path=ENV_FILE):
    """Read KEY=value lines from .env into the environment.

    Existing environment variables win, so a value injected by the deployment
    platform is never overwritten by a stale local file.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def require(name):
    """Return an environment variable, or exit with an actionable message."""
    load_env_file()
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set.\n"
            f"Local: add a line to {ENV_FILE.name}:  {name}=your-key-here\n"
            f"Deployed: set {name} in the platform's environment variables."
        )
    return value
