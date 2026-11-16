import { describe, expect, it } from 'vitest';

import { detectLanguage } from '@/app/providers/i18n';
import { dayPart, formatTime, intlLocale, localHour } from '@/shared/utils/datetime';

describe('intlLocale', () => {
  it('uses Kyrgyz when the runtime has it, Russian otherwise', () => {
    expect(intlLocale('ky', () => true)).toBe('ky-KG');
    expect(intlLocale('ky', () => false)).toBe('ru-RU');
    expect(intlLocale('en', () => false)).toBe('en-GB');
  });
});

describe('datetime utils', () => {
  const moment = new Date('2026-11-16T20:30:00Z');

  it('computes the local hour in the user time zone', () => {
    expect(localHour(moment, 'Asia/Bishkek')).toBe(2); // UTC+6, next day
    expect(localHour(moment, 'UTC')).toBe(20);
  });

  it('respects 12/24-hour preference', () => {
    const base = { language: 'en' as const, timezone: 'UTC' };
    expect(formatTime(moment, { ...base, timeFormat: '24h' })).toBe('20:30');
    expect(formatTime(moment, { ...base, timeFormat: '12h' })).toMatch(/8:30\s?pm/i);
  });

  it.each([
    [6, 'morning'],
    [13, 'day'],
    [19, 'evening'],
    [2, 'night'],
  ] as const)('hour %i is %s', (hour, part) => {
    expect(dayPart(hour)).toBe(part);
  });
});

describe('detectLanguage', () => {
  it('maps browser languages to supported ones', () => {
    expect(detectLanguage(['ky-KG', 'ru'])).toBe('ky');
    expect(detectLanguage(['en-US'])).toBe('en');
    expect(detectLanguage(['de-DE', 'fr'])).toBe('ru');
    expect(detectLanguage([])).toBe('ru');
  });
});

describe('clock options', () => {
  it('formats wall-clock times in 12/24-hour style', async () => {
    const { formatClock } = await import('@/shared/utils/datetime');
    expect(formatClock('07:00', '24h')).toBe('07:00');
    expect(formatClock('00:30', '12h')).toBe('12:30 AM');
    expect(formatClock('23:00', '12h')).toBe('11:00 PM');
  });

  it('offers half-hour steps and keeps an off-grid saved value', async () => {
    const { clockOptions } = await import('@/shared/utils/datetime');
    expect(clockOptions('24h')).toHaveLength(48);
    const withCustom = clockOptions('24h', '07:15');
    expect(withCustom).toHaveLength(49);
    expect(withCustom.map((o) => o.value).indexOf('07:15')).toBe(
      withCustom.map((o) => o.value).indexOf('07:00') + 1,
    );
  });
});

describe('day, week and year progress', () => {
  // 2026-11-16 is a Monday; 14:30 UTC = 20:30 in Asia/Bishkek (UTC+6).
  const now = new Date('2026-11-16T14:30:00Z');

  it('reads wall-clock fields in the user time zone', async () => {
    const { localParts } = await import('@/shared/utils/datetime');
    expect(localParts(now, 'Asia/Bishkek')).toMatchObject({
      day: 16,
      hour: 20,
      minute: 30,
      weekday: 1,
    });
    expect(localParts(new Date('2026-11-16T19:00:00Z'), 'Asia/Bishkek')).toMatchObject({
      day: 17,
      weekday: 2,
    });
  });

  it('places now inside the working window', async () => {
    const { dayWindow } = await import('@/shared/utils/datetime');
    const during = dayWindow(now, 'Asia/Bishkek', '07:00', '23:00');
    expect(during.phase).toBe('during');
    if (during.phase === 'during') {
      expect(during.minutesLeft).toBe(150);
      expect(during.progress).toBeCloseTo(810 / 960);
    }
    expect(dayWindow(now, 'Asia/Bishkek', '21:00', '23:00')).toMatchObject({
      phase: 'before',
      minutesUntilStart: 30,
    });
    expect(dayWindow(now, 'Asia/Bishkek', '07:00', '18:00')).toMatchObject({ phase: 'after' });
  });

  it('computes week progress from the chosen first weekday', async () => {
    const { weekProgress } = await import('@/shared/utils/datetime');
    expect(weekProgress(now, 'Asia/Bishkek', 1)).toBeCloseTo((20 * 60 + 30) / (7 * 1440));
    expect(weekProgress(now, 'Asia/Bishkek', 7)).toBeCloseTo((1440 + 20 * 60 + 30) / (7 * 1440));
  });

  it('computes year progress', async () => {
    const { yearProgress } = await import('@/shared/utils/datetime');
    const { year, progress } = yearProgress(now, 'Asia/Bishkek');
    expect(year).toBe(2026);
    expect(progress).toBeCloseTo((319 + 20.5 / 24) / 365, 4);
  });
});
