"""Run on the application host: python deploy/kronos/healthcheck.py."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.dl_prediction.remote import KronosClient  # noqa: E402

if __name__ == "__main__":
    import json

    print(json.dumps(KronosClient().status(), ensure_ascii=False, indent=2))
