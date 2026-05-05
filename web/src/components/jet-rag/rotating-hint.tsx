'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface RotatingHintProps {
  /** 회전할 메시지 풀 — 1개면 회전 없이 고정. */
  messages: readonly string[];
  /** 회전 간격(ms). default 90000 (90초). */
  intervalMs?: number;
  className?: string;
}

/** W25 D14 Sprint A — 임베딩 진행 중 안내문 자동 회전.
 *
 * 일정 시간(default 90초)마다 다음 메시지로 fade transition. AGENTS.md §2 패턴
 * 따라 useEffect 안 동기 setState 회피 — interval 콜백 안 setState 만 사용.
 */
export function RotatingHint({
  messages,
  intervalMs = 90000,
  className,
}: RotatingHintProps) {
  const [idx, setIdx] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (messages.length <= 1) return;
    const FADE_MS = 300;
    const tick = setInterval(() => {
      // fade-out → 메시지 swap → fade-in
      setVisible(false);
      window.setTimeout(() => {
        setIdx((prev) => (prev + 1) % messages.length);
        setVisible(true);
      }, FADE_MS);
    }, intervalMs);
    return () => clearInterval(tick);
  }, [messages, intervalMs]);

  if (messages.length === 0) return null;
  return (
    <p
      className={cn(
        'text-xs text-muted-foreground transition-opacity duration-300',
        visible ? 'opacity-100' : 'opacity-0',
        className,
      )}
      aria-live="polite"
    >
      {messages[idx]}
    </p>
  );
}

/** 기본 안내문 풀 — 임베딩 진행 중 1~2분 마다 회전. timedOut 시는 별도 fixed 메시지. */
export const DEFAULT_INGEST_HINTS = [
  '문서를 처리하고 있어요. 잠시만 기다려 주세요.',
  '조금 시간이 걸릴 수 있어요. 새로고침 없이 대기하면 자동으로 업데이트됩니다.',
  '큰 파일은 임베딩에 시간이 더 소요됩니다.',
  'PDF 표·그림은 vision 분석으로 추가 시간이 필요합니다.',
  '브라우저를 닫아도 백엔드 처리는 계속됩니다.',
  '처리 결과는 자동으로 화면에 반영됩니다.',
] as const;
