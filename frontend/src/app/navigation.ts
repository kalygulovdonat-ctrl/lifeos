import {
  CalendarDays,
  ChartColumn,
  ClipboardCheck,
  HeartPulse,
  LayoutDashboard,
  ListTodo,
  NotebookPen,
  Repeat,
  Settings,
  Sparkles,
  Target,
  Timer,
  type LucideIcon,
} from 'lucide-react';

export type ModuleKey =
  | 'dashboard'
  | 'schedule'
  | 'tasks'
  | 'habits'
  | 'goals'
  | 'journal'
  | 'time'
  | 'analytics'
  | 'reviews'
  | 'wellness'
  | 'assistant'
  | 'settings';

export interface NavItem {
  key: ModuleKey;
  to: string;
  icon: LucideIcon;
  /** Roadmap phase that delivers the module (PRD §13); undefined = available now. */
  phase?: string;
  end?: boolean;
}

export interface NavGroup {
  key: 'today' | 'planning' | 'growth' | 'insight';
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    key: 'today',
    items: [{ key: 'dashboard', to: '/', icon: LayoutDashboard, end: true }],
  },
  {
    key: 'planning',
    items: [
      { key: 'schedule', to: '/schedule', icon: CalendarDays },
      { key: 'tasks', to: '/tasks', icon: ListTodo },
      { key: 'time', to: '/time', icon: Timer },
    ],
  },
  {
    key: 'growth',
    items: [
      { key: 'habits', to: '/habits', icon: Repeat },
      { key: 'goals', to: '/goals', icon: Target },
      { key: 'journal', to: '/journal', icon: NotebookPen },
      { key: 'wellness', to: '/wellness', icon: HeartPulse },
    ],
  },
  {
    key: 'insight',
    items: [
      { key: 'analytics', to: '/analytics', icon: ChartColumn },
      { key: 'reviews', to: '/reviews', icon: ClipboardCheck },
      { key: 'assistant', to: '/assistant', icon: Sparkles },
    ],
  },
];

export const SETTINGS_ITEM: NavItem = { key: 'settings', to: '/settings', icon: Settings };

export const ALL_NAV_ITEMS: NavItem[] = [...NAV_GROUPS.flatMap((g) => g.items), SETTINGS_ITEM];

/** Items shown in the compact mobile tab bar. */
export const MOBILE_NAV_KEYS: ModuleKey[] = ['dashboard', 'schedule', 'tasks', 'habits'];

export function navItem(key: ModuleKey): NavItem {
  const item = ALL_NAV_ITEMS.find((i) => i.key === key);
  if (!item) throw new Error(`Unknown module ${key}`);
  return item;
}
