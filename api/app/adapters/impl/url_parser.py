"""trafilatura 기반 URL 본문 추출기.

W2 명세 v0.3 §3.E — Tertiary Golden Path (§6.3) 카페 아이폰 URL 공유 시나리오.

설계
- 입력은 HTML bytes (UploadFile 동등) — fetch 는 라우터(`POST /documents/url`)가 담당
- trafilatura.extract 로 본문만 추출 (광고·메뉴·footer 자동 제거)
- 본문이 빈약(빈 문자열)하면 raise — graceful skip 아닌 fail (사용자 인지 가능)
- 단락 분할은 \\n\\n 우선, 없으면 \\n 으로
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

import trafilatura

from app.adapters.parser import ExtractedSection, ExtractionResult

logger = logging.getLogger(__name__)


class UrlParser:
    source_type = "url"

    def can_parse(self, file_name: str, mime_type: str | None) -> bool:
        ext = PurePosixPath(file_name).suffix.lower()
        if ext in (".html", ".htm"):
            return True
        return bool(mime_type and mime_type.startswith("text/html"))

    def parse(self, data: bytes, *, file_name: str) -> ExtractionResult:
        try:
            html = data.decode("utf-8", errors="replace")
        except Exception as exc:
            raise RuntimeError(f"HTML 디코드 실패: {file_name}: {exc}") from exc

        try:
            text = trafilatura.extract(
                html,
                output_format="txt",
                include_comments=False,
                include_tables=True,
                favor_precision=True,  # 노이즈 회피 우선
            )
        except Exception as exc:
            raise RuntimeError(f"trafilatura 추출 예외: {file_name}: {exc}") from exc

        if not text or not text.strip():
            raise RuntimeError(
                f"trafilatura 추출 결과 빈 문자열: {file_name} (본문 빈약 또는 페이지 구조 인식 실패)"
            )

        # 단락 분할 — 빈 줄 기준 우선
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) <= 1:
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        sections = [
            ExtractedSection(text=p, page=None, section_title=None, bbox=None)
            for p in paragraphs
        ]
        return ExtractionResult(
            source_type=self.source_type,
            sections=sections,
            raw_text=text.strip(),
            warnings=[],
        )
