/**
 * Single HTTP client for the LifeOS API (SDD §8.4).
 *
 * - Access token lives only in memory (authStore), never in localStorage (ADR-004).
 * - Refresh token is an HttpOnly cookie; refresh/logout send the CSRF token (double submit).
 * - On 401 TOKEN_EXPIRED the client refreshes once (single-flight) and retries the request.
 * - Every POST gets an Idempotency-Key unless the caller passes one (ADR-019).
 */
import { useAuthStore } from '@/shared/store/authStore';

export const API_BASE = '/api/v1';

export interface ApiErrorBody {
  success: false;
  error: { code: string; message: string; details: Record<string, unknown> };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Field errors as `{ field: "first message" }` for forms. */
  fieldErrors(): Record<string, string> {
    const result: Record<string, string> = {};
    for (const [field, value] of Object.entries(this.details)) {
      const first = Array.isArray(value) ? value[0] : value;
      if (typeof first === 'string') result[field] = first;
    }
    return result;
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  idempotencyKey?: string | false;
  signal?: AbortSignal;
  /** Internal: skip the refresh-and-retry cycle. */
  skipAuthRefresh?: boolean;
  /** Internal: endpoint authenticated by cookie and protected by CSRF. */
  csrf?: boolean;
}

export function readCookie(name: string): string | undefined {
  const match = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : undefined;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = `${API_BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as Partial<ApiErrorBody>;
    if (body && body.error) {
      return new ApiError(response.status, body.error.code, body.error.message, body.error.details);
    }
  } catch {
    // non-JSON error (proxy, network appliance)
  }
  return new ApiError(
    response.status,
    response.status >= 500 ? 'INTERNAL_ERROR' : 'UNKNOWN_ERROR',
    response.statusText,
  );
}

let refreshInFlight: Promise<string | null> | null = null;

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = request<{ access: string }>('/auth/refresh/', {
      method: 'POST',
      skipAuthRefresh: true,
      csrf: true,
      idempotencyKey: false,
    })
      .then((data) => {
        useAuthStore.getState().setAccessToken(data.access);
        return data.access;
      })
      .catch(() => {
        useAuthStore.getState().clear();
        return null;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, signal, skipAuthRefresh = false, csrf = false } = options;
  const headers: Record<string, string> = { Accept: 'application/json' };
  const { accessToken, language } = useAuthStore.getState();

  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (language) headers['Accept-Language'] = language;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (csrf) {
    const token = readCookie('csrftoken');
    if (token) headers['X-CSRFToken'] = token;
  }
  if (method === 'POST' && options.idempotencyKey !== false) {
    headers['Idempotency-Key'] = options.idempotencyKey || newIdempotencyKey();
  }

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
    signal,
  });

  if (response.status === 401 && !skipAuthRefresh) {
    const error = await parseError(response);
    if (error.code === 'TOKEN_EXPIRED' || error.code === 'NOT_AUTHENTICATED') {
      const fresh = await refreshAccessToken();
      if (fresh) return request<T>(path, { ...options, skipAuthRefresh: true });
    }
    throw error;
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions['query'], signal?: AbortSignal) =>
    request<T>(path, { query, signal }),
  post: <T>(path: string, body?: unknown, options: Omit<RequestOptions, 'method' | 'body'> = {}) =>
    request<T>(path, { ...options, method: 'POST', body }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body }),
  delete: (path: string) => request<void>(path, { method: 'DELETE' }),
};
