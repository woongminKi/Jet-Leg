"""Load 스테이지 — 청크 레코드를 pgvector 테이블에 upsert.

Day 4 범위: 텍스트·메타만 적재. `dense_vec` / `sparse_json` 은 NULL / `{}` 로 남음.
Day 5 에 embed 스테이지가 청크를 재조회해 임베딩 채운 뒤 같은 `(doc_id, chunk_idx)` 유니크 키로
UPSERT 해서 채운다.
"""

from __future__ import annotations

from app.adapters.impl.supabase_vectorstore import SupabasePgVectorStore
from app.adapters.vectorstore import ChunkRecord
from app.ingest.jobs import stage

_STAGE = "load"


def run_load_stage(job_id: str, *, chunks: list[ChunkRecord]) -> int:
    """chunks 를 Supabase 에 upsert. 반환: 적재(또는 업데이트) 건수."""
    with stage(job_id, _STAGE):
        if not chunks:
            return 0
        vector_store = SupabasePgVectorStore()
        vector_store.upsert_chunks(chunks)
        return len(chunks)
