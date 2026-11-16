import {
  ChartColumn,
  ChevronDown,
  CircleCheck,
  Compass,
  Globe,
  Lightbulb,
  Play,
  Zap,
} from 'lucide-react';
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
      <span className={styles.brandMark} aria-hidden="true">
        <Zap size={18} strokeWidth={2.4} />
      </span>
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

/** Plan → Execute → Track → Reflect → Improve (PRD §17). */
const CYCLE = [
  { key: 'plan', icon: Compass },
  { key: 'execute', icon: Play },
  { key: 'track', icon: ChartColumn },
  { key: 'reflect', icon: Lightbulb },
  { key: 'improve', icon: CircleCheck },
] as const;

function BrandPanel() {
  const { t } = useTranslation('auth');
  return (
    <aside className={styles.authPanel} aria-hidden="true">
      <Brand onDark link={false} />
      <div className={styles.panelHeadline}>
        <h2>{t('panel.headline')}</h2>
        <p>{t('panel.subheadline')}</p>
      </div>
      <ul className={styles.cycle}>
        {CYCLE.map(({ key, icon: Icon }) => (
          <li key={key} className={styles.cycleItem}>
            <span className={styles.cycleIcon}>
              <Icon size={17} />
            </span>
            <span className={styles.cycleText}>
              <strong>{t(`panel.cycle.${key}.title`)}</strong>
              <span>{t(`panel.cycle.${key}.text`)}</span>
            </span>
          </li>
        ))}
      </ul>
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
