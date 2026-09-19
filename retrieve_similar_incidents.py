"""
Step 3b: Retrieval (LlamaIndex version)
Given a newly flagged block's event history, search the LlamaIndex /
Chroma knowledge base for the most similar past incidents. This is the
"evidence" that will later get handed to the AI for explanation.
"""
import chromadb

from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from event_descriptions import describe_block

CHROMA_DIR = "./chroma_store"
COLLECTION_NAME = "hdfs_incidents"

Settings.embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")
Settings.llm = None


def get_similar_incidents(event_counts: dict, top_k: int = 3):
    """
    event_counts: dict like {'E3': 2, 'E7': 1, ...} for the new flagged block
    top_k: how many similar past incidents to retrieve
    Returns a list of dicts: [{"description": ..., "label": ..., "block_id": ...}, ...]
    """
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # Reconnect to the already-built index (no re-embedding of old data)
    index = VectorStoreIndex.from_vector_store(vector_store)
    retriever = index.as_retriever(similarity_top_k=top_k)

    query_text = describe_block(event_counts)
    results = retriever.retrieve(query_text)

    matches = []
    for r in results:
        matches.append({
            "description": r.node.text,
            "label": r.node.metadata.get("label"),
            "block_id": r.node.metadata.get("block_id"),
            "score": round(r.score, 3) if r.score is not None else None,
        })
    return matches


if __name__ == "__main__":
    # Quick test: pretend we just flagged a new block with these event counts
    # (looks like a block that failed while being written, a plausible anomaly)
    test_event_counts = {"E5": 1, "E7": 2, "E14": 1}

    print("New flagged block description:")
    print(" ", describe_block(test_event_counts))
    print()

    print("Top similar past incidents found:")
    matches = get_similar_incidents(test_event_counts, top_k=3)
    for i, m in enumerate(matches, start=1):
        print(f"\n{i}. [{m['label']}] Block {m['block_id']} (similarity score: {m['score']})")
        print(f"   {m['description']}")