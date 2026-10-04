"""Creates all tables (and the pgvector extension) in the target Postgres database."""
import _bootstrap  # noqa: F401
from sqlalchemy import text

from app.database import Base, engine
from app import models  # noqa: F401  (ensures models are registered on Base.metadata)

if __name__ == "__main__":
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    print("Schema ready.")
