"""W25 D14+1 (E) — 검색 retrieval 메트릭 (Recall@K / MRR / nDCG@K).

골든셋 (query → 정답 chunk_idx set) 기반 측정.
정답 라벨 = binary relevance (해당 chunk_idx 가 relevant set 에 있으면 1, 아니면 0).

본 모듈은 list[int] 단순 입력 받아 메트릭만 계산 — 외부 의존성 0.
스크립트 (`evals/eval_retrieval_metrics.py`) 가 search 응답에서 chunk_idx list 추출 후 호출.
"""

from __future__ import annotations

import math
from typing import Iterable


def recall_at_k(
    predicted_chunks: list[int], relevant_chunks: set[int] | Iterable[int], k: int = 10
) -> float:
    """Recall@K — top-K 예측 중 정답 chunks 가 잡힌 비율.

    relevant 가 비어있으면 정의 불가 → 0.0 반환.
    """
    relevant_set = set(relevant_chunks)
    if not relevant_set:
        return 0.0
    top_k = predicted_chunks[:k]
    hits = sum(1 for c in top_k if c in relevant_set)
    return hits / len(relevant_set)


def mrr(
    predicted_chunks: list[int], relevant_chunks: set[int] | Iterable[int], k: int = 10
) -> float:
    """Mean Reciprocal Rank — top-K 내 첫 정답 chunk 의 1/rank.

    top-K 안에 정답 0개면 0.0.
    """
    relevant_set = set(relevant_chunks)
    for i, c in enumerate(predicted_chunks[:k], start=1):
        if c in relevant_set:
            return 1.0 / i
    return 0.0


def ndcg_at_k(
    predicted_chunks: list[int], relevant_chunks: set[int] | Iterable[int], k: int = 10
) -> float:
    """nDCG@K (binary relevance) — DCG / IDCG.

    DCG = Σ (rel_i / log2(i+2)), i=0..k-1.
    IDCG = 정답 chunks 가 모두 top 에 모인 이상적 DCG (cap K).
    relevant 가 비어있으면 0.0.
    """
    relevant_set = set(relevant_chunks)
    if not relevant_set:
        return 0.0
    top_k_rel = [1.0 if c in relevant_set else 0.0 for c in predicted_chunks[:k]]
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(top_k_rel))
    ideal_count = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))
    return dcg / idcg if idcg > 0 else 0.0


def aggregate_metrics(
    per_query_results: list[dict],
) -> dict:
    """per-query 메트릭 list → 평균 집계.

    Args:
        per_query_results: [{"recall_at_10": float, "mrr": float, "ndcg_at_10": float}, ...]
    Returns:
        {"recall_at_10": mean, "mrr": mean, "ndcg_at_10": mean, "n": int}
    """
    if not per_query_results:
        return {"recall_at_10": 0.0, "mrr": 0.0, "ndcg_at_10": 0.0, "n": 0}
    n = len(per_query_results)
    return {
        "recall_at_10": sum(r["recall_at_10"] for r in per_query_results) / n,
        "mrr": sum(r["mrr"] for r in per_query_results) / n,
        "ndcg_at_10": sum(r["ndcg_at_10"] for r in per_query_results) / n,
        "n": n,
    }
