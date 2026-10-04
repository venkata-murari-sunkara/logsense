import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

EMBEDDING_DIM = 384


class Block(Base):
    __tablename__ = "blocks"

    block_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_counts: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    true_label: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    predicted_label: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    predicted_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Set ONLY by an explicit human "Review" action (see /blocks/{id}/review) —
    # deliberately distinct from whether the AI has ever analyzed this block
    # (that's `has_analysis`, derived from the analyses table). Running the
    # AI pipeline, via Analyze or Live Simulation, must never touch this.
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="block")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_id: Mapped[str] = mapped_column(ForeignKey("blocks.block_id"), index=True)

    predicted_label: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    grounded_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    ungrounded_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    block: Mapped["Block"] = relationship(back_populates="analyses")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    grounded_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    ungrounded_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    results: Mapped[list["EvaluationResult"]] = relationship(back_populates="run")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_run_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_runs.id"), index=True
    )
    block_id: Mapped[str] = mapped_column(ForeignKey("blocks.block_id"))

    true_label: Mapped[str] = mapped_column(String(10), nullable=False)
    grounded_verdict: Mapped[str] = mapped_column(String(10), nullable=False)
    grounded_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ungrounded_verdict: Mapped[str] = mapped_column(String(10), nullable=False)
    ungrounded_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    run: Mapped["EvaluationRun"] = relationship(back_populates="results")
