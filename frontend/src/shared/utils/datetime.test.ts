import { describe, expect, it } from 'vitest';

import { detectLanguage } from '@/app/providers/i18n';
import {
  addDays,
  addMonths,
  clockOptions,
  dateKey,
  dayPart,
  dayWindow,
  daysBetween,
  formatClock,
  formatTime,
  intlLocale,
  isoWeekday,
  localHour,
  localParts,
  startOfWeek,
  weekProgress,
  yearProgress,
  zonedIso,
} from '@/shared/utils/datetime';

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
  it('formats wall-clock times in 12/24-hour style', () => {
    expect(formatClock('07:00', '24h')).toBe('07:00');
    expect(formatClock('00:30', '12h')).toBe('12:30 AM');
    expect(formatClock('23:00', '12h')).toBe('11:00 PM');
  });

  it('offers half-hour steps and keeps an off-grid saved value', () => {
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

  it('reads wall-clock fields in the user time zone', () => {
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

  it('places now inside the working window', () => {
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

  it('computes week progress from the chosen first weekday', () => {
    expect(weekProgress(now, 'Asia/Bishkek', 1)).toBeCloseTo((20 * 60 + 30) / (7 * 1440));
    expect(weekProgress(now, 'Asia/Bishkek', 7)).toBeCloseTo((1440 + 20 * 60 + 30) / (7 * 1440));
  });

  it('computes year progress', () => {
    const { year, progress } = yearProgress(now, 'Asia/Bishkek');
    expect(year).toBe(2026);
    expect(progress).toBeCloseTo((319 + 20.5 / 24) / 365, 4);
  });
});

describe('calendar keys', () => {
  it('converts wall clock to UTC across DST', () => {
    expect(zonedIso('2026-11-18', '10:00', 'Asia/Bishkek')).toBe('2026-11-18T04:00:00.000Z');
    expect(zonedIso('2026-07-01', '09:00', 'Europe/Berlin')).toBe('2026-07-01T07:00:00.000Z');
    expect(zonedIso('2026-12-01', '09:00', 'Europe/Berlin')).toBe('2026-12-01T08:00:00.000Z');
  });

  it('does week and month arithmetic on local dates', () => {
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(addMonths('2026-01-31', 1)).toBe('2026-02-01');
    expect(isoWeekday('2026-11-18')).toBe(3);
    expect(startOfWeek('2026-11-18', 1)).toBe('2026-11-16');
    expect(startOfWeek('2026-11-18', 7)).toBe('2026-11-15');
    expect(daysBetween('2026-11-16', '2026-11-22')).toBe(6);
    // 20:00 UTC on the 18th is already the 19th in Bishkek (UTC+6)
    expect(dateKey(new Date('2026-11-18T20:00:00Z'), 'Asia/Bishkek')).toBe('2026-11-19');
  });
});
