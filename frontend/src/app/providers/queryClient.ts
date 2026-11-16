import { QueryClient } from '@tanstack/react-query';

import { ApiError } from '@/shared/api/client';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        // Do not retry client errors (4xx): they will not succeed on retry.
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
      mutations: { retry: false },
    },
  });
}
