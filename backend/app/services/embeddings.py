import os
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from huggingface_hub import InferenceClient


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


class EmbeddingConfigurationError(RuntimeError):
    """Raised when hosted embedding inference has not been configured."""


class EmbeddingServiceError(RuntimeError):
    """Raised when hosted embedding inference does not return usable vectors."""


def _embedding_client() -> InferenceClient:
    """Create a backend-only client for Hugging Face feature extraction."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    token = os.getenv("HF_TOKEN")
    if not token:
        raise EmbeddingConfigurationError(
            "Hosted embeddings are not configured. Set HF_TOKEN in the backend environment."
        )

    model = os.getenv("HF_EMBEDDING_MODEL") or DEFAULT_MODEL_NAME
    return InferenceClient(model=model, provider="hf-inference", token=token, timeout=60)


def embedding_dimension() -> int:
    """Return the fixed dimension expected from all-MiniLM-L6-v2."""
    return EMBEDDING_DIMENSION


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """Return remotely generated, L2-normalized float32 vectors for FAISS.

    FAISS uses inner product, so normalizing once here preserves the existing
    cosine-similarity behavior without requiring PyTorch in the web process.
    """
    values = list(texts)
    if not values:
        return np.empty((0, embedding_dimension()), dtype="float32")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise EmbeddingServiceError("Hosted embeddings require non-empty text input.")

    try:
        response = _embedding_client().feature_extraction(values)
    except EmbeddingConfigurationError:
        raise
    except Exception as error:
        raise EmbeddingServiceError("The Hugging Face embedding request failed.") from error

    try:
        vectors = np.asarray(response, dtype="float32")
    except (TypeError, ValueError) as error:
        raise EmbeddingServiceError("Hugging Face returned malformed embedding data.") from error

    if vectors.ndim == 1 and len(values) == 1:
        vectors = vectors.reshape(1, -1)
    if vectors.ndim != 2 or vectors.shape[0] != len(values) or vectors.shape[1] != EMBEDDING_DIMENSION:
        shape = tuple(vectors.shape)
        raise EmbeddingServiceError(
            f"Hugging Face returned embeddings with shape {shape}; expected ({len(values)}, {EMBEDDING_DIMENSION})."
        )
    if not np.isfinite(vectors).all():
        raise EmbeddingServiceError("Hugging Face returned invalid embedding values.")

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise EmbeddingServiceError("Hugging Face returned an empty embedding vector.")
    return np.ascontiguousarray(vectors / norms, dtype="float32")
