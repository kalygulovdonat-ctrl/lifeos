import { describe, expect, it } from 'vitest';

import type { TimeEntry } from '@/shared/api/types';

import { formatStopwatch, liveSeconds } from './useTimer';

const base: TimeEntry = {
  id: 'x',
  task: null,
  task_id: null,
  event_id: null,
  category_id: null,
  description: '',
  status: 'RUNNING',
  source: 'TIMER',
  started_at: '2026-11-18T10:00:00Z',
  ended_at: null,
  paused_seconds: 120,
  duration_seconds: null,
  elapsed_seconds: 0,
  open_pause_at: null,
  is_focus: false,
};

describe('timer maths', () => {
  it('counts running time minus closed pauses', () => {
    expect(liveSeconds(base, Date.parse('2026-11-18T10:10:00Z'))).toBe(480);
  });
  it('freezes while paused', () => {
    const paused = { ...base, status: 'PAUSED' as const, open_pause_at: '2026-11-18T10:05:00Z' };
    expect(liveSeconds(paused, Date.parse('2026-11-18T11:00:00Z'))).toBe(180);
  });
  it('formats a stopwatch', () => {
    expect(formatStopwatch(59)).toBe('00:59');
    expect(formatStopwatch(3725)).toBe('1:02:05');
  });
});
