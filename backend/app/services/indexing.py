import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Memory
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts, embedding_dimension
from app.services.vector_store import add_vectors, clear_index, indexed_ids, rebuild_index


logger = logging.getLogger(__name__)


def index_memory(db: Session, memory: Memory) -> None:
    """Create missing chunks and vectorize any chunks not already in FAISS.

    Chunk uniqueness plus stable chunk IDs make this safe to call repeatedly.
    """
    if memory.processing_status != "ready" or not memory.extracted_text:
        return

    chunks = db.scalars(
        select(Chunk).where(Chunk.memory_id == memory.id).order_by(Chunk.chunk_index)
    ).all()
    if not chunks:
        chunks = [
            Chunk(memory_id=memory.id, chunk_index=index, text=chunk)
            for index, chunk in enumerate(chunk_text(memory.extracted_text))
        ]
        if not chunks:
            return
        db.add_all(chunks)
        db.commit()
        for chunk in chunks:
            db.refresh(chunk)

    for chunk in chunks:
        if chunk.vector_index_id is None:
            chunk.vector_index_id = chunk.id
    db.commit()

    dimension = embedding_dimension()
    present_ids = indexed_ids(dimension)
    missing_chunks = [chunk for chunk in chunks if chunk.vector_index_id not in present_ids]
    if not missing_chunks:
        return

    vectors = embed_texts([chunk.text for chunk in missing_chunks])
    add_vectors(vectors, [chunk.vector_index_id for chunk in missing_chunks], dimension)


def index_existing_memories(db: Session) -> None:
    """Index prior Stage 3 records without importing untracked upload files."""
    memories = db.scalars(
        select(Memory).where(Memory.processing_status == "ready", Memory.extracted_text.is_not(None))
    ).all()
    for memory in memories:
        try:
            index_memory(db, memory)
        except Exception:
            # Retrieval can retry at a later startup without blocking the core API.
            logger.exception("Could not index memory %s", memory.id)

    reconcile_vector_index(db)


def reconcile_vector_index(db: Session) -> None:
    """Make FAISS match the persisted searchable Chunk records exactly.

    SQLite is the authoritative source for chunk metadata.  This repairs an
    index left incomplete or stale by a prior interrupted run without adding
    duplicate vectors.  It is safe to call again after every restart.
    """
    chunks = db.scalars(
        select(Chunk)
        .join(Memory, Chunk.memory_id == Memory.id)
        .where(Memory.processing_status == "ready", Memory.extracted_text.is_not(None))
        .order_by(Chunk.id)
    ).all()

    mapping_changed = False
    for chunk in chunks:
        if chunk.vector_index_id != chunk.id:
            chunk.vector_index_id = chunk.id
            mapping_changed = True
    if mapping_changed:
        db.commit()

    dimension = embedding_dimension()
    expected_ids = {chunk.vector_index_id for chunk in chunks}
    try:
        present_ids = indexed_ids(dimension)
    except Exception:
        logger.warning("The persisted FAISS index could not be read; rebuilding it from SQLite chunks.")
        present_ids = set()

    if present_ids == expected_ids:
        return

    logger.info(
        "Reconciling FAISS index: %s persisted chunk IDs, %s indexed vector IDs.",
        len(expected_ids),
        len(present_ids),
    )
    rebuild_vector_index(chunks)


def rebuild_vector_index(chunks: list[Chunk]) -> None:
    """Recreate FAISS from the supplied remaining SQLite chunks."""
    if not chunks:
        clear_index()
        return

    dimension = embedding_dimension()
    vectors = embed_texts([chunk.text for chunk in chunks])
    rebuild_index(vectors, [chunk.vector_index_id or chunk.id for chunk in chunks], dimension)
