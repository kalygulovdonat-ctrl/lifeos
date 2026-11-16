import { ArrowLeft, Compass, Rocket } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { navItem, type ModuleKey } from '@/app/navigation';
import { Badge, Card, IconTile } from '@/shared/components/ui';

import styles from './placeholder.module.css';

/** Stand-in for modules scheduled in later roadmap phases (PRD §13). */
export default function PlaceholderPage({
  moduleKey,
  phase,
}: {
  moduleKey: ModuleKey;
  phase: string;
}) {
  const { t } = useTranslation();
  const Icon = navItem(moduleKey).icon;
  const features = t(`modules.${moduleKey}.features`, { returnObjects: true }) as unknown;
  const list = Array.isArray(features) ? (features as string[]) : [];

  return (
    <Card className={styles.card}>
      <div className={styles.glow} aria-hidden="true" />
      <span className={styles.orbits} aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span className={styles.floating}>
        <IconTile size={64}>
          <Icon size={30} strokeWidth={1.8} />
        </IconTile>
      </span>
      <Badge tone="accent" icon={<Rocket size={12} />}>
        {t('placeholder.badge', { phase })}
      </Badge>
      <h1 className={styles.title}>{t(`nav.${moduleKey}`)}</h1>
      <p className={styles.description}>{t(`modules.${moduleKey}.description`)}</p>
      {list.length ? (
        <ul className={styles.features}>
          {list.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
      ) : null}
      <p className={styles.note}>{t('placeholder.description', { phase })}</p>
      <Link to="/" className={styles.back}>
        <ArrowLeft size={15} aria-hidden="true" />
        {t('notFound.action')}
      </Link>
    </Card>
  );
}

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <Card className={styles.card}>
      <IconTile size={64}>
        <Compass size={30} strokeWidth={1.8} />
      </IconTile>
      <h1 className={styles.title}>{t('notFound.title')}</h1>
      <p className={styles.description}>{t('notFound.description')}</p>
      <Link to="/" className={styles.back}>
        <ArrowLeft size={15} aria-hidden="true" />
        {t('notFound.action')}
      </Link>
    </Card>
  );
}
