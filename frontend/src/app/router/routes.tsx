import { lazy } from 'react';
import { Navigate, type RouteObject } from 'react-router';

import { AppLayout } from '@/app/layouts/AppLayout';
import { AuthLayout } from '@/app/layouts/AuthLayout';
import { NAV_GROUPS } from '@/app/navigation';
import PlaceholderPage, { NotFoundPage } from '@/modules/placeholder/PlaceholderPage';

const LoginPage = lazy(() => import('@/modules/auth/LoginPage'));
const RegisterPage = lazy(() => import('@/modules/auth/RegisterPage'));
const DashboardPage = lazy(() => import('@/modules/dashboard/DashboardPage'));
const ProfileSettingsPage = lazy(() => import('@/modules/settings/ProfileSettingsPage'));
const CategoriesSettingsPage = lazy(() => import('@/modules/settings/CategoriesSettingsPage'));
const TasksPage = lazy(() => import('@/modules/tasks/TasksPage'));
const SchedulePage = lazy(() => import('@/modules/schedule/SchedulePage'));

/** Modules not built yet get a placeholder; their phase comes from the navigation config. */
const UPCOMING = NAV_GROUPS.flatMap((group) => group.items).filter((item) => item.phase);

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
      { path: 'settings/categories', element: <CategoriesSettingsPage /> },
      { path: 'schedule', element: <Navigate to="/schedule/week" replace /> },
      { path: 'schedule/:view', element: <SchedulePage /> },
      { path: 'tasks', element: <TasksPage /> },
      { path: 'tasks/inbox', element: <TasksPage inbox /> },
      { path: 'tasks/:taskId', element: <TasksPage /> },
      ...UPCOMING.map(({ to, key, phase }) => ({
        path: `${to.slice(1)}/*`,
        element: <PlaceholderPage moduleKey={key} phase={phase ?? ''} />,
      })),
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];
