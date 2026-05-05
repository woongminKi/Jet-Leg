-- W25 D14 — answer_ragas_evals 테이블 (RAGAS 정량 평가 캐시).
--
-- 목적: /answer 응답에 대한 RAGAS 5 메트릭 측정 결과 저장.
-- 캐시: 같은 (query, answer_text, doc_id) 입력 시 재호출 회피 (LLM judge 비용 절감).
--
-- 메트릭 (JSONB):
--   {faithfulness: 0.95, answer_relevancy: 0.82, context_precision: ?, context_recall: ?, answer_correctness: ?}
--   - reference answer 없으면 context_precision/recall/correctness 는 null
--
-- ROLLBACK:
-- DROP TABLE IF EXISTS answer_ragas_evals;

CREATE TABLE IF NOT EXISTS answer_ragas_evals (
    id            BIGSERIAL PRIMARY KEY,
    user_id       UUID,
    doc_id        UUID REFERENCES documents(id) ON DELETE SET NULL,
    query         TEXT NOT NULL,
    answer_text   TEXT NOT NULL,
    contexts      TEXT[],         -- 평가 시 사용된 contexts (출처 chunks 본문)
    metrics       JSONB NOT NULL, -- 5 메트릭 점수 (값 없으면 null)
    model_judge   TEXT,           -- judge LLM 모델 이름 (예: gemini-2.5-flash)
    took_ms       INTEGER,
    error_msg     TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 캐시 lookup 가속 (가장 최근 평가 우선)
CREATE INDEX IF NOT EXISTS idx_answer_ragas_lookup
    ON answer_ragas_evals (doc_id, query, created_at DESC);
