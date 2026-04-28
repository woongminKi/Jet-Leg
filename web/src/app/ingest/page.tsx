'use client';

import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError, uploadDocument } from '@/lib/api';
import { DropZone } from '@/components/jet-rag/drop-zone';
import { UploadList } from '@/components/jet-rag/upload-list';
import type { UploadItemData } from '@/components/jet-rag/upload-item';

export default function IngestPage() {
  const router = useRouter();
  const [items, setItems] = useState<UploadItemData[]>([]);

  // W2 §3.M / DE-28 — 자동 이동 정책: "단일=자동, 다중=첫 완료만 자동".
  // 페이지 lifecycle 동안 1회만 라우팅. duplicated 또는 첫 completed 가 트리거.
  const autoRoutedRef = useRef(false);

  const handleFiles = async (files: File[]) => {
    const placeholders: UploadItemData[] = files.map((file) => ({
      localId: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
      fileName: file.name,
      sizeBytes: file.size,
      docId: null,
      jobId: null,
      duplicated: false,
      retryNonce: 0,
    }));
    setItems((prev) => [...placeholders, ...prev]);

    await Promise.all(
      placeholders.map(async (placeholder, idx) => {
        const file = files[idx];
        try {
          const res = await uploadDocument(file, 'drag-drop');
          setItems((prev) =>
            prev.map((it) =>
              it.localId === placeholder.localId
                ? {
                    ...it,
                    docId: res.doc_id,
                    jobId: res.job_id,
                    duplicated: res.duplicated,
                  }
                : it,
            ),
          );
          // duplicated → 즉시 기존 문서로 이동 (DE-28)
          if (res.duplicated && !autoRoutedRef.current) {
            autoRoutedRef.current = true;
            router.push(`/doc/${res.doc_id}?duplicated=1`);
          }
        } catch (err) {
          const message =
            err instanceof ApiError ? err.detail : '알 수 없는 오류가 발생했습니다.';
          setItems((prev) =>
            prev.map((it) =>
              it.localId === placeholder.localId
                ? { ...it, uploadError: message }
                : it,
            ),
          );
        }
      }),
    );
  };

  // 재시도 성공 시 같은 doc_id 의 새 job 으로 갱신 + retryNonce 증가로
  // useDocsBatchPolling 의 wakeUpKey 가 바뀌어 폴링이 재개된다.
  const handleReingest = (localId: string, jobId: string) => {
    setItems((prev) =>
      prev.map((it) =>
        it.localId === localId
          ? { ...it, jobId, retryNonce: it.retryNonce + 1 }
          : it,
      ),
    );
  };

  // 첫 completed 1회만 자동 라우팅. 그 이후의 completed 는 "상세 보기" 링크로 처리.
  const handleCompleted = (docId: string) => {
    if (autoRoutedRef.current) return;
    autoRoutedRef.current = true;
    router.push(`/doc/${docId}?uploaded=1`);
  };

  return (
    <main className="container mx-auto flex-1 px-4 py-8 md:px-6 md:py-12">
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            문서 업로드
          </h1>
          <p className="text-sm text-muted-foreground">
            한국어 PDF, HWP, DOCX, 이미지 등을 올리면 자동으로 청킹·태그·요약·임베딩까지 처리됩니다.
          </p>
        </header>

        <DropZone onFiles={handleFiles} />

        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-foreground">처리 현황</h2>
          <UploadList
            items={items}
            onReingest={handleReingest}
            onCompleted={handleCompleted}
          />
        </section>
      </div>
    </main>
  );
}
