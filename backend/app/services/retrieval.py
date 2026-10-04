from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Block
from app.services.embeddings import embed_text
from app.services.event_descriptions import describe_block


def _fetch_ann(
    db: Session,
    distance,
    label: str,
    limit: int,
    exclude_block_id: str | None,
) -> list[tuple[Block, float]]:
    """Fast path: let the HNSW index pick nearest neighbors, then filter by
    label. pgvector's ANN index orders-then-filters, so if `label` is rare
    within the index's internal candidate window, this can come back with
    fewer than `limit` rows (or zero) even though matches exist elsewhere
    in the ranking — callers must handle that by falling back to _fetch_exact.
    """
    stmt = (
        select(Block, distance.label("distance"))
        .where(Block.embedding.is_not(None))
        .where(Block.true_label == label)
        .order_by(distance)
        .limit(limit + (1 if exclude_block_id else 0))
    )
    rows = db.execute(stmt).all()
    out = []
    for block, dist in rows:
        if exclude_block_id and block.block_id == exclude_block_id:
            continue
        out.append((block, dist))
        if len(out) >= limit:
            break
    return out


def _fetch_exact(
    db: Session,
    distance,
    label: str,
    limit: int,
    exclude_block_id: str | None,
) -> list[tuple[Block, float]]:
    """Exact fallback: materialize just the rows for `label` (using the
    true_label index) *before* computing/sorting distance, so the HNSW
    index is never consulted and no matches can be silently dropped. A
    plain (non-materialized) CTE gets inlined by the planner right back
    into the same order-then-filter ANN plan, so the MATERIALIZED hint is
    required, not optional.
    """
    base = select(Block.block_id, Block.embedding).where(Block.true_label == label)
    if exclude_block_id:
        base = base.where(Block.block_id != exclude_block_id)
    candidates = base.where(Block.embedding.is_not(None)).cte("candidates").prefix_with("MATERIALIZED")

    dist_expr = candidates.c.embedding.cosine_distance(distance.right)
    stmt = select(candidates.c.block_id, dist_expr.label("distance")).order_by(dist_expr).limit(limit)
    rows = db.execute(stmt).all()

    if not rows:
        return []
    blocks_by_id = {
        b.block_id: b
        for b in db.execute(
            select(Block).where(Block.block_id.in_([r.block_id for r in rows]))
        ).scalars()
    }
    return [(blocks_by_id[r.block_id], r.distance) for r in rows]


def _fetch_nearest(
    db: Session,
    distance,
    label: str,
    limit: int,
    exclude_block_id: str | None,
) -> list[tuple[Block, float]]:
    rows = _fetch_ann(db, distance, label, limit, exclude_block_id)
    if len(rows) < limit:
        rows = _fetch_exact(db, distance, label, limit, exclude_block_id)
    return rows


def get_similar_incidents(
    db: Session,
    event_counts: dict,
    top_k: int = 3,
    exclude_block_id: str | None = None,
) -> list[dict]:
    """
    Given a block's event history, find similar past incidents using
    pgvector cosine distance over the description embeddings.

    The dataset is heavily imbalanced (~33 Normal blocks per Anomaly), so
    pure nearest-neighbor search over the whole population returns almost
    entirely Normal evidence even for a genuine anomaly — evaluation showed
    this measurably biased grounded explanations toward "Normal" (32%
    recall on real anomalies vs 87% for the ungrounded baseline). Instead,
    fetch the nearest Anomaly-labeled and nearest Normal-labeled incidents
    *separately* and merge them, guaranteeing both classes get a voice
    regardless of their relative density. This never inspects the query
    block's own true label — only which label each retrieved neighbor has —
    so it doesn't leak the answer, it just prevents the majority class from
    crowding out the minority one.
    """
    query_text = describe_block(event_counts)
    query_vector = embed_text(query_text)
    distance = Block.embedding.cosine_distance(query_vector)

    n_anomaly = (top_k + 1) // 2  # the rarer class gets the extra slot on odd top_k
    n_normal = top_k - n_anomaly

    anomaly_rows = _fetch_nearest(db, distance, "Anomaly", n_anomaly, exclude_block_id)
    normal_rows = _fetch_nearest(db, distance, "Normal", n_normal, exclude_block_id)

    combined = sorted(anomaly_rows + normal_rows, key=lambda pair: pair[1])

    return [
        {
            "block_id": block.block_id,
            "label": block.true_label,
            "description": block.description,
            "score": round(1 - float(dist), 4),
        }
        for block, dist in combined
    ]
