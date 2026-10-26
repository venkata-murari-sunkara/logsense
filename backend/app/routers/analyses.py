from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis, Block
from app.schemas import AnalysisResult, AnalysisSummary, IncidentTicket
from app.services.ticket import build_incident_ticket

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(
    block_id: str | None = Query(None),
    predicted_label: str | None = Query(None, description="Filter by AI verdict: Anomaly or Normal"),
    source: str | None = Query(None, description="Filter by source: manual or simulation"),
    reviewed: bool | None = Query(None, description="Filter by whether a human has explicitly reviewed the block"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Analysis, Block.reviewed_at)
        .join(Block, Block.block_id == Analysis.block_id)
        .order_by(Analysis.created_at.desc())
    )
    if block_id:
        stmt = stmt.where(Analysis.block_id == block_id)
    if predicted_label:
        stmt = stmt.where(Analysis.predicted_label == predicted_label)
    if source:
        stmt = stmt.where(Analysis.source == source)
    if reviewed is not None:
        stmt = stmt.where(Block.reviewed_at.is_not(None) if reviewed else Block.reviewed_at.is_(None))
    stmt = stmt.limit(limit).offset(offset)
    rows = db.execute(stmt).all()
    return [
        AnalysisSummary.model_validate(analysis).model_copy(update={"reviewed_at": reviewed_at})
        for analysis, reviewed_at in rows
    ]


@router.get("/{analysis_id}", response_model=AnalysisResult)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    block = db.get(Block, analysis.block_id)
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
        reviewed_at=block.reviewed_at,
    )


@router.get("/{analysis_id}/ticket", response_model=IncidentTicket)
def get_incident_ticket(analysis_id: int, db: Session = Depends(get_db)):
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.predicted_label != "Anomaly":
        raise HTTPException(
            status_code=400,
            detail="No incident ticket is needed for a Normal verdict",
        )
    block = db.get(Block, analysis.block_id)
    return build_incident_ticket(analysis, block)
