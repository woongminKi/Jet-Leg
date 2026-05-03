# 2026-05-03 W15 Day 1 — 스캔 PDF max 페이지 cap e2e (한계 #64 회수)

> Day 4 §6 추천 작은 한계 회수 sprint. DB 영속화 (Option A ~3h) 대신 가성비 작업.

---

## 0. 한 줄 요약

W15 Day 1 — `ExtractScanPdfReroutingTest.test_scan_pdf_respects_max_5_page_cap` 신규 시나리오 ship. 6-page 스캔 PDF → 첫 5 페이지만 ImageParser 호출 + warning 검증. 단위 테스트 **240 → 241** ran, 회귀 0. 한계 #64 회수.

---

## 1. 비판적 재검토

### 1.1 Option A vs 작은 sprint

| 옵션 | 비용 | 위험 |
|---|---|---|
| Option A: DB 영속화 (vision_usage / search_slo) | ~3h | 마이그레이션 + 사용자 적용 의존, 토큰 부담↑ |
| **Option C: 작은 sprint 묶음** | ~30분 | 메인 스레드 단독 ship, 회귀 risk 0 |

→ Option C 채택. DB 영속화는 W15 Day 2+ 에 분할 (마이그레이션 SQL 만 작성 → 사용자 적용 → Python write-through).

### 1.2 한계 #64 의 의도

`_MAX_SCAN_PAGES=5` 가 Vision API 비용 cap (Gemini Flash RPD 20 무료 티어). 5 페이지 초과 PDF 도 첫 5 페이지만 OCR + warning 명시.

W11 Day 2 e2e (`test_scan_pdf_reroutes_to_image_parser`) 는 1-page PDF만 → cap 동작 미커버.

---

## 2. 구현

### 2.1 변경 파일

| 파일 | 변경 |
|---|---|
| `api/tests/test_e2e_pipeline.py` | `test_scan_pdf_respects_max_5_page_cap` 신규 시나리오 |

### 2.2 시나리오 핵심

```python
# 6 페이지 빈 PDF (스캔본 시뮬, cap 5 초과)
pdf_doc = fitz.open()
for _ in range(6):
    pdf_doc.new_page(width=595, height=842)

# ImageParser.parse mock — page 단위 호출 추적
def _mock_image_parse(self_unused, data, *, file_name):
    parse_calls.append(file_name)
    return ExtractionResult(...)

with patch.object(extract_mod, "SupabaseBlobStorage", _FakeStorage), \
     patch.object(type(extract_mod._image_parser), "parse", _mock_image_parse):
    result = extract_mod.run_extract_stage(job_id, doc_id)

# 검증
assert len(parse_calls) == 5  # cap 적용
for i in range(1, 6):
    assert any(f"page{i}" in name for name in parse_calls)
assert not any("page6" in name for name in parse_calls)  # page6 skip
assert any("6페이지" in w and "5페이지" in w for w in result.warnings)
```

### 2.3 cap 정책 코드 (extract.py:191~194)

```python
process_count = min(total_pages, _MAX_SCAN_PAGES)  # 5
if total_pages > _MAX_SCAN_PAGES:
    msg = (
        f"스캔 PDF {total_pages}페이지 중 첫 {_MAX_SCAN_PAGES}페이지만 처리 "
        "(Vision API 비용 cap)"
    )
    warnings.append(msg)
```

→ 코드 변경 0 (기존 cap 동작 유지). 본 sprint 는 e2e 회귀 보호만 추가.

---

## 3. 검증

```bash
uv run python -m unittest tests.test_e2e_pipeline.ExtractScanPdfReroutingTest
# Ran 2 tests — OK (1 기존 + 1 신규)

uv run python -m unittest discover tests
# Ran 241 tests in 5.296s — OK (240 → 241, 회귀 0)
```

---

## 4. 누적 KPI (W15 Day 1 마감)

| KPI | W14 Day 5 | W15 Day 1 |
|---|---|---|
| 단위 테스트 | 240 | **241** (+1) |
| 한계 회수 누적 | 24 | **25** (+ #64) |
| 마지막 commit | 4ee8f14 | (Day 1 commit 예정) |

---

## 5. 다음 작업 — W15 Day 2 (자동 진입)

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **DB 영속화 마이그레이션 005·006 SQL** (한계 #34·#62·#76·#81) | 사용자 적용 대기 — 마이그레이션 ship |
| 2 | **augment 본 검증** (한계 #48) | quota 회복 |
| 3 | **mode 별 SLO frontend by_mode mini-row 정확도 검증** | 작은 polish |

**Day 2 자동 진입**: DB 영속화 마이그레이션 SQL 작성 — 사용자 Studio direct apply 대기.

---

## 6. 한 문장 요약

W15 Day 1 — 6-page 스캔 PDF cap (5 페이지) e2e 시나리오 신규. 단위 테스트 240 → 241 ran 회귀 0. 한계 #64 회수.
