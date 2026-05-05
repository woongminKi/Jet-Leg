"""W25 D14 — update_stage_progress / clear_stage_progress 회귀 보호.

ingest_jobs.stage_progress JSONB 컬럼이 vision_enrich 등에서 페이지 단위로
업데이트되는지 + 마이그레이션 010 미적용 환경에서도 graceful skip 하는지 검증.
+ 첫 실패 시 cool-down (이번 프로세스 동안 비활성) 회귀 보호.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class StageProgressHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        from app.ingest.jobs import reset_stage_progress_disabled

        reset_stage_progress_disabled()

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


class StageProgressCoolDownTest(unittest.TestCase):
    """W25 D14 — 첫 실패 시 모듈 flag 비활성으로 41회 fail 폭주 회피."""

    def setUp(self) -> None:
        from app.ingest.jobs import reset_stage_progress_disabled

        reset_stage_progress_disabled()

    def test_first_failure_disables_subsequent_calls(self) -> None:
        """첫 호출 실패 → 이후 호출은 supabase.table 호출 없이 early return."""
        from app.ingest import jobs as jobs_module

        client = MagicMock()
        client.table.return_value.update.return_value.eq.return_value.execute.side_effect = (
            RuntimeError("column stage_progress does not exist")
        )
        with patch.object(jobs_module, "get_supabase_client", return_value=client):
            # 첫 호출 — 실패하지만 raise 안 함, 모듈 flag 비활성됨
            jobs_module.update_stage_progress("job-1", current=1, total=41)
            self.assertEqual(client.table.call_count, 1)

            # 이후 40회 호출 — 모두 early return (supabase 호출 0)
            for current in range(2, 42):
                jobs_module.update_stage_progress(
                    "job-1", current=current, total=41
                )
            # 첫 호출 1회만 — 41회 fail 폭주 회피
            self.assertEqual(client.table.call_count, 1)

    def test_clear_also_skips_after_failure(self) -> None:
        """update 가 비활성된 후 clear 도 early return."""
        from app.ingest import jobs as jobs_module

        client = MagicMock()
        client.table.return_value.update.return_value.eq.return_value.execute.side_effect = (
            RuntimeError("column stage_progress does not exist")
        )
        with patch.object(jobs_module, "get_supabase_client", return_value=client):
            jobs_module.update_stage_progress("job-1", current=1, total=10)
            self.assertEqual(client.table.call_count, 1)
            # 이후 clear 도 호출 없음
            jobs_module.clear_stage_progress("job-1")
            self.assertEqual(client.table.call_count, 1)

    def test_reset_helper_re_enables(self) -> None:
        """reset_stage_progress_disabled() 호출 시 재활성 (테스트 격리 용)."""
        from app.ingest import jobs as jobs_module

        client = MagicMock()
        client.table.return_value.update.return_value.eq.return_value.execute.side_effect = (
            RuntimeError("transient")
        )
        with patch.object(jobs_module, "get_supabase_client", return_value=client):
            jobs_module.update_stage_progress("job-1", current=1, total=10)
        self.assertEqual(client.table.call_count, 1)

        # reset → 다시 활성
        jobs_module.reset_stage_progress_disabled()
        client2 = MagicMock()
        with patch.object(jobs_module, "get_supabase_client", return_value=client2):
            jobs_module.update_stage_progress("job-2", current=1, total=10)
        self.assertEqual(client2.table.call_count, 1)


if __name__ == "__main__":
    unittest.main()
