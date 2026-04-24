from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMProvider(Protocol):
    """LLM 텍스트 생성 공급자. Gemini 2.5 Flash(기본) · OpenAI(스텁) · Ollama(v2).

    Vision(이미지 캡셔닝) 은 `VisionCaptioner` 로 분리됨 (DE-19 어댑터 재편).
    여기서 `images` 파라미터는 텍스트 생성 중 맥락 참고용 보조 입력으로만 사용.
    """

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        images: list[bytes] | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str: ...
