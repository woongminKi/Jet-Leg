"""W8 Day 4 — vision_metrics 카운터 + ImageParser 통합 단위 테스트.

검증 포인트
- record_call(success=True/False) → total/success/error 정확 누적
- last_called_at ISO 8601 + UTC 포맷
- thread-safe (간단한 ThreadPoolExecutor 동시 호출)
- ImageParser.parse() 가 captioner.caption 성공/실패 모두 record (raise 도 카운트)

stdlib unittest + mock only.
"""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

# import 단계에서 환경 변수 체크하는 모듈 회피.
os.environ.setdefault("HF_API_TOKEN", "dummy-test-token")
os.environ.setdefault("GEMINI_API_KEY", "dummy-test-token")


class VisionMetricsBasicTest(unittest.TestCase):
    """record_call → get_usage 누적 동작."""

    def setUp(self) -> None:
        from app.services import vision_metrics
        vision_metrics.reset()

    def test_initial_state_zeros(self) -> None:
        from app.services import vision_metrics
        usage = vision_metrics.get_usage()
        self.assertEqual(usage["total_calls"], 0)
        self.assertEqual(usage["success_calls"], 0)
        self.assertEqual(usage["error_calls"], 0)
        self.assertIsNone(usage["last_called_at"])

    def test_record_increments_counters(self) -> None:
        from app.services import vision_metrics

        vision_metrics.record_call(success=True)
        vision_metrics.record_call(success=True)
        vision_metrics.record_call(success=False)

        usage = vision_metrics.get_usage()
        self.assertEqual(usage["total_calls"], 3)
        self.assertEqual(usage["success_calls"], 2)
        self.assertEqual(usage["error_calls"], 1)

    def test_last_called_at_iso_format(self) -> None:
        from app.services import vision_metrics

        vision_metrics.record_call(success=True)
        usage = vision_metrics.get_usage()
        self.assertIsNotNone(usage["last_called_at"])
        # ISO 8601 + UTC tz (+00:00 또는 'Z')
        self.assertTrue(
            usage["last_called_at"].endswith("+00:00")
            or usage["last_called_at"].endswith("Z"),
            f"UTC tz suffix 기대 — got {usage['last_called_at']}",
        )


class VisionMetricsThreadSafetyTest(unittest.TestCase):
    """4 worker × 50 호출 = 200 record_call 동시 → race 0."""

    def setUp(self) -> None:
        from app.services import vision_metrics
        vision_metrics.reset()

    def test_concurrent_records_consistent(self) -> None:
        from app.services import vision_metrics

        def worker(_):
            for _ in range(50):
                vision_metrics.record_call(success=True)

        with ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(worker, range(4)))

        usage = vision_metrics.get_usage()
        self.assertEqual(usage["total_calls"], 200)
        self.assertEqual(usage["success_calls"], 200)
        self.assertEqual(usage["error_calls"], 0)


class ImageParserVisionIntegrationTest(unittest.TestCase):
    """ImageParser.parse() 가 captioner 성공·실패 모두 record."""

    def setUp(self) -> None:
        from app.services import vision_metrics
        vision_metrics.reset()

    def _make_png_bytes(self) -> bytes:
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (100, 50), color="white").save(buf, format="PNG")
        return buf.getvalue()

    def test_success_records_one_success(self) -> None:
        from app.adapters.impl.image_parser import ImageParser
        from app.adapters.vision import VisionCaption
        from app.services import vision_metrics

        captioner = MagicMock()
        captioner.caption.return_value = VisionCaption(
            type="문서",
            caption="모의 캡션",
            ocr_text="모의 OCR",
            structured=None,
        )
        parser = ImageParser(captioner=captioner)
        parser.parse(self._make_png_bytes(), file_name="test.png")

        usage = vision_metrics.get_usage()
        self.assertEqual(usage["total_calls"], 1)
        self.assertEqual(usage["success_calls"], 1)
        self.assertEqual(usage["error_calls"], 0)

    def test_failure_records_one_error_and_raises(self) -> None:
        from app.adapters.impl.image_parser import ImageParser
        from app.services import vision_metrics

        captioner = MagicMock()
        captioner.caption.side_effect = RuntimeError("Gemini down")
        parser = ImageParser(captioner=captioner)

        with self.assertRaises(RuntimeError):
            parser.parse(self._make_png_bytes(), file_name="test.png")

        usage = vision_metrics.get_usage()
        self.assertEqual(usage["total_calls"], 1)
        self.assertEqual(usage["success_calls"], 0)
        self.assertEqual(usage["error_calls"], 1)
        # 일반 fail 은 quota_exhausted_at 미갱신
        self.assertIsNone(usage["last_quota_exhausted_at"])


class VisionQuotaExhaustedTrackingTest(unittest.TestCase):
    """W11 Day 1 — 한계 #38 lite — fast-fail 시점만 정확 capture."""

    def setUp(self) -> None:
        from app.services import vision_metrics
        vision_metrics.reset()

    def test_quota_exhausted_at_set_on_429(self) -> None:
        from app.adapters.impl.image_parser import ImageParser
        from app.services import vision_metrics
        from io import BytesIO
        from PIL import Image

        captioner = MagicMock()
        captioner.caption.side_effect = RuntimeError(
            "429 RESOURCE_EXHAUSTED. quota exceeded"
        )
        parser = ImageParser(captioner=captioner)

        png_buf = BytesIO()
        Image.new("RGB", (50, 50), color="white").save(png_buf, format="PNG")

        with self.assertRaises(RuntimeError):
            parser.parse(png_buf.getvalue(), file_name="quota.png")

        usage = vision_metrics.get_usage()
        self.assertEqual(usage["error_calls"], 1)
        # quota 감지 → last_quota_exhausted_at 갱신
        self.assertIsNotNone(usage["last_quota_exhausted_at"])
        self.assertTrue(
            usage["last_quota_exhausted_at"].endswith("+00:00")
            or usage["last_quota_exhausted_at"].endswith("Z"),
            f"UTC tz suffix 기대 — got {usage['last_quota_exhausted_at']}",
        )

    def test_quota_exhausted_at_persists_after_success(self) -> None:
        """quota 감지 후 다른 정상 호출이 와도 last_quota_exhausted_at 유지."""
        from app.adapters.impl.image_parser import ImageParser
        from app.adapters.vision import VisionCaption
        from app.services import vision_metrics
        from io import BytesIO
        from PIL import Image

        png_buf = BytesIO()
        Image.new("RGB", (50, 50), color="white").save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        # 1. quota 발생
        captioner_fail = MagicMock()
        captioner_fail.caption.side_effect = RuntimeError(
            "429 RESOURCE_EXHAUSTED"
        )
        with self.assertRaises(RuntimeError):
            ImageParser(captioner=captioner_fail).parse(
                png_bytes, file_name="q.png"
            )

        usage_after_fail = vision_metrics.get_usage()
        first_quota_at = usage_after_fail["last_quota_exhausted_at"]
        self.assertIsNotNone(first_quota_at)

        # 2. 정상 호출 — last_called_at 은 갱신, last_quota_exhausted_at 은 유지
        captioner_ok = MagicMock()
        captioner_ok.caption.return_value = VisionCaption(
            type="문서", caption="ok", ocr_text="", structured=None
        )
        ImageParser(captioner=captioner_ok).parse(
            png_bytes, file_name="ok.png"
        )

        usage_after_ok = vision_metrics.get_usage()
        self.assertEqual(
            usage_after_ok["last_quota_exhausted_at"], first_quota_at,
            "정상 호출은 last_quota_exhausted_at 갱신 X",
        )
        # last_called_at 은 정상 호출로 갱신
        self.assertNotEqual(
            usage_after_ok["last_called_at"], first_quota_at,
            "정상 호출은 last_called_at 갱신",
        )


if __name__ == "__main__":
    unittest.main()
