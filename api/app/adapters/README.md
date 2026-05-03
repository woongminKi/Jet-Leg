# api/app/adapters — 어댑터 레이어

Cloud→Local 전환 경로를 코드 레벨에 박아둔 Protocol 기반 어댑터.

기획서 §14.5 의 v2 (Local-first 전환) 가 이 레이어 위에서 동작 — Gemini→Ollama, BGE-M3 HF→로컬, Supabase pgvector→LanceDB 같은 스왑이 1 모듈 변경으로 가능하도록 설계.

---

## 디렉토리 구조

```
adapters/
├── __init__.py
├── llm.py                # LLMAdapter Protocol + ChatMessage
├── vision.py             # VisionCaptioner Protocol + VisionCaption (4필드 JSON 계약)
├── embedding.py          # EmbeddingProvider Protocol + EmbeddingResult
├── vectorstore.py        # VectorStore Protocol + ChunkRecord / SearchHit
├── parser.py             # DocumentParser Protocol + ExtractionResult / ExtractedSection
└── impl/                 # 실 구현체
    ├── gemini_llm.py
    ├── gemini_vision.py
    ├── _gemini_common.py        # Gemini SDK 공유 유틸 (quota 감지 포함)
    ├── bgem3_hf_embedding.py    # BGE-M3 via HF Inference + LRU cache (W4 Day 1)
    ├── supabase_vectorstore.py
    ├── supabase_storage.py
    ├── pymupdf_parser.py        # PDF (텍스트 레이어 + heading 휴리스틱 W4)
    ├── hwpx_parser.py           # HWPX (XML 기반)
    ├── hwpml_parser.py          # HWPML (HWP 변형, W2 후속)
    ├── hwp_parser.py            # HWP 5.x (OLE2 binary)
    ├── docx_parser.py           # DOCX (python-docx, W5)
    ├── pptx_parser.py           # PPTX (python-pptx + Vision OCR rerouting, W8)
    ├── url_parser.py            # URL (trafilatura)
    └── image_parser.py          # 이미지 (EXIF + 1024px + Vision composition)
```

## 5개 인터페이스

| Protocol | 책임 | 현재 impl | 미래 swap 후보 |
|---|---|---|---|
| `LLMAdapter` | 텍스트 생성 (tag/summary/action_items) | `GeminiLLM` (2.5 Flash) | OpenAI GPT-4o-mini · Ollama Qwen2.5-Korean |
| `VisionCaptioner` | 이미지 → 4필드 JSON (type·caption·ocr_text·structured) | `GeminiVisionCaptioner` | OpenAI Vision · 로컬 LLaVA |
| `EmbeddingProvider` | 텍스트 → dense vec (1024) + sparse 토큰 | `BGEM3HFEmbeddingProvider` (HF Inference Providers) | Upstage Solar · 로컬 BGE-M3 |
| `VectorStore` | chunks · documents 영속화 + 검색 | `SupabaseVectorStore` | LanceDB · Qdrant |
| `DocumentParser` | 파일 bytes → ExtractedSection 리스트 | 7종 (pdf·hwpx·hwpml·hwp·docx·pptx·url·image) | (포맷별 안정 구현) |

## 디자인 정책

### 1. Protocol 기반 (PEP 544)

```python
class VisionCaptioner(Protocol):
    def caption(self, image_bytes: bytes, *, mime_type: str) -> VisionCaption: ...
```

- 추상 베이스 클래스 (ABC) 대신 **structural typing** — 인터페이스 일치만으로 swap 가능
- 단위 테스트가 `MagicMock()` 으로 자유롭게 stub
- 새 impl 추가 시 ABC 상속 강제 X (rigidity 회피)

### 2. composition over inheritance

```python
class ImageParser:
    def __init__(self, captioner: VisionCaptioner | None = None) -> None:
        self._captioner = captioner or GeminiVisionCaptioner()
```

- `ImageParser` 가 `VisionCaptioner` 를 composition (DI 패턴)
- 단위 테스트가 fake captioner 주입 → Vision API 호출 0
- 미래 OpenAI Vision swap 시 `ImageParser(captioner=OpenAIVisionCaptioner())` 한 줄

### 3. impl/ 분리

- `impl/` 외부에서는 인터페이스만 import — `from app.adapters import VisionCaptioner`
- impl 의 구체 클래스는 internal — 인스턴스 생성 시점에만 import (lazy)

### 4. 단일 책임 + 표준 계약

- 4필드 JSON (Vision) 같은 계약은 인터페이스 docstring 에 명시
- impl 이 다르더라도 같은 schema 반환 → frontend / RAG 파이프라인 무관

## DoD ④ — OpenAI 어댑터 스왑 시연 (W21~W23 사용자 보류)

기획서 §14.2 DoD ④ — "어댑터 2개 (Gemini + OpenAI 스텁)" 1줄 swap 시연.

진행 대기 (사용자 보류 해제 시 진행):
- `impl/openai_llm.py` — `LLMAdapter` 구현
- `impl/openai_vision.py` — `VisionCaptioner` 구현
- `impl/openai_embedding.py` — `EmbeddingProvider` 구현 (text-embedding-3-small 1536-dim → 1024 차원 일치 필요 — Matryoshka or 별도 처리)
- swap 시연 commit — `impl/__init__.py` 의 default factory 1줄 변경

비판적 재검토 — 1024 vs 1536 차원 mismatch:
- pgvector HNSW 인덱스 `vector(1024)` 하드코딩 → swap 시 차원 일관 필요
- text-embedding-3-small Matryoshka 1024 dim 지원 (2024+) — 활용 가능
- 또는 마이그레이션 9 신규로 차원 변경 (대량 reembed 부담)

## v2 (Local-first 전환, 2~3개월) 진입 시

기획서 §14.5 — Cloud → Local 1줄 swap.

| 어댑터 | Cloud (현재) | Local (v2) |
|---|---|---|
| LLM | Gemini 2.5 Flash | **Ollama + Qwen2.5-Korean** |
| Vision | Gemini 2.5 Flash | LLaVA (Ollama) 또는 GPT-4o-mini API 유지 |
| Embedding | BGE-M3 HF Inference | **로컬 BGE-M3** (sentence-transformers) |
| VectorStore | Supabase pgvector | **LanceDB 로컬** |
| Storage | Supabase Storage | 로컬 파일시스템 (`~/jet-rag/storage/`) |

본 README 의 Protocol 패턴이 v2 전환 비용을 1주 미만으로 압축. **어댑터 레이어 자체가 v2 의 narrative 증명**.
