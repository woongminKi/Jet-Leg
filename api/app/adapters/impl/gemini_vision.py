"""Gemini 2.5 Flash 기반 `VisionCaptioner` 구현체.

기획서 §10.4 의 단일 호출 4필드 JSON 계약을 그대로 구현. 호출자는 정규화된 bytes 를
넘기는 책임 (`ImageParser` 가 다운스케일·EXIF transpose 담당, QA 검수 C-2). 본 구현은:

- google-genai SDK `inline_data` 로 이미지 1장 전달
- response_mime_type=application/json + `_PROMPT` 로 4필드 보장
- 3회 retry + 지수 백오프 (`_gemini_common.with_retry`)
- 파싱 시 type 필드는 화이트리스트, 외 케이스는 보수적으로 "기타" 분류

HEIC/HEIF 는 Gemini 가 직접 지원 (DE-17) — mime_type 만 정확히 전달하면 됨.
"""

from __future__ import annotations

import json
import logging

from google.genai import types

from app.adapters.impl._gemini_common import get_client, with_retry
from app.adapters.vision import VisionCaption, VisionCategory

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash"

# 기획서 §10.4 의 단일 호출 JSON 프롬프트.
# - type 은 8종 화이트리스트 (애매하면 "기타")
# - structured 는 type 별 다른 schema:
#   · 명함 → name/title/contact
#   · 차트 → axis/series/values
#   · 표 → headers/rows
#   · 화이트보드 → action_items (W13 Day 1 — US-07 회수)
#   · 그 외 → null
# - 한국어 출력 강제
_PROMPT = """\
당신은 이미지에서 정보를 정확하게 추출하는 분석가입니다.
다음 JSON 스키마에 정확히 맞춰 한국어로 응답하세요. 다른 텍스트 없이 JSON 만 출력합니다.

{
  "type": "문서|스크린샷|메신저대화|화이트보드|명함|차트|표|기타 중 하나 (애매하면 기타)",
  "ocr_text": "이미지의 모든 텍스트를 위→아래·좌→우 순서로. 텍스트가 없으면 빈 문자열",
  "caption": "이미지의 한국어 한 문장 요약 (≤ 80자, 끝에 마침표 없이)",
  "structured": "type 별 구조화 객체 — 명함: {name, title, contact}, 차트: {axis, series, values}, 표: {headers, rows}, 화이트보드: {action_items: [\"항목1\", \"항목2\", ...]} (담당자·기한 명시 시 그대로 보존). 구조화 불가 시 null"
}
"""

_VALID_TYPES: set[VisionCategory] = {
    "문서", "스크린샷", "메신저대화", "화이트보드", "명함", "차트", "표", "기타",
}


class GeminiVisionCaptioner:
    def __init__(self, *, model: str = _DEFAULT_MODEL) -> None:
        self._model = model

    def caption(self, image_bytes: bytes, *, mime_type: str) -> VisionCaption:
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(text=_PROMPT),
                ],
            ),
        ]
        config = types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )

        def call() -> str:
            response = get_client().models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
            text = response.text
            if text is None or not text.strip():
                raise RuntimeError(f"Gemini Vision 응답이 비어있습니다: {response}")
            return text

        text = with_retry(call, label="gemini.vision.caption")
        return self._parse(text)

    @staticmethod
    def _parse(text: str) -> VisionCaption:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Gemini Vision JSON 파싱 실패: {exc}; 응답 앞 200자: {text[:200]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise RuntimeError(
                f"Gemini Vision 응답이 dict 가 아닙니다: {type(data).__name__}; 앞 200자: {text[:200]!r}"
            )

        type_raw = data.get("type")
        type_: VisionCategory
        if type_raw in _VALID_TYPES:
            type_ = type_raw  # type: ignore[assignment]
        else:
            logger.warning("Gemini Vision type 화이트리스트 외 값 → '기타' 강제: %r", type_raw)
            type_ = "기타"

        ocr_text = data.get("ocr_text") or ""
        if not isinstance(ocr_text, str):
            ocr_text = str(ocr_text)

        caption_text = data.get("caption") or ""
        if not isinstance(caption_text, str):
            caption_text = str(caption_text)

        structured = data.get("structured")
        if not isinstance(structured, dict) or not structured:
            structured = None

        return VisionCaption(
            type=type_,
            ocr_text=ocr_text,
            caption=caption_text,
            structured=structured,
        )
