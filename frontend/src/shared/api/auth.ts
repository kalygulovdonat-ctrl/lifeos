import { api, request } from '@/shared/api/client';
import type { AuthResponse, Language, Profile } from '@/shared/api/types';

export interface RegisterInput {
  email: string;
  password: string;
  display_name: string;
  timezone: string;
  language: Language;
}

export interface LoginInput {
  email: string;
  password: string;
}

export const authApi = {
  register: (input: RegisterInput) =>
    request<AuthResponse>('/auth/register/', {
      method: 'POST',
      body: input,
      skipAuthRefresh: true,
    }),
  login: (input: LoginInput) =>
    request<AuthResponse>('/auth/login/', { method: 'POST', body: input, skipAuthRefresh: true }),
  logout: () =>
    request<void>('/auth/logout/', {
      method: 'POST',
      csrf: true,
      skipAuthRefresh: true,
      idempotencyKey: false,
    }),
  changePassword: (old_password: string, new_password: string) =>
    api.post<{ access: string }>('/auth/password/change/', { old_password, new_password }),
};

export const profileApi = {
  get: () => api.get<Profile>('/profile/'),
  update: (patch: Partial<Profile>) => api.patch<Profile>('/profile/', patch),
  completeOnboarding: () => api.post<Profile>('/profile/onboarding/complete/'),
};
