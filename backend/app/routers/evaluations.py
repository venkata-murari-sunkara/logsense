from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import EvaluationRun
from app.schemas import EvaluationRunCreate, EvaluationRunDetail, EvaluationRunSummary
from app.services.evaluation import run_evaluation

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationRunSummary, status_code=201)
def create_evaluation(
    payload: EvaluationRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    run = EvaluationRun(sample_size=payload.sample_size, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(run_evaluation, run.id, payload.sample_size)
    return run


@router.get("", response_model=list[EvaluationRunSummary])
def list_evaluations(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/{run_id}", response_model=EvaluationRunDetail)
def get_evaluation(run_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.results))
        .where(EvaluationRun.id == run_id)
    )
    run = db.execute(stmt).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run
