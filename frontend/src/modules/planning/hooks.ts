import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { growthKeys } from '@/shared/api/growth';
import { categoriesApi, keys } from '@/shared/api/planning';
import type { Category } from '@/shared/api/types';

/** Invalidate everything a planning mutation can change (SDD §8.3). */
export function useInvalidatePlanning() {
  const qc = useQueryClient();
  return useCallback(() => {
    void qc.invalidateQueries({ queryKey: keys.tasks });
    void qc.invalidateQueries({ queryKey: keys.events });
    void qc.invalidateQueries({ queryKey: keys.dashboard });
    // Task changes move goal progress and actual time (SDD §8.3).
    void qc.invalidateQueries({ queryKey: growthKeys.goals });
    void qc.invalidateQueries({ queryKey: growthKeys.habits });
    void qc.invalidateQueries({ queryKey: growthKeys.time });
  }, [qc]);
}

export function useCategories() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: keys.categories,
    queryFn: categoriesApi.list,
    staleTime: 60_000,
  });
  const label = useCallback(
    (c: Category) =>
      c.system_key && !c.is_name_custom ? t(`categories.system.${c.system_key}`) : c.name,
    [t],
  );
  const byId = useMemo(() => new Map((query.data ?? []).map((c) => [c.id, c])), [query.data]);
  return { categories: query.data ?? [], byId, label, isLoading: query.isLoading };
}
