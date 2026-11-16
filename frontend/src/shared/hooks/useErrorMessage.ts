import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '@/shared/api/client';

/** Maps any thrown value to a translated, user-facing message (errors.<CODE>). */
export function useErrorMessage() {
  const { t, i18n } = useTranslation('common');
  return useCallback(
    (error: unknown): string => {
      if (error instanceof ApiError) {
        const key = `errors.${error.code}`;
        return i18n.exists(key, { ns: 'common' }) ? t(key) : t('errors.UNKNOWN_ERROR');
      }
      if (error instanceof TypeError) return t('errors.NETWORK_ERROR');
      return t('errors.UNKNOWN_ERROR');
    },
    [t, i18n],
  );
}
