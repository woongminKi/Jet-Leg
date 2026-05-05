import { getActiveDocs, type ActiveDocsResponse } from '@/lib/api';
import { IngestUI } from '@/components/jet-rag/ingest-ui';
import type { UploadItemData } from '@/components/jet-rag/upload-item';

/** W25 D14 Sprint 0 — RSC 첫 fetch 로 진행 중·실패 doc 자동 표시.
 *  새로고침 후에도 처리 현황 카드가 살아있도록, GET /documents/active 결과를
 *  UploadItemData placeholder 로 변환해 IngestUI 에 hydrate. 백엔드 미기동 시
 *  graceful — items=[] 빈 리스트로 떨어뜨리고 기존 빈 상태 안내문 노출. */
export default async function IngestPage() {
  const active = await getActiveDocs(24).catch<ActiveDocsResponse | null>(
    () => null,
  );
  const initialItems: UploadItemData[] = (active?.items ?? []).map((d) => ({
    localId: `restored-${d.doc_id}`,
    fileName: d.file_name,
    sizeBytes: d.size_bytes,
    docId: d.doc_id,
    jobId: d.job.job_id,
    duplicated: false,
    retryNonce: 0,
  }));

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

        <IngestUI initialItems={initialItems} />
      </div>
    </main>
  );
}
