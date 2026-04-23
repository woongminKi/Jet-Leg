# Jet-Rag

> 한국 직장인을 위한 멀티포맷 RAG 기반 개인 지식 에이전트.
>
> "정리하지 않아도, 기억의 단편으로 꺼내 쓰는 앱."

**상태**: v0.1 MVP 개발 중 (W1 Day 7 완료, 6주 일정 / 착수 2026-04-22 · 완료 목표 2026-06-02)
**목적**: 포트폴리오 프로젝트. 공공·대기업 비IT 실무자가 일상적으로 받는 HWP/HWPX·PDF·이미지·URL 자료를 자연어로 역검색.

---

## 문제

한국 직장인은 하루에 HWP·PDF·스크린샷·URL 20건을 받지만 일주일 뒤엔 무엇을 받았는지도, 어디에 있는지도 기억하지 못한다. 기존 도구(Notion AI / Mem / Apple Notes / Obsidian / Evernote)는 **HWP 미지원 + 한국어 RAG 취약 + 공공·대기업 보안 정책과 충돌**로 이 페르소나를 커버하지 못한다.

## 해결 접근

1. **멀티포맷 인제스트** — HWP/HWPX·PDF·DOCX·이미지·URL 5경로
2. **Vision 캡셔닝 + OCR 2-pass** — 표·다이어그램·화이트보드까지 검색 가능화
3. **하이브리드 검색** — BM25 + Vector + RRF + 메타 필터
4. **쿼리 라우팅** — "지난달"·"이 파일만" 같은 자연어 제약을 스코프/필터로 변환
5. **Ragas 평가 루프** — "잘 되는 척"이 아니라 수치로 증명

## 기술 스택 (MVP, 2026-04-23 기준)

| 레이어 | 선택 |
|---|---|
| Backend | FastAPI (Python 3.12, uv) |
| Frontend | Next.js 16 + Tailwind v4 + shadcn/ui (new-york, neutral) + Noto Sans KR |
| DB / Storage | Supabase (Postgres + pgvector + Storage, ivfflat lists=100) |
| 임베딩 | BGE-M3 via Hugging Face Inference Providers (dense 1024 만, sparse 는 W3 에 Postgres FTS 로 대체) |
| 생성 LLM | Gemini 2.5 Flash (무료 티어 RPD 20) |
| Vision / OCR | Gemini 2.5 Flash 내장 (W2 도입 예정) |
| 평가 | Ragas (W5 도입) |
| 어댑터 스텁 | OpenAI (LLM / Embedding / Vision 각 1개, W6 스왑 시연) |
| 호스팅 | Railway (BE) · Vercel (FE) — 배포는 W6 |

**어댑터 레이어 설계** (`api/app/adapters/`) 로 Cloud→Local 전환 경로 확보. v2 는 Ollama + LanceDB 로컬 전환.

## 레포 구조

```
Jet-Rag/
├── api/         # FastAPI 백엔드 (W1 Day 2~)
├── web/         # Next.js 프론트엔드 (W1 Day 6~)
├── docs/        # ADR · 아키텍처 노트 · v0 와이어프레임 (참조 자료)
├── evals/       # Ragas 평가 셋 / 러너 (W5~)
└── work-log/    # 일자별 작업 로그 + 기획서
```

## 기획 문서

- `work-log/2026-04-22 개인 지식 에이전트 기획서 v0.1.md` — 문제 정의, 페르소나, 10 유저 스토리, 6주 로드맵, 11 KPI, 어댑터 레이어
- `work-log/2026-04-23 작업 이어가기 가이드.md` — 다른 머신에서 W1 Day 6 부터 이어가기 위한 환경 셋업 가이드
- `work-log/2026-04-XX W1 Day N …md` — 일자별 작업 로그

---

## 개발

### 사전 요구 사항

| 도구 | 용도 |
|---|---|
| Python 3.12 + [uv](https://docs.astral.sh/uv/) | 백엔드 |
| Node.js 20+ + pnpm | 프론트 |
| Git + gh CLI | 형상 관리 |
| Supabase 프로젝트 | DB + Storage |
| Gemini API 키 (Google AI Studio) | LLM |
| Hugging Face 토큰 (Read 권한) | 임베딩 |

집 / 다른 컴퓨터 셋업 절차는 `work-log/2026-04-23 작업 이어가기 가이드.md` 참고.

### 환경 변수

```bash
# 레포 루트
cp .env.example .env
# 편집기로 SUPABASE_URL / SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY / GEMINI_API_KEY / HF_API_TOKEN 입력
```

```bash
# 프론트 (web/)
cd web
cp .env.example .env.local
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 (기본값)
```

### 백엔드 (API) 실행

```bash
cd api
uv sync                                  # 첫 실행 시 의존성 설치
uv run uvicorn app.main:app --reload     # http://localhost:8000
```

- 헬스: <http://localhost:8000/health>
- OpenAPI Swagger UI: <http://localhost:8000/docs>
- 시스템 통계 한눈에: <http://localhost:8000/stats>

### 프론트 (web) 실행

```bash
cd web
pnpm install                             # 첫 실행 시
pnpm dev                                 # http://localhost:3000
```

- 홈 (S1): <http://localhost:3000>
- 검색 (S2): <http://localhost:3000/search?q=반도체>
- 인제스트 (S6): <http://localhost:3000/ingest>

> **두 서버를 동시에 띄워야** 프론트가 백엔드 API 를 호출할 수 있다. 터미널 두 개 또는 `tmux` 권장.

### Supabase 초기 셋업 (첫 1회)

1. [Supabase](https://supabase.com) 프로젝트 생성
2. SQL Editor → `api/migrations/001_init.sql` 전체 복붙 → Run
3. Storage → New bucket: `documents` (Private)
4. Settings → API → service_role 키 복사 → `.env` 의 `SUPABASE_SERVICE_ROLE_KEY` 에 입력

---

## 현재 가용 기능 (2026-04-23 W1 Day 7)

### 백엔드 엔드포인트
- `POST /documents` — 멀티파트 업로드 (PDF/HWP/HWPX/DOCX/PPTX/이미지/TXT/MD, 최대 50MB), SHA-256 dedup, 7스테이지 파이프라인 비동기 시작
- `POST /documents/{id}/reingest` — 기존 doc chunks/메타 reset 후 재처리 (Day 4 데이터 dense_vec 채우기 등)
- `GET /documents` — 최신순 리스트 (tags/summary/flags/chunks_count/latest_job_status 포함)
- `GET /documents/{id}/status` — 인제스트 진행 상태 + 스테이지 로그
- `GET /search?q=` — Postgres `ilike` 키워드 검색, doc 단위 그룹화 + relevance 점수 + matched_chunks highlight
- `GET /stats` — 시스템 통계 (총/이번달 문서, doc_type 분포, 인기 태그 top-10, jobs 상태)

### 인제스트 파이프라인 (7 스테이지)
```
extract → chunk → tag_summarize → load → embed → doc_embed → dedup
```

### 프론트 화면
- **S1 홈** (`/`) — Hero 검색 + 최근 추가 + 인기 태그 + 문서 통계
- **S2 검색** (`/search?q=`) — 결과 카드 + 매칭 청크 하이라이트 + relevance 표시
- **S6 인제스트** (`/ingest`) — 드래그앤드롭 + 7스테이지 실시간 진행 (1.5s 폴링)

---

## KPI 목표 (발표 카드)

> HWP 인제스트 ≥95% · Ragas Faithfulness ≥0.85 · 출처 일치율 ≥95% · P95 응답 ≤3초

## 포트폴리오 공개 규칙

- `.env` · API 키 일체 비커밋 (`.gitignore` 엄수)
- 평가 데이터셋은 공공·합성 자료만 (실업무 자료 금지)
- 개인 업로드 샘플은 repo 외부에 보관 (`assets/` 는 gitignored)

## 라이선스

[MIT](./LICENSE)
