import { useTranslation } from 'react-i18next';
import { Link, Navigate, Outlet } from 'react-router';

import { LANGUAGES, type Language } from '@/shared/api/types';
import { FullPageSpinner } from '@/shared/components/ui';
import { useAuthStore } from '@/shared/store/authStore';

import styles from './layouts.module.css';

const LANGUAGE_NAMES: Record<Language, string> = { ru: 'Русский', en: 'English', ky: 'Кыргызча' };

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation('auth');
  return (
    <label>
      <span className="visually-hidden">{t('languageSwitcher')}</span>
      <select
        className={styles.langSelect}
        value={i18n.language}
        onChange={(e) => {
          const language = e.target.value as Language;
          useAuthStore.getState().setLanguage(language);
          void i18n.changeLanguage(language);
        }}
      >
        {LANGUAGES.map((lng) => (
          <option key={lng} value={lng}>
            {LANGUAGE_NAMES[lng]}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Brand() {
  return (
    <Link to="/" className={styles.brand}>
      <span className={styles.brandMark} aria-hidden="true">
        L
      </span>
      LifeOS
    </Link>
  );
}

/** Public pages (login/register). Signed-in users are sent to the dashboard. */
export function AuthLayout() {
  const status = useAuthStore((s) => s.status);
  if (status === 'unknown') return <FullPageSpinner />;
  if (status === 'authenticated') return <Navigate to="/" replace />;
  return (
    <div className={styles.authShell}>
      <div className={styles.authInner}>
        <div className={styles.authTop}>
          <Brand />
          <LanguageSwitcher />
        </div>
        <Outlet />
      </div>
    </div>
  );
}
