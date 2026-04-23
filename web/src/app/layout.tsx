import type { Metadata } from 'next';
import { Noto_Sans_KR } from 'next/font/google';
import './globals.css';
import { Header } from '@/components/jet-rag/header';
import { cn } from '@/lib/utils';

const notoSansKr = Noto_Sans_KR({
  subsets: ['latin'],
  weight: ['300', '400', '500', '700'],
  variable: '--font-sans',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Jet-Rag',
  description: '한국어 멀티포맷 RAG 개인 지식 에이전트',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={cn('h-full antialiased', notoSansKr.variable)}>
      <body className="min-h-full flex flex-col font-sans">
        <Header />
        {children}
      </body>
    </html>
  );
}
