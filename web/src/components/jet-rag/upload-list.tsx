'use client';

import { useDocsBatchPolling } from '@/lib/hooks/use-docs-batch-polling';
import type { UploadItemData } from './upload-item';
import { UploadItem } from './upload-item';

interface UploadListProps {
  items: UploadItemData[];
  onReingest?: (localId: string, jobId: string) => void;
  onCompleted?: (docId: string) => void;
}

export function UploadList({ items, onReingest, onCompleted }: UploadListProps) {
  // 폴링 대상 doc_id (docId 가 있고, duplicated 아닌 케이스만)
  const pollableIds = items
    .filter((it) => !it.duplicated && it.docId)
    .map((it) => it.docId as string);

  // 어떤 item 이 retry 되면 wakeUpKey 가 변해 폴링 재개
  const wakeUpKey = items.reduce((sum, it) => sum + it.retryNonce, 0);

  const polling = useDocsBatchPolling(
    pollableIds,
    pollableIds.length > 0,
    wakeUpKey,
  );

  if (items.length === 0) {
    return (
      <p className="text-center text-sm text-muted-foreground">
        업로드한 파일이 여기에 표시됩니다.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.localId}>
          <UploadItem
            data={item}
            job={item.docId ? polling.jobsByDocId[item.docId] ?? null : null}
            timedOut={polling.timedOut}
            pollingError={polling.error}
            onReingest={onReingest}
            onCompleted={onCompleted}
          />
        </li>
      ))}
    </ul>
  );
}
