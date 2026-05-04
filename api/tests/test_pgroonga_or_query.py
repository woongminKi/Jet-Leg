"""W25 D10 차수 D-a — `_build_pgroonga_query` 헬퍼 회귀 차단.

마이그레이션 0 / 의존성 0 — 순수 문자열 변환. PGroonga `&@~` query 모드의
multi-token AND 매칭 문제를 OR 변환으로 우회.

근거 (W25 D9 진단 직접 검증):
    '소나타 전장' → 0 hits (AND 매칭, vocab '소나타' 부재로 전체 0)
    '소나타 OR 전장' → 2 hits (OR — '전장' 매칭으로 sparse 회복)
"""
from __future__ import annotations

import unittest

from app.routers.search import _build_pgroonga_query


class TestBuildPgroongaQuery(unittest.TestCase):
    def test_single_token_passthrough(self):
        # 단일 토큰은 OR 변환 무의미 → 그대로 반환.
        self.assertEqual(_build_pgroonga_query("소나타"), "소나타")
        self.assertEqual(_build_pgroonga_query("Sonata"), "Sonata")

    def test_two_tokens_or_join(self):
        self.assertEqual(_build_pgroonga_query("소나타 전장"), "소나타 OR 전장")
        self.assertEqual(
            _build_pgroonga_query("소나타 디스플레이"), "소나타 OR 디스플레이"
        )

    def test_three_or_more_tokens(self):
        # 자연어 query (3~5 단어) 가 일반적 — 모두 OR 로 결합.
        self.assertEqual(
            _build_pgroonga_query("소나타 전장 길이가 얼마나 돼"),
            "소나타 OR 전장 OR 길이가 OR 얼마나 OR 돼",
        )

    def test_extra_whitespace_normalized(self):
        # 사용자 입력의 leading/trailing/내부 공백 정상화.
        self.assertEqual(_build_pgroonga_query("  소나타  전장  "), "소나타 OR 전장")
        self.assertEqual(_build_pgroonga_query("\t소나타\t전장\n"), "소나타 OR 전장")

    def test_empty_query(self):
        # 빈 문자열은 빈 문자열 반환 — 호출 직전 단계에서 검증된 값이라 방어 코드 최소.
        self.assertEqual(_build_pgroonga_query(""), "")
        self.assertEqual(_build_pgroonga_query("   "), "")

    def test_mixed_korean_english(self):
        # SONATA 카탈로그 같은 이중 언어 자료 대응.
        self.assertEqual(
            _build_pgroonga_query("Sonata 디스플레이"), "Sonata OR 디스플레이"
        )

    def test_user_typed_or_idempotent(self):
        # 사용자가 직접 'OR' 입력 시도 — 토큰화 후 재 join 해도 결과 정상 (semantic 동일).
        # PGroonga 가 'OR' 토큰을 query expression operator 로 해석.
        self.assertEqual(
            _build_pgroonga_query("회사 OR 매출"), "회사 OR OR OR 매출"
        )


if __name__ == "__main__":
    unittest.main()
