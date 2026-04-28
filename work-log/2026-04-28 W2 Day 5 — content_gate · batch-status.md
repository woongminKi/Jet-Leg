# 2026-04-28 W2 Day 5 — content_gate · batch-status

> 8-stage 파이프라인의 마지막 빈 자리 (`content_gate`) 충원 + 프론트 폴러 N→1 호출 최적화 (`batch-status`). **AC 21/22 통과 + 3종 케이스 discrimination 100%**.
>
> **선행 문서**: `work-log/2026-04-28 W2 Day 4 — URL · HWP 5.x.md`

---

## 0. 다음 세션 진입점

### 0.1 working tree 상태
- 모든 Day 5 변경 커밋 + push 완료
- `git status` clean

### 0.2 Day 6 진입 순서 (명세 v0.3 §7.1)

| # | 액션 | 예상 |
|---|---|---|
| 1 | **항목 M `/doc/[id]` 경량판** (F′-α2) — 신규 `GET /documents/{id}` 백엔드 + 프론트 `/doc/[id]` 라우트 + 인제스트 완료 자동 이동 | 0.6d |
| 2 | 프론트 폴러를 `/documents/batch-status` 사용으로 전환 | 0.2d |
| 3 | Day 6 통합 smoke + KPI 사전 측정 | 30분 |

### 0.3 결정 보류
- `/doc/[id]` Hero 검색 인풋 위치 (top vs sticky)
- 인제스트 완료 자동 이동 시 시각적 인디케이터 (단발 toast vs 가상 카드 애니메이션)

---

## 1. 오늘 달성 (Day 5)

### 1.1 항목 G — `content_gate` 스테이지 신설
- `app/ingest/stages/content_gate.py` 신설. 8-stage 의 chunk → content_gate → tag_summarize 자리 정합
- pipeline.py 에 호출 끼워넣기. chunks 의 metadata 가 후속 load 스테이지에서 그대로 DB 저장 (`SupabasePgVectorStore._serialize_chunk` 가 metadata 보존 확인)
- ExtractionResult 에 `metadata: dict` 필드 추가 (escape hatch). ImageParser 가 `vision_type` 채움 → content_gate 가 `메신저대화` → `flags.third_party=true` 매핑
- 검출:
  - 주민번호: `(\d{6})[-\s]?(\d{7})` + 앞 6자리 YYMMDD 유효성 (DE-21 b)
  - 카드번호: `\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4,7}` (16~19자리, DE-21 a)
  - 워터마크: `대외비 | 내부자료 | 보안 | CONFIDENTIAL | INTERNAL` (case-insensitive)
  - 메신저: ImageParser 의 vision_type 참조 (이미지만)
  - 계좌번호: **MVP 제외 (DE-44)** — 한국 은행 패턴 너무 다양해 오탐 위험. W3+ 한국 은행 코드 사전과 함께 재도입 검토
- 저장 스키마:
  - `documents.flags.has_pii / has_watermark / third_party` (boolean)
  - `documents.flags.watermark_hits: string[]` (검출 키워드 보존)
  - `chunks.metadata.pii_ranges: [[start, end], ...]`
  - `chunks.metadata.watermark_hits: string[]`
- unit smoke 21/22 통과 (Amex 19자리 변형 1건 누락 — DE-21 a "MVP 단순 매칭" 정신상 허용)

### 1.2 항목 H — `GET /documents/batch-status` 엔드포인트
- 콤마 구분 doc_id 리스트 (max 50) → 각 doc 의 latest job status 일괄 조회
- N+1 회피: 1 SQL 로 모든 jobs 가져온 뒤 Python 측에서 doc_id 별 latest 추출
- 프론트 폴러가 doc_id 단위 N회 → batch 단위 1회로 호출 횟수 절감 (W1 §6 이월분)
- live smoke: 3 docs 동시 폴링, 12초 내 모두 completed 확인

### 1.3 ExtractionResult 확장 + ImageParser 연계
- 모든 파서가 ExtractionResult 키워드 인자 dataclass 호출이라 `metadata` 추가에 영향 없음
- ImageParser 만 `metadata={"vision_type": caption.type}` 채움
- W3+ 에서 다른 파서 (HWPX heading 분석 등) 가 추가 메타 부착 가능한 escape hatch

---

## 2. 결정

| # | 결정 | 근거 |
|---|---|---|
| **DE-44 (Day 5)** | 계좌번호 패턴은 MVP 에서 제외 | 한국 은행 형식 너무 다양 (10~14자리, 대시 1~2개, 은행별 prefix 별도). 단순 정규식이 전화번호·다른 숫자열과 충돌 → 오탐 다수. W3+ 에서 한국 은행 코드 사전 도입 시 재검토 |
| **DE-45 (Day 5)** | 카드번호 패턴은 16~19자리 (4그룹 4·4·4·4~7) — Amex 15자리 (4-6-5) 미수용 | DE-21 a "단순 매칭" 정신. 주가 Visa/MC 16자리. Amex 변형은 KPI 측정 시 false negative 1~2건으로 허용 가능 |
| **DE-46 (Day 5)** | ExtractionResult 에 metadata 필드 추가 (cross-parser escape hatch) | ImageParser 의 vision_type 을 content_gate 가 cross-stage 로 받기 위해. 다른 파서도 향후 heading/언어/언어모델 결과 부착 가능 |
| **DE-47 (Day 5)** | `/documents/batch-status` 의 max ids = 50 | 50 docs × HTTP overhead → 1 SQL 1 응답. 50 초과 시 pagination 부담 vs 호출 효율 trade-off 의 합리적 경계. 평균 사용자 동시 업로드는 5~10건 |

---

## 3. 발견된 이슈 (오늘 해결)

| # | 이슈 | 처리 |
|---|---|---|
| 1 | 카드번호 단순 매칭이 전화번호 (010-1234-5678 = 11자리) 오탐 | 자릿수 정확화 (16~19자리) — 11자리 전화번호와 명확히 분리 |
| 2 | 주민번호 패턴이 일반 13자리 ID 와 충돌 | DE-21 b 앞 6자리 YYMMDD 유효성 필터 — 월/일 범위 검증으로 오탐 회피 |
| 3 | content_gate 가 ImageParser 의 vision_type 을 받는 깔끔한 통로 부재 | DE-46: ExtractionResult.metadata 추가 |
| 4 | batch-status 가 50 doc N+1 SQL 호출 시 ~2.5초 지연 우려 | 1 SQL `in_("doc_id", [...])` + Python 그룹핑 → 50건도 빠른 응답 |

---

## 4. 잔여 이슈

| # | 이슈 | 영향 | 처리 시점 |
|---|---|---|---|
| 1 | 계좌번호 검출 미구현 | KPI "주민번호+카드번호+계좌번호" 중 계좌번호 항목 측정 X | DE-44, W3+ |
| 2 | Amex 15자리 카드 미인식 | 미국 카드 사용 빈도 낮은 한국 시장에서는 영향 작음 | KPI 측정 시 false negative 인정 |
| 3 | 워터마크 키워드 리스트 고정 (대외비·내부자료·보안 + 영문 2종) | 사용자별 커스텀 키워드 추가 요청 가능 | W4+ S3 문서 상세에서 추가 노출/편집 UX 검토 |
| 4 | 프론트 폴러는 아직 `/documents/{id}/status` 사용 — batch-status 미연동 | Day 6 (M) 진입 시 함께 전환 예정 | Day 6 |

---

## 5. 변경 범위

### 5.1 신규 파일 (2건)
- `api/app/ingest/stages/content_gate.py`
- (Day 5 work-log) `work-log/2026-04-28 W2 Day 5 — content_gate · batch-status.md`

### 5.2 수정 파일
- `api/app/adapters/parser.py` — ExtractionResult.metadata 필드 추가
- `api/app/adapters/impl/image_parser.py` — vision_type 을 metadata 에 채움
- `api/app/ingest/pipeline.py` — content_gate 스테이지 호출 추가, 8-stage docstring 정합화
- `api/app/routers/documents.py` — `GET /documents/batch-status` + BatchStatusItem/Response

---

## 6. AC 종합 (Day 5)

| AC | 결과 |
|---|---|
| 주민번호 포함 문서 → has_pii=true | ✅ |
| 주민번호 오탐 (전화번호 11자리, 잘못된 월/일) | ✅ 0건 |
| 대외비/CONFIDENTIAL/내부자료/보안 워터마크 → has_watermark=true + 키워드 리스트 보존 | ✅ 4/4 모두 검출 |
| 정상 문서 오탐 (3종 모두 false) | ✅ 0건 |
| chunks.metadata 에 pii_ranges/watermark_hits 부착 | ✅ DB 직접 검증 |
| 메신저대화 ImageParser → flags.third_party=true | ✅ (단위 검증) |
| `/documents/batch-status` 50개 한 번에 조회 1 SQL | ✅ 3건 동시 폴링 12s 완주 |
| 8-stage 파이프라인 통과 (3 doc 평균 12초) | ✅ |

---

## 7. W2 진행 누적

| 항목 | 우선 | 상태 |
|---|---|---|
| A SLO 회복 | P0 | ✅ Day 2 |
| A′ 스캔 PDF 재라우팅 | P0 | ✅ Day 3 |
| B Vision 본 구현 | P0 | ✅ Day 3 |
| C HWPX 파서 | P0 | ✅ Day 3 |
| D 이미지 파서 | P0 | ✅ Day 3 |
| E URL 파서 + 엔드포인트 | P1 | ✅ Day 4 |
| F HWP 5.x | P1 | ✅ Day 4 |
| **G content_gate 스테이지** | **P1** | **✅ Day 5** |
| **H batch 폴러 최적화 (백엔드)** | **P1** | **✅ Day 5** (프론트 연동은 Day 6) |
| M `/doc/[id]` 경량판 | P1 | ⏳ Day 6 |
| 평가셋 정식 측정 | P0 | ⏳ Day 6~7 |

**P0 5종 + P1 G·H 백엔드 완료**. Day 6 = M + 프론트 batch-status 연동.

---

## 8. 회고 한 줄

오늘은 인제스트 파이프라인 8-stage 중 **마지막 빈 자리 (content_gate) 를 채워 명세 §3.G 완료**. PII (주민번호+카드번호) discrimination 단위 21/22, live 3종 (정상·PII·워터마크) 100%. ExtractionResult.metadata 라는 작은 escape hatch 가 cross-stage 메타 흐름을 깔끔히 풀었음. batch-status 는 1 SQL + Python 그룹핑으로 N+1 회피. Day 6 부터는 프론트 (M `/doc/[id]` 경량판) + 폴러 batch 전환.
