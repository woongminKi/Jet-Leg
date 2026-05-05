'use client';

import { useEffect, useRef, useState } from 'react';
import { getActiveDocs, type ActiveDocItem } from '@/lib/api';
import { getBrowserSupabase } from '@/lib/supabase/client';

/** W25 D14 Phase 1 — 글로벌 active docs 상태 (Supabase Realtime 기반).
 *
 *  동작:
 *   1) 마운트 시 1회 GET /documents/active fetch (initial state)
 *   2) Supabase Realtime 으로 ingest_jobs INSERT/UPDATE 구독 — 변경 즉시 부분 갱신
 *   3) status 가 terminal (completed/failed/cancelled) 로 전이된 doc 은 onTerminal 콜백
 *      호출 후 active 리스트에서 제거 (헤더 indicator 카운트 감소)
 *
 *  graceful: Realtime 미설정 시 polling (15s) fallback — UX 약간 늦어지지만 동작.
 */

const FALLBACK_POLL_MS = 15000;
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);

export interface ActiveDocsState {
  items: ActiveDocItem[];
  loading: boolean;
}

export function useActiveDocsRealtime(
  onTerminal?: (item: ActiveDocItem, terminalStatus: string) => void,
): ActiveDocsState {
  const [items, setItems] = useState<ActiveDocItem[]>([]);
  const [loading, setLoading] = useState(true);
  const onTerminalRef = useRef(onTerminal);
  // React 19 — ref update 는 effect 에서만 (lint react-hooks/refs)
  useEffect(() => {
    onTerminalRef.current = onTerminal;
  }, [onTerminal]);

  useEffect(() => {
    let cancelled = false;
    const itemsByJobId = new Map<string, ActiveDocItem>();
    const itemsByDocId = new Map<string, ActiveDocItem>();

    const upsertItem = (item: ActiveDocItem) => {
      itemsByJobId.set(item.job.job_id, item);
      itemsByDocId.set(item.doc_id, item);
    };
    const removeItem = (docId: string, jobId: string) => {
      itemsByJobId.delete(jobId);
      itemsByDocId.delete(docId);
    };
    const flush = () => {
      if (cancelled) return;
      setItems(Array.from(itemsByDocId.values()));
    };

    const initial = async () => {
      try {
        const res = await getActiveDocs(24);
        if (cancelled) return;
        for (const it of res.items) upsertItem(it);
        flush();
      } catch {
        // graceful: 백엔드 미기동 환경에서도 Realtime push 만으로 점진 채움
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    initial();

    const sb = getBrowserSupabase();
    if (!sb) {
      // fallback polling (Realtime 미설정 환경)
      const tick = setInterval(() => {
        if (cancelled) return;
        getActiveDocs(24)
          .then((res) => {
            if (cancelled) return;
            // 전체 교체 (단순 fallback)
            itemsByJobId.clear();
            itemsByDocId.clear();
            for (const it of res.items) upsertItem(it);
            flush();
          })
          .catch(() => {});
      }, FALLBACK_POLL_MS);
      return () => {
        cancelled = true;
        clearInterval(tick);
      };
    }

    const channel = sb
      .channel('jet-rag:ingest_jobs')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'ingest_jobs' },
        (payload) => {
          if (cancelled) return;
          // payload.new 는 row snapshot. queued_at < 24h 필터는 frontend 에서 단순화.
          const next = payload.new as
            | {
                id: string;
                doc_id: string;
                status: string;
                current_stage: string | null;
                attempts: number;
                error_msg: string | null;
                queued_at: string;
                started_at: string | null;
                finished_at: string | null;
              }
            | undefined;

          if (!next || !next.id || !next.doc_id) return;

          const existing = itemsByJobId.get(next.id) ?? itemsByDocId.get(next.doc_id);

          if (TERMINAL_STATUSES.has(next.status)) {
            // 완료·실패·취소 → 제거 + onTerminal 콜백
            if (existing) {
              const finalItem: ActiveDocItem = {
                ...existing,
                job: {
                  ...existing.job,
                  status: next.status as ActiveDocItem['job']['status'],
                  current_stage: next.current_stage as ActiveDocItem['job']['current_stage'],
                  attempts: next.attempts,
                  error_msg: next.error_msg,
                  finished_at: next.finished_at,
                },
              };
              removeItem(next.doc_id, next.id);
              flush();
              onTerminalRef.current?.(finalItem, next.status);
            }
            return;
          }

          // queued/running — upsert 후 flush. file_name/size 는 active fetch 결과 보존,
          // 신규 row 면 백엔드 fetch 1회 보강 (heavy 없음, 단건 GET).
          if (existing) {
            upsertItem({
              ...existing,
              job: {
                ...existing.job,
                status: next.status as ActiveDocItem['job']['status'],
                current_stage: next.current_stage as ActiveDocItem['job']['current_stage'],
                attempts: next.attempts,
                error_msg: next.error_msg,
                queued_at: next.queued_at,
                started_at: next.started_at,
                finished_at: next.finished_at,
              },
            });
            flush();
          } else {
            // 신규 doc — 메타 보강을 위해 active 재조회 (debounce 효과)
            getActiveDocs(24)
              .then((res) => {
                if (cancelled) return;
                for (const it of res.items) upsertItem(it);
                flush();
              })
              .catch(() => {});
          }
        },
      )
      .subscribe();

    return () => {
      cancelled = true;
      sb.removeChannel(channel);
    };
  }, []);

  return { items, loading };
}
