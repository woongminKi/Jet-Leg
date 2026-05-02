# 2026-05-02 W3 Day 5 마감 — HWPX heading + golden + DoD

> 어제(2026-04-29) 핸드오프 §6.1 의 Day 5 목표 4건을 모두 ship + 3 commit push 완료.
> Day 6 (사용자 비동기 정성 검토) 진입 직전.
>
> **자매 문서**:
> - `2026-04-29 W3 Day 5 진입 핸드오프.md` — Day 5 진입 input
> - `2026-04-29 W3 스프린트 명세 v0.5.md` — Option Z CONFIRMED, KPI §13.1 매핑
> - `2026-05-02 golden 평가셋 v0.1.md` — Day 5 #4 산출물
> - `2026-04-30 chunk 품질 진단 리포트.md` — W3 Day 4 G(1) 결과

---

## 0. TL;DR

- HWPX/HWPML heading sticky propagate ship — KPI §13.1 `section_title ≥ 30%` **HWPX 100% 충족** (PDF 0% W4-Q-17 이월).
- 사용자 자산 HWPX 2건 (직제_규정 + 한마음생활체육관) 인제스트 + chunks.flags chunk_filter e2e 통과 (B-5 PASS).
- golden 20건 평가셋 v0.1 작성 — Day 6 정성 검토 input + W6+ 정량 Recall@10 base.
- D-2 (CDN false positive 0/6) + B-5 (HWPX 마킹 18.6%/22.2%) 게이트 PASS.
- P2 docstring 4건 보강 (C-1 doc 별 breakdown / C-4 되돌리기 SQL / G-1 README 004-rollback / G-3 운영자 게이트).
- 라이브 smoke 5/5 top-1 hit (휴관일·이사장·대법원 판결·쏘나타·2.2%), 평균 478ms (warm KPI §13.1 P95<500ms 거의 충족).
- 회귀 0 (72/72 unittest PASS, Day 4 EOD 의 57 → +15 신규 = 72).
- 3 commit push (origin/main = `a8933aa`).

---

## 1. Day 5 작업 7건 — 시간 순

| # | 마일스톤 | 산출물 |
|---|---|---|
| 1 | hwpx 라이브러리 API + chunk pipeline 사전 조사 (Explore) | 메인 스레드 컨텍스트 (`para.element.styleIDRef` → `HwpxDocument.styles[id].name` 검증) |
| 2 | F HWPX/HWPML heading sticky propagate 구현 (senior-developer) | `api/app/adapters/impl/hwpx_parser.py`·`hwpml_parser.py` 수정 + 신규 테스트 15건 |
| 3 | HWPX 2건 인제스트 + section_title 채움 비율 측정 | KPI 100%/100% 충족, chunks.flags 마킹 18.6%/22.2% |
| 4 | golden 20건 평가셋 v0.1 작성 (senior-planner) | `work-log/2026-05-02 golden 평가셋 v0.1.md` |
| 5 | Day 5 진입 게이트 — B-5 e2e + D-2 CDN + P2 docstring 4건 | 3 파일 보강 (rollback SQL · README · backfill 스크립트) |
| 6 | 라이브 smoke 5건 (golden 키워드 G-011~G-015 sanity check) | 5/5 top-1 hit 100%, 평균 478ms |
| 7 | 본 종합 정리 + W3 DoD 코드 측면 게이트 통과 | 본 문서 |

---

## 2. 코드 변경 + commit 그래프

### 2.1 변경 파일

| 파일 | 변경 | LOC |
|---|---|---|
| `api/app/adapters/impl/hwpx_parser.py` | `_HEADING_STYLE_PATTERN` + `_HEADING_TEXT_PATTERN` + `_is_heading_paragraph` + sticky `current_title` + `HwpxDocument.open()` graceful degrade | +69 / -3 |
| `api/app/adapters/impl/hwpml_parser.py` | 텍스트 패턴 fallback + sticky | +14 / -1 |
| `api/tests/test_hwpx_heading.py` | 신규 (실 자산 2건 + 합성) | +160 |
| `api/tests/test_hwpml_heading.py` | 신규 (합성 HWPML XML) | +77 |
| `api/migrations/README.md` | 004-rollback 행 추가 | +1 |
| `api/migrations/004_rollback.sql` | 운영자 게이트 강화 + DROP EXTENSION 트러블슈팅 SQL | +9 |
| `api/scripts/backfill_chunk_flags.py` | dry-run doc 별 breakdown + 되돌리기 SQL docstring | +22 |
| `work-log/2026-05-02 golden 평가셋 v0.1.md` | 신규 | +388 |
| `work-log/2026-05-02 W3 Day 5 마감.md` | 본 문서 (신규) | (현재) |

### 2.2 commit 그래프 (Day 5)

| # | Hash | Commit |
|---|---|---|
| 1 | `a1f2d62` | `feat(adapters)`: HWPX/HWPML heading sticky propagate (KPI §13.1 ≥30% 충족) |
| 2 | `05f67de` | `docs(work-log)`: golden 평가셋 v0.1 — KPI §13.1 정성 sanity check input |
| 3 | `a8933aa` | `chore`: P2 docstring·dry-run 보강 (Day 5 진입 게이트 4건) |
| 4 | (this) | `docs(work-log)`: W3 Day 5 마감 — HWPX heading + golden + DoD |

W3 누적 commit (Day 1 ship 부터 본 문서까지) = **17 commit**.

---

## 3. KPI 측정 결과

### 3.1 §13.1 section_title ≥ 30%

| doc | type | total chunks | filled | ratio | KPI |
|---|---|---:|---:|---:|---|
| 직제_규정(2024.4.30.개정) | hwpx | 70 | 70 | **100.0%** | ✅ |
| 한마음생활체육관_운영_내규(2024.4.30.개정) | hwpx | 18 | 18 | **100.0%** | ✅ |
| sample-report | pdf | 375 | 0 | 0.0% | W4-Q-17 |
| sonata-the-edge_catalog | pdf | 75 | 0 | 0.0% | W4-Q-17 |
| law sample3 | pdf | 12 | 0 | 0.0% | W4-Q-17 |
| jet_rag_day4_sample | pdf | 3 | 0 | 0.0% | W4-Q-17 |

전체 평균 15.9% — Day 5 목표인 **HWPX 인프라 ≥30%** 는 100%/100% 로 충족. PDF 0% 는 핸드오프 §3.4 결정대로 W4-Q-17 (PyMuPDFParser heading 추출 강화) 이월.

### 3.2 §13.1 출처 일치율 (라이브 smoke)

| query | top-1 doc (정답) | matched_chunks | top-1 hit | took_ms |
|---|---|---:|---|---:|
| 휴관일 | b758eec4 (한마음, hwpx) ✅ | 13 | Y | 638 |
| 이사장 | dd8c1fb0 (직제, hwpx) ✅ | 38 | Y | 457 |
| 대법원 판결 | 49ef8d01 (law, pdf) ✅ | 12 | Y | 420 |
| 쏘나타 | 6004fd65 (sonata, pdf) ✅ | 49 | Y | 394 |
| 2.2% | 3970feab (sample-report, pdf) ✅ | 3 | Y | 480 |

- top-1 hit 5/5 = **100%** (KPI 목표 0.95 충족)
- 평균 took_ms = 478ms (cold start 638ms 1건 제외하면 평균 437ms)
- KPI §13.1 P95 < 500ms — warm path 충족, cold start 1~2초는 R-W3-5 / W4-Q-3 (embedding cache) 이월

### 3.3 chunk_filter e2e (B-5)

| doc | total chunks | flagged | ratio |
|---|---:|---:|---:|
| 직제_규정 | 70 | 13 | 18.6% |
| 한마음생활체육관 | 18 | 4 | 22.2% |

신규 인제스트 시 chunk_filter 가 자동 적용되어 `flags.filtered_reason='table_noise'` 마킹 정상 작동. 백필 dry-run 결과 마킹 대상 0건 (이미 모든 chunks 가 적용 완료).

### 3.4 D-2 CDN false positive

| URL | Result |
|---|---|
| `https://cdn.jsdelivr.net/...` | PASS (4 IP) |
| `https://www.cloudflare.com/` | PASS (2 IP) |
| `https://fonts.googleapis.com/...` | PASS (1 IP) |
| `https://cdnjs.cloudflare.com/...` | PASS (2 IP) |
| `https://www.google.com/` | PASS (8 IP) |
| `https://github.com/` | PASS (1 IP) |

CDN 6/6 모두 통과 (false positive 0). DNS rebinding 엄격 정책 임계값 완화 결정 불요.

---

## 4. 잔존 이슈

### 4.1 P3 (W4 이월, 의도적 보류)

| ID | 항목 | 사유 |
|---|---|---|
| A-3 임시 호환 | `search_sparse_only_pgroonga` 이름 misleading TODO 주석 | 작은 nit, rollback 적용 시점만 의미 있음 |
| B-2 | `chunk_filter._classify_chunk` 빈 청크 → `filtered_reason='empty'` 마킹 | dead branch (chunk.py 가 빈 단락 skip), 우선순위 낮음 |
| D-4 | IPv6 loopback (`::1`) 명시 unit test | url_gate 14건 covered indirectly, 명시 추가는 가독성 |
| F-4 | `search_metrics` ring buffer 의 003/004 sample 혼재 우려 | uvicorn 재시작 시 자연 reset, F-4 자체는 문서화 only |
| G-2 | chunk_filter 의 metric/logging 부재 | W4-Q-15 와 묶어서 일괄 처리 권장 |

### 4.2 W4 우선순위 (이월 항목 재정렬)

| # | 항목 | 우선순위 사유 |
|---|---|---|
| 1 | W4-Q-3 embedding cache | cold start 1~2초 P95 위협 — 가장 시급 |
| 2 | W4-Q-17 (NEW) PDF heading 추출 강화 | KPI §13.1 의 PDF 0% → 30%+ 끌어올리기 |
| 3 | W4-Q-14 청킹 정책 본격 변경 | 5h 묶음 권장 |
| 4 | W4-Q-15 추가 노이즈 필터링 룰 (b)·(c) | 사용자 정성 검토 결과 + W6+ 데이터 후 |
| 5 | W4-Q-9 DOCX/PPTX 파서 | v0.4 Option Y 의 W4 이월 |

---

## 5. Day 6 사용자 비동기 정성 검토 안내

### 5.1 검토 input

- `work-log/2026-05-02 golden 평가셋 v0.1.md` — 20건 query + expected_doc + meta_filters
- 라이브 측정 도구 (서버 가동 상태에서):
  ```bash
  # 단건
  curl -sG 'http://localhost:8000/search' \
    --data-urlencode 'q=체육관 휴관일이 언제예요' \
    --data-urlencode 'limit=10' | python3 -m json.tool

  # 메타 혼합 (예: G-016)
  curl -sG 'http://localhost:8000/search' \
    --data-urlencode 'q=체육관 운영' \
    --data-urlencode 'doc_type=hwpx' \
    --data-urlencode 'limit=10' | python3 -m json.tool
  ```

### 5.2 §4.3 체크리스트 (golden v0.1 §4.3)

- [ ] 자연어 10건: top-3 안에 expected_doc 들어오는 건수 (목표 7건 이상)
- [ ] 키워드 5건: 4건 이상 top-1 hit (sparse 강점) — **메인 스레드 측정 5/5 top-1 hit 통과**
- [ ] 메타 혼합 5건: 5건 모두 top-3 hit (메타 필터 회귀)
- [ ] 한국어 어미 변형 강건성 (G-003 `되더라`)
- [ ] 영어+한국어 혼합 (G-019 `AI 투자`)
- [ ] 숫자+특수문자 (G-015 `2.2%`) — **메인 스레드 측정 통과**
- [ ] Top-3 안에 페르소나 A 가 "이게 정답이네" 라고 인정할 chunk 가 있는가 (정성)
- [ ] "다른 doc 의 chunk 가 잘못 섞여 있다" 사례가 있는가 (false positive)

### 5.3 Day 6 결과 분기

- **8/8 통과**: W3 마감 confirm → W4 진입
- **6~7/8 통과**: 부분 confirm, 미달 항목만 Day 7+ 짧은 sprint
- **5/8 미만**: Day 7+ 추가 sprint 권장 + golden v0.2 보강

---

## 6. DoD 코드 측면 게이트

| # | 항목 | 결과 |
|---|---|---|
| 1 | F HWPX heading ship + section_title ≥30% | ✅ HWPX 100%/100% (PDF 0% W4 이월) |
| 2 | golden 20건 평가셋 작성 | ✅ v0.1 ship |
| 3 | 단위 테스트 회귀 0 | ✅ 72/72 PASS |
| 4 | 라이브 smoke (P95) | ⚠️ warm 478ms 충족 / cold start 1~2초 W4-Q-3 이월 |
| 5 | chunk_filter e2e (B-5) | ✅ 신규 인제스트 자동 마킹 18.6%/22.2% |
| 6 | DNS rebinding CDN false positive (D-2) | ✅ 0/6 |
| 7 | P2 docstring 보강 4건 | ✅ C-1·C-4·G-1·G-3 |

DoD 코드 측면 통과. **Day 6 사용자 비동기 정성 검토** 가 W3 마감의 마지막 게이트.

---

## 7. 운영 정책 (Day 5 신규/변경)

- HwpxParser 의 `HwpxDocument.open(BytesIO)` 두 번 열기 패턴 — graceful degrade 정책 (실패 시 텍스트 패턴 fallback). 동일 패턴 W4-Q-17 (PyMuPDFParser heading) 에도 재사용 권장.
- 백필 dry-run 의 doc 별 breakdown — 운영 가시성 패턴. W4 의 다른 backfill 작업 (예: F (HWPX heading) re-run) 에도 동일 출력 포맷 채택.
- 004_rollback.sql 의 운영자 게이트 강화 — 향후 마이그레이션 005+ 의 rollback SQL 도 동일 docstring 구조 (트리거 조건 / 적용 절차 / 검증 / 적용 후 후속).

---

## 8. 한 문장 요약

오늘 (2026-05-02) Day 5 목표 7건 모두 ship — **HWPX section_title 100%·라이브 smoke 5/5 top-1 hit·72/72 PASS·3 commit push**. W3 DoD 코드 측면 통과, **Day 6 사용자 비동기 정성 검토 진입 직전**.
