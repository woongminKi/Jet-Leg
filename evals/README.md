# evals — KPI 측정 평가셋

> W2 스프린트 KPI 측정 시드 + W22 마감 시점 진척 + DoD ②③ Ragas 진입 가이드.
> **상태 (W22 마감)**: golden v0.3 ship (top-1 100%, 20/20) — `golden_batch_smoke.py` 활용. Ragas 미도입 (DoD ②③ 차단).

## 디렉토리

| 경로 | 용도 | 상태 (W22 마감) |
|---|---|---|
| `hwpx_samples/` | HWPX 파서 성공률 측정 | W2 Day 1 시드 (.gitkeep). 사용자 자료 누적 후 활성 |
| `vision_samples/` | Vision 캡셔닝 정확도 측정 | `expected.schema.json` 보유. 메신저 스샷 10 + 문서 스샷 10 사용자 누적 대기 |
| `pdf_samples/` | PDF 성공률 + 스캔 PDF 재라우팅 | W1 smoke 3건 + W15 Day 1 스캔 PDF cap e2e |

## 성공 정의

### HWPX (명세 §3.C)

10건 중 9건 이상이 [S1~S3] 전부 충족해야 통과 (≥ 0.9):

- **[S1]** `chunks` 테이블에 1 row 이상 생성
- **[S2]** chunk 평균 길이 ≥ 200자 (조사·한자 보존 지표)
- **[S3]** `section_title` 이 chunks 중 ≥ 30% 에 채워짐 (헤딩 추출)

### Vision (명세 §3.B)

`min(분류 정확도, OCR 정확도) ≥ 0.85`.

- **분류 정확도**: `VisionCaption.type == expected.type` 건수 / 전체
- **OCR 정확도**: 숫자·고유명사 오독만 "실패" 로 카운트 (전문 누락은 경고만 — §12.3 "2등 시민" 원칙)

### PDF (명세 §1.2)

W2 범위는 SLO 회복 smoke (3건) + 스캔 PDF 재라우팅 검증 1건. 정식 98% KPI 측정은 W5 이월.

## 데이터 출처 가이드라인

- **공공 자료만** — 저작권 이슈 회피 (국회 의안 정보시스템, 기재부 보도자료, 공공데이터포털)
- 민감 정보 없는 익명 데이터
- 파일 크기: 각 파일 10MB 이하 (repo 부피 관리)
- 모든 샘플에 **출처 URL 을 메타 파일로 병기** (CSV 또는 jsonl)

## 기대값 스키마 (Vision)

`vision_samples/expected.schema.json` 참조. 각 샘플은 `expected.jsonl` 에 한 줄:

```json
{"filename": "msg_01.png", "type": "메신저대화", "ocr_ground_truth": "홍길동: 오늘 3시...", "notes": ""}
```

## 비워두는 방침

Day 1 은 디렉토리 + 스키마만. 실제 샘플 수집은 W2 Day 2 아침에 30분~1시간. 커밋 크기 제어를 위해 대용량 이미지·HWPX 는 별도 PR 로 분리 관리 검토.

---

## W22 시점 — 사용자 액션 가이드 (Ragas 진입)

### DoD ②③ 차단 해소 절차

**1단계: 의존성 승인**

```bash
cd api && uv add ragas datasets
```

비용:
- `ragas` ~10 MB + 의존성 (`datasets`, `pandas`, `numpy`)
- 사용자 묵시 승인 필요 (외부 의존성 0 정책 변경)

**2단계: 평가 데이터셋 45건 누적**

기획서 §3 페르소나 A 자료 분포:
- HWP/HWPX 10건 — 공공기관·법률·내규
- PDF 10건 — 보고서·논문·매뉴얼
- 스크린샷 15건 — 메신저·화이트보드·문서
- DOCX 10건 — 브리핑·보고서

각 자료당 **3 QA 페어** (총 135 QA) — golden_batch_smoke 의 G-001~G-020 패턴 확장.

**3단계: `evals/run_ragas.py` 신규 작성**

```python
# Ragas 통합 — 5 metric: faithfulness / answer_relevancy / context_recall / context_precision / answer_correctness
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall

# golden_v0.4.csv (135 QA) 로드 → /search 호출 → context · answer 누적 → ragas evaluate
```

**4단계: `make eval` 통합** (DoD ③)

```makefile
eval:
\tcd api && uv run python evals/run_ragas.py --output ../work-log/ragas-result.md
```

### 현재 회귀 보호 (Ragas 도입 전)

`api/scripts/golden_batch_smoke.py` 가 빠른 회귀 검증 도구. W21 Day 1 강화:

```bash
cd api
uv run python scripts/golden_batch_smoke.py --mode all --require-top1-min 0.85
```

CI 통합 가능 — `--require-top1-min` exit 1 임계 미달 시 fail.

### 데이터셋 누적 진행 상태

W22 마감 시점:
- HWPX: 0 (사용자 자료 대기)
- PDF: 5 (smoke 3 + golden v0.3 일부)
- 스크린샷: 0
- DOCX: 0 (golden v0.3 G-021~G-025 placeholder)

**총 진척: 11 / 45 (24%)** — 사용자 자료 누적 차단.
