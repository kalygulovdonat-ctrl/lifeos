import { lazy } from 'react';
import { Navigate, type RouteObject } from 'react-router';

import { AppLayout } from '@/app/layouts/AppLayout';
import { AuthLayout } from '@/app/layouts/AuthLayout';
import PlaceholderPage, { NotFoundPage } from '@/modules/placeholder/PlaceholderPage';

const LoginPage = lazy(() => import('@/modules/auth/LoginPage'));
const RegisterPage = lazy(() => import('@/modules/auth/RegisterPage'));
const DashboardPage = lazy(() => import('@/modules/dashboard/DashboardPage'));
const ProfileSettingsPage = lazy(() => import('@/modules/settings/ProfileSettingsPage'));

/** Modules not built yet, with the roadmap phase that delivers them (PRD §13). */
const UPCOMING: ReadonlyArray<{ path: string; key: string; phase: string }> = [
  { path: 'schedule/*', key: 'schedule', phase: 'Phase 1' },
  { path: 'tasks/*', key: 'tasks', phase: 'Phase 1' },
  { path: 'habits/*', key: 'habits', phase: 'Phase 2' },
  { path: 'goals/*', key: 'goals', phase: 'Phase 2' },
  { path: 'journal/*', key: 'journal', phase: 'Phase 2' },
  { path: 'time/*', key: 'time', phase: 'Phase 2' },
  { path: 'analytics/*', key: 'analytics', phase: 'Phase 3' },
  { path: 'reviews/*', key: 'reviews', phase: 'Phase 3' },
  { path: 'assistant/*', key: 'assistant', phase: 'Phase 3' },
  { path: 'wellness/*', key: 'wellness', phase: 'Phase 4' },
];

export const routes: RouteObject[] = [
  {
    element: <AuthLayout />,
    children: [
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
    ],
  },
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'settings', element: <Navigate to="/settings/profile" replace /> },
      { path: 'settings/profile', element: <ProfileSettingsPage /> },
      ...UPCOMING.map(({ path, key, phase }) => ({
        path,
        element: <PlaceholderPage moduleKey={key} phase={phase} />,
      })),
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];
