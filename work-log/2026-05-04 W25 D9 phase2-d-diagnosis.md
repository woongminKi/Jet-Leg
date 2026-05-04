# W25 D9 — Phase 2 차수 D 진단: PGroonga sparse 0건 root cause 식별

> **결론**: **PGroonga 한국어 sparse 가 10/10 QA 에서 0건** 확인. 단, 문제는 PGroonga 미작동이 아니라 (A) 문서 vocabulary 부재 (B) `&@~` query mode 가 multi-token AND 매칭 (C) Mecab 토크나이저 일부 명사 미분해 — 3 분기. **OR query 변환은 즉시 적용 가능 (`소나타 OR 전장` → 2 hits 작동 확인)**.

> 측정 일시: 2026-05-04 21:49 / 환경: 컴퓨터 이동 후 신규 측정 / ragas 미설치 — stdlib only 진단 스크립트 (`evals/run_phase2_d_diagnosis.py`) 사용

---

## 0. 한 줄 결론

W25 D8 핸드오프 §4.1 "차수 D 진단 먼저" 가 **압도적 정당화** — 10 QA × hybrid 호출 모두에서 sparse_hits=0. 단, root cause 는 한 가지가 아니라 3 layer (vocabulary / query mode / 토크나이저). **D-a (query OR 변환, 마이그레이션 0)** 가 가장 빠른 ROI.

---

## 1. 측정 결과 요약

### 1.1 격차 4건 (W25 D7 mini-Ragas precision < 1.00) — 모두 sparse=0

| id | query | expected | sparse hits | dense recall | dense rank |
|---|---|---|---:|---:|---:|
| G-S-001 | 소나타 전장 길이가 얼마나 돼? | [66, 85] | **0** | 1.00 | 2 |
| G-S-005 | 소나타 트림 종류 뭐가 있어? | [39, 43] | **0** | 0.00 | - |
| G-S-006 | 소나타 N Line 특징이 뭐야? | [37, 38] | **0** | 1.00 | 2 |
| G-S-008 | 소나타 디스플레이는 어떤 종류야? | [4, 5] | **0** | 0.50 | 4 |

### 1.2 전체 10 QA — sparse_hits 분포

```
[0, 0, 0, 0, 0, 0, 0, 0, 0, 0]   ← 모두 0
```

- sparse-only 평균 recall: **0.000**
- dense-only 평균 recall: **0.825**
- → RRF fusion 이 **dense rank 만 의존** (sparse 가 모든 chunk 에 0 기여)

### 1.3 dense 단독 측정 (doc_id 스코프)

- 본 진단은 doc_id 명시 (단일 SONATA 스코프) → dense recall 0.825
- W25 D7 mini-Ragas 는 doc_id 미명시 (list mode) → recall 1.000
- 차이 정상 — 동일 baseline 에서 fix 효과 비교 시 본 측정 사용

---

## 2. Root cause 3 layer (직접 SQL 진단)

### 2.1 Layer A — 문서 vocabulary 부재

```
SELECT doc.title FROM documents WHERE id='3b901245...'
→ 'sonata-the-edge_catalog'

SELECT count(*) FROM chunks WHERE doc_id='...' AND text ILIKE '%소나타%'
→ 0 (영문 'Sonata' 만 사용, 한국어 '소나타' 단어 본문에 0 건)
```

**해석**: SONATA 카탈로그 자체가 한국어 단어 "소나타" 를 본문에 거의 안 씀. doc_title 도 영문. 사용자 query "소나타" 와 PGroonga 매칭이 원천 불가능.

**fix 후보**:
- doc_title 을 chunks 본문에 prepend (인덱싱 시점, 재인덱싱 필요)
- query expansion 사전 (소나타 ↔ Sonata) — 마이그레이션 0

### 2.2 Layer B — `&@~` query mode 가 multi-token AND 매칭

```
RPC search_sparse_only_pgroonga 직접 호출 결과:
  q='소나타'         -> 0 hits  (vocab 부재)
  q='Sonata'        -> 3 hits  (영문 매칭)
  q='전장'          -> 2 hits  (단독)
  q='소나타 전장'     -> 0 hits  ← 두 단어 모두 매칭 요구 (AND)
  q='소나타 OR 전장' -> 2 hits  ← OR 작동 확인
  q='디스플레이'      -> 5 hits  (단독)
  q='소나타 디스플레이' -> 0 hits  (AND)
  q='Sonata 디스플레이' -> 0 hits  (AND)
```

**해석**: PGroonga `&@~` query mode 는 query 의 모든 토큰이 같은 chunk 에 존재해야 매칭. 사용자 자연어 query (3~5 단어) 에서 한 단어만 vocab 부재여도 전체 0.

**fix 후보 (즉시 적용 가능)**:
- search.py 에서 query 를 공백 split → ` OR ` join → PGroonga 에 전달
- 마이그레이션 0, 재인덱싱 0
- 검증: `소나타 OR 전장` → 2 hits 직접 확인

### 2.3 Layer C — Mecab 토크나이저 일부 명사 미분해

```
격차 4건 query 의 단일 단어 sparse hits:
  G-S-001: 소나타=0, 전장=2, 길이=0
  G-S-005: 소나타=0, 트림=11, 종류=0
  G-S-006: 소나타=0, N Line=32, 특징=0
  G-S-008: 소나타=0, 디스플레이=6, 종류=0
```

**해석**: "종류", "특징", "길이" — 일반 명사임에도 0 hits. chunks 본문에 분명히 등장하는 단어인데 PGroonga Mecab 가 다른 토큰으로 분해 또는 사전에 없음.

**fix 후보 (시간 비용 큼)**:
- Mecab 한국어 사전 강화 (mecab-ko-dic 추가)
- PGroonga normalizer 변경 (`NormalizerNFKC100`)
- B 보완책 — 본격 검토 시 별도 sprint

---

## 3. 차수 D 분기 결정

본 진단으로 차수 D 를 3 sub-차수로 세분화:

| 차수 | 이름 | 비용 | 효과 예상 | ROI |
|---|---|---|---|---|
| **D-a** | **query OR 변환 (런타임)** | search.py 5줄 + 단위테스트 | 4건 격차 중 일부 회복 (vocab 있는 단어로 sparse 매칭) | **★★★** |
| D-b | doc_title prepend (인덱싱) | chunk.py + 재인덱싱 | "소나타" vocab 부재 해결 | ★★ |
| D-c | Mecab 사전 강화 | 마이그레이션 + extension 빌드 | "종류/특징" 같은 일반 명사 매칭 | ★ |

### 권고 — D-a 즉시 진입 + 측정

이유:
1. **마이그레이션 0** — search.py 만 변경, ship 즉시 검증
2. **본 진단 스크립트로 효과 정량화** (`evals/run_phase2_d_diagnosis.py` ragas 무관)
3. 측정 결과 따라 D-b/D-c 추가 검토 또는 차수 B (chunk 분리) 로 분기

D-a fix 후 기대치:
- "전장 OR 길이" 매칭으로 G-S-001 sparse hits 회복 → RRF dense+sparse 합산으로 first_hit_rank 1 가능성
- "디스플레이 OR 종류" 로 G-S-008 sparse hits 회복

---

## 4. D-a sprint 진입 명세 (W25 D10 후보)

### 변경
- `api/app/routers/search.py` `_to_pgroonga_query(q: str) -> str` 헬퍼 신설
  - 공백 split → 빈 토큰 제외 → ` OR ` join
  - PGroonga query expression escape (예약어 회피)
  - 단일 토큰은 그대로 (OR 불필요)
- RPC 호출 4 곳 (`search_hybrid_rrf` / `search_sparse_only` / `search_sparse_only_pgroonga` / split RPC) 모두 `_to_pgroonga_query(clean_q)` 적용

### 회귀 보호
- 단위 테스트 — `_to_pgroonga_query` ("소나타 전장" → "소나타 OR 전장", "소나타" → "소나타", " 소나타  전장 " → "소나타 OR 전장", "" → "" 등)
- 단위 테스트 회귀 0 (현재 287)

### 측정
```
python3 evals/run_phase2_d_diagnosis.py --output "work-log/2026-05-04 W25 D10 phase2-d-a-result.md"
```

기대치 (분기):
- sparse-only 평균 recall 0.000 → 0.3~0.6
- hybrid first_hit_rank 4건 격차 case 개선 (rank 4→2 등)
- 부작용 없음 (RRF 가 둘을 합산 — sparse 추가는 ranking 개선만)

### 위험
- PGroonga query expression 의 OR 우선순위 / escape 처리 — 안전한 토큰만 join, 특수문자 strip
- 너무 많은 OR → sparse hits 폭증 → noise 증가 가능 → top_k cap 으로 자연 보호

### 롤백 조건
- D-a 측정 후 **dense recall 또는 hybrid first_hit_rank 가 악화** 시 롤백
- 본 진단 스크립트 재측정 + W25 D7 mini-Ragas 재측정 (ragas 설치 후) 으로 종합 판정

---

## 5. 변경된 파일 (본 진단 sprint)

- `evals/run_phase2_d_diagnosis.py` — 신규 stdlib only 진단 스크립트 (10 QA × 3 mode 측정)
- `work-log/2026-05-04 W25 D9 phase2-d-diagnosis.md` — 본 문서

회귀 0 — search.py 변경 0 / 마이그레이션 0 / 단위 테스트 287 OK 유지.

---

## 6. 학습

1. **mini-Ragas Phase 1 (W25 D7) → 차수 D 진단 (W25 D9) 의 신호 정확도** — D7 격차 4건 (precision 0.5/0.05/0.5/0.25) 가 정확히 sparse=0 case 와 일치. 정량 도구 → 정량 진단 → fix 분기의 chain 작동.

2. **"PGroonga 미작동" 가설은 부분적 — 진짜 원인은 3 layer**. 단일 가설로 진입하지 않고 sub-차수 로 세분화하는 진단이 다음 sprint 정당성 명확화.

3. **`evals/run_phase2_d_diagnosis.py` 가 ragas 없이도 정량 진단 도구로 작동** — Phase 2 fix 효과 측정의 즉시 사용 가능 baseline. 새 컴퓨터 환경 의존성 회피.

4. **OR query 변환의 즉시성** — `소나타 OR 전장` → 2 hits 가 직접 검증됨. D-a 의 ship 가능성 매우 높음.

---

## 7. 다음 sprint 후보 (D10)

1. **D-a — query OR 변환 ship + 측정** (P1, 즉시 진입)
2. D-b — doc_title chunks prepend + 재인덱싱 (P2, D-a 효과 미달 시)
3. D-c — Mecab 사전 강화 (P3, 별도 sprint)
4. B — chunk 분리 정책 (P2, D 차수 효과 측정 후 병행 검토)
5. C — section_title heading boost (P3, B 와 병행 가능)
