import { useEffect } from 'react';

import i18n from '@/app/providers/i18n';
import { profileApi } from '@/shared/api/auth';
import { refreshAccessToken } from '@/shared/api/client';
import type { Profile, Theme } from '@/shared/api/types';
import { useAuthStore } from '@/shared/store/authStore';

/**
 * Restores the session after a page reload (NFR-010): the access token was only in memory,
 * so we exchange the HttpOnly refresh cookie for a new one and load the profile.
 */
export function useSessionBootstrap(): void {
  const status = useAuthStore((s) => s.status);

  useEffect(() => {
    if (status !== 'unknown') return;
    let cancelled = false;
    (async () => {
      const access = await refreshAccessToken();
      if (cancelled) return;
      if (!access) {
        useAuthStore.getState().clear();
        return;
      }
      try {
        const profile = await profileApi.get();
        if (!cancelled) useAuthStore.getState().setSession(access, profile);
      } catch {
        if (!cancelled) useAuthStore.getState().clear();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status]);
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', theme);
}

/** Keeps UI language and theme in sync with the signed-in profile. */
export function useProfilePreferences(): void {
  const profile = useAuthStore((s) => s.profile);
  useEffect(() => {
    if (!profile) return;
    syncPreferences(profile);
  }, [profile]);
}

export function syncPreferences(profile: Pick<Profile, 'language' | 'theme'>): void {
  if (i18n.language !== profile.language) void i18n.changeLanguage(profile.language);
  applyTheme(profile.theme);
}
