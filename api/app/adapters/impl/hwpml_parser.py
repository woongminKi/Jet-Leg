"""HWPML 파서 — 한컴 HWP 의 옛 XML 직렬화 형식 (Hwp ML 2.x).

W2 후속 (2026-04-28 발견). 법제처/국가법령정보센터 export 가 OLE2 (.hwp) 도
HWPX (zip) 도 아닌 **HWPML XML** 로 떨어지는 케이스 대응.

매직바이트
- (BOM 있음) `EF BB BF 3C 3F 78 6D 6C` = `\\ufeff<?xml`
- (BOM 없음) `3C 3F 78 6D 6C`         = `<?xml`
- 첫 ~4KB 안에 `<HWPML` 루트 태그 등장 — 임의 XML(.hwp 위장) 차단

추출 전략
- `xml.etree.ElementTree` (Python 표준) — 의존성 추가 0
- 본문은 `BODY > SECTION > P > TEXT > CHAR` 트리. `<P>` 단위 단락 분리, 각 P 안의
  모든 `<CHAR>.text` 합쳐 단락 텍스트
- 메타데이터: `<DOCSUMMARY><TITLE/SUBJECT/AUTHOR/DATE>` — content_gate 와는 별개로
  ExtractionResult.metadata 에 부착해 후속 활용 가능 (현재 미사용)

doc_type 정책
- DB CHECK 제약 (`pdf|hwp|hwpx|docx|pptx|image|url|txt|md`) 보존을 위해
  documents.doc_type 은 'hwp' 그대로. ExtractionResult.source_type 만 'hwpml'.
- dispatcher (extract.py) 가 raw bytes prefix 로 Hwp5Parser vs HwpmlParser 분기.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

from app.adapters.parser import ExtractedSection, ExtractionResult

logger = logging.getLogger(__name__)

_HWPML_ROOT = "HWPML"
_SNIFF_BYTES = 4096

# heading 판별 — HWPX 와 동일한 텍스트 inline 패턴 (HWPML 은 Style 매핑 복잡도 vs 효과
# trade-off 로 텍스트 패턴만 사용. 자산 빈도 낮음 — Day 5 기준 0건).
_HEADING_TEXT_PATTERN = re.compile(
    r"^(제\s*\d+\s*[조항장절편관]|부칙|별표\s*\d*|별첨\s*\d*)([\s(].*)?$"
)
_HEADING_TEXT_MAX_LEN = 80


def is_hwpml_bytes(head: bytes) -> bool:
    """raw bytes 앞부분이 HWPML XML 인지 sniff.

    BOM 유무 무관. 첫 _SNIFF_BYTES 안에 `<HWPML` 루트 태그가 등장해야 True.
    임의 XML(.hwp 위장) 은 root 태그가 다르므로 False.
    """
    if not head:
        return False
    stripped = head.lstrip(b"\xef\xbb\xbf")
    if not stripped.lstrip().startswith(b"<?xml"):
        return False
    return b"<" + _HWPML_ROOT.encode() in head[:_SNIFF_BYTES]


class HwpmlParser:
    source_type = "hwpml"

    def can_parse(self, file_name: str, mime_type: str | None) -> bool:
        ext = PurePosixPath(file_name).suffix.lower()
        return ext == ".hwp"

    def parse(self, data: bytes, *, file_name: str) -> ExtractionResult:
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise RuntimeError(
                f"HWPML XML 파싱 실패: {file_name}: {exc}. "
                "이 파일을 PDF 또는 HWPX 로 변환 후 다시 업로드해 주세요."
            ) from exc

        if root.tag != _HWPML_ROOT:
            raise RuntimeError(
                f"HWPML 루트 태그가 아닙니다 (root={root.tag!r}): {file_name}"
            )

        sections: list[ExtractedSection] = []
        raw_parts: list[str] = []
        warnings: list[str] = []

        for body in root.iter("BODY"):
            for section in body.iter("SECTION"):
                section_idx = section.get("Id")
                # sticky propagate — heading 단락 만나면 갱신, 그 이전은 fallback (section idx)
                fallback_title = f"section {section_idx}" if section_idx else None
                current_title: str | None = None
                for p in section.iter("P"):
                    # leaf P 만 — nested P 가 있으면 outer 는 컨테이너로 보고 skip
                    # (자식 P 가 자기 텍스트를 별도 단락으로 가져감 → 중복 회피)
                    if len(list(p.iter("P"))) > 1:
                        continue
                    text = _collect_paragraph_text(p)
                    if not text:
                        continue
                    if (
                        len(text) <= _HEADING_TEXT_MAX_LEN
                        and _HEADING_TEXT_PATTERN.match(text)
                    ):
                        current_title = text
                    sections.append(
                        ExtractedSection(
                            text=text,
                            page=None,  # HWPML 은 page 개념 없음
                            section_title=current_title or fallback_title,
                            bbox=None,
                        )
                    )
                    raw_parts.append(text)

        if not sections:
            warnings.append("HWPML 본문에서 텍스트 단락을 찾지 못했습니다.")

        metadata = _extract_summary_metadata(root)

        return ExtractionResult(
            source_type=self.source_type,
            sections=sections,
            raw_text="\n\n".join(raw_parts),
            warnings=warnings,
            metadata=metadata,
        )


def _collect_paragraph_text(p_elem: ET.Element) -> str:
    """`<P>` 의 직계 `<TEXT>/<CHAR>` 텍스트만 순서대로 join.

    구조: `<P><TEXT>...<CHAR>본문</CHAR>...</TEXT></P>`. 직계 2단으로 한정해
    nested PARAMETERSET·SECDEF 안의 스타일 메타데이터 CHAR 와 nested P 의 본문을
    회피.
    """
    chars: list[str] = []
    for char_elem in p_elem.findall("./TEXT/CHAR"):
        if char_elem.text:
            chars.append(char_elem.text)
    return "".join(chars).strip()


def _extract_summary_metadata(root: ET.Element) -> dict:
    """`<DOCSUMMARY>` 의 메타데이터 추출 (TITLE/SUBJECT/AUTHOR/DATE/KEYWORDS)."""
    out: dict = {}
    for tag in ("TITLE", "SUBJECT", "AUTHOR", "DATE", "KEYWORDS"):
        elem = root.find(f"./HEAD/DOCSUMMARY/{tag}")
        if elem is not None and elem.text and elem.text.strip():
            out[f"hwpml_{tag.lower()}"] = elem.text.strip()
    return out
