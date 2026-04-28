"""HWP 5.x 구포맷 파서 — pyhwp `hwp5txt` CLI subprocess.

W2 명세 v0.3 §3.F. HWP 5.x 는 OLE2 (CFB) 컨테이너 — pyhwp 의 Python API 가 매우
low-level 이라 공식 CLI `hwp5txt` 를 subprocess 로 호출하는 게 가장 안정적·이식적.

설계
- venv 의 `hwp5txt` 실행파일을 sys.executable 의 같은 bin 디렉토리에서 직접 호출
- 임시 파일에 bytes 를 쓴 후 CLI 에 경로 전달 → stdout 텍스트 수신
- 추출 결과는 단락 단위로 분할 (\\n\\n 우선, 없으면 \\n)
- timeout 30s — 큰 HWP 도 텍스트 추출은 빠름

기획서 §10.3 graceful degradation — HWP 자체 미지원이 아니라 추출 실패는 fail 로 마킹
(사용자 인지 가능). 암호화 HWP, 손상된 파일 등은 hwp5txt 의 stderr 메시지를 그대로 노출.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from app.adapters.parser import ExtractedSection, ExtractionResult

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30


class Hwp5Parser:
    source_type = "hwp"

    def can_parse(self, file_name: str, mime_type: str | None) -> bool:
        ext = PurePosixPath(file_name).suffix.lower()
        return ext == ".hwp"

    def parse(self, data: bytes, *, file_name: str) -> ExtractionResult:
        text = _hwp_to_text(data, file_name=file_name)

        if not text.strip():
            return ExtractionResult(
                source_type=self.source_type,
                sections=[],
                raw_text="",
                warnings=[
                    "HWP 추출 결과가 빈 문자열입니다 (텍스트 없음 또는 추출 실패)."
                ],
            )

        # 단락 분할 — \\n\\n 우선, fallback \\n
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


def _hwp_to_text(data: bytes, *, file_name: str) -> str:
    """`hwp5txt` CLI 를 subprocess 로 호출. 실패 시 RuntimeError raise."""
    cli_path = Path(sys.executable).parent / "hwp5txt"
    if not cli_path.exists():
        raise RuntimeError(
            f"hwp5txt CLI 를 찾을 수 없습니다: {cli_path} (pyhwp 설치 확인)"
        )

    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        try:
            result = subprocess.run(
                [str(cli_path), tmp_path],
                capture_output=True,
                timeout=_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"hwp5txt timeout ({_TIMEOUT_SECONDS}s 초과): {file_name}"
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(
                f"hwp5txt 변환 실패 (rc={result.returncode}): {file_name}: {stderr.strip()}"
            )
        return result.stdout.decode("utf-8", errors="replace")
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            logger.warning("HWP 임시 파일 삭제 실패: %s", tmp_path)
