# 2026-05-03 W8 Day 3 — dedup Tier 3 e2e + debug mobile 노출

> 가성비 sprint — 한계 #26 (Tier 3 e2e 부재) + 한계 #15 (debug 모바일 미노출) 동시 회수.

---

## 0. 한 줄 요약

W8 Day 3 — 두 한계 회수 ship (`4e42101`). 단위 테스트 **186 → 188** ran (+2 Tier 3 시나리오), 회귀 0. dedup Tier 2/3 분기 e2e 완성 + mobile 사용자도 debug 토글 가능.

---

## 1. F1 — dedup Tier 3 e2e (한계 #26)

### 1.1 Tier 정의 회상

```
Tier 2: cosine ≥ 0.95            → "거의 동일한 자료" (duplicate_of)
Tier 3: 0.85 ≤ cosine < 0.95
        AND filename ratio ≥ 0.6 → "이전 버전 관계 추정" (previous_version_of)
```

### 1.2 신규 시나리오 (2건)

| 시나리오 | 설계 | 검증 |
|---|---|---|
| `test_tier3_match_marks_previous_version` | my_vec=[1,0,…], other_vec=[0.9, sqrt(0.19), 0,…] → cos≈0.9 + storage_path 유사 (`report_v1.pdf` ↔ `report_v2.pdf`) | duplicate_tier=3 + previous_version_of + filename_similarity ≥0.6 |
| `test_tier3_filename_too_different_no_match` | 같은 cos≈0.9 인데 storage_path 매우 다름 (`economy_kr.pdf` ↔ `zzzzzzzz.docx`) → filename ratio < 0.6 | match=None, flags 변경 없음 |

### 1.3 cosine 0.9 시뮬

```python
import math
my_vec = [1.0] + [0.0] * 1023
rest = math.sqrt(1.0 - 0.81)  # ≈ 0.4359
other_vec = [0.9, rest] + [0.0] * 1022
# cos(my, other) = 1*0.9 + 0*rest + ... = 0.9
```

### 1.4 dedup 분기 e2e 커버리지 (W8 Day 3 마감)

| 분기 | 시나리오 | 상태 |
|---|---|---|
| Tier 2 (cos ≥ 0.95) | `DedupTier2Test` | W8 Day 1 ship |
| Tier 3 (cos ∈ [0.85, 0.95) + filename ≥ 0.6) | `test_tier3_match_marks_previous_version` | **Day 3 신규** |
| Tier 3 미매칭 (filename < 0.6) | `test_tier3_filename_too_different_no_match` | **Day 3 신규** |
| 후보 0건 | (잠재 후속) | TBD |

---

## 2. F2 — search debug 토글 mobile 노출 (한계 #15)

### 2.1 변경 범위

`web/src/components/jet-rag/search-subheader.tsx` — Bug 버튼 className `"hidden md:inline-flex"` 제거.

### 2.2 비판적 재검토

- 모든 진단 정보를 mobile 노출 vs 핵심만? 좁은 폭 보호 vs 사용자 가시성 트레이드오프
- **결정**: Bug 토글 버튼만 mobile 노출 (핵심 기능). queryParsed badges (dense/sparse) 는 md+ 유지 — 좁은 mobile 폭에서 가로 배치 어려움
- 향후 사용자 피드백 후 dense/sparse 모바일 노출 검토

### 2.3 효과

mobile 사용자가 `?debug=1` 토글 가능 → ResultCard 펼침으로 chunk_id/idx/page/section/rrf/highlight/metadata 노출. mobile 에서도 W7 Day 1·3·4 의 메타 가치 회수.

---

## 3. 누적 KPI (W8 Day 3 마감)

| KPI | W8 Day 2 | W8 Day 3 |
|---|---|---|
| 단위 테스트 | 186 ran | **188 ran** (+2) |
| dedup e2e 커버 | Tier 2 만 | **Tier 2 + Tier 3 (match·non-match)** |
| 한계 회수 | #23 | **#15 + #26** (누적 #15·#23·#26) |
| frontend mobile UX | debug 토글 미노출 | **mobile 노출** (queryParsed 는 md+ 유지) |
| 마지막 commit | 9fafb61 | **4e42101** |

---

## 4. W8 누적 commit

| Day | commit | 본질 |
|---|---|---|
| Day 1 | `33cf821` | DE-68 PPTX ship + input_gate fix |
| Day 1 | `d0fd5a9` | doc_embed/dedup/tag_summarize e2e |
| Day 1 doc | `5704f9a` | Day 1 work-log |
| Day 2 | `9fafb61` | PPTX Vision OCR rerouting (한계 #23) |
| **Day 3** | **`4e42101`** | **Tier 3 e2e + debug mobile** |

---

## 5. 알려진 한계 (Day 3 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 32 | dedup 후보 0건 케이스 e2e 부재 | 잠재 후속 (graceful 동작은 코드상 보장) |
| 33 | mobile queryParsed badges 미노출 | 사용자 피드백 후 검토 (의도된 정책) |

---

## 6. 다음 작업 — W8 Day 4 후보

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **monitor_search_slo CI 자동화** | GitHub Actions cron yaml — 매일 baseline |
| 2 | **PPTX 텍스트 + Vision 혼합 슬라이드** | 한계 #28 보강 (텍스트 + 이미지 결합) |
| 3 | **/stats Vision OCR 사용량 가시성** | RPD cap 추적 (한계 #29) |
| 4 | **golden v0.3 placeholder 활성** | DOCX 자료 5건 누적 후 |
| 5 | **frontend ChunksStatsCard 의 filtered_breakdown 한글 라벨 누락 회수** | 한계 #18 |

**추천: monitor_search_slo CI (~1h)** — 회귀 보호 운영 인프라.

비판적 재검토:
- GitHub Actions 활성화 여부 사용자 환경 의존 → yaml 만 추가하고 사용자가 enable 결정 (CLAUDE.md 의 "사용자 협조 필요" 분류와 일치)
- 또는 더 가벼운 작업: 한계 #18 회수 (한글 라벨 fallback 명시)

---

## 7. 한 문장 요약

W8 Day 3 — dedup Tier 3 e2e (cosine 0.9 + filename 유사) + debug mobile 노출 ship. 한계 #15·#26 회수. 단위 테스트 188 ran, 회귀 0. 마지막 commit `4e42101`.
