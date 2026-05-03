# 2026-05-03 W15 Day 3 — vision_metrics + search_metrics DB write-through (한계 #34·#61·#62·#76·#81)

> Day 2 마이그레이션 005·006 SQL 위에 Python write-through 활성. graceful — 마이그레이션 미적용 시 in-memory only.

---

## 0. 한 줄 요약

W15 Day 3 — `vision_metrics` + `search_metrics` 모듈에 `_persist_to_db()` 헬퍼 ship. 마이그레이션 005·006 적용 후 자동 활성, 미적용 시 graceful (in-memory only). `JET_RAG_METRICS_PERSIST_ENABLED='0'` env 로 단위 테스트 timeout 회피. 단위 테스트 **241 → 243** ran, 회귀 0.

---

## 1. 비판적 재검토

### 1.1 write-through 위치

| 옵션 | 설계 | 결정 |
|---|---|---|
| Lock 보유 중 DB insert | 단순 | ❌ 락 시간↑ → throughput↓ |
| **Lock 해제 후 fire-and-forget** | in-memory append + DB insert 분리 | ✅ 채택 |
| 별도 worker thread / queue | 정확도↑ | ⚠ 복잡도↑ — MVP 단계 over-engineering |

### 1.2 graceful 정책

`_persist_to_db` 가 모든 Exception swallow + log debug. 이유:
- 마이그레이션 005·006 미적용 시 테이블 부재 → PGRST 에러 → swallow
- DB 장애 시 호출자 (ImageParser / search) 영향 0
- 사용자 005 적용 후 자연 회복

### 1.3 단위 테스트 timeout 문제

- 첫 시도: write-through 활성 시 단위 테스트 4s → 35s (실 supabase 시도 fail)
- 해결: `JET_RAG_METRICS_PERSIST_ENABLED` env, `tests/__init__.py` 에서 강제 "0"
- 운영 (uvicorn) 환경은 default "1" 유지

---

## 2. 구현

### 2.1 변경 파일

| 파일 | 변경 |
|---|---|
| `api/app/services/vision_metrics.py` | `record_call(error_msg=, source_type=)` 시그니처 확장 + `_persist_to_db` 헬퍼 + env gate |
| `api/app/services/search_metrics.py` | `record_search(query_text=)` 확장 + `_persist_to_db` + env gate |
| `api/app/routers/search.py` | 4 개 record_search 호출 모두 `query_text=clean_q` 명시 |
| `api/tests/__init__.py` | **신규** — env 강제 "0" 설정 |
| `api/tests/test_vision_metrics.py` | `PersistGracefulTest` 2 시나리오 (env disabled / DB failure swallow) |

### 2.2 vision_metrics 헬퍼

```python
def _persist_to_db(*, called_at, success, error_msg, quota_exhausted, source_type):
    if os.environ.get(_PERSIST_ENV_KEY, "1") == "0":
        return
    try:
        from app.db import get_supabase_client
        client = get_supabase_client()
        client.table("vision_usage_log").insert({
            "called_at": called_at.isoformat(),
            "success": success,
            "error_msg": error_msg,
            "quota_exhausted": quota_exhausted,
            "source_type": source_type,
        }).execute()
    except Exception as exc:
        logger.debug("vision_usage_log insert skip (graceful): %s", exc)
```

### 2.3 search_metrics 헬퍼 — 동일 패턴

`record_search(query_text=)` 추가 → `_persist_to_db` 가 row 1건 insert (mode/fallback/cache_hit 모두 보존).

### 2.4 search.py — query_text 전달

`sed` 로 4 record_search 호출에 `query_text=clean_q` 추가:
- line 217 (503 raise 직전)
- line 280 (rpc_rows 0건)
- line 349 (sparse-only fallback)
- line 453 (정상 응답)

---

## 3. 검증

```bash
# 신규 시나리오 (PersistGracefulTest)
uv run python -m unittest tests.test_vision_metrics
# Ran 10 tests in 0.607s — OK (8 기존 + 2 신규)

# 전체 회귀
uv run python -m unittest discover tests
# Ran 243 tests in 30.868s — OK (회귀 0)
```

라이브 활성 (사용자 액션):
1. Studio → 005·006 적용
2. uvicorn 재시작 (또는 `JET_RAG_METRICS_PERSIST_ENABLED=1` 명시 set)
3. 검색 1회 후 `SELECT count(*) FROM search_metrics_log` → 1+ 확인

---

## 4. 누적 KPI (W15 Day 3 마감)

| KPI | W15 Day 2 | W15 Day 3 |
|---|---|---|
| 단위 테스트 | 241 | **243** (+2) |
| **한계 회수 누적** | 25 | **30** (+ #34·#61·#62·#76·#81) |
| metrics 영속화 | in-memory only | **+ DB write-through (graceful)** |
| 마지막 commit | c0253a6 | (Day 3 commit 예정) |

**한계 5건 한 번에 회수** — DB 영속화 패턴 ship 으로 휘발성 trade-off 5건 (#34 / #61 / #62 / #76 / #81) 동시 해소.

---

## 5. 알려진 한계 (Day 3 신규)

| # | 한계 | 회수 시점 |
|---|---|---|
| 87 | search.py 4 record_search 호출의 query_text=clean_q — 검색어 평문 보존 (단일 사용자 MVP). 멀티 사용자 도입 시 hash 화 (DE-21) | 멀티 유저 진입 시 |
| 88 | _persist_to_db 가 동기 호출 — search 응답 latency 에 N ms 영향 (graceful swallow 라도 DB roundtrip 1회) | 비동기 큐 도입 검토 |
| 89 | tests/__init__.py 의 env 강제 "0" — pytest 도입 시 conftest.py 로 통일 | pytest 도입 시 |
| 90 | source_type 파라미터 미연결 — ImageParser caller (PptxParser 등) 가 호출 컨텍스트 알지만 record_call 에 전달 안 함 | optional 보강 |

---

## 6. 다음 작업 — W15 Day 4 (자동 진입)

| 우선 | 항목 | 사유 |
|---|---|---|
| 1 | **DB 영속화 후 추세 분석 RPC** (한계 #38 후속) | 시간 범위 / mode 별 aggregate — 마이그레이션 007 |
| 2 | **augment 본 검증** | quota 회복 |
| 3 | **OpenAI 어댑터 스왑 시연** (DoD ④) | 사용자 보류 해제 시 |
| 4 | **frontend by_mode 추세 그래프** | DB 영속화 후 시계열 시각화 |

**Day 4 자동 진입**: 토큰 cap 가까움 → W15 종합 핸드오프 우선 검토.

---

## 7. 한 문장 요약

W15 Day 3 — vision_metrics + search_metrics DB write-through ship + tests/__init__.py env gate. 단위 테스트 241 → 243 ran 회귀 0. **한계 5건 동시 회수** (#34·#61·#62·#76·#81), 누적 25 → **30**.
