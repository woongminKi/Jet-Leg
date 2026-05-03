# 2026-05-03 W10 Day 3 — search_metrics.reset() 정리 + nested metadata pretty

> 작은 한계 두 개 묶음 sprint — 자율 진행 원칙 적용 후 가성비↑.

---

## 0. 한 줄 요약

W10 Day 3 — search_metrics.reset() 호출 정리 (한계 #61 — `reset()` 함수가 이미 존재했음) + ChunkDebugPanel nested metadata indent 2 + pre-wrap 가독성 개선 (한계 #17). 단위 테스트 213 ran 그대로, 회귀 0. 한계 2건 회수.

---

## 1. F1 — search_metrics.reset() 호출 정리 (한계 #61)

### 1.1 발견

W10 Day 2 work-log §4 한계 #61: "search_metrics._ring.clear() 직접 호출 — 외부 reset API 부재".

비판적 재검토 — 코드 직접 확인:
```python
# api/app/services/search_metrics.py:142
def reset() -> None:
    """테스트 전용 — ring buffer 비움. 운영 코드에서 호출하지 말 것."""
    with _lock:
        _ring.clear()
```

→ `reset()` API **이미 존재**. test_e2e_pipeline.py 의 setUp 에서 직접 `_ring.clear()` 호출하던 것이 잘못 — public API 사용으로 변경.

### 1.2 변경

```python
# 이전 (W10 Day 2)
search_metrics._ring.clear()  # noqa: SLF001 — 테스트 시점 격리

# 이후 (W10 Day 3)
search_metrics.reset()
```

→ noqa 주석 제거 + 캡슐화 회복.

---

## 2. F2 — nested metadata pretty (한계 #17)

### 2.1 변경

`ChunkDebugPanel` 의 metadata row 처리 — `MetaRow` 서브 컴포넌트로 분리:

```tsx
function MetaRow({ k, value }) {
  const isComplex =
    (typeof value === 'object' && value !== null) || Array.isArray(value);
  const formatted = isComplex
    ? JSON.stringify(value, null, 2)  // ← indent 2
    : JSON.stringify(value);          // primitive 한 줄
  return (
    <div className={isComplex ? 'pl-3' : 'flex gap-2 pl-3'}>
      <span className={...}>{k}</span>
      <span className={isComplex
        ? 'block whitespace-pre-wrap break-all rounded bg-muted/40 px-1.5 py-0.5 text-[10px]'
        : 'break-all'}>{formatted}</span>
    </div>
  );
}
```

### 2.2 효과

| 케이스 | 이전 (W10 Day 2) | 이후 |
|---|---|---|
| primitive (string, number) | 한 줄 | 한 줄 (변동 X) |
| array `[1, 2, 3]` | `[1,2,3]` 한 줄 | indent 2 줄바꿈 (긴 배열 가독성↑) |
| object `{a: 1, b: {c: 2}}` | 한 줄 깊게 nested | indent 2 + bg-muted 박스 |

`whitespace-pre-wrap` + `bg-muted/40` 박스로 nested 구조 시각적으로 분리.

### 2.3 비판적 재검토

| 옵션 | 결정 |
|---|---|
| yaml-like 변환 | ❌ 라이브러리 의존성↑ |
| 항상 indent 2 | ❌ primitive 도 줄바꿈되어 컴팩트 손실 |
| **isComplex 분기** | ✅ 채택 — primitive 컴팩트 유지 + nested 만 펼침 |

### 2.4 검증

- tsc 0 error · lint 0 error
- 기존 ResultCard 회귀 0 (단순 컴포넌트 추가)
- backend 213 ran (변경 없음)

---

## 3. 누적 KPI (W10 Day 3 마감)

| KPI | W10 Day 2 | W10 Day 3 |
|---|---|---|
| 단위 테스트 | 213 ran | 213 ran (변경 X) |
| 한계 회수 누적 | 14 | **16** (+ #17·#61) |
| ChunkDebugPanel 가독성 | 11px + contrast↑ | + nested metadata 펼침 |
| 마지막 commit | c987cdf | (Day 3 commit 예정) |

---

## 4. 알려진 한계 (Day 3 신규)

없음.

---

## 5. 다음 작업 — W10 Day 4 후보

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **augment 본 검증** (한계 #48) | quota 회복 시점 |
| 2 | **VisionUsageCard 한계 #38** | API quota header (~2h) |
| 3 | **monitor_search_slo CI yaml** | 사용자 환경 가이드 |
| 4 | **mobile 가독성** (한계 #40) | 사용자 피드백 |
| 5 | **W10 종합 핸드오프** | 다음 세션 진입 자료 |

**추천: VisionUsageCard 한계 #38 보강** — 큰 작업이지만 quota 정확도 본질적 개선.

비판적 재검토: Gemini SDK 가 quota 응답에 어떤 header / metadata 노출하는지 직접 확인 필요. SDK 문서 참고. 본 sprint 토큰 cap 가까워지면 종합 핸드오프로 전환.

---

## 6. 한 문장 요약

W10 Day 3 — search_metrics.reset() public API 사용 정리 + ChunkDebugPanel nested metadata indent 2 + pre-wrap. 단위 테스트 213 ran 회귀 0. 한계 2건 회수 (#17·#61).
