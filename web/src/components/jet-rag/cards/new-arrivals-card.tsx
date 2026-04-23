import Link from 'next/link';
import { ArrowRight, FileText, Sparkles } from 'lucide-react';
import type { Document } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { docTypeLabel } from '@/lib/doc-type-label';
import { formatRelativeTime } from '@/lib/format';

interface NewArrivalsCardProps {
  documents: Document[];
}

export function NewArrivalsCard({ documents }: NewArrivalsCardProps) {
  return (
    <Card>
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
              <li key={doc.id} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {doc.title}
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
                        {docTypeLabel(doc.doc_type)}
                      </Badge>
                      {doc.tags.slice(0, 2).map((tag) => (
                        <Badge
                          key={tag}
                          variant="secondary"
                          className="h-5 px-1.5 text-[10px]"
                        >
                          #{tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <span className="shrink-0 whitespace-nowrap text-xs text-muted-foreground">
                    {formatRelativeTime(doc.created_at)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
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
