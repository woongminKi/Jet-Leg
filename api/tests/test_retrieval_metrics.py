"""W25 D14+1 (E) — retrieval_metrics 단위 테스트.

Recall@K / MRR / nDCG@K 계산 정확성 + edge case (빈 입력 / 정답 없음).
stdlib unittest 만 — 외부 의존성 0.
"""

from __future__ import annotations

import math
import unittest


class RecallAtKTest(unittest.TestCase):
    def test_perfect_recall(self) -> None:
        from app.services.retrieval_metrics import recall_at_k
        # 정답 [1, 2, 3] 모두 top-3 안에 있음
        self.assertEqual(recall_at_k([1, 2, 3, 4, 5], {1, 2, 3}, k=10), 1.0)

    def test_partial_recall(self) -> None:
        from app.services.retrieval_metrics import recall_at_k
        # 정답 3개 중 1개 잡힘 → 1/3
        self.assertAlmostEqual(recall_at_k([1, 99, 98], {1, 2, 3}, k=10), 1 / 3)

    def test_no_relevant_returns_zero(self) -> None:
        from app.services.retrieval_metrics import recall_at_k
        self.assertEqual(recall_at_k([1, 2, 3], set(), k=10), 0.0)

    def test_k_caps_predictions(self) -> None:
        from app.services.retrieval_metrics import recall_at_k
        # k=2 면 top-2 만 봄 — [1, 99] 중 1만 hit → 1/3
        self.assertAlmostEqual(recall_at_k([1, 99, 2, 3], {1, 2, 3}, k=2), 1 / 3)

    def test_empty_predictions(self) -> None:
        from app.services.retrieval_metrics import recall_at_k
        self.assertEqual(recall_at_k([], {1, 2}, k=10), 0.0)


class MRRTest(unittest.TestCase):
    def test_first_hit_at_rank_1(self) -> None:
        from app.services.retrieval_metrics import mrr
        self.assertEqual(mrr([1, 99, 98], {1, 2, 3}, k=10), 1.0)

    def test_first_hit_at_rank_3(self) -> None:
        from app.services.retrieval_metrics import mrr
        self.assertAlmostEqual(mrr([99, 98, 1], {1}, k=10), 1 / 3)

    def test_no_hit_returns_zero(self) -> None:
        from app.services.retrieval_metrics import mrr
        self.assertEqual(mrr([99, 98, 97], {1, 2}, k=10), 0.0)

    def test_hit_after_k_returns_zero(self) -> None:
        from app.services.retrieval_metrics import mrr
        # k=2 안에 정답 없음 → 0 (rank 3 의 정답 무시)
        self.assertEqual(mrr([99, 98, 1], {1}, k=2), 0.0)


class NDCGTest(unittest.TestCase):
    def test_perfect_ranking_returns_one(self) -> None:
        from app.services.retrieval_metrics import ndcg_at_k
        # 정답 [1, 2, 3] 이 top-3 에 정확히 = IDCG 와 동일 → 1.0
        self.assertAlmostEqual(ndcg_at_k([1, 2, 3, 99, 98], {1, 2, 3}, k=10), 1.0)

    def test_no_relevant_returns_zero(self) -> None:
        from app.services.retrieval_metrics import ndcg_at_k
        self.assertEqual(ndcg_at_k([1, 2, 3], set(), k=10), 0.0)

    def test_known_value_calculation(self) -> None:
        """ranking [1, 99, 2] / relevant {1, 2} / k=3 → DCG = 1/log2(2) + 0 + 1/log2(4)
        = 1.0 + 0.5 = 1.5. IDCG (정답 2개 ideal) = 1/log2(2) + 1/log2(3) ≈ 1.6309.
        nDCG ≈ 1.5 / 1.6309 ≈ 0.9197.
        """
        from app.services.retrieval_metrics import ndcg_at_k
        result = ndcg_at_k([1, 99, 2], {1, 2}, k=3)
        expected = (1.0 + 1.0 / math.log2(4)) / (1.0 + 1.0 / math.log2(3))
        self.assertAlmostEqual(result, expected, places=4)

    def test_no_hit_returns_zero(self) -> None:
        from app.services.retrieval_metrics import ndcg_at_k
        self.assertEqual(ndcg_at_k([99, 98, 97], {1, 2}, k=10), 0.0)

    def test_idcg_capped_at_k(self) -> None:
        """relevant 가 K 보다 많으면 IDCG 는 K 까지만 ideal."""
        from app.services.retrieval_metrics import ndcg_at_k
        # relevant 5개 / k=2 / ranking [1, 2, ...] 이 정답 둘 → DCG = 1 + 1/log2(3)
        # IDCG (k=2) = 1 + 1/log2(3) → nDCG = 1.0
        self.assertAlmostEqual(
            ndcg_at_k([1, 2, 99], {1, 2, 3, 4, 5}, k=2), 1.0
        )


class AggregateMetricsTest(unittest.TestCase):
    def test_empty_input(self) -> None:
        from app.services.retrieval_metrics import aggregate_metrics
        result = aggregate_metrics([])
        self.assertEqual(result["n"], 0)
        self.assertEqual(result["recall_at_10"], 0.0)

    def test_average(self) -> None:
        from app.services.retrieval_metrics import aggregate_metrics
        result = aggregate_metrics([
            {"recall_at_10": 1.0, "mrr": 1.0, "ndcg_at_10": 1.0},
            {"recall_at_10": 0.5, "mrr": 0.5, "ndcg_at_10": 0.5},
        ])
        self.assertEqual(result["n"], 2)
        self.assertAlmostEqual(result["recall_at_10"], 0.75)
        self.assertAlmostEqual(result["mrr"], 0.75)
        self.assertAlmostEqual(result["ndcg_at_10"], 0.75)


if __name__ == "__main__":
    unittest.main()
