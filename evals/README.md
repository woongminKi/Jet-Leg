# evals — W2 평가셋 (시드)

> W2 스프린트 KPI 측정용 평가 데이터. W5 45문서/135QA Ragas 평가셋은 별도.

## 디렉토리

| 경로 | 용도 | W2 Day 1 시드 | W2 Day 2 수집 목표 |
|---|---|---|---|
| `hwpx_samples/` | HWPX 파서 성공률 측정 | `.gitkeep` | 공공기관 공개 HWPX 10건 (국회 의안 · 기재부 보도자료 등) |
| `vision_samples/` | Vision 캡셔닝 정확도 측정 | `expected.schema.json` | 메신저 스샷 10 + 문서 스샷 10 + 기대값 `expected.jsonl` |
| `pdf_samples/` | PDF 성공률 + 스캔 PDF 재라우팅 | — | W1 smoke 3건 + 스캔 PDF 1건 + 혼재 PDF 1건 |

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
