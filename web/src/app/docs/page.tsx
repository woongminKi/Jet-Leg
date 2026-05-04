/**
 * `/docs` 라우트 — 전체 문서 + 태그/타입 필터 (W25 D1·D2).
 *
 * - W17 패턴 1 — Server Component 첫 fetch + Client Component 가 in-memory 필터.
 * - 백엔드 무변경 — `GET /documents` 재사용 (limit=100, MVP 단일 사용자 가정).
 * - graceful fallback — `.catch(() => null)` 로 백엔드 미기동 환경 대응.
 * - searchParams 는 Next 16 기준 Promise.
 */

import { listDocuments } from '@/lib/api';
import type { DocType } from '@/lib/api';
import { DocsBrowser } from '@/components/jet-rag/docs/docs-browser';

interface DocsPageProps {
  searchParams: Promise<{ tag?: string; type?: string }>;
}

const INITIAL_FETCH_LIMIT = 100;

const DOC_TYPE_VALUES: DocType[] = [
  'pdf',
  'hwp',
  'hwpx',
  'docx',
  'pptx',
  'image',
  'url',
  'txt',
  'md',
];

function parseDocType(raw: string | undefined): DocType | null {
  if (!raw) return null;
  return (DOC_TYPE_VALUES as string[]).includes(raw) ? (raw as DocType) : null;
}

function parseTag(raw: string | undefined): string | null {
  const trimmed = raw?.trim();
  return trimmed ? trimmed : null;
}

export default async function DocsPage({ searchParams }: DocsPageProps) {
  const { tag: tagParam, type: typeParam } = await searchParams;
  const initialTag = parseTag(tagParam);
  const initialType = parseDocType(typeParam);

  const response = await listDocuments(INITIAL_FETCH_LIMIT, 0).catch(() => null);

  if (!response) {
    return (
      <main className="flex-1">
        <DocsHeader />
        <section className="container mx-auto px-4 py-8 md:px-6 md:py-12">
          <div className="rounded-lg border border-dashed border-border bg-muted/20 px-6 py-16 text-center">
            <p className="text-base font-medium text-foreground">
              문서 목록을 불러오지 못했어요
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              잠시 후 다시 시도해 주세요. (백엔드 미기동 시 발생)
            </p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="flex-1">
      <DocsHeader />
      <section className="container mx-auto px-4 py-8 md:px-6 md:py-12">
        <DocsBrowser
          initialDocuments={response.items}
          total={response.total}
          initialTag={initialTag}
          initialType={initialType}
        />
      </section>
    </main>
  );
}

function DocsHeader() {
  return (
    <header className="border-b border-border bg-card/40">
      <div className="container mx-auto px-4 py-8 md:px-6 md:py-10">
        <h1 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
          전체 문서
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          태그와 문서 타입으로 좁혀 보세요. 자연어 검색은 상단 검색창을 이용하세요.
        </p>
      </div>
    </header>
  );
}
