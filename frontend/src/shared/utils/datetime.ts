/**
 * Date/time formatting in the user's time zone and locale (SDD §2, §8.5).
 * The API always returns UTC with an offset; we only convert for display.
 */
import type { Language, TimeFormat } from '@/shared/api/types';

/**
 * Intl locale tags. Some browsers ship ICU without Kyrgyz data; then dates use Russian,
 * the same fallback the UI translations use (i18n fallbackLng ky → ru).
 */
const INTL_LOCALE: Record<Language, string> = { ru: 'ru-RU', en: 'en-GB', ky: 'ky-KG' };
const INTL_FALLBACK: Partial<Record<Language, string>> = { ky: 'ru-RU' };

export function intlLocale(
  language: Language,
  isSupported: (tag: string) => boolean = (tag) =>
    Intl.DateTimeFormat.supportedLocalesOf([tag]).length > 0,
): string {
  const tag = INTL_LOCALE[language];
  if (isSupported(tag)) return tag;
  return INTL_FALLBACK[language] ?? tag;
}

export interface DisplayPrefs {
  language: Language;
  timezone: string;
  timeFormat: TimeFormat;
}

export function formatLongDate(date: Date, prefs: DisplayPrefs): string {
  return new Intl.DateTimeFormat(intlLocale(prefs.language), {
    timeZone: prefs.timezone,
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

export function formatTime(date: Date, prefs: DisplayPrefs): string {
  return new Intl.DateTimeFormat(intlLocale(prefs.language), {
    timeZone: prefs.timezone,
    hour: 'numeric',
    minute: '2-digit',
    hour12: prefs.timeFormat === '12h',
  }).format(date);
}

/** Local hour (0–23) of `date` in the given IANA zone. */
export function localHour(date: Date, timezone: string): number {
  const hour = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    hour: 'numeric',
    hourCycle: 'h23',
  }).format(date);
  return Number(hour);
}

export type DayPart = 'morning' | 'day' | 'evening' | 'night';

export function dayPart(hour: number): DayPart {
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 18) return 'day';
  if (hour >= 18 && hour < 23) return 'evening';
  return 'night';
}

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

export function supportedTimezones(): string[] {
  const intl = Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] };
  const zones = intl.supportedValuesOf?.('timeZone') ?? [];
  return zones.includes('UTC') ? zones : ['UTC', ...zones];
}

/** "HH:MM" wall-clock time rendered in the user's 12/24-hour preference (no time zone involved). */
export function formatClock(hhmm: string, timeFormat: TimeFormat): string {
  const [h = 0, m = 0] = hhmm.split(':').map(Number);
  const mm = String(m).padStart(2, '0');
  if (timeFormat === '24h') return `${String(h).padStart(2, '0')}:${mm}`;
  const suffix = h < 12 ? 'AM' : 'PM';
  return `${h % 12 || 12}:${mm} ${suffix}`;
}

/** Half-hour steps for a day, keeping an off-grid current value selectable. */
export function clockOptions(
  timeFormat: TimeFormat,
  current?: string,
): Array<{ value: string; label: string }> {
  const values = Array.from({ length: 48 }, (_, i) => {
    const h = String(Math.floor(i / 2)).padStart(2, '0');
    return `${h}:${i % 2 ? '30' : '00'}`;
  });
  if (current && !values.includes(current)) values.push(current);
  return values.sort().map((value) => ({ value, label: formatClock(value, timeFormat) }));
}

export interface LocalParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  /** ISO weekday: 1 = Monday … 7 = Sunday. */
  weekday: number;
}

const WEEKDAYS: Record<string, number> = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 };

/** Calendar fields of `date` as seen on a wall clock in `timezone`. */
export function localParts(date: Date, timezone: string): LocalParts {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    weekday: 'short',
    hourCycle: 'h23',
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '0';
  return {
    year: Number(get('year')),
    month: Number(get('month')),
    day: Number(get('day')),
    hour: Number(get('hour')),
    minute: Number(get('minute')),
    weekday: WEEKDAYS[get('weekday')] ?? 1,
  };
}

const toMinutes = (hhmm: string) => {
  const [h = 0, m = 0] = hhmm.split(':').map(Number);
  return h * 60 + m;
};

export type DayWindowState =
  | { phase: 'before'; minutesUntilStart: number; progress: 0 }
  | { phase: 'during'; minutesLeft: number; progress: number }
  | { phase: 'after'; progress: 1 };

/** Where "now" sits inside the user's working window (profile day_start/day_end). */
export function dayWindow(now: Date, timezone: string, start: string, end: string): DayWindowState {
  const p = localParts(now, timezone);
  const minute = p.hour * 60 + p.minute;
  const from = toMinutes(start);
  const to = toMinutes(end);
  if (minute < from) return { phase: 'before', minutesUntilStart: from - minute, progress: 0 };
  if (minute >= to) return { phase: 'after', progress: 1 };
  return { phase: 'during', minutesLeft: to - minute, progress: (minute - from) / (to - from) };
}

/** Share of the current week that has passed, honouring the user's first weekday. */
export function weekProgress(now: Date, timezone: string, weekStart: number): number {
  const p = localParts(now, timezone);
  const dayIndex = (p.weekday - weekStart + 7) % 7;
  return (dayIndex * 1440 + p.hour * 60 + p.minute) / (7 * 1440);
}

/** Share of the current calendar year that has passed, plus the year itself. */
export function yearProgress(now: Date, timezone: string): { year: number; progress: number } {
  const p = localParts(now, timezone);
  const startOfYear = Date.UTC(p.year, 0, 1);
  const today = Date.UTC(p.year, p.month - 1, p.day);
  const daysInYear = (Date.UTC(p.year + 1, 0, 1) - startOfYear) / 86_400_000;
  const dayOfYear = (today - startOfYear) / 86_400_000;
  return { year: p.year, progress: (dayOfYear + (p.hour * 60 + p.minute) / 1440) / daysInYear };
}
