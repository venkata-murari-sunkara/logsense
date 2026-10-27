import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, exists, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis, Block
from app.schemas import AnalysisResult, BlockDetail, BlockSummary
from app.services.detector import EVENT_COLUMNS
from app.services.pipeline import analyze_block

router = APIRouter(prefix="/api/blocks", tags=["blocks"])

# Confidence alone leaves huge ties in the priority queue (most flagged
# blocks sit at ~100%). These break those ties: blocks whose history
# includes an exception/error-type event first (checked directly against
# ground truth — 67.5% of real anomalies have one vs 7.0% of false alarms
# at 100% confidence, a real signal), then by total event volume, then by
# block_id so the order is fully stable.
ERROR_EVENT_CODES = ["E4", "E7", "E10", "E12", "E14", "E17", "E20"]


def _has_error_event_expr():
    return or_(*(cast(Block.event_counts[code].astext, Integer) > 0 for code in ERROR_EVENT_CODES))


def _total_event_count_expr():
    return sum(cast(Block.event_counts[code].astext, Integer) for code in EVENT_COLUMNS)


def _has_analysis_expr():
    return exists(select(1).where(Analysis.block_id == Block.block_id))


@router.get("", response_model=list[BlockSummary])
def list_blocks(
    label: str | None = Query(None, description="Filter by true_label: Normal or Anomaly"),
    predicted_label: str | None = Query(None, description="Filter by model verdict"),
    search: str | None = Query(None, description="Substring match on block_id"),
    reviewed: bool | None = Query(None, description="Filter by whether a human has explicitly reviewed the block"),
    sort: str = Query("block_id", description="'block_id' or 'confidence_desc'"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    has_analysis_expr = _has_analysis_expr()
    stmt = select(Block, has_analysis_expr)
    if label:
        stmt = stmt.where(Block.true_label == label)
    if predicted_label:
        stmt = stmt.where(Block.predicted_label == predicted_label)
    if search:
        stmt = stmt.where(Block.block_id.ilike(f"%{search}%"))
    if reviewed is not None:
        stmt = stmt.where(Block.reviewed_at.is_not(None) if reviewed else Block.reviewed_at.is_(None))
    if sort == "confidence_desc":
        stmt = stmt.order_by(
            Block.predicted_confidence.desc().nulls_last(),
            _has_error_event_expr().desc(),
            _total_event_count_expr().desc(),
            Block.block_id.asc(),
        )
    else:
        stmt = stmt.order_by(Block.block_id)
    stmt = stmt.limit(limit).offset(offset)
    rows = db.execute(stmt).all()
    return [
        BlockSummary.model_validate(block).model_copy(update={"has_analysis": has_analysis})
        for block, has_analysis in rows
    ]


@router.get("/{block_id}", response_model=BlockDetail)
def get_block(block_id: str, db: Session = Depends(get_db)):
    block = db.get(Block, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    has_analysis = db.execute(
        select(exists(select(1).where(Analysis.block_id == block_id)))
    ).scalar_one()
    return BlockDetail.model_validate(block).model_copy(update={"has_analysis": has_analysis})


@router.post("/{block_id}/review", response_model=BlockDetail)
def mark_reviewed(block_id: str, db: Session = Depends(get_db)):
    """The only place reviewed_at is ever set — an explicit human action,
    never a side effect of running the AI pipeline (Analyze or Simulation)."""
    block = db.get(Block, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    block.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(block)
    has_analysis = db.execute(
        select(exists(select(1).where(Analysis.block_id == block_id)))
    ).scalar_one()
    return BlockDetail.model_validate(block).model_copy(update={"has_analysis": has_analysis})


@router.post("/{block_id}/analyze", response_model=AnalysisResult)
def analyze(
    block_id: str,
    include_ungrounded: bool = Query(True),
    top_k: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    block = db.get(Block, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")

    analysis = analyze_block(db, block, include_ungrounded=include_ungrounded, top_k=top_k)
    return AnalysisResult(
        id=analysis.id,
        block_id=analysis.block_id,
        predicted_label=analysis.predicted_label,
        confidence=analysis.confidence,
        source=analysis.source,
        true_label=block.true_label,
        grounded_explanation=analysis.grounded_explanation,
        ungrounded_explanation=analysis.ungrounded_explanation,
        recommendation=analysis.recommendation,
        evidence=analysis.evidence,
        created_at=analysis.created_at,
    )
