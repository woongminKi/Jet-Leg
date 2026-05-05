-- W25 D14 — answer_feedback 테이블 신규.
--
-- 목적: /ask 답변에 대한 사용자 피드백 (👍/👎 + 옵션 코멘트) 누적.
-- 향후 RAGAS 자동 평가의 정성 ground truth + 답변 품질 회귀 추적용.
--
-- 설계 결정:
-- - answer 자체는 stateless (DB 미저장) — feedback row 가 query+doc_id+answer_text 보존
-- - doc_id NULLABLE — 전 doc 스코프 질문 (single doc 미지정) 도 기록 가능
-- - helpful BOOLEAN NOT NULL — 👍=true, 👎=false (3-state 회피, 단순화)
-- - comment NULLABLE — 사용자 옵션
--
-- ROLLBACK:
-- DROP TABLE IF EXISTS answer_feedback;

CREATE TABLE IF NOT EXISTS answer_feedback (
    id            BIGSERIAL PRIMARY KEY,
    user_id       UUID,
    doc_id        UUID REFERENCES documents(id) ON DELETE SET NULL,
    query         TEXT NOT NULL,
    answer_text   TEXT NOT NULL,
    helpful       BOOLEAN NOT NULL,
    comment       TEXT,
    sources_count INTEGER NOT NULL DEFAULT 0,
    model         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_answer_feedback_doc
    ON answer_feedback (doc_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_answer_feedback_helpful
    ON answer_feedback (helpful, created_at DESC);
