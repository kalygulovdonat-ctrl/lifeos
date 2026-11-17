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
const HabitsPage = lazy(() => import('@/modules/habits/HabitsPage'));
const HabitDetailPage = lazy(() => import('@/modules/habits/HabitDetailPage'));
const GoalsPage = lazy(() => import('@/modules/goals/GoalsPage'));
const GoalDetailPage = lazy(() => import('@/modules/goals/GoalDetailPage'));
const JournalPage = lazy(() => import('@/modules/journal/JournalPage'));
const DailyPage = lazy(() =>
  import('@/modules/journal/JournalEditorPage').then((m) => ({ default: m.DailyPage })),
);
const NotePage = lazy(() =>
  import('@/modules/journal/JournalEditorPage').then((m) => ({ default: m.NotePage })),
);
const TimePage = lazy(() => import('@/modules/time/TimePage'));
const MorePage = lazy(() => import('@/app/layouts/MorePage'));
const AnalyticsPage = lazy(() => import('@/modules/analytics/AnalyticsPage'));
const ReviewsPage = lazy(() => import('@/modules/reviews/ReviewsPage'));
const ReviewPage = lazy(() => import('@/modules/reviews/ReviewPage'));
const WellnessPage = lazy(() => import('@/modules/wellness/WellnessPage'));
const AssistantPage = lazy(() => import('@/modules/assistant/AssistantPage'));

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
      { path: 'habits', element: <HabitsPage /> },
      { path: 'habits/:habitId', element: <HabitDetailPage /> },
      { path: 'goals', element: <GoalsPage /> },
      { path: 'goals/:goalId', element: <GoalDetailPage /> },
      { path: 'journal', element: <JournalPage /> },
      { path: 'journal/new', element: <NotePage /> },
      { path: 'journal/date/:date', element: <DailyPage /> },
      { path: 'journal/:entryId', element: <NotePage /> },
      { path: 'time', element: <TimePage /> },
      { path: 'more', element: <MorePage /> },
      { path: 'analytics', element: <Navigate to="/analytics/week" replace /> },
      { path: 'analytics/:period', element: <AnalyticsPage /> },
      { path: 'reviews', element: <ReviewsPage /> },
      { path: 'reviews/:reviewId', element: <ReviewPage /> },
      { path: 'wellness', element: <WellnessPage /> },
      { path: 'assistant', element: <AssistantPage /> },
      { path: 'assistant/:conversationId', element: <AssistantPage /> },
      ...UPCOMING.map(({ to, key, phase }) => ({
        path: `${to.slice(1)}/*`,
        element: <PlaceholderPage moduleKey={key} phase={phase ?? ''} />,
      })),
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];
