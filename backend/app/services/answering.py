from collections.abc import Sequence

from app.services.llm import complete


ANSWER_SYSTEM_PROMPT = """You answer questions about a person's saved memories.
Use only the supplied memory evidence. Do not infer or invent facts that are not supported by that evidence. If retrieved memories contain multiple plausible but conflicting facts, do not silently choose one: briefly mention each relevant value or claim and identify its memory when useful. Do not claim one is newer, correct, or authoritative unless the evidence says so. If the evidence is insufficient, clearly say that you cannot find enough information in the saved memories. Keep the answer concise and useful. Do not generate citations or mention source numbers."""


def answer_from_memories(question: str, sources: Sequence[dict[str, str | float]]) -> str:
    """Produce a grounded answer from retrieved chunks only."""
    evidence = "\n\n".join(
        f"MEMORY: {source['filename']}\nCONTENT: {source['chunk_text']}"
        for source in sources
    )
    return complete(
        ANSWER_SYSTEM_PROMPT,
        f"QUESTION:\n{question}\n\nSAVED MEMORY EVIDENCE:\n{evidence}",
        max_tokens=220,
    )


def unique_memory_sources(sources: Sequence[dict[str, str | float]]) -> list[dict[str, str | float]]:
    """Keep the highest-ranked chunk for each source memory."""
    seen_memory_ids: set[str] = set()
    unique_sources = []
    for source in sources:
        memory_id = str(source["memory_id"])
        if memory_id not in seen_memory_ids:
            seen_memory_ids.add(memory_id)
            unique_sources.append(source)
    return unique_sources
