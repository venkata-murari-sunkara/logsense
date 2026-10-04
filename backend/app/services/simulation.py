"""
Live simulation: feeds stored (not-yet-analyzed) blocks into the real
detection -> retrieval -> explanation pipeline on a timer, so the dashboard
fills in the same way it would if new blocks were actually arriving. Every
tick runs the exact pipeline used by the manual "Analyze" button — nothing
here is faked or pre-scripted, it just picks which real stored block goes
through it next.
"""
import datetime
import logging
import random
import threading

from sqlalchemy import exists, func, select

from app.database import SessionLocal
from app.models import Analysis, Block
from app.services.pipeline import analyze_block

logger = logging.getLogger("logsense.simulation")

MIN_INTERVAL_SECONDS = 5.0
ANOMALY_BIAS = 0.4  # fraction of ticks that pull from model-flagged Anomaly blocks


class _SimulationState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.running = False
        self.interval_seconds = 20.0
        self.started_at: datetime.datetime | None = None
        self.ticks = 0
        self.errors = 0
        self.last_block_id: str | None = None
        self.last_verdict: str | None = None
        self.last_ran_at: datetime.datetime | None = None
        self.last_error: str | None = None


_state = _SimulationState()


def _has_analysis_expr():
    return exists(select(1).where(Analysis.block_id == Block.block_id))


def _pick_block(db) -> Block | None:
    label = "Anomaly" if random.random() < ANOMALY_BIAS else "Normal"
    stmt = (
        select(Block)
        .where(Block.predicted_label == label)
        .where(~_has_analysis_expr())
        .order_by(func.random())
        .limit(1)
    )
    block = db.execute(stmt).scalar_one_or_none()
    if block is not None:
        return block
    # That class is exhausted (every such block already analyzed) — fall
    # back to any unanalyzed block at all rather than stalling forever.
    stmt = select(Block).where(~_has_analysis_expr()).order_by(func.random()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def _tick() -> None:
    db = SessionLocal()
    try:
        block = _pick_block(db)
        if block is None:
            with _state.lock:
                _state.last_error = "No unanalyzed blocks remain"
            logger.warning("simulation: no unanalyzed blocks remain")
            return
        analysis = analyze_block(db, block, include_ungrounded=False, source="simulation")
        with _state.lock:
            _state.ticks += 1
            _state.last_block_id = block.block_id
            _state.last_verdict = analysis.predicted_label
            _state.last_ran_at = datetime.datetime.now(datetime.timezone.utc)
            _state.last_error = None
    except Exception as exc:  # noqa: BLE001
        logger.warning("simulation tick failed: %s", exc)
        with _state.lock:
            _state.errors += 1
            _state.last_error = str(exc)
    finally:
        db.close()


def _loop(interval_seconds: float) -> None:
    while not _state.stop_event.is_set():
        _tick()
        _state.stop_event.wait(interval_seconds)


def start(interval_seconds: float) -> dict:
    interval_seconds = max(interval_seconds, MIN_INTERVAL_SECONDS)
    with _state.lock:
        if _state.running:
            return status()
        _state.stop_event.clear()
        _state.running = True
        _state.interval_seconds = interval_seconds
        _state.started_at = datetime.datetime.now(datetime.timezone.utc)
        _state.ticks = 0
        _state.errors = 0
        thread = threading.Thread(target=_loop, args=(interval_seconds,), daemon=True)
        _state.thread = thread
        thread.start()
    return status()


def stop() -> dict:
    with _state.lock:
        _state.stop_event.set()
        _state.running = False
        thread = _state.thread
        _state.thread = None
    if thread is not None:
        thread.join(timeout=2)
    return status()


def status() -> dict:
    with _state.lock:
        return {
            "running": _state.running,
            "interval_seconds": _state.interval_seconds,
            "started_at": _state.started_at,
            "ticks": _state.ticks,
            "errors": _state.errors,
            "last_block_id": _state.last_block_id,
            "last_verdict": _state.last_verdict,
            "last_ran_at": _state.last_ran_at,
            "last_error": _state.last_error,
        }
