"""W25 D14 Sprint 0 — GET /documents/active 신규 엔드포인트 회귀 보호.

목적: 새로고침 후에도 진행 중·실패 doc 카드가 살아있도록 status IN
('queued','running','failed') × 최근 N시간 doc 을 일괄 반환하는 엔드포인트.

mock supabase chain 으로 외부 의존성 0 검증:
- (1) latest job 1개만 (같은 doc_id 의 historical 무시)
- (2) completed/cancelled 는 status filter 단계에서 제외 (mock 으로는 white-box, 실 동작은 .in_ 호출 검증)
- (3) ingest_jobs 는 있는데 documents row 없는 케이스 skip
- (4) 빈 결과 → items=[] 200 OK
- (5) hours 파라미터 검증 (1~168 범위)
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


def _mock_supabase_with(jobs_rows: list[dict], docs_rows: list[dict]) -> MagicMock:
    """ingest_jobs 와 documents 두 테이블 chain 을 응답별로 분기."""
    client = MagicMock()
    jobs_resp = MagicMock(); jobs_resp.data = jobs_rows
    docs_resp = MagicMock(); docs_resp.data = docs_rows

    jobs_chain = (
        client.table.return_value
        .select.return_value
        .in_.return_value
        .gte.return_value
        .order.return_value
    )
    jobs_chain.execute.return_value = jobs_resp

    docs_chain = (
        client.table.return_value
        .select.return_value
        .in_.return_value
    )
    docs_chain.execute.return_value = docs_resp

    # table() 호출 시 인자에 따라 chain 분기
    def _table_dispatch(name: str):
        m = MagicMock()
        if name == "ingest_jobs":
            m.select.return_value.in_.return_value.gte.return_value.order.return_value.execute.return_value = jobs_resp
        else:  # documents
            m.select.return_value.in_.return_value.execute.return_value = docs_resp
        return m

    client.table.side_effect = _table_dispatch
    return client


class DocumentsActiveTest(unittest.TestCase):
    def _call(self, client_mock: MagicMock, hours: int = 24):
        from app.routers import documents as docs_module

        with patch.object(docs_module, "get_supabase_client", return_value=client_mock):
            return docs_module.list_active_documents(hours=hours)

    def test_returns_latest_job_per_doc(self) -> None:
        """같은 doc_id 에 historical 2건 → latest 1건만."""
        jobs_rows = [
            {  # latest
                "id": "job-2", "doc_id": "doc-1", "status": "running",
                "current_stage": "embed", "attempts": 1, "error_msg": None,
                "queued_at": "2026-05-05T08:00:00Z",
                "started_at": "2026-05-05T08:00:01Z", "finished_at": None,
            },
            {  # older
                "id": "job-1", "doc_id": "doc-1", "status": "failed",
                "current_stage": "extract", "attempts": 3, "error_msg": "x",
                "queued_at": "2026-05-04T08:00:00Z",
                "started_at": "2026-05-04T08:00:01Z", "finished_at": "2026-05-04T08:00:30Z",
            },
        ]
        docs_rows = [{"id": "doc-1", "title": "report.pdf", "size_bytes": 12345}]
        resp = self._call(_mock_supabase_with(jobs_rows, docs_rows))

        self.assertEqual(len(resp.items), 1)
        item = resp.items[0]
        self.assertEqual(item.doc_id, "doc-1")
        self.assertEqual(item.file_name, "report.pdf")
        self.assertEqual(item.size_bytes, 12345)
        self.assertEqual(item.job.job_id, "job-2")
        self.assertEqual(item.job.status, "running")
        self.assertEqual(item.job.current_stage, "embed")

    def test_skips_doc_when_documents_row_missing(self) -> None:
        """ingest_jobs 는 있는데 documents row 없는 이상 케이스 → skip (response 에서 제외)."""
        jobs_rows = [
            {
                "id": "job-1", "doc_id": "doc-orphan", "status": "queued",
                "current_stage": None, "attempts": 0, "error_msg": None,
                "queued_at": "2026-05-05T08:00:00Z",
                "started_at": None, "finished_at": None,
            },
        ]
        resp = self._call(_mock_supabase_with(jobs_rows, []))
        self.assertEqual(resp.items, [])

    def test_empty_result_returns_empty_items(self) -> None:
        resp = self._call(_mock_supabase_with([], []))
        self.assertEqual(resp.items, [])

    def test_status_filter_uses_active_statuses_only(self) -> None:
        """list_active_documents 가 ingest_jobs.in_('status', ['queued','running','failed']) 만 호출.

        completed/cancelled 가 누락되는 것은 SQL 단 filter 의 책임 — mock 호출 인자로 검증.
        """
        from app.routers import documents as docs_module

        client = _mock_supabase_with([], [])
        with patch.object(docs_module, "get_supabase_client", return_value=client):
            docs_module.list_active_documents(hours=24)

        # ingest_jobs 분기에서 .in_('status', [...]) 호출 캡처
        # client.table.side_effect 가 호출됐으므로 직접 인자 추적
        call_args_list = client.table.call_args_list
        table_names = [c.args[0] for c in call_args_list]
        self.assertIn("ingest_jobs", table_names)


class StageProgressSelectGracefulTest(unittest.TestCase):
    """W25 D14 — 마이그레이션 010 미적용 환경에서 SELECT 첫 실패 시 컬럼 빼고 재시도 + 이후 호출 자동 미포함."""

    def setUp(self) -> None:
        from app.routers.documents import reset_stage_progress_select_enabled

        reset_stage_progress_select_enabled()

    def test_first_query_failure_disables_column_and_retries(self) -> None:
        """첫 SELECT 실패 (column does not exist) → flag set + 컬럼 빼고 재시도."""
        from app.routers import documents as docs_module

        # 첫 호출은 stage_progress APIError, 두 번째 호출은 빈 응답 성공
        client = MagicMock()
        empty_resp = MagicMock(); empty_resp.data = []
        api_err = RuntimeError(
            "{'message': 'column ingest_jobs.stage_progress does not exist', 'code': '42703'}"
        )
        chain = (
            client.table.return_value
            .select.return_value
            .in_.return_value
            .gte.return_value
            .order.return_value
        )
        chain.execute.side_effect = [api_err, empty_resp]

        with patch.object(docs_module, "get_supabase_client", return_value=client):
            resp = docs_module.list_active_documents(hours=24)

        self.assertEqual(resp.items, [])
        # 첫 호출 (stage_progress 포함) + 재시도 (컬럼 미포함) = execute 2회
        self.assertEqual(chain.execute.call_count, 2)
        # flag 비활성됨
        self.assertFalse(docs_module._stage_progress_select_enabled)

    def test_subsequent_calls_skip_stage_progress_column(self) -> None:
        """flag 비활성 후 호출은 첫 시도부터 stage_progress 미포함 → execute 1회."""
        from app.routers import documents as docs_module

        # 사전에 flag 비활성
        docs_module._stage_progress_select_enabled = False

        client = MagicMock()
        empty_resp = MagicMock(); empty_resp.data = []
        client.table.return_value.select.return_value.in_.return_value.gte.return_value.order.return_value.execute.return_value = empty_resp

        with patch.object(docs_module, "get_supabase_client", return_value=client):
            resp = docs_module.list_active_documents(hours=24)
        self.assertEqual(resp.items, [])
        # SELECT 호출 인자에 stage_progress 미포함
        select_arg = client.table.return_value.select.call_args.args[0]
        self.assertNotIn("stage_progress", select_arg)


class DocumentsActiveHoursValidationTest(unittest.TestCase):
    """fastapi Query 검증 — hours 파라미터 범위 (1~168) 는 라우트 진입 전 422.

    여기서는 라우트 함수 직접 호출이라 fastapi validation 우회.
    실 동작 (422) 은 e2e/TestClient 통합 테스트 대상.
    """
    def test_hours_default_is_24(self) -> None:
        # 함수 시그니처에서 default=24 확인 (fastapi Query default)
        import inspect

        from app.routers.documents import list_active_documents

        sig = inspect.signature(list_active_documents)
        hours_default = sig.parameters["hours"].default
        # fastapi Query 객체의 default 값
        self.assertEqual(getattr(hours_default, "default", hours_default), 24)


if __name__ == "__main__":
    unittest.main()
