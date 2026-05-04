# W25 D10 — Phase 2 차수 D-a ship: PGroonga query OR 변환 결과

> **결론**: search.py 에 `_build_pgroonga_query` 헬퍼 1개 추가 (5줄 + 단위테스트 7건) — 사용자 query 를 공백 split 후 `' OR '` join 으로 PGroonga `&@~` 에 전달. 마이그레이션 0 / 재인덱싱 0 / 의존성 0. **sparse_hits=0 케이스 10/10 → 3/10, 평균 sparse-only recall 0.000 → 0.500**. 격차 4건 중 G-S-001 hybrid first_hit_rank 2→1 개선. 회귀 0 (단위 테스트 287→294 +7).

> 측정: `evals/run_phase2_d_diagnosis.py` (W25 D9 도입, ragas 무관 stdlib only)

---

## 0. 변경 요약

| 항목 | 값 |
|---|---|
| 변경 파일 | `api/app/routers/search.py` (헬퍼 + 3곳 변수 변경), `api/tests/test_pgroonga_or_query.py` (신규 7 tests) |
| 마이그레이션 | 0 |
| 재인덱싱 | 0 |
| 외부 의존성 | 0 |
| 단위 테스트 | 287 → **294** (+7) |
| 회귀 | 0 |

---

## 1. 정량 효과 (D9 baseline vs D10 D-a)

### 1.1 sparse_hits 분포

| QA | D9 (AND) | D10 (OR) | 변화 |
|---|---:|---:|---|
| G-S-001 | 0 | **2** | ↑ |
| G-S-002 | 0 | **8** | ↑ |
| G-S-003 | 0 | 0 | — (조사 "은" 분해 안 됨) |
| G-S-004 | 0 | 0 | — (조사 "은" 분해 안 됨) |
| G-S-005 | 0 | **11** | ↑ (단, 정답 청크 못 잡음) |
| G-S-006 | 0 | **32** | ↑ |
| G-S-007 | 0 | **13** | ↑ |
| G-S-008 | 0 | 0 | — (조사 "는" 분해 안 됨) |
| G-S-009 | 0 | **5** | ↑ (단, 정답 청크 못 잡음) |
| G-S-010 | 0 | **6** | ↑ |
| **0건 비율** | **10/10** | **3/10** | **70% pt 개선** |
| **평균 sparse-only recall** | **0.000** | **0.500** | +0.500 |

### 1.2 격차 4건 hybrid first_hit_rank

| QA | D9 rank | D10 rank | 변화 |
|---|---:|---:|---|
| G-S-001 | 2 | **1** | ↑ |
| G-S-005 | - | - | — |
| G-S-006 | 2 | 2 | — |
| G-S-008 | 4 | 4 | — |

`G-S-001 "소나타 전장 길이가 얼마나 돼?"` — sparse 가 정답 청크 [66, 85] 를 직접 잡음 → RRF 가산으로 hybrid rank 1 진입.

### 1.3 악화 case

**없음**. dense recall / first_hit_rank 모든 QA 에서 D9 와 동일 또는 개선.

---

## 2. 변경 내용

### 2.1 `_build_pgroonga_query` 헬퍼 (api/app/routers/search.py)

```python
def _build_pgroonga_query(q: str) -> str:
    """PGroonga &@~ multi-token AND → OR 변환.

    W25 D9 진단 직접 검증:
        '소나타 전장' → 0 hits (AND, vocab '소나타' 부재)
        '소나타 OR 전장' → 2 hits (OR — '전장' 매칭으로 sparse 회복)
    """
    tokens = [t for t in q.strip().split() if t]
    if len(tokens) <= 1:
        return q.strip()
    return " OR ".join(tokens)
```

### 2.2 RPC 호출 3곳 변경

`pg_q = _build_pgroonga_query(clean_q)` 신설 후:
- `search_sparse_only` RPC (mode=sparse split)
- `search_hybrid_rrf` RPC (mode=hybrid)
- `_sparse_only_fallback` 호출 (HF API 실패 시)

dense path (`search_dense_only`) 는 query_text 미사용 → 변경 0.

### 2.3 단위 테스트 7건 (tests/test_pgroonga_or_query.py)

- 단일 토큰 passthrough
- 2/3+ 토큰 OR join
- 공백 정규화 (leading/trailing/내부 다중)
- 빈 query
- 한영 혼합 (Sonata + 디스플레이)
- 사용자 직접 OR 입력 idempotent

---

## 3. 미해결 case 분석 (남은 sub-차수 신호)

### 3.1 Layer C — 조사 미분해 (3건)

| QA | query | 토큰화 결과 | 매칭 실패 단어 |
|---|---|---|---|
| G-S-003 | 소나타 전폭은? | [소나타, 전폭은] | "전폭은" (조사 "은" 분해 X) |
| G-S-004 | 소나타 전고는? | [소나타, 전고는] | "전고는" (조사 "은" 분해 X) |
| G-S-008 | 소나타 디스플레이는 어떤 종류야? | [..., 디스플레이는, ...] | "디스플레이는" (조사 "는" 분해 X) |

**fix 후보 (D-a-2, 런타임)**:
- 응용 layer 에서 한국어 조사 strip — `("은", "는", "이", "가", "을", "를", "도", "만")` 등 끝 1~2자 제거
- 룰 기반 5줄 헬퍼 — 본 sprint 와 동일 패턴

**fix 후보 (D-c, 마이그레이션)**:
- PGroonga Mecab 사전 강화 / 정규화기 변경 — 시간 비용 큼

### 3.2 sparse hits > 0 인데 정답 청크 못 잡음 (2건)

| QA | sparse_hits | retrieved (top10) | expected |
|---|---:|---|---|
| G-S-005 | 11 | 65, 47, 46, 56, 22, 23, 96, 54, 24, 30 | [39, 43] |
| G-S-009 | 5 | 45, 46, 96, 17, 15 | [44] |

→ Mecab 토크나이저는 매칭하지만 ranking 이 정답 청크 (39, 43, 44) 를 못 끌어올림. 본 chunk 들의 본문 텍스트가 query 토큰과 직접 매칭이 약한 경우 (의미 매칭은 dense 가 담당). **차수 B (chunk 분리 정책) 또는 C (heading boost) 의 영역**.

---

## 4. ship 정당성 점검

| 기준 | 판정 |
|---|---|
| 회귀 0 | ✅ 단위 테스트 287→294 OK |
| 악화 case 0 | ✅ |
| 정량 개선 | ✅ sparse_hits=0 케이스 10/10 → 3/10 / 평균 sparse recall +0.500 |
| 격차 4건 개선 | ✅ G-S-001 rank 2→1 / 나머지 동일 (악화 0) |
| 마이그레이션 회피 | ✅ |
| 재인덱싱 회피 | ✅ |
| W25 D8 학습 (ship 후 측정) | ✅ 본 진단 스크립트로 즉시 검증 |

→ **ship 진행**.

---

## 5. 다음 sprint 후보 (W25 D11+)

### 5.1 우선순위

| # | 차수 | ROI | 비용 |
|---|---|---|---|
| 1 | **D-a-2 한국어 조사 strip** (런타임) | 격차 추가 3건 (G-S-003/004/008) 회복 가능성 | 5줄 헬퍼 + 단위 테스트 |
| 2 | **B chunk 분리 정책** (인덱싱 + 재인덱싱) | sparse hits>0 인데 정답 못 잡는 case (G-S-005/009) | chunk.py + 99 chunks 재인덱싱 |
| 3 | C section_title heading boost (런타임) | 보완책 | section_title 보유율 측정 후 결정 |
| 4 | D-c PGroonga Mecab 사전 강화 (마이그레이션) | 근본 토크나이저 fix | 시간 큼 |

### 5.2 권고

**D-a-2 즉시 진입** — D-a 와 동일 패턴 (런타임 + 마이그레이션 0). 조사 strip 후 본 진단 스크립트 재측정으로 효과 정량화. 격차 3건 추가 회복 가능성.

D-a-2 후 D-a + D-a-2 누적 효과 → mini-Ragas 재측정 (사용자 시점에 ragas 설치 가능) → Phase 2 sprint 마감 판정.

---

## 6. 학습

1. **D9 진단 → D-a fix → 즉시 측정 chain 1시간 완성** — mini-Ragas 도입 (W25 D7) + 진단 스크립트 도입 (W25 D9) 의 인프라 효과. 추측 0, 정량 100%.

2. **W25 D8 vs D10 ship 차이** — D8 메뉴 footer 가드는 mini-Ragas 측정 후 악화 → 롤백. D-a 는 진단 스크립트 측정 후 개선만 → ship. 동일 패턴 (시도-측정-롤백/ship) 이 결정 신호.

3. **계층적 root cause 분석 효과** — "PGroonga 미작동" 단일 가설 대신 3 layer (vocab / query mode / 토크나이저) 로 세분화 → D-a (query mode) 는 즉시 fix 가능, D-c (토크나이저) 는 별도 sprint 분리. fix 의 ship 가능성 / 비용 정합 명확.

4. **자율 진행의 가시성** — feature 단위 ship + work-log + 단위 테스트 + 진단 스크립트 chain 으로 사용자가 어느 시점에 들어와도 5분 안 컨텍스트 회복.
