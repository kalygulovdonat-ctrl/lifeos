/** API calls and query keys for Phase 2: habits, goals, journal, time tracking (SDD §7.2). */
import { api, request } from '@/shared/api/client';
import type {
  FrequencyType,
  Goal,
  GoalAction,
  GoalDetail,
  GoalHistory,
  GoalLevel,
  GoalNode,
  Habit,
  HabitDay,
  HabitDetail,
  HabitLog,
  HabitLogStatus,
  HabitPause,
  HabitStats,
  JournalEntry,
  JournalType,
  Milestone,
  Paginated,
  PlanVsActual,
  ProgressType,
  Task,
  TimeEntry,
  TodayHabit,
  TrackingType,
} from '@/shared/api/types';

export const growthKeys = {
  habits: ['habits'] as const,
  habitList: (archived: boolean) => ['habits', 'list', archived] as const,
  habitToday: (date?: string) => ['habits', 'today', date ?? 'today'] as const,
  habit: (id: string) => ['habits', 'detail', id] as const,
  habitStats: (id: string, period: string) => ['habits', 'stats', id, period] as const,
  habitHistory: (id: string, from: string, to: string) =>
    ['habits', 'history', id, from, to] as const,
  goals: ['goals'] as const,
  goalTree: (archived: boolean) => ['goals', 'tree', archived] as const,
  goal: (id: string) => ['goals', 'detail', id] as const,
  goalTasks: (id: string) => ['goals', 'tasks', id] as const,
  goalHistory: (id: string) => ['goals', 'history', id] as const,
  journal: ['journal'] as const,
  journalList: (q: Record<string, string | undefined>) => ['journal', 'list', q] as const,
  journalEntry: (id: string) => ['journal', 'entry', id] as const,
  journalDay: (date: string) => ['journal', 'day', date] as const,
  time: ['time'] as const,
  timer: ['time', 'timer'] as const,
  timeEntries: (from: string, to: string) => ['time', 'entries', from, to] as const,
  planVsActual: (from: string, to: string) => ['time', 'pva', from, to] as const,
};

/* ---------- habits ---------- */

export interface HabitInput {
  name?: string;
  description?: string;
  category_id?: string | null;
  tracking_type?: TrackingType;
  unit?: string;
  scale_min?: number | null;
  scale_max?: number | null;
  start_date?: string;
  end_date?: string | null;
  color?: string | null;
  schedule?: {
    frequency_type: FrequencyType;
    weekdays_mask?: number | null;
    times_per_period?: number | null;
    interval_days?: number | null;
    target_value?: string | null;
    target_comparison?: 'GTE' | 'LTE';
  };
}

export const habitsApi = {
  list: (archived = false) =>
    api.get<{ results: Habit[] }>('/habits/', { archived }).then((r) => r.results),
  today: (date?: string) =>
    api.get<{ date: string; results: TodayHabit[] }>('/habits/today/', { date }),
  get: (id: string) => api.get<HabitDetail>(`/habits/${id}/`),
  create: (input: HabitInput) => api.post<HabitDetail>('/habits/', input),
  update: (id: string, input: HabitInput) => api.patch<HabitDetail>(`/habits/${id}/`, input),
  archive: (id: string) => api.post<HabitDetail>(`/habits/${id}/archive/`),
  restore: (id: string) => api.post<HabitDetail>(`/habits/${id}/restore/`),
  log: (
    id: string,
    input: { log_date?: string; status?: HabitLogStatus; value?: string | null; note?: string },
  ) => api.post<HabitLog>(`/habits/${id}/logs/`, input),
  voidLog: (logId: string) => api.delete(`/habit-logs/${logId}/`),
  stats: (id: string, period: 'week' | 'month' | 'year') =>
    api.get<HabitStats>(`/habits/${id}/stats/`, { period }),
  history: (id: string, from: string, to: string) =>
    api.get<{ days: HabitDay[]; logs: HabitLog[] }>(`/habits/${id}/history/`, { from, to }),
  pause: (id: string, input: { start_date: string; end_date?: string | null; reason?: string }) =>
    api.post<HabitPause>(`/habits/${id}/pauses/`, input),
  removePause: (pauseId: string) => api.delete(`/habit-pauses/${pauseId}/`),
};

/* ---------- goals ---------- */

export interface GoalInput {
  parent_id?: string | null;
  level?: GoalLevel;
  title?: string;
  description?: string;
  category_id?: string | null;
  start_date?: string;
  target_date?: string | null;
  progress_type?: ProgressType;
  metric_unit?: string;
  start_value?: string | null;
  target_value?: string | null;
}

export const goalsApi = {
  tree: (archived = false) =>
    api.get<{ results: GoalNode[] }>('/goals/', { tree: true, archived }).then((r) => r.results),
  list: (status?: string) =>
    api.get<{ results: Goal[] }>('/goals/', { status }).then((r) => r.results),
  get: (id: string) => api.get<GoalDetail>(`/goals/${id}/`),
  create: (input: GoalInput) => api.post<GoalDetail>('/goals/', input),
  update: (id: string, input: GoalInput) => api.patch<GoalDetail>(`/goals/${id}/`, input),
  remove: (id: string) => api.delete(`/goals/${id}/`),
  status: (id: string, action: GoalAction, reason = '') =>
    api.post<GoalDetail>(`/goals/${id}/status/`, { action, reason }),
  progress: (id: string, value: string, note = '') =>
    api.post<GoalDetail>(`/goals/${id}/progress/`, { value, note }),
  history: (id: string) => api.get<GoalHistory>(`/goals/${id}/progress-history/`),
  tasks: (id: string) => api.get<{ results: Task[] }>(`/goals/${id}/tasks/`).then((r) => r.results),
  linkTask: (id: string, taskId: string) => api.post<GoalDetail>(`/goals/${id}/tasks/${taskId}/`),
  unlinkTask: (id: string, taskId: string) =>
    request<GoalDetail>(`/goals/${id}/tasks/${taskId}/`, { method: 'DELETE' }),
  addMilestone: (id: string, input: { title: string; due_date?: string | null }) =>
    api.post<Milestone>(`/goals/${id}/milestones/`, input),
  updateMilestone: (
    mid: string,
    patch: Partial<Pick<Milestone, 'title' | 'status' | 'due_date'>>,
  ) => api.patch<Milestone>(`/milestones/${mid}/`, patch),
  removeMilestone: (mid: string) => api.delete(`/milestones/${mid}/`),
};

/* ---------- journal ---------- */

export interface JournalInput {
  entry_date?: string;
  entry_type?: JournalType;
  title?: string;
  sections?: Record<string, string>;
  body?: string;
  category_id?: string | null;
}

export const journalApi = {
  list: (q: { q?: string; type?: string; from?: string; to?: string; page?: string }) =>
    api.get<Paginated<JournalEntry>>('/journal/', { page_size: 30, ...q }),
  get: (id: string) => api.get<JournalEntry>(`/journal/${id}/`),
  byDate: (date: string) => api.get<JournalEntry>(`/journal/by-date/${date}/`),
  create: (input: JournalInput) => api.post<JournalEntry>('/journal/', input),
  update: (id: string, input: JournalInput) => api.patch<JournalEntry>(`/journal/${id}/`, input),
  remove: (id: string) => api.delete(`/journal/${id}/`),
};

/* ---------- time tracking ---------- */

export interface TimerInput {
  task_id?: string | null;
  event_id?: string | null;
  category_id?: string | null;
  description?: string;
  is_focus?: boolean;
}

export const timeApi = {
  timer: () => api.get<TimeEntry | null>('/timer/'),
  start: (input: TimerInput) => api.post<TimeEntry>('/timer/start/', input),
  pause: () => api.post<TimeEntry>('/timer/pause/'),
  resume: () => api.post<TimeEntry>('/timer/resume/'),
  stop: () => api.post<TimeEntry>('/timer/stop/'),
  discard: () => api.post<void>('/timer/discard/'),
  entries: (from: string, to: string) =>
    api.get<Paginated<TimeEntry> & { total_seconds: number }>('/time-entries/', {
      from,
      to,
      page_size: 100,
    }),
  createManual: (input: TimerInput & { started_at: string; ended_at: string }) =>
    api.post<TimeEntry>('/time-entries/', input),
  update: (
    id: string,
    input: TimerInput & { started_at?: string; ended_at?: string; reason?: string },
  ) => api.patch<TimeEntry>(`/time-entries/${id}/`, input),
  remove: (id: string) => api.delete(`/time-entries/${id}/`),
  planVsActual: (from: string, to: string) =>
    api.get<PlanVsActual>('/time-entries/plan-vs-actual/', { from, to }),
  forTask: (taskId: string) =>
    api.get<{ results: TimeEntry[] }>(`/tasks/${taskId}/time-entries/`).then((r) => r.results),
};
