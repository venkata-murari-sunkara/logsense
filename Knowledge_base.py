"""
Step 3a: Build the Evidence Knowledge Base (LlamaIndex version)
Takes a sample of past blocks, turns each into a plain-English
description, and indexes them with LlamaIndex (embeddings +
Chroma vector store under the hood) so we can later retrieve
"similar past incidents" for a newly flagged block.
"""
import pandas as pd
import chromadb

from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from event_descriptions import describe_block

FEATURES_PATH = "HDFS_v1/preprocessed/Event_occurrence_matrix.csv"
LABELS_PATH = "HDFS_v1/preprocessed/anomaly_label.csv"
CHROMA_DIR = "./chroma_store"
COLLECTION_NAME = "hdfs_incidents"

# How many past incidents to store in the knowledge base for the MVP demo.
SAMPLE_SIZE = 2000

# Use a small, fast embedding model, via LlamaIndex's HuggingFace
# embedding wrapper. Setting it globally means every LlamaIndex call
# (here and in the retrieval script) uses this same model.
Settings.embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")
Settings.llm = None  # we don't need LlamaIndex's own LLM here, Groq is separate

print("Loading data...")
features = pd.read_csv(FEATURES_PATH)
labels = pd.read_csv(LABELS_PATH)
data = features.merge(labels, on="BlockId", suffixes=("", "_true"))

event_columns = [c for c in data.columns if c.startswith("E")]

# Balanced sample: some normal, some anomalies, so there are real
# problem examples in the knowledge base to retrieve later.
anomalies = data[data["Label_true"] == "Anomaly"]
normals = data[data["Label_true"] == "Normal"]

n_anom = min(len(anomalies), SAMPLE_SIZE // 4)
n_norm = min(len(normals), SAMPLE_SIZE - n_anom)
sample = pd.concat([
    anomalies.sample(n=n_anom, random_state=42),
    normals.sample(n=n_norm, random_state=42),
])
print(f"Building knowledge base from {len(sample)} past incidents "
      f"({n_anom} anomalies, {n_norm} normal).")

# Turn each block's event counts into a LlamaIndex Document, with the
# plain-English description as the text and block id / label as metadata
# (metadata travels with the chunk and comes back on retrieval).
print("Building documents...")
documents = []
for _, row in sample.iterrows():
    event_counts = {col: int(row[col]) for col in event_columns}
    description = describe_block(event_counts)
    documents.append(
        Document(
            text=description,
            doc_id=row["BlockId"],
            metadata={"block_id": row["BlockId"], "label": row["Label_true"]},
        )
    )

# Set up Chroma as the vector store LlamaIndex will write embeddings into
print("Setting up Chroma vector store...")
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)

# Clear any previous run so re-running this script doesn't duplicate entries
existing = chroma_collection.get()
if existing["ids"]:
    chroma_collection.delete(ids=existing["ids"])

vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# This is the one call doing the heavy lifting: embeds every document
# and writes it into the Chroma vector store.
print("Embedding and indexing (this may take a minute)...")
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
    show_progress=True,
)

print(f"\nDone. Knowledge base saved to {CHROMA_DIR}")
print(f"Contains {chroma_collection.count()} past incidents, ready for retrieval.")