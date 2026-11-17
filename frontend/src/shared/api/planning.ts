/** API calls and query keys for Phase 1: tasks, schedule, categories, dashboard (SDD §7.2, §8.3). */
import { api, request } from '@/shared/api/client';
import type {
  CalendarEvent,
  Category,
  DashboardData,
  EventBrief,
  FreeTime,
  Paginated,
  Priority,
  Recurrence,
  Subtask,
  Task,
  TaskDetail,
  TaskHistoryItem,
  TaskStatus,
  TimeType,
} from '@/shared/api/types';

/* ---------- query keys ---------- */

export interface TaskQuery {
  status?: string;
  priority?: string;
  q?: string;
  inbox?: boolean;
  overdue?: boolean;
  archived?: boolean;
  category?: string;
  due_from?: string;
  due_to?: string;
  ordering?: string;
  page_size?: number;
}

export const keys = {
  tasks: ['tasks'] as const,
  taskList: (q: TaskQuery) => ['tasks', 'list', q] as const,
  task: (id: string) => ['tasks', 'detail', id] as const,
  taskHistory: (id: string) => ['tasks', 'history', id] as const,
  events: ['events'] as const,
  eventRange: (from: string, to: string) => ['events', 'range', from, to] as const,
  freeSlots: (date: string) => ['events', 'free', date] as const,
  dashboard: ['dashboard'] as const,
  dashboardDay: (date?: string) => ['dashboard', date ?? 'today'] as const,
  categories: ['categories'] as const,
};

/* ---------- tasks ---------- */

export interface TaskInput {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: Priority;
  category_id?: string | null;
  tag_ids?: string[];
  due_at?: string | null;
  due_date?: string | null;
  estimated_minutes?: number | null;
  subtasks?: string[];
}

export const tasksApi = {
  list: (q: TaskQuery) => api.get<Paginated<Task>>('/tasks/', { page_size: 100, ...q }),
  get: (id: string) => api.get<TaskDetail>(`/tasks/${id}/`),
  create: (input: TaskInput) => api.post<TaskDetail>('/tasks/', input),
  quick: (title: string) => api.post<TaskDetail>('/tasks/quick/', { title }),
  update: (id: string, patch: TaskInput) => api.patch<TaskDetail>(`/tasks/${id}/`, patch),
  remove: (id: string) => api.delete(`/tasks/${id}/`),
  setStatus: (id: string, status: TaskStatus, reason = '') =>
    api.post<TaskDetail>(`/tasks/${id}/status/`, { status, reason }),
  complete: (id: string) => api.post<TaskDetail>(`/tasks/${id}/complete/`),
  postpone: (id: string, input: { new_due_date?: string | null; reason?: string }) =>
    api.post<TaskDetail>(`/tasks/${id}/postpone/`, input),
  triage: (id: string) => api.post<TaskDetail>(`/tasks/${id}/triage/`),
  archive: (id: string) => api.post<TaskDetail>(`/tasks/${id}/archive/`),
  restore: (id: string) => api.post<TaskDetail>(`/tasks/${id}/restore/`),
  history: (id: string) =>
    api.get<{ results: TaskHistoryItem[] }>(`/tasks/${id}/history/`).then((r) => r.results),
  schedule: (
    id: string,
    input: { start_at: string; end_at: string; time_type?: TimeType },
    force = false,
  ) =>
    request<CalendarEvent>(`/tasks/${id}/schedule/`, {
      method: 'POST',
      body: input,
      query: force ? { force: true } : undefined,
    }),
  addSubtask: (taskId: string, title: string) =>
    api.post<Subtask>(`/tasks/${taskId}/subtasks/`, { title }),
  updateSubtask: (id: string, patch: Partial<Pick<Subtask, 'title' | 'is_done'>>) =>
    api.patch<Subtask>(`/subtasks/${id}/`, patch),
  removeSubtask: (id: string) => api.delete(`/subtasks/${id}/`),
};

/* ---------- schedule ---------- */

export interface EventInput {
  title?: string;
  description?: string;
  location?: string;
  start_at?: string;
  end_at?: string;
  time_type?: TimeType;
  category_id?: string | null;
  task_id?: string | null;
  reminder_minutes?: number | null;
  recurrence?: Recurrence | null;
  status?: CalendarEvent['status'];
  scope?: 'this' | 'following';
}

const forceQuery = (force: boolean) => (force ? { force: true } : undefined);

/** Epoch seconds of an occurrence, the path segment of /occurrences/{epoch}/. */
export const occurrenceEpoch = (event: CalendarEvent) =>
  event.occurrence_key ? event.occurrence_key.split(':')[1] : '';

export const scheduleApi = {
  range: (from: string, to: string) =>
    api.get<{ results: CalendarEvent[] }>('/events/', { from, to }).then((r) => r.results),
  create: (input: EventInput, force = false) =>
    request<CalendarEvent>('/events/', { method: 'POST', body: input, query: forceQuery(force) }),
  update: (id: string, input: EventInput, force = false) =>
    request<CalendarEvent>(`/events/${id}/`, {
      method: 'PATCH',
      body: input,
      query: forceQuery(force),
    }),
  remove: (id: string) => api.delete(`/events/${id}/`),
  setStatus: (id: string, status: CalendarEvent['status']) =>
    api.post<CalendarEvent>(`/events/${id}/status/`, { status }),
  updateSeries: (seriesId: string, input: EventInput, force = false) =>
    request<CalendarEvent>(`/event-series/${seriesId}/`, {
      method: 'PATCH',
      body: input,
      query: forceQuery(force),
    }),
  removeSeries: (seriesId: string) => api.delete(`/event-series/${seriesId}/`),
  updateOccurrence: (event: CalendarEvent, input: EventInput, force = false) =>
    request<CalendarEvent>(
      `/event-series/${event.series_id}/occurrences/${occurrenceEpoch(event)}/`,
      { method: 'PATCH', body: input, query: forceQuery(force) },
    ),
  cancelOccurrence: (event: CalendarEvent) =>
    api.delete(`/event-series/${event.series_id}/occurrences/${occurrenceEpoch(event)}/`),
  freeSlots: (date: string) => api.get<FreeTime>('/schedule/free-slots/', { date }),
  getSeries: (seriesId: string) => api.get<CalendarEvent>(`/event-series/${seriesId}/`),
  checkConflicts: (input: {
    start_at: string;
    end_at: string;
    time_type: TimeType;
    exclude_id?: string | null;
  }) =>
    api.post<{
      has_conflict: boolean;
      results: Array<{ severity: 'CONFLICT' | 'WARNING'; event: EventBrief }>;
    }>('/events/check-conflicts/', input, { idempotencyKey: false }),
};

/* ---------- categories & dashboard ---------- */

export const categoriesApi = {
  list: () =>
    api.get<Paginated<Category>>('/categories/', { page_size: 100 }).then((r) => r.results),
  create: (input: Pick<Category, 'name' | 'color'>) =>
    api.post<Category>('/categories/', { ...input, scope: 'ANY' }),
  update: (id: string, patch: Partial<Pick<Category, 'name' | 'color'>>) =>
    api.patch<Category>(`/categories/${id}/`, patch),
  archive: (id: string) => api.delete(`/categories/${id}/`),
};

export const dashboardApi = {
  get: (date?: string) => api.get<DashboardData>('/dashboard/', { date }),
};
