import type { PointerEvent } from 'react';

export const EASE = [0.2, 0.7, 0.2, 1] as const;

/** Tracks the pointer so CSS can paint a soft spotlight under it (--x, --y). */
export function spotlight(event: PointerEvent<HTMLElement>) {
  const el = event.currentTarget;
  const rect = el.getBoundingClientRect();
  el.style.setProperty('--x', `${event.clientX - rect.left}px`);
  el.style.setProperty('--y', `${event.clientY - rect.top}px`);
}

export const staggerParent = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.1 } },
};

export const riseChild = {
  hidden: { opacity: 0, y: 18, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.55, ease: EASE } },
};
