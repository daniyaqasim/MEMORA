from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal, init_db
from app.routes.memories import router as memories_router
from app.routes.search import router as search_router
from app.services.analysis import analyze_existing_memories
from app.services.image_processing import backfill_existing_images
from app.services.indexing import index_existing_memories


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        backfill_existing_images(db)
        index_existing_memories(db)
        analyze_existing_memories(db)
    finally:
        db.close()
    yield


app = FastAPI(title="MEMORA API", lifespan=lifespan)

# Local Vite development servers and the deployed MEMORA frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://memora-six-psi.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(memories_router)
app.include_router(search_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Provide a lightweight availability check for the frontend."""
    return {"status": "ok", "service": "MEMORA API"}
