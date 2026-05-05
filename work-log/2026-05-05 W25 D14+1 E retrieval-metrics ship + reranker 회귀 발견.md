# 2026-05-05 W25 D14+1 — E 측정 인프라 ship + ⚠️ reranker 정량 회귀 발견

> 검색 성능 향상 plan §S1 (P0) 측정 인프라 정착. baseline 측정 결과 **S2 reranker (87f5a4b) 의 정량 회귀 확인** — 정직 인정 + 다음 액션 제안.

---

## 0. 한 줄 요약

E (S1 측정 인프라) ship 완료 — Recall@10 / MRR / nDCG@10 + reranker on/off 비교 도구 (`evals/eval_retrieval_metrics.py`).
**baseline 측정 결과: S2 reranker (87f5a4b) ON 시 검색 품질 -50% 회귀** — 가설: HF sentence-similarity pipeline 이 cross-encoder 미작동.
정직 인정 + 다음 액션 제안. **378 tests OK (+16건, 회귀 0)**.

---

## 1. ship 결과 (E — S1 측정 인프라)

### 1.1 신규 모듈

| 파일 | 역할 |
|---|---|
| `api/app/services/retrieval_metrics.py` | Recall@K / MRR / nDCG@K 계산 (binary relevance, stdlib 만) |
| `api/tests/test_retrieval_metrics.py` | 16건 — perfect/partial/edge case 검증 |
| `evals/eval_retrieval_metrics.py` | 골든셋 → search 호출 → 메트릭 산출. reranker on/off 비교 (단일 process, ENV 토글) |
| `Makefile` `eval-retrieval` target | `make eval-retrieval [COMPARE=1]` entry-point |

### 1.2 골든셋 활용

기존 자산 `evals/golden_v0.4_sonata.csv` (sonata catalog 10건, query + expected_chunk_idx_hints) 그대로 활용.
chunk-level relevance 기반 정확한 Recall@10 / MRR / nDCG 측정 가능.

### 1.3 단위 테스트 회귀

378 tests OK (이전 362 → +16건, 0 fail).

---

## 2. ⚠️ baseline 측정 결과 — reranker 정량 회귀

### 2.1 집계 평균 (sonata 10건, doc-scope `?doc_id=...`)

| 메트릭 | reranker OFF | reranker ON | Δ |
|---|---:|---:|---:|
| **Recall@10** | **0.9000** | **0.4000** | **-0.5000** |
| **MRR** | **0.7167** | **0.1192** | **-0.5975** |
| **nDCG@10** | **0.7458** | **0.1856** | **-0.5602** |
| latency (avg) | 489ms | **9270ms** | +8781ms |

→ **모든 메트릭에서 회귀**. "+8~12pp" 추정의 **정확히 반대 방향**.

### 2.2 패턴 분석 — reranker ON top-5 가 query 무관

| query | OFF top-5 | ON top-5 |
|---|---|---|
| 시트 종류 | **47, 46, 44**, 42, 53 | 53, 12, 6, 45, 43 |
| 트림 종류 | 65, 22, 23, 47, 56 | 53, **45, 43**, 10, 38 |
| 안전 기능 | **30, 27, 26**, 61, 29 | **12, 53, 6**, 16, 45 |
| 디스플레이 | 62, **5**, 39, **4**, 43 | **6, 16**, 43, 10, 45 |
| 외장 색상 | 45, 46, 96, 17, 15 | 53, 12, **6, 45**, 16 |
| 블루링크 | **62, 61**, 17, **60**, 30 | **6, 12, 16, 45**, 43 |

**ON 시 chunks 12 / 6 / 16 / 45 / 43 / 53 이 거의 모든 query 의 top-5 에 반복 등장** — query-specific 변별력 X.

### 2.3 가설 — HF sentence-similarity pipeline 이 cross-encoder 미작동

증거:
1. ON top-5 가 query 무관하게 동일 chunks → query-independent ranking
2. 정상 cross-encoder 라면 query 마다 score 달라야 함
3. HF Inference API `sentence-similarity` pipeline 은 sentence-transformers 모델용 — 일반 임베딩 cosine similarity 반환 가능
4. BGE-reranker-v2-m3 는 cross-encoder (`AutoModelForSequenceClassification`) — `sentence-similarity` pipeline 이 cross-encoder 모드로 동작 안 할 가능성

추가 증거:
- W25 D14 핸드오프 §6.3 "RAGAS auto 한계" 의 RAGAS LLMContextPrecisionWithoutReference 가 0점 일관 → 본 reranker 도 비슷한 false negative 가능성

---

## 3. 정직 인정 (CLAUDE.md 비판적 한계 원칙)

### 3.1 1차 sprint 의 가정 오류

W25 D14+1 S2 (commit 87f5a4b) ship 시:
- **smoke 결과 정성적으로 좋아 보임** — chunk[38] p.19 매칭 (시트 본문)
- 단, 골든셋 정답은 chunk 44/46/47 (Colors 표) → reranker 와 다른 chunk 선택
- 정성 vs 정량 어긋남 — **정량 검증 없이 ship 했던 것이 본 sprint (E) 에서 발견**

### 3.2 비판적 재검토 미흡 항목

W25 D14+1 S2 ship 직전 비판적 재검토 3회 했지만:
- "+8~12pp planner 추정 — 한국어 도메인 정량 검증 X" 인정했음
- 그러나 **HF API endpoint pipeline 의 정확성은 검증 안 했음**
- smoke 1회 (정성) 만으로 ship → 정량 baseline 없이 결정

### 3.3 사용자 영향

- **운영 영향 0** — `JETRAG_RERANKER_ENABLED` default `false`, 사용자가 활성 안 했으면 영향 없음
- **개발 영향**: S2 ship 의 효과가 사실상 negative → 본 sprint (E) 측정 인프라가 제때 발견

---

## 4. 다음 액션 후보

### 4.1 P0 (즉시) — reranker endpoint 검증

| 후보 | 내용 | 작업량 |
|---|---|---|
| **A** | HF API endpoint pipeline 변경 시도 — `text-classification` 또는 직접 raw POST `https://api-inference.huggingface.co/models/BAAI/bge-reranker-v2-m3` body=`{"inputs": [[query, passage], ...]}` | 中 (~1시간) |
| **B** | FlagEmbedding 라이브러리 in-process 도입 — 검증된 cross-encoder, but 의존성 大 (torch + 568MB 모델) | 中~大 (사용자 승인 필요) |
| **C** | Cohere Rerank API 또는 Voyage AI rerank — 비용 발생 ($1/1k searches) | 中 (사용자 승인 필요) |
| **D** | reranker 폐기 — `JETRAG_RERANKER_ENABLED` default false 유지, 코드는 보존 | 下 (commit 0) |

### 4.2 권고 — A (endpoint 변경) → 회복 안 되면 D (보존)

A 가 가성비 최고. 의존성 0, 코드 변경 small, ~1시간 검증 가능.
A 실패 시 D 채택 (코드 보존, 활성 안 함, 다른 후보로 우선 이전).

### 4.3 다른 후보 (보류)

핸드오프 §5.1 의 S3 (HyDE), S4 (doc-level embedding), S5 (PGroonga 정밀화) — 측정 인프라 (본 sprint) 위에서 비교 가능. 단 reranker 결정 후.

---

## 5. 환경 변수 / 사용 가이드

### 5.1 측정 실행

```bash
# 단일 mode (현재 ENV)
make eval-retrieval

# reranker on/off 비교
make eval-retrieval COMPARE=1
```

산출: `work-log/<오늘> retrieval-metrics.md` — 집계 + 상세 markdown.

### 5.2 reranker 권고 — **현재는 끄기**

```bash
# .env 또는 셸
unset JETRAG_RERANKER_ENABLED
# 또는 export JETRAG_RERANKER_ENABLED=false
```

본 sprint (E) baseline 결과 기준. endpoint 검증 (P0-A) 후 재평가.

---

## 6. 한계 (정직 인정)

### 6.1 측정 자체의 한계

- 골든셋 N=10 (sonata 단일 doc) — 다양성 부족
- 골든셋 정답 chunks 가 narrow (예: "시트 종류" → chunk 44/46/47 만 정답) — chunk 38 (시트 본문) 도 사용자에겐 적합할 수 있음
- 다른 docs (b218e8a1 데이터센터, 의료 빅데이터) 골든셋 미존재
- doc-scope 검색 (`?doc_id=...`) 만 측정 — 일반 검색 (multi-doc) 의 reranker 효과는 다를 수 있음

### 6.2 가설 검증 안 됨

- "HF sentence-similarity pipeline 이 cross-encoder 미작동" 은 **가설**
- 증거: top-5 query-independent. 단 다른 원인 가능성도 존재
- HF API 직접 호출 시 response 분석 필요 (P0-A 작업의 일부)

### 6.3 reranker 의 본질 한계 가능성

- BGE-reranker 가 **표 / 카탈로그 형식 chunk** 에 약할 수 있음 (자연어 query 와 표 chunk 의 cross-encoder 매칭 한계)
- sonata catalog 가 표/색상/옵션 위주 → 일반 자연어 docs (데이터센터, 의료) 에선 다른 결과 가능
- 일반 doc 골든셋 추가 후 재측정 필요

---

## 7. 메모리 / CLAUDE.md 갱신 제안

본 finding 은 향후 sprint 패턴에 영향:
1. **smoke 정성 vs 정량 measurement 어긋남 가능** — 정량 baseline 없이 ship 위험 → CLAUDE.md "정량 검증 없이 활성 default 변경 금지" 추가 검토
2. **HF Inference API pipeline 검증 필수** — 새 모델 도입 시 endpoint 응답 schema 직접 확인. sentence-similarity != cross-encoder 가 아닌 모델 특성 함정

---

## 8. 한 문장 요약

W25 D14+1 E — 측정 인프라 ship 성공 (Recall@10 / MRR / nDCG, sonata 10건 baseline 측정).
**S2 reranker 정량 회귀 (-50%, query-independent ranking) 발견** — HF sentence-similarity pipeline 가설.
정직 인정 + P0-A (endpoint 변경) 또는 P0-D (보존) 권고. 운영 영향 0 (default off 유지).
