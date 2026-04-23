const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`[${status}] ${detail}`);
    this.name = 'ApiError';
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...(init?.headers ?? {}) },
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new ApiError(res.status, await safeReadDetail(res));
  }
  return res.json() as Promise<T>;
}

export async function apiPostFormData<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    body: formData,
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new ApiError(res.status, await safeReadDetail(res));
  }
  return res.json() as Promise<T>;
}

/**
 * Body 없는 단순 POST. reingest 처럼 path 만으로 동작이 결정되는 엔드포인트용.
 * Content-Length: 0 을 명시해 일부 프록시가 빈 POST 를 거절하지 않도록 한다.
 */
export async function apiPost<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Length': '0' },
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new ApiError(res.status, await safeReadDetail(res));
  }
  return res.json() as Promise<T>;
}

async function safeReadDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return body.detail;
    return JSON.stringify(body);
  } catch {
    return res.statusText;
  }
}
