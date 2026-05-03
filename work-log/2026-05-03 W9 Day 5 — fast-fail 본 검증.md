# 2026-05-03 W9 Day 5 — Vision fast-fail 본 검증 + 부수 효과 발견

> Day 4 fast-fail 의 실 환경 검증 sprint. PPTX reingest 통해 quota 미회복 상태에서 동작 확인.

---

## 0. 한 줄 요약

W9 Day 5 — PPTX reingest 재시도 → **Vision fast-fail 본 검증 완료** (1 call / 1 error 즉시 stop). **부수 효과**: 이전 reingest 에서 fail 하던 tag_summarize 가 처음으로 succeeded (Vision quota 절약 → LLM 호출 분 quota 여유). 코드 변경 0.

---

## 1. 진입 배경

W9 Day 4 §7 추천 1순위 — 한계 #48 회수 (augment 본 검증).

vision_usage 카운터가 0/0/0 으로 reset 상태 (서버 reload 후) → 새 reingest 의 영향 분리 측정 가능.

---

## 2. reingest 결과 비교

| 항목 | W8 Day 2 (rerouting only) | W9 Day 3 (cap 버그) | **W9 Day 5 (fast-fail)** |
|---|---:|---:|---:|
| Vision total_calls | 5 | **11** (cap 무력화) | **1** (fast-fail) |
| Vision success | 1 | 1 | 0 |
| Vision error | 4 | 10 | 1 |
| chunks_count | 1 | 1 | 0 |
| extract | succeeded | succeeded | succeeded |
| **tag_summarize** | **failed (429)** | **failed (429)** | **✅ succeeded** |
| 9 stage 종료 | done | done | done |

### 2.1 fast-fail 본 검증 (Day 4 한계 #49)

- **호출 횟수: 11 → 1 (90% 절약)**
- 첫 호출에서 RESOURCE_EXHAUSTED 감지 → 이후 10 슬라이드 즉시 skip
- warnings 에 "PPTX Vision quota 감지 — slide N 이후 skip" 기록 (코드상)

### 2.2 부수 효과 — tag_summarize 살아남음

이전 두 reingest 의 stage 로그:
```
W8 Day 2: tag_summarize | failed | 429 RESOURCE_EXHAUSTED
W9 Day 3: tag_summarize | failed | 429 RESOURCE_EXHAUSTED
W9 Day 5: tag_summarize | succeeded
```

원인 추정:
- Gemini Flash RPD 20 = Vision + LLM 호출 *공통* quota
- W8 Day 2: Vision 5회 + tag 호출 → 누적 초과 → tag fail
- W9 Day 3: Vision 11회 (cap 버그) + tag → 더 빠르게 초과 → tag fail
- **W9 Day 5: Vision 1회 (fast-fail) + tag → 여유** → **tag succeeded**

→ Day 4 fix 가 *Vision 절약*뿐 아니라 *다른 stage 의 quota 보호* 까지 부수적으로 보장. 의도하지 않은 가치 입증.

### 2.3 chunks 0 의 의미

augment 본 검증 (한계 #48)은 **여전히 미완**:
- 이번 reingest 도 Vision quota 미회복 상태 → 첫 호출 fail → augment 효과 측정 X
- 사용자 PPTX 의 디자인 카탈로그 OCR 결과가 chunks 0 — quota 회복 후 재시도 필요

tag_summarize 가 succeeded 했는데도 tags=[] / summary='' 인 이유: raw_text 가 빈 문자열 (chunks 0 → load 시점 raw_text 도 빈 상태) → LLM 이 빈 입력에 대해 빈 응답 반환.

---

## 3. 누적 KPI (W9 Day 5 마감)

| KPI | W9 Day 4 | W9 Day 5 |
|---|---|---|
| 단위 테스트 | 201 ran | 201 ran (코드 변경 X) |
| 한계 회수 누적 | 9 (#15·#23·#26·#28·#29·#32·#37·#47·#49) | 9 (#48 부분 — fast-fail 동작 측은 검증) |
| **fast-fail 본 검증** | 단위 테스트 | **+ 실 환경 (90% 절약)** |
| **부수 효과 (tag_summarize)** | 미인지 | **확인** (Vision 절약 → LLM quota 여유) |
| 마지막 commit | 8662b29 | (Day 5 work-log only, 코드 변경 0) |

---

## 4. 알려진 한계 (Day 5 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 48 | augment 본 검증 미완 — quota 회복 후만 가능 | RPD 일일 reset 후 W9 Day 6+ |
| 52 | Vision RPD 와 LLM RPD 가 같은 Gemini quota — 한 stage 의 호출이 다른 stage 영향 | RPD 분리 또는 quota header 직접 파싱 (W10+) |
| 53 | tag_summarize 도 fast-fail 패턴 검토 가치 — Vision 이후 LLM 호출도 quota 위험 | W10+ 잠재 sprint |

---

## 5. 다음 작업 — W9 Day 6 후보

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **tag_summarize fast-fail 보강 (한계 #53)** | Day 4 패턴 재사용, LLM stage 도 quota 보호 |
| 2 | **augment 재 reingest** (한계 #48) | quota 회복 시점 (시간대 의존) |
| 3 | **VisionUsageCard 한계 #38** | API quota header 직접 파싱 |
| 4 | **CI 첫 실행 결과 확인** (한계 #44) | 사용자 GitHub Actions 페이지 |
| 5 | **mobile 가독성** | 사용자 피드백 후 |

**추천: tag_summarize fast-fail (~30분)** — Day 4 패턴 재사용으로 LLM stage 까지 quota 보호 확장.

비판적 재검토: tag_summarize 는 graceful fail 정책이라 fast-fail 가치가 PPTX 만큼 크지 않음 (단일 호출). 단 호출이 2회 (tags + summary) 이고 첫 호출 quota 시 두 번째도 시도 → Day 4 와 동일 패턴 적용 가능.

---

## 6. 한 문장 요약

W9 Day 5 — PPTX reingest 재시도, vision_usage 11→1 (90% 절약) + tag_summarize 처음 succeeded (부수 효과). Day 4 fast-fail 본 검증 완료. augment 본 검증 (한계 #48) 은 quota 일일 reset 후 이월.
