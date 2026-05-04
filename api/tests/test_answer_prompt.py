"""W25 D12 — `/answer` 라우터 prompt 구성 회귀 차단.

단위 테스트는 LLM/Supabase 호출 없이 `_build_messages` 만 검증.
실 endpoint 호출은 smoke (uvicorn + 실 Gemini) 로 별도 검증.
"""
from __future__ import annotations

import unittest

from app.adapters.llm import ChatMessage
from app.routers.answer import _build_messages, _CHUNK_TEXT_MAX


def _make_chunk(idx: int, text: str = "본문", title: str | None = "샘플 문서") -> dict:
    return {
        "chunk_id": f"chunk-{idx}",
        "doc_id": f"doc-{idx}",
        "doc_title": title,
        "chunk_idx": idx,
        "text": text,
        "page": idx + 1,
        "section_title": None,
        "score": 1.0,
    }


class TestBuildMessages(unittest.TestCase):
    def test_system_message_first(self):
        chunks = [_make_chunk(0, "샘플 본문")]
        msgs = _build_messages("질문", chunks)
        self.assertEqual(msgs[0].role, "system")
        # faithfulness 키 phrase 포함.
        self.assertIn("외부 지식이나 추측을 절대 추가하지 마세요", msgs[0].content)
        self.assertIn("[1], [2]", msgs[0].content)

    def test_user_message_includes_query_and_chunks(self):
        chunks = [
            _make_chunk(0, "전장 4,910mm", title="소나타 카탈로그"),
            _make_chunk(1, "전폭 1,860mm", title="소나타 카탈로그"),
        ]
        msgs = _build_messages("소나타 전장 길이가 얼마나 돼?", chunks)
        user = msgs[1]
        self.assertEqual(user.role, "user")
        self.assertIn("소나타 전장 길이가 얼마나 돼?", user.content)
        self.assertIn("[1] 소나타 카탈로그", user.content)
        self.assertIn("[2] 소나타 카탈로그", user.content)
        self.assertIn("전장 4,910mm", user.content)
        self.assertIn("전폭 1,860mm", user.content)

    def test_long_chunk_truncated(self):
        # _CHUNK_TEXT_MAX 초과 chunk 는 절단 + ... 표시.
        long_text = "한국어 가" * (_CHUNK_TEXT_MAX // 2)
        chunks = [_make_chunk(0, long_text)]
        msgs = _build_messages("질문", chunks)
        self.assertIn("...", msgs[1].content)

    def test_no_title_fallback(self):
        chunks = [_make_chunk(0, "본문", title=None)]
        msgs = _build_messages("질문", chunks)
        self.assertIn("(제목 없음)", msgs[1].content)

    def test_empty_chunks_still_builds_messages(self):
        # PoC 흐름 — endpoint 가 0건 시 LLM 호출 전 회피하지만 헬퍼 자체는 robust.
        msgs = _build_messages("질문", [])
        self.assertEqual(len(msgs), 2)
        self.assertIn("질문", msgs[1].content)
        self.assertIn("검색 결과:", msgs[1].content)

    def test_messages_are_chatmessages(self):
        msgs = _build_messages("질문", [_make_chunk(0)])
        for m in msgs:
            self.assertIsInstance(m, ChatMessage)


if __name__ == "__main__":
    unittest.main()
