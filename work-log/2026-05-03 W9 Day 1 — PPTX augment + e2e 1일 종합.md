# 2026-05-03 W9 Day 1 — PPTX 텍스트+Vision augment + e2e 1일 종합 smoke

> W8 종합 §4.3 Option A 진입. 한계 #28 (PPTX 혼합 슬라이드) 회수 + 사용자 자료 누적 후 정량 검증.

---

## 0. 한 줄 요약

W9 Day 1 — PPTX **augment 모드** 추가 (`c7a7f98`). 텍스트 < 50자 슬라이드는 image OCR 결합으로 정보량↑. 단위 테스트 **195 → 198** ran. e2e 1일 종합 smoke — documents **11건** / chunks **1509** / failed 0 / 검색 cache hit p50 **219ms**.

---

## 1. F1 — PPTX augment 모드 (한계 #28 회수)

### 1.1 비판적 재검토

| 옵션 | 설명 | 결정 |
|---|---|---|
| A | threshold 도입 (텍스트 < N자면 OCR 추가) | ✅ 채택 — 단순, RPD 절약 |
| B | 항상 OCR 결합 | ❌ RPD cap 빨리 소진 |
| C | 사용자 토글 | ❌ 복잡도↑ |

→ A 채택, threshold = **50자**.

### 1.2 두 모드 통합

```python
# pptx_parser.py
current_text_len = sum(len(p) for p in slide_text_parts)
needs_ocr = (
    self._image_parser is not None
    and vision_slides_used < _MAX_VISION_SLIDES
    and current_text_len < _VISION_AUGMENT_TEXT_THRESHOLD
)
if needs_ocr:
    ocr_text = _vision_ocr_largest_picture(...)
    if ocr_text:
        vision_slides_used += 1
        if not slide_text_parts:
            # rerouting (W8 Day 2): OCR 만 사용
            slide_title = slide_title or f"p.{slide_idx + 1} (Vision OCR)"
            slide_text_parts = [ocr_text]
        else:
            # augment (W9 Day 1 신규): 기존 텍스트 + OCR 결합
            slide_text_parts = [*slide_text_parts, ocr_text]
```

| 모드 | 조건 | 결과 |
|---|---|---|
| skip | text ≥ 50자 또는 image_parser=None | 기존 텍스트만 사용, OCR 호출 0 |
| augment (신규) | 0 < text < 50 + image 있음 + cap 안 | 기존 텍스트 + OCR 결합 |
| rerouting (W8 Day 2) | text 0 + image 있음 + cap 안 | OCR 만 사용 |

### 1.3 단위 테스트 (3 신규)

| 시나리오 | 검증 |
|---|---|
| `test_short_text_triggers_augment` | "디자인 컨셉 표지 슬라이드" (18자) + Picture → OCR 1회 + 결합 텍스트 |
| `test_long_text_skips_augment` | 100+ 자 텍스트 → OCR 호출 0 |
| `test_augment_respects_max_cap` | 6 슬라이드 짧은 텍스트 → 첫 5개 augment, 6번째 텍스트만 |

### 1.4 검증

- 기존 12 PptxParser 테스트 모두 PASS (rerouting mode 회귀 0)
- 신규 3건 PASS — **15 / 198 ran**, 회귀 0

---

## 2. F2 — e2e 1일 종합 smoke

### 2.1 documents 분포

```
total: 11 / failed: 0
by_doc_type: {md: 2, pdf: 4, hwpx: 2, docx: 2, pptx: 1}
```

사용자 자료 **모두 인제스트 성공** — 9 stage chain 안정성 검증.

### 2.2 chunks 분포

```json
{
  "total": 1509,
  "effective": 997,
  "filtered_breakdown": {"extreme_short": 430, "table_noise": 65, "header_footer": 17},
  "filtered_ratio": 0.3393
}
```

- W6 1256 → **1509** (+253, DOCX 2건·PPTX 1건·기타 누적)
- effective 745 → **997** (+252, 새 자료 대부분 정상)
- filtered_ratio 0.4076 → **0.3393** (정상 자료 추가로 비율 정상화)

### 2.3 검색 smoke (6 query)

| q | total | took_ms (cold) | dense | sparse | fused |
|---|---:|---:|---:|---:|---:|
| GPU | 5 | 564 | 50 | 1 | 50 |
| 계약 | 5 | 480 | 43 | 8 | 50 |
| **태양계** | **1** | 499 | 44 | 42 | 50 |
| **삼국시대** | **1** | 458 | 48 | 44 | 50 |
| **브랜딩** | **4** | 784 | 50 | 0 | 50 |
| 청소년 | 6 | 435 | 49 | 3 | 50 |

**사용자 자료 모두 검색 매칭**:
- 태양계 → 승인글 템플릿1.docx (DE-67 검증)
- 삼국시대 → 승인글 템플릿3.docx
- 브랜딩 → 브랜딩_스튜디오앤드오어.pptx (PPTX OCR 1 chunk 매칭, DE-68 검증)

### 2.4 SLO

| 단계 | p50_ms | p95_ms | cache_hit_rate |
|---|---:|---:|---:|
| cold 6건 | 480 | 564 | 0.0 |
| warm 6건 (재호출) | **219** | 564 | 0.5 |

- **자체 목표 500ms 회수** (cache hit 시 p50 219ms)
- p95 564ms — cold 1회 영향, 절대 목표 3s 충분히 안
- fallback 0 — HF Inference 안정

### 2.5 vision_usage

서버 reload 후 0 (W8 Day 4 휘발성 정책 — 한계 #34). PPTX reingest 시 누적되는 것은 W8 Day 2 검증.

---

## 3. 누적 KPI (W9 Day 1 마감)

| KPI | W8 Day 6 | W9 Day 1 |
|---|---|---|
| 단위 테스트 | 195 ran | **198 ran** (+3 augment) |
| documents 분포 | 9 (mock 기준) | **11 (실 자료)** |
| chunks total | 1256 | **1509** |
| 검색 cache hit p50 | 169ms | **219ms** (warm 6건 평균) |
| 한계 회수 | 6건 (W8) | **+ #28 (W9)** = 7건 누적 |
| 마지막 commit | 6b0d099 | **c7a7f98** |

---

## 4. 알려진 한계 (Day 1 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 41 | augment threshold 50자 — 휴리스틱, 자료 다양성 따라 조정 필요 | 사용자 피드백 후 |
| 42 | augment + rerouting 합산 cap (max 5) — 자료가 큰 PPT 에서 부족 | RPD 한도 시 |
| 43 | Day 2 PPTX reingest 의 chunk 1 - augment 모드 도입 후 재실행 시 chunk 증가 가능 | 다음 reingest 검증 |

---

## 5. 다음 작업 — W9 Day 2 후보

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **PPTX 자료 reingest — augment 효과 측정** | 한계 #43 — Day 2 reingest 결과 (chunks 1) 가 augment 후 증가 검증 |
| 2 | **monitor_search_slo CI yaml** | GitHub Actions cron — yaml 만 추가 후 사용자 enable |
| 3 | **VisionUsageCard 한계 #38 보강** | API quota header 직접 파싱 |
| 4 | **mobile 가독성 (한계 #40)** | 사용자 피드백 누적 후 |
| 5 | **Ragas 평가 통합** | 사용자 의존성 승인 |

**추천: PPTX reingest (~10분, 가성비↑)** — Day 1 augment ship 의 사용자 자료 검증 회수.

---

## 6. 한 문장 요약

W9 Day 1 — PPTX augment 모드 ship (`c7a7f98`, threshold 50자) + e2e 1일 종합 smoke. 단위 테스트 198 ran 회귀 0, documents 11건 / chunks 1509, 사용자 자료 모두 검색 매칭, cache hit p50 219ms.
