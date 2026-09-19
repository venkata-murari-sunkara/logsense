"""
Step 2: Anomaly Detection
Trains a simple classifier to predict whether a block is Normal or an
Anomaly, using the event-count features we already have (E1...E29 =
how many times each log template happened for that block).
"""
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
import joblib

FEATURES_PATH = "HDFS_v1/preprocessed/Event_occurrence_matrix.csv"
LABELS_PATH = "HDFS_v1/preprocessed/anomaly_label.csv"

# Load features (event counts per block) and real labels
features = pd.read_csv(FEATURES_PATH)
labels = pd.read_csv(LABELS_PATH)

# Merge them together on BlockId so each row has both counts and the true label
data = features.merge(labels, on="BlockId", suffixes=("", "_true"))

# The event count columns are our input (X); the real label is what we predict (y)
event_columns = [c for c in data.columns if c.startswith("E")]
X = data[event_columns]
y = (data["Label_true"] == "Anomaly").astype(int)  # 1 = Anomaly, 0 = Normal

print(f"Total blocks: {len(data)}")
print(f"Anomalies: {y.sum()} ({y.mean()*100:.2f}%)")
print(f"Normal: {(y == 0).sum()}\n")

# Split into training data (to learn from) and test data (to check performance on)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Train a simple classifier. class_weight="balanced" helps since anomalies
# are rare (~3%) compared to normal blocks (~97%)
model = LogisticRegression(max_iter=1000, class_weight="balanced")
model.fit(X_train, y_train)

# Check how well it did on data it hasn't seen before
y_pred = model.predict(X_test)

print("=== Performance on held-out test data ===")
print(classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"]))
print("Confusion matrix (rows=actual, cols=predicted):")
print(confusion_matrix(y_test, y_pred))

# Save the trained model so we can reuse it later without retraining
joblib.dump(model, "anomaly_model.joblib")
print("\nSaved trained model to anomaly_model.joblib")