# 2026-04-29 W3 Day 2 마감 — Phase 2~4 ship 종합

> Day 2 #1 (search 라우터 재작성) ship 후 같은 날 안에 Phase 2/3/4 모두 마감.
> 자매 문서:
> - `2026-04-29 W3 Day 2 — search 라우터 재작성.md` (Phase 1 = Day 2 #1 결과)
> - `2026-04-29 W3 스프린트 명세 v0.5.md` (CONFIRMED, Option Z)
> - `2026-04-29 청킹 정책 검토.md` (G(2) 보고서, W4-Q-14 입력)
> - `2026-04-30 chunk 품질 진단 리포트.md` (G(1) 결과)

---

## 0. TL;DR

오늘 (2026-04-29) Day 2 #1 ship 후 senior-qa 회귀 점검 → 결함 3건 (정량 KPI 측정 불가 / simple FTS 한국어 sparse=0 / chunk 품질 미반영) 인정 → **명세 v0.5 (Option Z) 채택** + Phase 2~4 일괄 ship. **Day 3 작업 (G + DE-60) 까지 같은 날 안에 마감, 정상 일정 1d 단축**.

**최종 상태**:
- v0.5 CONFIRMED — DE-60 (PGroonga) · DE-61 (KPI 정성화) · DE-62 (chunk 품질 G) 채택
- 마이그레이션 004 (PGroonga) Studio 적용 + 라이브 검증 통과 — DE-60 회복 명확
- search_metrics ring buffer + /stats.search_slo + housekeeping P0 (5-1, 8-7) + Phase 2 잔존 P1 통합 ship
- chunk 품질 진단 리포트 + 청킹 정책 검토 보고서 작성 — W4-Q-14 + W4-Q-17 (NEW) 결정 입력
- 새 발견: **section_title 0%** — PDF parser 의 heading 추출 한계, **W4-Q-17 (NEW) 로 이월**

---

## 1. Phase 2 — Housekeeping P0 (5-1 · 8-7 · 1-1)

### 1.1 변경 파일

| 파일 | 변경 |
|---|---|
| `api/app/adapters/impl/bgem3_hf_embedding.py` | +25/-0 — `lru_cache` import + `is_transient_hf_error()` alias + `get_bgem3_provider()` 싱글톤 |
| `api/app/routers/search.py` | +18/-3 — fallback 분기 분리 (transient → fallback / 영구 → 503) + 싱글톤 호출 |
| `api/app/ingest/stages/embed.py` · `doc_embed.py` | 각 +2/-2 — 싱글톤 호출 통일 |
| `api/tests/test_bgem3_singleton.py` | 신규 +192 — 11 케이스 |
| `api/tests/test_search_user_isolation.py` | 신규 +159 — 격리 + 대조군 |

### 1.2 결과
- 5-1 silent degradation 차단: HF 4xx → 503 raise (운영자 알림 + Retry-After), 5xx/network → sparse-only fallback
- 8-7 httpx.Client leak: 프로세스당 1 인스턴스 (lru_cache)
- 1-1 RPC user_id_arg 회귀 테스트: synthetic 2nd user 격리 + 대조군

---

## 2. Phase 3 — search_metrics + Phase 2 잔존 P1 통합

### 2.1 변경 파일

| 파일 | 변경 |
|---|---|
| `api/app/services/search_metrics.py` | 신규 +132 — `deque(maxlen=500)` + `threading.Lock` + `record_search/get_search_slo/_reset_for_tests` |
| `api/app/routers/stats.py` | +25/-1 — `SearchSloStats` 모델 + `StatsResponse.search_slo` |
| `api/app/routers/search.py` | +47/-10 — 메트릭 hook (4 응답 분기) + `query_parsed.fallback_reason` (D-1) + 503 의 `Retry-After: 60` (A-3) |
| `api/tests/test_search_metrics.py` | 신규 +91 — 4 케이스 |
| `api/tests/test_search_user_isolation.py` | +96/-10 — C-1 (RPC 직접 호출) + E-4 (sparse fallback soft-delete) + addClassCleanup |
| `web/src/lib/api/types.ts` | +25/-1 — `SearchSloStats` + `QueryParsedInfo.fallback_reason` |

### 2.2 D-1/D-2 (Phase 3 보강)

| 파일 | 변경 |
|---|---|
| `api/tests/test_search_503_retry_after.py` | 신규 +178 — Retry-After 헤더 라이브 부착 검증 (단위 + TestClient 라이브 4 케이스) |
| `web/src/app/search/error.tsx` | 신규 +102 — Next.js 16 v16.2.0 신 API (`{ error, unstable_retry }` + `'use client'`) — Server Component 503 처리 |

### 2.3 결과
- search_slo 정상 노출: `{p50_ms, p95_ms, sample_count, avg_dense/sparse/fused_hits, fallback_count, fallback_breakdown}`
- 503 응답에 Retry-After: 60 헤더 부착 (Starlette 변환 라이브 검증)
- search/error.tsx 가 503 → "검색 일시 오류" 토스트 / generic → "검색 중 오류" + reset

---

## 3. Phase 4 — DE-60 (PGroonga) + DE-62 (chunk 품질 G)

### 3.1 마이그레이션 004 — `api/migrations/004_pgroonga_korean_fts.sql` 신규

내용:
- `CREATE EXTENSION IF NOT EXISTS pgroonga`
- `chunks.flags JSONB DEFAULT '{}'::jsonb` 컬럼 신설 + `idx_chunks_flags GIN`
- 003 의 `chunks.fts` 컬럼 + `idx_chunks_fts` 제거
- `idx_chunks_text_pgroonga ON chunks USING pgroonga (text)` 신규
- `search_hybrid_rrf` RPC 재작성 — sparse path: `text &@~ query_text` (PGroonga query 모드, Mecab) + `pgroonga_score` 정렬 + `flags.filtered_reason IS NULL` 필터
- `search_sparse_only_pgroonga` RPC 신설 (옵션 B) — fallback path

### 3.2 적용 결과 (사용자가 Studio SQL Editor 직접 실행)

MCP execute_sql 검증:
- pgroonga extension 활성 ✅
- chunks.flags 추가 + idx_chunks_flags ✅
- chunks.fts 컬럼/인덱스 제거 ✅
- idx_chunks_text_pgroonga 신규 ✅
- search_hybrid_rrf + search_sparse_only_pgroonga RPC 등록 ✅

### 3.3 search.py `_sparse_only_fallback` 변경

기존 PostgREST `.filter("fts", "plfts(simple)", q)` → RPC 호출:
```python
client.rpc("search_sparse_only_pgroonga", {
    "query_text": q,
    "user_id_arg": str(user_id),
    "top_k": top_k,
}).execute()
```

### 3.4 chunk 품질 진단 도구 — `api/scripts/diagnose_chunk_quality.py` 신규 (~310줄)

CLI:
```bash
uv run python scripts/diagnose_chunk_quality.py --output ../work-log/2026-04-30\ chunk\ 품질\ 진단\ 리포트.md
```

기능: chunks fetch (page-by-page) → 표 노이즈 / 헤더-푸터 / section_title / 길이 분포 → markdown 리포트.

### 3.5 단위 테스트

- `api/tests/test_pgroonga_migration.py` 신규 +8 케이스 (mock 검증)
- 기존 27/27 PASS 회귀 0 + Phase 2/3/4 합계 **42/42 PASS** (test_bgem3_singleton 11 + test_search_user_isolation 4 + test_search_metrics 7 + test_search_503_retry_after 4 + test_pgroonga_migration 8 + test_search_user_isolation 추가 신규들)

---

## 4. DE-60 회복 라이브 검증

직전 simple FTS 시대의 sparse=0 구조적 실패가 PGroonga 로 명확히 회복:

| 쿼리 | 직전 (simple) | 현재 (PGroonga) | 비고 |
|---|---|---|---|
| `"판결"` | 0 (가정) | **sparse_hits=21** | LIKE 와 동일 매칭 |
| `"쏘나타 디 엣지"` | 0 | **sparse_hits=1** | 한국어 어절 매칭 |
| `"대법원 판결"` | 0 | **sparse_hits=9** | 자연어 두 단어 |

took_ms: cold 1.2~2.2초, warm 480ms. cold start 가 P95<500ms 위협 — HF API embed_query latency variance 가 본질 (R-W3-5).

`query_parsed.has_sparse=True` 노출 정상.

---

## 5. chunk 품질 진단 결과 — 새 발견

`work-log/2026-04-30 chunk 품질 진단 리포트.md`

**핵심 지표**:
- chunks 총 465건, doc 4건 (모두 PDF)
- **section_title 채움 비율 0%** — KPI §13.1 의 30% 한참 미달
- 표 노이즈 의심 36.8% (171건) — sample-report 가 40%
- 헤더/푸터 의심 0% (heuristic 약함 가능)
- 청크 길이: avg 249 / p50 224 / p95 466 / max 969 — 한국어 권장 500~1000 의 하단

**doc 별**:
| doc | chunks | table_noise% | section% |
|---|---:|---:|---:|
| sample-report | 375 | 40% | 0% |
| sonata-the-edge_catalog | 75 | 24% | 0% |
| law sample3 | 12 | 8% | 0% |
| jet_rag_day4_sample | 3 | 0% | 0% |

---

## 6. 남은 이슈

### 6.1 section_title 0% — W4-Q-17 (NEW) 로 이월

**현상**: PDF parser (PyMuPDFParser) 가 ExtractedSection 의 section_title 을 채우지 않는 것으로 추정. chunk.py 의 `_to_chunk_records` 는 section_title 을 그대로 보존만 함.

**영향**: KPI §13.1 의 "section_title ≥ 30%" 절대 미달. 사용자 자산 4 doc 모두 PDF 라 명세 v0.5 §3.F (HWPX/HWPML 한정) 가 KPI 충족시켜줄 doc 0건.

**결정**: **W4-Q-17 (NEW) 로 이월** — PDF heading 추출 강화는 명세 변경. v0.5 의 KPI 정성화 (DE-61) 가 이미 정량 KPI 폐기 — section_title 30% 도 정성 sanity check 로 포함.

**Day 5 정성 검토 시**: 사용자가 PDF 검색 결과의 section_title 부재가 UX 에 미치는 영향 직접 검토.

### 6.2 표 노이즈 36.8% — Day 4 G(3) 자동 필터링 룰로 처리 예정

sample-report doc 가 노이즈 비율 40%. G(3) 자동 필터링 룰 (`flags.filtered_reason='table_noise'`) 도입 정당화 강함. Day 4 작업 — 명세 v0.5 §3.G(3) 그대로 진행.

### 6.3 cold start P95 위협

HF API embed_query 가 cold 1~2초. P95<500ms SLO 위협. R-W3-5 의 embedding cache (W4-Q-3) 우선순위 ↑.

### 6.4 Phase 3/4 의 잔존 P1/P2 (Phase 4 senior-qa 결과 후 정리)

- A-2 prod build 의 ApiError sanitize → search/page.tsx try/catch 추가 검토 (W4)
- Retry-After 헤더의 reverse proxy 처리 → 운영 시 검증
- multi-worker 환경 측정값 분산 → docstring "단일 worker 전제" 명시 + 운영 가이드
- 그 외 다수 — Phase 4 senior-qa 결과 받아 일괄 정리

---

## 7. 다음 스코프

### 7.1 Day 4 (2026-05-01)

| 항목 | 내용 |
|---|---|
| C Tier 3 dedup | `ingest/stages/dedup.py` 확장 — 파일명 trigram + doc_embedding 코사인 |
| E DNS rebinding 방어 | `routers/_url_gate.py` 1차/2차 IP resolve 비교 |
| **G(3) 자동 필터링 룰** | `ingest/stages/chunk_filter.py` 신규 — 표 노이즈 룰 (a) 1개 도입 + 백필 dry-run + 사용자 confirm 게이트 |

### 7.2 Day 5 (2026-05-02)

| 항목 | 내용 |
|---|---|
| F HWPX/HWPML heading | `adapters/impl/hwpx_parser.py` · `hwpml_parser.py` heading propagate |
| golden 20건 평가 자료 작성 | top-3 검증 결과 마크다운 리포트 생성 |
| DoD 코드 측면 | 게이트 §7.1 통과 |
| W3 종합 정리 | `2026-05-02 W3 종합 정리.md` |

### 7.3 Day 6 (2026-05-03) — 사용자 비동기 정성 검토

DoD §7.2 (Q5 B) — 사용자가 본인 페이스로 golden 20건 검토 → confirm 또는 Day 7+ 추가 sprint.

---

## 8. 새 W4 이월 항목

| # | 항목 | 사유 |
|---|---|---|
| **W4-Q-17 (NEW)** | PDF heading 추출 강화 (PyMuPDFParser 의 section_title 채움) | chunk 진단 결과 PDF doc 4건 모두 section_title 0% — KPI 30% 절대 미달. v0.5 §3.F (HWPX/HWPML) 가 PDF 미포함이라 명세 외. |
| W4-Q-14 (기존) | 청킹 정책 본격 변경 | `2026-04-29 청킹 정책 검토.md` 의 약점 11건 → 5h 묶음 권장 |
| W4-Q-15 (기존) | 노이즈 필터링 룰 (b)·(c) 추가 | Day 4 의 룰 (a) 후 사용자 정성 검토 결과 기반 |
| W4-Q-16 (기존) | search_metrics ring buffer → DB 영속화 | W6+ 사용자 자산 누적 시점 |

---

## 9. 한 문장 요약

W3 v0.5 Option Z 채택 + Phase 2~4 (housekeeping P0 + 측정 인프라 + PGroonga 마이그레이션 004 + chunk 진단 도구) 같은 날 안에 ship 마감, **DE-60 회복 라이브 검증 통과** (sparse_hits 21/9/1 명확), **section_title 0% 새 발견** → W4-Q-17 (NEW) 이월. Day 3 작업까지 1d 단축, 다음 Day 4 = C·E·G(3) 자동 필터링 룰.
