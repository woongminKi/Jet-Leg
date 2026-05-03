# 2026-05-03 W14 Day 2 — monitor search SLO CI yaml + 가이드

> W8 Day 2 §6 부터 누적 추천된 monitor_search_slo CI 자동화 — 사용자 환경 의존성 가이드 명시 후 ship.

---

## 0. 한 줄 요약

W14 Day 2 — `.github/workflows/monitor-search-slo.yml` 신규 ship. workflow_dispatch (수동) + schedule (commented out) + secrets 가이드. monitor 스크립트는 `JET_RAG_API_BASE` env 지원으로 외부 배포 backend 가리킴 가능. backend 회귀 0.

---

## 1. 비판적 재검토

### 1.1 옵션

| 옵션 | 비용 | 결정 |
|---|---|---|
| **A. yaml + workflow_dispatch + 가이드** | 30분 | ✅ 채택 — 사용자 액션 명시 |
| B. CI 환경에 backend 시작 (Supabase secrets) | 큰 복잡도 | ❌ 사용자 환경 의존 |
| C. workflow 미도입 (사용자가 직접 cron) | 0 | ❌ 핸드오프 §5 W8~W13 추천 묵힘 |

### 1.2 backend URL 결정

monitor 스크립트가 `_BASE = "http://localhost:8000"` 하드코딩 → CI 환경에서 동작 X.

**fix**: `JET_RAG_API_BASE` env 지원 — 사용자가 secrets / vars 로 외부 backend URL 전달.

```python
_BASE = os.environ.get("JET_RAG_API_BASE", "http://localhost:8000").rstrip("/")
```

→ local 동작 보존 + CI / cron 활용 가능.

---

## 2. 구현

### 2.1 변경 파일

| 파일 | 변경 |
|---|---|
| `api/scripts/monitor_search_slo.py` | `_BASE` 가 `JET_RAG_API_BASE` env 지원 — local default 보존 |
| `.github/workflows/monitor-search-slo.yml` | **신규** — workflow_dispatch + 주석 schedule + warmup input + artifact upload |
| `README.md` | CI 섹션 갱신 — monitor 가이드 4단계 명시 |

### 2.2 workflow 설계

```yaml
on:
  workflow_dispatch:
    inputs:
      warmup: { type: boolean, default: false }
  # schedule:
  #   - cron: "0 2 * * *"  # 매일 02:00 UTC = 11:00 KST

jobs:
  monitor:
    if: ${{ vars.JET_RAG_API_BASE != '' || secrets.JET_RAG_API_BASE != '' }}
    env:
      JET_RAG_API_BASE: ${{ secrets.JET_RAG_API_BASE || vars.JET_RAG_API_BASE }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3 (python 3.12)
      - run: uv sync --frozen (api dir)
      - run: uv run python scripts/monitor_search_slo.py [--warmup]
      - upload-artifact: search-slo-snapshot-${run_id} (work-log markdown, 30d retention)
```

### 2.3 사용자 액션 4단계 (README 가이드)

1. `Settings → Secrets → JET_RAG_API_BASE` 추가 (배포된 backend URL)
2. `Settings → Actions → Workflow permissions: Read and write` (필요 시)
3. yaml 의 `schedule` 주석 해제 (매일 자동) **또는** Actions 탭 수동 실행
4. 결과는 artifact 로 30일 보관

secrets 미설정 시 workflow 자체가 skip — 다른 CI 영향 0.

### 2.4 local 사용 패턴 보존

```bash
cd api && uv run python scripts/monitor_search_slo.py            # localhost:8000 기본
JET_RAG_API_BASE=https://api.example.com uv run python scripts/monitor_search_slo.py --warmup
```

---

## 3. 검증

```bash
# env 변수 override 동작 검증
JET_RAG_API_BASE=http://localhost:9999 uv run python -c "from scripts.monitor_search_slo import _BASE; print(_BASE)"
# → http://localhost:9999

cd api && uv run python -m unittest discover tests
# Ran 236 tests in 4.301s — OK (회귀 0)
```

GitHub Actions yaml 자체는 push 후 GitHub 가 평가 — local 검증은 syntax 만 (`actionlint` 미도입).

---

## 4. 누적 KPI (W14 Day 2 마감)

| KPI | W14 Day 1 | W14 Day 2 |
|---|---|---|
| 단위 테스트 | 236 | 236 |
| CI workflow | 1 (ci.yml) | **2 (+ monitor-search-slo.yml)** |
| **한계 #44 / W8 Day 2 추천** | 활성 | **회수** (사용자 enable 후 자동) |
| 마지막 commit | 9e3ba28 | (Day 2 commit 예정) |

---

## 5. 알려진 한계 (Day 2 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 80 | secrets 미설정 시 workflow skip — 사용자가 enable 안 하면 가시성 0 | 사용자 액션 |
| 81 | artifact 30일 retention — 장기 추세 추적 불가 | DB 영속화 (한계 #34·#76) |
| 82 | actionlint local 검증 미도입 — yaml 문법 오류는 GitHub 에서만 발견 | actionlint pre-commit 검토 |

---

## 6. 다음 작업 — W14 Day 3 (자동 진입)

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **OpenAI 어댑터 스왑 시연** | DoD ④ (~3h) |
| 2 | **augment 본 검증** | quota 회복 |
| 3 | **mode 별 SLO 분리** (한계 #77) | 정확도 |
| 4 | **doc 스코프 fallback UX** (한계 #68) | 사용자 피드백 |

**Day 3 자동 진입**: OpenAI 어댑터 스왑 시연 — DoD ④ 회수 가성비↑ (잔여 핵심 가치).

---

## 7. 한 문장 요약

W14 Day 2 — monitor-search-slo.yml + JET_RAG_API_BASE env 지원 ship + README 가이드 4단계. workflow 2개 (ci + monitor) 누적. backend 회귀 0.
