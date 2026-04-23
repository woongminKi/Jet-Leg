# Jet-Rag

> 한국 직장인을 위한 멀티포맷 RAG 기반 개인 지식 에이전트.
>
> "정리하지 않아도, 기억의 단편으로 꺼내 쓰는 앱."

**상태**: v0.1 MVP 개발 중 (W1 / 6주, 착수 2026-04-22 · 완료 목표 2026-06-02)
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

## 기술 스택 (MVP)

| 레이어 | 선택 |
|---|---|
| Backend | FastAPI (Python 3.12, uv) |
| Frontend | Next.js + PWA (pnpm) |
| DB / Storage | Supabase (Postgres + pgvector + Storage) |
| 임베딩 | BGE-M3 via Hugging Face Inference API (dense + sparse) |
| 생성 LLM | Gemini 2.0 Flash (무료 티어) |
| Vision / OCR | Gemini 2.0 Flash 내장 |
| 평가 | Ragas |
| 어댑터 스텁 | OpenAI (LLM / Embedding / Vision 각 1개) |
| 호스팅 | Railway (BE) · Vercel (FE) |

**어댑터 레이어 설계**(`app/adapters/`)로 Cloud→Local 전환 경로 확보. v2는 Ollama + LanceDB 로컬 전환.

## 레포 구조

```
Jet-Rag/
├── api/         # FastAPI 백엔드 (W1 Day 2~)
├── web/         # Next.js PWA 프론트엔드 (W1 Day 6~)
├── evals/       # Ragas 평가 셋 / 러너 (W5~)
├── docs/        # ADR, 아키텍처 노트
└── work-log/    # 일자별 작업 로그 · 기획서
```

## 기획 문서

- `work-log/2026-04-22 개인 지식 에이전트 기획서 v0.1.md` — 문제 정의, 페르소나, 10개 유저 스토리, 6주 로드맵, 11개 KPI, 어댑터 레이어
- `work-log/2026-04-22 작업 이어가기 가이드.md` — 환경 세팅, W1 Day 1 실행 순서

## 개발

**요구 사항 (집 컴퓨터)**
- Python 3.12 + [uv](https://docs.astral.sh/uv/) · Node.js 20+ + pnpm · gh CLI · Git
- Supabase 프로젝트 + Gemini API 키 (W1 Day 1~2 필수), HF / Railway / Vercel은 해당 주차에 가입

### 설치 (백엔드)

도구가 없다면 먼저 [uv 설치](https://docs.astral.sh/uv/getting-started/installation/) 후 Python 3.12를 준비합니다.

```bash
uv python install 3.12   # 시스템에 3.12가 없을 때
cd api
uv sync                  # pyproject.toml / uv.lock 기준 의존성 설치
```

루트에 환경 변수 파일이 없으면 템플릿을 복사한 뒤 값을 채웁니다 (`api`는 상위 디렉터리의 `.env`를 읽습니다).

```bash
cd ..                   # 레포 루트
cp .env.example .env    # 편집기로 SUPABASE_*, GEMINI_API_KEY 입력
```

### 실행 (API)

```bash
cd api
uv run uvicorn app.main:app --reload
```

- 헬스: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

`web/`·`evals/` 스캐폴드는 주차별로 채워지며, 프론트 설치·실행 명령은 해당 디렉터리가 생기면 이 README에 이어서 적습니다.

## KPI 목표 (발표 카드)

> HWP 인제스트 ≥95% · Ragas Faithfulness ≥0.85 · 출처 일치율 ≥95% · P95 응답 ≤3초

## 포트폴리오 공개 규칙

- `.env`·API 키 일체 비커밋 (`.gitignore` 엄수)
- 평가 데이터셋은 공공·합성 자료만 (실업무 자료 금지)
- 개인 업로드 샘플은 repo 외부에 보관

## 라이선스

[MIT](./LICENSE)
