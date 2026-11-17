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
  actual_minutes: number;
  goal_ids: string[];
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
  habits: { planned: number; done: number; items: TodayHabit[] };
  goals: Goal[];
  active_timer: TimeEntry | null;
  tracked_minutes: number;
}

/* ---------- Habits (backend/apps/habits/serializers.py) ---------- */

export type TrackingType = 'BOOLEAN' | 'DURATION' | 'QUANTITY' | 'SCALE';
export type FrequencyType =
  'DAILY' | 'WEEKDAYS' | 'TIMES_PER_WEEK' | 'TIMES_PER_MONTH' | 'EVERY_N_DAYS';
export type HabitLogStatus = 'DONE' | 'PARTIAL' | 'SKIPPED' | 'REST' | 'MISSED';

export interface HabitSchedule {
  valid_from: string;
  valid_to: string | null;
  frequency_type: FrequencyType;
  weekdays_mask: number | null;
  times_per_period: number | null;
  interval_days: number | null;
  target_value: string | null;
  target_comparison: 'GTE' | 'LTE';
}

export interface Habit {
  id: string;
  name: string;
  description: string;
  category_id: string | null;
  tracking_type: TrackingType;
  unit: string;
  scale_min: number | null;
  scale_max: number | null;
  start_date: string;
  end_date: string | null;
  color: string | null;
  is_active: boolean;
  is_archived: boolean;
  schedule: HabitSchedule | null;
  created_at: string;
}

export interface HabitPause {
  id: string;
  start_date: string;
  end_date: string | null;
  reason: string;
}

export interface HabitDetail extends Habit {
  schedules: HabitSchedule[];
  pauses: HabitPause[];
}

export interface TodayHabit {
  habit: Habit;
  planned: boolean;
  paused: boolean;
  status: HabitLogStatus | null;
  value: string | null;
  target_value: string | null;
  log_ids: string[];
  period_done: number | null;
  period_needed: number | null;
  current_streak: number;
}

export interface HabitLog {
  id: string;
  habit_id: string;
  log_date: string;
  status: HabitLogStatus;
  value: string | null;
  note: string;
  unit_snapshot: string;
  target_value_snapshot: string | null;
  logged_at: string;
  is_voided: boolean;
}

export interface HabitStats {
  consistency: number | null;
  success: number;
  eligible: number;
  current_streak: number;
  best_streak: number;
  total_value: string;
  done_days: number;
}

export interface HabitDay {
  date: string;
  planned: boolean;
  paused: boolean;
  status: HabitLogStatus | null;
  value: string | null;
}

/* ---------- Goals (backend/apps/goals/views.py) ---------- */

export type GoalLevel = 'VISION' | 'YEARLY' | 'QUARTERLY' | 'MONTHLY' | 'CUSTOM';
export type GoalStatus = 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'ABANDONED';
export type ProgressType = 'METRIC' | 'MILESTONES' | 'TASKS' | 'MANUAL';
export type GoalAction = 'PAUSE' | 'RESUME' | 'COMPLETE' | 'ABANDON' | 'REOPEN';

export interface Milestone {
  id: string;
  title: string;
  due_date: string | null;
  status: 'PENDING' | 'COMPLETED' | 'SKIPPED';
  weight: string;
  completed_at: string | null;
  sort_order: number;
}

export interface Goal {
  id: string;
  parent_id: string | null;
  level: GoalLevel;
  title: string;
  description: string;
  category_id: string | null;
  status: GoalStatus;
  start_date: string;
  target_date: string | null;
  progress_type: ProgressType;
  metric_unit: string;
  start_value: string | null;
  target_value: string | null;
  current_value: string | null;
  progress_pct: string;
  target_reached: boolean;
  completed_at: string | null;
  milestones_total: number;
  milestones_done: number;
  tasks_total: number;
  tasks_done: number;
  created_at: string;
}

export interface GoalNode extends Goal {
  children: GoalNode[];
}

export interface GoalDetail extends Goal {
  milestones: Milestone[];
}

export interface GoalHistory {
  progress: Array<{
    id: string;
    recorded_at: string;
    value: string | null;
    progress_pct: string;
    source: string;
    note: string;
  }>;
  status: Array<{
    id: string;
    from_status: GoalStatus | null;
    to_status: GoalStatus;
    reason: string;
    changed_at: string;
  }>;
}

/* ---------- Journal ---------- */

export type JournalType = 'DAILY' | 'FREE' | 'NOTE';
export const DAILY_SECTIONS = [
  'happened',
  'accomplished',
  'problems',
  'learned',
  'grateful',
  'improve',
  'tomorrow',
] as const;
export type DailySection = (typeof DAILY_SECTIONS)[number];

export interface JournalEntry {
  id: string;
  entry_date: string;
  entry_type: JournalType;
  title: string;
  template_key: string | null;
  sections: Partial<Record<DailySection, string>>;
  body: string;
  category_id: string | null;
  tag_ids: string[];
  is_sensitive: boolean;
  ai_allowed: boolean;
  mood: number | null;
  energy: number | null;
  created_at: string;
  updated_at: string;
}

/* ---------- Time tracking ---------- */

export interface TimeEntry {
  id: string;
  task: { id: string; title: string } | null;
  task_id: string | null;
  event_id: string | null;
  category_id: string | null;
  description: string;
  status: 'RUNNING' | 'PAUSED' | 'STOPPED';
  source: string;
  started_at: string;
  ended_at: string | null;
  paused_seconds: number;
  duration_seconds: number | null;
  elapsed_seconds: number;
  open_pause_at: string | null;
  is_focus: boolean;
  warnings?: Array<{ code: string; ids: string[] }>;
}

export interface PlanVsActual {
  planned_minutes: number;
  matched_minutes: number;
  actual_minutes: number;
  unplanned_minutes: number;
  focus_minutes: number;
  accuracy: number | null;
  items: Array<{
    title: string;
    start_at: string;
    time_type: TimeType;
    planned_minutes: number;
    actual_minutes: number;
  }>;
}
