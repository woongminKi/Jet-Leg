"""W13 Day 1 — US-07 회수: 화이트보드 action_items 추출 단위 테스트.

배경
- 기획서 §3 US-07: "화이트보드 사진 → 액션 아이템만 구조화 추출"
- gemini_vision._PROMPT 가 화이트보드 type 시 structured.action_items 반환
- ImageParser 가 _extract_action_items 로 list of str / list of dict 정규화 후
  별도 ExtractedSection ("액션 아이템") 생성

stdlib unittest + mock only.
"""

from __future__ import annotations

import os
import unittest
from io import BytesIO
from unittest.mock import MagicMock

from PIL import Image

os.environ.setdefault("HF_API_TOKEN", "dummy-test-token")
os.environ.setdefault("GEMINI_API_KEY", "dummy-test-token")


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (50, 50), color="white").save(buf, format="PNG")
    return buf.getvalue()


class ExtractActionItemsHelperTest(unittest.TestCase):
    """_extract_action_items 정규화 동작."""

    def test_list_of_strings(self) -> None:
        from app.adapters.impl.image_parser import _extract_action_items

        out = _extract_action_items(
            {"action_items": ["A 보고", "B 검토", "  공백 trim  "]}
        )
        self.assertEqual(out, ["A 보고", "B 검토", "공백 trim"])

    def test_list_of_dicts_joined(self) -> None:
        from app.adapters.impl.image_parser import _extract_action_items

        out = _extract_action_items({
            "action_items": [
                {"task": "보고서 작성", "owner": "김철수", "due_date": "2026-05-10"},
                {"task": "검토", "owner": "박영희"},
            ]
        })
        self.assertEqual(len(out), 2)
        self.assertIn("보고서 작성", out[0])
        self.assertIn("김철수", out[0])
        self.assertIn("2026-05-10", out[0])

    def test_empty_or_none(self) -> None:
        from app.adapters.impl.image_parser import _extract_action_items

        self.assertEqual(_extract_action_items(None), [])
        self.assertEqual(_extract_action_items({}), [])
        self.assertEqual(_extract_action_items({"action_items": None}), [])
        self.assertEqual(_extract_action_items({"action_items": []}), [])
        self.assertEqual(_extract_action_items({"other_key": ["x"]}), [])

    def test_filters_blank_strings(self) -> None:
        from app.adapters.impl.image_parser import _extract_action_items

        out = _extract_action_items({"action_items": ["", "  ", "valid"]})
        self.assertEqual(out, ["valid"])


class WhiteboardSectionTest(unittest.TestCase):
    """ImageParser 가 화이트보드 caption 시 액션 아이템 별도 ExtractedSection 생성."""

    def setUp(self) -> None:
        from app.services import vision_metrics
        vision_metrics.reset()

    def test_whiteboard_with_action_items(self) -> None:
        from app.adapters.impl.image_parser import ImageParser
        from app.adapters.vision import VisionCaption

        captioner = MagicMock()
        captioner.caption.return_value = VisionCaption(
            type="화이트보드",
            ocr_text="OKR 회의 화이트보드",
            caption="OKR 회의 화이트보드 사진",
            structured={
                "action_items": ["보고서 초안 5/10까지", "예산 확정"],
            },
        )

        result = ImageParser(captioner=captioner).parse(
            _png_bytes(), file_name="board.png"
        )

        # caption + ocr + action_items 3 섹션
        section_titles = [s.section_title for s in result.sections]
        self.assertIn("액션 아이템", section_titles)
        action_section = next(
            s for s in result.sections if s.section_title == "액션 아이템"
        )
        self.assertIn("보고서 초안", action_section.text)
        self.assertIn("예산 확정", action_section.text)
        # 불릿 형식 검증
        self.assertTrue(action_section.text.startswith("- "))

    def test_non_whiteboard_no_action_items_section(self) -> None:
        """type='문서' + structured=None → 액션 아이템 섹션 미생성."""
        from app.adapters.impl.image_parser import ImageParser
        from app.adapters.vision import VisionCaption

        captioner = MagicMock()
        captioner.caption.return_value = VisionCaption(
            type="문서",
            ocr_text="일반 문서 텍스트",
            caption="일반 문서",
            structured=None,
        )

        result = ImageParser(captioner=captioner).parse(
            _png_bytes(), file_name="doc.png"
        )

        section_titles = [s.section_title for s in result.sections]
        self.assertNotIn("액션 아이템", section_titles)

    def test_whiteboard_without_action_items(self) -> None:
        """화이트보드 type 이지만 structured.action_items 누락 → 섹션 미생성."""
        from app.adapters.impl.image_parser import ImageParser
        from app.adapters.vision import VisionCaption

        captioner = MagicMock()
        captioner.caption.return_value = VisionCaption(
            type="화이트보드",
            ocr_text="필기 텍스트만",
            caption="화이트보드 사진",
            structured={"other_field": "x"},  # action_items 없음
        )

        result = ImageParser(captioner=captioner).parse(
            _png_bytes(), file_name="board2.png"
        )

        section_titles = [s.section_title for s in result.sections]
        self.assertNotIn("액션 아이템", section_titles)


if __name__ == "__main__":
    unittest.main()
