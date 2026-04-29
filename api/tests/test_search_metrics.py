"""W3 Day 2 Phase 3 — `search_metrics` ring buffer 단위 테스트.

외부 의존성 0 (stdlib + app.services 만). Supabase env 없이도 실행됨.
"""

from __future__ import annotations

import unittest

from app.services import search_metrics


class SearchMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        # 모듈 레벨 ring 은 프로세스 전역 — 각 테스트 간 격리 위해 reset.
        search_metrics.reset()

    def tearDown(self) -> None:
        search_metrics.reset()

    def test_empty_ring_returns_none_percentiles(self) -> None:
        slo = search_metrics.get_search_slo()
        self.assertEqual(slo["sample_count"], 0)
        self.assertIsNone(slo["p50_ms"])
        self.assertIsNone(slo["p95_ms"])
        self.assertIsNone(slo["avg_dense_hits"])
        self.assertEqual(slo["fallback_count"], 0)
        # breakdown 은 항상 3개 키 노출 (0 이라도) — 프론트가 키 존재 가정 가능.
        self.assertEqual(
            set(slo["fallback_breakdown"].keys()),
            {"transient_5xx", "permanent_4xx", "none"},
        )
        self.assertEqual(slo["fallback_breakdown"]["none"], 0)

    def test_p50_p95_nearest_rank(self) -> None:
        # 100, 200, ..., 1000 (10건). p50 idx=int(0.5*9)=4 → 500, p95 idx=int(0.95*9)=8 → 900.
        for ms in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000):
            search_metrics.record_search(
                took_ms=ms,
                dense_hits=5,
                sparse_hits=3,
                fused=8,
                has_dense=True,
                fallback_reason=None,
            )
        slo = search_metrics.get_search_slo()
        self.assertEqual(slo["sample_count"], 10)
        self.assertEqual(slo["p50_ms"], 500)
        self.assertEqual(slo["p95_ms"], 900)
        self.assertAlmostEqual(slo["avg_dense_hits"], 5.0)
        self.assertAlmostEqual(slo["avg_sparse_hits"], 3.0)
        self.assertAlmostEqual(slo["avg_fused"], 8.0)
        self.assertEqual(slo["fallback_count"], 0)
        self.assertEqual(slo["fallback_breakdown"]["none"], 10)
        self.assertEqual(slo["fallback_breakdown"]["transient_5xx"], 0)

    def test_fallback_breakdown_counts(self) -> None:
        # 정상 2건 + transient 1건 + permanent 1건
        for _ in range(2):
            search_metrics.record_search(
                took_ms=100, dense_hits=1, sparse_hits=1, fused=1,
                has_dense=True, fallback_reason=None,
            )
        search_metrics.record_search(
            took_ms=500, dense_hits=0, sparse_hits=2, fused=2,
            has_dense=False, fallback_reason="transient_5xx",
        )
        search_metrics.record_search(
            took_ms=50, dense_hits=0, sparse_hits=0, fused=0,
            has_dense=False, fallback_reason="permanent_4xx",
        )
        slo = search_metrics.get_search_slo()
        self.assertEqual(slo["sample_count"], 4)
        self.assertEqual(slo["fallback_count"], 2)
        self.assertEqual(slo["fallback_breakdown"]["transient_5xx"], 1)
        self.assertEqual(slo["fallback_breakdown"]["permanent_4xx"], 1)
        self.assertEqual(slo["fallback_breakdown"]["none"], 2)

    def test_ring_overflow_keeps_only_recent(self) -> None:
        # maxlen=500 이므로 510건 record 후 마지막 500건만 유지되는지 — 그 중 가장 오래된 took_ms 가 11.
        for ms in range(1, 511):
            search_metrics.record_search(
                took_ms=ms, dense_hits=0, sparse_hits=0, fused=0,
                has_dense=True, fallback_reason=None,
            )
        slo = search_metrics.get_search_slo()
        self.assertEqual(slo["sample_count"], 500)
        # took_ms 11..510 → p50 idx=int(0.5*499)=249 → 11+249=260, p95 idx=int(0.95*499)=474 → 11+474=485
        self.assertEqual(slo["p50_ms"], 260)
        self.assertEqual(slo["p95_ms"], 485)


if __name__ == "__main__":
    unittest.main()
