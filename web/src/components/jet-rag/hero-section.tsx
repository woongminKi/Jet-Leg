'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FileText, Search, Sparkles, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export function HeroSection() {
  const router = useRouter();
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  };

  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-primary/5 via-background to-background">
      <div className="container mx-auto px-4 py-16 md:px-6 md:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
            <Sparkles className="h-4 w-4" />
            정리하지 않아도, 기억의 단편으로 꺼내 쓰는
          </div>

          <h1 className="mb-4 text-balance text-3xl font-bold tracking-tight text-foreground md:text-4xl lg:text-5xl">
            무엇을 찾고 계신가요?
          </h1>
          <p className="mb-8 text-balance text-lg text-muted-foreground">
            자연어로 검색하면 과거에 받았던 문서를 빠르게 찾아드려요.
          </p>

          <form onSubmit={handleSubmit} className="mx-auto max-w-2xl">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="search"
                name="q"
                placeholder='예: "지난달 기재부 가이드라인 변경점"'
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="h-14 rounded-xl border-2 border-border bg-card pl-12 pr-32 text-base shadow-sm focus:border-primary"
              />
              <Button
                type="submit"
                className="absolute right-2 top-1/2 h-10 -translate-y-1/2 px-6"
              >
                검색
              </Button>
            </div>
          </form>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg" className="gap-2">
              <Link href="/ingest">
                <Upload className="h-5 w-5" />
                파일 업로드
              </Link>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="lg"
              className="gap-2"
              disabled
              title="Day 7+ 에서 활성화됩니다"
            >
              <FileText className="h-5 w-5" />
              전체 문서 보기
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
