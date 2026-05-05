"""W25 D14 — update_stage_progress / clear_stage_progress 회귀 보호.

ingest_jobs.stage_progress JSONB 컬럼이 vision_enrich 등에서 페이지 단위로
업데이트되는지 + 마이그레이션 010 미적용 환경에서도 graceful skip 하는지 검증.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class StageProgressHelpersTest(unittest.TestCase):
    def test_update_stage_progress_calls_jsonb_update(self) -> None:
        from app.ingest import jobs as jobs_module

        client = MagicMock()
        with patch.object(jobs_module, "get_supabase_client", return_value=client):
            jobs_module.update_stage_progress(
                "job-1", current=12, total=41, unit="pages"
            )

        # ingest_jobs.update({stage_progress: {...}}).eq('id','job-1').execute()
        client.table.assert_called_with("ingest_jobs")
        update_call = client.table.return_value.update.call_args
        payload = update_call.args[0]
        self.assertIn("stage_progress", payload)
        self.assertEqual(payload["stage_progress"], {
            "current": 12, "total": 41, "unit": "pages",
        })

    def test_update_stage_progress_skips_on_db_error(self) -> None:
        """마이그레이션 010 미적용 등 DB 예외 시 graceful — 임베딩 파이프라인 무영향."""
        from app.ingest import jobs as jobs_module

        client = MagicMock()
        client.table.return_value.update.return_value.eq.return_value.execute.side_effect = (
            RuntimeError("column stage_progress does not exist")
        )
        with patch.object(jobs_module, "get_supabase_client", return_value=client):
            # raise 안 함
            jobs_module.update_stage_progress(
                "job-1", current=1, total=10, unit="pages"
            )

    def test_clear_stage_progress_sets_null(self) -> None:
        from app.ingest import jobs as jobs_module

        client = MagicMock()
        with patch.object(jobs_module, "get_supabase_client", return_value=client):
            jobs_module.clear_stage_progress("job-1")
        update_call = client.table.return_value.update.call_args
        self.assertEqual(update_call.args[0], {"stage_progress": None})


if __name__ == "__main__":
    unittest.main()
