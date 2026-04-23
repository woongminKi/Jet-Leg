import { Skeleton } from '@/components/ui/skeleton';

export default function HomeLoading() {
  return (
    <main className="flex-1">
      <section className="container mx-auto px-4 py-16 md:px-6 md:py-24">
        <div className="mx-auto max-w-3xl space-y-6">
          <Skeleton className="mx-auto h-7 w-72" />
          <Skeleton className="mx-auto h-12 w-full max-w-md" />
          <Skeleton className="mx-auto h-14 w-full max-w-2xl rounded-xl" />
          <div className="flex justify-center gap-3">
            <Skeleton className="h-11 w-32" />
            <Skeleton className="h-11 w-32" />
          </div>
        </div>
      </section>
      <section className="container mx-auto px-4 pb-12 md:px-6">
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Skeleton className="h-64 w-full rounded-xl" />
            <Skeleton className="h-32 w-full rounded-xl" />
          </div>
          <div className="space-y-6">
            <Skeleton className="h-40 w-full rounded-xl" />
            <Skeleton className="h-56 w-full rounded-xl" />
          </div>
        </div>
      </section>
    </main>
  );
}
