import json
import logging
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import BACKEND_DIRECTORY
from app.models import Memory
from app.services.indexing import index_memory
from app.services.llm import LLMConfigurationError, complete_vision


logger = logging.getLogger(__name__)
IMAGE_MIME_TYPES = {"png": "image/png", "jpeg": "image/jpeg"}

VISION_PROMPT = """Analyze this saved screenshot or image for a personal memory system.
Use only information visibly supported by the image. Capture meaningful visible text, names, products, prices, dates, places, events, and other salient details. Do not infer sensitive attributes about people.
Return a JSON object with exactly these string fields:
- understood_content: a factual, searchable description of the visible image content.
- summary: a concise factual description of what the image contains.
- context_inference: a cautious explanation of why someone may have saved it. Use uncertainty language such as may, might, or appears; never claim to know their actual intent.
If text is unreadable or information is absent, say so rather than inventing it."""


def _image_path(memory: Memory) -> Path:
    return BACKEND_DIRECTORY / memory.file_path


def understand_image_memory(memory: Memory) -> tuple[str, str, str]:
    """Produce the single vision-derived representation used by all later stages."""
    mime_type = IMAGE_MIME_TYPES[memory.file_type]
    response = complete_vision(_image_path(memory), mime_type, VISION_PROMPT)
    try:
        payload = json.loads(response)
    except json.JSONDecodeError as error:
        raise ValueError("The hosted vision model did not return valid JSON.") from error

    values = tuple(payload.get(field) for field in ("understood_content", "summary", "context_inference"))
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError("The hosted vision model did not return complete image understanding.")
    return tuple(value.strip() for value in values)  # type: ignore[return-value]


def process_image_memory(db: Session, memory: Memory) -> None:
    """Persist image understanding once, then reuse the normal chunk/index pipeline."""
    understood_content, summary, context_inference = understand_image_memory(memory)
    memory.extracted_text = understood_content
    memory.summary = summary
    memory.context_inference = context_inference
    memory.processing_status = "ready"
    db.commit()
    db.refresh(memory)
    index_memory(db, memory)


def backfill_existing_images(db: Session) -> None:
    """Idempotently understand prior image memories which have no usable text."""
    memories = db.scalars(
        select(Memory).where(
            Memory.file_type.in_(IMAGE_MIME_TYPES),
            or_(Memory.extracted_text.is_(None), Memory.extracted_text == ""),
            Memory.processing_status.in_(("ready", "failed")),
        )
    ).all()
    for memory in memories:
        try:
            process_image_memory(db, memory)
        except LLMConfigurationError:
            db.rollback()
            logger.warning("Skipping image backfill because hosted vision configuration is missing.")
            return
        except Exception:
            db.rollback()
            memory.processing_status = "failed"
            memory.extracted_text = None
            db.commit()
            logger.exception("Could not understand image memory %s", memory.id)
