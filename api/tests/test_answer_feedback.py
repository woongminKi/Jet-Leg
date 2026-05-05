"""W25 D14 — POST /answer/feedback 회귀 보호.

마이그 011 미적용 환경에서 graceful skip + 첫 실패 후 cool-down 검증.
정상 INSERT 케이스 검증.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class AnswerFeedbackTest(unittest.TestCase):
    def setUp(self) -> None:
        from app.routers.answer import reset_feedback_disabled

        reset_feedback_disabled()

    def _payload(self):
        from app.routers.answer import AnswerFeedbackRequest

        return AnswerFeedbackRequest(
            query="질문 예시",
            answer_text="답변 예시",
            helpful=True,
            comment=None,
            doc_id=None,
            sources_count=3,
            model="gemini-2.5-flash",
        )

    def test_normal_insert_returns_feedback_id(self) -> None:
        from app.routers import answer as answer_module

        client = MagicMock()
        resp = MagicMock(); resp.data = [{"id": 42}]
        client.table.return_value.insert.return_value.execute.return_value = resp

        with patch.object(answer_module, "get_supabase_client", return_value=client):
            result = answer_module.submit_answer_feedback(self._payload())

        self.assertEqual(result.feedback_id, 42)
        self.assertFalse(result.skipped)

    def test_table_missing_returns_skipped_and_disables(self) -> None:
        """마이그 011 미적용 시 graceful — skipped=true + 이후 호출 silently 비활성."""
        from app.routers import answer as answer_module

        client = MagicMock()
        client.table.return_value.insert.return_value.execute.side_effect = (
            RuntimeError("relation \"answer_feedback\" does not exist")
        )

        with patch.object(answer_module, "get_supabase_client", return_value=client):
            result1 = answer_module.submit_answer_feedback(self._payload())
            # 첫 호출 — 시도 후 fail → skipped
            self.assertTrue(result1.skipped)
            self.assertIsNone(result1.feedback_id)
            self.assertEqual(client.table.call_count, 1)

            # 두 번째 호출 — flag 비활성, supabase 호출 0
            result2 = answer_module.submit_answer_feedback(self._payload())
            self.assertTrue(result2.skipped)
            self.assertEqual(client.table.call_count, 1)


if __name__ == "__main__":
    unittest.main()
