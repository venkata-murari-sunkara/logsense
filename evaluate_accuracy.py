"""
Step 5: Accuracy Evaluation
Runs both the grounded (RAG) and ungrounded explanation generators over
a sample of real, labeled blocks, then checks with simple keyword
matching whether each explanation's conclusion (problem vs normal)
matches the true label. This directly tests the core research
question: does grounding improve accuracy?
"""
import pandas as pd
import time

from generate_explanation import generate_explanation, generate_explanation_ungrounded

FEATURES_PATH = "HDFS_v1/preprocessed/Event_occurrence_matrix.csv"
LABELS_PATH = "HDFS_v1/preprocessed/anomaly_label.csv"

SAMPLE_SIZE_PER_CLASS = 10  # 10 anomalies + 10 normal = 20 total, keep small for the demo

ANOMALY_WORDS = [
    "anomaly", "anomalous", "fail", "error", "issue", "problem",
    "unusual", "concern", "unexpected", "corrupt", "abnormal",
]
NORMAL_WORDS = [
    "normal", "routine", "expected", "no issue", "no problem",
    "successful", "healthy", "nothing wrong", "not a problem",
]


def classify_verdict(explanation_text: str) -> str:
    """Simple keyword check: does the explanation conclude 'Anomaly' or 'Normal'?"""
    text = explanation_text.lower()
    anomaly_hits = sum(1 for w in ANOMALY_WORDS if w in text)
    normal_hits = sum(1 for w in NORMAL_WORDS if w in text)
    return "Anomaly" if anomaly_hits > normal_hits else "Normal"


def main():
    print("Loading data...")
    features = pd.read_csv(FEATURES_PATH)
    labels = pd.read_csv(LABELS_PATH)
    data = features.merge(labels, on="BlockId", suffixes=("", "_true"))
    event_columns = [c for c in data.columns if c.startswith("E")]

    anomalies = data[data["Label_true"] == "Anomaly"].sample(
        n=SAMPLE_SIZE_PER_CLASS, random_state=7
    )
    normals = data[data["Label_true"] == "Normal"].sample(
        n=SAMPLE_SIZE_PER_CLASS, random_state=7
    )
    sample = pd.concat([anomalies, normals]).sample(frac=1, random_state=7)  # shuffle

    results = []
    for i, (_, row) in enumerate(sample.iterrows(), start=1):
        event_counts = {col: int(row[col]) for col in event_columns}
        true_label = row["Label_true"]

        print(f"[{i}/{len(sample)}] Block {row['BlockId']} (true: {true_label})...")

        grounded_text = generate_explanation(event_counts)
        time.sleep(0.5)  # small pause to be gentle on the free API rate limit
        ungrounded_text = generate_explanation_ungrounded(event_counts)
        time.sleep(0.5)

        grounded_verdict = classify_verdict(grounded_text)
        ungrounded_verdict = classify_verdict(ungrounded_text)

        results.append({
            "block_id": row["BlockId"],
            "true_label": true_label,
            "grounded_verdict": grounded_verdict,
            "grounded_correct": grounded_verdict == true_label,
            "ungrounded_verdict": ungrounded_verdict,
            "ungrounded_correct": ungrounded_verdict == true_label,
        })

    results_df = pd.DataFrame(results)
    results_df.to_csv("evaluation_results.csv", index=False)

    grounded_accuracy = results_df["grounded_correct"].mean()
    ungrounded_accuracy = results_df["ungrounded_correct"].mean()

    print("\n=== Accuracy Comparison ===")
    print(f"Grounded (RAG) accuracy:   {grounded_accuracy:.0%}")
    print(f"Ungrounded accuracy:       {ungrounded_accuracy:.0%}")
    print(f"\nFull results saved to evaluation_results.csv")


if __name__ == "__main__":
    main()