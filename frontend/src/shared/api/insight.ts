/** Phase 3 & 4 API: analytics, weekly review, wellness, notifications, AI (SDD §7.2). */
import { api, request } from '@/shared/api/client';
import type { Task } from '@/shared/api/types';

/* ---------- types (mirror backend serializers) ---------- */

export interface Metric {
  key: string;
  value: number | null;
  numerator: number | null;
  denominator: number | null;
  reason?: 'NO_DATA';
}

export interface DaySeries {
  date: string;
  tasks_completed: number;
  habits_done: number;
  focus_minutes: number;
  tracked_minutes: number;
}

export interface WellnessDay {
  date: string;
  mood: number | null;
  energy: number | null;
  stress: number | null;
  sleep_minutes: number | null;
  sleep_quality: number | null;
}

export interface WellnessSummary {
  mood: number | null;
  energy: number | null;
  stress: number | null;
  sleep_minutes: number | null;
  sleep_quality: number | null;
  checkins: number;
  sleep_entries: number;
  series: WellnessDay[];
  signals?: Array<{ code: 'HEAVY_DAYS' | 'SHORT_SLEEP' | 'HIGH_STRESS'; [k: string]: unknown }>;
  threshold_minutes?: number;
}

export interface AnalyticsSummary {
  period: 'day' | 'week' | 'month';
  from: string;
  to: string;
  formula_version: string;
  is_final: boolean;
  tasks: {
    completion_rate: Metric;
    completed: number;
    overdue_open: number;
    postponed: number;
    created: number;
  };
  habits: {
    consistency: Metric;
    habits: Array<{
      id: string;
      name: string;
      color: string | null;
      consistency: number | null;
      success: number;
      eligible: number;
      current_streak: number;
    }>;
  };
  time: {
    focus_hours: Metric;
    tracked_hours: number;
    schedule_accuracy: Metric;
    planned_minutes: number;
    actual_minutes: number;
    unplanned_minutes: number;
    distribution: Array<{
      category_id: string | null;
      name: string | null;
      system_key: string | null;
      color: string | null;
      minutes: number;
      share: number | null;
    }>;
  };
  goals: {
    active: Array<{ id: string; title: string; progress_pct: number; target_date: string | null }>;
    completed_in_period: number;
  };
  wellness: WellnessSummary;
  series: DaySeries[];
  previous?: {
    from: string;
    to: string;
    task_completion_rate: number | null;
    habit_consistency: number | null;
    focus_hours: number | null;
  };
}

export type ReviewDecision = 'CARRY_OVER' | 'RESCHEDULE' | 'BACKLOG' | 'CANCEL' | 'KEEP';

export interface Review {
  id: string;
  week_start: string;
  week_end: string;
  status: 'DRAFT' | 'COMPLETED';
  stats_snapshot: AnalyticsSummary;
  formula_version: string;
  wins: string;
  challenges: string;
  lessons: string;
  next_week_focus: string;
  week_rating: number | null;
  completed_at: string | null;
  decisions: Array<{ task_id: string; decision: ReviewDecision; new_due_at: string | null }>;
}

export type ReviewListItem = Pick<
  Review,
  'id' | 'week_start' | 'week_end' | 'status' | 'week_rating' | 'completed_at'
>;

export interface Checkin {
  id: string;
  recorded_at: string;
  local_date: string;
  mood: number | null;
  energy: number | null;
  stress: number | null;
  note: string;
  source: 'MANUAL' | 'JOURNAL' | 'REVIEW';
}

export interface Sleep {
  id: string;
  sleep_start: string;
  sleep_end: string;
  wake_date: string;
  minutes: number;
  quality: number | null;
  note: string;
}

export interface AppNotification {
  id: string;
  type: string;
  message_key: string;
  params: Record<string, unknown>;
  link: string;
  read_at: string | null;
  created_at: string;
}

export type AIScope =
  'TASKS' | 'SCHEDULE' | 'HABITS' | 'GOALS' | 'JOURNAL' | 'WELLNESS' | 'ANALYTICS';

export interface AIStatus {
  enabled: boolean;
  provider: string;
  model: string;
  scopes: AIScope[];
  all_scopes: AIScope[];
  tokens_this_month: number;
  monthly_limit: number;
}

export interface AIAction {
  id: string;
  action_type:
    | 'CREATE_TASK'
    | 'UPDATE_TASK'
    | 'CREATE_EVENT'
    | 'UPDATE_EVENT'
    | 'RESCHEDULE_EVENT'
    | 'CREATE_SUBTASKS'
    | 'LOG_HABIT'
    | 'CREATE_JOURNAL_DRAFT';
  payload: Record<string, unknown>;
  edited_payload: Record<string, unknown> | null;
  assumptions: string[];
  preview: { conflicts?: Array<{ title: string; severity: string }> };
  status: 'PROPOSED' | 'CONFIRMED' | 'EXECUTED' | 'REJECTED' | 'FAILED' | 'EXPIRED' | 'REVERTED';
  result_object_type: string | null;
  result_object_id: string | null;
  error: { code: string; detail: string } | null;
  expires_at: string;
}

export interface AIMessage {
  id: string;
  role: 'USER' | 'ASSISTANT' | 'TOOL';
  content: string;
  status: 'OK' | 'ERROR' | 'PENDING';
  error_code: string | null;
  created_at: string;
  actions: AIAction[];
}

export interface AIConversation {
  id: string;
  title: string;
  model: string;
  created_at: string;
  updated_at: string;
}

/* ---------- keys ---------- */

export const insightKeys = {
  analytics: (period: string, date: string) => ['analytics', period, date] as const,
  reviews: ['reviews'] as const,
  review: (id: string) => ['reviews', id] as const,
  reviewTasks: (id: string) => ['reviews', id, 'tasks'] as const,
  wellness: ['wellness'] as const,
  wellnessSummary: (from: string, to: string) => ['wellness', 'summary', from, to] as const,
  checkins: (from: string, to: string) => ['wellness', 'checkins', from, to] as const,
  sleeps: (from: string, to: string) => ['wellness', 'sleep', from, to] as const,
  notifications: ['notifications'] as const,
  ai: ['ai'] as const,
  aiStatus: ['ai', 'status'] as const,
  aiConversations: ['ai', 'conversations'] as const,
  aiConversation: (id: string) => ['ai', 'conversation', id] as const,
};

/* ---------- calls ---------- */

export const analyticsApi = {
  get: (period: 'day' | 'week' | 'month', date?: string) =>
    api.get<AnalyticsSummary>(
      `/analytics/${{ day: 'daily', week: 'weekly', month: 'monthly' }[period]}/`,
      { date },
    ),
};

export const reviewsApi = {
  list: () => api.get<{ results: ReviewListItem[] }>('/reviews/').then((r) => r.results),
  start: (week_start?: string) => api.post<Review>('/reviews/', week_start ? { week_start } : {}),
  get: (id: string) => api.get<Review>(`/reviews/${id}/`),
  update: (
    id: string,
    patch: Partial<
      Pick<Review, 'wins' | 'challenges' | 'lessons' | 'next_week_focus' | 'week_rating'>
    >,
  ) => api.patch<Review>(`/reviews/${id}/`, patch),
  refresh: (id: string) => api.post<Review>(`/reviews/${id}/refresh-stats/`),
  tasks: (id: string) =>
    api.get<{ results: Task[] }>(`/reviews/${id}/unfinished-tasks/`).then((r) => r.results),
  decide: (
    id: string,
    decisions: Array<{ task_id: string; decision: ReviewDecision; new_due_at?: string | null }>,
  ) => request<Review>(`/reviews/${id}/task-decisions/`, { method: 'PUT', body: { decisions } }),
  complete: (id: string) => api.post<Review>(`/reviews/${id}/complete/`),
};

export const wellnessApi = {
  summary: (from: string, to: string) =>
    api.get<WellnessSummary>('/wellness/summary/', { from, to }),
  checkins: (from: string, to: string) =>
    api.get<{ results: Checkin[] }>('/wellness/checkins/', { from, to }).then((r) => r.results),
  addCheckin: (input: {
    mood?: number | null;
    energy?: number | null;
    stress?: number | null;
    note?: string;
  }) => api.post<Checkin>('/wellness/checkins/', input),
  removeCheckin: (id: string) => api.delete(`/wellness/checkins/${id}/`),
  sleeps: (from: string, to: string) =>
    api.get<{ results: Sleep[] }>('/wellness/sleep/', { from, to }).then((r) => r.results),
  addSleep: (input: {
    sleep_start: string;
    sleep_end: string;
    quality?: number | null;
    note?: string;
  }) => api.post<Sleep>('/wellness/sleep/', input),
  removeSleep: (id: string) => api.delete(`/wellness/sleep/${id}/`),
};

export const notificationsApi = {
  list: () =>
    api.get<{ results: AppNotification[]; count: number }>('/notifications/', { page_size: 30 }),
  unread: () => api.get<{ count: number }>('/notifications/unread-count/'),
  read: (id: string) =>
    api.post<AppNotification>(`/notifications/${id}/read/`, undefined, { idempotencyKey: false }),
  readAll: () =>
    api.post<{ updated: number }>('/notifications/read-all/', undefined, { idempotencyKey: false }),
};

export const aiApi = {
  status: () => api.get<AIStatus>('/ai/status/'),
  setScopes: (scopes: AIScope[]) =>
    request<{ scopes: AIScope[] }>('/ai/consents/', { method: 'PUT', body: { scopes } }),
  conversations: () =>
    api.get<{ results: AIConversation[] }>('/ai/conversations/').then((r) => r.results),
  newConversation: () => api.post<AIConversation>('/ai/conversations/', {}),
  conversation: (id: string) =>
    api.get<AIConversation & { messages: AIMessage[] }>(`/ai/conversations/${id}/`),
  removeConversation: (id: string) => api.delete(`/ai/conversations/${id}/`),
  send: (id: string, content: string) =>
    api.post<{ user_message: AIMessage; assistant_message: AIMessage }>(
      `/ai/conversations/${id}/messages/`,
      { content },
    ),
  message: (id: string) => api.get<AIMessage>(`/ai/messages/${id}/`),
  context: (id: string) =>
    api.get<{ results: Array<{ scope: AIScope; object_type: string; count: number }> }>(
      `/ai/messages/${id}/context/`,
    ),
  confirm: (id: string, edited_payload?: Record<string, unknown>) =>
    api.post<AIAction>(`/ai/actions/${id}/confirm/`, edited_payload ? { edited_payload } : {}),
  reject: (id: string) => api.post<AIAction>(`/ai/actions/${id}/reject/`),
  revert: (id: string) => api.post<AIAction>(`/ai/actions/${id}/revert/`),
};
