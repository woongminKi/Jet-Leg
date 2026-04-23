'use client';

import { useEffect, useState } from 'react';
import { ApiError, getDocumentStatus, type JobStatus } from '@/lib/api';

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_DURATION_MS = 5 * 60 * 1000; // 5분
const MAX_CONSECUTIVE_ERRORS = 5;

export interface PollingState {
  job: JobStatus | null;
  loading: boolean;
  error: string | null;
  timedOut: boolean;
}

export function useJobStatusPolling(
  docId: string | null,
  enabled: boolean,
): PollingState {
  const [state, setState] = useState<PollingState>(() => ({
    job: null,
    loading: enabled && !!docId,
    error: null,
    timedOut: false,
  }));

  useEffect(() => {
    if (!enabled || !docId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const start = Date.now();
    let consecutiveErrors = 0;

    const isExpired = () => Date.now() - start > MAX_POLL_DURATION_MS;

    const schedule = () => {
      if (cancelled) return;
      timer = setTimeout(tick, POLL_INTERVAL_MS);
    };

    const tick = async () => {
      try {
        const res = await getDocumentStatus(docId);
        if (cancelled) return;
        consecutiveErrors = 0;
        setState((prev) => ({
          ...prev,
          job: res.job,
          loading: false,
          error: null,
        }));
        const status = res.job?.status;
        if (status === 'completed' || status === 'failed' || status === 'cancelled') return;
        if (isExpired()) {
          setState((prev) => ({ ...prev, timedOut: true }));
          return;
        }
        schedule();
      } catch (err) {
        if (cancelled) return;
        consecutiveErrors += 1;
        const message = err instanceof ApiError ? err.detail : '상태 조회 실패';
        setState((prev) => ({ ...prev, loading: false, error: message }));
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS || isExpired()) {
          setState((prev) => ({ ...prev, timedOut: true }));
          return;
        }
        schedule();
      }
    };

    tick();

    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
    };
  }, [docId, enabled]);

  return state;
}
