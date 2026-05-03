-- ============================================================
-- 007_metrics_trend_rpc.sql — W16 Day 1 (DoD: 추세 분석 RPC)
-- ============================================================
-- 배경
--   W15 Day 2 마이그레이션 005·006 으로 search_metrics_log + vision_usage_log
--   영속화 ship. W15 Day 3 Python write-through 까지 ship 완료.
--   본 마이그레이션은 시간 범위 + (search 의 경우) mode 별 aggregate RPC 2개 제공.
--   frontend 시계열 그래프 (W16 Day 3) 의 데이터 소스.
--
-- 설계
--   - get_search_metrics_trend(range_label TEXT, mode_label TEXT)
--       range_label: '24h' / '7d' / '30d'
--       mode_label : 'all' / 'hybrid' / 'dense' / 'sparse'
--       bucket    : 24h → 1h / 7d → 6h / 30d → 1d
--       반환      : bucket_start, sample_count, p50_ms, p95_ms, fallback_count
--   - get_vision_usage_trend(range_label TEXT)
--       range_label: '24h' / '7d' / '30d'
--       bucket    : search 와 동일
--       반환      : bucket_start, sample_count, success_count, quota_exhausted_count
--
-- 정렬 패턴
--   epoch floor — to_timestamp(FLOOR(epoch / bucket_secs) * bucket_secs).
--   24h/7d/30d 모두 동일 패턴. timezone-safe (UTC), DST 영향 없음.
--   range_start 도 동일 floor → generate_series 와 LEFT JOIN 정확히 일치.
--
-- 인덱스 활용
--   006 의 idx_search_metrics_log_mode_recorded (mode, recorded_at DESC) — composite
--   006 의 idx_search_metrics_log_recorded_at (recorded_at DESC)         — fallback / mode='all'
--   005 의 idx_vision_usage_log_called_at      (called_at DESC)          — 시간 범위
--
-- 보안
--   SECURITY DEFINER + service_role 만 GRANT — 005·006 RLS 정책과 동일.
--   anon / authenticated 키로는 호출 불가.
--
-- 적용 절차
--   Supabase Studio → SQL Editor → 본 파일 paste → Run.
--   (005·006 가 먼저 적용되어 있어야 함 — 테이블 미존재 시 RPC 정의 자체는 성공하나
--    호출 시 relation does not exist 발생)
--
-- 검증 SQL (적용 후 — 005·006 도 적용된 상태)
--   INSERT INTO search_metrics_log
--     (took_ms, dense_hits, sparse_hits, fused, has_dense, mode, query_text)
--     VALUES (150, 10, 5, 10, TRUE, 'hybrid', 'trend-test');
--   SELECT * FROM get_search_metrics_trend('24h', 'all');
--   → 25 row (1h 단위 + 시작 boundary, zero-fill), 1 row 의 sample_count=1, 나머지 0
--   DELETE FROM search_metrics_log WHERE query_text = 'trend-test';
--
--   INSERT INTO vision_usage_log (success, quota_exhausted, source_type)
--     VALUES (TRUE, FALSE, 'image');
--   SELECT * FROM get_vision_usage_trend('24h');
--   → 25 row, 1 row 의 sample_count=1
--   DELETE FROM vision_usage_log WHERE source_type = 'image';
-- ============================================================

-- ---------------- search_metrics_log 추세 RPC ----------------
CREATE OR REPLACE FUNCTION get_search_metrics_trend(
    range_label TEXT DEFAULT '7d',
    mode_label  TEXT DEFAULT 'all'
)
RETURNS TABLE (
    bucket_start    TIMESTAMPTZ,
    sample_count    INT,
    p50_ms          INT,
    p95_ms          INT,
    fallback_count  INT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    bucket_secs   BIGINT;
    range_secs    BIGINT;
    range_start   TIMESTAMPTZ;
BEGIN
    -- range / bucket 매핑
    IF range_label = '24h' THEN
        range_secs  := 86400;     -- 24 * 3600
        bucket_secs := 3600;      -- 1h
    ELSIF range_label = '7d' THEN
        range_secs  := 604800;    -- 7 * 86400
        bucket_secs := 21600;     -- 6h
    ELSIF range_label = '30d' THEN
        range_secs  := 2592000;   -- 30 * 86400
        bucket_secs := 86400;     -- 1d
    ELSE
        RAISE EXCEPTION 'invalid range_label: %', range_label
            USING HINT = 'use 24h / 7d / 30d';
    END IF;

    IF mode_label NOT IN ('all', 'hybrid', 'dense', 'sparse') THEN
        RAISE EXCEPTION 'invalid mode_label: %', mode_label
            USING HINT = 'use all / hybrid / dense / sparse';
    END IF;

    -- range_start 를 bucket boundary 에 정렬 (epoch floor)
    range_start := to_timestamp(
        FLOOR(EXTRACT(EPOCH FROM now() - make_interval(secs => range_secs)) / bucket_secs)
        * bucket_secs
    );

    RETURN QUERY
    WITH buckets AS (
        SELECT generate_series(
            range_start,
            now(),
            make_interval(secs => bucket_secs)
        ) AS b_start
    ),
    samples AS (
        SELECT
            to_timestamp(
                FLOOR(EXTRACT(EPOCH FROM recorded_at) / bucket_secs) * bucket_secs
            ) AS b_start,
            took_ms,
            fallback_reason
        FROM search_metrics_log
        WHERE recorded_at >= range_start
          AND (mode_label = 'all' OR mode = mode_label)
    )
    SELECT
        b.b_start AS bucket_start,
        COALESCE(COUNT(s.took_ms), 0)::INT AS sample_count,
        COALESCE(percentile_cont(0.5)  WITHIN GROUP (ORDER BY s.took_ms), 0)::INT AS p50_ms,
        COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY s.took_ms), 0)::INT AS p95_ms,
        COALESCE(COUNT(s.fallback_reason), 0)::INT AS fallback_count
    FROM buckets b
    LEFT JOIN samples s ON s.b_start = b.b_start
    GROUP BY b.b_start
    ORDER BY b.b_start ASC;
END;
$$;

REVOKE ALL ON FUNCTION get_search_metrics_trend(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION get_search_metrics_trend(TEXT, TEXT) TO service_role;


-- ---------------- vision_usage_log 추세 RPC ----------------
CREATE OR REPLACE FUNCTION get_vision_usage_trend(
    range_label TEXT DEFAULT '7d'
)
RETURNS TABLE (
    bucket_start            TIMESTAMPTZ,
    sample_count            INT,
    success_count           INT,
    quota_exhausted_count   INT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    bucket_secs   BIGINT;
    range_secs    BIGINT;
    range_start   TIMESTAMPTZ;
BEGIN
    IF range_label = '24h' THEN
        range_secs  := 86400;
        bucket_secs := 3600;
    ELSIF range_label = '7d' THEN
        range_secs  := 604800;
        bucket_secs := 21600;
    ELSIF range_label = '30d' THEN
        range_secs  := 2592000;
        bucket_secs := 86400;
    ELSE
        RAISE EXCEPTION 'invalid range_label: %', range_label
            USING HINT = 'use 24h / 7d / 30d';
    END IF;

    range_start := to_timestamp(
        FLOOR(EXTRACT(EPOCH FROM now() - make_interval(secs => range_secs)) / bucket_secs)
        * bucket_secs
    );

    RETURN QUERY
    WITH buckets AS (
        SELECT generate_series(
            range_start,
            now(),
            make_interval(secs => bucket_secs)
        ) AS b_start
    ),
    samples AS (
        SELECT
            to_timestamp(
                FLOOR(EXTRACT(EPOCH FROM called_at) / bucket_secs) * bucket_secs
            ) AS b_start,
            success,
            quota_exhausted
        FROM vision_usage_log
        WHERE called_at >= range_start
    )
    SELECT
        b.b_start AS bucket_start,
        COALESCE(COUNT(s.success), 0)::INT AS sample_count,
        COALESCE(COUNT(*) FILTER (WHERE s.success = TRUE), 0)::INT AS success_count,
        COALESCE(COUNT(*) FILTER (WHERE s.quota_exhausted = TRUE), 0)::INT AS quota_exhausted_count
    FROM buckets b
    LEFT JOIN samples s ON s.b_start = b.b_start
    GROUP BY b.b_start
    ORDER BY b.b_start ASC;
END;
$$;

REVOKE ALL ON FUNCTION get_vision_usage_trend(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION get_vision_usage_trend(TEXT) TO service_role;

-- ============================================================
-- 끝. API endpoint `/stats/trend` 는 W16 Day 2.
-- ============================================================
