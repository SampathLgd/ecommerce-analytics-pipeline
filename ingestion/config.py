"""
Shared Postgres connection config for ingestion scripts.

Reads from environment variables so the same code works locally (Phase 0's
docker-compose.yml) without hardcoding credentials. Defaults match a typical
docker-compose Postgres service.
"""
import os
from sqlalchemy import create_engine

DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5433")
DB_NAME = os.environ.get("POSTGRES_DB", "ecommerce")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine():
    """Return a SQLAlchemy engine for the Postgres instance."""
    return create_engine(DB_URL)
