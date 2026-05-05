'use client';

import { createContext, useContext, type ReactNode } from 'react';
import {
  useActiveDocsRealtime,
  type ActiveDocsState,
} from '@/lib/hooks/use-active-docs-realtime';
import { notifyDocTerminal } from '@/lib/notifications/notify-doc';

/** W25 D14 — ActiveDocsContext + Provider — useActiveDocsRealtime singleton.
 *
 *  이슈: IngestUI / ActiveDocsIndicator 가 각각 useActiveDocsRealtime 호출하면
 *  같은 channel name (`jet-rag:ingest_jobs`) 으로 중복 subscribe → Supabase Realtime
 *  "cannot add postgres_changes callbacks after subscribe()" 에러 + 토스트 중복.
 *
 *  해결: layout.tsx 가 Provider 한 번만 wrap → 하위 컴포넌트는 useActiveDocs() 로
 *  같은 state 공유. Realtime channel 1개만, onTerminal 콜백 중복 0.
 */

const ActiveDocsContext = createContext<ActiveDocsState | null>(null);

export function ActiveDocsProvider({ children }: { children: ReactNode }) {
  const value = useActiveDocsRealtime(notifyDocTerminal);
  return (
    <ActiveDocsContext.Provider value={value}>{children}</ActiveDocsContext.Provider>
  );
}

export function useActiveDocs(): ActiveDocsState {
  const ctx = useContext(ActiveDocsContext);
  if (!ctx) {
    // Provider 미래핑 시 안전 fallback (loading=true, items=[])
    return { items: [], loading: true };
  }
  return ctx;
}
