from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chunk, Memory
from app.services.analysis import analyze_memory
from app.services.extraction import extract_text
from app.services.image_processing import IMAGE_MIME_TYPES, process_image_memory
from app.services.indexing import index_memory, rebuild_vector_index


router = APIRouter(prefix="/api/memories", tags=["memories"])

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 1024 * 1024
UPLOADS_DIRECTORY = Path(__file__).resolve().parents[2] / "uploads"

SUPPORTED_FILES = {
    ".pdf": {"file_type": "pdf", "media_types": {"application/pdf", "application/x-pdf"}},
    ".png": {"file_type": "png", "media_types": {"image/png"}},
    ".jpg": {"file_type": "jpeg", "media_types": {"image/jpeg", "image/pjpeg"}},
    ".jpeg": {"file_type": "jpeg", "media_types": {"image/jpeg", "image/pjpeg"}},
    ".txt": {"file_type": "txt", "media_types": {"text/plain"}},
}


def validate_upload(file: UploadFile) -> tuple[str, str, str]:
    """Return a safe display name, extension, and file type for a valid upload."""
    original_filename = Path(file.filename or "").name
    if not original_filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A file is required.")

    extension = Path(original_filename).suffix.lower()
    file_details = SUPPORTED_FILES.get(extension)
    if not file_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload a PDF, PNG, JPEG, or TXT file.",
        )

    content_type = (file.content_type or "").lower()
    generic_content_types = {"", "application/octet-stream"}
    if content_type not in generic_content_types and content_type not in file_details["media_types"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The uploaded file type does not match its {extension} extension.",
        )

    return original_filename, extension, file_details["file_type"]


def serialize_memory(memory: Memory, include_extracted_text: bool = False) -> dict[str, str | int | None]:
    """Return API-safe memory metadata without exposing the storage path."""
    result: dict[str, str | int | None] = {
        "id": memory.id,
        "filename": memory.filename,
        "stored_filename": memory.stored_filename,
        "file_type": memory.file_type,
        "size": memory.size,
        "uploaded_at": memory.uploaded_at.isoformat(),
        "processing_status": memory.processing_status,
        "status": "uploaded",
    }
    if include_extracted_text:
        result["file_path"] = memory.file_path
        result["extracted_text"] = memory.extracted_text
        result["summary"] = memory.summary
        result["context_inference"] = memory.context_inference
    return result


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_memory(
    file: UploadFile | None = File(default=None), db: Session = Depends(get_db)
) -> dict[str, str | int | None]:
    """Store a file, create its persistent memory record, then extract supported text."""
    if file is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A file is required.")

    original_filename, extension, file_type = validate_upload(file)
    UPLOADS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    memory_id = uuid4().hex
    stored_file = UPLOADS_DIRECTORY / f"{memory_id}{extension}"
    temporary_file = UPLOADS_DIRECTORY / f".{memory_id}.part"
    total_size = 0

    try:
        with temporary_file.open("wb") as destination:
            while chunk := await file.read(CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File is too large. The maximum upload size is 10 MB.",
                    )
                destination.write(chunk)

        if total_size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")

        temporary_file.replace(stored_file)
    except HTTPException:
        temporary_file.unlink(missing_ok=True)
        raise
    except OSError as error:
        temporary_file.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The file could not be saved.",
        ) from error
    finally:
        await file.close()

    memory = Memory(
        id=memory_id,
        filename=original_filename,
        stored_filename=stored_file.name,
        file_type=file_type,
        file_path=str(Path("uploads") / stored_file.name),
        size=total_size,
        processing_status="processing",
    )
    try:
        db.add(memory)
        db.commit()
        db.refresh(memory)
    except SQLAlchemyError as error:
        db.rollback()
        stored_file.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The memory record could not be saved.",
        ) from error

    if file_type in IMAGE_MIME_TYPES:
        try:
            process_image_memory(db, memory)
        except Exception:
            db.rollback()
            memory.processing_status = "failed"
            memory.extracted_text = None
    else:
        try:
            memory.extracted_text = extract_text(stored_file, file_type)
            memory.processing_status = "ready"
        except Exception:
            # A file remains a valid memory even when its Stage 3 extraction fails.
            memory.processing_status = "failed"
            memory.extracted_text = None

    try:
        db.commit()
        db.refresh(memory)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The memory was saved, but its processing status could not be updated.",
        ) from error

    if file_type not in IMAGE_MIME_TYPES:
        try:
            index_memory(db, memory)
        except Exception:
            # The memory remains available; startup will retry indexing if needed.
            pass

    if memory.extracted_text and not (memory.summary and memory.context_inference):
        try:
            memory.summary, memory.context_inference = analyze_memory(memory)
            db.commit()
            db.refresh(memory)
        except Exception:
            # AI analysis is additive; it must never make a valid memory unavailable.
            db.rollback()

    return serialize_memory(memory)


@router.get("")
def list_memories(db: Session = Depends(get_db)) -> list[dict[str, str | int | None]]:
    """List persisted memories with newest uploads first."""
    memories = db.scalars(select(Memory).order_by(Memory.uploaded_at.desc())).all()
    return [serialize_memory(memory) for memory in memories]


@router.get("/{memory_id}")
def get_memory(memory_id: str, db: Session = Depends(get_db)) -> dict[str, str | int | None]:
    """Return one persisted memory and any text extracted in Stage 3."""
    memory = db.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
    return serialize_memory(memory, include_extracted_text=True)


@router.get("/{memory_id}/image")
def get_memory_image(memory_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Serve an original image only through its persisted memory ID."""
    memory = db.get(Memory, memory_id)
    if memory is None or memory.file_type not in IMAGE_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image memory not found.")

    image_path = UPLOADS_DIRECTORY / memory.stored_filename
    if not image_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The stored image file was not found.")
    return FileResponse(image_path, media_type=IMAGE_MIME_TYPES[memory.file_type])


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """Remove a memory, its chunks, its vector presence, and its stored file."""
    memory = db.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")

    stored_file = UPLOADS_DIRECTORY / memory.stored_filename
    staged_file = UPLOADS_DIRECTORY / f".{memory.id}.deleting"
    file_staged = False
    if stored_file.exists():
        try:
            stored_file.replace(staged_file)
            file_staged = True
        except OSError as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The uploaded file could not be prepared for deletion.",
            ) from error

    try:
        remaining_chunks = db.scalars(
            select(Chunk).where(Chunk.memory_id != memory.id).order_by(Chunk.id)
        ).all()
        rebuild_vector_index(remaining_chunks)
    except Exception as error:
        if file_staged:
            staged_file.replace(stored_file)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The semantic index could not be updated; the memory was not deleted.",
        ) from error

    try:
        db.execute(delete(Chunk).where(Chunk.memory_id == memory.id))
        db.delete(memory)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        # Restore the old search index from the still-persisted database state.
        try:
            rebuild_vector_index(db.scalars(select(Chunk).order_by(Chunk.id)).all())
        finally:
            if file_staged:
                staged_file.replace(stored_file)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The memory record could not be deleted.",
        ) from error

    if file_staged:
        try:
            staged_file.unlink()
        except OSError as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The memory was deleted, but its stored file could not be removed.",
            ) from error

    return {"status": "deleted"}
