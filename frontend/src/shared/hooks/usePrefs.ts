import { useEffect, useState } from 'react';

import { useAuthStore } from '@/shared/store/authStore';
import { dateKey, type DisplayPrefs } from '@/shared/utils/datetime';

export interface Prefs extends DisplayPrefs {
  weekStart: number;
  dayStart: string;
  dayEnd: string;
}

/** Display preferences of the signed-in user (time zone, language, 12/24 h, week start). */
export function usePrefs(): Prefs {
  const profile = useAuthStore((s) => s.profile);
  return {
    language: profile?.language ?? 'ru',
    timezone: profile?.timezone ?? 'UTC',
    timeFormat: profile?.time_format ?? '24h',
    weekStart: profile?.week_start ?? 1,
    dayStart: (profile?.day_start_time ?? '07:00').slice(0, 5),
    dayEnd: (profile?.day_end_time ?? '23:00').slice(0, 5),
  };
}

/** Ticking clock for live UI (now-line, greetings). */
export function useNow(intervalMs = 30_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

/** Today's local date key in the user's time zone. */
export function useToday(): string {
  const { timezone } = usePrefs();
  const now = useNow(60_000);
  return dateKey(now, timezone);
}
