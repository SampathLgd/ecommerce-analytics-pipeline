"""
Phase 0 - deliverable: verify the Postgres connection works before building
anything on top of it.

Usage:
    python ingestion/test_connection.py
"""
import sys

from config import get_engine
from sqlalchemy import text


def main() -> None:
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            print(f"[OK] Connected to Postgres. SELECT 1 returned: {result}")
    except Exception as e:
        print(f"[ERROR] Could not connect to Postgres: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
