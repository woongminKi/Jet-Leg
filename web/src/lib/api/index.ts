import { apiGet, apiPostFormData } from './client';
import type {
  DocumentListResponse,
  DocumentStatusResponse,
  SearchResponse,
  SourceChannel,
  Stats,
  UploadResponse,
} from './types';

export * from './types';
export { ApiError } from './client';

export const getStats = () => apiGet<Stats>('/stats');

export const listDocuments = (limit = 20, offset = 0) =>
  apiGet<DocumentListResponse>(`/documents?limit=${limit}&offset=${offset}`);

export const searchDocuments = (q: string, limit = 10, offset = 0) =>
  apiGet<SearchResponse>(
    `/search?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`,
  );

export const uploadDocument = (
  file: File,
  sourceChannel: SourceChannel = 'drag-drop',
) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('source_channel', sourceChannel);
  return apiPostFormData<UploadResponse>('/documents', fd);
};

export const getDocumentStatus = (docId: string, includeLogs = false) =>
  apiGet<DocumentStatusResponse>(
    `/documents/${docId}/status${includeLogs ? '?include_logs=true' : ''}`,
  );
