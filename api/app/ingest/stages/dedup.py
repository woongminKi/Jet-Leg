"""Tier 2 / Tier 3 중복 감지 스테이지 — 기획서 §10.8.

Tier 1 (SHA-256 일치) 은 라우터 upload 단계에서 이미 처리. 이 스테이지는 doc_embedding 기반.

Tier 2: 문서 임베딩 cosine similarity ≥ 0.95 → "거의 동일한 자료"
    flags.duplicate_tier = 2
    flags.duplicate_of   = <other_doc_id>
    flags.duplicate_similarity = 0.97

Tier 3: 위를 통과 못 하고 sim ≥ 0.85 + 파일명 유사도 ≥ 0.6 → "이전 버전 관계 추정"
    flags.duplicate_tier = 3
    flags.previous_version_of = <other_doc_id>
    flags.duplicate_similarity = 0.88

검출만 수행. UI 경고·머지·변경점 diff 호출(§10.6 호출 3) 은 W3 이후.

MVP 규모(수백 문서)에선 Python 측에서 cosine 계산이 충분. W3 에 규모 늘면 pgvector RPC 함수로 이관.
"""

from __future__ import annotations

import logging
import math
from difflib import SequenceMatcher
from typing import Any

from app.config import get_settings
from app.db import get_supabase_client
from app.ingest.jobs import skip_stage, stage

logger = logging.getLogger(__name__)

_STAGE = "dedup"
_TIER2_THRESHOLD = 0.95
_TIER3_SIM_THRESHOLD = 0.85
_TIER3_FILENAME_THRESHOLD = 0.6


def run_dedup_stage(job_id: str, *, doc_id: str) -> dict | None:
    """Tier 2/3 검출. 반환: 매칭 시 정보 dict, 없으면 None."""
    client = get_supabase_client()
    settings = get_settings()

    me = _fetch_me(client, doc_id)
    if not me or not me.get("doc_embedding"):
        skip_stage(job_id, stage=_STAGE, reason="doc_embedding 이 없어 스킵")
        return None

    my_vec = _parse_vec(me["doc_embedding"])
    my_name = me.get("storage_path") or me.get("title") or ""

    with stage(job_id, _STAGE):
        candidates = _fetch_candidates(
            client, user_id=settings.default_user_id, exclude_id=doc_id
        )
        if not candidates:
            logger.info("dedup: doc=%s 비교 대상 없음", doc_id)
            return None

        ranked: list[tuple[float, dict]] = []
        for c in candidates:
            other_vec = _parse_vec(c["doc_embedding"])
            sim = _cosine(my_vec, other_vec)
            ranked.append((sim, c))
        ranked.sort(key=lambda x: x[0], reverse=True)

        top_sim, top_row = ranked[0]
        top_name = top_row.get("storage_path") or top_row.get("title") or ""
        fname_sim = _filename_similarity(my_name, top_name)

        match: dict | None = None
        if top_sim >= _TIER2_THRESHOLD:
            match = {
                "duplicate_tier": 2,
                "duplicate_of": top_row["id"],
                "duplicate_similarity": round(top_sim, 4),
            }
        elif top_sim >= _TIER3_SIM_THRESHOLD and fname_sim >= _TIER3_FILENAME_THRESHOLD:
            match = {
                "duplicate_tier": 3,
                "previous_version_of": top_row["id"],
                "duplicate_similarity": round(top_sim, 4),
                "filename_similarity": round(fname_sim, 4),
            }

        if match:
            _apply_flags(client, doc_id=doc_id, patch=match)
            logger.info(
                "dedup: doc=%s tier=%d other=%s sim=%.4f",
                doc_id,
                match["duplicate_tier"],
                top_row["id"],
                top_sim,
            )
        else:
            logger.info(
                "dedup: doc=%s 매칭 없음 (top_sim=%.4f, fname=%.4f)",
                doc_id,
                top_sim,
                fname_sim,
            )

        return match


# ---------------------- internals ----------------------


def _fetch_me(client: Any, doc_id: str) -> dict | None:
    resp = (
        client.table("documents")
        .select("id, title, storage_path, doc_embedding")
        .eq("id", doc_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _fetch_candidates(client: Any, *, user_id: str, exclude_id: str) -> list[dict]:
    resp = (
        client.table("documents")
        .select("id, title, storage_path, doc_embedding")
        .eq("user_id", user_id)
        .is_("deleted_at", "null")
        .neq("id", exclude_id)
        .not_.is_("doc_embedding", "null")
        .execute()
    )
    return resp.data or []


def _apply_flags(client: Any, *, doc_id: str, patch: dict) -> None:
    existing = (
        client.table("documents")
        .select("flags")
        .eq("id", doc_id)
        .limit(1)
        .execute()
        .data[0]
        .get("flags")
        or {}
    )
    merged = {**dict(existing), **patch}
    client.table("documents").update({"flags": merged}).eq("id", doc_id).execute()


def _parse_vec(raw: Any) -> list[float]:
    if isinstance(raw, list):
        return [float(x) for x in raw]
    if isinstance(raw, str):
        import json
        parsed = json.loads(raw)
        return [float(x) for x in parsed]
    raise TypeError(f"doc_embedding 파싱 실패: {type(raw).__name__}")


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _filename_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()
