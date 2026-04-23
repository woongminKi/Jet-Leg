import { getStats, listDocuments } from '@/lib/api';
import { HeroSection } from '@/components/jet-rag/hero-section';
import { HomeGrid } from '@/components/jet-rag/home-grid';

export default async function HomePage() {
  const [stats, documents] = await Promise.all([
    getStats(),
    listDocuments(5),
  ]);

  return (
    <main className="flex-1">
      <HeroSection />
      <HomeGrid stats={stats} recentDocuments={documents.items} />
    </main>
  );
}
