import Link from 'next/link';
import { Upload, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { HeaderSearch } from './header-search';
import { HeaderMobileToggle } from './header-mobile-toggle';

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
      <div className="container mx-auto flex h-16 items-center justify-between gap-4 px-4 md:px-6">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Zap className="h-5 w-5" />
          </div>
          <span className="hidden font-semibold text-foreground sm:inline-block">
            Jet-Rag
          </span>
        </Link>

        <HeaderSearch />

        <div className="flex items-center gap-2">
          <Button asChild size="sm" className="hidden sm:flex gap-2">
            <Link href="/ingest">
              <Upload className="h-4 w-4" />
              <span className="hidden lg:inline">업로드</span>
            </Link>
          </Button>

          <HeaderMobileToggle />
        </div>
      </div>
    </header>
  );
}
