"""Migrate only the deployed database, then serve one API process."""
import subprocess
import sys
from pathlib import Path

import uvicorn

def main() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
    uvicorn.run("main:app", host="0.0.0.0", port=8808, workers=1,
                proxy_headers=True, forwarded_allow_ips="*", access_log=False)


if __name__ == "__main__":
    main()
