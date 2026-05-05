"""W25 D14+1 D2 — Query expansion (도메인 동의어 사전).

목적: 사용자 query 의 한 토큰이 corpus 에 없을 때 (외래어/약어/한자어) sparse path
(PGroonga `&@~`) 0 hits 회귀를 동의어 추가로 회복.

흐름:
1. 사용자 query → tokenize (공백 split)
2. 각 토큰에 대해 사전에 등록된 동의어 lookup
3. 매칭된 토큰 → "(원본 OR 동의어)" 으로 PGroonga query 확장

사전 정책:
- 양방향 (한국어 ↔ 외래어 / 약어 ↔ 풀이름)
- 11 docs 도메인 기준 (자동차 / IT / 의료 / 법률 / 학습)
- 보수적 (false positive 회피) — 30 entry 미만, 도메인 명확한 것만
- search.py 의 PGroonga query 만 expansion. dense path 는 원본 유지 (BGE-M3 가 의미적 처리).
"""

from __future__ import annotations

# 양방향 동의어 사전 — 좌우 토큰이 서로 expansion.
# 키: 한쪽 토큰 / 값: 동의어 list. lookup 시 양방향 매칭 (lookup 함수가 처리).
_SYNONYMS: dict[str, list[str]] = {
    # === 자동차 (sonata catalog) ===
    "쏘나타": ["sonata", "Sonata"],
    "sonata": ["쏘나타"],
    "Sonata": ["쏘나타"],
    "전장": ["전체길이", "길이"],
    "전폭": ["너비", "폭"],
    "전고": ["높이"],
    "트림": ["등급", "grade"],
    "휠": ["wheel"],
    # === IT / 정책 (데이터센터) ===
    "AI": ["인공지능", "artificial intelligence"],
    "인공지능": ["AI"],
    "DC": ["데이터센터", "data center"],
    "데이터센터": ["DC", "data center"],
    "ESG": ["환경 사회 지배구조"],
    # === 의료 (보건의료) ===
    "빅데이터": ["대용량 데이터", "big data"],
    "EHR": ["전자의무기록"],
    # === 법률 (law sample 2/3) ===
    "변제충당": ["변제 순서", "변제 충당"],
    "소멸시효": ["시효 소멸"],
    "원고": ["고소인", "claimant"],
    "피고": ["상대방", "respondent"],
    # === 규정 / 운영 ===
    "휴관": ["휴무", "쉬는날"],
    "직제": ["조직 구조", "조직도"],
    "본부": ["부서"],
    # === 학습자료 (태양계 / 삼국) ===
    "태양계": ["solar system"],
    "삼국시대": ["고구려 백제 신라", "삼국"],
    "행성": ["planet"],
}


def expand_tokens(tokens: list[str]) -> list[list[str]]:
    """각 토큰을 (원본 + 동의어) 리스트로 확장.

    Args:
        tokens: ["쏘나타", "전장"] 등 사용자 query 의 토큰 list.
    Returns:
        [["쏘나타", "sonata", "Sonata"], ["전장", "전체길이", "길이"]]
        — 동의어 없는 토큰은 [token] 단독 list.
    """
    out: list[list[str]] = []
    for tok in tokens:
        if not tok:
            continue
        synonyms = _SYNONYMS.get(tok, [])
        # 대소문자 무시 lookup (영어 토큰 대응)
        if not synonyms:
            for key, vals in _SYNONYMS.items():
                if key.lower() == tok.lower():
                    synonyms = vals
                    break
        if synonyms:
            expanded = [tok] + [s for s in synonyms if s != tok]
            out.append(expanded)
        else:
            out.append([tok])
    return out


def build_pgroonga_query(query: str) -> str:
    """W25 D14+1 D2 — PGroonga query expansion.

    토큰별 동의어 (괄호로 묶어 OR) → 전체 query 는 OR 합산 (W25 D10 D-a 패턴).

    예: "쏘나타 전장 길이"
    → ["쏘나타", "sonata", "Sonata"] OR ["전장", "전체길이", "길이"] OR ["길이"]
    → "쏘나타 OR sonata OR Sonata OR 전장 OR 전체길이 OR 길이"

    단일 토큰 query 는 단순 expansion (괄호 의미 없음).
    동의어 없는 query 는 원본 그대로 (W25 D10 D-a 와 동일).
    """
    tokens = [t for t in query.strip().split() if t]
    if not tokens:
        return query.strip()
    expanded = expand_tokens(tokens)
    # flatten — PGroonga `&@~` OR 단순 합산
    flat: list[str] = []
    for group in expanded:
        flat.extend(group)
    # dedupe 보존 순서
    seen: set[str] = set()
    out: list[str] = []
    for t in flat:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    if len(out) <= 1:
        return out[0] if out else query.strip()
    return " OR ".join(out)
