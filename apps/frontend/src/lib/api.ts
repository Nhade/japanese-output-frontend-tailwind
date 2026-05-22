type QueryValue = string | number | boolean | null | undefined;

export interface ApiRequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  query?: Record<string, QueryValue>;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

const API_BASE_URL = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '').replace(/\/+$/, '');

function normalizePath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`;
}

function appendQuery(path: string, query?: Record<string, QueryValue>): string {
  if (!query) return path;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') continue;
    params.set(key, String(value));
  }

  const qs = params.toString();
  return qs ? `${path}${path.includes('?') ? '&' : '?'}${qs}` : path;
}

export function apiUrl(path: string, query?: Record<string, QueryValue>): string {
  return `${API_BASE_URL}${appendQuery(normalizePath(path), query)}`;
}

async function parseResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }

  return text;
}

function errorMessage(data: unknown, fallback: string): string {
  if (data && typeof data === 'object' && 'error' in data) {
    const value = (data as { error?: unknown }).error;
    if (typeof value === 'string' && value.trim()) return value;
  }
  if (typeof data === 'string' && data.trim()) return data;
  return fallback;
}

export async function apiFetch(path: string, options: ApiRequestOptions = {}): Promise<Response> {
  const { body, query, headers, ...init } = options;
  const requestHeaders = new Headers(headers);
  let requestBody: BodyInit | null | undefined;

  if (body === undefined || body === null) {
    requestBody = undefined;
  } else if (
    typeof body === 'string'
    || body instanceof Blob
    || body instanceof FormData
    || body instanceof URLSearchParams
  ) {
    requestBody = body;
  } else {
    requestHeaders.set('Content-Type', 'application/json');
    requestBody = JSON.stringify(body);
  }

  const response = await fetch(apiUrl(path, query), {
    credentials: 'include',
    ...init,
    headers: requestHeaders,
    body: requestBody,
  });

  if (!response.ok) {
    const data = await parseResponse(response);
    throw new ApiError(errorMessage(data, `Request failed with ${response.status}`), response.status, data);
  }

  return response;
}

export async function apiJson<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const response = await apiFetch(path, options);
  return await parseResponse(response) as T;
}

export async function apiBlob(path: string, options: ApiRequestOptions = {}): Promise<Blob> {
  const response = await apiFetch(path, options);
  return await response.blob();
}
