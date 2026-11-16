import { create } from 'zustand';

import type { Language, Profile } from '@/shared/api/types';

export type SessionStatus = 'unknown' | 'authenticated' | 'anonymous';

interface AuthState {
  status: SessionStatus;
  accessToken: string | null;
  profile: Profile | null;
  /** Language used for Accept-Language; follows the profile once signed in. */
  language: Language;
  setSession: (access: string, profile: Profile) => void;
  setAccessToken: (access: string) => void;
  setProfile: (profile: Profile) => void;
  setLanguage: (language: Language) => void;
  clear: () => void;
}

/** Kept in memory only: a page reload re-establishes the session via the refresh cookie. */
export const useAuthStore = create<AuthState>((set) => ({
  status: 'unknown',
  accessToken: null,
  profile: null,
  language: 'ru',
  setSession: (accessToken, profile) =>
    set({ accessToken, profile, status: 'authenticated', language: profile.language }),
  setAccessToken: (accessToken) => set({ accessToken }),
  setProfile: (profile) => set({ profile, language: profile.language }),
  setLanguage: (language) => set({ language }),
  clear: () => set({ accessToken: null, profile: null, status: 'anonymous' }),
}));
