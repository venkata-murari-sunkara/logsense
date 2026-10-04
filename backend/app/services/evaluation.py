import datetime
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Block, EvaluationResult, EvaluationRun
from app.services import explanation
from app.services.retrieval import get_similar_incidents

logger = logging.getLogger("logsense.evaluation")

ANOMALY_WORDS = [
    "anomaly", "anomalous", "fail", "error", "issue", "problem",
    "unusual", "concern", "unexpected", "corrupt", "abnormal",
]
NORMAL_WORDS = [
    "normal", "routine", "expected", "no issue", "no problem",
    "successful", "healthy", "nothing wrong", "not a problem",
]

# Max blocks in flight at once. Concurrency here buys parallel pgvector
# retrieval and per-block error isolation; it does NOT buy more Groq
# throughput than the free-tier quota allows — every worker shares the same
# global call throttle in explanation.py, so this just bounds how many
# blocks are queued up waiting for their turn rather than racing unbounded.
BATCH_SIZE = 8


def classify_verdict(explanation_text: str) -> str:
    """Simple keyword check: does the explanation conclude 'Anomaly' or 'Normal'?"""
    text = explanation_text.lower()
    anomaly_hits = sum(1 for w in ANOMALY_WORDS if w in text)
    normal_hits = sum(1 for w in NORMAL_WORDS if w in text)
    return "Anomaly" if anomaly_hits > normal_hits else "Normal"


def _sample_blocks(db: Session, sample_size: int) -> list[Block]:
    per_class = max(sample_size // 2, 1)
    anomalies = db.execute(
        select(Block)
        .where(Block.true_label == "Anomaly")
        .order_by(func.random())
        .limit(per_class)
    ).scalars().all()
    normals = db.execute(
        select(Block)
        .where(Block.true_label == "Normal")
        .order_by(func.random())
        .limit(sample_size - len(anomalies))
    ).scalars().all()
    blocks = list(anomalies) + list(normals)
    # Free-tier LLM quotas can cut a run off mid-way (daily/per-minute token caps).
    # Interleave classes so any prefix of this list is still a roughly balanced
    # sample instead of "all anomalies, then all normals".
    random.shuffle(blocks)
    return blocks


def _process_block(block_data: dict) -> dict:
    """Runs the grounded/ungrounded pipeline for one block.

    Executes in a worker thread, so it opens its own DB session (SQLAlchemy
    sessions aren't thread-safe) and never lets an exception escape — a
    block that fails even after explanation.py's own retries is reported
    back as a failure instead of killing the whole evaluation run.
    """
    bid = block_data["block_id"]
    db = SessionLocal()
    try:
        evidence = get_similar_incidents(
            db, block_data["event_counts"], top_k=3, exclude_block_id=bid
        )
        grounded_text = explanation.generate_explanation(block_data["event_counts"], evidence)
        ungrounded_text = explanation.generate_explanation_ungrounded(block_data["event_counts"])
        grounded_verdict = classify_verdict(grounded_text)
        ungrounded_verdict = classify_verdict(ungrounded_text)
        return {
            "ok": True,
            "block_id": block_data["block_id"],
            "true_label": block_data["true_label"],
            "grounded_verdict": grounded_verdict,
            "grounded_correct": grounded_verdict == block_data["true_label"],
            "ungrounded_verdict": ungrounded_verdict,
            "ungrounded_correct": ungrounded_verdict == block_data["true_label"],
        }
    except Exception as exc:  # noqa: BLE001
        # A silent failure here previously looked identical to a hang: the
        # run just sat at 0 results with no visible signal while retries
        # played out. Log it so a stalled run is diagnosable in real time.
        logger.warning("block %s failed after retries: %s", bid, exc)
        return {"ok": False, "block_id": block_data["block_id"], "error": str(exc)}
    finally:
        db.close()


def run_evaluation(run_id: int, sample_size: int) -> None:
    """Runs in a background task with its own DB session.

    Blocks are processed concurrently in a bounded pool (BATCH_SIZE at a
    time) rather than one at a time or fully unbounded. Each block's result
    is committed as soon as it lands, so a later failure — or the process
    being killed — never wipes out already-collected results.
    """
    db = SessionLocal()
    try:
        run = db.get(EvaluationRun, run_id)
        blocks = _sample_blocks(db, sample_size)
        block_dicts = [
            {"block_id": b.block_id, "event_counts": b.event_counts, "true_label": b.true_label}
            for b in blocks
        ]

        grounded_correct_count = 0
        ungrounded_correct_count = 0
        succeeded = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
            futures = [executor.submit(_process_block, bd) for bd in block_dicts]
            for future in as_completed(futures):
                result = future.result()
                if not result["ok"]:
                    failed += 1
                    continue

                succeeded += 1
                grounded_correct_count += int(result["grounded_correct"])
                ungrounded_correct_count += int(result["ungrounded_correct"])
                db.add(
                    EvaluationResult(
                        evaluation_run_id=run_id,
                        block_id=result["block_id"],
                        true_label=result["true_label"],
                        grounded_verdict=result["grounded_verdict"],
                        grounded_correct=result["grounded_correct"],
                        ungrounded_verdict=result["ungrounded_verdict"],
                        ungrounded_correct=result["ungrounded_correct"],
                    )
                )
                db.commit()

        if succeeded == 0:
            raise RuntimeError(f"All {failed} sampled blocks failed; no results were collected")

        run.grounded_accuracy = grounded_correct_count / succeeded
        run.ungrounded_accuracy = ungrounded_correct_count / succeeded
        run.failed_count = failed
        run.status = "completed"
        run.completed_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        run = db.get(EvaluationRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error = str(exc)
            run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
