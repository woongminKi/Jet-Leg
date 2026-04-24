"""Gemini 2.5 Flash 기반 `VisionCaptioner` 구현체 (W2 Day 1 스켈레톤).

HEIC/HEIF 는 Gemini 2.5 Flash 가 직접 지원 (DE-17 RESOLVED) — 별도 변환 없이
mime_type 만 정확히 전달하면 된다.

실제 단일 호출 JSON 프롬프트 (기획서 §10.4) · JSON 파싱 · 3회 retry · 다운스케일
로직은 W2 Day 2 에 구현. 현재는 Protocol 구현체 자리만 확보한다.
"""

from __future__ import annotations

from app.adapters.vision import VisionCaption

_DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiVisionCaptioner:
    def __init__(self, *, model: str = _DEFAULT_MODEL) -> None:
        self._model = model

    def caption(self, image_bytes: bytes, *, mime_type: str) -> VisionCaption:
        raise NotImplementedError(
            "GeminiVisionCaptioner.caption() 은 W2 Day 2 구현 예정 (현재 스켈레톤)."
        )
