"""W3 Day 5 #1 — HwpxParser heading sticky propagate 단위 테스트.

검증 범위
- `_is_heading_paragraph` 의 (A) Style 정규식 / (B) 텍스트 fallback / 길이 cap
- 실 자산 두 개에 대한 KPI §13.1 "section_title 채움 비율 ≥ 30%" 충족
- heading 단락 자체가 ExtractedSection 으로 포함됨 (옵션 A)
- sticky propagate — heading 다음 본문 단락이 직전 heading text 를 상속
- BadZipFile 시 RuntimeError raise

실 HWPX 자산은 프로젝트 루트(.../piLab/Jet-Rag/) 에 위치 — 복사 금지, 절대 경로 참조.
환경 변수 `JETRAG_TEST_HWPX_DIR` 로 override 가능. 파일 부재 시 skip (CI 환경 호환).
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

# 모듈 import 단계에서 환경 변수 요구 회피
os.environ.setdefault("HF_API_TOKEN", "dummy-test-token")


_DEFAULT_HWPX_DIR = "/Users/kiwoongmin/Desktop/piLab/Jet-Rag"
_FILE_A = "직제_규정(2024.4.30.개정).hwpx"
_FILE_B = "한마음생활체육관_운영_내규(2024.4.30.개정).hwpx"


def _hwpx_path(name: str) -> Path:
    base = os.environ.get("JETRAG_TEST_HWPX_DIR", _DEFAULT_HWPX_DIR)
    return Path(base) / name


class IsHeadingParagraphTest(unittest.TestCase):
    """`_is_heading_paragraph` 의 분기별 동작."""

    def test_style_pattern_match(self) -> None:
        from app.adapters.impl.hwpx_parser import _is_heading_paragraph

        # 한국 공공·법령 HWPX 의 실제 스타일명
        self.assertTrue(_is_heading_paragraph("대전광역시 직제 규정", "법-제목"))
        self.assertTrue(_is_heading_paragraph("제1장 총칙", "장"))
        self.assertTrue(_is_heading_paragraph("제1조 목적", "조"))
        self.assertTrue(_is_heading_paragraph("머리말 본문", "머리말"))
        self.assertTrue(_is_heading_paragraph("1", "간지1"))
        self.assertTrue(_is_heading_paragraph("별표", "별표"))
        # 영문 outline 스타일도 인식
        self.assertTrue(_is_heading_paragraph("Intro", "Heading 1"))
        self.assertTrue(_is_heading_paragraph("Ch", "chapter 2"))

    def test_style_pattern_no_match_for_body_or_meta(self) -> None:
        from app.adapters.impl.hwpx_parser import _is_heading_paragraph

        # 본문 / 메타 / 표 스타일은 heading 아님
        self.assertFalse(_is_heading_paragraph("일반 본문", "바탕글"))
        self.assertFalse(_is_heading_paragraph("개정 2001.1.1.", "법률개정날짜"))
        self.assertFalse(_is_heading_paragraph("간격 단락", "간격"))
        self.assertFalse(_is_heading_paragraph("셀 텍스트", "표안-가운데"))
        self.assertFalse(_is_heading_paragraph("값", "표안-일반"))

    def test_text_fallback_when_style_missing(self) -> None:
        from app.adapters.impl.hwpx_parser import _is_heading_paragraph

        # style.name 이 본문 스타일이지만 텍스트가 outline 패턴 → fallback hit
        self.assertTrue(_is_heading_paragraph("제1조(목적) 이 규정은", "바탕글"))
        self.assertTrue(_is_heading_paragraph("부칙", "바탕글"))
        self.assertTrue(_is_heading_paragraph("별표 1", None))
        self.assertTrue(_is_heading_paragraph("제3장 구성", None))

    def test_text_fallback_length_cap(self) -> None:
        """긴 본문이 prefix 만 outline 패턴이면 false positive 차단."""
        from app.adapters.impl.hwpx_parser import _is_heading_paragraph

        long_text = "제1조(목적) " + "x" * 200  # > 80 chars
        self.assertFalse(_is_heading_paragraph(long_text, "바탕글"))

    def test_neither_style_nor_text_pattern(self) -> None:
        from app.adapters.impl.hwpx_parser import _is_heading_paragraph

        self.assertFalse(_is_heading_paragraph("일반 한 줄 텍스트", "바탕글"))
        self.assertFalse(_is_heading_paragraph("", None))


class HwpxParserBadInputTest(unittest.TestCase):
    """오류 입력 처리."""

    def test_bad_zip_raises_runtime_error(self) -> None:
        from app.adapters.impl.hwpx_parser import HwpxParser

        with self.assertRaises(RuntimeError) as ctx:
            HwpxParser().parse(b"not a zip", file_name="bad.hwpx")
        self.assertIn("HWPX 열기 실패", str(ctx.exception))


class HwpxParserRealAssetTest(unittest.TestCase):
    """실 HWPX 자산에 대한 KPI 검증. 자산 부재 시 skip."""

    def _parse(self, file_name: str):
        from app.adapters.impl.hwpx_parser import HwpxParser

        path = _hwpx_path(file_name)
        if not path.exists():
            self.skipTest(f"HWPX fixture not found: {path}")
        data = path.read_bytes()
        return HwpxParser().parse(data, file_name=file_name)

    def _assert_kpi(self, file_name: str) -> None:
        result = self._parse(file_name)
        total = len(result.sections)
        self.assertGreater(total, 0, f"sections empty for {file_name}")
        filled = sum(1 for s in result.sections if s.section_title)
        ratio = filled / total
        # KPI §13.1 — 채움 비율 ≥ 30%
        self.assertGreaterEqual(
            ratio,
            0.30,
            f"section_title ratio={ratio:.1%} (<30%) for {file_name} "
            f"(total={total}, filled={filled})",
        )

    def test_directive_regulation_kpi(self) -> None:
        self._assert_kpi(_FILE_A)

    def test_gym_internal_rule_kpi(self) -> None:
        self._assert_kpi(_FILE_B)

    def test_heading_paragraph_itself_included(self) -> None:
        """heading 단락 자체가 ExtractedSection 에 들어있어야 함 (옵션 A)."""
        result = self._parse(_FILE_A)
        # 직제_규정 첫 단락이 '대전광역시시설관리공단 직제 규정' (법-제목)
        first_texts = [s.text for s in result.sections[:3]]
        self.assertTrue(
            any("직제 규정" in t for t in first_texts),
            f"법-제목 단락이 sections 에 포함되지 않음: first 3 = {first_texts!r}",
        )

    def test_sticky_propagate_after_heading(self) -> None:
        """heading 단락 직후의 본문 단락이 그 heading text 를 section_title 로 상속."""
        result = self._parse(_FILE_A)
        # heading 패턴인 단락 찾고, 다음 단락의 section_title 이 그 heading text 인지 확인
        from app.adapters.impl.hwpx_parser import _HEADING_TEXT_PATTERN

        for i, sec in enumerate(result.sections[:-1]):
            if (
                len(sec.text) <= 80
                and _HEADING_TEXT_PATTERN.match(sec.text)
                and sec.section_title == sec.text
            ):
                # 다음 단락이 같은 title 을 sticky 로 갖는지 검증 (또는 더 깊은 heading 으로 갱신)
                nxt = result.sections[i + 1]
                self.assertIsNotNone(
                    nxt.section_title,
                    f"sticky propagate 실패: idx={i + 1} title=None",
                )
                return  # 한 건 확인이면 충분
        self.fail("text-pattern heading 단락을 찾지 못함 — 자산 가정과 다름")


if __name__ == "__main__":
    unittest.main()
