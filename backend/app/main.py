from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, chat, dashboard, documents, exercises, health, languages, users
from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.services.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    if not settings.skip_db_init:
        init_db()
        db = SessionLocal()
        try:
            seed_demo_data(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title="Agent IA de formation",
    description="MVP — formation et évaluation pédagogique (RAG local via Ollama)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(exercises.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(languages.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Agent IA de formation — API", "docs": "/docs"}
