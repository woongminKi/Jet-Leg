# 2026-05-03 W11 Day 2 — extract 분기 e2e 보강 (한계 #58·#59)

> CLAUDE.md 자율 진행 v2 적용 후 첫 sprint. extract 9/9 stage 의 분기 케이스 e2e 마감.

---

## 0. 한 줄 요약

W11 Day 2 — extract 의 HWPML 분기 + 스캔 PDF rerouting 두 e2e 시나리오 추가. 단위 테스트 **215 → 218** ran, 회귀 0. 한계 2건 회수 (#58·#59).

---

## 1. F1 — extract HWPML 분기 e2e (한계 #59)

### 1.1 변경

`ExtractHwpmlTest` 신규:
- **`test_hwpml_xml_prefix_dispatches_hwpml_parser`**: doc_type='hwp' + raw bytes 가 `<?xml ... <HWPML>` prefix → `is_hwpml_bytes` True → `HwpmlParser` dispatch. result.source_type == "hwpml".
- **`test_hwp_ole2_does_not_use_hwpml_parser`** (negative): OLE2 시그니처 (`\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1`) → HwpmlParser 미호출 (Hwp5Parser 직행). spy 패턴으로 검증.

### 1.2 합성 HWPML bytes

```python
hwpml_bytes = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<HWPML Version="2.8" ...>\n'
    '  <BODY><SECTION>\n'
    '    <P><TEXT><CHAR>e2e 검증 본문 텍스트</CHAR></TEXT></P>\n'
    '  </SECTION></BODY>\n'
    '</HWPML>'
).encode("utf-8")
```

→ `is_hwpml_bytes` 의 sniff 로직 통과 (BOM 무관 + `<?xml` 필수).

---

## 2. F2 — extract 스캔 PDF rerouting e2e (한계 #58)

### 2.1 변경

`ExtractScanPdfReroutingTest` 신규:
- 빈 1-page PDF (`fitz.open() + new_page`) → raw_text 0 → `_is_scan_pdf` True
- `_reroute_pdf_to_image` 호출 → ImageParser.parse mock 호출 카운트 1
- `documents.flags.scan=True` 마킹 검증 (DB CHECK 회피, doc_type='pdf' 유지)

### 2.2 mock 전략

```python
# ImageParser 인스턴스의 parse 메서드 mock — class-level patch
def _mock_image_parse(self_unused, data, *, file_name):
    parse_calls.append(file_name)
    return ExtractionResult(
        source_type="image",
        sections=[ExtractedSection(text="[표지] 모의 OCR", ...)],
        raw_text="[표지] 모의 OCR",
        ...
        metadata={"vision_type": "표지"},
    )

with patch.object(extract_mod, "SupabaseBlobStorage", _FakeStorage), \
     patch.object(type(extract_mod._image_parser), "parse", _mock_image_parse):
    result = run_extract_stage(job_id, doc_id)
```

→ Vision API 외부 호출 0, 가상 OCR 결과로 흐름만 검증.

### 2.3 검증 결과

- ImageParser.parse 호출 1회 (1-page PDF)
- result.source_type == "pdf" (rerouting 후에도 유지)
- raw_text 에 OCR 결과 포함
- flags.scan = True

---

## 3. e2e 9 stage 커버리지 + 분기 (W11 Day 2 마감)

| stage / 분기 | 시나리오 | 커버 시점 |
|---|---|---|
| extract DOCX dispatch | DOCX bytes → DocxParser | W10 Day 1 |
| extract 비지원 포맷 skip | xlsx → graceful skip | W10 Day 1 |
| **extract HWPML 분기** | XML prefix → HwpmlParser | **W11 Day 2** ✅ |
| **extract OLE2 분기 (negative)** | OLE2 → HwpmlParser 미호출 | **W11 Day 2** ✅ |
| **extract 스캔 PDF rerouting** | 빈 PDF → ImageParser fallback + flags.scan | **W11 Day 2** ✅ |
| chunk·chunk_filter·content_gate·load·embed·doc_embed·dedup·tag_summarize | (이전 sprint) | W7~W9 |

→ extract 모든 분기 커버 완성.

---

## 4. 누적 KPI (W11 Day 2 마감)

| KPI | W11 Day 1 | W11 Day 2 |
|---|---|---|
| 단위 테스트 | 215 ran | **218 ran** (+3) |
| 한계 회수 누적 | 17 | **19** (+ #58·#59) |
| extract 분기 커버 | 2/5 (DOCX·xlsx) | **5/5** ✅ |
| 마지막 commit | 5b25d86 | (Day 2 commit 예정) |

---

## 5. 알려진 한계 (Day 2 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 64 | 스캔 PDF max 5 페이지 cap 분기 미커버 (현재 1-page만) | 더 많은 페이지 합성 시 |
| 65 | ImageParser.parse class-level patch — 인스턴스 변경에 취약 | 안정 가정 |

---

## 6. 다음 작업 — W11 Day 3 (자동 진입)

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **monitor_search_slo CI yaml + 가이드** | 사용자 환경 가이드 |
| 2 | **MVP DoD §14.2 점검 매트릭스** | 유저 스토리·KPI 11개 진척도 시각화 |
| 3 | **augment 본 검증** (한계 #48) | quota 회복 시점 |
| 4 | **mobile 가독성** (한계 #40) | 사용자 피드백 |
| 5 | **한계 #64 스캔 PDF max 페이지 cap** | 보강 |

**Day 3 자동 진입**: monitor CI yaml 가이드 + MVP DoD 점검 — 운영 자산 마무리.

---

## 7. 한 문장 요약

W11 Day 2 — extract HWPML XML 분기 + OLE2 negative + 스캔 PDF rerouting 3 시나리오 추가. 단위 테스트 215 → 218 ran 회귀 0. 한계 2건 회수. extract 5/5 분기 커버 완성.
