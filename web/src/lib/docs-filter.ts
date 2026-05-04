/**
 * `/docs` 라우트의 in-memory 필터·태그 집계·URL 빌더 (W25 D1·D2).
 *
 * - 단일 사용자 100건 규모 가정 — refetch 없이 client 측 필터.
 * - 외부 의존성 0 — 순수 함수만. 단위 테스트 친화 (DocsBrowser 와 분리 export).
 * - destination 통일: `popular-tags-card` 도 본 모듈의 `buildDocsUrl({ tag })` 와 같은 의미의
 *   `/docs?tag=...` 를 사용한다 (역할 분담 — `/search` 는 자연어, `/docs` 는 메타).
 */
import type { Document, DocType } from '@/lib/api';

export interface DocsFilter {
  /** 활성 태그. null 이면 태그 필터 비활성. 빈 문자열도 비활성 처리. */
  tag: string | null;
  /** 활성 문서 타입. null 이면 타입 필터 비활성. */
  type: DocType | null;
}

/**
 * 단일 문서가 현재 필터를 모두 통과하는지 검사.
 * - tag: 문서 `tags` 배열에 정확히 포함되어야 통과 (대소문자 구분).
 * - type: 문서 `doc_type` 와 정확히 일치해야 통과.
 * - 둘 다 비활성이면 항상 통과.
 */
function matchesFilter(doc: Document, filter: DocsFilter): boolean {
  if (filter.tag && !doc.tags.includes(filter.tag)) return false;
  if (filter.type && doc.doc_type !== filter.type) return false;
  return true;
}

/**
 * 필터 적용 — 입력 순서 보존 (백엔드의 created_at desc 그대로).
 * 빈 필터는 전체 반환 (참조 동일성을 깨도 무방, in-memory 100건 규모).
 */
export function filterDocuments(
  docs: readonly Document[],
  filter: DocsFilter,
): Document[] {
  if (!filter.tag && !filter.type) return [...docs];
  return docs.filter((d) => matchesFilter(d, filter));
}

/**
 * 전체 문서의 `tags` 빈도 집계.
 * - 빈도 desc, 동률 시 태그 사전순 asc.
 * - 빈 입력 / 모든 태그 누락 시 빈 배열.
 */
export function aggregateTags(
  docs: readonly Document[],
): Array<{ tag: string; count: number }> {
  const counter = new Map<string, number>();
  for (const doc of docs) {
    for (const tag of doc.tags) {
      counter.set(tag, (counter.get(tag) ?? 0) + 1);
    }
  }
  return Array.from(counter.entries())
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => (b.count - a.count) || a.tag.localeCompare(b.tag));
}

/**
 * 등장한 doc_type 집합. 토글 UI 가 실제 데이터 기반으로 옵션 제한할 때 사용.
 * - 등장 빈도 desc.
 */
export function aggregateDocTypes(
  docs: readonly Document[],
): Array<{ type: DocType; count: number }> {
  const counter = new Map<DocType, number>();
  for (const doc of docs) {
    counter.set(doc.doc_type, (counter.get(doc.doc_type) ?? 0) + 1);
  }
  return Array.from(counter.entries())
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count);
}

/**
 * `/docs` 라우트 URL 빌더.
 * - 빈 값(null/undefined/빈 문자열)은 query param 에서 제거.
 * - 둘 다 null → `/docs` (no query string).
 * - 양쪽 모두 활성 → `/docs?tag=foo&type=pdf` (URLSearchParams 의 안정적 순서).
 */
export function buildDocsUrl(input: {
  tag?: string | null;
  type?: DocType | string | null;
}): string {
  const params = new URLSearchParams();
  if (input.tag) params.set('tag', input.tag);
  if (input.type) params.set('type', input.type);
  const qs = params.toString();
  return qs ? `/docs?${qs}` : '/docs';
}
