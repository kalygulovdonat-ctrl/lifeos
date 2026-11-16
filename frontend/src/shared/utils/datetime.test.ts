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
