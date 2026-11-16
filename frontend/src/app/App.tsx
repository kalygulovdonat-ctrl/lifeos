import { QueryClientProvider } from '@tanstack/react-query';
import { Suspense, useState } from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router';

import { createQueryClient } from '@/app/providers/queryClient';
import { routes } from '@/app/router/routes';
import { FullPageSpinner } from '@/shared/components/ui';
import { useProfilePreferences, useSessionBootstrap } from '@/shared/hooks/useSession';

const router = createBrowserRouter(routes);

export function App() {
  const [queryClient] = useState(createQueryClient);
  useSessionBootstrap();
  useProfilePreferences();

  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<FullPageSpinner />}>
        <RouterProvider router={router} />
      </Suspense>
    </QueryClientProvider>
  );
}
