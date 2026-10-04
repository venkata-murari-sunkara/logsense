"""
Natural-language interface over stored analyses. Deliberately not a
free-form chatbot: each turn, we gather a compact snapshot of *real*
current data (stats, recent analyses, top priorities, common anomaly
patterns, and the specific block if one's mentioned) and instruct the
model to answer using only that data — the same grounding discipline as
the rest of the app, just applied to a conversational surface instead of
a single-block analysis.
"""
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Analysis, Block, EvaluationRun
from app.services import explanation

BLOCK_ID_PATTERN = re.compile(r"blk_-?\d+")

SYSTEM_INSTRUCTIONS = """You are the LogSense assistant, answering questions about a log anomaly detection system.

You will be given a snapshot of the system's current real data below. Answer the user's question using ONLY this data. If the answer isn't contained in the data provided, say so plainly instead of guessing — do not invent block IDs, numbers, or events that aren't in the snapshot. Keep answers short and in plain language; a reader may not have a technical background. When you reference a specific block, use its exact ID from the data."""


def _gather_context(db: Session, question: str) -> str:
    sections = []

    total_blocks = db.execute(select(func.count()).select_from(Block)).scalar_one()
    anomaly_count = db.execute(
        select(func.count()).select_from(Block).where(Block.true_label == "Anomaly")
    ).scalar_one()
    flagged_by_model = db.execute(
        select(func.count()).select_from(Block).where(Block.predicted_label == "Anomaly")
    ).scalar_one()
    flagged_unreviewed = db.execute(
        select(func.count())
        .select_from(Block)
        .where(Block.predicted_label == "Anomaly")
        .where(Block.reviewed_at.is_(None))
    ).scalar_one()
    total_analyses = db.execute(select(func.count()).select_from(Analysis)).scalar_one()
    sections.append(
        "OVERALL STATS:\n"
        f"- Total blocks on record: {total_blocks}\n"
        f"- Confirmed real anomalies (ground truth): {anomaly_count}\n"
        f"- Blocks the AI has ever flagged: {flagged_by_model}\n"
        f"- Flagged blocks not yet reviewed: {flagged_unreviewed}\n"
        f"- Total analyses run so far: {total_analyses}"
    )

    latest_eval = db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.status == "completed")
        .order_by(EvaluationRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_eval:
        sections.append(
            "LATEST ACCURACY TEST:\n"
            f"- Grounded (using evidence) accuracy: {latest_eval.grounded_accuracy * 100:.1f}%\n"
            f"- Ungrounded (guessing alone) accuracy: {latest_eval.ungrounded_accuracy * 100:.1f}%\n"
            f"- Sample size: {latest_eval.sample_size}, run at {latest_eval.created_at}"
        )

    recent = db.execute(
        select(Analysis).order_by(Analysis.created_at.desc()).limit(10)
    ).scalars().all()
    if recent:
        lines = "\n".join(
            f"- Block {a.block_id}: {a.predicted_label} ({a.confidence * 100:.1f}% confidence), "
            f"analyzed {a.created_at} via {a.source}"
            for a in recent
        )
        sections.append(f"MOST RECENT ANALYSES (newest first):\n{lines}")

    top_priorities = db.execute(
        select(Block)
        .where(Block.predicted_label == "Anomaly")
        .where(Block.reviewed_at.is_(None))
        .order_by(Block.predicted_confidence.desc().nulls_last())
        .limit(5)
    ).scalars().all()
    if top_priorities:
        lines = "\n".join(
            f"- Block {b.block_id}: {b.predicted_confidence * 100:.1f}% confidence, not yet reviewed"
            for b in top_priorities
        )
        sections.append(f"TOP UNREVIEWED PRIORITY CASES:\n{lines}")

    mentioned_ids = set(BLOCK_ID_PATTERN.findall(question))
    for block_id in list(mentioned_ids)[:3]:
        block = db.get(Block, block_id)
        if block is None:
            continue
        analysis = db.execute(
            select(Analysis)
            .where(Analysis.block_id == block_id)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        detail = (
            f"BLOCK {block_id} (specifically asked about):\n"
            f"- Ground truth: {block.true_label}\n"
            f"- AI verdict: {block.predicted_label} ({(block.predicted_confidence or 0) * 100:.1f}% confidence)\n"
            f"- History: {block.description}"
        )
        if analysis:
            detail += f"\n- Explanation from last analysis: {analysis.grounded_explanation}"
            if analysis.recommendation:
                detail += f"\n- Recommended fix: {analysis.recommendation}"
        else:
            detail += "\n- This block has not been analyzed yet."
        sections.append(detail)

    return "\n\n".join(sections)


def answer_question(db: Session, question: str, history: list[dict]) -> str:
    context = _gather_context(db, question)
    system_message = {"role": "system", "content": f"{SYSTEM_INSTRUCTIONS}\n\n--- CURRENT DATA SNAPSHOT ---\n{context}"}
    messages = [system_message, *history, {"role": "user", "content": question}]
    return explanation.complete_messages(messages)
