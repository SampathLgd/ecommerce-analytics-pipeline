# ingestion/apply_schema.py — one-off script to apply sql/schema.sql
from pathlib import Path
from sqlalchemy import text
from config import get_engine

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

def main():
    engine = get_engine()
    sql = SCHEMA_PATH.read_text()
    with engine.begin() as conn:
        conn.execute(text(sql))
    print(f"Applied {SCHEMA_PATH}")

if __name__ == "__main__":
    main()