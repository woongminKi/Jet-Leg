-- W25 D14 Phase 1 — Supabase Realtime publication 에 ingest_jobs 추가.
--
-- 목적: 글로벌 ActiveDocsIndicator 가 polling 없이 ingest_jobs 의 status·current_stage
-- 변경을 WebSocket 으로 즉시 수신. 다른 페이지에서도 백그라운드 진행 가시화.
--
-- 효과:
-- - polling 폐기 → 모든 페이지의 5s GET /documents/active 부하 0
-- - 변경 즉시 push (~ms 지연)
-- - 멀티유저 SaaS 진입 시 RLS 와 자연스럽게 통합
--
-- 영향 범위: ingest_jobs 테이블 (status='running' 도중 변화·terminal 전이만 트리거).
-- DDL 외 row 변경 없음. CASCADE 등 무관. 안전.

ALTER PUBLICATION supabase_realtime ADD TABLE ingest_jobs;

-- ROLLBACK:
-- ALTER PUBLICATION supabase_realtime DROP TABLE ingest_jobs;
