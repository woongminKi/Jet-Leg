"""python-hwpx 기반 HWPX 문서 파서.

W2 명세 v0.3 §3.C — 페르소나 A 의 주요 포맷. HWPX 는 한글 2014+ 의 기본 저장 포맷
(ZIP 컨테이너 + Contents/section*.xml).

설계
- `TextExtractor` 는 ZipFile / 경로를 받음 → bytes 는 BytesIO 로 감싸 ZipFile 구성
- section 단위로 단락을 순회해 `ExtractedSection` 누적
- HWPX 는 PDF 와 달리 page 개념이 없음 → `ExtractedSection.page` 는 항상 None
- 단락/섹션 단위 부분 실패 허용 (`warnings`)

`section_title` 정책 (W3 Day 5 갱신, KPI §13.1 충족)
- heading 단락 sticky propagate — heading 만나면 `current_title` 갱신, 다음 본문 단락
  들은 그 title 을 상속 (chunk.py `_merge_short_sections` 가 첫 non-null 보존)
- heading 판별: (A) Style.name 정규식 매칭 → (B) 단락 텍스트 inline 패턴 fallback
- heading 단락 자체도 `ExtractedSection` 에 포함해 검색 대상에 둠 (옵션 A)
- 첫 heading 만나기 전 단락은 `section_title=None` (이전 동작 호환)

기획서 §10.3 그라데이션 — 한국 공공·기업 자료 다수가 HWPX. 추출 실패는 graceful skip 이 아니라
파이프라인 fail 로 가야 사용자가 인지 가능 → `parse()` 에서 raise.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import PurePosixPath

import hwpx

from app.adapters.parser import ExtractedSection, ExtractionResult

logger = logging.getLogger(__name__)


# heading 판별 — Style.name 정규식
# 한국 공공·법령 HWPX 의 실제 스타일명 기반 (예: 법-제목 / 장 / 절 / 조 / 간지N / 머리말 / 별표).
# 본문/메타 스타일 (바탕글 / 본문 / 법률개정날짜 / 간격 / 표안-* 등) 은 매칭되지 않도록 ^...$ 앵커.
_HEADING_STYLE_PATTERN = re.compile(
    r"^(법-제목|제목|소제목|머리말|간지\d*|장|절|조|편|관|항목제목"
    r"|별표(\s*-.*)?|별첨(\s*-.*)?|Heading\s*\d*|개요\s*\d*|chapter\s*\d*)$",
    re.IGNORECASE,
)

# heading 판별 — 단락 텍스트 inline 패턴 (fallback)
# Style.name 매칭이 안 되는데 (`바탕글` 등) 텍스트 자체가 outline 패턴인 경우 잡음.
_HEADING_TEXT_PATTERN = re.compile(
    r"^(제\s*\d+\s*[조항장절편관]|부칙|별표\s*\d*|별첨\s*\d*)([\s(].*)?$"
)

# 텍스트 inline 패턴 적용 최대 길이 — 너무 긴 본문이 우연히 prefix 만 매칭하는 false positive 차단
_HEADING_TEXT_MAX_LEN = 80


class HwpxParser:
    source_type = "hwpx"

    def can_parse(self, file_name: str, mime_type: str | None) -> bool:
        ext = PurePosixPath(file_name).suffix.lower()
        if ext == ".hwpx":
            return True
        # HWPX 의 표준 MIME 타입은 정착되지 않음 → 확장자 우선.
        # 일부 클라이언트가 application/zip 으로 전송하는 케이스는 무시 (DOCX/PPTX 와 충돌)
        return False

    def parse(self, data: bytes, *, file_name: str) -> ExtractionResult:
        sections: list[ExtractedSection] = []
        warnings: list[str] = []
        raw_parts: list[str] = []

        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise RuntimeError(
                f"HWPX 열기 실패 (zip 형식 아님): {file_name}: {exc}"
            ) from exc

        # styles 매핑은 graceful degrade — HwpxDocument 열기 실패 시 빈 dict 로 진행.
        # 같은 BytesIO 를 두 번 못 쓰므로 별도 인스턴스.
        styles_map: dict[str, str] = {}
        doc = None
        try:
            doc = hwpx.HwpxDocument.open(io.BytesIO(data))
            styles_map = {
                sid: getattr(style, "name", None) or ""
                for sid, style in doc.styles.items()
            }
        except Exception as exc:  # noqa: BLE001 — styles 매핑 실패해도 본문 추출은 계속
            msg = f"HwpxDocument 열기 실패 → 텍스트 패턴 fallback 으로 진행: {exc}"
            warnings.append(msg)
            logger.warning("%s (file=%s)", msg, file_name)
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:  # noqa: BLE001 — close 실패는 비치명적
                    pass

        try:
            try:
                extractor = hwpx.TextExtractor(zf)
            except Exception as exc:
                raise RuntimeError(
                    f"HWPX 파서 초기화 실패: {file_name}: {exc}"
                ) from exc

            current_title: str | None = None
            try:
                for sec in extractor.iter_sections():
                    try:
                        for para in extractor.iter_paragraphs(sec):
                            try:
                                text = extractor.paragraph_text(para.element).strip()
                            except Exception as exc:  # noqa: BLE001
                                msg = (
                                    f"section[{sec.index}] paragraph[{para.index}] "
                                    f"추출 실패: {exc}"
                                )
                                warnings.append(msg)
                                logger.warning("%s (file=%s)", msg, file_name)
                                continue
                            if not text:
                                continue

                            style_id = para.element.get("styleIDRef")
                            style_name = styles_map.get(style_id) if style_id else None
                            if _is_heading_paragraph(text, style_name):
                                current_title = text

                            sections.append(
                                ExtractedSection(
                                    text=text,
                                    page=None,  # HWPX 는 page 개념 없음
                                    section_title=current_title,
                                    bbox=None,
                                )
                            )
                            raw_parts.append(text)
                    except Exception as exc:  # noqa: BLE001 — section 단위 부분 실패 허용
                        msg = (
                            f"section[{sec.index}] '{sec.name}' 단락 순회 실패: {exc}"
                        )
                        warnings.append(msg)
                        logger.warning("%s (file=%s)", msg, file_name)
            finally:
                extractor.close()
        finally:
            zf.close()

        return ExtractionResult(
            source_type=self.source_type,
            sections=sections,
            raw_text="\n\n".join(raw_parts),
            warnings=warnings,
        )


def _is_heading_paragraph(text: str, style_name: str | None) -> bool:
    """단락이 heading 인지 판정.

    (A) Style.name 이 heading 정규식과 매칭되면 True.
    (B) 그렇지 않더라도 텍스트가 inline outline 패턴이고 길이 ≤ `_HEADING_TEXT_MAX_LEN`
        이면 True (본문 prefix false positive 차단).
    """
    if style_name and _HEADING_STYLE_PATTERN.match(style_name.strip()):
        return True
    if len(text) <= _HEADING_TEXT_MAX_LEN and _HEADING_TEXT_PATTERN.match(text):
        return True
    return False


def _normalize_section_title(raw: str | None) -> str | None:
    """`hwpx.SectionInfo.name` 정규화 (deprecated, W3 Day 5 이후 미사용).

    sticky heading propagate 가 진짜 의미의 section title 을 채우게 되면서 ZIP 내부 경로
    sentinel 처리는 더 이상 필요 없음. 외부 import 호환을 위해 함수는 남김.
    """
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if cleaned.startswith("Contents/section") and cleaned.endswith(".xml"):
        return None
    return cleaned
