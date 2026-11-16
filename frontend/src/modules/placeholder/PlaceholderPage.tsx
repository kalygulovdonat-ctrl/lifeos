import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { Card, EmptyState } from '@/shared/components/ui';

/** Stand-in for modules scheduled in later roadmap phases (PRD §13). */
export default function PlaceholderPage({
  moduleKey,
  phase,
}: {
  moduleKey: string;
  phase: string;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <EmptyState
        title={t('placeholder.title', { module: t(`nav.${moduleKey}`) })}
        description={t('placeholder.description', { phase })}
      />
    </Card>
  );
}

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <Card>
      <EmptyState title={t('notFound.title')} action={<Link to="/">{t('notFound.action')}</Link>} />
    </Card>
  );
}
