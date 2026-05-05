"""Doc-level embedding 스테이지 — 기획서 §10.6 diff 감지 / §10.8 Tier 2 dedup 전제.

문서 하나를 대표하는 1024-dim 벡터를 `documents.doc_embedding` 에 저장.

소스 우선순위
    1. `summary` + `implications` — tag_summarize 가 성공적으로 저장한 요약
    2. `raw_text[:3000]` — 요약이 NULL 인 경우 (태그·요약 호출 실패한 케이스)
    3. 둘 다 없으면 건너뜀 (스테이지는 succeeded, doc_embedding 은 NULL 유지)
"""

from __future__ import annotations

import logging
import unicodedata

from app.adapters.impl.bgem3_hf_embedding import get_bgem3_provider
from app.adapters.parser import ExtractionResult
from app.db import get_supabase_client
from app.ingest.jobs import stage

logger = logging.getLogger(__name__)

_STAGE = "doc_embed"
_RAW_FALLBACK_CHARS = 3000


def run_doc_embed_stage(
    job_id: str, *, doc_id: str, extraction: ExtractionResult
) -> bool:
    """doc_embedding 생성 후 documents 갱신. 반환: 실제로 벡터를 채웠는지 여부."""
    with stage(job_id, _STAGE):
        client = get_supabase_client()
        row = (
            client.table("documents")
            .select("summary, implications")
            .eq("id", doc_id)
            .limit(1)
            .execute()
            .data[0]
        )

        source = _pick_source(
            summary=row.get("summary"),
            implications=row.get("implications"),
            raw_text=extraction.raw_text,
        )
        if not source:
            logger.info("doc_embed: doc=%s 소스 텍스트 없음 → 스킵", doc_id)
            return False

        provider = get_bgem3_provider()
        emb = provider.embed(source)

        (
            client.table("documents")
            .update({"doc_embedding": emb.dense})
            .eq("id", doc_id)
            .execute()
        )
        return True


def _pick_source(
    *, summary: str | None, implications: str | None, raw_text: str
) -> str | None:
    """W25 D14+1 D1 — 임베딩 입력 NFC 정규화 (한국어 chunks 와 일관).

    HWP/HWPX 의 raw_text 가 NFD 일 때 doc_embedding 의 임베딩 분포가 chunks 와 어긋남
    → multi-doc 검색 doc-level RRF 가산의 신뢰도 저하 회피.
    """
    if summary and summary.strip():
        parts = [summary.strip()]
        if implications and implications.strip():
            parts.append(implications.strip())
        return unicodedata.normalize("NFC", "\n\n".join(parts))
    if raw_text and raw_text.strip():
        return unicodedata.normalize(
            "NFC", raw_text[:_RAW_FALLBACK_CHARS].strip()
        )
    return None
