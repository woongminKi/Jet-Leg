# 2026-05-02 W5 Day 2 마감 — DOCX 파서 (DE-67) ship

> W5 Day 1 마감 직후, 사용자 의존성 승인 (`python-docx`) 받고 DE-67 ship 진입.
> W4-Q-9 sniff 평가 (~1.5d 예상) 보다 빠른 ~3h 내 ship — HwpxParser 패턴 직접 재사용 효과.

## 0. TL;DR

- `python-docx==1.2.0` 의존성 추가 (사용자 승인)
- `app/adapters/impl/docx_parser.py` 신규 — HwpxParser sticky propagate 패턴 직접 재사용
- `iter_inner_content()` (python-docx 1.x) 로 paragraph + table XML 순서 보존
- 표 처리: 행/셀을 ` | ` separator 로 join → chunk_filter table_noise 룰과 자연 통합
- `extract.py` 디스패처에 `"docx": _docx_parser` 추가
- 단위 테스트 신규 **10건** — heading sticky 3 + 표 처리 3 + can_parse 2 + corrupted 1 + raw_text 1
- 회귀 0 (139 → **149/149 PASS**)
- DE-67 ship 완료, **DE-68 (PPTX)** 는 사용자 PPT 자료 + 가치 검증 후 결정 (W4-Q-9 sniff §6 정합)

## 1. 작업 4건

| # | 마일스톤 | 산출물 |
|---|---|---|
| 1 | python-docx 의존성 추가 + API smoke (iter_inner_content 검증) | `pyproject.toml` 갱신 |
| 2 | DocxParser 직접 구현 (HwpxParser 패턴 재사용) | `app/adapters/impl/docx_parser.py` |
| 3 | extract.py 디스패처 + import 추가 | `app/ingest/stages/extract.py` |
| 4 | 단위 테스트 10건 + 합성 DOCX 검증 + 회귀 | `tests/test_docx_parser.py` |

## 2. 변경 파일

| 파일 | 변경 | LOC |
|---|---|---|
| `api/pyproject.toml` + `uv.lock` | python-docx 1.2.0 추가 | (lock 자동) |
| `api/app/adapters/impl/docx_parser.py` | 신규 | +145 |
| `api/app/ingest/stages/extract.py` | DocxParser import + `_docx_parser` 인스턴스 + `_PARSERS_BY_DOC_TYPE` 추가 | +5 |
| `api/tests/test_docx_parser.py` | 신규 — 10건 | +180 |
| `work-log/2026-05-02 W5 Day 2 마감.md` | 본 문서 | (현재) |

## 3. 핵심 설계 — HwpxParser 패턴 재사용

### 3.1 heading sticky propagate (HwpxParser 동일 알고리즘)

```python
current_title: str | None = None
for content in doc.iter_inner_content():
    if isinstance(content, Paragraph):
        text = content.text.strip()
        style_name = content.style.name if content.style else None
        if _is_heading_paragraph(text, style_name):
            current_title = text
        sections.append(ExtractedSection(text=text, section_title=current_title, ...))
    elif isinstance(content, Table):
        sections.append(ExtractedSection(text=_table_to_text(content), section_title=current_title, ...))
```

### 3.2 heading 판별

- (A) `paragraph.style.name` 이 `"Heading 1~9"` / `"Title"` / `"제목"` / `"법-제목"` 등 매칭 (HwpxParser 정규식 확장)
- (B) inline 텍스트 패턴 fallback — `제 N 조 (목적)` / `부칙` / `별표 N` 등

### 3.3 표 처리

- `Table` 객체를 만나면 별도 `ExtractedSection` 생성
- 텍스트화: 행은 ` | ` join, 행 사이는 `\n`
- 빈 셀만 있는 표는 skip
- chunk_filter 의 table_noise 룰이 표 청크를 자동 마킹 가능 (의도적)

### 3.4 graceful degrade

- `iter_inner_content()` 가 python-docx 1.x 신 API → 0.x 환경에서는 paragraphs + tables 분리 fallback (순서 손실 trade-off)
- 단락/표 단위 부분 실패는 warnings 누적 + continue
- corrupted DOCX → RuntimeError wrap (HwpxParser 패턴)

## 4. 단위 테스트 (10건)

| 클래스 | 케이스 | 검증 |
|---|---|---|
| CanParseTest | docx/non-docx 확장자 | 2건 |
| HeadingStickyPropagateTest | heading propagate / no-heading / inline pattern | 3건 |
| TableExtractionTest | 표 join / 빈 표 skip / 표 title 상속 | 3건 |
| CorruptedDocxTest | invalid bytes → RuntimeError | 1건 |
| RawTextTest | raw_text concat 검증 | 1건 |

회귀: 139 → **149/149 PASS** (테스트 추가만, 기존 0 영향).

## 5. 비판적 자가 검토

1. **W4-Q-9 sniff 의 1.5d 예상 vs 실 ~3h**: HwpxParser 패턴 직접 재사용 + python-docx 의 `iter_inner_content()` 가 표·단락 순서 보존 → 본격 구현 비용 ↓. sniff 의 보수적 추정 정합.
2. **표 처리 정책 trade-off**: ` | ` separator 로 단순 텍스트화 → chunk_filter table_noise 룰이 마킹할 가능성. 페르소나 A 의 표 검색 가치는 W6+ 측정 후 정책 재검토 (예: Markdown table syntax 변환).
3. **iter_inner_content (1.x 신 API) 의존**: python-docx 0.x 환경에서는 fallback. 현재 `python-docx==1.2.0` 명시 → fallback dead branch. 의존성 down-grade 시점 까지 안전.
4. **footnote/endnote 미커버**: W4-Q-9 sniff 에서 미언급. 추후 자료 발견 시 별도 작업.
5. **합성 DOCX vs 실 자료 검증**: 단위 테스트는 합성 DOCX 만 사용. 실 사용자 자료 (회의록·보고서) 의 다양한 스타일 (사용자 정의 styleName 등) 은 사용자 자료 업로드 후 측정.

## 6. AC 매트릭스

| AC | 결과 | 충족 |
|---|---|---|
| python-docx 의존성 추가 (사용자 승인) | 1.2.0 | ✅ |
| DocxParser 작성 + heading 추출 + 표 처리 | 145 LOC | ✅ |
| extract.py 디스패처 통합 | docx 디스패치 | ✅ |
| 단위 테스트 ≥ 10건 | 10건 | ✅ |
| 회귀 0 | 139 → 149 | ✅ |
| graceful degrade (corrupted DOCX) | RuntimeError wrap | ✅ |
| 한국어 unicode 처리 | 검증 (합성 DOCX 한국어 텍스트) | ✅ |

## 7. DE 결정

| # | 결정 | 채택 | 사유 |
|---|---|---|---|
| **DE-67** | DOCX 파서 어댑터 | (a) **HwpxParser sticky propagate 패턴 재사용** | 코드 ~145 LOC + 단위 테스트 10건 으로 ship 완료. python-docx 1.x 의 `iter_inner_content` 가 paragraph + table 순서 보존 → 본격 구현 비용 < sniff 추정 |
| **DE-68** | PPTX 본격 구현 | DRAFT 유지 | 사용자 PPT 자료 + 가치 검증 후 W5 후속 결정 |

## 8. 다음 단계

### 8.1 W5 Day 3 후보

- **DE-68 평가** (사용자 PPT 자료 1건 인제스트 + sniff) — 사용자 자료 협조 필요
- **청킹 약점 4.6** (PDF 표 청크 격리) — chunk.py + chunk_filter 통합
- **청킹 약점 4.8** (종결어미 패턴 확장) — `네`/`군`/`지`/`나요?` 등 (W4 chunk.py 4.1 의 char class 추가 검토)
- **청킹 약점 4.9** (chunk_idx 추적 메타) — original_section_idx / split_part_of

### 8.2 사용자 자료 + 정성 검토 후

- 실제 DOCX 1건 인제스트 → section_title 채움 비율 + 표 청크 분포 측정
- chunk_filter table_noise 룰의 false positive 측정 (`|` separator 가 짧은 라인 + 숫자 비율 임계 충족 가능)

## 9. commit + push

| Hash | Commit |
|---|---|
| (이번 commit) | `feat(adapters)`: DOCX 파서 (DE-67) ship — HwpxParser 패턴 재사용 + iter_inner_content (W5 Day 2) |

## 10. 한 문장 요약

W5 Day 2 — `python-docx==1.2.0` 의존성 + DocxParser ship (HwpxParser sticky propagate 패턴 재사용 + `iter_inner_content` 로 paragraph + table 순서 보존), 단위 테스트 **10건 PASS** + 회귀 0 (139 → **149/149 PASS**), **DE-67 (a) heuristic-only CONFIRMED**, sniff 의 1.5d 예상 → 실 ~3h 로 단축.
