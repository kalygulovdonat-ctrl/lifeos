import '@testing-library/jest-dom/vitest';
import '@/app/providers/i18n';

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach } from 'vitest';

import i18n from '@/app/providers/i18n';
import { useAuthStore } from '@/shared/store/authStore';

afterEach(async () => {
  cleanup();
  useAuthStore.setState({ status: 'unknown', accessToken: null, profile: null, language: 'ru' });
  await i18n.changeLanguage('ru');
  document.cookie.split('; ').forEach((c) => {
    const name = c.split('=')[0];
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  });
});

// jsdom reports en-US; tests assert Russian (the default product language) unless they switch.
beforeEach(async () => {
  await i18n.changeLanguage('ru');
});
