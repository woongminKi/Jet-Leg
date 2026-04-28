"""URL 업로드 안전 검증.

W2 명세 v0.3 §3.E + DE-18 — 클라우드 환경에서 SSRF 공격 (내부 메타데이터 endpoint
169.254.169.254, Kubernetes 내부 서비스 등) 을 차단하기 위해 host 의 IP 가 private
범위에 속하면 거절한다.

체크 항목
1. 스킴이 http/https 인가 (file://, gopher://, ftp:// 등 거절)
2. host 가 명시적으로 위험한 이름인가 (localhost, 0.0.0.0)
3. host 의 실제 IP 가 private/loopback/link-local/reserved 범위인가

DNS rebinding 공격도 동시 고려해야 완벽하지만, 현재 단일사용자 MVP 범위에서는
단순 1회 resolve + 즉시 fetch 패턴으로 충분 (W3+ 강화 가능).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# 이름으로 명시적 차단할 호스트 (IP resolve 불요)
_BLOCKED_NAMES: frozenset[str] = frozenset(
    {"localhost", "0.0.0.0", "::", "::1"}
)


def validate_url_safety(url: str) -> tuple[bool, str]:
    """URL 안전 검증. 반환: (안전 여부, 사유 문자열).

    호출자는 False 시 사용자에게 그대로 노출 가능한 한국어 사유로 400 응답.
    """
    parsed = urlparse(url)

    # 1) 스킴
    if parsed.scheme not in ("http", "https"):
        return False, f"지원하지 않는 스킴입니다: {parsed.scheme!r} (http/https 만 허용)"

    # 2) host 존재
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False, "URL 에 호스트가 없습니다."

    # 3) 명시적 차단 이름
    if host in _BLOCKED_NAMES:
        return False, f"내부 호스트 차단: {host}"

    # 4) IP 분석 — 직접 IP 입력 또는 DNS resolve 후 검증
    ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        # 도메인 → DNS resolve
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            return False, f"DNS 조회 실패: {host} ({exc})"
        if not infos:
            return False, f"DNS 조회 결과가 없습니다: {host}"
        try:
            ip_obj = ipaddress.ip_address(infos[0][4][0])
        except ValueError as exc:
            return False, f"DNS 결과 IP 파싱 실패: {exc}"

    if ip_obj.is_loopback:
        return False, f"loopback IP 차단: {ip_obj}"
    if ip_obj.is_private:
        return False, f"private IP 차단: {ip_obj}"
    if ip_obj.is_link_local:
        return False, f"link-local IP 차단: {ip_obj} (예: 169.254.0.0/16 메타데이터)"
    if ip_obj.is_reserved or ip_obj.is_multicast:
        return False, f"reserved/multicast IP 차단: {ip_obj}"

    return True, "OK"
