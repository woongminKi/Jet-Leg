"""W25 D9 — Phase 2 차수 D 진단: PGroonga 한국어 sparse 0건 케이스 식별.

목적
----
W25 D7 mini-Ragas 측정에서 4건 격차 (G-S-001/005/006/008, Precision < 1.00) 의
근본 원인이 "PGroonga 한국어 sparse 매칭이 0건이라 dense 단독 ranking 만 의존" 인지 검증.

W25 D8 핸드오프 권고:
> 차수 (D) PGroonga 회복 을 먼저 진단 — sparse_hits 로그 분석 (4건 격차 케이스에서
> sparse 가 0인지 확인)

본 스크립트는 ragas/datasets 의존성 없이 stdlib 만으로 동작 (W25 D7 의 run_ragas.py 와
달리 LLM judge 불필요 — 단순 hit 카운트 + retrieved_idx 추출).

측정 항목
---------
각 QA 에 대해 mode=hybrid · dense · sparse 3종 호출:
- query_parsed.dense_hits / sparse_hits / fused
- retrieved_idx (SONATA chunks 만, top_k 단위)
- expected_idx hit 여부 (recall) + 첫 hit rank (precision)

결과 markdown:
- sparse_hits=0 케이스 식별 (PGroonga 토크나이저 0건 매칭)
- mode 별 recall/precision 비교 (dense 단독 vs sparse 단독 vs hybrid)
- D 차수 본격 fix 진입 여부 결정 신호

사용
----
    cd api && uv run python ../evals/run_phase2_d_diagnosis.py
    # 또는
    python3 evals/run_phase2_d_diagnosis.py --output "work-log/2026-05-04 W25 D9 phase2-d-diagnosis.md"

전제
----
- `uvicorn` 8000 포트 가동 + SUPABASE 환경 유효
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
from pathlib import Path
from typing import Any

_SONATA_DOC_ID = "3b901245-598a-4ed5-b490-632bc39f600d"
_SEARCH_BASE = "http://localhost:8000"
_DEFAULT_TOP_K = 10
_MODES = ("hybrid", "dense", "sparse")

_EVALS_DIR = Path(__file__).resolve().parent
_DEFAULT_CSV = _EVALS_DIR / "golden_v0.4_sonata.csv"


def _parse_int_list(raw: str) -> list[int]:
    if not raw or not raw.strip():
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _load_golden(csv_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["expected_chunk_idx_hints"] = _parse_int_list(
                r.get("expected_chunk_idx_hints", "")
            )
            rows.append(r)
    return rows


def _fetch_search(q: str, top_k: int, doc_id: str, mode: str) -> dict[str, Any]:
    params = {"q": q, "limit": str(top_k), "mode": mode, "doc_id": doc_id}
    url = f"{_SEARCH_BASE}/search?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def _retrieved_idxs(resp: dict[str, Any], target_doc_id: str) -> list[int]:
    out: list[int] = []
    for item in resp.get("items") or []:
        if item.get("doc_id") != target_doc_id:
            continue
        for ch in item.get("matched_chunks") or []:
            out.append(int(ch.get("chunk_idx", -1)))
    return out


def _recall(retrieved: list[int], expected: list[int]) -> float:
    if not expected:
        return 1.0
    s = set(retrieved)
    return sum(1 for i in expected if i in s) / len(expected)


def _first_hit_rank(retrieved: list[int], expected: list[int]) -> int | None:
    s = set(expected)
    for rank, idx in enumerate(retrieved, start=1):
        if idx in s:
            return rank
    return None


def _run_one(qa: dict[str, Any], top_k: int, doc_id: str) -> dict[str, Any]:
    out = {
        "id": qa["id"],
        "query": qa["query"],
        "expected": qa["expected_chunk_idx_hints"],
        "by_mode": {},
    }
    for mode in _MODES:
        start = time.monotonic()
        try:
            resp = _fetch_search(qa["query"], top_k=top_k, doc_id=doc_id, mode=mode)
        except Exception as exc:  # noqa: BLE001
            out["by_mode"][mode] = {"error": str(exc)}
            continue
        took_ms = int((time.monotonic() - start) * 1000)
        retrieved = _retrieved_idxs(resp, doc_id)
        qp = resp.get("query_parsed") or {}
        out["by_mode"][mode] = {
            "dense_hits": qp.get("dense_hits"),
            "sparse_hits": qp.get("sparse_hits"),
            "fused": qp.get("fused"),
            "retrieved": retrieved[:top_k],
            "recall": _recall(retrieved[:top_k], qa["expected_chunk_idx_hints"]),
            "first_hit_rank": _first_hit_rank(
                retrieved[:top_k], qa["expected_chunk_idx_hints"]
            ),
            "took_ms": took_ms,
        }
    return out


def _format_markdown(results: list[dict[str, Any]], top_k: int) -> str:
    lines: list[str] = []
    lines.append(f"# W25 D9 — Phase 2 차수 D 진단: PGroonga sparse 0건 케이스")
    lines.append("")
    lines.append(f"- 측정 일시: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 평가 데이터셋: `evals/golden_v0.4_sonata.csv` (10 QA)")
    lines.append(f"- doc_id (SONATA): `{_SONATA_DOC_ID}`")
    lines.append(f"- 측정 모드: hybrid · dense · sparse · top_k={top_k}")
    lines.append("")

    sparse_zero = [
        r for r in results
        if r["by_mode"].get("sparse", {}).get("sparse_hits") == 0
    ]
    sparse_low = [
        r for r in results
        if 0 < (r["by_mode"].get("sparse", {}).get("sparse_hits") or 0) <= 3
    ]

    lines.append("## 0. 한 줄 결론")
    lines.append("")
    if len(sparse_zero) >= 5:
        verdict = "**PGroonga 한국어 토크나이저 사실상 미작동** — 차수 D 본격 fix 진입 정당화."
    elif len(sparse_zero) >= 1:
        verdict = (
            f"**부분 미작동** — {len(sparse_zero)}/{len(results)} QA 에서 sparse=0. "
            "차수 D 진단 + B 또는 C 분기 검토."
        )
    else:
        verdict = "PGroonga 정상 — 격차 4건 원인은 sparse 0 이 아님. 차수 B/C 분기."
    lines.append(verdict)
    lines.append("")

    lines.append("## 1. mode 별 sparse_hits 분포")
    lines.append("")
    lines.append("| id | query | expected | hybrid sparse_hits | sparse-only retrieved (top10) | sparse recall | first_hit_rank |")
    lines.append("|---|---|---|---:|---|---:|---:|")
    for r in results:
        h = r["by_mode"].get("hybrid", {})
        s = r["by_mode"].get("sparse", {})
        sh = h.get("sparse_hits")
        sret = s.get("retrieved") or []
        srec = s.get("recall")
        sfhr = s.get("first_hit_rank")
        lines.append(
            f"| {r['id']} | `{r['query']}` | {r['expected']} | "
            f"{sh if sh is not None else '-'} | "
            f"{', '.join(str(i) for i in sret) if sret else '(0건)'} | "
            f"{srec:.2f} | {sfhr if sfhr is not None else '-'} |"
        )
    lines.append("")

    lines.append("## 2. mode 별 정량 비교 (recall / first_hit_rank)")
    lines.append("")
    lines.append("| id | hybrid recall | hybrid rank | dense recall | dense rank | sparse recall | sparse rank |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in results:
        cells = [r["id"]]
        for m in _MODES:
            mr = r["by_mode"].get(m, {})
            rec = mr.get("recall")
            fhr = mr.get("first_hit_rank")
            cells.append(f"{rec:.2f}" if rec is not None else "-")
            cells.append(str(fhr) if fhr is not None else "-")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## 3. 4건 격차 case 진단 (W25 D7 mini-Ragas 격차)")
    lines.append("")
    target_ids = ("G-S-001", "G-S-005", "G-S-006", "G-S-008")
    for r in results:
        if r["id"] not in target_ids:
            continue
        s = r["by_mode"].get("sparse", {})
        d = r["by_mode"].get("dense", {})
        h = r["by_mode"].get("hybrid", {})
        lines.append(f"### {r['id']} `{r['query']}`")
        lines.append("")
        lines.append(f"- expected: {r['expected']}")
        lines.append(
            f"- sparse: hits={s.get('sparse_hits')} retrieved={s.get('retrieved')} "
            f"recall={s.get('recall'):.2f} first_hit_rank={s.get('first_hit_rank')}"
        )
        lines.append(
            f"- dense: hits={d.get('dense_hits')} retrieved={d.get('retrieved')[:5]}... "
            f"recall={d.get('recall'):.2f} first_hit_rank={d.get('first_hit_rank')}"
        )
        lines.append(
            f"- hybrid: dense_hits={h.get('dense_hits')} sparse_hits={h.get('sparse_hits')} "
            f"first_hit_rank={h.get('first_hit_rank')}"
        )
        # 진단
        sh = s.get("sparse_hits") or 0
        if sh == 0:
            lines.append("- **진단**: PGroonga 0건 매칭 — 한국어 토크나이저 작동 안 함 (D 차수 신호)")
        elif s.get("recall") == 0:
            lines.append("- **진단**: sparse 매칭은 있지만 정답 청크 못 잡음 — sparse 단독 부족")
        else:
            lines.append("- **진단**: sparse 가 정답 청크를 잡음 — RRF 합산 정책 또는 dense 가산 효과 점검")
        lines.append("")

    # 종합 분석
    lines.append("## 4. 종합 분석")
    lines.append("")
    sparse_hits_list = [
        r["by_mode"].get("hybrid", {}).get("sparse_hits") or 0
        for r in results
    ]
    sparse_recall_list = [
        r["by_mode"].get("sparse", {}).get("recall") or 0
        for r in results
    ]
    dense_recall_list = [
        r["by_mode"].get("dense", {}).get("recall") or 0
        for r in results
    ]
    lines.append(f"- sparse_hits 분포 (hybrid 호출 시): {sparse_hits_list}")
    lines.append(
        f"- sparse_hits=0 케이스: {len(sparse_zero)}/{len(results)} "
        f"({[r['id'] for r in sparse_zero]})"
    )
    lines.append(
        f"- sparse_hits 1~3 케이스: {len(sparse_low)}/{len(results)} "
        f"({[r['id'] for r in sparse_low]})"
    )
    if sparse_recall_list:
        lines.append(f"- 평균 sparse-only recall: {statistics.mean(sparse_recall_list):.3f}")
        lines.append(f"- 평균 dense-only recall: {statistics.mean(dense_recall_list):.3f}")
    lines.append("")

    lines.append("## 5. 차수 결정 신호")
    lines.append("")
    sparse_zero_count = len(sparse_zero)
    if sparse_zero_count >= 5:
        lines.append(
            "- **차수 D (PGroonga 한국어 sparse 회복) 진입 정당화** — "
            f"{sparse_zero_count}/10 QA 에서 sparse=0. Mecab 토크나이저 / 인덱스 재생성 / "
            "한국어 형태소 룰 점검 필요."
        )
    elif sparse_zero_count >= 1:
        lines.append(
            f"- **부분 미작동** — {sparse_zero_count}/10 sparse=0. "
            "차수 D 진단 부분 정당화. 격차 4건 중 sparse=0 비율 따라 분기."
        )
    else:
        lines.append(
            "- PGroonga 정상 — 격차 4건 원인은 sparse 부재가 아님. "
            "차수 B (chunk 분리) 또는 C (heading boost) 진입."
        )
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top_k", type=int, default=_DEFAULT_TOP_K)
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV)
    parser.add_argument("--doc_id", default=_SONATA_DOC_ID)
    parser.add_argument("--output", "-o", type=Path, default=None)
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"[FAIL] {args.csv}", file=sys.stderr)
        return 1

    qas = _load_golden(args.csv)
    print(f"[INFO] {len(qas)} QA × 3 mode 측정 시작...", file=sys.stderr)

    results = []
    for qa in qas:
        r = _run_one(qa, top_k=args.top_k, doc_id=args.doc_id)
        sh = r["by_mode"].get("sparse", {}).get("sparse_hits")
        srec = r["by_mode"].get("sparse", {}).get("recall") or 0.0
        print(
            f"[OK] {r['id']} sparse_hits={sh} sparse_recall={srec:.2f}",
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
