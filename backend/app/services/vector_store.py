from collections.abc import Sequence

import faiss
import numpy as np

from app.database import DATA_DIRECTORY


INDEX_PATH = DATA_DIRECTORY / "memora.faiss"
_index: faiss.Index | None = None


def get_index(dimension: int) -> faiss.Index:
    """Load the persisted cosine-similarity FAISS index, or create an empty one."""
    global _index
    if _index is None:
        DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
        if INDEX_PATH.exists():
            _index = faiss.read_index(str(INDEX_PATH))
            if _index.d != dimension:
                raise RuntimeError("The existing FAISS index has an incompatible embedding dimension.")
        else:
            _index = faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))
    return _index


def indexed_ids(dimension: int) -> set[int]:
    index = get_index(dimension)
    if index.ntotal == 0:
        return set()
    return {int(vector_id) for vector_id in faiss.vector_to_array(index.id_map)}


def add_vectors(vectors: np.ndarray, vector_ids: Sequence[int], dimension: int) -> None:
    """Persist normalized vectors under stable SQLite-backed IDs."""
    if len(vector_ids) == 0:
        return
    index = get_index(dimension)
    index.add_with_ids(
        np.ascontiguousarray(vectors, dtype="float32"),
        np.asarray(vector_ids, dtype="int64"),
    )
    faiss.write_index(index, str(INDEX_PATH))


def rebuild_index(vectors: np.ndarray, vector_ids: Sequence[int], dimension: int) -> None:
    """Replace the persisted index atomically in-process using remaining SQLite chunks."""
    global _index
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    rebuilt_index = faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))
    if vector_ids:
        rebuilt_index.add_with_ids(
            np.ascontiguousarray(vectors, dtype="float32"),
            np.asarray(vector_ids, dtype="int64"),
        )
    faiss.write_index(rebuilt_index, str(INDEX_PATH))
    _index = rebuilt_index


def clear_index() -> None:
    """Remove the persisted index when no searchable chunks remain."""
    global _index
    INDEX_PATH.unlink(missing_ok=True)
    _index = None


def search_vectors(query_vector: np.ndarray, limit: int, dimension: int) -> list[tuple[int, float]]:
    """Return (vector ID, cosine similarity) pairs, highest score first."""
    index = get_index(dimension)
    if index.ntotal == 0:
        return []
    scores, ids = index.search(np.ascontiguousarray(query_vector, dtype="float32"), min(limit, index.ntotal))
    return [(int(vector_id), float(score)) for vector_id, score in zip(ids[0], scores[0]) if vector_id >= 0]
