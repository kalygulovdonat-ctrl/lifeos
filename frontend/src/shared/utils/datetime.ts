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
