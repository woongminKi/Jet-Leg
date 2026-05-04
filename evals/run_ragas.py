"""W25 D7 — Ragas mini 검색 품질 측정 (Phase 1, 검색만).

목적
----
사용자 시나리오: 검색 결과 카드의 "매칭 강도 100%" 가 항상 나오는 점을
사용자가 "이게 진짜 정확한지 의심" → Ragas 로 정량 측정 진입.

본 스크립트는 **검색만** 측정한다 (답변 생성은 v1.5 결정):
    - Context Recall   : 정답 청크가 검색 top-N 안에 있는가
    - Context Precision: 검색 결과의 관련성 순서

설계 근거 (사용자 결정 — W25 D7 sprint 명세)
- Q1 OK   — `uv add ragas datasets` 외부 의존성 승인 (W11~W24 정책 첫 변경)
- Q2 (a)  — mini-Ragas (SONATA 1건 + 10 QA) 즉시 측정
- Q3 (α)  — 검색만 측정 (LLM answer 어댑터 신규 회피)

Ragas 메트릭 사용 방식
- Ragas 의 `context_recall` / `context_precision` 기본 구현은 LLM judge 가 필요해
  무료 티어 (Gemini 1,500 회/일) 부담을 피하기 위해 본 스크립트는
  **rule-based 자체 계산** 으로 둘 다 산출한다 (Ragas 0.4.x 와 동일 정의).
- ground truth 는 사람이 작성한 chunk_idx 힌트 — 그 청크가 retrieved 안에 들어왔는가
  로 binary recall, retrieved 의 첫 hit 순위로 precision 산출.
- 향후 Phase 2 에서 Ragas 의 LLM judge 모드 (Faithfulness 등) 합칠 때 동일 데이터셋
  재사용 — `datasets.Dataset` 호환 schema 유지.

사용
----
    cd api && uv run python ../evals/run_ragas.py --top_k 10
    cd api && uv run python ../evals/run_ragas.py --top_k 10 \\
        --output ../work-log/2026-05-04\\ ragas-mini-result.md

전제
- `uvicorn` 이 8000 포트에서 떠 있어야 함 (`/search` 호출).
- `.env` 의 SUPABASE_* 가 유효해야 함 (정답 청크 본문 fetch 용).
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# Ragas / datasets 는 향후 LLM judge 합치기 위한 schema 호환을 보장하려는 임포트.
# rule-based 계산 자체에는 직접 사용하지 않지만, dependency 가 추가됐다는
# 사실 자체가 본 sprint 의 핵심 변경 — import 실패 시 즉시 설치 가이드 출력.
try:
    from datasets import Dataset  # noqa: F401  — schema 호환 증명용 (사용은 내부 함수)
except ImportError as exc:  # noqa: BLE001
    print(
        "[FAIL] datasets 가 설치되지 않았습니다. `cd api && uv add ragas datasets` 실행 후 재시도.",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# SONATA 카탈로그 doc_id (W25 D7 명세 — 99 chunks, p.1~29)
_SONATA_DOC_ID = "3b901245-598a-4ed5-b490-632bc39f600d"

# /search 엔드포인트 — golden_batch_smoke.py 와 동일 패턴 (uvicorn 8000)
_SEARCH_BASE = "http://localhost:8000"

# Ragas 0.4.x context_precision 정의 — top-K 내 첫 hit 위치를 기반으로 한 (1 / rank).
# 본 스크립트는 multi-ground-truth 를 허용 (한 query 에 정답 청크 여러 개) — 첫 hit rank 사용.
_DEFAULT_TOP_K = 10

# 평가 데이터셋 CSV 경로 — 본 스크립트와 같은 디렉토리.
_EVALS_DIR = Path(__file__).resolve().parent
_DEFAULT_CSV = _EVALS_DIR / "golden_v0.4_sonata.csv"


# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------


def _load_golden(csv_path: Path) -> list[dict[str, Any]]:
    """golden_v0.4_sonata.csv 로드 — 한 행 = 한 QA pair.

    schema:
        id, query, expected_pages, expected_chunk_idx_hints, answer, context

    `expected_chunk_idx_hints` 는 콤마 구분 정수 → list[int].
    `expected_pages` 도 콤마 구분 정수 → list[int] (현재 본 스크립트는 미사용 — 메타).
    """
    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["expected_chunk_idx_hints"] = _parse_int_list(
                r.get("expected_chunk_idx_hints", "")
            )
            r["expected_pages"] = _parse_int_list(r.get("expected_pages", ""))
            rows.append(r)
    return rows


def _parse_int_list(raw: str) -> list[int]:
    """`'66,85'` 또는 `'66, 85'` → `[66, 85]`. 빈 문자열 → `[]`."""
    if not raw or not raw.strip():
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


# ---------------------------------------------------------------------------
# 검색 호출 (uvicorn 가정)
# ---------------------------------------------------------------------------


def _fetch_search(
    q: str, top_k: int, doc_id: str | None = None, mode: str = "hybrid"
) -> dict[str, Any]:
    """`/search?q=...&limit=top_k&mode=hybrid&doc_id=...` 호출.

    doc_id 명시 시 SONATA 단일 doc 스코프 — chunks cap 200 적용 (W25 D5).
    이 단계의 limit 의미는 doc 단위 (1) 가 아니라 matched_chunks 응답 cap 이라
    Phase 1 에서는 doc_id 미명시 (list 모드, top_k doc) 로 측정한다.
    """
    params: dict[str, str] = {"q": q, "limit": str(top_k), "mode": mode}
    if doc_id:
        params["doc_id"] = doc_id
    qs = urllib.parse.urlencode(params)
    url = f"{_SEARCH_BASE}/search?{qs}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def _retrieved_chunk_ids(
    search_resp: dict[str, Any], target_doc_id: str
) -> list[tuple[int, int]]:
    """검색 응답에서 SONATA chunks 만 추출 → `[(global_rank, chunk_idx), ...]`.

    list 모드 응답 schema:
        items: [
            { doc_id, matched_chunks: [{ chunk_idx, ... }, ...], ... }, ...
        ]
    SONATA doc 의 matched_chunks 만 보고 각 chunk 의 (전체 rank, chunk_idx) 쌍 반환.
    rank 은 1-based — Ragas precision 의 (1 / rank) 정의에 맞춤.
    """
    pairs: list[tuple[int, int]] = []
    rank = 0
    for item in search_resp.get("items") or []:
        if item.get("doc_id") != target_doc_id:
            # SONATA 외 doc 은 본 평가 범위 외 — rank 만 흘려보냄 (Ragas precision 정의).
            for _ in item.get("matched_chunks") or []:
                rank += 1
            continue
        for ch in item.get("matched_chunks") or []:
            rank += 1
            pairs.append((rank, int(ch.get("chunk_idx", -1))))
    return pairs


# ---------------------------------------------------------------------------
# Ragas 메트릭 (rule-based, LLM judge 회피)
# ---------------------------------------------------------------------------


def _context_recall(
    retrieved_idxs: Iterable[int], expected_idxs: list[int]
) -> float:
    """Context Recall — 정답 청크가 retrieved 안에 들어왔는가.

    Ragas 0.4.x 정의: |relevant ∩ retrieved| / |relevant|.
    expected_idxs 가 비어있으면 NaN 회피로 1.0 반환 (정의상 분모 0).
    """
    if not expected_idxs:
        return 1.0
    retrieved_set = set(retrieved_idxs)
    hits = sum(1 for idx in expected_idxs if idx in retrieved_set)
    return hits / len(expected_idxs)


def _context_precision(
    retrieved_pairs: list[tuple[int, int]], expected_idxs: list[int]
) -> float:
    """Context Precision — 검색 결과의 관련성 순서.

    Ragas 0.4.x 정의 (간이): top-K 내 첫 relevant hit 의 (1 / rank).
    본 스크립트의 retrieved_pairs 는 [(rank, chunk_idx), ...] 정렬됨.
    None hit → 0.0, 첫 hit @ rank=1 → 1.0, rank=5 → 0.2.
    """
    if not expected_idxs or not retrieved_pairs:
        return 0.0
    expected_set = set(expected_idxs)
    for rank, idx in retrieved_pairs:
        if idx in expected_set:
            return 1.0 / rank
    return 0.0


# ---------------------------------------------------------------------------
# 실행 + 리포트
# ---------------------------------------------------------------------------


def _run_one(
    qa: dict[str, Any], top_k: int, doc_id: str
) -> dict[str, Any]:
    """한 QA 에 대해 /search 호출 → recall/precision 계산."""
    start = time.monotonic()
    try:
        resp = _fetch_search(qa["query"], top_k=top_k, doc_id=doc_id)
    except Exception as exc:  # noqa: BLE001
        return {
            **qa,
            "error": str(exc),
            "recall": None,
            "precision": None,
            "took_ms": int((time.monotonic() - start) * 1000),
        }
    took_ms = int((time.monotonic() - start) * 1000)
    retrieved_pairs = _retrieved_chunk_ids(resp, target_doc_id=doc_id)
    retrieved_idxs = [idx for _, idx in retrieved_pairs]
    recall = _context_recall(retrieved_idxs, qa["expected_chunk_idx_hints"])
    precision = _context_precision(
        retrieved_pairs, qa["expected_chunk_idx_hints"]
    )
    return {
        **qa,
        "recall": recall,
        "precision": precision,
        "took_ms": took_ms,
        "retrieved_idxs": retrieved_idxs,
        "retrieved_count": len(retrieved_pairs),
        "matched_chunk_count_total": resp.get("total"),
    }


def _format_markdown(results: list[dict[str, Any]], top_k: int) -> str:
    """결과 → markdown 리포트 (work-log 에 저장).

    포함 섹션:
        - 헤더 (날짜·top_k·doc_id)
        - 종합 (평균 recall · 평균 precision · p95 latency)
        - QA 별 상세 표
        - 분석 (사용자 의도: 70~90% 기대)
    """
    lines: list[str] = []
    lines.append(f"# W25 D7 — Ragas mini 검색 품질 측정 결과 (top_k={top_k})")
    lines.append("")
    lines.append(f"- 측정 일시: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 평가 데이터셋: `evals/golden_v0.4_sonata.csv` (10 QA)")
    lines.append(f"- doc_id (SONATA): `{_SONATA_DOC_ID}` (99 chunks)")
    lines.append(f"- 메트릭: Context Recall · Context Precision (Ragas 0.4.x 정의 / rule-based)")
    lines.append("")

    successful = [r for r in results if "error" not in r]
    if successful:
        avg_recall = statistics.mean(r["recall"] for r in successful)
        avg_precision = statistics.mean(r["precision"] for r in successful)
        ms_list = [r["took_ms"] for r in successful if r["took_ms"]]
        p95 = sorted(ms_list)[int(len(ms_list) * 0.95)] if ms_list else 0
        lines.append("## 종합")
        lines.append("")
        lines.append(f"- 총 {len(results)} QA — 성공 {len(successful)} / 에러 {len(results) - len(successful)}")
        lines.append(f"- **Context Recall@{top_k} (평균)**: **{avg_recall:.3f}** ({avg_recall*100:.1f}%)")
        lines.append(f"- **Context Precision@{top_k} (평균)**: **{avg_precision:.3f}**")
        if ms_list:
            lines.append(
                f"- latency: avg {statistics.mean(ms_list):.0f}ms · "
                f"p50 {statistics.median(ms_list):.0f}ms · "
                f"p95 {p95:.0f}ms"
            )
        lines.append("")

    lines.append("## QA 별 상세")
    lines.append("")
    lines.append("| id | query | expected_idx | retrieved_idx (top10) | recall | precision | took_ms |")
    lines.append("|---|---|---|---|---:|---:|---:|")
    for r in results:
        if "error" in r:
            lines.append(f"| {r['id']} | `{r['query']}` | {r['expected_chunk_idx_hints']} | err | - | - | - |")
            continue
        retrieved_short = (
            ", ".join(str(i) for i in r["retrieved_idxs"][:10]) or "(없음)"
        )
        lines.append(
            f"| {r['id']} | `{r['query']}` | "
            f"{r['expected_chunk_idx_hints']} | {retrieved_short} | "
            f"{r['recall']:.2f} | {r['precision']:.2f} | {r['took_ms']} |"
        )
    lines.append("")

    lines.append("## 분석")
    lines.append("")
    lines.append("### 사용자 의도 대비")
    lines.append("")
    lines.append("- 사용자 기대: Context Recall 70~90%")
    if successful:
        avg_recall = statistics.mean(r["recall"] for r in successful)
        if avg_recall >= 0.9:
            verdict = "**기대 상회** — 검색 품질 우수"
        elif avg_recall >= 0.7:
            verdict = "**기대 부합** — 검색 품질 양호"
        elif avg_recall >= 0.5:
            verdict = "**기대 미달** — 검색 품질 개선 필요"
        else:
            verdict = "**기대 크게 미달** — 검색 파이프라인 점검 필요"
        lines.append(f"- 측정 결과 ({avg_recall*100:.1f}%): {verdict}")
    lines.append("")
    lines.append("### 특이 케이스")
    lines.append("")
    if successful:
        low_recall = [r for r in successful if r["recall"] < 0.5]
        if low_recall:
            lines.append(f"- Recall < 0.5 (정답 청크 절반 이상 놓친 QA):")
            for r in low_recall:
                lines.append(
                    f"    - `{r['id']}` ({r['query']}) — recall {r['recall']:.2f}, "
                    f"expected={r['expected_chunk_idx_hints']}, retrieved={r['retrieved_idxs'][:5]}..."
                )
        else:
            lines.append("- Recall < 0.5 케이스 없음.")
    lines.append("")

    lines.append("## Phase 2 진입 조건")
    lines.append("")
    lines.append("- 사용자 자료 누적 → 평가 데이터셋 확장 (45 doc / 135 QA 목표)")
    lines.append("- LLM answer 어댑터 도입 결정 시 Ragas Faithfulness / Answer Relevancy / Answer Correctness 추가")
    lines.append("- 본 mini-Ragas 결과 + 사용자 피드백 → Phase 2 우선순위 확정")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ragas mini 검색 품질 측정 (W25 D7 Phase 1)"
    )
    parser.add_argument(
        "--top_k",
        type=int,
        default=_DEFAULT_TOP_K,
        help=f"/search limit (default {_DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=_DEFAULT_CSV,
        help=f"평가 데이터셋 CSV 경로 (default {_DEFAULT_CSV.name})",
    )
    parser.add_argument(
        "--doc_id",
        default=_SONATA_DOC_ID,
        help=f"평가 doc_id (default SONATA={_SONATA_DOC_ID[:8]}...)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="markdown 결과 출력 경로. 미지정 시 stdout.",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"[FAIL] 평가 데이터셋 CSV 가 없습니다: {args.csv}", file=sys.stderr)
        return 1

    qas = _load_golden(args.csv)
    print(f"[INFO] {len(qas)} QA 로드 from {args.csv.name}", file=sys.stderr)
    print(f"[INFO] /search 호출 (top_k={args.top_k}, doc_id={args.doc_id[:8]}...)", file=sys.stderr)

    results: list[dict[str, Any]] = []
    for qa in qas:
        r = _run_one(qa, top_k=args.top_k, doc_id=args.doc_id)
        if "error" in r:
            print(f"[ERROR] {qa['id']} {qa['query']} — {r['error']}", file=sys.stderr)
        else:
            print(
                f"[OK] {qa['id']} recall={r['recall']:.2f} "
                f"precision={r['precision']:.2f} took={r['took_ms']}ms",
                file=sys.stderr,
            )
        results.append(r)

    md = _format_markdown(results, top_k=args.top_k)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(md, encoding="utf-8")
        print(f"[OK] 결과 저장 → {args.output}", file=sys.stderr)
    else:
        print(md)

    successful = [r for r in results if "error" not in r]
    if not successful:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
