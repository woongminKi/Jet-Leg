"""W25 D14+1 D4 — HyDE (Hypothetical Document Embedding).

흐름:
1. 사용자 query 를 Gemini 에 전달 → query 에 답할 만한 가상 문단 1개 생성
2. (query + hypothetical_doc) concat → BGE-M3 임베딩
3. 그 임베딩으로 dense path 검색

장점: 짧은 키워드 query → 긴 자연어 doc 매칭이 더 정확해짐.
단점: latency +1~2초 (Gemini 호출). cache 필수.

opt-in ENV: `JETRAG_HYDE_ENABLED=true` (default false).
실패 시 원본 query 임베딩으로 fallback (silent degradation 회피 — query_parsed 에 표기).
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict

from app.adapters.impl.gemini_llm import GeminiLLMProvider
from app.adapters.llm import ChatMessage

logger = logging.getLogger(__name__)

_HYDE_PROMPT = """다음 검색 query 에 답할 만한 한국어 본문 1문단 (3~5 문장) 을 작성해주세요.

[제약]
- 한국어로만 작성 (영어 단어 X)
- 사실 추정 가능한 자연스러운 본문 형태 (실제 문서에 등장할 만한 표현)
- 본문만 출력 (다른 설명·따옴표·라벨 X)

[query]
{query}

[가상 본문 1문단]"""

# query → hypothetical doc cache (LRU). 같은 query 반복 호출 시 Gemini 호출 0.
_CACHE_MAXSIZE = 256
_cache: OrderedDict[str, str] = OrderedDict()
_cache_lock = threading.Lock()


def generate_hypothetical_doc(
    llm: GeminiLLMProvider, query: str
) -> str:
    """query → 가상 본문 (Gemini). 실패 시 raise.

    Cache hit 시 Gemini 호출 0.
    """
    with _cache_lock:
        cached = _cache.get(query)
        if cached is not None:
            _cache.move_to_end(query)
            return cached

    prompt = _HYDE_PROMPT.format(query=query)
    response = llm.complete(
        [ChatMessage(role="user", content=prompt)],
        temperature=0.3,
    )
    hyp = response.strip()
    # 라벨 / 따옴표 정리
    for prefix in ("가상 본문:", "본문:", "답변:"):
        if hyp.startswith(prefix):
            hyp = hyp[len(prefix):].strip()
    hyp = hyp.strip("'\"`「」『』")

    with _cache_lock:
        _cache[query] = hyp
        while len(_cache) > _CACHE_MAXSIZE:
            _cache.popitem(last=False)
    return hyp


def clear_cache() -> None:
    """테스트 전용 — HyDE LRU 비움."""
    with _cache_lock:
        _cache.clear()
