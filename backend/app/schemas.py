import datetime

from pydantic import BaseModel, ConfigDict


class BlockSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    block_id: str
    true_label: str
    predicted_label: str | None
    predicted_confidence: float | None
    has_analysis: bool = False
    reviewed_at: datetime.datetime | None = None


class BlockDetail(BlockSummary):
    event_counts: dict[str, int]
    description: str


class EvidenceItem(BaseModel):
    block_id: str
    label: str
    description: str
    score: float | None


class IncidentTicket(BaseModel):
    title: str
    body: str


class AnalysisResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    block_id: str
    predicted_label: str
    confidence: float
    source: str = "manual"
    true_label: str
    grounded_explanation: str
    ungrounded_explanation: str | None
    recommendation: str | None = None
    evidence: list[EvidenceItem]
    created_at: datetime.datetime
    reviewed_at: datetime.datetime | None = None


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    block_id: str
    predicted_label: str
    confidence: float
    source: str = "manual"
    created_at: datetime.datetime
    reviewed_at: datetime.datetime | None = None


class EvaluationRunCreate(BaseModel):
    sample_size: int = 50


class EvaluationRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sample_size: int
    status: str
    grounded_accuracy: float | None
    ungrounded_accuracy: float | None
    failed_count: int = 0
    created_at: datetime.datetime
    completed_at: datetime.datetime | None


class EvaluationResultItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    block_id: str
    true_label: str
    grounded_verdict: str
    grounded_correct: bool
    ungrounded_verdict: str
    ungrounded_correct: bool


class EvaluationRunDetail(EvaluationRunSummary):
    results: list[EvaluationResultItem]


class SimulationStart(BaseModel):
    interval_seconds: float = 20.0


class SimulationStatus(BaseModel):
    running: bool
    interval_seconds: float
    started_at: datetime.datetime | None
    ticks: int
    errors: int
    last_block_id: str | None
    last_verdict: str | None
    last_ran_at: datetime.datetime | None
    last_error: str | None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str


class Stats(BaseModel):
    total_blocks: int
    anomaly_count: int
    normal_count: int
    flagged_by_model: int
    flagged_unreviewed: int
    total_analyses: int
    latest_evaluation: EvaluationRunSummary | None
