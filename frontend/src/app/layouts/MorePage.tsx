import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ALL_NAV_ITEMS } from '@/app/navigation';
import { PageHeader } from '@/shared/components/ui';

import styles from './layouts.module.css';

/** Phone-only index of every module (the tab bar fits four). */
export default function MorePage() {
  const { t } = useTranslation();
  return (
    <div>
      <PageHeader title={t('nav.more')} />
      <ul className={styles.moreList}>
        {ALL_NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <li key={item.key}>
              <Link to={item.to} className={styles.moreItem}>
                <Icon size={20} aria-hidden="true" />
                <span>{t(`nav.${item.key}`)}</span>
                {item.phase ? <small>{t('nav.soon', { phase: item.phase })}</small> : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
