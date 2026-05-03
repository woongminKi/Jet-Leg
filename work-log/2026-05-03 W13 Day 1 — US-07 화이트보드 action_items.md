# 2026-05-03 W13 Day 1 — US-07 화이트보드 action_items 추출 (US 8/8 완성)

> W12 핸드오프 §5.3 Option C — 유저 스토리 8/8 완성으로 DoD ① 회수.

---

## 0. 한 줄 요약

W13 Day 1 — Gemini Vision `_PROMPT` 에 화이트보드 → `structured.action_items` 명시 + ImageParser 가 별도 "액션 아이템" ExtractedSection 생성. 단위 테스트 **225 → 232** ran (+7), 회귀 0. **유저 스토리 8/8 완성** ✅.

---

## 1. 비판적 재검토

### 1.1 발견 — VisionCaption.structured 미활용

기존:
- `VisionCaption.structured: dict | None` 필드 이미 존재
- `_PROMPT` 가 명함·차트·표만 명시 (화이트보드 미커버)
- ImageParser 가 structured 활용 안 함 (caption + ocr 만 sections 생성)

→ Vision 측에서 화이트보드 prompt 추가 + ImageParser 측에서 action_items 노출 = US-07 회수.

### 1.2 list of str vs list of dict 정규화

Gemini 응답이 list of str ("보고서 작성") 또는 list of dict (`{task, owner, due_date}`) 두 형태 모두 가능. 둘 다 수용:
- str → trim + 빈 문자열 제외
- dict → values join (`task · owner · due_date` 형태)

---

## 2. 구현

### 2.1 변경 파일

| 파일 | 변경 |
|---|---|
| `app/adapters/impl/gemini_vision.py` | `_PROMPT` structured schema 에 화이트보드 case 추가 (`{action_items: [...]}`) |
| `app/adapters/impl/image_parser.py` | `_extract_action_items` 헬퍼 + structured 활용한 별도 section |
| `tests/test_image_action_items.py` | 신규 7 시나리오 |

### 2.2 핵심 로직

```python
# _PROMPT 갱신
"structured": "type 별 ... 화이트보드: {action_items: [\"항목1\", ...]} (담당자·기한 명시 시 그대로 보존). 구조화 불가 시 null"

# _extract_action_items 헬퍼
def _extract_action_items(structured):
    if not isinstance(structured, dict): return []
    raw = structured.get("action_items")
    if not isinstance(raw, list): return []
    out = []
    for item in raw:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned: out.append(cleaned)
        elif isinstance(item, dict):
            parts = [str(v).strip() for v in item.values() if v]
            if parts: out.append(" · ".join(parts))
    return out

# ImageParser.parse — 별도 ExtractedSection
action_items = _extract_action_items(caption.structured)
if action_items:
    bullet_text = "\n".join(f"- {item}" for item in action_items)
    sections.append(ExtractedSection(
        text=bullet_text, page=None,
        section_title="액션 아이템", bbox=None,
    ))
```

### 2.3 단위 테스트 (7 신규)

`ExtractActionItemsHelperTest` (4):
- list of strings (trim + 빈 제외)
- list of dicts → values join (task · owner · due_date)
- 빈/None/누락 → []
- blank strings 필터

`WhiteboardSectionTest` (3):
- 화이트보드 + action_items → "액션 아이템" 섹션 + 불릿 형식
- 문서 type + structured=None → 섹션 미생성
- 화이트보드 + action_items 누락 → 섹션 미생성

---

## 3. 유저 스토리 8/8 매트릭스 (W13 Day 1 마감)

| # | 스토리 | 상태 | 변동 |
|---|---|:---:|---|
| US-01 | 자연어 + 날짜 검색 | ✅ | (기존) |
| US-02 | 출처 배지 | ✅ | (기존) |
| US-03 | 표·이미지 역검색 | ✅ | (기존) |
| US-04 | 자동 태그 다중 필터 | ✅ | (기존) |
| US-06 | 3줄 요약 + 관점 | ✅ | (기존) |
| **US-07** | **화이트보드 액션 아이템** | ✅ | **W13 Day 1 회수** (이전 ⚠ 부분) |
| US-08 | 단일 문서 스코프 QA | ✅ | (W11 Day 4 + W12 Day 1) |
| US-09 | 숫자·엔티티 역검색 | ✅ | (기존) |

**8/8 완성** — DoD ① "유저 스토리 8건 완료" 회수.

---

## 4. 검증

```bash
uv run python -m unittest tests.test_image_action_items
# Ran 7 tests — OK

uv run python -m unittest discover tests
# Ran 232 tests in 4.769s — OK (225 → 232, 회귀 0)
```

라이브 검증은 사용자 화이트보드 사진 자료 + Gemini Vision quota 회복 시 가능.

---

## 5. 누적 KPI (W13 Day 1 마감)

| KPI | W12 Day 2 | W13 Day 1 |
|---|---|---|
| 단위 테스트 | 225 | **232** (+7) |
| **유저 스토리** | 7/8 | **8/8 ✅** |
| **DoD ① 유저 스토리 8건** | ⚠ 부분 | **✅ 충족** |
| 한계 회수 | 20 | 20 |
| 마지막 commit | ddcdb9d | (Day 1 commit 예정) |

---

## 6. 알려진 한계 (Day 1 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 72 | structured 의 다른 type (명함·차트·표) 도 활용 가능하지만 현재 화이트보드만 별도 section | 사용자 자료 누적 후 |
| 73 | action_items 는 OCR 텍스트와 중복 가능 (Vision 이 OCR 와 분리해서 추출 보장 X) | 프롬프트 명시로 완화 — 후속 검증 필요 |

---

## 7. 다음 작업 — W13 Day 2 (자동 진입)

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **하이브리드 +5pp ablation** | KPI "하이브리드 우세" 측정 (~2h) |
| 2 | **OpenAI 어댑터 스왑 시연** | DoD ④ (~3h) |
| 3 | **augment 본 검증** (한계 #48) | quota 회복 시점 |
| 4 | **monitor CI yaml** | 운영 |
| 5 | **doc 스코프 fallback UX** (한계 #68) | 사용자 피드백 |

**Day 2 자동 진입**: 하이브리드 +5pp ablation — KPI 추가 측정 가능 인프라.

---

## 8. 한 문장 요약

W13 Day 1 — 화이트보드 action_items 추출 ship (Gemini prompt + ImageParser section). 유저 스토리 **8/8 완성** ✅, DoD ① 회수. 단위 테스트 225 → 232 ran 회귀 0.
