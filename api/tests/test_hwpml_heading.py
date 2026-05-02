"""W3 Day 5 #1 — HwpmlParser heading sticky propagate 단위 테스트.

HWPML 은 자산 빈도 낮음 → 합성 XML 로 검증.
- heading 패턴 단락 만나면 `current_title` 갱신
- 이후 본문 단락은 sticky 상속
- heading 만나기 전 단락은 fallback (`section {Id}`)
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("HF_API_TOKEN", "dummy-test-token")


_HWPML_FIXTURE = """\
<?xml version="1.0" encoding="UTF-8"?>
<HWPML>
  <BODY>
    <SECTION Id="0">
      <P><TEXT><CHAR>전문 머리말 (heading 전 단락)</CHAR></TEXT></P>
      <P><TEXT><CHAR>제1조(목적)</CHAR></TEXT></P>
      <P><TEXT><CHAR>이 규정은 OOO 을 목적으로 한다.</CHAR></TEXT></P>
      <P><TEXT><CHAR>제2조(정의)</CHAR></TEXT></P>
      <P><TEXT><CHAR>이 규정에서 사용하는 용어의 뜻은 다음과 같다.</CHAR></TEXT></P>
      <P><TEXT><CHAR>부칙</CHAR></TEXT></P>
      <P><TEXT><CHAR>이 규정은 공포한 날부터 시행한다.</CHAR></TEXT></P>
    </SECTION>
  </BODY>
</HWPML>
"""


class HwpmlHeadingPropagateTest(unittest.TestCase):
    def setUp(self) -> None:
        from app.adapters.impl.hwpml_parser import HwpmlParser

        self.result = HwpmlParser().parse(
            _HWPML_FIXTURE.encode("utf-8"), file_name="synthetic.hwp"
        )

    def test_sections_count(self) -> None:
        self.assertEqual(len(self.result.sections), 7)

    def test_pre_heading_uses_section_fallback(self) -> None:
        """첫 heading 만나기 전 단락은 fallback (section 0)."""
        first = self.result.sections[0]
        self.assertEqual(first.text, "전문 머리말 (heading 전 단락)")
        self.assertEqual(first.section_title, "section 0")

    def test_heading_paragraph_self_title(self) -> None:
        """heading 단락 자체의 section_title 이 자기 텍스트."""
        secs = self.result.sections
        self.assertEqual(secs[1].text, "제1조(목적)")
        self.assertEqual(secs[1].section_title, "제1조(목적)")
        self.assertEqual(secs[3].text, "제2조(정의)")
        self.assertEqual(secs[3].section_title, "제2조(정의)")
        self.assertEqual(secs[5].text, "부칙")
        self.assertEqual(secs[5].section_title, "부칙")

    def test_sticky_propagate_to_body(self) -> None:
        """heading 직후 본문 단락이 sticky 상속."""
        secs = self.result.sections
        self.assertEqual(secs[2].section_title, "제1조(목적)")
        self.assertEqual(secs[4].section_title, "제2조(정의)")
        self.assertEqual(secs[6].section_title, "부칙")

    def test_section_title_fill_ratio_meets_kpi(self) -> None:
        """모든 단락이 fallback 또는 sticky 로 채워지므로 100% (≥ 30%)."""
        total = len(self.result.sections)
        filled = sum(1 for s in self.result.sections if s.section_title)
        self.assertGreaterEqual(filled / total, 0.30)


if __name__ == "__main__":
    unittest.main()
