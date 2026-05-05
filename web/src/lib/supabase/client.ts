import { createClient, type SupabaseClient } from '@supabase/supabase-js';

/** W25 D14 Phase 1 — 브라우저 전용 Supabase 클라이언트.
 *  Realtime 구독에만 사용. anon key (RLS 준수) — service role 절대 노출 금지.
 *  싱글톤 패턴으로 페이지 전환 시 connection 재사용. */

let _client: SupabaseClient | null = null;

export function getBrowserSupabase(): SupabaseClient | null {
  if (typeof window === 'undefined') return null;
  if (_client) return _client;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    // graceful — Realtime 미설정 환경에서도 in-app polling 으로 fallback 가능
    if (process.env.NODE_ENV !== 'production') {
      console.warn(
        '[Realtime] NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY 미설정 — Realtime 비활성',
      );
    }
    return null;
  }

  _client = createClient(url, anonKey, {
    auth: { persistSession: false, autoRefreshToken: false },
    realtime: { params: { eventsPerSecond: 5 } },
  });
  return _client;
}
