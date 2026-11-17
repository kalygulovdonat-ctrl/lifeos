import { Check, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import {
  forwardRef,
  useEffect,
  useId,
  useRef,
  type ReactNode,
  type TextareaHTMLAttributes,
} from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';

import { EASE } from './motion-utils';
import styles from './overlay.module.css';
import ui from './ui.module.css';

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Escape closes, Tab stays inside, focus returns to the opener, page does not scroll behind. */
function useDialogBehaviour<T extends HTMLElement>(open: boolean, onClose: () => void) {
  const ref = useRef<T>(null);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';
    const frame = requestAnimationFrame(() => {
      const root = ref.current;
      const target =
        root?.querySelector<HTMLElement>('[data-autofocus]') ??
        root?.querySelector<HTMLElement>(FOCUSABLE);
      target?.focus();
    });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        close.current();
        return;
      }
      if (e.key !== 'Tab' || !ref.current) return;
      const items = [...ref.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (!items.length) return;
      const first = items[0]!;
      const last = items[items.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      opener?.focus?.();
    };
  }, [open]);

  return ref;
}

interface OverlayProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
}

function Head({ id, title, onClose }: { id: string; title: ReactNode; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <header className={styles.head}>
      <h2 id={id}>{title}</h2>
      <button
        type="button"
        className={styles.close}
        onClick={onClose}
        aria-label={t('actions.close')}
      >
        <X size={18} />
      </button>
    </header>
  );
}

export function Modal({ open, onClose, title, children, footer, size = 'md' }: OverlayProps) {
  const ref = useDialogBehaviour<HTMLDivElement>(open, onClose);
  const titleId = useId();
  return createPortal(
    <AnimatePresence>
      {open ? (
        <div className={styles.layer}>
          <motion.div
            className={styles.backdrop}
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.div
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className={[styles.modal, styles[size]].join(' ')}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            transition={{ duration: 0.22, ease: EASE }}
          >
            <Head id={titleId} title={title} onClose={onClose} />
            <div className={styles.body}>{children}</div>
            {footer ? <footer className={styles.foot}>{footer}</footer> : null}
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}

export function Drawer({ open, onClose, title, children, footer }: Omit<OverlayProps, 'size'>) {
  const ref = useDialogBehaviour<HTMLElement>(open, onClose);
  const titleId = useId();
  return createPortal(
    <AnimatePresence>
      {open ? (
        <div className={styles.layer}>
          <motion.div
            className={styles.backdrop}
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className={styles.drawer}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.32, ease: EASE }}
          >
            <Head id={titleId} title={title} onClose={onClose} />
            <div className={styles.body}>{children}</div>
            {footer ? <footer className={styles.foot}>{footer}</footer> : null}
          </motion.aside>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}

/** Round "done" toggle used for tasks and subtasks. */
export function CheckButton({
  checked,
  onChange,
  label,
  disabled,
  size = 22,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  size?: number;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={styles.check}
      data-checked={checked || undefined}
      style={{ width: size, height: size }}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        onChange(!checked);
      }}
    >
      <motion.span
        initial={false}
        animate={{ scale: checked ? 1 : 0, opacity: checked ? 1 : 0 }}
        transition={{ type: 'spring', stiffness: 520, damping: 28 }}
      >
        <Check size={Math.round(size * 0.62)} strokeWidth={3} />
      </motion.span>
    </button>
  );
}

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { label, error, id, className, ...rest },
  ref,
) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div className={ui.field}>
      <label htmlFor={fieldId} className={ui.label}>
        {label}
      </label>
      <textarea
        ref={ref}
        id={fieldId}
        className={[ui.input, styles.textarea, className].filter(Boolean).join(' ')}
        aria-invalid={error ? true : undefined}
        {...rest}
      />
      {error ? (
        <span className={ui.error} role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
});

/** Small tone-coloured notice used for schedule warnings. */
export function Notice({
  tone = 'warning',
  icon,
  children,
}: {
  tone?: 'warning' | 'danger' | 'info' | 'success';
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={styles.notice} data-tone={tone} role={tone === 'danger' ? 'alert' : 'status'}>
      {icon}
      <div>{children}</div>
    </div>
  );
}
