-- W25 D14 — ingest_jobs.stage_progress JSONB 컬럼 추가.
--
-- 목적: 한 stage 안에서 sub-step 진행 (예: vision_enrich 페이지 12/41) 을 실시간 표시.
-- {current: int, total: int, unit: 'pages'|'chunks'|...} 구조.
--
-- Realtime: ingest_jobs 가 이미 supabase_realtime publication 에 추가됨 (009).
-- stage_progress UPDATE 시 자동 push → web indicator panel + StageProgress 실시간 갱신.
--
-- NULL 허용 — stage_progress 미사용 stage (chunk·embed 등 빠른 stage) 는 NULL.

ALTER TABLE ingest_jobs ADD COLUMN IF NOT EXISTS stage_progress JSONB;

-- ROLLBACK:
-- ALTER TABLE ingest_jobs DROP COLUMN IF EXISTS stage_progress;
