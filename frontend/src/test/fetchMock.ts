import { vi } from 'vitest';

export interface Call {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: unknown;
}

type Handler = (
  call: Call,
) => { status: number; body?: unknown } | Promise<{ status: number; body?: unknown }>;

/** Minimal fetch stub: routes by "METHOD path" and records every call. */
export function mockFetch(routes: Record<string, Handler | Handler[]>) {
  const calls: Call[] = [];
  const counters: Record<string, number> = {};

  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    const method = (init.method ?? 'GET').toUpperCase();
    const path = url.split('?')[0]!.replace('/api/v1', '');
    const call: Call = {
      url,
      method,
      headers: (init.headers as Record<string, string>) ?? {},
      body: init.body ? JSON.parse(String(init.body)) : undefined,
    };
    calls.push(call);

    const key = `${method} ${path}`;
    const entry = routes[key];
    if (!entry)
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND' } }), { status: 404 });
    const index = counters[key] ?? 0;
    counters[key] = index + 1;
    const handler = Array.isArray(entry) ? entry[Math.min(index, entry.length - 1)]! : entry;
    const { status, body } = await handler(call);
    return new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  });

  vi.stubGlobal('fetch', fn);
  return { calls, fn };
}

export const apiError = (status: number, code: string, details: Record<string, unknown> = {}) => ({
  status,
  body: { success: false, error: { code, message: code, details } },
});

export const sampleProfile = {
  id: '0193a000-0000-7000-8000-000000000001',
  email: 'aibek@example.com',
  display_name: 'Айбек',
  avatar: null,
  timezone: 'Asia/Bishkek',
  language: 'ru' as const,
  time_format: '24h' as const,
  date_format: 'DD.MM.YYYY',
  week_start: 1,
  theme: 'system' as const,
  day_start_time: '07:00:00',
  day_end_time: '23:00:00',
  pomodoro_settings: { work: 25, short: 5, long: 15, cycle: 4 },
  overload_threshold_minutes: 600,
  onboarding_completed_at: null,
};
