# 2026-05-03 W9 Day 6 — tag_summarize fast-fail (한계 #53 회수)

> Day 4 PptxParser fast-fail 패턴을 LLM stage 에 확장. quota 감지 시 두 번째 호출 skip.

---

## 0. 한 줄 요약

W9 Day 6 — `_call_tags` quota 감지 시 `_call_summary` skip ship. `is_quota_exhausted` 를 `app.services.quota` 공통 모듈로 분리 (pptx_parser ↔ tag_summarize 의존성 정석화). 단위 테스트 **201 → 203** ran.

---

## 1. 진입 배경

W9 Day 5 §5 추천 1순위 — Day 5 의 부수 효과 발견 (Vision fast-fail → tag_summarize 살아남음) 이후, tag_summarize 자체에도 fast-fail 적용.

- tag_summarize 는 doc 당 LLM 호출 2회 (_call_tags + _call_summary)
- 첫 호출 quota 시 두 번째도 시도 → fail 누적 + LLM 비용 낭비
- Day 4 패턴 재사용으로 50% 호출 절약

---

## 2. 비판적 재검토

### 2.1 의존성 방향

| 옵션 | 설계 | 결정 |
|---|---|---|
| A | tag_summarize 가 pptx_parser 의 `_is_quota_exhausted` import | ❌ stage → adapter 의존 어색 |
| **B** | `app/services/quota.py` 공통 모듈로 분리 | ✅ 채택 |
| C | tag_summarize 안에 동일 함수 중복 정의 | ❌ DRY 위반 |

→ **B 채택**. pptx_parser 의 `_is_quota_exhausted` 도 `is_quota_exhausted` (public) 로 변경 + 동일 모듈 참조.

### 2.2 fast-fail 위치

```python
# tag_summarize.py
quota_exhausted = False
try:
    tags = _call_tags(extraction.raw_text)
except Exception as exc:
    errors.append(f"tags: {exc}")
    if is_quota_exhausted(str(exc)):
        quota_exhausted = True

if quota_exhausted:
    # _call_summary 호출 skip — LLM 비용 + 응답 시간 절약
    errors.append("summary: skipped due to quota")
else:
    try:
        summary = _call_summary(extraction.raw_text)
    except Exception as exc:
        errors.append(f"summary: {exc}")
```

graceful 정책 유지 — quota 감지로 stop 해도 파이프라인은 계속 진행 (load·embed·doc_embed·dedup 모두 진행).

---

## 3. 구현

### 3.1 신규 파일 — `app/services/quota.py`

```python
def is_quota_exhausted(error_msg: str) -> bool:
    """RESOURCE_EXHAUSTED / 429 / quota 키워드 검사."""
    if not error_msg:
        return False
    upper = error_msg.upper()
    return (
        "RESOURCE_EXHAUSTED" in upper
        or "429" in error_msg
        or "QUOTA" in upper
    )
```

### 3.2 변경 파일

| 파일 | 변경 |
|---|---|
| `app/services/quota.py` | 신규 — 공통 quota 휴리스틱 |
| `app/adapters/impl/pptx_parser.py` | `_is_quota_exhausted` 제거 → `is_quota_exhausted` import |
| `app/ingest/stages/tag_summarize.py` | quota 감지 → summary 호출 skip (50% 절약) |

### 3.3 단위 테스트 (2 신규)

| 시나리오 | 검증 |
|---|---|
| `test_quota_exhausted_skips_summary_call` | _call_tags raise "429 RESOURCE_EXHAUSTED…" → call_count 1 (이전 정책: 2) |
| `test_non_quota_failure_still_attempts_summary` | "Service temporarily unavailable" → 두 호출 모두 시도 (정책 유지) |

기존 4개 TagSummarizeGracefulTest + PptxParser 18 테스트 모두 PASS (회귀 0).

### 3.4 두 단계 quota 보호 매트릭스 (W9 Day 4 + Day 6)

| Stage | 호출 횟수 (quota 시) | Day 4·6 fix 후 |
|---|---:|---:|
| PptxParser Vision | 11 (cap 무력화 시) | **1 (fast-fail)** |
| tag_summarize LLM | 2 (tags + summary) | **1 (summary skip)** |

→ Gemini RPD 20 cap 안에서 더 많은 doc 처리 가능.

---

## 4. 검증

```bash
uv run python -m unittest tests.test_e2e_pipeline.TagSummarizeGracefulTest
# Ran 4 tests — OK

uv run python -m unittest discover tests
# Ran 203 tests in 4.013s — OK (201 → 203, 회귀 0)
```

---

## 5. 누적 KPI (W9 Day 6 마감)

| KPI | W9 Day 5 | W9 Day 6 |
|---|---|---|
| 단위 테스트 | 201 ran | **203 ran** (+2) |
| 한계 회수 누적 | 9 | **10** (+ #53) |
| Vision quota 보호 | cap + fast-fail | 동일 |
| **LLM quota 보호** | 미도입 | **fast-fail (summary skip)** |
| 마지막 commit | a0d7d05 | (Day 6 commit 예정) |

---

## 6. 알려진 한계 (Day 6 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 54 | doc_embed 의 BGE-M3 호출도 RPD 영향 — HF 무료 티어 별개라 quota 영향 작음 | HF 의 RPD 모니터링 필요 시 |
| 55 | tag_summarize 의 _call_tags 가 두 번째 호출(summary) 보다 먼저 quota 발생 가정 | 실제 호출 순서가 변동되면 fast-fail 효과 변동 |

---

## 7. 다음 작업 — W9 Day 7+ 후보

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **augment 본 검증** (한계 #48) | quota 일일 reset 후 재 reingest |
| 2 | **VisionUsageCard 한계 #38** | API quota header 직접 파싱 (W10+) |
| 3 | **mobile 가독성** (한계 #40) | 사용자 피드백 후 |
| 4 | **CI 첫 실행 결과 확인** (한계 #44) | 사용자 GH Actions 직접 |
| 5 | **search debug mode mobile fallback badge** | 한계 #33 |

**추천: augment 본 검증 (~10분, quota 회복 시점에)** — Day 1·3·4·6 누적 효과 종합 검증.

비판적 재검토: quota 회복은 시간대 의존이라 즉시 재시도가 아닌 *시간 진행 후 재시도*가 합리적. 본 sprint 에서는 마감 timing 적절.

---

## 8. 한 문장 요약

W9 Day 6 — tag_summarize fast-fail ship. is_quota_exhausted 를 app.services.quota 공통 모듈로 분리 + tag_summarize 의 두 번째 LLM 호출 skip (quota 감지 시). 단위 테스트 201 → 203 ran 회귀 0. 한계 #53 회수.
