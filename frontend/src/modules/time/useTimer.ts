import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useInvalidatePlanning } from '@/modules/planning/hooks';
import { growthKeys, timeApi, type TimerInput } from '@/shared/api/growth';
import type { TimeEntry } from '@/shared/api/types';

/** Live seconds of the active timer, derived from server state (BR-056). */
export function liveSeconds(entry: TimeEntry | null | undefined, at: number): number {
  if (!entry) return 0;
  if (entry.status === 'STOPPED') return entry.duration_seconds ?? 0;
  const end = entry.open_pause_at ? Date.parse(entry.open_pause_at) : at;
  return Math.max(
    0,
    Math.floor((end - Date.parse(entry.started_at)) / 1000) - entry.paused_seconds,
  );
}

/** "1 ч 20 мин" / "45 мин" in the user's language. */
export function useMinutesLabel() {
  const { t } = useTranslation('time');
  return (minutes: number) => {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return h ? t('hm', { h, m }) : t('m', { m });
  };
}

export function formatStopwatch(total: number): string {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function useTick(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}

export function useTimer() {
  const invalidate = useInvalidatePlanning();
  const query = useQuery({
    queryKey: growthKeys.timer,
    queryFn: timeApi.timer,
    refetchInterval: 60_000,
  });
  const entry = query.data ?? null;
  const now = useTick(entry?.status === 'RUNNING');
  const onSettled = () => invalidate();

  const start = useMutation({ mutationFn: (input: TimerInput) => timeApi.start(input), onSettled });
  const pause = useMutation({ mutationFn: timeApi.pause, onSettled });
  const resume = useMutation({ mutationFn: timeApi.resume, onSettled });
  const stop = useMutation({ mutationFn: timeApi.stop, onSettled });
  const discard = useMutation({ mutationFn: timeApi.discard, onSettled });

  return {
    entry,
    seconds: liveSeconds(entry, now),
    isLoading: query.isLoading,
    start,
    pause,
    resume,
    stop,
    discard,
    busy:
      start.isPending || pause.isPending || resume.isPending || stop.isPending || discard.isPending,
    error: start.error ?? pause.error ?? resume.error ?? stop.error ?? discard.error,
  };
}
