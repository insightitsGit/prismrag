"""Load .env and run postgres store tests."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _load_dotenv() -> None:
    p = Path(__file__).resolve().parents[1] / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        os.environ.setdefault(key.strip(), val)


if __name__ == "__main__":
    _load_dotenv()
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "pytest", "tests/test_lib_postgres_store.py", "-v", "--tb=short"],
            cwd=str(Path(__file__).resolve().parents[1]),
        )
    )
