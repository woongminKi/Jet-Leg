# W25 D14 — PDF 표/그림 정확도: vision enrich stage ship (Sprint 1)

> **결론**: 일반 PDF 의 표/그림/다이어그램 정보 보강용 `_enrich_pdf_with_vision()` 함수 추가 (ENV `JETRAG_PDF_VISION_ENRICH` opt-in). **회귀 0** (default false → 기존 자료 영향 0). 단위 테스트 4건 추가. **사용자 paid tier 활성화 + 본 PDF reingest 후 Sprint 2 검증** 필요.

> Step 0 PoC + Option B PoC + 자율 비판적 재검토 (3회+) 결과 — 무료 quota 한계 인정 → 유료 Gemini Flash paid tier 결정 → 인제스트 시점 모든 페이지 vision (a) 채택. 답변 시점 multimodal (c) 은 LLM 이 이미지 활용 약함 PoC 실증 → 후순위.

---

## 0. 사용자 의도 / 진단 / 결정 흐름

| 단계 | 내용 |
|---|---|
| 사용자 보고 | 데이터센터 안내서 PDF 적재 후 "테스트베드 조성 지원 사업 체계" query → p.4 표 답변 잘림 + p.6 그림 정보 누락 |
| 진단 | (1) PyMuPDF 가 표를 raw text 로 cell 순서 뒤섞임 + 일부 누락 (chunk 17개 분리) (2) 이미지 블록 (type=1) 완전 무시 → 그림 정보 chunks 0건 |
| 비판적 재검토 (1차) | A+E (find_tables + page expansion) → 그림 미해결 |
| 비판적 재검토 (2차) | heuristic D / 모든 페이지 vision → 무료 quota 가정 잘못 |
| 비판적 재검토 (3차) | 실측 quota = **20 호출/일** (Gemini Flash 무료 RPD) — (a)/(c) 모두 무료로 비현실 |
| 사용자 결정 | 유료 Gemini Flash paid tier 비용 OK |
| 채택 | (a) 인제스트 시점 모든 페이지 vision (chunks 풍부화) — paid tier 안에서 quota 무관 |

---

## 1. Sprint 1 변경 (commit 단위)

### 1.1 `api/app/ingest/stages/extract.py`

```python
_PDF_VISION_ENRICH_ENABLED = os.environ.get("JETRAG_PDF_VISION_ENRICH", "false").lower() == "true"
_VISION_ENRICH_MAX_PAGES = int(os.environ.get("JETRAG_PDF_VISION_ENRICH_MAX_PAGES", "50"))

def _enrich_pdf_with_vision(data, *, base_result, file_name, image_parser):
    """PyMuPDF 결과 보존 + 페이지별 vision 호출 → 추가 sections 병합.
    section_title='(vision) p.N' 으로 출처 식별. cap 50 안전장치.
    """
```

**흐름 변경**:
- 일반 PDF (스캔 X) + ENV 활성 시 → `_enrich_pdf_with_vision()` 호출
- PyMuPDF sections 보존 + vision 결과 (ocr_text + structured + caption) 를 페이지별 추가 section 으로 append
- chunks 자동 생성 (chunk.py 변경 0)

### 1.2 `api/tests/test_extract_pdf_vision_enrich.py` (신규)

단위 테스트 4건 (Gemini API mock):
- `test_appends_vision_sections_with_page_meta` — sections 병합 + page 메타 + parser 호출 횟수
- `test_per_page_failure_graceful` — 페이지 단위 실패 graceful (warning 추가, 다른 페이지 계속)
- `test_max_pages_cap` — cap 초과 시 첫 N 페이지만 처리 + warning
- `test_pdf_open_failure_returns_base_result` — 잘못된 PDF bytes → base_result 보존

### 1.3 회귀

- 단위 테스트 308 → **312** (+4)
- ENV `JETRAG_PDF_VISION_ENRICH` default false → SONATA + 기존 자료 영향 0
- tsc/lint 무관 (백엔드 변경)

---

## 2. Sprint 2 — 완료 결과 (2026-05-05)

### 2.1 paid tier 활성화 + reingest

- 사용자 paid tier 활성화 완료 (Tier 1 / 후불 / Default Gemini Project)
- `JETRAG_PDF_VISION_ENRICH=true` ENV 적용 후 uvicorn 재시작
- `POST /documents/b218e8a1.../reingest` 호출 → job 2410e78b 시작
- 인제스트 완료 16분 14초 (모든 stage succeeded)

### 2.2 인제스트 통계

| 항목 | 값 |
|---|---|
| 총 chunks | 384 (PyMuPDF 단독) → **428** (+44 vision sections) |
| vision 처리 페이지 | 32/41 (Google 503 retry 실패 9페이지 누락 — p.18, 19, 20, 21, 23, 26, 27, 34, 37) |
| extract latency | 884초 (페이지당 평균 ~21초, vision 503 retry 영향) |
| embed latency | 74초 (BGE-M3 페이지별) |
| 비용 추정 | ~$0.024 (32 페이지 × $0.00075) |

### 2.3 검증 — 사용자 query 직접 재호출

**query**: `"테스트베드 조성 지원 사업 체계 구조가 어떻게 되어 있어?"` (사용자 화면 시나리오 동일)

**검색 ranking 변화**:
- 이전 (Image #1): p.4 chunk 15 (표 헤더 일부, 48자) 가 1위, p.6 chunk 가 6위 (그림 정보 0건)
- 현재: **p.6 vision chunk (idx 392, 745자) 가 top 1** — 정답 페이지가 1위 진입

**답변 변화**:

이전 (잘린 답변):
```
분 야 과제당 예산 지원 과제수 지원내용 및 지원대상 테스트베드 조성 ❶ 지원...
```

현재 (vision 통합 답변):
```
테스트베드 조성 지원 사업은 실증 연계형 테스트베드 조성 사업으로,
주관기관이 테스트베드를 조성하고 활용하며 2건 이상의 장비·SW 실증 대상을
확보합니다 [1]. 장비·SW 보유 기업은 UPS, 배터리, 액체냉각, 항온항습기,
발전기, 서버·스토리지, 네트워크, 보안 관제, DCMIM 등 다양한 장비·SW를
테스트베드에서 실증합니다 [1]. 수요기관은 실증된 장비·SW의 활용을
검토하고 확보합니다 [1]. 이 사업은 실증 및 검증 환경이 가능한 테스트베드를
구축 및 조성하며, 국산화 장비·SW 실증 및 친환경·고효율 실증 등과 연계하여
진행됩니다 [1].
```

→ Image #3 그림 다이어그램의 모든 핵심 라벨 (실증 연계형 / 주관기관 / 수요기관 / UPS·배터리·액체냉각·항온항습기·발전기·서버·스토리지·네트워크·보안 관제·DCMIM / 국산화·친환경 실증) **모두 정확히 포함**.

**출처 8개 중 7개가 vision chunks** — 검색 ranking 자체가 vision chunks 우선.

### 2.4 minor fix — vision_metrics source_type 화이트리스트 추가

인제스트 중 warning 로그 발견:
```
vision_metrics.record_call source_type='pdf_vision_enrich' 무효 — None 으로 fallback
```

원인: `app/services/vision_metrics.py` 의 `_VALID_SOURCE_TYPES` 화이트리스트에 신규 `pdf_vision_enrich` 미포함. metrics 만 None fallback (graceful), 인제스트 자체 영향 0.

fix: 화이트리스트에 `pdf_vision_enrich` 추가 + 단위 테스트 fixture 갱신.

### 2.5 sprint 2 변경 파일 (commit)

- `api/app/services/vision_metrics.py` — source_type 화이트리스트 +1
- `api/tests/test_vision_metrics.py` — fixture +1
- `work-log/2026-05-04 W25 D14 PDF vision enrich.md` — Sprint 2 결과 추가

회귀 0 (단위 테스트 312 OK 유지).

---

## 3. Sprint 2 후속 검토 (사용자 결정)



### 후속 후보

| # | 후보 | 가치 |
|---|---|---|
| **a** | 503 retry 실패 9페이지 재처리 | 누락 페이지 보강 (paid tier 면 retry 충분) |
| b | SONATA 도 ENV 켜고 reingest | 일관성 (단 SONATA 는 표/그림 적은 카탈로그 — 가치 작음) |
| c | mini-Ragas 골든셋에 본 PDF QA 추가 | 정량 측정 |
| d | 다른 사용자 자료 (HWPX/PPTX/이미지) 적재 | 데이터셋 확장 |

---

## 3. 비판적 한계 (정직 인정)

1. **단위 테스트 mock 검증** — 실제 Gemini Vision 응답 구조 (특히 한국어 다이어그램) 와의 정합성 은 사용자 PDF reingest 후 실측 필요
2. **vision OCR 와 PyMuPDF text 중복** — 같은 페이지의 같은 텍스트가 두 sections 에 등장할 수 있음. chunk_filter dedup 룰이 일부 처리하지만 100% X
3. **인제스트 latency** — 페이지당 1~3초 (본 PDF 41 페이지 = 1~2분). 사용자 자료 누적 적재 패턴 검증 필요
4. **paid tier 비용** — $0.00075/페이지 추정 (실측은 사용자 billing 대시보드)
5. **cap 50 적정성 미검증** — 50 페이지 초과 PDF (정부 공고문 등) 에서 부분 누락 가능

---

## 4. 다음 sprint 후보 (Sprint 2 검증 후)

| # | 후보 | 가치 |
|---|---|---|
| **a** | Sprint 2 검증 — paid 활성화 + reingest + 측정 | 본 의도 직접 해결 |
| b | (c) 답변 시점 multimodal 보완 — 검색 ranking 후순위 case | a 효과 미달 시 |
| c | SONATA 도 ENV 켜고 reingest (선택) | 일관성 |
| d | mini-Ragas 골든셋 본 PDF 추가 | Ragas 측정 정량화 |
| e | 다른 사용자 자료 (HWPX/PPTX/이미지) 적재 → 데이터셋 확장 | 통계 의미 ↑ |

---

## 5. Karpathy 가이드라인 적용 회고

1. **Think Before Coding** — 사용자 push 받고 비판적 재검토 4회 (A+E → heuristic D → 모든 페이지 vision → 답변 시점 multimodal → quota 가설 정정 → 유료 Flash 결정). CLAUDE.md 새 원칙 (자율 N회 재검토) 추가.
2. **Simplicity First** — 별도 stage 신설 회피, 기존 `_reroute_pdf_to_image()` 패턴 재활용한 함수 추가. ENV opt-in 으로 회귀 0.
3. **Surface Assumptions** — quota 가설 (1500/일 → 실측 20/일), vision 정확도 가설 (PoC 검증), latency 가설 (실측 미정)
4. **Verifiable Success Criteria** — 단위 테스트 4건 / Sprint 2 의 본 PDF reingest + 답변 변화 측정
