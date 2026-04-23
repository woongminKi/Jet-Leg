import Link from 'next/link';
import type { TagCount } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface PopularTagsCardProps {
  tags: TagCount[];
}

export function PopularTagsCard({ tags }: PopularTagsCardProps) {
  const top = tags.slice(0, 10);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold">인기 태그</CardTitle>
      </CardHeader>
      <CardContent>
        {top.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            아직 집계된 태그가 없어요.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {top.map((t) => (
              <Link key={t.tag} href={`/search?q=${encodeURIComponent(t.tag)}`}>
                <Badge
                  variant="secondary"
                  className="cursor-pointer transition-colors hover:bg-primary hover:text-primary-foreground"
                >
                  #{t.tag}
                  <span className="ml-1 text-[10px] opacity-70">{t.count}</span>
                </Badge>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
