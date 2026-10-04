import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Memory
from app.services.embeddings import embed_texts, embedding_dimension
from app.services.vector_store import indexed_ids, search_vectors

MINIMUM_COSINE_SIMILARITY = 0.20
MAX_SCORE_GAP = 0.12
LEXICAL_STOP_WORDS = {
    "about", "anything", "could", "from", "have", "looking", "memory",
    "saved", "that", "this", "were", "what", "where", "which", "with",
    "would", "your",
}


def lexical_fallback(db: Session, question: str, query_vector, limit: int, session_id: str) -> list[dict[str, str | float]]:
    """Recover exact identifiers that a sentence embedding may not represent well.

    This is intentionally used only when semantic retrieval found no usable
    evidence. It remains memory-content based and returns a real cosine score
    for each selected chunk rather than treating a lexical hit as an answer.
    """
    terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z0-9]{3,}", question)
        if term.lower() not in LEXICAL_STOP_WORDS
    }
    if not terms:
        return []

    rows = db.execute(
        select(Chunk, Memory)
        .join(Memory, Chunk.memory_id == Memory.id)
        .where(
            Memory.processing_status == "ready",
            Memory.extracted_text.is_not(None),
            Memory.session_id == session_id,
        )
    ).all()
    matching_rows = []
    for chunk, memory in rows:
        chunk_terms = set(re.findall(r"[A-Za-z0-9]{3,}", chunk.text.lower()))
        overlap = len(terms & chunk_terms)
        if overlap:
            matching_rows.append((overlap, chunk, memory))

    if not matching_rows:
        return []

    matching_rows.sort(key=lambda match: (-match[0], match[1].id))
    selected_rows = matching_rows[:limit]
    vectors = embed_texts([chunk.text for _, chunk, _ in selected_rows])
    results = []
    for vector, (_, chunk, memory) in zip(vectors, selected_rows):
        results.append(
            {
                "memory_id": memory.id,
                "filename": memory.filename,
                "file_type": memory.file_type,
                "chunk_text": chunk.text,
                "score": float(query_vector[0].dot(vector)),
            }
        )
    return results


def semantic_search(db: Session, question: str, session_id: str, limit: int = 5) -> list[dict[str, str | float]]:
    """Retrieve the most semantically similar persisted chunks for a question."""
    if db.scalar(
        select(Chunk.id)
        .join(Memory, Chunk.memory_id == Memory.id)
        .where(Memory.session_id == session_id)
        .limit(1)
    ) is None:
        return []

    query_vector = embed_texts([question])
    # Retrieve a wider candidate set before applying the evidence floor. A fixed
    # absolute cutoff alone can exclude a valid memory for short acronyms or
    # differently worded questions even when it is close to the best match.
    dimension = embedding_dimension()
    # The index is shared across anonymous sessions. Retrieve the available
    # candidates, then scope them through SQLite before calculating relevance.
    # This prevents another session's high-scoring vector from excluding a
    # lower-scoring but valid chunk owned by the requesting session.
    matches = search_vectors(query_vector, len(indexed_ids(dimension)), dimension)
    if not matches:
        return []

    vector_ids = [vector_id for vector_id, _ in matches]
    rows = db.execute(
        select(Chunk, Memory)
        .join(Memory, Chunk.memory_id == Memory.id)
        .where(Chunk.vector_index_id.in_(vector_ids), Memory.session_id == session_id)
    ).all()
    records_by_vector_id = {chunk.vector_index_id: (chunk, memory) for chunk, memory in rows}

    session_matches = [
        (vector_id, score, records_by_vector_id[vector_id])
        for vector_id, score in matches
        if vector_id in records_by_vector_id
    ]
    if not session_matches:
        return lexical_fallback(db, question, query_vector, limit, session_id)

    highest_score = session_matches[0][1]
    evidence_floor = max(MINIMUM_COSINE_SIMILARITY, highest_score - MAX_SCORE_GAP)
    results = []
    for vector_id, score, record in session_matches:
        # Keep candidates close to the strongest result, while retaining a modest
        # absolute floor for genuinely unrelated memories. Scores remain cosine
        # similarity rather than confidence.
        if score < evidence_floor:
            break
        chunk, memory = record
        results.append(
            {
                "memory_id": memory.id,
                "filename": memory.filename,
                "file_type": memory.file_type,
                "chunk_text": chunk.text,
                # Normalized vectors make this cosine similarity, not confidence.
                "score": score,
            }
        )
        if len(results) == limit:
            break
    return results or lexical_fallback(db, question, query_vector, limit, session_id)
