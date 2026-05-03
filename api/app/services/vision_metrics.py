"""W8 Day 4 — Vision API 호출 카운터 (한계 #29 회수).
W11 Day 1 — quota 시점 추적 추가 (한계 #38 lite).

배경
- W8 Day 2 PPTX Vision OCR rerouting 후 Gemini Flash RPD 20 무료 티어 cap 모니터링.
- W8 Day 2 실 reingest 시 tag_summarize 에서 429 — quota 추적 가시성 부재 → W8 Day 4 카운터 도입.
- W11 Day 1 — Gemini SDK 가 RPD 직접 노출 X 제약 → fast-fail 시점만 정확히 capture
  (한계 #38 본격 회수는 SDK 한계로 어려움, lite 버전).

설계 원칙
- search_metrics 패턴 재사용 — in-memory + threading.Lock + stdlib only
- 모든 Vision 경로 통일 — ImageParser.parse() 진입점
- last_quota_exhausted_at — quota 초과 시점만 따로 기록 (한계 #38 lite)
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_total_calls: int = 0
_success_calls: int = 0
_error_calls: int = 0
_last_called_at: datetime | None = None
_last_quota_exhausted_at: datetime | None = None  # W11 Day 1 — 한계 #38 lite


def record_call(*, success: bool, quota_exhausted: bool = False) -> None:
    """Vision API 1회 호출 결과 기록 — ImageParser.parse() 가 호출.

    `quota_exhausted` (W11 Day 1 한계 #38 lite):
        True 시 last_quota_exhausted_at 갱신. 다음 호출 시점까지 사용자에게
        "최근 quota 소진" 정보 노출 가능.
    """
    global _total_calls, _success_calls, _error_calls
    global _last_called_at, _last_quota_exhausted_at
    with _lock:
        _total_calls += 1
        now = datetime.now(timezone.utc)
        if success:
            _success_calls += 1
        else:
            _error_calls += 1
        _last_called_at = now
        if quota_exhausted:
            _last_quota_exhausted_at = now


def get_usage() -> dict:
    """현재 누적 카운트 스냅샷. /stats 응답에서 사용."""
    with _lock:
        return {
            "total_calls": _total_calls,
            "success_calls": _success_calls,
            "error_calls": _error_calls,
            "last_called_at": (
                _last_called_at.isoformat() if _last_called_at else None
            ),
            "last_quota_exhausted_at": (
                _last_quota_exhausted_at.isoformat()
                if _last_quota_exhausted_at
                else None
            ),
        }


def reset() -> None:
    """테스트용 — 카운터 초기화."""
    global _total_calls, _success_calls, _error_calls
    global _last_called_at, _last_quota_exhausted_at
    with _lock:
        _total_calls = 0
        _success_calls = 0
        _error_calls = 0
        _last_called_at = None
        _last_quota_exhausted_at = None
