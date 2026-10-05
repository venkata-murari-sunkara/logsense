from sqlalchemy.orm import Session

from app.models import Analysis, Block
from app.services import detector, explanation
from app.services.retrieval import get_similar_incidents


def analyze_block(
    db: Session,
    block: Block,
    include_ungrounded: bool = True,
    top_k: int = 3,
    source: str = "manual",
) -> Analysis:
    predicted_label, confidence = detector.predict(block.event_counts)

    evidence = get_similar_incidents(
        db, block.event_counts, top_k=top_k, exclude_block_id=block.block_id
    )
    # Nothing's been written yet — end the read transaction here so the
    # connection isn't held idle-in-transaction through the Groq calls
    # below (each throttled to a 3s+ minimum gap, more under retries).
    # Neon kills connections that sit idle-in-transaction too long; this
    # is what took down a concurrent evaluation run partway through.
    db.commit()

    grounded_text = explanation.generate_explanation(block.event_counts, evidence)
    ungrounded_text = (
        explanation.generate_explanation_ungrounded(block.event_counts)
        if include_ungrounded
        else None
    )
    # A "Normal" verdict has nothing to remediate — only spend a call on
    # concrete next steps when the block is actually flagged as a problem.
    recommendation = (
        explanation.generate_recommendation(block.event_counts, evidence, grounded_text)
        if predicted_label == "Anomaly"
        else None
    )

    analysis = Analysis(
        block_id=block.block_id,
        predicted_label=predicted_label,
        confidence=confidence,
        source=source,
        grounded_explanation=grounded_text,
        ungrounded_explanation=ungrounded_text,
        recommendation=recommendation,
        evidence=evidence,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis
