import { ChartColumn, CircleCheck, Compass, Lightbulb, Play } from 'lucide-react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { LogoMark } from '@/shared/components/brand';

import styles from './LifeOrbit.module.css';

/** Plan → Execute → Track → Reflect → Improve (PRD §17). */
const STEPS = [
  { key: 'plan', icon: Compass },
  { key: 'execute', icon: Play },
  { key: 'track', icon: ChartColumn },
  { key: 'reflect', icon: Lightbulb },
  { key: 'improve', icon: CircleCheck },
] as const;

const STEP_MS = 2600;

/**
 * The LifeOS loop as a slowly turning orbit. One step at a time is highlighted
 * and described underneath, so the panel reads like a short story, not a list.
 */
export function LifeOrbit() {
  const { t } = useTranslation('auth');
  const reduceMotion = useReducedMotion();
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (reduceMotion) return;
    const id = window.setInterval(() => setActive((i) => (i + 1) % STEPS.length), STEP_MS);
    return () => window.clearInterval(id);
  }, [reduceMotion]);

  const step = STEPS[active] ?? STEPS[0];

  return (
    <div className={styles.wrap}>
      <div className={styles.stage}>
        <svg className={styles.rings} viewBox="0 0 400 400" aria-hidden="true">
          <circle cx="200" cy="200" r="150" className={styles.ringOuter} />
          <circle cx="200" cy="200" r="96" className={styles.ringInner} />
        </svg>

        <div className={styles.core}>
          <span className={styles.pulse} />
          <span className={styles.pulse} style={{ animationDelay: '1.3s' }} />
          <LogoMark size={72} />
        </div>

        <div className={[styles.orbit, reduceMotion ? styles.still : ''].join(' ')}>
          {STEPS.map(({ key, icon: Icon }, i) => {
            const angle = (i / STEPS.length) * 360 - 90;
            const isActive = i === active;
            return (
              <div
                key={key}
                className={styles.slot}
                style={{ transform: `rotate(${angle}deg) translate(150px) rotate(${-angle}deg)` }}
              >
                <div className={styles.upright}>
                  <motion.div
                    className={[styles.node, isActive ? styles.nodeActive : ''].join(' ')}
                    animate={{ scale: isActive ? 1.18 : 1 }}
                    transition={{ type: 'spring', stiffness: 260, damping: 18 }}
                  >
                    <Icon size={20} />
                  </motion.div>
                  <span className={[styles.label, isActive ? styles.labelActive : ''].join(' ')}>
                    {t(`panel.cycle.${key}.title`)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className={styles.caption}>
        <div className={styles.captionText}>
          <AnimatePresence initial={false}>
            <motion.div
              key={step.key}
              className={styles.captionItem}
              initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, y: -8, filter: 'blur(4px)' }}
              transition={{ duration: 0.5, ease: [0.2, 0.7, 0.2, 1] }}
            >
              <span className={styles.stepNo}>
                {String(active + 1).padStart(2, '0')} / {String(STEPS.length).padStart(2, '0')}
              </span>
              <strong>{t(`panel.cycle.${step.key}.title`)}</strong>
              <p>{t(`panel.cycle.${step.key}.text`)}</p>
            </motion.div>
          </AnimatePresence>
        </div>
        <div className={styles.dots}>
          {STEPS.map((s, i) => (
            <span key={s.key} className={i === active ? styles.dotActive : undefined} />
          ))}
        </div>
      </div>
    </div>
  );
}
