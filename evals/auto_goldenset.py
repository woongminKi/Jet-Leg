"""W25 D14+1 D1 — self-supervised 골든셋 자동 생성 (사용자 부담 0).

flow:
1. 적재된 docs (11건) 에서 stratified sampling 으로 chunks 선택 (각 doc N건)
2. 각 chunk → Gemini 한국어 자연어 query 1개 생성 (한국어 강제 prompt)
3. 정답 chunk = 자기 chunk_idx (relevant, weight 1.0)
4. 같은 doc 내 chunks dense_vec 와 cosine ≥ 임계 → acceptable (weight 0.5)
   - BGE-M3 chunks.dense_vec 이미 DB 적재됨 → 추가 임베딩 호출 0
   - QA 의 narrowness 발견 직접 해결

산출: `evals/golden_v0.5_auto.csv`
schema: id, query, doc_id, relevant_chunks, acceptable_chunks, source_chunk_text, source_doc_title

사용:
    cd api && uv run python ../evals/auto_goldenset.py --chunks-per-doc 5 --acceptable-cosine 0.7

비용: 11 docs × 5 chunks × 1 Gemini call ≈ 55 호출 (~$0.05). 시간 ~5~10분.

한국어 강제 prompt — RAGAS auto 의 영어 mix 한계 회피 (W25 D14 §6.3 학습).
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import sys
from pathlib import Path

# api/ 를 import path 에 추가
_API_PATH = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(_API_PATH))

from app.adapters.impl.gemini_llm import GeminiLLMProvider  # noqa: E402
from app.adapters.llm import ChatMessage  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_supabase_client  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

_QUERY_PROMPT = """다음 chunk 의 핵심 정보를 묻는 한국어 자연어 query 1개를 생성해주세요.

[제약]
- 한국어로만 작성 (영어 단어 X)
- 사용자가 검색창에 자연스럽게 입력할 만한 형태 (10~25자, 의문문 또는 명사형 모두 OK)
- chunk 텍스트의 키워드를 그대로 복사하지 말고, 의미를 묻는 형태로 변형
- query 만 출력 (다른 설명·따옴표 X)

[chunk 텍스트]
{chunk_text}

[query]"""


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _parse_pgvector(emb) -> list[float] | None:
    """Supabase pgvector 응답 → list[float]. string 또는 list 둘 다."""
    if emb is None:
        return None
    if isinstance(emb, str):
        try:
            return [float(x) for x in emb.strip("[]").split(",")]
        except ValueError:
            return None
    if isinstance(emb, list):
        return [float(x) for x in emb]
    return None


def _sample_chunks(
    client, doc_id: str, n: int, seed: int = 42
) -> list[dict]:
    """doc 의 모든 chunks 중 stratified sampling — chunk_idx 균등 분포."""
    chunks = (
        client.table("chunks")
        .select("id, chunk_idx, text, dense_vec")
        .eq("doc_id", doc_id)
        .order("chunk_idx")
        .execute()
        .data
        or []
    )
    if not chunks:
        return []
    # 매우 짧은 chunk (50자 미만) 제외 — query 생성 의미 없음
    chunks = [c for c in chunks if len((c.get("text") or "").strip()) >= 50]
    if not chunks:
        return []
    if len(chunks) <= n:
        return chunks
    # stratified — 균등 간격
    step = len(chunks) / n
    indices = [int(step * i + step / 2) for i in range(n)]
    indices = list(dict.fromkeys(indices))[:n]
    return [chunks[i] for i in indices]


def _gemini_generate_query(
    llm: GeminiLLMProvider,
    chunk_text: str,
    *,
    inter_call_sleep: float = 1.0,
    extra_retry: int = 5,
) -> str:
    """chunk text → Gemini 한국어 query 1개.

    503 high demand 대응 — 외부 retry layer 추가 (gemini_llm 의 retry 3회 외).
    inter_call_sleep 초 sleep 으로 rate limit 완화.
    """
    import time

    prompt = _QUERY_PROMPT.format(chunk_text=chunk_text[:1500])
    last_exc: Exception | None = None
    for attempt in range(extra_retry):
        try:
            response = llm.complete(
                [ChatMessage(role="user", content=prompt)],
                temperature=0.4,
            )
            q = response.strip()
            for prefix in ("query:", "쿼리:", "질문:", "Q:"):
                if q.lower().startswith(prefix.lower()):
                    q = q[len(prefix):].strip()
            q = q.strip("'\"`「」『』")
            time.sleep(inter_call_sleep)  # 다음 호출 rate limit 완화
            return q
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            # 503 high demand 일 때 longer backoff
            err_str = str(exc)
            if "503" in err_str or "UNAVAILABLE" in err_str:
                wait = min(30.0, 5.0 * (2 ** attempt))
                logger.warning(
                    "extra retry %d/%d — 503 high demand, %.0fs 대기",
                    attempt + 1, extra_retry, wait,
                )
                time.sleep(wait)
            else:
                raise
    assert last_exc is not None
    raise last_exc


def _find_acceptable_chunks(
    target_chunk: dict, all_doc_chunks: list[dict], cosine_min: float
) -> list[int]:
    """같은 doc 내 chunks 와 cosine 계산 → 임계 이상 chunks (자기 제외)."""
    target_vec = _parse_pgvector(target_chunk.get("dense_vec"))
    if not target_vec or len(target_vec) != 1024:
        return []
    target_idx = target_chunk["chunk_idx"]
    acceptable: list[tuple[int, float]] = []
    for c in all_doc_chunks:
        if c["chunk_idx"] == target_idx:
            continue
        vec = _parse_pgvector(c.get("dense_vec"))
        if not vec or len(vec) != 1024:
            continue
        sim = _cosine(target_vec, vec)
        if sim >= cosine_min:
            acceptable.append((c["chunk_idx"], sim))
    # cosine 내림차순 — top-k 라기보다 임계 이상 모두
    acceptable.sort(key=lambda x: x[1], reverse=True)
    return [idx for idx, _ in acceptable]


def main() -> int:
    parser = argparse.ArgumentParser(description="self-supervised 골든셋 자동 생성")
    parser.add_argument(
        "--chunks-per-doc", type=int, default=5,
        help="각 doc 에서 sampling 할 chunks 수 (default 5)"
    )
    parser.add_argument(
        "--acceptable-cosine", type=float, default=0.7,
        help="acceptable chunks BGE-M3 cosine 임계 (default 0.7)"
    )
    parser.add_argument(
        "--output", type=str,
        default=str(Path(__file__).parent / "golden_v0.5_auto.csv"),
        help="출력 CSV 경로",
    )
    parser.add_argument(
        "--limit-docs", type=int, default=None,
        help="처리할 docs 수 제한 (default 전체)"
    )
    parser.add_argument(
        "--model", type=str, default="gemini-2.5-flash",
        help="Gemini 모델 (default gemini-2.5-flash, 503 시 flash-lite 시도)"
    )
    parser.add_argument(
        "--inter-call-sleep", type=float, default=1.0,
        help="호출 간 sleep 초 (default 1.0)"
    )
    args = parser.parse_args()

    client = get_supabase_client()
    settings = get_settings()

    docs = (
        client.table("documents")
        .select("id, title, doc_type")
        .eq("user_id", settings.default_user_id)
        .is_("deleted_at", "null")
        .order("created_at")
        .execute()
        .data
        or []
    )
    if args.limit_docs:
        docs = docs[: args.limit_docs]
    if not docs:
        print("[ERROR] 적재된 docs 없음", file=sys.stderr)
        return 1
    print(f"[OK] 대상 docs: {len(docs)}건", file=sys.stderr)

    llm = GeminiLLMProvider(model=args.model)
    rows: list[dict] = []
    qid = 0
    random.seed(42)

    for d in docs:
        doc_id = d["id"]
        title = d["title"][:60]
        # 각 doc 의 모든 chunks 1회 fetch (acceptable 비교용 + sampling)
        all_chunks = (
            client.table("chunks")
            .select("id, chunk_idx, text, dense_vec")
            .eq("doc_id", doc_id)
            .order("chunk_idx")
            .execute()
            .data
            or []
        )
        sampled = _sample_chunks(client, doc_id, args.chunks_per_doc)
        if not sampled:
            print(f"  [{doc_id[:8]}] sampling 실패 (chunks 없음 또는 너무 짧음)", file=sys.stderr)
            continue

        for chunk in sampled:
            qid += 1
            try:
                query = _gemini_generate_query(
                    llm, chunk["text"],
                    inter_call_sleep=args.inter_call_sleep,
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"  [G-A-{qid:03d}] {doc_id[:8]} chunk={chunk['chunk_idx']} "
                    f"Gemini 실패: {exc}",
                    file=sys.stderr,
                )
                continue
            acceptable = _find_acceptable_chunks(
                chunk, all_chunks, args.acceptable_cosine
            )
            rows.append(
                {
                    "id": f"G-A-{qid:03d}",
                    "query": query,
                    "doc_id": doc_id,
                    "doc_title": title,
                    "relevant_chunks": str(chunk["chunk_idx"]),
                    "acceptable_chunks": ",".join(map(str, acceptable)),
                    "source_chunk_text": chunk["text"][:200].replace("\n", " "),
                }
            )
            print(
                f"  [G-A-{qid:03d}] {doc_id[:8]} chunk={chunk['chunk_idx']} "
                f"acceptable={len(acceptable)} q={query[:40]!r}",
                file=sys.stderr,
            )

    # CSV 출력
    output = Path(args.output)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id", "query", "doc_id", "doc_title",
                "relevant_chunks", "acceptable_chunks", "source_chunk_text",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[OK] {len(rows)} 건 → {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
