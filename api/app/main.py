from fastapi import FastAPI

from app.routers import documents_router

app = FastAPI(
    title="Jet-Rag API",
    version="0.1.0",
    description="한국어 멀티포맷 RAG 개인 지식 에이전트 — 백엔드",
)

app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
