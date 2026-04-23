"""인제스트 파이프라인 entrypoint — `BackgroundTasks` 로 호출되는 단일 진입점.

Day 4 전반부 스코프 (§10.2 [4] · [7] · [10])
    extract → chunk → load

Day 4.5~5 에 [8] tag_summarize 와 [9] embed 가 추가되면 이 순서의 중간·끝에 삽입된다.
"""

from __future__ import annotations

import logging

from .jobs import fail_job, finish_job, start_job
from .stages.chunk import run_chunk_stage
from .stages.extract import run_extract_stage
from .stages.load import run_load_stage

logger = logging.getLogger(__name__)


def run_pipeline(job_id: str, doc_id: str) -> None:
    try:
        start_job(job_id, stage="extract")

        extraction = run_extract_stage(job_id, doc_id)
        if extraction is None:
            # 비 PDF graceful skip — 후속 스테이지 스킵, job 은 정상 완료
            finish_job(job_id)
            return

        chunk_records = run_chunk_stage(
            job_id, doc_id=doc_id, extraction=extraction
        )

        # TODO(Day 4.5): tag_summarize 스테이지 삽입

        loaded = run_load_stage(job_id, chunks=chunk_records)
        logger.info(
            "ingest pipeline done: job=%s doc=%s chunks_loaded=%s warnings=%s",
            job_id,
            doc_id,
            loaded,
            len(extraction.warnings),
        )

        finish_job(job_id)
    except Exception as exc:  # noqa: BLE001 — 최상위 경계
        logger.exception(
            "ingest pipeline failed: job=%s doc=%s", job_id, doc_id
        )
        try:
            fail_job(job_id, error_msg=str(exc))
        except Exception:
            logger.exception("ingest pipeline failure bookkeeping 실패")
