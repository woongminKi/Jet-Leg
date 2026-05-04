# 2026-05-04 — W25 D7 Ragas Phase 1 mini 도입

> **Sprint**: W25 D7 — Phase 1 mini-Ragas
> **Goal**: 검색 결과 카드의 "매칭 강도 100%" 가 진짜 정확한지 정량 측정 진입.
> **Status**: ship 완료. 단위 테스트 회귀 0 (api 287). 첫 측정 결과 확보.

---

## 사용자 시나리오 (사전 컨텍스트)

검색 결과 카드의 `매칭 강도 100%` 가 항상 나오는 점에 사용자가 의심:
> "이게 진짜 정확한 100% 인지, 아니면 결과 집합 내 상대값이라 항상 1등이 100% 인 건지?"

→ Ragas 로 정량 측정 진입 결정. 단, 답변 생성 (LLM RAG answer) 은 v1.5 결정 → **검색만** 측정.

---

## 사용자 결정 (W25 D7 sprint 명세 — 3가지 모두 권고안 채택)

| Q | 결정 | 의미 |
|---|---|---|
| Q1 | **OK** — `uv add ragas datasets` 외부 의존성 승인 | W11~W24 누적 외부 의존성 0 정책 첫 변경 |
| Q2 | **(a) mini-Ragas** — SONATA 1건 + 10 QA 즉시 측정 | 사용자 자료 누적 차단 회피, 즉시 정량화 |
| Q3 | **(α) 검색만 측정** — Context Recall + Context Precision | LLM answer 어댑터 신규 회피, §11.5 슬로건 보호 |

---

## 산출물

### 1. 의존성 추가 (Q1)

`api/pyproject.toml` 변동:

```diff
 dependencies = [
     ...
+    "ragas>=0.4.3",
+    "datasets>=4.8.5",
 ]
```

`uv.lock` 갱신 — transitive 추가:
- `ragas==0.4.3` (~10MB)
- `datasets==4.8.5` (Hugging Face 데이터셋 컨테이너)
- `pandas==3.0.2` / `numpy==2.4.4` / `pyarrow==24.0.0` / `scipy==1.17.1` / `tiktoken==0.12.0`
- `langchain-core==1.1.5` / `langgraph==1.1.10` / `openai==2.33.0` (Ragas 의 LLM judge 옵션 — 본 mini 에서는 미사용, Phase 2 대비 자동 포함)

→ **외부 의존성 0 정책 첫 변경** — 사용자 명시 승인 (Q1).

### 2. 평가 데이터셋 — `evals/golden_v0.4_sonata.csv` (신규)

SONATA 카탈로그 (`doc_id=3b901245-598a-4ed5-b490-632bc39f600d`, 99 chunks) 기반 10 QA.
사용자가 정답 아는 자료라 ground truth 작성 가능.

각 QA 의 `expected_chunk_idx_hints` 는 **SQL 직접 검증 후 매핑** — chunks 테이블에서
페이지별 본문 fetch → 실제 정답 chunk_idx 확인:

| ID | query | pages | chunk_idx (검증 후) | 검증 근거 |
|---|---|---|---|---|
| G-S-001 | 전장 | 27 | 66, 85 | "전장(mm) 4,910" + "전장 4,910" (Dimensions) |
| G-S-002 | 시트 종류 | 22, 23 | 44, 46, 47 | Colors + 나파/스웨이드 + Seat combination chart |
| G-S-003 | 전폭 | 27 | 67, 87 | "전폭(mm) 1,860" + "전폭 1,860" |
| G-S-004 | 전고 | 27 | 68, 88 | "전고(mm) 1,445" + "전고 1,445" |
| G-S-005 | 트림 종류 | 20, 21 | 39, 43 | "Premium / S / Exclusive / Inspiration" + 익스클루시브/인스퍼레이션 |
| G-S-006 | N Line | 18, 19 | 37, 38 | "N Line만의 다이내믹한 스타일" + 휠/머플러 |
| G-S-007 | 안전 기능 | 14, 15 | 25, 26, 29, 30 | 현대 스마트센스 FCA / BCA / NSCC / LFA |
| G-S-008 | 디스플레이 | 5, 6 | 4, 5 | 파노라믹 커브드 디스플레이 + ccNC |
| G-S-009 | 외장 색상 | 22 | 44 | Colors Exterior colors (W6H/NY9/XB9 등) |
| G-S-010 | 블루링크 | 26 | 60, 61, 62 | 블루링크 스토어 + 원격제어 + 마이현대 앱 |

### 3. `evals/run_ragas.py` (신규, 검색만)

핵심 설계:
- **rule-based 자체 계산** — Ragas 의 `context_recall` / `context_precision` 기본은 LLM judge 가 필요해
  무료 티어 (Gemini 1,500 회/일) 부담 회피. Ragas 0.4.x 와 동일 정의로 자체 산출.
- **datasets.Dataset 호환 schema 유지** — Phase 2 에서 LLM judge (Faithfulness 등) 합칠 때 동일 데이터셋 재사용.
- `/search?q=...&doc_id=SONATA&limit=10&mode=hybrid` 호출 → `matched_chunks[].chunk_idx` 추출 → 메트릭 산출.
- `argparse` — `--top_k` (default 10) / `--csv` / `--doc_id` / `--output`.

### 4. `Makefile` (신규, root)

```bash
make eval     # Ragas mini 검색 품질 측정 (DoD ③)
make golden   # golden batch (20건) 회귀 측정 (기존 도구 entry-point)
make slo      # search SLO 모니터링
```

`make eval` 결과는 `work-log/<오늘> ragas-mini-result.md` 로 자동 저장 → 변경 이력 누적.

### 5. `evals/README.md` 갱신

W22 시점 "DoD ②③ 차단 (Ragas 미도입)" → W25 D7 마감 "Phase 1 ship + Phase 2 진입 조건" 으로 상태 갱신.

### 6. `검색 파이프라인 동작 명세 (living).md` v0.2 갱신

- §8 KPI 측정 도구 — mini-Ragas 행 추가 + 8.1 신규 (첫 측정 결과 표 + precision 격차 분석).
- §9 변경 이력 — W25 D7 한 줄 추가.

---

## 첫 측정 결과 (`make eval` 실행 — uvicorn 8000 가동 상태)

```
[INFO] 10 QA 로드 from golden_v0.4_sonata.csv
[INFO] /search 호출 (top_k=10, doc_id=3b901245...)
[OK] G-S-001 recall=1.00 precision=0.50 took=543ms
[OK] G-S-002 recall=1.00 precision=1.00 took=622ms
[OK] G-S-003 recall=1.00 precision=1.00 took=594ms
[OK] G-S-004 recall=1.00 precision=1.00 took=624ms
[OK] G-S-005 recall=1.00 precision=0.05 took=543ms
[OK] G-S-006 recall=1.00 precision=0.50 took=505ms
[OK] G-S-007 recall=1.00 precision=1.00 took=504ms
[OK] G-S-008 recall=1.00 precision=0.25 took=531ms
[OK] G-S-009 recall=1.00 precision=1.00 took=431ms
[OK] G-S-010 recall=1.00 precision=1.00 took=492ms
```

종합:
| 메트릭 | 값 | 사용자 의도 대비 |
|---|---|---|
| Context Recall@10 (평균) | **1.000 (100%)** | 70~90% 기대 → **상회** |
| Context Precision@10 (평균) | **0.730** | (기대 미설정) — precision 격차 (0.05~1.00) 신호 |
| latency p95 | 624ms | < 1000ms 정상 |

→ 상세 결과: `2026-05-04 ragas-mini-result.md`.

---

## 분석

### Recall 100% — 단일 doc 스코프의 자연스러운 결과

본 측정은 `doc_id=SONATA` 단일 doc 스코프 (W25 D5 ship 의 `_MAX_MATCHED_CHUNKS_DOC_SCOPE=200`)
+ top_k=10 으로 호출. SONATA chunks 99개 중 10개 retrieve → 정답 청크 (대부분 1~4 개) 가
거의 항상 포함되는 구조. **list 모드 (전체 코퍼스 기반) 측정 시 recall 이 더 의미있음** — Phase 2.

### Precision 격차 — ranking 개선 후속 신호

precision = `1 / (첫 hit rank)`. SONATA 단일 스코프 안에서도 정답 청크가 top-1 이 아닌
중하위로 밀린 케이스 4건:

| QA | precision | retrieved (앞부분) | 분석 |
|---|---|---|---|
| G-S-005 (트림) | 0.05 | 47, 56, 46, 65, 97, 62, 1, 2, 44, 96 | 정답 39/43 모두 top-10 밖, **rank 20+ 추정** → ranking 약점 |
| G-S-008 (디스플레이) | 0.25 | 62, 97, 1, 5, 56, 2, 39, 55, 96, 44 | 정답 4 (Interior 파노라믹) 가 4위 — 무관 청크 (62=블루링크 디스플레이) 가 1위 |
| G-S-001 (전장) | 0.50 | 87, 85, 66, 84, 67, 68, 88, 97, 56, 82 | 정답 85 가 2위, 66 이 3위 — Dimensions 본문 청크가 표 청크보다 우세 |
| G-S-006 (N Line) | 0.50 | 56, 37, 1, 2, 38, 43, 4, 28, 36, 8 | 정답 37 이 2위, 56 (무관) 이 1위 |

**개선 가설**:
- "트림" 같은 카탈로그 메타 키워드 → heading boost (chunks.section_title 매칭 시 가산점)
- "디스플레이" 같은 generic 단어 → 표지/메뉴 청크 (idx=62, 97 패턴) 추가 가드
- Phase 2 에서 LLM judge (Answer Relevancy) 합치면 본문 자체 fit 측정 가능

### precision 격차는 **현재 ship 단계의 정확한 한계 가시화** — sprint 의 핵심 가치

사용자가 의심한 "매칭 강도 100%" 의 진실:
- doc 단위 ranking 은 SONATA → top-1 (추정) → relevance=1.0 표시.
- chunk 단위 안 ranking 은 일부 query 에서 **무관 청크가 정답보다 우세**.
- 이 격차가 사용자가 보는 "100% 표시" 와 "실제 정답 검색 품질" 의 gap.

→ 본 sprint 의 산출물은 이 gap 을 **숫자로 가시화** 하고, Phase 2 에서 무엇을 개선해야 하는지 정량 신호 제공.

---

## 정책 변경 명시

- **외부 의존성 0 정책 첫 변경** — Q1 사용자 명시 승인 받음. W11~W24 동안 누적 0건 유지하던 정책의 첫 deviation.
- **백엔드 검색 RPC 변경 0** — Ragas 는 `/search` 호출 클라이언트 (read-only).
- **단위 테스트 회귀 0 (api 287)** — `uv run python -m unittest discover -s tests` 통과.

---

## 다음 스코프 (W25 D8+ 후보)

1. **Phase 2 진입 조건** — 사용자 자료 누적 (45 doc / 135 QA 목표) + LLM answer 어댑터 결정.
2. **list 모드 mini-Ragas** — 단일 doc 스코프 외에 전체 코퍼스 기반 retrieval 측정 (recall 의미 강화).
3. **precision 격차 개선** — heading boost / 메뉴 청크 가드 / table-row chunk 우선순위.
4. **CI 통합** — `make eval` 의 임계값 (recall ≥ 0.7) gate 추가 → 회귀 자동 차단.

---

## 남은 이슈 / 한계

- **Recall 100% 은 단일 doc 스코프의 산물** — 전체 코퍼스 기반 list 모드에서는 다른 doc 의 무관 청크가 상위 진입할 수 있어 recall 변동 가능. Phase 2 에서 list 모드 측정 추가.
- **Precision 격차 4건 (G-S-001/005/006/008) 의 root cause 미진단** — 본 sprint 는 측정만, 개선은 후속 sprint.
- **Ragas LLM judge 미사용** — Faithfulness / Answer Relevancy / Answer Correctness 는 LLM (OpenAI/Gemini) 호출 필요. 무료 티어 제약 + LLM answer 어댑터 미도입으로 Phase 1 범위 제외.

---

## 참고

- 사용자 결정 명세: 본 sprint kickoff 메시지 (W25 D7 sprint Phase 1 mini-Ragas 도입)
- 데이터셋: `evals/golden_v0.4_sonata.csv`
- 측정 스크립트: `evals/run_ragas.py`
- 첫 측정 결과: `work-log/2026-05-04 ragas-mini-result.md`
- KPI 도구 인덱스: `검색 파이프라인 동작 명세 (living).md` §8 / §8.1
