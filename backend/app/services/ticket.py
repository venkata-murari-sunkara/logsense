"""
Assembles an already-completed analysis (explanation + evidence +
recommendation) into a ready-to-file incident ticket. No LLM call — this is
a deterministic template over data we already generated, so it's free and
instant, and the wording of the underlying analysis stays the single source
of truth (the ticket never says anything the analysis didn't already say).
"""
from app.models import Analysis


def _severity_label(confidence: float) -> str:
    if confidence >= 0.99:
        return "Highest confidence"
    if confidence >= 0.9:
        return "High confidence"
    return "Moderate confidence"


def build_incident_ticket(analysis: Analysis) -> dict:
    if analysis.predicted_label != "Anomaly":
        raise ValueError("A ticket only makes sense for a confirmed Anomaly verdict")

    title = f"[LogSense] Confirmed anomaly — block {analysis.block_id}"
    severity = _severity_label(analysis.confidence)
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
Severity: {severity} ({analysis.confidence * 100:.1f}%)
Detected: {detected_at}
Block ID: {analysis.block_id}
Source: {analysis.source}
Generated automatically by LogSense AI — verify before taking action.
"""

    return {"title": title, "body": body}
