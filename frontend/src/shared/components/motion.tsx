import { animate, motion, useInView, useReducedMotion } from 'motion/react';
import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react';

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
  children,
}: {
  value: number;
  size?: number;
  stroke?: number;
  children?: ReactNode;
}) {
  const radius = (size - stroke) / 2;
  const clamped = Math.min(1, Math.max(0, value));
  return (
    <div className={styles.ring} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <defs>
          <linearGradient id="ring-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#f9a8d4" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(255 255 255 / 16%)"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#ring-gradient)"
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
