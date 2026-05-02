'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

interface SearchSubheaderProps {
  initialQuery: string;
  total: number;
  tookMs: number;
  /** W7 Day 1 — 검색 경로 진단 (선택, backward compat). dense/sparse hits + fallback 표시. */
  queryParsed?: {
    has_dense: boolean;
    has_sparse: boolean;
    dense_hits: number;
    sparse_hits: number;
    fused: number;
    fallback_reason?: string | null;
  };
}

export function SearchSubheader({
  initialQuery,
  total,
  tookMs,
  queryParsed,
}: SearchSubheaderProps) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  };

  return (
    <div className="sticky top-16 z-40 border-b border-border bg-card/95 backdrop-blur">
      <div className="container mx-auto flex items-center gap-3 px-4 py-3 md:px-6">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => router.push('/')}
          aria-label="홈으로"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>

        <form onSubmit={handleSubmit} className="relative flex-1 max-w-2xl">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            name="q"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="검색어를 입력하세요"
            className="h-10 pl-9"
          />
        </form>

        <Badge variant="secondary" className="hidden whitespace-nowrap sm:inline-flex">
          {total}개 결과 · {(tookMs / 1000).toFixed(2)}초
        </Badge>
        {queryParsed && (
          <div
            className="hidden items-center gap-1 md:inline-flex"
            title={
              queryParsed.fallback_reason
                ? `fallback: ${queryParsed.fallback_reason}`
                : `dense ${queryParsed.dense_hits} · sparse ${queryParsed.sparse_hits} → fused ${queryParsed.fused}`
            }
          >
            <Badge
              variant={queryParsed.has_dense ? 'outline' : 'destructive'}
              className="h-5 px-1.5 text-[10px]"
            >
              dense {queryParsed.dense_hits}
            </Badge>
            <Badge
              variant={queryParsed.has_sparse ? 'outline' : 'secondary'}
              className="h-5 px-1.5 text-[10px]"
            >
              sparse {queryParsed.sparse_hits}
            </Badge>
            {queryParsed.fallback_reason && (
              <Badge variant="destructive" className="h-5 px-1.5 text-[10px]">
                {queryParsed.fallback_reason}
              </Badge>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
