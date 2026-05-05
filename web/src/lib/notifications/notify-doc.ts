'use client';

import { toast } from 'sonner';
import type { ActiveDocItem } from '@/lib/api';

/** W25 D14 Phase 1 — doc 완료/실패 알림 추상화.
 *
 *  Phase 2 (PWA + Web Push) 도입 시 이 함수 안에서 push subscription 분기 추가만
 *  하면 호출부 무수정. 현재는 sonner toast 만 트리거.
 */

const navigateToDoc = (docId: string) => {
  window.location.assign(`/doc/${docId}`);
};

export function notifyDocCompleted(item: ActiveDocItem): void {
  toast.success('문서 처리 완료', {
    description: item.file_name,
    duration: 8000,
    action: {
      label: '상세 보기',
      onClick: () => navigateToDoc(item.doc_id),
    },
  });
  // Phase 2 hook (예시):
  // if (Notification.permission === 'granted') {
  //   navigator.serviceWorker?.ready.then((reg) => {
  //     reg.showNotification('문서 처리 완료', { body: item.file_name, ... });
  //   });
  // }
}

export function notifyDocFailed(item: ActiveDocItem): void {
  toast.error('문서 처리 실패', {
    description: item.file_name,
    duration: 10000,
    action: {
      label: '다시 시도',
      onClick: () => navigateToDoc(item.doc_id),
    },
  });
}

export function notifyDocTerminal(item: ActiveDocItem, terminalStatus: string): void {
  if (terminalStatus === 'completed') notifyDocCompleted(item);
  else if (terminalStatus === 'failed') notifyDocFailed(item);
  // cancelled 은 사용자 의도 종료 → 알림 없음
}
