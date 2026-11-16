"""One environment file for local runs and persistent container configuration."""

import os
from pathlib import Path


def backend_env_file() -> Path:
    configured = os.environ.get("BACKING_ENV_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / ".env"
