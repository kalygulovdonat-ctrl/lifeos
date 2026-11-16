import { useQueryClient } from '@tanstack/react-query';
import { LogOut } from 'lucide-react';
import { Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router';

import {
  MOBILE_NAV_KEYS,
  NAV_GROUPS,
  navItem,
  SETTINGS_ITEM,
  type NavItem,
} from '@/app/navigation';
import { authApi } from '@/shared/api/auth';
import { Avatar, FullPageSpinner } from '@/shared/components/ui';
import { useAuthStore } from '@/shared/store/authStore';

import { Brand } from './AuthLayout';
import styles from './layouts.module.css';

function SidebarLink({ item }: { item: NavItem }) {
  const { t } = useTranslation();
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) => [styles.navLink, isActive ? styles.navLinkActive : ''].join(' ')}
    >
      <Icon size={18} strokeWidth={2} aria-hidden="true" />
      <span className={styles.navLabel}>{t(`nav.${item.key}`)}</span>
      {item.phase ? (
        <span className={styles.navSoon} title={t('nav.soon', { phase: item.phase })} />
      ) : null}
    </NavLink>
  );
}

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

  const name = profile?.display_name ?? '';

  return (
    <div className={styles.appShell}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarBrand}>
          <Brand />
        </div>
        <nav className={styles.nav} aria-label={t('nav.mainNavigation')}>
          {NAV_GROUPS.map((group) => (
            <div key={group.key} className={styles.navGroup}>
              {group.key !== 'today' ? (
                <span className={styles.navGroupTitle}>{t(`nav.groups.${group.key}`)}</span>
              ) : null}
              {group.items.map((item) => (
                <SidebarLink key={item.key} item={item} />
              ))}
            </div>
          ))}
          <div className={styles.navGroup} style={{ marginTop: 'auto' }}>
            <SidebarLink item={SETTINGS_ITEM} />
          </div>
        </nav>
        <div className={styles.userCard}>
          <Avatar name={name} />
          <div className={styles.userMeta}>
            <span className={styles.userName}>{name}</span>
            <span className={styles.userEmail}>{profile?.email}</span>
          </div>
          <button
            type="button"
            className={styles.iconButton}
            onClick={logout}
            aria-label={t('nav.logout')}
            title={t('nav.logout')}
          >
            <LogOut size={17} aria-hidden="true" />
          </button>
        </div>
      </aside>

      <main className={styles.main}>
        <div className={styles.mobileTop}>
          <Brand />
          <button
            type="button"
            className={styles.iconButton}
            onClick={logout}
            aria-label={t('nav.logout')}
          >
            <LogOut size={18} aria-hidden="true" />
          </button>
        </div>
        <div className={styles.mainInner} key={location.pathname}>
          <Suspense fallback={<FullPageSpinner />}>
            <Outlet />
          </Suspense>
        </div>
      </main>

      <nav className={styles.tabBar} aria-label={t('nav.mainNavigation')}>
        {MOBILE_NAV_KEYS.map((key) => {
          const item = navItem(key);
          const Icon = item.icon;
          return (
            <NavLink
              key={key}
              to={item.to}
              end={item.end}
              className={({ isActive }) => [styles.tab, isActive ? styles.tabActive : ''].join(' ')}
            >
              <Icon size={20} aria-hidden="true" />
              {t(`nav.${key}`)}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
