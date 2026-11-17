/**
 * Hand-written until `npm run api:types` generates schema.d.ts from the backend OpenAPI
 * schema (SDD §8.4). Keep in sync with backend/apps/accounts/serializers.py.
 */
export const LANGUAGES = ['ru', 'en', 'ky'] as const;
export type Language = (typeof LANGUAGES)[number];

export type TimeFormat = '12h' | '24h';
export type Theme = 'light' | 'dark' | 'system';

export interface PomodoroSettings {
  work: number;
  short: number;
  long: number;
  cycle: number;
}

export interface Profile {
  id: string;
  email: string;
  display_name: string;
  avatar: string | null;
  timezone: string;
  language: Language;
  time_format: TimeFormat;
  date_format: string;
  week_start: number;
  theme: Theme;
  day_start_time: string;
  day_end_time: string;
  pomodoro_settings: PomodoroSettings;
  overload_threshold_minutes: number;
  onboarding_completed_at: string | null;
}

export interface AuthResponse {
  access: string;
  profile: Profile;
}

export interface Paginated<T> {
  count?: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type CategoryScope = 'TASK' | 'EVENT' | 'HABIT' | 'GOAL' | 'JOURNAL' | 'TIME' | 'ANY';

export interface Category {
  id: string;
  scope: CategoryScope;
  name: string;
  system_key: string | null;
  is_name_custom: boolean;
  color: string;
  icon: string | null;
  sort_order: number;
  is_archived: boolean;
}

/* ---------- Tasks (backend/apps/tasks/serializers.py) ---------- */

export const TASK_STATUSES = [
  'BACKLOG',
  'TODO',
  'IN_PROGRESS',
  'POSTPONED',
  'COMPLETED',
  'CANCELLED',
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'] as const;
export type Priority = (typeof PRIORITIES)[number];

export interface Subtask {
  id: string;
  title: string;
  is_done: boolean;
  done_at: string | null;
  sort_order: number;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: Priority;
  category_id: string | null;
  tag_ids: string[];
  due_at: string | null;
  due_has_time: boolean;
  due_date: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  estimated_minutes: number | null;
  completed_at: string | null;
  cancelled_at: string | null;
  postponed_count: number;
  triaged_at: string | null;
  in_inbox: boolean;
  is_overdue: boolean;
  sort_order: number;
  is_archived: boolean;
  subtasks_total: number;
  subtasks_done: number;
  created_at: string;
  updated_at: string;
}

export interface TaskDetail extends Task {
  subtasks: Subtask[];
}

export interface TaskHistoryItem {
  id: string;
  from_status: TaskStatus | null;
  to_status: TaskStatus;
  reason: string;
  old_due_at: string | null;
  new_due_at: string | null;
  actor_type: 'USER' | 'SYSTEM' | 'AI';
  changed_at: string;
}

/* ---------- Schedule (backend/apps/schedule/serializers.py) ---------- */

export const TIME_TYPES = ['FIXED', 'FOCUS', 'PERSONAL', 'REST', 'BUFFER', 'FREE'] as const;
export type TimeType = (typeof TIME_TYPES)[number];
export type EventStatus = 'PLANNED' | 'DONE' | 'MISSED' | 'CANCELLED';
export type Weekday = 'MO' | 'TU' | 'WE' | 'TH' | 'FR' | 'SA' | 'SU';

export interface Recurrence {
  freq: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY';
  interval?: number;
  by_day?: Weekday[];
  by_month_day?: number[];
  count?: number | null;
  until?: string | null;
}

export interface EventBrief {
  id: string | null;
  occurrence_key: string | null;
  title: string;
  start_at: string;
  end_at: string;
  time_type: TimeType;
}

export interface ScheduleWarning {
  code: 'SCHEDULE_OVERLAP';
  severity: 'CONFLICT' | 'WARNING';
  conflicting: EventBrief[];
}

export interface CalendarEvent {
  id: string | null;
  series_id: string | null;
  original_start_at: string | null;
  occurrence_key: string | null;
  title: string;
  description: string;
  location: string;
  start_at: string;
  end_at: string;
  all_day: boolean;
  timezone: string;
  time_type: TimeType;
  status: EventStatus;
  category_id: string | null;
  color: string | null;
  task: { id: string; title: string | null } | null;
  reminder_minutes: number | null;
  recurrence: Recurrence | null;
  warnings?: ScheduleWarning[];
}

export interface FreeTime {
  date: string;
  window_start: string;
  window_end: string;
  busy_minutes: number;
  free_minutes: number;
  reserved_free_minutes: number;
  slots: Array<{ start_at: string; end_at: string; minutes: number }>;
}

export interface DashboardData {
  date: string;
  timezone: string;
  schedule: CalendarEvent[];
  upcoming: CalendarEvent[];
  tasks: { today: Task[]; overdue: Task[]; completed_count: number; open_count: number };
  inbox_count: number;
  free_time: FreeTime;
  stats: {
    planned_minutes: number;
    focus_minutes: number;
    tasks_completed: number;
    tasks_total: number;
  };
  habits: null;
  goals: null;
  active_timer: null;
}
