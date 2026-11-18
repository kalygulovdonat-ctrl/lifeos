import { animate, motion, useInView, useReducedMotion } from 'motion/react';
import { Fragment, useEffect, useRef, useState, type ReactNode, useId } from 'react';

import { EASE } from './motion-utils';
import styles from './motion.module.css';

/** Number that counts up from 0 when it scrolls into view. */
export function CountUp({
  value,
  format = (n) => String(Math.round(n)),
  duration = 1.2,
}: {
  value: number;
  format?: (n: number) => string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);

  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setShown(value);
      return;
    }
    const controls = animate(0, value, { duration, ease: EASE, onUpdate: setShown });
    return () => controls.stop();
  }, [inView, value, duration, reduce]);

  return (
    <span ref={ref} className={styles.tabular}>
      {format(shown)}
    </span>
  );
}

/** Circular progress (0–1) that draws itself in. */
export function ProgressRing({
  value,
  size = 168,
  stroke = 12,
  tone = 'onDark',
  children,
}: {
  value: number;
  size?: number;
  stroke?: number;
  /** onDark: white ring for gradient heroes; onLight: brand ring for regular cards. */
  tone?: 'onDark' | 'onLight';
  children?: ReactNode;
}) {
  const radius = (size - stroke) / 2;
  const gradientId = useId().replace(/:/g, '');
  const light = tone === 'onLight';
  const clamped = Math.min(1, Math.max(0, value));
  return (
    <div className={styles.ring} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={light ? '#5650e6' : '#ffffff'} />
            <stop offset="100%" stopColor={light ? '#d946ef' : '#f9a8d4'} />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={light ? 'var(--color-surface-2)' : 'rgb(255 255 255 / 16%)'}
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          initial={{ pathLength: 0 }}
          animate={{ pathLength: clamped }}
          transition={{ duration: 1.4, ease: EASE, delay: 0.2 }}
        />
      </svg>
      <div className={styles.ringCenter}>{children}</div>
    </div>
  );
}

/** Thin horizontal progress bar that fills in. */
export function ProgressBar({ value }: { value: number }) {
  return (
    <div className={styles.bar}>
      <motion.span
        initial={{ scaleX: 0 }}
        animate={{ scaleX: Math.min(1, Math.max(0, value)) }}
        transition={{ duration: 1.2, ease: EASE, delay: 0.3 }}
      />
    </div>
  );
}

/** Splits text into words that rise in one after another. Keeps plain text for a11y/tests. */
export function RevealText({ text, delay = 0 }: { text: string; delay?: number }) {
  const reduce = useReducedMotion();
  if (reduce) return <>{text}</>;
  const words = text.split(' ');
  return (
    <span className={styles.reveal}>
      {words.map((word, i) => (
        // The space sits outside the inline-block mask, otherwise it would collapse.
        <Fragment key={`${word}-${i}`}>
          <span className={styles.revealMask}>
            <motion.span
              className={styles.revealWord}
              initial={{ y: '110%' }}
              animate={{ y: '0%' }}
              transition={{ duration: 0.7, ease: EASE, delay: delay + i * 0.06 }}
            >
              {word}
            </motion.span>
          </span>
          {i < words.length - 1 ? ' ' : null}
        </Fragment>
      ))}
    </span>
  );
}

const CONFETTI_COLORS = ['#5650e6', '#d946ef', '#f472b6', '#22c55e', '#f59e0b', '#3b82f6'];

/**
 * A short burst of confetti from the center of its parent (which needs `position: relative`).
 * Plays once when mounted; renders nothing when the user prefers reduced motion.
 */
export function Confetti({ pieces = 28, spread = 1 }: { pieces?: number; spread?: number }) {
  const reduce = useReducedMotion();
  const [bits] = useState(() =>
    Array.from({ length: pieces }, (_, i) => {
      const angle = (i / pieces) * Math.PI * 2 + Math.random() * 0.4;
      const distance = (70 + Math.random() * 90) * spread;
      return {
        x: Math.cos(angle) * distance,
        y: Math.sin(angle) * distance - 40 * spread,
        rotate: Math.random() * 540 - 270,
        color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
        round: i % 3 === 0,
        delay: Math.random() * 0.08,
      };
    }),
  );
  if (reduce) return null;
  return (
    <span className={styles.confetti} aria-hidden="true">
      {bits.map((b, i) => (
        <motion.i
          key={i}
          style={{ background: b.color, borderRadius: b.round ? '50%' : 2 }}
          initial={{ x: 0, y: 0, opacity: 1, scale: 0.6, rotate: 0 }}
          animate={{
            x: b.x,
            y: [0, b.y, b.y + 90 * spread],
            opacity: [1, 1, 0],
            scale: spread < 1 ? 0.7 : 1,
            rotate: b.rotate,
          }}
          transition={{ duration: 1.3, ease: 'easeOut', delay: b.delay, times: [0, 0.45, 1] }}
        />
      ))}
    </span>
  );
}

/** A check mark that pops in (completed task, confirmed AI draft). */
export function PopCheck({ size = 16 }: { size?: number }) {
  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      initial={{ scale: 0.4, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 500, damping: 18 }}
    >
      <motion.path
        d="M5 12.5l4.5 4.5L19 7.5"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.35, ease: EASE, delay: 0.1 }}
      />
    </motion.svg>
  );
}
