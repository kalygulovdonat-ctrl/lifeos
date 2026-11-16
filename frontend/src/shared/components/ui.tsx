import { ChevronDown, CircleAlert } from 'lucide-react';
import {
  forwardRef,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react';
import type { UseFormRegisterReturn } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import styles from './ui.module.css';

const cx = (...names: Array<string | false | null | undefined>) => names.filter(Boolean).join(' ');

/* ---------- Button ---------- */

type ButtonVariant = 'primary' | 'secondary' | 'ghost';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md' | 'lg';
  block?: boolean;
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  block = false,
  loading = false,
  icon,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        styles.button,
        styles[variant],
        size !== 'md' && styles[size],
        block && styles.block,
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className={styles.spinnerInline} aria-hidden="true" /> : icon}
      {children}
    </button>
  );
}

/* ---------- Fields ---------- */

interface FieldShellProps {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}

function FieldShell({ id, label, error, hint, children }: FieldShellProps) {
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      {children}
      {hint && !error ? (
        <span id={`${id}-hint`} className={styles.hint}>
          {hint}
        </span>
      ) : null}
      {error ? (
        <span id={`${id}-error`} className={styles.error} role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}

function describedBy(id: string, error?: string, hint?: string): string | undefined {
  if (error) return `${id}-error`;
  if (hint) return `${id}-hint`;
  return undefined;
}

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
  icon?: ReactNode;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, error, hint, icon, id, className, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <FieldShell id={inputId} label={label} error={error} hint={hint}>
      <div className={styles.control}>
        {icon ? (
          <span className={styles.controlIcon} aria-hidden="true">
            {icon}
          </span>
        ) : null}
        <input
          ref={ref}
          id={inputId}
          className={cx(styles.input, icon ? styles.withIcon : null, className)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(inputId, error, hint)}
          {...rest}
        />
      </div>
    </FieldShell>
  );
});

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  error?: string;
  hint?: string;
  icon?: ReactNode;
  options: ReadonlyArray<{ value: string; label: string }>;
}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, error, hint, icon, id, options, ...rest },
  ref,
) {
  const autoId = useId();
  const selectId = id ?? autoId;
  return (
    <FieldShell id={selectId} label={label} error={error} hint={hint}>
      <div className={styles.control}>
        {icon ? (
          <span className={styles.controlIcon} aria-hidden="true">
            {icon}
          </span>
        ) : null}
        <select
          ref={ref}
          id={selectId}
          className={cx(styles.input, styles.select, icon ? styles.withIcon : null)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(selectId, error, hint)}
          {...rest}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <span className={styles.chevron} aria-hidden="true">
          <ChevronDown size={16} />
        </span>
      </div>
    </FieldShell>
  );
});

interface SegmentedProps {
  label: string;
  options: ReadonlyArray<{ value: string; label: string; icon?: ReactNode }>;
  registration: UseFormRegisterReturn;
}

/** Radio group styled as a segmented control; works with react-hook-form `register`. */
export function SegmentedControl({ label, options, registration }: SegmentedProps) {
  const groupId = useId();
  return (
    <div className={styles.field} role="radiogroup" aria-labelledby={`${groupId}-label`}>
      <span id={`${groupId}-label`} className={styles.label}>
        {label}
      </span>
      <div className={styles.segmented}>
        {options.map((option) => (
          <label key={option.value} className={styles.segment}>
            <input type="radio" value={option.value} {...registration} />
            <span>
              {option.icon}
              {option.label}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

/* ---------- Surfaces ---------- */

export function Card({
  children,
  className,
  padded = true,
  as: Tag = 'section',
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  as?: 'section' | 'div' | 'article';
}) {
  return <Tag className={cx(styles.card, padded && styles.pad, className)}>{children}</Tag>;
}

export function Badge({
  children,
  tone = 'neutral',
  icon,
}: {
  children: ReactNode;
  tone?: 'neutral' | 'accent' | 'success';
  icon?: ReactNode;
}) {
  const toneClass = tone === 'success' ? styles.successTone : styles[tone];
  return (
    <span className={cx(styles.badge, toneClass)}>
      {icon}
      {children}
    </span>
  );
}

export function Avatar({ name, size = 36 }: { name: string; size?: number }) {
  const initials =
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toLocaleUpperCase())
      .join('') || '•';
  return (
    <span
      className={styles.avatar}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}

export function IconTile({ children, size = 40 }: { children: ReactNode; size?: number }) {
  return (
    <span className={styles.iconTile} style={{ width: size, height: size }} aria-hidden="true">
      {children}
    </span>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className={styles.pageHeader}>
      <div>
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions}
    </header>
  );
}

/* ---------- Feedback ---------- */

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className={cx(styles.alert, styles.alertDanger)} role="alert">
      <CircleAlert size={16} aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

export function FullPageSpinner() {
  const { t } = useTranslation();
  return (
    <div className={styles.spinnerWrap} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <span className="visually-hidden">{t('status.loading')}</span>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className={styles.empty}>
      {icon}
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {action}
    </div>
  );
}
