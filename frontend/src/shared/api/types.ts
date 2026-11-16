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
