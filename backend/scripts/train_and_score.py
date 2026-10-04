"""
Trains the anomaly classifier on the full block set stored in Postgres
(all 575K blocks, not a 2,000-block sample), then scores every block and
writes predicted_label / predicted_confidence back so the API and
frontend can show model verdicts without re-scoring on every request.
"""
import _bootstrap  # noqa: F401
import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sqlalchemy import text

from app.config import REPO_ROOT
from app.database import SessionLocal
from app.services.detector import EVENT_COLUMNS, MODEL_PATH


def load_blocks_df(db) -> pd.DataFrame:
    rows = db.execute(text("SELECT block_id, event_counts, true_label FROM blocks")).all()
    records = []
    for block_id, event_counts, true_label in rows:
        record = {col: int(event_counts.get(col, 0)) for col in EVENT_COLUMNS}
        record["block_id"] = block_id
        record["true_label"] = true_label
        records.append(record)
    return pd.DataFrame(records)


def main():
    db = SessionLocal()
    try:
        print("Loading blocks from Postgres...")
        data = load_blocks_df(db)
        X = data[EVENT_COLUMNS]
        y = (data["true_label"] == "Anomaly").astype(int)

        print(f"Total blocks: {len(data)}")
        print(f"Anomalies: {y.sum()} ({y.mean()*100:.2f}%)")
        print(f"Normal: {(y == 0).sum()}\n")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        model = LogisticRegression(max_iter=1000, class_weight="balanced")
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        print("=== Performance on held-out test data ===")
        print(classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"]))
        print("Confusion matrix (rows=actual, cols=predicted):")
        print(confusion_matrix(y_test, y_pred))

        joblib.dump(model, MODEL_PATH)
        print(f"\nSaved trained model to {MODEL_PATH}")

        print("\nScoring all blocks...")
        all_proba = model.predict_proba(X)[:, 1]
        updates = [
            {
                "bid": block_id,
                "label": "Anomaly" if proba >= 0.5 else "Normal",
                # Confidence in the predicted class, not always P(anomaly) —
                # a "Normal" verdict should show a high number, not P(anomaly)~0.
                "conf": float(max(proba, 1 - proba)),
            }
            for block_id, proba in zip(data["block_id"], all_proba)
        ]
        BATCH = 5000
        for i in range(0, len(updates), BATCH):
            db.execute(
                text(
                    "UPDATE blocks SET predicted_label = :label, "
                    "predicted_confidence = :conf WHERE block_id = :bid"
                ),
                updates[i : i + BATCH],
            )
            db.commit()
            print(f"  scored {min(i + BATCH, len(updates))}/{len(updates)}")

        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
