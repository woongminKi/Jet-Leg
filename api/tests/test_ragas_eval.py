"""W25 D14 — /answer/eval-ragas 회귀 보호.

RAGAS evaluate 자체는 LLM judge 호출 (외부 의존성) 이라 mock — 캐시 hit/miss 동작과
graceful skip (마이그 012 미적용 / 의존성 누락) 만 검증.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class RagasEvalCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        from app.routers.answer import reset_ragas_eval_disabled

        reset_ragas_eval_disabled()

    def test_get_returns_empty_when_no_cache(self) -> None:
        from app.routers import answer as answer_module

        with (
            patch.object(answer_module, "get_supabase_client", return_value=MagicMock()),
            patch.object(answer_module, "_query_ragas_cache", return_value=None),
        ):
            resp = answer_module.get_ragas_eval(query="태양계")

        self.assertFalse(resp.cached)
        self.assertFalse(resp.skipped)
        self.assertIsNone(resp.metrics.faithfulness)

    def test_get_returns_cached_metrics(self) -> None:
        from app.routers import answer as answer_module

        cached_row = {
            "metrics": {"faithfulness": 0.95, "answer_relevancy": 0.82},
            "model_judge": "gemini-2.5-flash",
            "took_ms": 4500,
            "created_at": "2026-05-05T12:00:00Z",
        }
        with (
            patch.object(answer_module, "get_supabase_client", return_value=MagicMock()),
            patch.object(answer_module, "_query_ragas_cache", return_value=cached_row),
        ):
            resp = answer_module.get_ragas_eval(query="태양계")

        self.assertTrue(resp.cached)
        self.assertEqual(resp.metrics.faithfulness, 0.95)
        self.assertEqual(resp.metrics.answer_relevancy, 0.82)
        self.assertEqual(resp.judge_model, "gemini-2.5-flash")

    def test_get_skips_when_disabled_flag_set(self) -> None:
        """_ragas_eval_disabled True 시 supabase 호출 0."""
        from app.routers import answer as answer_module

        answer_module._ragas_eval_disabled = True
        try:
            client_mock = MagicMock()
            with patch.object(answer_module, "get_supabase_client", return_value=client_mock):
                resp = answer_module.get_ragas_eval(query="x")
            self.assertTrue(resp.skipped)
            client_mock.table.assert_not_called()
        finally:
            answer_module.reset_ragas_eval_disabled()


class RagasEvalSubmitTest(unittest.TestCase):
    def setUp(self) -> None:
        from app.routers.answer import reset_ragas_eval_disabled

        reset_ragas_eval_disabled()

    def test_submit_returns_cached_without_calling_evaluate(self) -> None:
        """캐시 hit 시 evaluate_single 호출 0."""
        from app.routers import answer as answer_module

        cached_row = {
            "metrics": {"faithfulness": 0.9, "answer_relevancy": 0.7},
            "model_judge": "gemini-2.5-flash",
            "took_ms": 3000,
            "created_at": "2026-05-05T12:00:00Z",
        }
        payload = answer_module.RagasEvalRequest(
            query="질문", answer_text="답변", contexts=["ctx1"]
        )
        with (
            patch.object(answer_module, "get_supabase_client", return_value=MagicMock()),
            patch.object(answer_module, "_query_ragas_cache", return_value=cached_row),
            patch("app.services.ragas_eval.evaluate_single") as eval_mock,
        ):
            resp = answer_module.submit_ragas_eval(payload)

        self.assertTrue(resp.cached)
        self.assertEqual(resp.metrics.faithfulness, 0.9)
        eval_mock.assert_not_called()

    def test_submit_skips_when_ragas_unavailable(self) -> None:
        """RagasUnavailable 시 graceful skipped 응답."""
        from app.routers import answer as answer_module
        from app.services.ragas_eval import RagasUnavailable

        payload = answer_module.RagasEvalRequest(
            query="질문", answer_text="답변", contexts=["ctx1"]
        )
        with (
            patch.object(answer_module, "get_supabase_client", return_value=MagicMock()),
            patch.object(answer_module, "_query_ragas_cache", return_value=None),
            patch(
                "app.services.ragas_eval.evaluate_single",
                side_effect=RagasUnavailable("의존성 누락"),
            ),
        ):
            resp = answer_module.submit_ragas_eval(payload)

        self.assertTrue(resp.skipped)
        self.assertIsNotNone(resp.note)


if __name__ == "__main__":
    unittest.main()
