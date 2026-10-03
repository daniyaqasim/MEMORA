from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.answering import answer_from_memories, unique_memory_sources
from app.services.llm import LLMConfigurationError, LLMServiceError
from app.services.search import semantic_search


router = APIRouter(tags=["search"])
RESULT_LIMIT = 5


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@router.post("/api/search")
def search_memories(request: SearchRequest, db: Session = Depends(get_db)) -> dict[str, str | list[dict[str, str | float]]]:
    """Retrieve relevant evidence, then generate a grounded memory answer."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a question to search memories.")

    sources = unique_memory_sources(semantic_search(db, question, RESULT_LIMIT))
    if not sources:
        return {
            "question": question,
            "answer": "I couldn't find enough information in your saved memories to answer that.",
            "sources": [],
        }

    try:
        answer = answer_from_memories(question, sources)
    except LLMConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except LLMServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    return {"question": question, "answer": answer, "sources": sources}
