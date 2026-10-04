from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis, Block, EvaluationRun
from app.schemas import Stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=Stats)
def get_stats(db: Session = Depends(get_db)):
    total_blocks = db.execute(select(func.count()).select_from(Block)).scalar_one()
    anomaly_count = db.execute(
        select(func.count()).select_from(Block).where(Block.true_label == "Anomaly")
    ).scalar_one()
    normal_count = total_blocks - anomaly_count
    flagged_by_model = db.execute(
        select(func.count()).select_from(Block).where(Block.predicted_label == "Anomaly")
    ).scalar_one()
    total_analyses = db.execute(select(func.count()).select_from(Analysis)).scalar_one()
    # "Unreviewed" means no explicit human review yet — deliberately not
    # "no AI analysis exists" (that conflates the AI running with a human
    # having looked at it; Analyze and Live Simulation both leave this alone).
    flagged_unreviewed = db.execute(
        select(func.count())
        .select_from(Block)
        .where(Block.predicted_label == "Anomaly")
        .where(Block.reviewed_at.is_(None))
    ).scalar_one()

    latest_evaluation = db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.status == "completed")
        .order_by(EvaluationRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    return Stats(
        total_blocks=total_blocks,
        anomaly_count=anomaly_count,
        normal_count=normal_count,
        flagged_by_model=flagged_by_model,
        flagged_unreviewed=flagged_unreviewed,
        total_analyses=total_analyses,
        latest_evaluation=latest_evaluation,
    )
