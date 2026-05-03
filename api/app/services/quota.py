"""W9 — Gemini API quota 초과 감지 유틸리티.

배경
- W9 Day 4 PptxParser 가 Vision RESOURCE_EXHAUSTED 시 fast-fail 도입.
- W9 Day 6 tag_summarize 도 동일 패턴 적용 — 두 stage 가 같은 휴리스틱 공유.
- pptx_parser 에 두지 않고 별도 모듈로 분리 — 의존성 방향 정석화 (stage → util).

설계 — stdlib only.
"""

from __future__ import annotations


def is_quota_exhausted(error_msg: str) -> bool:
    """Gemini API 의 quota 초과 에러 메시지인지 검사.

    Gemini SDK 가 raise 하는 google.api_core.exceptions.ResourceExhausted 는
    str() 시 "429 RESOURCE_EXHAUSTED" 또는 "quota" 포함. 보수적으로 셋 다 검사.
    """
    if not error_msg:
        return False
    upper = error_msg.upper()
    return (
        "RESOURCE_EXHAUSTED" in upper
        or "429" in error_msg
        or "QUOTA" in upper
    )
