import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { JobStatusValue, StageValue } from '@/lib/api';
import { STAGE_LABELS, STAGE_ORDER } from '@/lib/stages';

interface StageProgressProps {
  currentStage: StageValue | null;
  status: JobStatusValue;
}

export function StageProgress({ currentStage, status }: StageProgressProps) {
  const isDone = status === 'completed';
  const isFailed = status === 'failed';
  const inProgressStage = !isDone && currentStage !== 'done' ? currentStage : null;
  const currentIdx = inProgressStage ? STAGE_ORDER.indexOf(inProgressStage) : -1;
  // W25 D14 Sprint A — running 상태 진행 stage 옆 spinner. queued/done/failed 시 미노출.
  const showRunningSpinner = status === 'running' && inProgressStage !== null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5">
        {STAGE_ORDER.map((stage, idx) => {
          const reached = isDone || idx <= currentIdx;
          const failedHere = isFailed && idx === currentIdx;
          return (
            <div
              key={stage}
              className={cn(
                'h-1.5 flex-1 rounded-full transition-colors',
                failedHere
                  ? 'bg-destructive'
                  : reached
                    ? isDone
                      ? 'bg-success'
                      : 'bg-primary'
                    : 'bg-muted',
              )}
              aria-label={STAGE_LABELS[stage]}
              title={STAGE_LABELS[stage]}
            />
          );
        })}
      </div>
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          {showRunningSpinner && (
            <Loader2 className="h-3 w-3 animate-spin text-primary" aria-hidden />
          )}
          <span>
            {isDone
              ? '모든 단계 완료'
              : isFailed
                ? `실패 단계: ${currentStage ? STAGE_LABELS[currentStage] : '시작 전'}`
                : inProgressStage
                  ? `현재: ${STAGE_LABELS[inProgressStage]}`
                  : status === 'queued'
                    ? '대기 중'
                    : '시작 전'}
          </span>
        </span>
        <span>
          {isDone
            ? `${STAGE_ORDER.length}/${STAGE_ORDER.length}`
            : isFailed
              ? '실패'
              : `${Math.max(0, currentIdx + 1)}/${STAGE_ORDER.length}`}
        </span>
      </div>
    </div>
  );
}
