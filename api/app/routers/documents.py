"""문서 업로드 및 인제스트 상태 조회 엔드포인트.

기획서 참조
- §10.2 인제스트 파이프라인 전체 플로우
- §10.8 Tier 1 중복 감지 (SHA-256)
- §10.11 SLO: 수신 응답 < 2초
- §11.3 입력 게이트 단계 A (확장자 화이트리스트, 크기 50MB)
"""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.adapters.impl.supabase_storage import SupabaseBlobStorage
from app.config import get_settings
from app.db import get_supabase_client
from app.ingest import create_job, get_latest_job_for_doc, list_logs_for_job, run_pipeline

router = APIRouter(prefix="/documents", tags=["documents"])

# 기획서 §11.3 단계 A
_ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "pdf",
    ".hwp": "hwp",
    ".hwpx": "hwpx",
    ".docx": "docx",
    ".pptx": "pptx",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".heic": "image",
    ".txt": "txt",
    ".md": "md",
}
_MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
_SourceChannel = Literal["drag-drop", "os-share", "clipboard", "url", "camera", "api"]


# ============================================================
# Response schemas
# ============================================================
class UploadResponse(BaseModel):
    doc_id: str
    job_id: str | None
    duplicated: bool


class JobStatus(BaseModel):
    job_id: str
    status: str
    current_stage: str | None
    attempts: int
    error_msg: str | None
    queued_at: str
    started_at: str | None
    finished_at: str | None


class DocumentStatusResponse(BaseModel):
    doc_id: str
    job: JobStatus | None
    logs: list[dict] | None = None


class DocumentListItem(BaseModel):
    id: str
    title: str
    doc_type: str
    source_channel: str
    size_bytes: int
    content_type: str
    tags: list[str]
    summary: str | None
    flags: dict
    chunks_count: int
    latest_job_status: str | None
    latest_job_stage: str | None
    created_at: str


class DocumentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DocumentListItem]


# ============================================================
# GET /documents — 리스트
# ============================================================
@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(20, ge=1, le=100, description="한 페이지 최대 반환 건수"),
    offset: int = Query(0, ge=0, description="건너뛸 건수 (페이지네이션)"),
) -> DocumentListResponse:
    """최신순 문서 리스트. 각 항목에 chunks 개수 + 최신 ingest_jobs 상태 포함.

    브라우저 `/docs` (Swagger UI) 에서 Try it out 으로 즉시 확인 가능한 검증 UX.
    """
    supabase = get_supabase_client()
    settings = get_settings()

    total_resp = (
        supabase.table("documents")
        .select("id", count="exact")
        .eq("user_id", settings.default_user_id)
        .is_("deleted_at", "null")
        .execute()
    )
    total = total_resp.count or 0

    docs_resp = (
        supabase.table("documents")
        .select(
            "id, title, doc_type, source_channel, size_bytes, content_type, "
            "tags, summary, flags, created_at"
        )
        .eq("user_id", settings.default_user_id)
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    items: list[DocumentListItem] = []
    for doc in docs_resp.data or []:
        doc_id = doc["id"]

        chunks_resp = (
            supabase.table("chunks")
            .select("id", count="exact")
            .eq("doc_id", doc_id)
            .execute()
        )
        chunks_count = chunks_resp.count or 0

        latest_job_resp = (
            supabase.table("ingest_jobs")
            .select("status, current_stage")
            .eq("doc_id", doc_id)
            .order("queued_at", desc=True)
            .limit(1)
            .execute()
        )
        latest_job = latest_job_resp.data[0] if latest_job_resp.data else None

        items.append(
            DocumentListItem(
                id=doc_id,
                title=doc["title"],
                doc_type=doc["doc_type"],
                source_channel=doc["source_channel"],
                size_bytes=doc["size_bytes"],
                content_type=doc["content_type"],
                tags=list(doc.get("tags") or []),
                summary=doc.get("summary"),
                flags=dict(doc.get("flags") or {}),
                chunks_count=chunks_count,
                latest_job_status=latest_job["status"] if latest_job else None,
                latest_job_stage=latest_job.get("current_stage") if latest_job else None,
                created_at=doc["created_at"],
            )
        )

    return DocumentListResponse(total=total, limit=limit, offset=offset, items=items)


# ============================================================
# POST /documents
# ============================================================
@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_channel: _SourceChannel = Form("api"),
    title: str | None = Form(None),
) -> UploadResponse:
    data = await file.read()
    file_name = file.filename or "untitled"

    # ---- 입력 게이트 단계 A ----
    ext = PurePosixPath(file_name).suffix.lower()
    doc_type = _ALLOWED_EXTENSIONS.get(ext)
    if doc_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원되지 않는 확장자입니다: {ext or '(없음)'}",
        )
    size = len(data)
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 파일입니다.",
        )
    if size > _MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 크기 상한(50MB) 초과: {size} bytes",
        )

    sha256 = hashlib.sha256(data).hexdigest()
    content_type = file.content_type or "application/octet-stream"
    settings = get_settings()
    supabase = get_supabase_client()

    # ---- Tier 1 dedup ----
    existing = (
        supabase.table("documents")
        .select("id")
        .eq("user_id", settings.default_user_id)
        .eq("sha256", sha256)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if existing.data:
        return UploadResponse(
            doc_id=existing.data[0]["id"],
            job_id=None,
            duplicated=True,
        )

    # ---- Storage 업로드 ----
    storage = SupabaseBlobStorage(bucket=settings.supabase_storage_bucket)
    blob = storage.put(data=data, file_name=file_name, content_type=content_type)

    # ---- documents insert ----
    doc_title = title or PurePosixPath(file_name).stem
    doc_row = (
        supabase.table("documents")
        .insert(
            {
                "user_id": settings.default_user_id,
                "title": doc_title,
                "doc_type": doc_type,
                "source_channel": source_channel,
                "storage_path": blob.path,
                "sha256": sha256,
                "size_bytes": size,
                "content_type": content_type,
            }
        )
        .execute()
    )
    doc_id = doc_row.data[0]["id"]

    # ---- ingest_jobs insert + BackgroundTasks ----
    job = create_job(doc_id=doc_id)
    background_tasks.add_task(run_pipeline, job.id, doc_id)

    return UploadResponse(doc_id=doc_id, job_id=job.id, duplicated=False)


# ============================================================
# GET /documents/{doc_id}/status
# ============================================================
@router.get("/{doc_id}/status", response_model=DocumentStatusResponse)
def get_document_status(
    doc_id: str,
    include_logs: bool = Query(False, alias="include_logs"),
) -> DocumentStatusResponse:
    supabase = get_supabase_client()
    existing = (
        supabase.table("documents")
        .select("id")
        .eq("id", doc_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문서를 찾을 수 없습니다.",
        )

    job = get_latest_job_for_doc(doc_id)
    job_payload = (
        JobStatus(
            job_id=job.id,
            status=job.status,
            current_stage=job.current_stage,
            attempts=job.attempts,
            error_msg=job.error_msg,
            queued_at=job.queued_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )
        if job
        else None
    )
    logs = list_logs_for_job(job.id) if include_logs and job else None

    return DocumentStatusResponse(doc_id=doc_id, job=job_payload, logs=logs)
