import { describe, expect, it } from 'vitest';

import type { CalendarEvent } from '@/shared/api/types';

import { eventsOnDay, layoutDay } from './layout';

const TZ = 'Asia/Bishkek'; // UTC+6, no DST

function ev(title: string, start: string, end: string): CalendarEvent {
  return {
    id: title,
    series_id: null,
    original_start_at: null,
    occurrence_key: null,
    title,
    description: '',
    location: '',
    start_at: start,
    end_at: end,
    all_day: false,
    timezone: TZ,
    time_type: 'FIXED',
    status: 'PLANNED',
    category_id: null,
    color: null,
    task: null,
    reminder_minutes: null,
    recurrence: null,
  };
}

describe('layoutDay', () => {
  it('places events by local minutes', () => {
    const [p] = layoutDay(
      [ev('a', '2026-11-18T03:00:00Z', '2026-11-18T04:30:00Z')],
      '2026-11-18',
      TZ,
    );
    expect(p).toMatchObject({ top: 9 * 60, bottom: 10 * 60 + 30, column: 0, columns: 1 });
  });

  it('puts overlapping events side by side and keeps clusters apart', () => {
    const placed = layoutDay(
      [
        ev('a', '2026-11-18T03:00:00Z', '2026-11-18T05:00:00Z'),
        ev('b', '2026-11-18T04:00:00Z', '2026-11-18T06:00:00Z'),
        ev('c', '2026-11-18T05:30:00Z', '2026-11-18T06:30:00Z'),
        ev('d', '2026-11-18T08:00:00Z', '2026-11-18T09:00:00Z'),
      ],
      '2026-11-18',
      TZ,
    );
    const by = Object.fromEntries(placed.map((p) => [p.event.title, p]));
    expect([by.a!.column, by.b!.column, by.c!.column]).toEqual([0, 1, 0]);
    expect(by.a!.columns).toBe(2);
    expect(by.d).toMatchObject({ column: 0, columns: 1 });
  });

  it('clips events that cross midnight', () => {
    const late = ev('late', '2026-11-18T17:00:00Z', '2026-11-18T20:00:00Z'); // 23:00–02:00 local
    const [today] = layoutDay([late], '2026-11-18', TZ);
    const [tomorrow] = layoutDay([late], '2026-11-19', TZ);
    expect(today).toMatchObject({ top: 23 * 60, bottom: 24 * 60, continuesAfter: true });
    expect(tomorrow).toMatchObject({ top: 0, bottom: 120, continuesBefore: true });
    expect(eventsOnDay([late], '2026-11-20', TZ)).toEqual([]);
  });
});
