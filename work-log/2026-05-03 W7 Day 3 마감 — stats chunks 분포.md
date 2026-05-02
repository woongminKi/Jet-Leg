# 2026-05-03 W7 Day 3 마감 — /stats 에 chunks 분포 (effective vs filtered)

> W7 Day 2 (lint + monitor_search_slo) 직후 Day 3 진입. 사용자 의존성 X 작업 우선.
> 인덱스 size 는 Postgres `pg_relation_size` RPC 마이그레이션 필요 (사용자 액션) → 보류.
> 대안: 마이그레이션 0건으로 chunks 분포 (effective vs filtered breakdown) 추가.

## 0. TL;DR

- `/stats` 응답에 신규 `chunks` 필드 추가 — `total / effective / filtered_breakdown / filtered_ratio`
- DE-65 후 chunks 1256 환경 실측 — **effective 744 (59.24%)** + **filtered 512 (40.76%)**
  - extreme_short: 430 (W6 Day 3 ship 효과 가시화)
  - table_noise: 65
  - header_footer: 17
- backward compatible (`chunks_total` 유지)
- 단위 테스트 회귀 0 (160/160 PASS)

## 1. 작업

| # | 마일스톤 | 산출물 |
|---|---|---|
| 1 | 비판적 재검토 — 인덱스 size 는 마이그레이션 필요 → chunks 분포로 우회 | 메인 스레드 결정 |
| 2 | `ChunksStats` 모델 + `_compute_chunks_stats` 헬퍼 | stats.py +30 LOC |
| 3 | StatsResponse 에 chunks 필드 추가 (backward compat) | +2 LOC |
| 4 | 라이브 검증 + 회귀 | 160/160 PASS |
| 5 | 본 종합 정리 | 본 문서 |

## 2. 변경 파일

| 파일 | 변경 | LOC |
|---|---|---|
| `api/app/routers/stats.py` | `ChunksStats` 모델 + StatsResponse.chunks 필드 + `_compute_chunks_stats` 헬퍼 | +37 |
| `work-log/2026-05-03 W7 Day 3 마감.md` | 본 문서 (신규) | (현재) |

## 3. 핵심 변경

### 3.1 `ChunksStats` 모델

```python
class ChunksStats(BaseModel):
    total: int                              # 전체 chunks 수 (chunks_total 와 동일)
    effective: int                          # 검색 대상 (filtered_reason IS NULL)
    filtered_breakdown: dict[str, int]      # 마킹 사유별 카운트
    filtered_ratio: float                   # 마킹 비율 (0.0 ~ 1.0)
```

### 3.2 `_compute_chunks_stats` 헬퍼

```python
def _compute_chunks_stats(supabase, chunks_total: int) -> ChunksStats:
    # filtered_reason IS NOT NULL 카운트 + flags 페이로드 fetch (사유 breakdown)
    filtered_resp = (
        supabase.table("chunks")
        .select("flags", count="exact")
        .not_.is_("flags->>filtered_reason", "null")
        .execute()
    )
    breakdown: dict[str, int] = {}
    for r in filtered_resp.data or []:
        reason = (r.get("flags") or {}).get("filtered_reason")
        if reason:
            breakdown[reason] = breakdown.get(reason, 0) + 1
    filtered_total = filtered_resp.count or 0
    effective = chunks_total - filtered_total
    return ChunksStats(...)
```

### 3.3 backward compatibility

- `chunks_total` 필드 유지 (deprecated 표시 X) — 기존 클라이언트 영향 0
- 신규 `chunks.total` = `chunks_total` 동일 값 (canonical)

## 4. 라이브 검증 (DE-65 후 chunks 1256 환경)

```json
{
  "total": 1256,
  "effective": 744,
  "filtered_breakdown": {
    "extreme_short": 430,
    "table_noise": 65,
    "header_footer": 17
  },
  "filtered_ratio": 0.4076
}
```

### 4.1 W6 Day 2 dry-run 추정 vs 실측 비교

| 카테고리 | W6 Day 2 추정 | W7 Day 3 실측 | 차이 |
|---|---:|---:|---|
| total | 1256 | 1256 | 0 |
| table_noise | ~67.4% (846/1256) | **5.2% (65/1256)** | **-62pp** |
| header_footer | ~19.2% (241/1256) | **1.4% (17/1256)** | **-17.8pp** |
| effective (W6 추정) | ~410 | **744** | +334 |

**해석**: W6 Day 2 의 G(1) 진단 휴리스틱 (`_TABLE_NOISE_SHORT_LINE_RATIO=0.70` / `_DIGIT_PUNCT_RATIO=0.50`) 은 **검색 대상 추정** 용 (느슨), 실 chunk_filter 마킹 (`0.90 / 0.70`) 은 **검색 제외** 용 (엄격). 두 휴리스틱의 임계 차이가 +60pp 차 발생.

→ W6 Day 2 의 "effective ~410" 추정은 G(1) 휴리스틱 기준이라 보수적. **실 검색 대상은 744 (대부분의 본문 청크 보존)**. 사용자 자료 누적 시 검색 효용 더 ↑ 예상.

## 5. 비판적 자가 검토

1. **인덱스 size 미노출의 trade-off**: `pg_relation_size` 는 마이그레이션 005 필요 (RPC 함수 신설). 사용자 의존성 X 룰 정합으로 보류. 마이그레이션 005 작성 후 사용자 confirm 시 ship 가능.
2. **`_compute_chunks_stats` 의 페이지네이션 부재**: 현재 chunks 1256 → 단일 fetch OK. 누적 자료 (10,000+ chunks) 시 page_size 1000 limit 도달 → 사유 breakdown 불완전 가능. 대규모 환경 진입 시 별도 RPC (group by reason) 권장. 현재는 simple wins.
3. **filtered_breakdown 의 dict order**: Python dict insertion order 보장이지만, JSON 직렬화 시 client 가 의존하면 안 됨. 클라이언트는 key set 기반 처리 권장.
4. **chunks_total 중복**: `chunks_total` (legacy) + `chunks.total` (신규) 가 동일 값. 다음 major 버전에서 `chunks_total` 제거 가능. 현재는 backward compat 우선.
5. **chunk_filter 가시성과 mismatch 가능**: `_compute_chunks_stats` 는 user_id filter 없음 — 모든 사용자 chunks 합산. 단일 사용자 MVP 환경이라 OK이지만 multi-user 시 user_id join 필요.

## 6. AC 매트릭스

| AC | 결과 | 충족 |
|---|---|---|
| chunks 분포 ChunksStats 모델 ship | +37 LOC | ✅ |
| backward compatibility (chunks_total 유지) | 동일 값 노출 | ✅ |
| filtered_breakdown 사유별 카운트 | 3 카테고리 (extreme_short / table_noise / header_footer) | ✅ |
| 라이브 검증 (chunks 1256 → effective 744) | filtered_ratio 0.4076 | ✅ |
| 회귀 0 | 160/160 PASS | ✅ |

## 7. 다음 단계 — W7 Day 4 후보

- **frontend stats 페이지 chunks 분포 시각화** — `ChunksStats` 의 effective/filtered ratio 도넛 차트 또는 stacked bar
- **마이그레이션 005 — pg_relation_size RPC** (사용자 confirm 시 ship)
- **e2e ingest mock test** — 회귀 보호 (4-5h)
- **frontend debug mode** — 마킹 chunk 옵션 노출

## 8. commit + push

| Hash | Commit |
|---|---|
| (이번 commit) | `feat(api)`: /stats 에 chunks 분포 (effective vs filtered breakdown) 추가 (W7 Day 3) |

## 9. 한 문장 요약

W7 Day 3 — `/stats` 에 신규 `chunks` 필드 (total / effective / filtered_breakdown / filtered_ratio) 추가, DE-65 후 chunks 1256 환경 실측 결과 **effective 744 (59.24%) + filtered 512 (40.76%, extreme_short 430 + table_noise 65 + header_footer 17)** — W6 Day 2 G(1) 진단 추정 (410) 보다 ↑ (검색 대상 더 풍부), 회귀 0 (160/160 PASS).
