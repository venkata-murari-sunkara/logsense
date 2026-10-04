import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.event_descriptions import EVENT_DESCRIPTIONS

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/timeline")
def get_timeline(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    rows = db.execute(
        text(
            """
            SELECT date_trunc('day', created_at) AS day, predicted_label, count(*) AS n
            FROM analyses
            WHERE created_at >= :since
            GROUP BY 1, 2
            ORDER BY 1
            """
        ),
        {"since": since},
    ).all()

    by_day: dict[str, dict] = {}
    for day, label, n in rows:
        key = day.date().isoformat()
        entry = by_day.setdefault(key, {"date": key, "anomaly_count": 0, "normal_count": 0})
        if label == "Anomaly":
            entry["anomaly_count"] = n
        else:
            entry["normal_count"] = n

    return {"days": sorted(by_day.values(), key=lambda d: d["date"])}


@router.get("/event-patterns")
def get_event_patterns(limit: int = Query(8, ge=1, le=29), db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT key AS event_code,
                   avg(CASE WHEN true_label = 'Anomaly' THEN (value::int > 0)::int::float END) AS anomaly_rate,
                   avg(CASE WHEN true_label = 'Normal' THEN (value::int > 0)::int::float END) AS normal_rate
            FROM blocks, jsonb_each_text(event_counts)
            GROUP BY key
            ORDER BY (
                avg(CASE WHEN true_label = 'Anomaly' THEN (value::int > 0)::int::float END)
                - avg(CASE WHEN true_label = 'Normal' THEN (value::int > 0)::int::float END)
            ) DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).all()

    return {
        "patterns": [
            {
                "event_code": r.event_code,
                "description": EVENT_DESCRIPTIONS.get(r.event_code, r.event_code),
                "anomaly_rate": round(r.anomaly_rate or 0.0, 4),
                "normal_rate": round(r.normal_rate or 0.0, 4),
            }
            for r in rows
        ]
    }
