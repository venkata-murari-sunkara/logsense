from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # Neon's serverless compute auto-suspends only when there are zero open
    # connections. SQLAlchemy's default pool doesn't actually close a
    # connection on checkin — it parks it open for reuse — so after the
    # very first request, one connection stays alive in the background
    # forever, and Neon's compute never gets to suspend no matter how
    # little traffic the app actually sees. This app's load is bursty
    # (occasional requests, a simulation tick every 5-20s while running,
    # nothing the rest of the time), not sustained, so paying a fresh
    # connection's setup cost per request is the right trade: NullPool
    # opens one connection per checkout and genuinely closes it on
    # checkin, so idle periods are actually idle and billing follows
    # real usage instead of running 24/7.
    poolclass=NullPool,
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
