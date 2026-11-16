import { afterEach, describe, expect, it, vi } from 'vitest';

import { api, ApiError, refreshAccessToken } from '@/shared/api/client';
import { useAuthStore } from '@/shared/store/authStore';
import { apiError, mockFetch, sampleProfile } from '@/test/fetchMock';

afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
  it('sends bearer token and Accept-Language', async () => {
    useAuthStore.getState().setSession('access-1', { ...sampleProfile, language: 'ky' });
    const { calls } = mockFetch({ 'GET /profile/': () => ({ status: 200, body: sampleProfile }) });

    await api.get('/profile/');

    expect(calls[0]!.headers.Authorization).toBe('Bearer access-1');
    expect(calls[0]!.headers['Accept-Language']).toBe('ky');
  });

  it('adds an Idempotency-Key to POST requests', async () => {
    const { calls } = mockFetch({ 'POST /tags/': () => ({ status: 201, body: { id: '1' } }) });
    await api.post('/tags/', { name: 'a' });
    await api.post('/tags/', { name: 'b' }, { idempotencyKey: 'fixed-key' });

    expect(calls[0]!.headers['Idempotency-Key']).toMatch(/^[0-9a-f-]{36}$/);
    expect(calls[1]!.headers['Idempotency-Key']).toBe('fixed-key');
  });

  it('turns error bodies into ApiError with field errors', async () => {
    mockFetch({
      'POST /tags/': () => apiError(400, 'VALIDATION_ERROR', { name: ['Already exists.'] }),
    });
    const error = await api.post('/tags/', { name: 'x' }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe('VALIDATION_ERROR');
    expect((error as ApiError).fieldErrors()).toEqual({ name: 'Already exists.' });
  });

  it('refreshes once on 401 and retries the original request', async () => {
    useAuthStore.getState().setSession('expired', sampleProfile);
    document.cookie = 'csrftoken=csrf-123; path=/';
    const { calls } = mockFetch({
      'GET /profile/': [
        () => apiError(401, 'TOKEN_EXPIRED'),
        () => ({ status: 200, body: sampleProfile }),
      ],
      'POST /auth/refresh/': () => ({ status: 200, body: { access: 'fresh' } }),
    });

    const profile = await api.get('/profile/');

    expect(profile).toEqual(sampleProfile);
    const refresh = calls.find((c) => c.url.endsWith('/auth/refresh/'))!;
    expect(refresh.headers['X-CSRFToken']).toBe('csrf-123');
    expect(refresh.headers['Idempotency-Key']).toBeUndefined();
    expect(calls.at(-1)!.headers.Authorization).toBe('Bearer fresh');
    expect(useAuthStore.getState().accessToken).toBe('fresh');
  });

  it('shares a single refresh between concurrent 401s', async () => {
    useAuthStore.getState().setSession('expired', sampleProfile);
    const { calls } = mockFetch({
      'GET /a/': [() => apiError(401, 'TOKEN_EXPIRED'), () => ({ status: 200, body: 'a' })],
      'GET /b/': [() => apiError(401, 'TOKEN_EXPIRED'), () => ({ status: 200, body: 'b' })],
      'POST /auth/refresh/': async () => {
        await new Promise((r) => setTimeout(r, 10));
        return { status: 200, body: { access: 'fresh' } };
      },
    });

    await expect(Promise.all([api.get('/a/'), api.get('/b/')])).resolves.toEqual(['a', 'b']);
    expect(calls.filter((c) => c.url.endsWith('/auth/refresh/'))).toHaveLength(1);
  });

  it('clears the session when refresh fails', async () => {
    useAuthStore.getState().setSession('expired', sampleProfile);
    mockFetch({
      'GET /profile/': () => apiError(401, 'TOKEN_EXPIRED'),
      'POST /auth/refresh/': () => apiError(401, 'REFRESH_INVALID'),
    });

    await expect(api.get('/profile/')).rejects.toMatchObject({ code: 'TOKEN_EXPIRED' });
    expect(useAuthStore.getState().status).toBe('anonymous');
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it('refreshAccessToken returns null without a valid cookie', async () => {
    mockFetch({ 'POST /auth/refresh/': () => apiError(401, 'REFRESH_INVALID') });
    await expect(refreshAccessToken()).resolves.toBeNull();
  });
});
