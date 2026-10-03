from collections.abc import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Load the local embedding model once per API process."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embedding_dimension() -> int:
    return int(get_model().get_sentence_embedding_dimension())


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """Return L2-normalized vectors so FAISS inner product equals cosine similarity."""
    if not texts:
        return np.empty((0, embedding_dimension()), dtype="float32")
    vectors = get_model().encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
    return np.ascontiguousarray(vectors, dtype="float32")
