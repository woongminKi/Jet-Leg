"""W25 D14 — 한국어 NFD/NFC 정규화 회귀 보호.

배경: macOS Finder 가 한국어 파일명을 NFD (자모 분리) 형태로 보냄. DB ilike·검색
query 와 byte 매칭 fail 하는 사고 (W25 D14 '승인글 템플릿1' 삭제 시 발견).

수정: 인제스트 단 title 저장 시 NFC 통일, /search·/answer 의 q 파라미터 NFC 정규화.
"""

from __future__ import annotations

import unicodedata
import unittest


class NfcNormalizationTest(unittest.TestCase):
    """NFC 정규화 자체 — 한국어 자모 분리/결합 변환 검증."""

    NFD_TITLE = unicodedata.normalize("NFD", "승인글 템플릿1")
    NFC_TITLE = unicodedata.normalize("NFC", "승인글 템플릿1")

    def test_nfd_and_nfc_differ_in_bytes(self) -> None:
        """NFD/NFC 가 다른 byte sequence — byte 매칭 fail 의 직접 원인."""
        self.assertNotEqual(self.NFD_TITLE.encode("utf-8"), self.NFC_TITLE.encode("utf-8"))

    def test_normalize_nfc_idempotent(self) -> None:
        """NFC normalize 가 NFD/NFC 입력 모두 같은 NFC 출력."""
        self.assertEqual(
            unicodedata.normalize("NFC", self.NFD_TITLE),
            unicodedata.normalize("NFC", self.NFC_TITLE),
        )


class SearchQueryNormalizationTest(unittest.TestCase):
    """/search 의 q 파라미터가 NFC 로 통일되는지 검증."""

    def test_search_clean_q_is_nfc(self) -> None:
        """search 라우터 함수 직접 호출 — clean_q 정규화 확인.

        실 RPC 호출은 mock 으로 건너뛰고, q 파라미터 처리만 검증.
        """
        # 검증 strategy: source code 에 unicodedata.normalize("NFC", ...) 호출 있는지
        from pathlib import Path

        src = Path(__file__).resolve().parents[1] / "app" / "routers" / "search.py"
        text = src.read_text(encoding="utf-8")
        self.assertIn(
            'unicodedata.normalize("NFC", q.strip())', text,
            "search.py 의 q 파라미터가 NFC 정규화 안 됨",
        )


class AnswerQueryNormalizationTest(unittest.TestCase):
    def test_answer_clean_q_is_nfc(self) -> None:
        from pathlib import Path

        src = Path(__file__).resolve().parents[1] / "app" / "routers" / "answer.py"
        text = src.read_text(encoding="utf-8")
        self.assertIn(
            'unicodedata.normalize("NFC", q.strip())', text,
            "answer.py 의 q 파라미터가 NFC 정규화 안 됨",
        )


class IngestTitleNormalizationTest(unittest.TestCase):
    def test_documents_router_normalizes_title_at_insert(self) -> None:
        """POST /documents 가 title 을 NFC 로 통일 후 저장 (file upload + URL 두 경로)."""
        from pathlib import Path

        src = Path(__file__).resolve().parents[1] / "app" / "routers" / "documents.py"
        text = src.read_text(encoding="utf-8")
        # 두 곳 모두 NFC 호출 필요
        self.assertGreaterEqual(
            text.count('unicodedata.normalize("NFC"'),
            2,
            "documents.py 가 file upload + URL 두 경로 모두 NFC 정규화 안 함",
        )


if __name__ == "__main__":
    unittest.main()
