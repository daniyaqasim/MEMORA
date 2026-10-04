from uuid import UUID

from fastapi import Header, HTTPException, status


SESSION_HEADER = "X-Memora-Session"
LEGACY_SESSION_ID = "legacy-unscoped"


def get_session_id(session_id: str | None = Header(default=None, alias=SESSION_HEADER)) -> str:
    """Validate the anonymous browser namespace used for memory operations."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid X-Memora-Session header is required for memory operations.",
        )
    try:
        return str(UUID(session_id))
    except (ValueError, AttributeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Memora-Session must be a valid UUID.",
        ) from error
