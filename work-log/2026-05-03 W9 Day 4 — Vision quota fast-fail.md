# 2026-05-03 W9 Day 4 — Vision quota fast-fail (한계 #49 회수)

> Day 3 cap fix 의 짝 — quota 초과 즉시 감지 + 이후 슬라이드 skip 으로 cap 5회 호출도 절약.

---

## 0. 한 줄 요약

W9 Day 4 — `_vision_ocr_largest_picture` 가 `(text, quota_exhausted)` tuple 반환. RESOURCE_EXHAUSTED / 429 / quota 키워드 감지 시 caller 가 break. 단위 테스트 **199 → 201** ran (+2 fast-fail 시나리오), 회귀 0. Day 3 cap (5회) 위에 두 단계 보호.

---

## 1. 진입 배경

W9 Day 3 fix 후에도 잔여 risk:
- cap 시도 카운트 = 5 → quota 초과 시 5회 헛 호출
- 첫 호출에서 RESOURCE_EXHAUSTED 받으면 나머지 4회는 *예측 가능한* 실패
- → fast-fail 로 4회 절약 (5/5 → 1/5)

---

## 2. 비판적 재검토

| 옵션 | 설계 | 결정 |
|---|---|---|
| A. tuple 반환 (text, quota_exhausted) | 명확한 신호, caller 가 break | ✅ 채택 |
| B. PptxParser 가 RuntimeError 메시지 직접 검사 | 함수 시그니처 변경 X | ❌ fragile (호출 흐름 분산) |
| C. 별도 QuotaExhausted exception | 정통 pattern | ⚠ ImageParser/Vision 인터페이스 광범위 수정 |

→ A 채택. `_vision_ocr_largest_picture` 의 반환 확장만으로 충분.

### 2.1 quota 키워드 감지

`_is_quota_exhausted(error_msg: str) -> bool`:
- `"RESOURCE_EXHAUSTED"` (Gemini SDK 표준)
- `"429"` (HTTP code)
- `"QUOTA"` (대문자 무시 — 광범위 보호)

---

## 3. 구현

### 3.1 `_vision_ocr_largest_picture` 반환 확장

```python
def _vision_ocr_largest_picture(...) -> tuple[str | None, bool]:
    ...
    except Exception as exc:
        msg = str(exc)
        warnings.append(...)
        if _is_quota_exhausted(msg):
            return None, True  # ← caller 에 신호
        return None, False
    text = (result.raw_text or "").strip()
    return (text or None), False
```

### 3.2 PptxParser parse() fast-fail

```python
vision_quota_exhausted = False
for slide_idx, slide in enumerate(prs.slides):
    needs_ocr = (
        self._image_parser is not None
        and not vision_quota_exhausted  # ← W9 Day 4 신규
        and vision_slides_attempted < _MAX_VISION_SLIDES
        and current_text_len < _VISION_AUGMENT_TEXT_THRESHOLD
    )
    if needs_ocr:
        vision_slides_attempted += 1
        ocr_text, quota_exhausted = _vision_ocr_largest_picture(...)
        if quota_exhausted:
            vision_quota_exhausted = True
            warnings.append(f"PPTX Vision quota 감지 — slide {N} 이후 skip")
        if ocr_text:
            ...
```

### 3.3 단위 테스트 (2 신규)

| 시나리오 | 검증 |
|---|---|
| `test_quota_exhausted_fast_fail` | 11 slides + ImageParser raise "429 RESOURCE_EXHAUSTED..." → parse_calls **1회** (cap 5 미적용까지 stop) |
| `test_429_in_message_triggers_fast_fail` | "HTTP 429 Too Many Requests" 메시지 → 1회 stop |

기존 Day 3 `test_failure_respects_cap_quota_protection` — 메시지를 "Service temporarily unavailable" 로 변경 (quota 키워드 미포함) → cap 5회 동작 분리 검증 유지.

### 3.4 두 단계 보호 매트릭스

| 시나리오 | Day 3 cap (시도 기준) | Day 4 fast-fail | 호출 횟수 |
|---|:---:|:---:|---:|
| 정상 (모두 success) | ✓ 5회 | — | 5 |
| 일반 fail (예: 5xx) | ✓ 5회 | — | 5 |
| **quota 초과 (429)** | ✓ 5회 | **✓ 1회 stop** | **1** |
| 첫 N개만 fail | ✓ | 비활성 | 5 |

→ quota 케이스에서 4회 절약 (80%↓). 다른 fail 케이스는 Day 3 cap 정책 유지.

---

## 4. 검증

```bash
uv run python -m unittest tests.test_pptx_parser
# Ran 18 tests in 0.149s — OK (16 + 2 신규)

uv run python -m unittest discover tests
# Ran 201 tests in 4.824s — OK (199 → 201, 회귀 0)
```

---

## 5. 누적 KPI (W9 Day 4 마감)

| KPI | W9 Day 3 | W9 Day 4 |
|---|---|---|
| 단위 테스트 | 199 ran | **201 ran** (+2) |
| 한계 회수 | 7 + #47 | **+ #49** = 9건 누적 (#15·#23·#26·#28·#29·#32·#37·#47·#49) |
| Vision quota 보호 레이어 | 1 (cap 시도) | **2 (cap + fast-fail)** |
| 마지막 commit | 317b663 | (Day 4 commit 예정) |

---

## 6. 알려진 한계 (Day 4 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 50 | _is_quota_exhausted 휴리스틱 — 메시지 형식 변경 시 감지 실패 가능 | google.api_core.exceptions.ResourceExhausted 직접 catch (W10+) |
| 51 | fast-fail flag 슬라이드 단위 — 같은 reingest 안에서 quota 회복은 미감지 | 정상 trade-off (reingest 단위로 결정) |

---

## 7. 다음 작업 — W9 Day 5 후보

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **PPTX reingest 재시도** | quota 회복 후 augment + cap + fast-fail 모두 본 검증 (한계 #48) |
| 2 | **VisionUsageCard 한계 #38 보강** | API quota header 직접 파싱 |
| 3 | **mobile 가독성 (한계 #40)** | 사용자 피드백 후 |
| 4 | **e2e ingest 9 stage 마지막 1 (extract) e2e** | parser 단위 테스트 외 통합 흐름 검증 |
| 5 | **CI 첫 실행 결과 확인** (한계 #44) | 사용자 GitHub Actions 페이지 |

**추천: PPTX reingest 재시도 (한계 #48 회수)** — Day 1·3·4 누적 효과 본 검증.

---

## 8. 한 문장 요약

W9 Day 4 — Vision quota fast-fail ship. _vision_ocr_largest_picture 반환을 (text, quota_exhausted) tuple 로 확장 + RESOURCE_EXHAUSTED/429/quota 키워드 감지. 단위 테스트 199 → 201 ran 회귀 0. Day 3 cap (5) 위에 두 단계 보호.
