"""
Assembles an already-completed analysis (explanation + evidence +
recommendation) into a ready-to-file incident ticket. No LLM call — this is
a deterministic template over data we already generated, so it's free and
instant, and the wording of the underlying analysis stays the single source
of truth (the ticket never says anything the analysis didn't already say).
"""
from app.models import Analysis, Block

# Confidence (how sure the AI is in its verdict) and severity (how serious
# the underlying problem looks) are different questions — a block can be
# flagged with near-certainty yet involve only a couple of odd events, or
# vice versa. Confidence comes straight from the model; severity here uses
# a simple, independent proxy instead: total event volume on the block,
# thresholded against this dataset's actual distribution among flagged
# blocks (checked directly: p25=2, median=4, p75=25, p90=27 events).
def _severity_from_event_volume(event_counts: dict) -> str:
    total_events = sum(event_counts.values())
    if total_events >= 20:
        return "High"
    if total_events >= 6:
        return "Medium"
    return "Low"


def build_incident_ticket(analysis: Analysis, block: Block) -> dict:
    if analysis.predicted_label != "Anomaly":
        raise ValueError("A ticket only makes sense for a confirmed Anomaly verdict")

    title = f"[LogSense] Likely anomaly — block {analysis.block_id}"
    severity = _severity_from_event_volume(block.event_counts)
    detected_at = analysis.created_at.strftime("%Y-%m-%d %H:%M %Z").strip()

    evidence_lines = "\n".join(
        f"- [{e['label']}] {e['block_id']}: {e['description']}" for e in analysis.evidence
    ) or "- No comparable past incidents were retrieved."

    body = f"""## Summary
{analysis.grounded_explanation}

## Supporting evidence (similar past incidents)
{evidence_lines}

## Recommended fix
{analysis.recommendation or "No remediation steps were generated."}

---
Detected: {detected_at}
Block ID: {analysis.block_id}
Source: {analysis.source}
Generated automatically by LogSense AI — verify before taking action.
"""

    return {
        "title": title,
        "body": body,
        "confidence": analysis.confidence,
        "severity": severity,
    }
