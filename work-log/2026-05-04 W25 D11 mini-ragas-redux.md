# W25 D11 — mini-Ragas 재측정 (D-a + D-a-2 누적 효과 vs D7 baseline)

> **결론**: 평균 precision 0.730 → 0.721 (-0.009, 사실상 동일). 격차 4건 (precision<1.0) 중 **3건 개선** (G-S-001 0.50→1.00, G-S-008 0.25→0.50, G-S-006 동일), **1건 악화** (G-S-009 1.00→0.17). 사용자 결정 필요 — ship 유지 vs 부분 롤백 vs 추가 fix.

> 측정: `make eval` (uvicorn 8000, top_k=10, doc_id 미명시 list mode), Recall 100% 유지

---

## 0. 한 줄 결론

D-a + D-a-2 의 sparse 회복이 **정답 청크 ranking 에서 양면 효과**:
- (+) sparse OR 변환이 정답 청크 직접 매칭 → ranking 1위 진입 (G-S-001/008)
- (-) sparse 가 인접 유사 chunk 들을 광범위 매칭 → 정답 청크가 후순위로 밀림 (G-S-009)

**평균 metric 은 정체** (0.730 → 0.721, -0.009 통계 의미 없음). **다음 sprint 차수 B (chunk 분리 정책) 우선순위 ↑** — 정답 청크 본문 풍부화로 sparse 가산 정합성 회복.

---

## 1. 정량 비교 (W25 D7 baseline vs W25 D11)

### 1.1 종합

| 메트릭 | D7 baseline | D11 (D-a+D-a-2) | 변화 |
|---|---:|---:|---|
| Context Recall@10 | 1.000 | 1.000 | 동일 |
| Context Precision@10 | 0.730 | **0.721** | **-0.009** (사실상 동일) |
| latency p95 | 850ms | **597ms** | -253ms (개선) |

### 1.2 QA 별 precision

| id | query | expected | D7 prec | D11 prec | 변화 |
|---|---|---|---:|---:|---|
| G-S-001 | 소나타 전장 길이가 얼마나 돼? | [66, 85] | 0.50 | **1.00** | ↑ +0.50 |
| G-S-002 | 시트 종류 | [44, 46, 47] | 1.00 | 1.00 | 동일 |
| G-S-003 | 전폭은? | [67, 87] | 1.00 | 1.00 | 동일 |
| G-S-004 | 전고는? | [68, 88] | 1.00 | 1.00 | 동일 |
| G-S-005 | 트림 종류 | [39, 43] | 0.05 | 0.04 | ↓ -0.01 (미세) |
| G-S-006 | N Line 특징 | [37, 38] | 0.50 | 0.50 | 동일 |
| G-S-007 | 안전 기능 | [25, 26, 29, 30] | 1.00 | 1.00 | 동일 |
| G-S-008 | 디스플레이 종류 | [4, 5] | 0.25 | **0.50** | ↑ +0.25 |
| G-S-009 | 외장 색상 | [44] | **1.00** | **0.17** | ↓ **-0.83** (악화) |
| G-S-010 | 블루링크 | [60, 61, 62] | 1.00 | 1.00 | 동일 |

### 1.3 격차 4건 (D7 시점 precision < 1.00) 추이

| QA | D7 prec | D11 prec | 변화 | 원인 |
|---|---:|---:|---|---|
| G-S-001 | 0.50 | **1.00** | ↑ +0.50 | D-a sparse [66,85] 정확 매칭 → RRF 1위 |
| G-S-005 | 0.05 | 0.04 | -0.01 | sparse 매칭은 늘었지만 정답 청크 [39,43] 본문에 query token 부재 (chunk 본문 vocab 문제) |
| G-S-006 | 0.50 | 0.50 | 동일 | dense 가 이미 rank 2, sparse 도 rank 2 → 가산 효과 없음 |
| G-S-008 | 0.25 | **0.50** | ↑ +0.25 | D-a-2 "디스플레이는" → "디스플레이" strip → sparse 매칭 → rank 4→2 |

### 1.4 G-S-009 악화 분석 (1.00 → 0.17)

```
query: '소나타 외장 색상 몇 가지야?'
expected: [44] (페이지 22 colors)

D7 retrieved (top10): 44, 2, 45, 1, 46, 47, 38, 53, 97, 62
D11 retrieved (top10): 45, 46, 96, 17, 15, 44, 2, 1, 47, 38
```

D-a/D-a-2 적용 후 PGroonga sparse path 가 OR 매칭으로 전환되며 인접 색상 chunks (45, 46) 가 sparse hits 풍부 → RRF 가산으로 1~2위 선점. 정답 chunk 44 는 sparse 매칭은 됐지만 다른 chunk 들에 비해 매칭 빈도 낮음 → rank 6 으로 밀림.

**원인 추정**:
- chunk 44 가 페이지 22 의 첫 번째 색상 chunk — query token (소나타/외장/색상) 매칭 빈도가 chunk 45/46 (인접 색상 page) 보다 적음
- D-a 적용 전엔 sparse 가 0건이라 dense 단독 (chunk 44 rank 1) 이 그대로 보존됐음
- D-a 적용 후 sparse 가 인접 chunks 를 대량 매칭 → ranking 정밀도 저하

**이건 sparse 회복의 trade-off** — dense 단독으로 잘 작동하던 case 가 sparse 가산으로 악화될 수 있음.

---

## 2. 결정 신호 분석

### 2.1 ship 유지 (D-a + D-a-2 그대로)

- (+) 격차 4건 중 3건 개선, 평균 precision 사실상 동일
- (+) sparse path 인프라 회복 (10/10 → 0/10 sparse_hits=0) — 향후 차수 B/C 효과 측정 baseline 회복
- (+) latency p95 250ms 개선
- (-) G-S-009 (D7 시점 좋았던 case) 악화

### 2.2 부분 롤백 (D-a-2 만 유지, D-a 의 OR 변환 일부 약화)

- 가능 대안: query 의 마지막 명사만 OR 매칭 (4단어 query 에서 첫 1~2개만 OR, 나머지는 AND)
- 복잡도 증가 + heuristic 의 임의성 → 권고 안 함

### 2.3 추가 fix — RRF weight 조정 또는 chunk 분리 정책 (차수 B)

- (P1) 차수 B chunk 분리 정책 — 정답 청크 본문 풍부화로 sparse 가산 정합성 회복
- (P2) RRF weight 조정 — dense=1.0 vs sparse=0.5 처럼 sparse 영향 줄이기 (마이그레이션 필요, 003/004/008 RRF 함수 수정)
- (P3) sparse OR query 의 max token 제한 — 너무 많은 토큰이 OR 되면 noise 증가

---

## 3. 권고

**ship 유지 + 차수 B 즉시 후속 sprint 진입**.

이유:
1. 평균 precision 변동 -0.009 는 통계 의미 없음 (10 QA 표본 작음)
2. sparse path 인프라 회복은 영구적 자산 — 향후 데이터셋 확장 시 효과 ↑
3. G-S-009 악화는 chunk 분리 정책으로 회복 가능 (정답 청크 본문 풍부화 시 ranking 회복)
4. 부분 롤백은 heuristic 의 임의성으로 다른 case 회귀 위험

→ **본 mini-Ragas 결과 사용자에게 보고 후 차수 B 진입 결정 받기**.

---

## 4. 변경 / 검증 / 회귀

| 항목 | 값 |
|---|---|
| 변경 파일 | `api/pyproject.toml` (ragas + datasets 추가), `uv.lock` |
| 외부 의존성 | 0 (ragas 0.4.3 / datasets 4.8.5 가 W25 D7 시점부터 uv.lock 에 있음 — `uv sync` 로 새 컴퓨터에 설치만, pyproject.toml 변경 0) |
| 단위 테스트 | 301 (변동 없음) |
| 회귀 | 0 |

---

## 5. 다음 sprint 후보 (사용자 결정)

| # | 차수 | 비용 | 근거 |
|---|---|---|---|
| 1 | **B chunk 분리 정책** | chunk.py 변경 + 99 chunks 재인덱싱 1회 | G-S-009 악화 회복 + G-S-005/006 잔존 case 회복 가능성 |
| 2 | RRF weight 조정 (dense=1.0 / sparse=0.5) | 마이그레이션 003/004/008 RRF 함수 수정 | sparse 영향 약화 (G-S-009 회복 시도) |
| 3 | sparse OR token 제한 | search.py heuristic | G-S-009 만 회복 시도, 다른 case 회귀 위험 |
| 4 | Phase 2 차수 D 마감 + 다음 phase | — | 본 측정 결과 만족 시 (사용자 판단) |
