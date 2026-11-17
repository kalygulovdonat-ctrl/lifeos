/**
 * i18n (SDD §8.5). Russian — the default and the fallback language — ships in the main
 * bundle; English and Kyrgyz are separate chunks loaded only when chosen (Phase 4 performance).
 */
import i18n, { type BackendModule, type ResourceKey } from 'i18next';
import { initReactI18next } from 'react-i18next';

import { LANGUAGES, type Language } from '@/shared/api/types';

export const NAMESPACES = [
  'common',
  'auth',
  'settings',
  'dashboard',
  'tasks',
  'schedule',
  'habits',
  'goals',
  'journal',
  'time',
  'analytics',
  'reviews',
  'wellness',
  'assistant',
  'notifications',
] as const;

const eager = import.meta.glob<{ default: ResourceKey }>('../../locales/ru/*.json', {
  eager: true,
});
const lazy = import.meta.glob<{ default: ResourceKey }>([
  '../../locales/en/*.json',
  '../../locales/ky/*.json',
]);

const nsOf = (path: string) => path.slice(path.lastIndexOf('/') + 1, -'.json'.length);

const ru: Record<string, ResourceKey> = Object.fromEntries(
  Object.entries(eager).map(([path, mod]) => [nsOf(path), mod.default]),
);

/** Loads one namespace of a non-default language on demand. */
const chunkBackend: BackendModule = {
  type: 'backend',
  init() {},
  read(language, namespace, callback) {
    const loader = lazy[`../../locales/${language}/${namespace}.json`];
    if (!loader) {
      callback(null, {});
      return;
    }
    loader()
      .then((mod) => callback(null, mod.default))
      .catch((error: Error) => callback(error, null));
  },
};

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

void i18n
  .use(chunkBackend)
  .use(initReactI18next)
  .init({
    resources: { ru },
    partialBundledLanguages: true,
    lng: detectLanguage(),
    fallbackLng: { ky: ['ru'], default: ['ru'] },
    supportedLngs: LANGUAGES,
    ns: NAMESPACES,
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    returnNull: false,
  });

i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng;
});
document.documentElement.lang = i18n.language;

export default i18n;
