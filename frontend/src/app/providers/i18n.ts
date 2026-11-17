import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enAuth from '@/locales/en/auth.json';
import enCommon from '@/locales/en/common.json';
import enDashboard from '@/locales/en/dashboard.json';
import enSchedule from '@/locales/en/schedule.json';
import enSettings from '@/locales/en/settings.json';
import enTasks from '@/locales/en/tasks.json';
import kyAuth from '@/locales/ky/auth.json';
import kyCommon from '@/locales/ky/common.json';
import kyDashboard from '@/locales/ky/dashboard.json';
import kySchedule from '@/locales/ky/schedule.json';
import kySettings from '@/locales/ky/settings.json';
import kyTasks from '@/locales/ky/tasks.json';
import ruAuth from '@/locales/ru/auth.json';
import ruCommon from '@/locales/ru/common.json';
import ruDashboard from '@/locales/ru/dashboard.json';
import ruSchedule from '@/locales/ru/schedule.json';
import ruSettings from '@/locales/ru/settings.json';
import ruTasks from '@/locales/ru/tasks.json';
import { LANGUAGES, type Language } from '@/shared/api/types';

export const resources = {
  ru: {
    common: ruCommon,
    auth: ruAuth,
    settings: ruSettings,
    dashboard: ruDashboard,
    tasks: ruTasks,
    schedule: ruSchedule,
  },
  en: {
    common: enCommon,
    auth: enAuth,
    settings: enSettings,
    dashboard: enDashboard,
    tasks: enTasks,
    schedule: enSchedule,
  },
  ky: {
    common: kyCommon,
    auth: kyAuth,
    settings: kySettings,
    dashboard: kyDashboard,
    tasks: kyTasks,
    schedule: kySchedule,
  },
} as const;

/** Browser language → supported language (SDD ADR-014: Kyrgyz is `ky`). */
export function detectLanguage(
  candidates: readonly string[] = navigator.languages ?? [],
): Language {
  for (const candidate of candidates) {
    const base = candidate.toLowerCase().split('-')[0];
    if ((LANGUAGES as readonly string[]).includes(base ?? '')) return base as Language;
  }
  return 'ru';
}

void i18n.use(initReactI18next).init({
  resources,
  lng: detectLanguage(),
  fallbackLng: { ky: ['ru'], default: ['ru'] },
  supportedLngs: LANGUAGES,
  ns: ['common', 'auth', 'settings', 'dashboard', 'tasks', 'schedule'],
  defaultNS: 'common',
  interpolation: { escapeValue: false },
  returnNull: false,
});

i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng;
});
document.documentElement.lang = i18n.language;

export default i18n;
