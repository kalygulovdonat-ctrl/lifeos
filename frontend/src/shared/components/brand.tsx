import { useId } from 'react';

import styles from './brand.module.css';

/**
 * LifeOS mark: an orbit with a moving "day" dot around a core — the
 * Plan → Execute → Track → Reflect → Improve loop as a single glyph.
 */
export function LogoMark({ size = 32, animated = true }: { size?: number; animated?: boolean }) {
  const id = useId().replace(/:/g, '');
  return (
    <span className={styles.mark} style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 40 40" width={size} height={size}>
        <defs>
          <linearGradient id={`g-${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#7c74ff" />
            <stop offset="55%" stopColor="#a855f7" />
            <stop offset="100%" stopColor="#f472b6" />
          </linearGradient>
        </defs>
        <rect width="40" height="40" rx="12" fill={`url(#g-${id})`} />
        <circle
          cx="20"
          cy="20"
          r="11"
          fill="none"
          stroke="rgb(255 255 255 / 45%)"
          strokeWidth="2"
        />
        <path
          d="M20 9 A11 11 0 0 1 31 20"
          fill="none"
          stroke="#fff"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
        <circle cx="20" cy="20" r="3.6" fill="#fff" />
        <g className={animated ? styles.orbiting : undefined}>
          <circle cx="31" cy="20" r="2.8" fill="#fff" />
        </g>
      </svg>
    </span>
  );
}

/** Three blurred colour fields drifting slowly; place inside a `position: relative` box. */
export function Aurora({ tone = 'brand' }: { tone?: 'brand' | 'soft' }) {
  return (
    <span
      className={[styles.aurora, tone === 'soft' ? styles.soft : ''].join(' ')}
      aria-hidden="true"
    >
      <i className={styles.a} />
      <i className={styles.b} />
      <i className={styles.c} />
    </span>
  );
}
