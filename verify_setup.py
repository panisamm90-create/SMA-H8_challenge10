from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

REQUIRED_PACKAGES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "pydantic": "pydantic",
    "requests": "requests",
    "dotenv": "python-dotenv",
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "joblib": "joblib",
    "sklearn": "scikit-learn",
    "lightgbm": "lightgbm",
    "tables": "tables",
}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        print("FAIL: Python 3.11+ is required.")
        return 1

    missing = []
    for module_name, package_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module_name)
            print(f"OK: {package_name}")
        except Exception as error:
            print(f"FAIL: {package_name}: {error}")
            missing.append(package_name)

    if missing:
        print("\nInstall dependencies with: python -m pip install -r requirements.txt")
        return 1

    load_env_file(Path(__file__).resolve().parent / ".env")
    print("\nEnvironment:")
    ors_configured = bool(os.getenv("ORS_API_KEY"))
    print("  ORS_API_KEY:", "configured" if ors_configured else "MISSING (required)")
    print("  TOMTOM_API_KEY:", "configured" if os.getenv("TOMTOM_API_KEY") else "not configured (optional)")
    print("  EVENTS_API_KEY:", "configured" if os.getenv("EVENTS_API_KEY") else "not configured (optional)")
    print("  OPENAI_API_KEY:", "configured" if os.getenv("OPENAI_API_KEY") else "not configured (optional)")

    try:
        from backend.engines.accident_engine import AccidentEngine
        from backend.engines.traffic_engine import TrafficEngine
        AccidentEngine()
        TrafficEngine()
        print("\nOK: bundled ML models load successfully.")
    except Exception as error:
        print(f"\nFAIL: model loading error: {error}")
        return 1

    if not ors_configured:
        print("\nFAIL: Add ORS_API_KEY to .env before route analysis.")
        return 1

    print("\nSetup verification complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
