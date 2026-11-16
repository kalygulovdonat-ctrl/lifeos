import { ChevronDown, Globe } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, Outlet } from 'react-router';

import { LANGUAGES, type Language } from '@/shared/api/types';
import { Aurora, LogoMark } from '@/shared/components/brand';
import { FullPageSpinner } from '@/shared/components/ui';
import { useAuthStore } from '@/shared/store/authStore';

import styles from './layouts.module.css';
import { LifeOrbit } from './LifeOrbit';

const LANGUAGE_NAMES: Record<Language, string> = { ru: 'Русский', en: 'English', ky: 'Кыргызча' };

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation('auth');
  return (
    <label className={styles.langWrap}>
      <span className="visually-hidden">{t('languageSwitcher')}</span>
      <Globe size={15} aria-hidden="true" />
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
      <ChevronDown size={14} aria-hidden="true" />
    </label>
  );
}

export function Brand({ onDark = false, link = true }: { onDark?: boolean; link?: boolean }) {
  const className = [styles.brand, onDark ? styles.brandOnDark : ''].join(' ');
  const content = (
    <>
      <LogoMark size={32} />
      LifeOS
    </>
  );
  // The decorative auth panel is aria-hidden, so it must not contain focusable links.
  if (!link) return <span className={className}>{content}</span>;
  return (
    <Link to="/" className={className}>
      {content}
    </Link>
  );
}

function BrandPanel() {
  const { t } = useTranslation('auth');
  return (
    <aside className={styles.authPanel} aria-hidden="true">
      <Aurora />
      <Brand onDark link={false} />
      <div className={styles.panelHeadline}>
        <h2 className="display">{t('panel.headline')}</h2>
        <p>{t('panel.subheadline')}</p>
      </div>
      <LifeOrbit />
      <p className={styles.panelFoot}>{t('panel.privacy')}</p>
    </aside>
  );
}

/** Public pages (login/register). Signed-in users are sent to the dashboard. */
export function AuthLayout() {
  const status = useAuthStore((s) => s.status);
  if (status === 'unknown') return <FullPageSpinner />;
  if (status === 'authenticated') return <Navigate to="/" replace />;
  return (
    <div className={styles.authShell}>
      <BrandPanel />
      <main className={styles.authMain}>
        <div className={styles.authTop}>
          <span className={styles.authMobileBrand}>
            <Brand />
          </span>
          <LanguageSwitcher />
        </div>
        <div className={styles.authFormArea}>
          <div className={styles.authFormInner}>
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
