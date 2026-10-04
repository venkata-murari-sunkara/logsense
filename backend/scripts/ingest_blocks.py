"""
Loads the full HDFS block dataset (event counts + ground-truth labels) from
CSV into the Postgres `blocks` table. Replaces the old CSV-per-request reads.
"""
import _bootstrap  # noqa: F401
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.config import REPO_ROOT
from app.database import SessionLocal
from app.models import Block
from app.services.event_descriptions import describe_block

FEATURES_PATH = REPO_ROOT / "data" / "Event_occurrence_matrix.csv"
LABELS_PATH = REPO_ROOT / "data" / "anomaly_label.csv"
BATCH_SIZE = 5000


def main():
    print("Loading CSVs...")
    features = pd.read_csv(FEATURES_PATH)
    labels = pd.read_csv(LABELS_PATH)
    data = features.merge(labels, on="BlockId", suffixes=("", "_true"))
    event_columns = [c for c in data.columns if c.startswith("E")]
    print(f"{len(data)} blocks loaded ({len(event_columns)} event columns).")

    db = SessionLocal()
    try:
        print("Clearing existing blocks table...")
        db.execute(delete(Block))
        db.commit()

        print("Ingesting in batches...")
        rows = []
        for i, row in enumerate(data.itertuples(index=False), start=1):
            row_dict = row._asdict()
            event_counts = {col: int(row_dict[col]) for col in event_columns}
            rows.append(
                {
                    "block_id": row_dict["BlockId"],
                    "event_counts": event_counts,
                    "description": describe_block(event_counts),
                    "true_label": row_dict["Label_true"],
                }
            )
            if len(rows) >= BATCH_SIZE:
                db.execute(insert(Block), rows)
                db.commit()
                print(f"  {i}/{len(data)}")
                rows = []
        if rows:
            db.execute(insert(Block), rows)
            db.commit()
            print(f"  {len(data)}/{len(data)}")

        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
