"""
Embeds every block's description (all 575K, not a 2,000-block sample) and
writes the vectors into Postgres via pgvector, then builds an HNSW index
for fast similarity search. Replaces the old ChromaDB knowledge base.
"""
import time

import _bootstrap  # noqa: F401
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.services.embeddings import embed_texts

FETCH_BATCH = 2000


def main():
    db = SessionLocal()
    start = time.time()
    try:
        total = db.execute(text("SELECT count(*) FROM blocks")).scalar_one()
        print(f"Embedding {total} blocks...")

        done = 0
        while True:
            rows = db.execute(
                text(
                    "SELECT block_id, description FROM blocks "
                    "WHERE embedding IS NULL ORDER BY block_id LIMIT :n"
                ),
                {"n": FETCH_BATCH},
            ).all()
            if not rows:
                break

            block_ids = [r.block_id for r in rows]
            descriptions = [r.description for r in rows]
            vectors = embed_texts(descriptions, show_progress=False)

            db.execute(
                text("UPDATE blocks SET embedding = :emb WHERE block_id = :bid"),
                [{"bid": bid, "emb": str(vec)} for bid, vec in zip(block_ids, vectors)],
            )
            db.commit()

            done += len(rows)
            elapsed = time.time() - start
            print(f"  {done}/{total}  ({elapsed:.0f}s elapsed)")

        print("Building HNSW index (vector_cosine_ops)...")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS blocks_embedding_hnsw_idx "
                    "ON blocks USING hnsw (embedding vector_cosine_ops)"
                )
            )
        print(f"Done in {time.time() - start:.0f}s.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
