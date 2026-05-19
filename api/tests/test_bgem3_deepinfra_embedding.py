"""BGEM3DeepInfraEmbeddingProvider + factory 분기 단위 테스트 (v1.5 W-1).

검증 범위
- 인증 토큰 부재 → init 단계 RuntimeError (한국어 메시지)
- 단일 embed 응답 파싱 + 차원 검증 (1024 강제)
- batch embed 응답 파싱 (index 정렬 포함)
- transient 5xx → retry 후 성공 (sleep mock, 실 호출 0)
- 4xx 영구 실패 → 즉시 실패 (retry 없음)
- factory 분기 (`JETRAG_EMBED_PROVIDER=deepinfra`) → DeepInfra 인스턴스 반환,
  default 는 HF 인스턴스 반환 (회귀 안전판)

stdlib `unittest` 만 사용 — 외부 의존성 0. 외부 DeepInfra 호출 0건 (모킹 only).
실행: `cd api && uv run python -m unittest tests.test_bgem3_deepinfra_embedding`
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import httpx


def _make_response(status: int, body: dict | bytes = b"{}") -> httpx.Response:
    """httpx.Response 픽스처 — _parse_*_response 에 직접 주입용."""
    request = httpx.Request("POST", "https://api.deepinfra.invalid/v1/openai/embeddings")
    if isinstance(body, dict):
        import json

        content = json.dumps(body).encode("utf-8")
    else:
        content = body
    return httpx.Response(status, request=request, content=content)


def _status_error(status: int, *, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.deepinfra.invalid/v1/openai/embeddings")
    response = httpx.Response(status, request=request, content=b"{}", headers=headers or {})
    return httpx.HTTPStatusError(f"{status} test", request=request, response=response)


def _embedding_payload(values: list[float]) -> dict:
    """OpenAI-compatible 단일 응답 페이로드."""
    return {
        "data": [{"embedding": values, "index": 0}],
        "model": "BAAI/bge-m3",
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


def _batch_payload(vectors: list[list[float]]) -> dict:
    return {
        "data": [{"embedding": v, "index": i} for i, v in enumerate(vectors)],
        "model": "BAAI/bge-m3",
        "usage": {"prompt_tokens": len(vectors), "total_tokens": len(vectors)},
    }


class DeepInfraAuthMissingTest(unittest.TestCase):
    """토큰 부재 → init RuntimeError. ENV·캐시 격리."""

    def setUp(self) -> None:
        # config.get_settings() 는 lru_cache 라 ENV 변화 반영 위해 캐시 클리어 필요.
        from app.config import get_settings

        get_settings.cache_clear()
        # 다른 테스트가 set 했을 수 있어 명시 제거.
        self._saved = os.environ.pop("DEEPINFRA_API_TOKEN", None)

    def tearDown(self) -> None:
        from app.config import get_settings

        if self._saved is not None:
            os.environ["DEEPINFRA_API_TOKEN"] = self._saved
        get_settings.cache_clear()

    def test_init_raises_runtime_error_without_token(self) -> None:
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )

        with self.assertRaises(RuntimeError) as ctx:
            BGEM3DeepInfraEmbeddingProvider()
        self.assertIn("DEEPINFRA_API_TOKEN", str(ctx.exception))


class DeepInfraParseSingleResponseTest(unittest.TestCase):
    """단일 응답 파싱 + 차원 검증."""

    def test_valid_response_returns_dense_vector(self) -> None:
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        vec = [0.001 * i for i in range(1024)]
        resp = _make_response(200, _embedding_payload(vec))

        result = di._parse_single_response(resp)

        self.assertEqual(len(result), 1024)
        self.assertAlmostEqual(result[0], 0.0, places=6)
        self.assertAlmostEqual(result[1], 0.001, places=6)

    def test_wrong_dimension_raises(self) -> None:
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        # 1023 차원 — 실수로 다른 모델이 endpoint 에 매핑될 때 가드.
        bad = [0.0] * 1023
        resp = _make_response(200, _embedding_payload(bad))

        with self.assertRaises(RuntimeError) as ctx:
            di._parse_single_response(resp)
        self.assertIn("차원 불일치", str(ctx.exception))

    def test_missing_data_key_raises(self) -> None:
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        resp = _make_response(200, {"model": "BAAI/bge-m3"})  # data 없음
        with self.assertRaises(RuntimeError) as ctx:
            di._parse_single_response(resp)
        self.assertIn("스키마", str(ctx.exception))


class DeepInfraBatchTest(unittest.TestCase):
    """batch 응답 — index 순서 보존 + 차원 검증."""

    def setUp(self) -> None:
        from app.config import get_settings

        get_settings.cache_clear()
        os.environ["DEEPINFRA_API_TOKEN"] = "dummy-test-token"

    def tearDown(self) -> None:
        from app.config import get_settings

        os.environ.pop("DEEPINFRA_API_TOKEN", None)
        get_settings.cache_clear()

    def test_embed_batch_returns_vectors_in_order(self) -> None:
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )

        v0 = [0.1] * 1024
        v1 = [0.2] * 1024
        v2 = [0.3] * 1024
        # 일부러 index 가 역순으로 도착해도 정렬되어야 함 — provider 가 sorted_items.
        scrambled = {
            "data": [
                {"embedding": v2, "index": 2},
                {"embedding": v0, "index": 0},
                {"embedding": v1, "index": 1},
            ],
            "model": "BAAI/bge-m3",
        }
        provider = BGEM3DeepInfraEmbeddingProvider()
        mock_resp = _make_response(200, scrambled)
        with patch.object(provider._client, "post", return_value=mock_resp):
            results = provider.embed_batch(["a", "b", "c"])

        self.assertEqual(len(results), 3)
        self.assertAlmostEqual(results[0].dense[0], 0.1, places=6)
        self.assertAlmostEqual(results[1].dense[0], 0.2, places=6)
        self.assertAlmostEqual(results[2].dense[0], 0.3, places=6)
        # sparse 는 빈 dict (HF 와 동일 정책).
        for r in results:
            self.assertEqual(r.sparse, {})

    def test_empty_batch_returns_empty_without_call(self) -> None:
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )

        provider = BGEM3DeepInfraEmbeddingProvider()
        # 호출이 발생하면 안 됨 — empty list 는 short-circuit.
        with patch.object(provider._client, "post") as post_mock:
            results = provider.embed_batch([])
        self.assertEqual(results, [])
        post_mock.assert_not_called()


class DeepInfraRetryTest(unittest.TestCase):
    """transient 5xx → backoff 재시도, 4xx → 즉시 실패."""

    def setUp(self) -> None:
        from app.config import get_settings

        get_settings.cache_clear()
        os.environ["DEEPINFRA_API_TOKEN"] = "dummy-test-token"

    def tearDown(self) -> None:
        from app.config import get_settings

        os.environ.pop("DEEPINFRA_API_TOKEN", None)
        get_settings.cache_clear()

    def test_transient_503_retries_then_succeeds(self) -> None:
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        attempts = {"n": 0}
        good_vec = [0.5] * 1024

        def fn() -> list[float]:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _status_error(503)
            return good_vec

        with patch.object(di.time, "sleep") as sleep_mock:
            result = di._with_retry(fn, label="test")

        self.assertEqual(attempts["n"], 3)
        self.assertEqual(result, good_vec)
        # 2번 sleep — backoff delay 가 _BASE_BACKOFF_SECONDS 이상.
        self.assertEqual(sleep_mock.call_count, 2)
        for call in sleep_mock.call_args_list:
            self.assertGreaterEqual(call.args[0], di._BASE_BACKOFF_SECONDS)

    def test_permanent_4xx_raises_without_retry(self) -> None:
        """401: 토큰 만료 → 즉시 raise. sleep 호출 0건."""
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        attempts = {"n": 0}

        def fn() -> list[float]:
            attempts["n"] += 1
            raise _status_error(401)

        with patch.object(di.time, "sleep") as sleep_mock:
            with self.assertRaises(httpx.HTTPStatusError):
                di._with_retry(fn, label="test")

        self.assertEqual(attempts["n"], 1, "4xx 는 retry 하지 않아야 함")
        sleep_mock.assert_not_called()

    def test_is_transient_deepinfra_error_classification(self) -> None:
        """HF 의 `is_transient_hf_error` 와 동일 분류 정책."""
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            is_transient_deepinfra_error,
        )

        # 4xx 영구 실패 — 즉시 노출.
        for code in (400, 401, 403, 404):
            with self.subTest(code=code):
                self.assertFalse(is_transient_deepinfra_error(_status_error(code)))
        # 429 / 5xx — transient.
        for code in (429, 500, 502, 503, 504):
            with self.subTest(code=code):
                self.assertTrue(is_transient_deepinfra_error(_status_error(code)))
        # 네트워크 transient.
        self.assertTrue(is_transient_deepinfra_error(httpx.ConnectError("dns")))
        self.assertTrue(is_transient_deepinfra_error(httpx.ReadTimeout("slow")))
        # 비-HTTP 오류 (응답 파싱 실패 등) 는 transient 아님.
        self.assertFalse(is_transient_deepinfra_error(RuntimeError("parse")))


class FactoryProviderSwitchTest(unittest.TestCase):
    """`get_bgem3_provider()` 가 `JETRAG_EMBED_PROVIDER` ENV 로 HF↔DeepInfra 분기.

    호출 사이트 8개 무변경 보장의 핵심. default 는 회귀 안전판 (`hf`).
    """

    def setUp(self) -> None:
        from app.adapters.impl.bgem3_hf_embedding import get_bgem3_provider
        from app.config import get_settings

        # ENV 변화 반영 위해 두 캐시 모두 클리어.
        get_bgem3_provider.cache_clear()
        get_settings.cache_clear()
        # 두 어댑터 모두 init 통과하도록 토큰 둘 다 주입.
        os.environ["HF_API_TOKEN"] = "dummy-hf-token"
        os.environ["DEEPINFRA_API_TOKEN"] = "dummy-di-token"

    def tearDown(self) -> None:
        from app.adapters.impl.bgem3_hf_embedding import get_bgem3_provider
        from app.config import get_settings

        get_bgem3_provider.cache_clear()
        os.environ.pop("JETRAG_EMBED_PROVIDER", None)
        os.environ.pop("HF_API_TOKEN", None)
        os.environ.pop("DEEPINFRA_API_TOKEN", None)
        get_settings.cache_clear()

    def test_default_returns_hf_provider(self) -> None:
        """ENV 미지정 → 기존 HF 어댑터 (회귀 안전판)."""
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )
        from app.adapters.impl.bgem3_hf_embedding import (
            BGEM3HFEmbeddingProvider,
            get_bgem3_provider,
        )

        os.environ.pop("JETRAG_EMBED_PROVIDER", None)
        provider = get_bgem3_provider()
        self.assertIsInstance(provider, BGEM3HFEmbeddingProvider)
        self.assertNotIsInstance(provider, BGEM3DeepInfraEmbeddingProvider)

    def test_explicit_deepinfra_returns_deepinfra_provider(self) -> None:
        """ENV=`deepinfra` → DeepInfra 어댑터 반환. 호출 사이트는 동일 시그니처라 무변경."""
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )
        from app.adapters.impl.bgem3_hf_embedding import get_bgem3_provider

        os.environ["JETRAG_EMBED_PROVIDER"] = "deepinfra"
        provider = get_bgem3_provider()
        self.assertIsInstance(provider, BGEM3DeepInfraEmbeddingProvider)
        # Protocol 시그니처 충족 확인 — 호출 사이트가 사용하는 attribute 들.
        self.assertEqual(provider.dense_dim, 1024)
        self.assertTrue(hasattr(provider, "embed"))
        self.assertTrue(hasattr(provider, "embed_batch"))
        self.assertTrue(hasattr(provider, "embed_query"))

    def test_unknown_value_falls_back_to_hf(self) -> None:
        """오타·미지 값 → default `hf` (startup crash 방지 graceful)."""
        from app.adapters.impl.bgem3_hf_embedding import (
            BGEM3HFEmbeddingProvider,
            get_bgem3_provider,
        )

        os.environ["JETRAG_EMBED_PROVIDER"] = "openai-bge"  # 미지원
        provider = get_bgem3_provider()
        self.assertIsInstance(provider, BGEM3HFEmbeddingProvider)

    def test_case_insensitive(self) -> None:
        """대소문자 무관 — `DeepInfra` / `DEEPINFRA` 도 인식."""
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )
        from app.adapters.impl.bgem3_hf_embedding import get_bgem3_provider

        os.environ["JETRAG_EMBED_PROVIDER"] = "DeepInfra"
        provider = get_bgem3_provider()
        self.assertIsInstance(provider, BGEM3DeepInfraEmbeddingProvider)


class ParseRetryAfterTest(unittest.TestCase):
    """DeepInfra `_parse_retry_after` 직접 단위 테스트 (W-2 P2 보강).

    HF 어댑터에서 복제된 함수라 `test_bgem3_retry_after.py` 와 동일 입력별 동작을
    검증 — 두 어댑터 간 정책 일관성 가드. 외부 호출 0건.
    """

    def test_integer_delta_seconds(self) -> None:
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        exc = _status_error(503, headers={"Retry-After": "30"})
        self.assertEqual(di._parse_retry_after(exc), 30.0)

    def test_http_date_returns_positive_delta(self) -> None:
        """HTTP-date 미래 → 양수 차 (실행 지연 고려 느슨하게)."""
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime

        from app.adapters.impl import bgem3_deepinfra_embedding as di

        future = datetime.now(timezone.utc) + timedelta(seconds=20)
        exc = _status_error(503, headers={"Retry-After": format_datetime(future)})
        delta = di._parse_retry_after(exc)

        self.assertIsNotNone(delta)
        assert delta is not None
        self.assertGreater(delta, 0.0)
        self.assertLessEqual(delta, di._MAX_RETRY_AFTER_SECONDS)
        self.assertLess(abs(delta - 20.0), 5.0)

    def test_negative_returns_none(self) -> None:
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        exc = _status_error(429, headers={"Retry-After": "-5"})
        self.assertIsNone(di._parse_retry_after(exc))

    def test_large_value_clamped_to_max(self) -> None:
        """악의적/과대 헤더 방어 — `_MAX_RETRY_AFTER_SECONDS` (60) 로 클램프."""
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        exc = _status_error(503, headers={"Retry-After": "9999"})
        self.assertEqual(di._parse_retry_after(exc), di._MAX_RETRY_AFTER_SECONDS)

    def test_none_when_header_absent(self) -> None:
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        exc = _status_error(503)
        self.assertIsNone(di._parse_retry_after(exc))

    def test_none_when_not_http_status_error(self) -> None:
        """HTTPStatusError 외 (ConnectError, RuntimeError) → None."""
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        self.assertIsNone(di._parse_retry_after(httpx.ConnectError("dns")))
        self.assertIsNone(di._parse_retry_after(RuntimeError("parse fail")))

    def test_none_for_garbage_string(self) -> None:
        """파싱 불가 문자열 → None (caller 가 지수 백오프로 fallback)."""
        from app.adapters.impl import bgem3_deepinfra_embedding as di

        for raw in ("abc", "soon", ""):
            with self.subTest(raw=raw):
                exc = _status_error(429, headers={"Retry-After": raw})
                self.assertIsNone(di._parse_retry_after(exc))


class PersistentCacheHitTest(unittest.TestCase):
    """`embed_query` 영구 캐시(DB) hit 경로 — `_last_cache_source="persistent"` 분기.

    `embed_query_cache.lookup` 을 monkey-patch 해 외부 HTTP 호출 없이 검증.
    LRU 도 hit 후 채워지는지 함께 확인.
    """

    def setUp(self) -> None:
        from app.config import get_settings

        get_settings.cache_clear()
        os.environ["DEEPINFRA_API_TOKEN"] = "dummy-test-token"

    def tearDown(self) -> None:
        from app.config import get_settings

        os.environ.pop("DEEPINFRA_API_TOKEN", None)
        get_settings.cache_clear()

    def test_persistent_cache_hit_skips_http_call(self) -> None:
        """영구 캐시 hit → HTTP post 호출 0, source="persistent", 반환 벡터 일치."""
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )

        provider = BGEM3DeepInfraEmbeddingProvider()
        provider.clear_embed_cache()  # LRU 비움 — persistent 분기로 떨어지게.

        persisted_vec = [0.42] * 1024

        # embed_query_cache 는 어댑터 내부에서 lazy import 되므로 모듈 경로 직접 patch.
        from app.services import embed_query_cache

        with patch.object(provider._client, "post") as post_mock, patch.object(
            embed_query_cache, "lookup", return_value=persisted_vec
        ) as lookup_mock, patch.object(
            embed_query_cache, "upsert"
        ) as upsert_mock:
            result = provider.embed_query("게이트 검증 쿼리")

        # 외부 호출 0건 — 핵심 보장.
        post_mock.assert_not_called()
        # lookup 1회 호출 + upsert 는 hit 시 안 부름.
        lookup_mock.assert_called_once()
        upsert_mock.assert_not_called()

        # 벡터 일치 (값 + 길이) — caller mutation 방어 위해 list 복사라 ID 는 다를 수 있어 값 비교.
        self.assertEqual(len(result), 1024)
        self.assertEqual(result, persisted_vec)

        # 어댑터 메트릭 — search.py 가 의존.
        self.assertTrue(provider._last_cache_hit)
        self.assertEqual(provider._last_cache_source, "persistent")

    def test_persistent_hit_warms_in_process_lru(self) -> None:
        """첫 호출=persistent → 두 번째 호출=lru. 두 경로 모두 HTTP 호출 0건."""
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )
        from app.services import embed_query_cache

        provider = BGEM3DeepInfraEmbeddingProvider()
        provider.clear_embed_cache()

        persisted_vec = [0.1] * 1024
        text = "동일 쿼리"

        with patch.object(provider._client, "post") as post_mock, patch.object(
            embed_query_cache, "lookup", return_value=persisted_vec
        ) as lookup_mock, patch.object(embed_query_cache, "upsert"):
            first = provider.embed_query(text)
            self.assertEqual(provider._last_cache_source, "persistent")

            # 2번째 호출 — LRU 에 채워졌으므로 persistent lookup 도 안 가야 함.
            second = provider.embed_query(text)

        self.assertEqual(provider._last_cache_source, "lru")
        self.assertTrue(provider._last_cache_hit)
        # HTTP 는 두 번 다 안 부름.
        post_mock.assert_not_called()
        # persistent lookup 도 첫 호출 1회만 — 두 번째는 LRU 가 먼저 가로챔.
        self.assertEqual(lookup_mock.call_count, 1)
        # 값 동일.
        self.assertEqual(first, persisted_vec)
        self.assertEqual(second, persisted_vec)


class EmbedBatchRetryTest(unittest.TestCase):
    """`embed_batch` 의 `_with_retry` 동작 — transient 5xx → 재시도 → 성공.

    `test_transient_503_retries_then_succeeds` 의 batch 시그니처 확장.
    index 역순 도착 시나리오까지 함께 검증.
    """

    def setUp(self) -> None:
        from app.config import get_settings

        get_settings.cache_clear()
        os.environ["DEEPINFRA_API_TOKEN"] = "dummy-test-token"

    def tearDown(self) -> None:
        from app.config import get_settings

        os.environ.pop("DEEPINFRA_API_TOKEN", None)
        get_settings.cache_clear()

    def test_embed_batch_transient_then_success(self) -> None:
        """1차 503 → 2차 200 batch → 3 EmbeddingResult 반환. post 2회 + sleep 1회."""
        from app.adapters.impl import bgem3_deepinfra_embedding as di
        from app.adapters.impl.bgem3_deepinfra_embedding import (
            BGEM3DeepInfraEmbeddingProvider,
        )

        provider = BGEM3DeepInfraEmbeddingProvider()

        v0 = [0.11] * 1024
        v1 = [0.22] * 1024
        v2 = [0.33] * 1024
        # index 역순 도착 시나리오 — provider 가 sorted_items 로 정렬해야 함.
        good_payload = {
            "data": [
                {"embedding": v2, "index": 2},
                {"embedding": v0, "index": 0},
                {"embedding": v1, "index": 1},
            ],
            "model": "BAAI/bge-m3",
        }

        # 1차 503 raise (raise_for_status() 가 HTTPStatusError 발생), 2차 200 batch.
        fail_resp = _make_response(503, b"server unavailable")
        good_resp = _make_response(200, good_payload)
        post_mock = MagicMock(side_effect=[fail_resp, good_resp])

        with patch.object(provider._client, "post", post_mock), patch.object(
            di.time, "sleep"
        ) as sleep_mock:
            results = provider.embed_batch(["t1", "t2", "t3"])

        # 결과 — 3개 + 1024 dim + index 정렬 반영.
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(len(r.dense), 1024)
            self.assertEqual(r.sparse, {})
        self.assertAlmostEqual(results[0].dense[0], 0.11, places=6)
        self.assertAlmostEqual(results[1].dense[0], 0.22, places=6)
        self.assertAlmostEqual(results[2].dense[0], 0.33, places=6)

        # 호출 횟수 — 1 fail + 1 success.
        self.assertEqual(post_mock.call_count, 2)
        # 1번 sleep — backoff delay 가 _BASE_BACKOFF_SECONDS 이상.
        self.assertEqual(sleep_mock.call_count, 1)
        self.assertGreaterEqual(
            sleep_mock.call_args_list[0].args[0], di._BASE_BACKOFF_SECONDS
        )


if __name__ == "__main__":
    unittest.main()
