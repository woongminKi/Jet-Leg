# 2026-04-23 W1 Day 7 reingest · 모바일 메뉴 · README

> Day 6 까지 백엔드 응답 확장 + UI 셸 3화면을 띄운 상태에서, Day 7 은 W1 마무리로 **재수집 엔드포인트** + **모바일 햄버거 패널 본체** + **README 두 서버 기동 가이드** 3가지를 정리. Day 3·4·5·6 와 마찬가지로 같은 날짜(2026-04-23) 에 연속 수행.

---

## 1. 오늘 달성한 것 — 4 커밋

| # | SHA | 제목 |
|---|---|---|
| 1 | `7b154f2` | feat(api): POST /documents/{id}/reingest 재수집 엔드포인트 추가 |
| 2 | `8e84538` | feat(web): 모바일 햄버거 패널 본체 구현 |
| 3 | `466cb3d` | docs(readme): 두 서버 기동 가이드 + Day 6/7 가용 기능 반영 |
| 4 | (이 work-log) | docs(work-log): W1 Day 7 reingest · 모바일 메뉴 · README |

---

## 2. 변경 상세

### 2.1 `POST /documents/{doc_id}/reingest` (커밋 1)

**목적**: Day 4 데이터처럼 dense_vec / doc_embedding 이 NULL 인 기존 4건을 Day 5 임베딩 스테이지를 포함한 현재 파이프라인으로 다시 처리.

**동작 흐름**
1. doc 존재 확인 (없으면 404)
2. **진행 중 job (queued/running) 있으면 409 Conflict** — race condition 방어
3. 기존 chunks 전체 삭제 (`DELETE FROM chunks WHERE doc_id=?`) + `chunks_deleted` 카운트 회수
4. `documents` 메타 reset: `tags=[]`, `summary=NULL`, `flags={}`, `doc_embedding=NULL`
5. 새 `ingest_jobs` row 생성 (이전 jobs/logs 는 history 로 보존)
6. `BackgroundTasks.add_task(run_pipeline, job_id, doc_id)` 큐잉
7. 응답: `ReingestResponse(doc_id, job_id, chunks_deleted)` (HTTP 202)

**의도된 사이드 이펙트**
- `tags`·`summary`·`flags`·`doc_embedding` 이 새 파이프라인 결과로 덮어써질 때까지 일시적으로 빈 값. 검색·통계가 잠깐 약화됨 (수십 초 단위).
- `storage_path` · `sha256` · `size_bytes` · `content_type` 은 유지 → Storage 재업로드 X, Tier 1 dedup 영향 0.

**검증 방법** (기존 4건 채우기 — 사용자 직접 액션):
```bash
# Swagger UI 또는 curl
curl -X POST http://localhost:8000/documents/3970feab-e02e-4b93-958b-09177a5debb6/reingest
# → 202 + {"doc_id": "...", "job_id": "...", "chunks_deleted": 375}
# → 1~2분 후 GET /documents/{id}/status 로 status="completed" 확인
```

`/documents` 호출하여 doc_id 4개 회수 후 각각 reingest. Gemini RPD 20 한도 고려 (각 doc 당 호출 2~3건 → 4건 reingest 시 약 12건 소비).

### 2.2 모바일 햄버거 패널 (커밋 2)

**문제**: Day 6 디자이너 검수가 짚은 dead UI — `header-mobile-toggle` 가 토글 state 만 가지고 있고 패널 본체 부재.

**구조 변경**
- `header.tsx` 를 client 화 + `mobileOpen` state lift up
- `header-mobile-toggle.tsx` 가 `open` / `onToggle` prop 받도록 — 외부 state 와 sync
- **`header-mobile-panel.tsx` 신설** — `border-t` + container 안에 검색 인풋 + 업로드 CTA 노출

**UX**
- 모바일에서 햄버거 아이콘 → 헤더 아래 패널 펼침
- 패널 안 검색 submit → `/search?q=...` 라우팅 + 자동 close (`onClose()`)
- 패널 안 "파일 업로드" → `/ingest` + 자동 close
- 로고 클릭 시에도 자동 close
- `aria-controls` / `aria-expanded` 접근성 보강

### 2.3 README 갱신 (커밋 3)

**갱신 항목**
- 기술 스택을 2026-04-23 현재 실제 사용 항목으로 정정 (Gemini 2.5-flash, BGE-M3 dense only, Tailwind v4, shadcn new-york)
- `web/.env.local` 환경 변수 섹션 신설
- 백엔드 (uvicorn 8000) + 프론트 (pnpm dev 3000) **두 서버 동시 기동 절차** 분리
- Supabase 초기 셋업 (마이그레이션 SQL + Storage bucket 생성) 단계 추가
- **"현재 가용 기능" 섹션 신설** — 6개 엔드포인트 + 7 스테이지 파이프라인 + 프론트 3화면 요약

---

## 3. 자가 검수 — reingest 잠재 이슈 점검

| # | 시나리오 | 위험도 | 결론 |
|---|---|---|---|
| 1 | 두 reingest 동시 호출 | 낮음 | 첫 호출이 새 job(queued) 생성하면, 두 번째 호출은 409 Conflict 로 거부. 단 두 호출이 정확히 동시(밀리초) 라면 두 job 생성 가능 — 단일 사용자 MVP 에서는 사실상 발생 X |
| 2 | reingest 와 일반 POST /documents 동시 (같은 sha256) | 낮음 | reingest 는 새 document row 생성 X. POST /documents 는 sha256 기반 Tier 1 dedup 으로 기존 row 재사용 + duplicated=true 반환. 충돌 없음 |
| 3 | chunks 삭제 후 파이프라인 실패 | 중간 | `documents.tags/summary/flags` 가 빈 상태로 남음. 사용자가 다시 reingest 호출하면 회복. 데이터 손실 (원래 tags/summary) 은 의도된 동작 — 새로 계산하기로 한 것 |
| 4 | `doc_embedding=None` 업데이트 시 pgvector NULL 허용 | 낮음 | DB 스키마상 doc_embedding 컬럼은 NULL 허용 (Day 3 마이그레이션). 정상 |
| 5 | storage 객체가 사라진 doc 의 reingest | 낮음 | extract 스테이지가 storage 에서 다시 읽음 → 실패 시 fail_job. 사용자에게 명확히 전달됨 |
| 6 | 기존 ingest_jobs/logs 누적 | 낮음 | history 의도. 30일 보존 후 cleanup 정책은 W2+ 운영 단계에서 |

**결론**: 단일 사용자 MVP 환경에서 발생 가능 시나리오는 모두 안전 처리됨. 운영 환경 다중 사용자 시점(W6+)에 distributed lock 또는 advisory lock 도입 검토.

---

## 4. 현재 프로젝트 상태 (Day 6 → Day 7 변경분)

```
api/app/routers/documents.py        ← reingest 엔드포인트 추가 (+80 lines)
web/src/components/jet-rag/
├── header.tsx                       ← client 화 + mobileOpen state
├── header-mobile-toggle.tsx         ← open/onToggle props 로 외부 state sync
└── header-mobile-panel.tsx          ← NEW: 검색 인풋 + 업로드 CTA
README.md                           ← 두 서버 기동 + 가용 기능 + Supabase 셋업
```

엔드포인트 목록 (7개로 확장):
- `POST /documents`
- `POST /documents/{id}/reingest`  ← NEW
- `GET /documents`
- `GET /documents/{id}/status`
- `GET /search?q=`
- `GET /stats`
- `GET /health`

---

## 5. 사용자 직접 확인 체크리스트

### 5.1 reingest 동작 검증 (선택)
```bash
# 백엔드 기동
cd api && uv run uvicorn app.main:app --reload

# 1. 기존 doc 목록 회수
curl http://localhost:8000/documents | python3 -m json.tool

# 2. dense_vec NULL 인 doc 1건 reingest 테스트
curl -X POST http://localhost:8000/documents/<doc_id>/reingest

# 3. 진행 상태 폴링 (1~2분)
curl 'http://localhost:8000/documents/<doc_id>/status?include_logs=true'

# 4. 완료 후 검색 결과에 해당 doc 의 매칭 청크가 잘 노출되는지 확인
curl 'http://localhost:8000/search?q=반도체&limit=5'
```

> **Gemini RPD 20 한도 주의**: 4건 모두 reingest 시 태그+요약 호출이 8건 발생. 다른 업로드 테스트와 합치면 한도 초과 가능. 하루 한도 내에서 분산 권장.

### 5.2 모바일 햄버거 패널 (브라우저 DevTools 모바일 뷰)
| # | 액션 | 기대 |
|---|---|---|
| 1 | DevTools → iPhone 14 Pro 등 모바일 뷰 토글 | 헤더 우측에 햄버거 아이콘 (≡) 노출 |
| 2 | 햄버거 클릭 | 헤더 아래 패널 펼침: 검색 인풋(autoFocus) + "파일 업로드" 버튼 |
| 3 | 패널 안 검색어 입력 + Enter | `/search?q=...` 라우팅 + 패널 자동 close |
| 4 | "파일 업로드" 클릭 | `/ingest` 이동 + 패널 자동 close |
| 5 | 로고 클릭 (홈으로) | 패널 자동 close |
| 6 | X 아이콘 클릭 | 패널 close |

---

## 6. 주요 의사결정 스냅샷 (Day 7 추가분)

| 항목 | 값 | 근거 |
|---|---|---|
| reingest 정책 | 전체 재처리만 (단계별 X) | MVP 단순화. 단계별 재처리는 W2 + 사용성 데이터 본 뒤 결정 |
| reingest 시 chunks | 삭제 후 새로 INSERT | UPSERT 보다 명확. 청크 idx 가 새 청킹 결과와 다를 수 있어 안전 |
| reingest 시 documents 메타 | `tags=[]`, `summary=NULL`, `flags={}`, `doc_embedding=NULL` reset | 새 파이프라인 결과로 덮어쓰기 위함. dedup 결과 (`flags.duplicate_tier`) 도 새로 계산 |
| reingest 동시성 방어 | latest job status 체크로 409 Conflict | 단일 사용자 MVP 에 충분. distributed lock 은 W6+ |
| 모바일 패널 구현 방식 | header.tsx client 화 + sibling 컴포넌트 | shadcn `sheet` 의존성 회피 (의존성 추가 0) |
| 모바일 패널 닫기 트리거 | submit / 링크 클릭 / 로고 클릭 / X 아이콘 | 패널 안 액션 후 자동 close 가 자연스러움 |

---

## 7. W1 마감 — 누적 결과 (Day 1 ~ Day 7)

### 백엔드 (api/)
- 7개 엔드포인트, 4개 테이블, 7스테이지 파이프라인
- 어댑터 5종 (DocumentParser/EmbeddingProvider/LLMProvider/BlobStorage/VectorStore) + 구현체 4개 (PyMuPDFParser, BGEM3HFEmbeddingProvider, GeminiLLMProvider, SupabaseBlobStorage, SupabasePgVectorStore)
- W1 DoD "PDF 업로드 → 키워드 검색 가능" 만족 + reingest 로 기존 데이터 회복 가능

### 프론트 (web/)
- 3 화면 (S1 홈 / S2 검색 / S6 인제스트) Next.js 16 + Tailwind v4 + shadcn (new-york, neutral)
- v0 와이어프레임 OKLCH 토큰 + Noto Sans KR 이식
- 라우트 분리 + RSC + Client 분리
- 모바일 햄버거 패널 동작
- 백엔드 응답과 1:1 매핑되는 타입 + API 클라이언트

### 미완료 → W2+ 이월
| 항목 | 처리 시점 |
|---|---|
| 멀티포맷 어댑터 (HWP/HWPX/DOCX/PPTX/이미지/URL) | W2 |
| Vision 경로 (Gemini 2.5 Flash 내장) | W2 |
| 입력 게이트 B (콘텐츠 게이트) | W2 |
| 8.6MB 업로드 수신 SLO 초과 (3.7초) — Storage 업로드 BackgroundTask 분리 | W2 |
| 하이브리드 검색 (dense + sparse/FTS + RRF) | W3 |
| 변경점 diff 감지 (tier 3) | W3 |
| `/doc/[id]` 문서 상세 라우트 | W2~3 |
| 쿼리 분석 row (NL→DSL) | W2 |
| 모바일 필터 Sheet (S2) | W3 |
| 다크 토글 UI | W4+ |
| 알림 / 설정 드롭다운 | W4+ |
| Ragas 평가셋 (45문서·135QA) | W5 |
| OpenAI 어댑터 스왑 시연 | W6 |
| Railway · Vercel 배포 | W6 |

---

## 8. 다음 스코프 — W2 (멀티포맷 + Vision)

기획서 §14.2 W2 로드맵:
1. **포맷별 어댑터**: HWP/HWPX (libhwp 또는 libreoffice headless), DOCX (python-docx), PPTX (python-pptx), 이미지 (Gemini Vision), URL (httpx + BeautifulSoup)
2. **Vision 경로**: 이미지/스캔 PDF 의 OCR + 캡셔닝 → chunks 텍스트화
3. **입력 게이트 B**: 콘텐츠 검사 (한국어 비율, 최소 텍스트 길이 등)
4. **수신 응답 SLO 회복**: Storage 업로드 BackgroundTask 분리 → POST /documents 가 < 2초 응답
5. **`/doc/[id]` 라우트** 또는 모달: 검색 결과 카드 클릭 시 문서 전체 보기
6. **NL→DSL 쿼리 분석**: 자연어 → date_range / doc_type / tag 필터 추출

---

## 9. 회고 한 줄

Day 7 은 W1 의 **운영 안정성 마감** — 기존 데이터 회복 수단 (reingest), 모바일 사용성 (햄버거 패널), 새 머신 셋업 가이드 (README). 6일 동안 매일 의미 있는 산출물 + work-log 가 누적되어 다른 컴퓨터로 옮겨가도 동일한 컨텍스트로 즉시 이어갈 수 있는 상태로 W1 마감.
