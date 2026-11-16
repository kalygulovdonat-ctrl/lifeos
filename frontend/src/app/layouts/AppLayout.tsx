import { useQueryClient } from '@tanstack/react-query';
import { Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router';

import { authApi } from '@/shared/api/auth';
import { Button, FullPageSpinner } from '@/shared/components/ui';
import { useAuthStore } from '@/shared/store/authStore';

import { Brand } from './AuthLayout';
import styles from './layouts.module.css';

export const NAV_ITEMS = [
  { to: '/', key: 'dashboard', end: true },
  { to: '/schedule', key: 'schedule' },
  { to: '/tasks', key: 'tasks' },
  { to: '/habits', key: 'habits' },
  { to: '/goals', key: 'goals' },
  { to: '/journal', key: 'journal' },
  { to: '/time', key: 'time' },
  { to: '/analytics', key: 'analytics' },
  { to: '/reviews', key: 'reviews' },
  { to: '/wellness', key: 'wellness' },
  { to: '/assistant', key: 'assistant' },
  { to: '/settings', key: 'settings' },
] as const;

/** Authenticated shell. Unauthenticated users are redirected to /login. */
export function AppLayout() {
  const { t } = useTranslation();
  const status = useAuthStore((s) => s.status);
  const profile = useAuthStore((s) => s.profile);
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  if (status === 'unknown') return <FullPageSpinner />;
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location }} />;

  const logout = async () => {
    try {
      await authApi.logout();
    } finally {
      useAuthStore.getState().clear();
      queryClient.clear();
      navigate('/login', { replace: true });
    }
  };

  return (
    <div className={styles.appShell}>
      <aside className={styles.sidebar}>
        <Brand />
        <nav className={styles.nav} aria-label={t('nav.mainNavigation')}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={'end' in item ? item.end : false}
              className={({ isActive }) =>
                [styles.navLink, isActive ? styles.navLinkActive : ''].join(' ')
              }
            >
              {t(`nav.${item.key}`)}
            </NavLink>
          ))}
        </nav>
        <div className={styles.sidebarFooter}>
          <span className={styles.userName}>{profile?.display_name}</span>
          <Button variant="ghost" onClick={logout}>
            {t('nav.logout')}
          </Button>
        </div>
      </aside>
      <main className={styles.main}>
        <Suspense fallback={<FullPageSpinner />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}
