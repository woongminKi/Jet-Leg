"""Gemini 2.5 Flash 기반 `LLMProvider` 구현체.

- google-genai SDK (2026년 최신) 래핑
- system / user / assistant role 을 Gemini system_instruction + Content 구조로 매핑
- JSON 모드 (response_mime_type='application/json')
- 3회 retry + 지수 백오프 (§10.10)

Vision 은 `GeminiVisionCaptioner` (adapters/impl/gemini_vision.py) 로 분리.
`_attach_images` 는 LLM 텍스트 생성 보조용으로만 유지하며 mime 은 PNG 고정 (레거시).
"""

from __future__ import annotations

import logging
import random
import time
from functools import lru_cache
from typing import Callable, TypeVar

from google import genai
from google.genai import types

from app.adapters.llm import ChatMessage
from app.config import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash"
_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 1.0

T = TypeVar("T")


class GeminiLLMProvider:
    """`LLMProvider` Protocol 구현체 (Gemini 2.5 Flash 기본)."""

    def __init__(self, *, model: str = _DEFAULT_MODEL) -> None:
        self._model = model

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        images: list[bytes] | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        system_instruction, conversation = self._build_contents(messages)
        if images:
            self._attach_images(conversation, images)

        config = self._build_config(
            system_instruction=system_instruction,
            temperature=temperature,
            json_mode=json_mode,
        )

        def call() -> str:
            response = _get_client().models.generate_content(
                model=self._model,
                contents=conversation,
                config=config,
            )
            text = response.text
            if text is None or not text.strip():
                raise RuntimeError(f"Gemini 응답이 비어있습니다: {response}")
            return text

        return _with_retry(call, label="gemini.generate_content")

    # ---------------------- 내부 변환 ----------------------

    @staticmethod
    def _build_contents(
        messages: list[ChatMessage],
    ) -> tuple[str | None, list[types.Content]]:
        system_parts: list[str] = []
        conversation: list[types.Content] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            elif msg.role == "user":
                conversation.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg.content)],
                    )
                )
            elif msg.role == "assistant":
                conversation.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=msg.content)],
                    )
                )
            else:
                raise ValueError(f"알 수 없는 role: {msg.role!r}")

        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, conversation

    @staticmethod
    def _attach_images(
        conversation: list[types.Content], images: list[bytes]
    ) -> None:
        if not conversation or conversation[-1].role != "user":
            raise ValueError("image 는 가장 최근의 user 메시지와 함께 전달돼야 합니다.")
        last_user = conversation[-1]
        last_user.parts.extend(
            types.Part.from_bytes(data=img, mime_type="image/png") for img in images
        )

    @staticmethod
    def _build_config(
        *,
        system_instruction: str | None,
        temperature: float,
        json_mode: bool,
    ) -> types.GenerateContentConfig:
        kwargs: dict = {"temperature": temperature}
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**kwargs)


# ---------------------- 모듈 레벨 유틸 ----------------------


@lru_cache
def _get_client() -> genai.Client:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY 가 설정되지 않았습니다. .env 를 확인하세요."
        )
    return genai.Client(api_key=settings.gemini_api_key)


def _with_retry(fn: Callable[[], T], *, label: str) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — 외부 API 호출 실패를 한 곳에서 흡수
            last_exc = exc
            if attempt == _MAX_ATTEMPTS:
                break
            delay = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            logger.warning(
                "%s 실패(attempt=%d/%d, delay=%.1fs): %s",
                label,
                attempt,
                _MAX_ATTEMPTS,
                delay,
                exc,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
