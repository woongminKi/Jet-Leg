import Link from 'next/link';
import { ArrowRight, FileText, Sparkles } from 'lucide-react';
import type { Document } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { docTypeLabel } from '@/lib/doc-type-label';
import { buildDocsUrl } from '@/lib/docs-filter';
import { formatRelativeTime } from '@/lib/format';

interface NewArrivalsCardProps {
  documents: Document[];
}

/**
 * 최근 추가 카드.
 * W25 D1·D2 — D-1 + D-4 결합 (QA 1차 fix 반영):
 *   - 행 전체가 `/doc/{id}` 로 진입하는 Link (hover 표시).
 *   - 태그 칩은 `/docs?tag=...` 별도 Link — 행 Link 와 중첩 회피를 위해
 *     pointer-events 위계 패턴 사용:
 *       * 행 컨테이너 = `relative`
 *       * 행 Link = absolute inset-0 (z-0) — 시각 hover/focus 영역, 포인터 이벤트 수신
 *       * 본문 (제목/태그/시간) = `relative z-10 pointer-events-none` — 클릭이 행 Link 로 통과
 *       * 태그 Link / 시간 표시는 `pointer-events-auto` 로 복원 — 태그만 별개 동작
 *   - 행 Link 에 가시 `focus-visible:ring` — 본문이 z-10 으로 가리는 케이스 방지.
 *   - 키보드 접근성 — 행 Link → 태그 Link 순서로 Tab 진입.
 */
export function NewArrivalsCard({ documents }: NewArrivalsCardProps) {
  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Sparkles className="h-5 w-5 text-primary" />
          최근 추가
          {documents.length > 0 && (
            <Badge variant="secondary" className="ml-1">
              {documents.length}건
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {documents.length === 0 ? (
          <EmptyState />
        ) : (
          <ul className="divide-y divide-border">
            {documents.map((doc) => (
              <DocRow key={doc.id} doc={doc} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function DocRow({ doc }: { doc: Document }) {
  return (
    <li className="group relative -mx-2 rounded-md py-3 first:pt-0 last:pb-0 hover:bg-accent/40">
      <Link
        href={`/doc/${doc.id}`}
        aria-label={`${doc.title} 문서 열기`}
        className="absolute inset-0 z-0 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      />
      <div className="pointer-events-none relative z-10 flex items-start justify-between gap-3 px-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground group-hover:text-foreground">
            {doc.title}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
              {docTypeLabel(doc.doc_type)}
            </Badge>
            {doc.tags.slice(0, 2).map((tag) => (
              <Link
                key={tag}
                href={buildDocsUrl({ tag })}
                aria-label={`${tag} 태그로 좁혀 문서 보기`}
                title="이 태그로 좁히기"
                className="pointer-events-auto rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Badge
                  variant="secondary"
                  className="h-5 cursor-pointer px-1.5 text-[10px] hover:bg-primary hover:text-primary-foreground"
                >
                  #{tag}
                </Badge>
              </Link>
            ))}
          </div>
        </div>
        <span className="shrink-0 whitespace-nowrap text-xs text-muted-foreground">
          {formatRelativeTime(doc.created_at)}
        </span>
      </div>
    </li>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
        <FileText className="h-5 w-5 text-muted-foreground" />
      </div>
      <p className="text-sm text-muted-foreground">
        아직 추가한 문서가 없어요. 첫 파일을 올려보세요.
      </p>
      <Link
        href="/ingest"
        className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
      >
        파일 업로드
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
