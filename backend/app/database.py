from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # Each evaluation run spins up to BATCH_SIZE worker threads, each holding
    # its own connection for the retrieval step. The default pool (5 + 10
    # overflow = 15) was too small for even one run's worth of workers plus
    # normal request traffic, and two concurrent runs exhausted it outright,
    # stalling both on 30s connection-checkout timeouts.
    pool_size=20,
    max_overflow=20,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
