/** Visual language shared by tasks, schedule and dashboard. */
import {
  Armchair,
  Brain,
  CalendarClock,
  Coffee,
  Hourglass,
  Sparkle,
  type LucideIcon,
} from 'lucide-react';

import type { Priority, TimeType } from '@/shared/api/types';

export const TIME_TYPE_META: Record<TimeType, { color: string; icon: LucideIcon }> = {
  FIXED: { color: '#3b82f6', icon: CalendarClock },
  FOCUS: { color: '#8b5cf6', icon: Brain },
  PERSONAL: { color: '#ec4899', icon: Sparkle },
  REST: { color: '#14b8a6', icon: Coffee },
  BUFFER: { color: '#94a3b8', icon: Hourglass },
  FREE: { color: '#22c55e', icon: Armchair },
};

export const PRIORITY_COLOR: Record<Priority, string> = {
  LOW: '#94a3b8',
  MEDIUM: '#3b82f6',
  HIGH: '#f59e0b',
  URGENT: '#ef4444',
};

export const PRIORITY_RANK: Record<Priority, number> = { LOW: 0, MEDIUM: 1, HIGH: 2, URGENT: 3 };
