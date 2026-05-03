# 2026-05-03 W10 Day 1 — extract e2e + FakeSupabaseClient .count 보강

> CLAUDE.md 자율 진행 원칙 적용 후 첫 sprint. e2e 9 stage 완전 커버 + 인프라 보강.

---

## 0. 한 줄 요약

W10 Day 1 — `_FakeQueryResponse.count` 보강 (한계 #20) + extract stage e2e 2 시나리오 추가 (한계 #19). **e2e 9/9 stage 완전 커버**. 단위 테스트 **210 → 212** ran, 회귀 0.

---

## 1. 진입 배경

W9 Day 8 핸드오프 §5.3 Option A 작업 중 한계 #19·#20 회수 — e2e 인프라 마무리 sprint.

CLAUDE.md 자율 진행 원칙 적용 후:
- 비판적 재검토로 후보 가성비 평가 (가장 ROI 높은 작업 자동 선택)
- 결정 사항은 commit·work-log 명시 (사후 가시성)

---

## 2. F1 — FakeSupabaseClient `.count` 보강 (한계 #20)

### 2.1 변경

```python
class _FakeQueryResponse:
    __slots__ = ("data", "count")  # ← count 추가

    def __init__(self, data, count=None):
        self.data = data
        self.count = count  # PostgREST select(count="exact") 응답


# _FakeTableQuery.select 시그니처 확장
def select(self, cols="*", *, count=None):
    self._op = "select"
    self._select_cols = cols
    self._count_mode = count
    return self


# _exec_select — limit 적용 *전* row 수 채움
count_value = len(out) if self._count_mode else None
if self._limit is not None:
    out = out[:self._limit]
return _FakeQueryResponse(out, count=count_value)
```

### 2.2 효과

`stats.py::_compute_chunks_stats` 같은 코드의 패턴 (`select("flags", count="exact")`) 을 e2e 에서 검증 가능. 향후 stats 라우터 e2e 추가 시 인프라 준비됨.

---

## 3. F2 — extract stage e2e (한계 #19)

### 3.1 변경 파일

| 파일 | 변경 |
|---|---|
| `tests/test_e2e_pipeline.py` | E2EBaseTest patches 12곳으로 확장 (+ `app.ingest.stages.extract.get_supabase_client`) |
| 〃 | `ExtractDocxTest` 신규 — DOCX dispatch 정상 흐름 |
| 〃 | `ExtractUnsupportedTest` 신규 — 비지원 포맷 (xlsx) graceful skip |

### 3.2 `ExtractDocxTest.test_docx_dispatch_returns_extraction`

```python
# 합성 DOCX bytes — 외부 sample 의존성 0
docx_doc = docx.Document()
docx_doc.add_paragraph("e2e 검증 본문 텍스트입니다.")
buf = io.BytesIO(); docx_doc.save(buf); docx_bytes = buf.getvalue()

# SupabaseBlobStorage.get mock — patch.object(extract_mod, "SupabaseBlobStorage", ...)
class _FakeStorage:
    def get(self, path: str) -> bytes:
        return docx_bytes

with patch.object(extract_mod, "SupabaseBlobStorage", _FakeStorage):
    result = extract_mod.run_extract_stage(job_id, doc_id)

# 검증
assert result.source_type == "docx"
assert "e2e 검증 본문" in result.raw_text
assert "extract_skipped" not in doc_row["flags"]
```

### 3.3 `ExtractUnsupportedTest.test_unsupported_format_marks_skipped`

- documents.doc_type='xlsx' (`_PARSERS_BY_DOC_TYPE` 미등록)
- `run_extract_stage` 결과: None (graceful skip)
- `flags.extract_skipped=True` + reason 마킹
- `flags.extract_skipped_reason` 에 "xlsx" 포함

---

## 4. e2e 9 stage 커버리지 (W10 Day 1 마감 시점)

| stage | 시나리오 | 커버 시점 |
|---|---|---|
| **extract** | DOCX dispatch + xlsx skip | **W10 Day 1** ✅ |
| chunk | 정상 + chunk_filter 마킹 | W7 Day 5 |
| chunk_filter | (chunk 와 통합 시나리오) | W7 Day 5 |
| content_gate | PII + 워터마크 + flags 머지 | W7 Day 6 |
| tag_summarize | 정상·LLM fail·quota fast-fail | W7 Day 6, W9 Day 6 |
| load | 정상 + empty | W7 Day 5 |
| embed | 정상 + dense_vec 1024 | W7 Day 5 |
| doc_embed | summary / raw_text fallback / skip | W8 Day 1 |
| dedup | Tier 2 / Tier 3 / 후보 0건 | W8 Day 1, W9 Day 3, W8 Day 6 |

→ **9/9 stage 통합 흐름 회귀 보호 완성**.

---

## 5. 검증

```bash
uv run python -m unittest tests.test_e2e_pipeline
# Ran 17 tests — OK (15 + 2 신규)

uv run python -m unittest discover tests
# Ran 212 tests in 4.194s — OK (210 → 212, 회귀 0)
```

---

## 6. 누적 KPI (W10 Day 1 마감)

| KPI | W9 Day 8 | W10 Day 1 |
|---|---|---|
| 단위 테스트 | 210 ran | **212 ran** (+2) |
| e2e 9 stage 커버 | 8/9 | **9/9** ✅ |
| 한계 회수 누적 | 11 | **13** (+ #19·#20) |
| 마지막 commit | ae27a71 | (Day 1 commit 예정) |

---

## 7. 알려진 한계 (Day 1 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 58 | extract e2e 의 스캔 PDF rerouting (`_reroute_pdf_to_image`) 미커버 | Vision mock 추가 후 |
| 59 | extract e2e 의 HWPML 분기 (`is_hwpml_bytes`) 미커버 | HWPML 합성 bytes 후 |

---

## 8. 다음 작업 — W10 Day 2 후보

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **monitor_search_slo CI 보강** | 사용자 환경 의존 부분 가이드 |
| 2 | **augment 본 검증** (한계 #48) | quota 회복 시점 |
| 3 | **debug UI 가독성** (한계 #16) | font-mono 10px → 11~12px |
| 4 | **VisionUsageCard 한계 #38** | API quota header 직접 파싱 |
| 5 | **stats router e2e** | F1 의 count 보강 활용 |

**추천: stats router e2e + debug UI 가독성** — F1 자산 회수 + 사용자 가시성 보강.

---

## 9. 한 문장 요약

W10 Day 1 — FakeSupabaseClient .count 보강 + extract e2e (DOCX dispatch + xlsx skip) ship. e2e **9/9 stage 완전 커버 완성**. 단위 테스트 210 → 212 ran 회귀 0. 한계 2건 회수 (#19·#20).
