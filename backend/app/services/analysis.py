import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Memory
from app.services.llm import LLMConfigurationError, complete


logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You analyze one personal memory. Use only the supplied memory text.
Return exactly two labeled lines:
SUMMARY: a short factual explanation of what the memory contains.
LIKELY_CONTEXT: a cautious explanation of why someone may have saved it. Use uncertainty language such as may, might, or appears. Do not claim to know the person's actual intent or add personal history."""


def analyze_memory(memory: Memory) -> tuple[str, str]:
    """Create persistent factual and cautious AI fields for extracted text."""
    if not memory.extracted_text:
        raise ValueError("A memory without extracted text cannot be analyzed.")

    response = complete(
        ANALYSIS_SYSTEM_PROMPT,
        f"MEMORY TEXT:\n{memory.extracted_text}",
        max_tokens=220,
    )
    lines = {line.partition(":")[0].strip().upper(): line.partition(":")[2].strip() for line in response.splitlines() if ":" in line}
    summary = lines.get("SUMMARY")
    context = lines.get("LIKELY_CONTEXT")
    if not summary or not context:
        raise ValueError("The hosted LLM did not return the requested memory analysis format.")
    return summary, context


def analyze_existing_memories(db: Session) -> None:
    """Idempotently analyze ready extracted memories missing either AI field."""
    memories = db.scalars(
        select(Memory).where(
            Memory.processing_status == "ready",
            Memory.extracted_text.is_not(None),
            or_(
                Memory.summary.is_(None),
                Memory.summary == "",
                Memory.context_inference.is_(None),
                Memory.context_inference == "",
            ),
        )
    ).all()
    for memory in memories:
        try:
            memory.summary, memory.context_inference = analyze_memory(memory)
            db.commit()
        except LLMConfigurationError:
            db.rollback()
            logger.warning("Skipping AI analysis because hosted LLM configuration is missing.")
            return
        except Exception:
            db.rollback()
            logger.exception("Could not analyze memory %s", memory.id)
