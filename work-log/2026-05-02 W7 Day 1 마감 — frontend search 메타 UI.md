# 2026-05-02 W7 Day 1 마감 — frontend search 메타 UI 노출

> W6 Day 5 (search 응답 메타 강화) 직후 W7 Day 1 진입. 백엔드 ship 한 메타가 사용자 면에서
> 활용 안 되면 가치 절반 → frontend UI 노출 우선 ship.

## 0. TL;DR

- `MatchedChunk` 타입에 `rrf_score` + `metadata` 옵셔널 필드 추가 (backward compatible)
- `ResultCard` 결과 카드에 두 시각화 추가 — 청크 우상단 배지
  - **`↻ overlap`** 배지 — `metadata.overlap_with_prev_chunk_idx` 가 있을 때 (4.4 효과)
  - **`rrf 0.0xxx`** mono 폰트 — RRF 점수 (검색 ranking 근거)
- `SearchSubheader` 에 검색 경로 진단 배지 — `dense N · sparse N` + `fallback_reason` 시
- type check + lint 통과 (사전 결함 1건 무관)
- 라이브 dev 서버 검증 — `?q=test` 응답에 `rrf` + `overlap` 키워드 노출 확인

## 1. 작업

| # | 마일스톤 | 산출물 |
|---|---|---|
| 1 | web/AGENTS.md 의 Next.js 16 신 API 룰 확인 | "NOT the Next.js you know" 룰 정합 작업 |
| 2 | `web/src/lib/api/types.ts` MatchedChunk 확장 (rrf_score / metadata) | +6 LOC |
| 3 | `result-card.tsx` 청크 우상단 메타 배지 추가 | +24 / -10 LOC |
| 4 | `search-subheader.tsx` queryParsed prop + dense/sparse 배지 | +28 / -2 LOC |
| 5 | `search/page.tsx` SearchSubheader 에 queryParsed 전달 | +1 LOC |
| 6 | type check + lint + dev 라이브 검증 | tsc 0 error, lint 사전결함 1건 |
| 7 | 본 종합 정리 | 본 문서 |

## 2. 변경 파일

| 파일 | 변경 | LOC |
|---|---|---|
| `web/src/lib/api/types.ts` | MatchedChunk + rrf_score + metadata 옵셔널 | +6 |
| `web/src/components/jet-rag/result-card.tsx` | matched_chunks 우상단 메타 배지 (overlap, rrf) | +24 / -10 |
| `web/src/components/jet-rag/search-subheader.tsx` | queryParsed prop + dense/sparse/fallback 배지 | +28 / -2 |
| `web/src/app/search/page.tsx` | SearchSubheader 에 queryParsed 전달 | +1 |
| `work-log/2026-05-02 W7 Day 1 마감.md` | 본 문서 (신규) | (현재) |

## 3. UI 디자인 결정

### 3.1 ResultCard 청크 우상단 배지

```
┌─────────────────────────────────────────────────┐
│ p.5 · 휴관일 (좌) ............. ↻ overlap rrf 0.0327 (우) │
│ 청크 본문 텍스트 (highlight 적용)...                │
└─────────────────────────────────────────────────┘
```

- 좌: 기존 (page + section_title)
- 우: 신규 (overlap badge + rrf score)
- mono 폰트로 숫자 정렬 — `font-mono tabular-nums`
- `title` 속성으로 hover tooltip — "이전 청크 idx N 와 100자 prefix overlap" / "RRF score (검색 ranking 근거)"
- 옵셔널 필드라 backward compatible (W6 Day 5 이전 응답에선 미표시)

### 3.2 SearchSubheader 검색 경로 진단

```
[← 홈] [🔍 검색바] [10개 결과 · 0.16초] [dense 47] [sparse 3]
```

- dense/sparse 배지: outline (정상) / destructive (실패) / secondary (없음)
- fallback_reason 있을 때만 destructive 배지로 추가 — sparse-only fallback 진입 visible
- `md:inline-flex` — 모바일에선 숨김 (좁은 폭 우선순위 ↓)

### 3.3 정보 위계 (디자인 결정)

| 우선순위 | 시각 강도 | 노출 |
|---|---|---|
| 가장 중요 (사용자 행동 영향) | 큰 폰트 + 색 강조 | 결과 카드 제목, 본문 highlight |
| 중요 (의사결정 보조) | 보통 폰트 + outline | 관련도 %, 태그, page/section_title |
| 디버깅/투명성 (선택 검토) | 작은 폰트 + 흐림 | rrf score, overlap badge, dense/sparse 카운트 |

→ 디버깅 정보가 본문 가독성을 해치지 않도록 `text-[9px]` + `text-muted-foreground` 로 흐리게.

## 4. 비판적 자가 검토

1. **시각 노이즈 risk**: 청크 우상단에 배지 2개 추가 → 좁은 화면에서 좌측 page/section_title 가 truncate 될 수 있음. `min-w-0` + `truncate` 로 처리.
2. **rrf_score 가독성**: `0.0327` 같은 4자리 소수가 일반 사용자에 의미 있는가? — 디버깅/투명성 목적, 일반 사용자는 무시 가능 (작은 폰트 + 흐림). 향후 사용자 자료 누적 시 0~1 정규화 검토.
3. **overlap badge 의도성**: 모든 idx > 0 청크에 overlap 메타 표시됨 (W4 Day 3 의 단순화). 정확하게는 split 인접만 overlap. 사용자가 "↻ overlap" 보고 "이 청크가 분할됐구나" 판정 가능. trade-off 수용.
4. **lint 사전 결함**: `use-doc-job-status.ts` 의 `react-hooks/set-state-in-effect` 1건 — 본 작업 무관. W7+ 별도 처리.
5. **모바일 미노출**: query_parsed 배지가 md+ 만 노출 → 모바일에서 검색 경로 진단 불가. trade-off 수용 (모바일 우선순위 ↓).
6. **Next.js 16 정합**: `searchParams: Promise<{q?: string}>` (이미 search/page.tsx 적용) + `'use client'` 직접 적용 (search-subheader). AGENTS.md 룰 정합.

## 5. AC 매트릭스

| AC | 결과 | 충족 |
|---|---|---|
| MatchedChunk 타입에 rrf_score + metadata 추가 | +6 LOC | ✅ |
| ResultCard 에 시각화 (overlap badge + rrf score) | +14 LOC | ✅ |
| SearchSubheader 에 query_parsed 시각화 | dense/sparse/fallback 배지 | ✅ |
| type check 통과 (`tsc --noEmit`) | 0 error | ✅ |
| 라이브 dev 검증 (rendered HTML 에 새 필드 노출) | grep `rrf|overlap` 6 hit | ✅ |
| backward compatible (옵셔널 필드만) | rrf_score / metadata `?:` | ✅ |
| 모바일 가독성 회귀 0 | `md:inline-flex` 로 좁은 화면 노이즈 차단 | ✅ |

## 6. commit + push

| Hash | Commit |
|---|---|
| (이번 commit) | `feat(web)`: 검색 결과 카드에 rrf score + overlap 메타 + dense/sparse 진단 노출 (W7 Day 1) |

## 7. 다음 단계 — W7 Day 2 후보

- **e2e ingest mock test** — 회귀 보호 강화 (4-5h, 의존성 0)
- **lint 사전 결함 (`react-hooks/set-state-in-effect`) 회수** — trivial
- **frontend 추가 개선** — extreme_short / table_noise 마킹 chunk 의 검색 결과 visual indicator (현재는 자동 제외라 노출 안 됨, 디버깅 모드 옵션 검토)

## 8. 한 문장 요약

W7 Day 1 — W6 Day 5 의 search 응답 메타 (rrf_score / metadata / query_parsed) 가 frontend 의 ResultCard 우상단 배지 + SearchSubheader 진단 배지로 시각화 ship, type check 통과 + 라이브 검증 (`?q=test` rendered HTML 에 rrf/overlap 노출 확인), backward compatible (옵셔널 필드만).
