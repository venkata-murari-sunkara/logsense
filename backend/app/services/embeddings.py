import threading

from sentence_transformers import SentenceTransformer

from app.config import get_settings

# sentence-transformers / torch aren't safe to lazily initialize from
# multiple threads at once (a bare @lru_cache lets concurrent first-callers
# race into the constructor simultaneously) — this crashed the process
# outright under concurrent evaluation load. Double-checked locking ensures
# exactly one thread ever constructs the model.
_model_lock = threading.Lock()
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                settings = get_settings()
                _model = SentenceTransformer(settings.embedding_model_name)
    return _model


# Construction wasn't the only unsafe part: calling .encode() on the same
# model instance from multiple threads at once crashed the process outright
# (likely conflicting native BLAS/OpenMP thread pools inside torch), even
# with construction already fixed above. Serialize inference calls too —
# each one is a single short description, so this costs latency, not
# throughput, and lets callers still run DB/Groq work concurrently around it.
_inference_lock = threading.Lock()


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    with _inference_lock:
        return model.encode(text, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str], batch_size: int = 256, show_progress: bool = False) -> list[list[float]]:
    model = get_embedding_model()
    with _inference_lock:
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
        )
    return vectors.tolist()
