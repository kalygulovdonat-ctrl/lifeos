import { useQueryClient } from '@tanstack/react-query';
import { LayoutGrid, LogOut, Moon, Sun } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
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
import { authApi, profileApi } from '@/shared/api/auth';
import { Avatar, FullPageSpinner } from '@/shared/components/ui';
import { applyTheme } from '@/shared/hooks/useSession';
import { useAuthStore } from '@/shared/store/authStore';

import { Brand } from './AuthLayout';
import styles from './layouts.module.css';
import { TimerPill } from '@/modules/time/TimerPill';

function SidebarLink({ item }: { item: NavItem }) {
  const { t } = useTranslation();
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      viewTransition
      className={({ isActive }) => [styles.navLink, isActive ? styles.navLinkActive : ''].join(' ')}
    >
      {({ isActive }) => (
        <>
          {isActive ? (
            // Shared layout id: the highlight glides to whichever item becomes active.
            <motion.span
              layoutId="nav-active"
              className={styles.navActiveBg}
              transition={{ type: 'spring', stiffness: 420, damping: 34 }}
            />
          ) : null}
          <Icon size={18} strokeWidth={2} aria-hidden="true" className={styles.navIcon} />
          <span className={styles.navLabel}>{t(`nav.${item.key}`)}</span>
          {item.phase ? (
            <span className={styles.navSoon} title={t('nav.soon', { phase: item.phase })} />
          ) : null}
        </>
      )}
    </NavLink>
  );
}

function resolvedTheme(theme: string | undefined): 'light' | 'dark' {
  if (theme === 'light' || theme === 'dark') return theme;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/** One-click light/dark switch; persists to the profile like the settings page does. */
function ThemeToggle() {
  const { t } = useTranslation('settings');
  const profile = useAuthStore((s) => s.profile);
  const current = resolvedTheme(profile?.theme);
  const next = current === 'dark' ? 'light' : 'dark';

  const toggle = async () => {
    applyTheme(next);
    try {
      const updated = await profileApi.update({ theme: next });
      useAuthStore.getState().setProfile(updated);
    } catch {
      applyTheme(profile?.theme ?? 'system');
    }
  };

  return (
    <button
      type="button"
      className={styles.iconButton}
      onClick={toggle}
      aria-label={t(next === 'dark' ? 'profile.themeDark' : 'profile.themeLight')}
      title={t(next === 'dark' ? 'profile.themeDark' : 'profile.themeLight')}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={current}
          className={styles.themeIcon}
          initial={{ rotate: -90, scale: 0.4, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0.4, opacity: 0 }}
          transition={{ duration: 0.25 }}
        >
          {current === 'dark' ? <Moon size={17} /> : <Sun size={17} />}
        </motion.span>
      </AnimatePresence>
    </button>
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
          <ThemeToggle />
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
        <TimerPill />
        <div className={styles.userCard}>
          <Avatar name={name} />
          <div className={styles.userMeta}>
            <span className={styles.userName}>{name}</span>
            <span className={styles.userEmail}>{profile?.email}</span>
          </div>
          <button
            type="button"
            className={[styles.iconButton, styles.logoutButton].join(' ')}
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
          <span className={styles.mobileActions}>
            <TimerPill compact />
            <ThemeToggle />
            <button
              type="button"
              className={styles.iconButton}
              onClick={logout}
              aria-label={t('nav.logout')}
            >
              <LogOut size={18} aria-hidden="true" />
            </button>
          </span>
        </div>
        <div className={styles.mainInner}>
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
              viewTransition
              className={({ isActive }) => [styles.tab, isActive ? styles.tabActive : ''].join(' ')}
            >
              <Icon size={20} aria-hidden="true" />
              {t(`nav.${key}`)}
            </NavLink>
          );
        })}
        <NavLink
          to="/more"
          viewTransition
          className={({ isActive }) => [styles.tab, isActive ? styles.tabActive : ''].join(' ')}
        >
          <LayoutGrid size={20} aria-hidden="true" />
          {t('nav.more')}
        </NavLink>
      </nav>
    </div>
  );
}
