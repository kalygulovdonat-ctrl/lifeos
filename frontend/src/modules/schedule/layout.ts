/** Pure calendar geometry: where each event sits in a day column (tested in layout.test.ts). */
import type { CalendarEvent } from '@/shared/api/types';
import { addDays, zonedIso } from '@/shared/utils/datetime';

export interface Placed {
  event: CalendarEvent;
  /** Minutes from local midnight, clipped to the day. */
  top: number;
  bottom: number;
  column: number;
  columns: number;
  continuesBefore: boolean;
  continuesAfter: boolean;
}

export const eventKey = (e: CalendarEvent) =>
  e.id ?? e.occurrence_key ?? `${e.title}-${e.start_at}`;

/** Events of one local day, placed side by side when they overlap. */
export function layoutDay(events: CalendarEvent[], day: string, timezone: string): Placed[] {
  const dayStart = Date.parse(zonedIso(day, '00:00', timezone));
  const dayEnd = Date.parse(zonedIso(addDays(day, 1), '00:00', timezone));
  const length = (dayEnd - dayStart) / 60_000;

  const items = events
    .map((event) => {
      const s = Date.parse(event.start_at);
      const e = Date.parse(event.end_at);
      if (e <= dayStart || s >= dayEnd) return null;
      const top = Math.max(0, (s - dayStart) / 60_000);
      const bottom = Math.min(length, (e - dayStart) / 60_000);
      return {
        event,
        top,
        bottom: Math.max(bottom, top + 15),
        column: 0,
        columns: 1,
        continuesBefore: s < dayStart,
        continuesAfter: e > dayEnd,
      } satisfies Placed;
    })
    .filter((x): x is Placed => x !== null)
    .sort((a, b) => a.top - b.top || b.bottom - a.bottom);

  // Greedy columns inside clusters of transitively overlapping events.
  let cluster: Placed[] = [];
  let clusterEnd = -1;
  const flush = () => {
    const width = Math.max(1, ...cluster.map((p) => p.column + 1));
    for (const p of cluster) p.columns = width;
    cluster = [];
  };
  for (const item of items) {
    if (item.top >= clusterEnd && cluster.length) flush();
    const taken = new Set(cluster.filter((p) => p.bottom > item.top).map((p) => p.column));
    let column = 0;
    while (taken.has(column)) column++;
    item.column = column;
    cluster.push(item);
    clusterEnd = Math.max(clusterEnd, item.bottom);
  }
  if (cluster.length) flush();
  return items;
}

/** Events touching a local day (month and agenda views). */
export function eventsOnDay(
  events: CalendarEvent[],
  day: string,
  timezone: string,
): CalendarEvent[] {
  const dayStart = Date.parse(zonedIso(day, '00:00', timezone));
  const dayEnd = Date.parse(zonedIso(addDays(day, 1), '00:00', timezone));
  return events.filter((e) => Date.parse(e.end_at) > dayStart && Date.parse(e.start_at) < dayEnd);
}
