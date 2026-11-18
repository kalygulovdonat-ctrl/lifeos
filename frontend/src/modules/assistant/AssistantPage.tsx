import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, Check, Eye, Plus, Send, ShieldCheck, Sparkles, Trash2, Undo2, X } from 'lucide-react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { useInvalidatePlanning } from '@/modules/planning/hooks';
import {
  aiApi,
  insightKeys,
  type AIAction,
  type AIMessage,
  type AIScope,
  type AIStatus,
} from '@/shared/api/insight';
import { PopCheck } from '@/shared/components/motion';
import { EASE } from '@/shared/components/motion-utils';
import { Notice } from '@/shared/components/overlay';
import { Alert, Button, PageHeader } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';

import s from './assistant.module.css';

const SENSITIVE: AIScope[] = ['JOURNAL', 'WELLNESS'];

export default function AssistantPage() {
  const { conversationId } = useParams();
  const { t } = useTranslation('assistant');
  const navigate = useNavigate();
  const qc = useQueryClient();
  const status = useQuery({ queryKey: insightKeys.aiStatus, queryFn: aiApi.status });
  const list = useQuery({ queryKey: insightKeys.aiConversations, queryFn: aiApi.conversations });
  const create = useMutation({
    mutationFn: aiApi.newConversation,
    onSuccess: (c) => {
      void qc.invalidateQueries({ queryKey: insightKeys.aiConversations });
      navigate(`/assistant/${c.id}`);
    },
  });
  const remove = useMutation({
    mutationFn: aiApi.removeConversation,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: insightKeys.aiConversations });
      navigate('/assistant');
    },
  });
  const st = status.data;

  return (
    <div className={s.page}>
      <PageHeader
        title={
          <span className={s.titleRow}>
            {t('title')}
            {st?.enabled && st.provider === 'fake' ? (
              <span className={s.demoBadge}>{t('demo.badge')}</span>
            ) : null}
          </span>
        }
        description={t('subtitle')}
      />
      {st?.enabled && st.provider === 'fake' ? (
        <Notice tone="info" icon={<Sparkles size={16} />}>
          <strong>{t('demo.title')}</strong> {t('demo.hint')}
        </Notice>
      ) : null}
      {st && !st.enabled ? (
        <Notice tone="info" icon={<Bot size={16} />}>
          <strong>{t('disabled.title')}</strong> {t('disabled.hint')}
        </Notice>
      ) : null}
      {st ? <Consents status={st} /> : null}
      {st?.enabled && st.scopes.length ? (
        <div className={s.layout}>
          <aside className={s.sidebar} aria-label={t('conversations')}>
            <Button
              size="sm"
              icon={<Plus size={15} />}
              loading={create.isPending}
              onClick={() => create.mutate()}
            >
              {t('newChat')}
            </Button>
            <ul>
              {(list.data ?? []).map((c) => (
                <li key={c.id}>
                  <Link
                    to={`/assistant/${c.id}`}
                    aria-current={c.id === conversationId ? 'page' : undefined}
                  >
                    {c.title || t('untitled')}
                  </Link>
                  <button
                    type="button"
                    onClick={() => remove.mutate(c.id)}
                    aria-label={t('deleteChat')}
                  >
                    <Trash2 size={13} />
                  </button>
                </li>
              ))}
            </ul>
          </aside>
          {conversationId ? (
            <Chat key={conversationId} conversationId={conversationId} />
          ) : (
            <div className={s.welcome}>
              <Sparkles size={28} />
              <h2>{t('welcome.title')}</h2>
              <p>{t('welcome.hint')}</p>
              <Button icon={<Plus size={16} />} onClick={() => create.mutate()}>
                {t('newChat')}
              </Button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function Consents({ status }: { status: AIStatus }) {
  const { t } = useTranslation('assistant');
  const qc = useQueryClient();
  const errorMessage = useErrorMessage();
  const [open, setOpen] = useState(status.scopes.length === 0);
  const save = useMutation({
    mutationFn: aiApi.setScopes,
    onSuccess: () => void qc.invalidateQueries({ queryKey: insightKeys.aiStatus }),
  });
  const toggle = (scope: AIScope) =>
    save.mutate(
      status.scopes.includes(scope)
        ? status.scopes.filter((x) => x !== scope)
        : [...status.scopes, scope],
    );
  const defaults = status.all_scopes.filter((x) => !SENSITIVE.includes(x));

  if (!open && status.scopes.length) {
    return (
      <div className={s.consentBar}>
        <ShieldCheck size={15} />
        <span>
          {t('consent.summary', { list: status.scopes.map((x) => t(`scope.${x}`)).join(', ') })}
        </span>
        <button type="button" onClick={() => setOpen(true)}>
          {t('consent.edit')}
        </button>
      </div>
    );
  }
  return (
    <section className={s.consent} aria-labelledby="consent-title">
      <h2 id="consent-title">
        <ShieldCheck size={16} /> {t('consent.title')}
      </h2>
      <p>{t('consent.hint')}</p>
      <ul>
        {status.all_scopes.map((scope) => (
          <li key={scope}>
            <label>
              <input
                type="checkbox"
                checked={status.scopes.includes(scope)}
                onChange={() => toggle(scope)}
                disabled={save.isPending}
              />
              <span>
                <strong>{t(`scope.${scope}`)}</strong>
                <small>{t(`scopeHint.${scope}`)}</small>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <div className={s.row}>
        {status.scopes.length === 0 ? (
          <Button
            size="sm"
            onClick={() => save.mutate(defaults, { onSuccess: () => setOpen(false) })}
            loading={save.isPending}
          >
            {t('consent.enable')}
          </Button>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>
            {t('consent.done')}
          </Button>
        )}
        {status.scopes.length ? (
          <Button size="sm" variant="ghost" onClick={() => save.mutate([])}>
            {t('consent.disable')}
          </Button>
        ) : null}
      </div>
      {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
    </section>
  );
}

function Chat({ conversationId }: { conversationId: string }) {
  const { t } = useTranslation('assistant');
  const qc = useQueryClient();
  const errorMessage = useErrorMessage();
  const [text, setText] = useState('');
  const bottom = useRef<HTMLDivElement>(null);
  const convo = useQuery({
    queryKey: insightKeys.aiConversation(conversationId),
    queryFn: () => aiApi.conversation(conversationId),
    // Poll while an answer is being generated (the provider runs in a background worker).
    refetchInterval: (q) =>
      q.state.data?.messages.some((m) => m.status === 'PENDING') ? 1500 : false,
  });
  const send = useMutation({
    mutationFn: (content: string) => aiApi.send(conversationId, content),
    onSuccess: () => {
      setText('');
      void qc.invalidateQueries({ queryKey: insightKeys.aiConversation(conversationId) });
      void qc.invalidateQueries({ queryKey: insightKeys.aiConversations });
      void qc.invalidateQueries({ queryKey: insightKeys.aiStatus });
    },
  });
  const messages = useMemo(() => convo.data?.messages ?? [], [convo.data]);
  const pending = messages.some((m) => m.status === 'PENDING');
  // Replies that arrive while the chat is open are typed out; history appears at once.
  const [history, setHistory] = useState<ReadonlySet<string> | null>(null);
  useEffect(() => {
    if (convo.data && history === null) setHistory(new Set(convo.data.messages.map((m) => m.id)));
  }, [convo.data, history]);
  const isFresh = (m: AIMessage) =>
    m.role === 'ASSISTANT' && history !== null && !history.has(m.id);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [messages.length, pending]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim() && !pending) send.mutate(text.trim());
  };
  const examples = [t('examples.plan'), t('examples.task'), t('examples.free')];

  return (
    <section className={s.chat} aria-label={t('chat')}>
      <div className={s.messages} aria-live="polite">
        {messages.length === 0 ? (
          <div className={s.examples}>
            <p>{t('examples.title')}</p>
            {examples.map((ex) => (
              <button key={ex} type="button" onClick={() => setText(ex)}>
                {ex}
              </button>
            ))}
          </div>
        ) : null}
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <motion.div
              key={m.id}
              layout="position"
              initial={{ opacity: 0, y: 14, scale: 0.92, x: m.role === 'USER' ? 16 : -16 }}
              animate={{ opacity: 1, y: 0, scale: 1, x: 0 }}
              transition={{ type: 'spring', stiffness: 420, damping: 30 }}
              style={{ transformOrigin: m.role === 'USER' ? '100% 100%' : '0% 100%' }}
              className={s.message}
              data-role={m.role}
            >
              <MessageBody message={m} conversationId={conversationId} typeOut={isFresh(m)} />
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottom} />
      </div>
      {send.error ? <Alert>{errorMessage(send.error)}</Alert> : null}
      <form className={s.composer} onSubmit={submit}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) submit(e);
          }}
          placeholder={t('placeholder')}
          aria-label={t('placeholder')}
          rows={2}
          maxLength={4000}
        />
        <button
          type="submit"
          disabled={!text.trim() || pending || send.isPending}
          aria-label={t('send')}
        >
          <Send size={17} />
        </button>
      </form>
      <p className={s.disclaimer}>{t('disclaimer')}</p>
    </section>
  );
}

/** Reveals text a few characters at a time, like someone typing; instant with reduced motion. */
function TypeOut({ text, onDone }: { text: string; onDone: () => void }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? text.length : 0);
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => {
    if (reduce) {
      done.current();
      return;
    }
    const step = Math.max(1, Math.ceil(text.length / 90)); // about 1.5 s whatever the length
    const id = window.setInterval(() => {
      setShown((n) => {
        const next = Math.min(text.length, n + step);
        if (next >= text.length) {
          window.clearInterval(id);
          done.current();
        }
        return next;
      });
    }, 16);
    return () => window.clearInterval(id);
  }, [text, reduce]);
  return (
    <p>
      <span className={s.srOnly}>{text}</span>
      <span aria-hidden="true">{text.slice(0, shown)}</span>
      {shown < text.length ? <span className={s.caret} aria-hidden="true" /> : null}
    </p>
  );
}

function MessageBody({
  message,
  conversationId,
  typeOut = false,
}: {
  message: AIMessage;
  conversationId: string;
  typeOut?: boolean;
}) {
  const [typed, setTyped] = useState(!typeOut);
  const { t } = useTranslation('assistant');
  const [showContext, setShowContext] = useState(false);
  const context = useQuery({
    queryKey: [...insightKeys.ai, 'context', message.id],
    queryFn: () => aiApi.context(message.id),
    enabled: showContext,
  });
  if (message.role === 'USER') return <p>{message.content}</p>;
  if (message.status === 'PENDING')
    return (
      <p className={s.thinking}>
        <span />
        <span />
        <span /> {t('thinking')}
      </p>
    );
  return (
    <>
      {message.status === 'ERROR' ? (
        <p className={s.error}>
          {t(`errors.${message.error_code ?? 'AI_INVALID_OUTPUT'}`, {
            defaultValue: t('errors.AI_INVALID_OUTPUT'),
          })}
        </p>
      ) : typed ? (
        <p>{message.content}</p>
      ) : (
        <TypeOut text={message.content} onDone={() => setTyped(true)} />
      )}
      <AnimatePresence>
        {typed
          ? message.actions.map((a, i) => (
              <motion.div
                key={a.id}
                initial={{ opacity: 0, height: 0, y: 10 }}
                animate={{ opacity: 1, height: 'auto', y: 0 }}
                transition={{ duration: 0.45, ease: EASE, delay: i * 0.08 }}
                style={{ overflow: 'hidden' }}
              >
                <ActionCard action={a} conversationId={conversationId} />
              </motion.div>
            ))
          : null}
      </AnimatePresence>
      {message.status === 'OK' && typed ? (
        <button type="button" className={s.contextBtn} onClick={() => setShowContext((v) => !v)}>
          <Eye size={13} /> {t('context.button')}
        </button>
      ) : null}
      {showContext && context.data ? (
        <p className={s.context}>
          {context.data.results.length
            ? context.data.results
                .map((r) => `${t(`scope.${r.scope}`)}${r.count ? ` (${r.count})` : ''}`)
                .join(', ')
            : t('context.none')}
        </p>
      ) : null}
    </>
  );
}

const EDITABLE: Record<string, string[]> = {
  CREATE_TASK: ['title', 'due_date', 'priority'],
  CREATE_EVENT: ['title', 'date', 'start', 'end'],
  RESCHEDULE_EVENT: ['date', 'start', 'end'],
  CREATE_JOURNAL_DRAFT: ['title', 'body'],
};

function ActionCard({ action, conversationId }: { action: AIAction; conversationId: string }) {
  const { t } = useTranslation('assistant');
  const tsch = useTranslation('schedule').t;
  const qc = useQueryClient();
  const invalidate = useInvalidatePlanning();
  const errorMessage = useErrorMessage();
  const [payload, setPayload] = useState<Record<string, unknown>>(
    action.edited_payload ?? action.payload,
  );
  const fields = EDITABLE[action.action_type] ?? [];
  const after = () => {
    void qc.invalidateQueries({ queryKey: insightKeys.aiConversation(conversationId) });
    invalidate();
  };
  const confirm = useMutation({
    mutationFn: () => aiApi.confirm(action.id, payload),
    onSettled: after,
  });
  const reject = useMutation({ mutationFn: () => aiApi.reject(action.id), onSettled: after });
  const revert = useMutation({ mutationFn: () => aiApi.revert(action.id), onSettled: after });
  const error = confirm.error ?? reject.error ?? revert.error;
  const proposed = action.status === 'PROPOSED';
  const link =
    action.result_object_type === 'task'
      ? `/tasks/${action.result_object_id}`
      : action.result_object_type === 'event'
        ? '/schedule/week'
        : action.result_object_type === 'journal_entry'
          ? `/journal/${action.result_object_id}`
          : action.result_object_type === 'habit_log'
            ? '/habits'
            : null;
  const readonly = Object.entries(action.payload).filter(
    ([k]) => !fields.includes(k) && k !== 'assumptions',
  );

  return (
    <div className={s.card} data-status={action.status}>
      <div className={s.cardHead}>
        <strong>{t(`action.${action.action_type}`)}</strong>
        <motion.span
          key={action.status}
          className={s.badge}
          data-status={action.status}
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 500, damping: 22 }}
        >
          {action.status === 'EXECUTED' ? <PopCheck size={11} /> : null}
          {t(`actionStatus.${action.status}`)}
        </motion.span>
      </div>
      {proposed ? (
        <div className={s.fields}>
          {fields.map((f) => (
            <label key={f}>
              <span>{t(`field.${f}`)}</span>
              {f === 'body' ? (
                <textarea
                  value={String(payload[f] ?? '')}
                  rows={3}
                  onChange={(e) => setPayload((p) => ({ ...p, [f]: e.target.value }))}
                />
              ) : f === 'priority' ? (
                <select
                  value={String(payload[f] ?? 'MEDIUM')}
                  onChange={(e) => setPayload((p) => ({ ...p, [f]: e.target.value }))}
                >
                  {['LOW', 'MEDIUM', 'HIGH', 'URGENT'].map((x) => (
                    <option key={x} value={x}>
                      {t(`priority.${x}`)}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={
                    f === 'date' || f === 'due_date'
                      ? 'date'
                      : f === 'start' || f === 'end'
                        ? 'time'
                        : 'text'
                  }
                  value={String(payload[f] ?? '')}
                  onChange={(e) => setPayload((p) => ({ ...p, [f]: e.target.value || null }))}
                />
              )}
            </label>
          ))}
        </div>
      ) : (
        <p className={s.cardSummary}>{String(payload.title ?? payload.body ?? '')}</p>
      )}
      {readonly.length ? (
        <p className={s.cardMeta}>
          {readonly
            .map(
              ([k, v]) =>
                `${t(`field.${k}`, { defaultValue: k })}: ${Array.isArray(v) ? v.join(', ') : k === 'time_type' ? tsch(`timeType.${String(v)}`) : String(v)}`,
            )
            .join(' · ')}
        </p>
      ) : null}
      {action.assumptions.length ? (
        <ul className={s.assumptions} aria-label={t('assumptions')}>
          {action.assumptions.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      ) : null}
      {action.preview.conflicts?.length ? (
        <p className={s.conflict}>
          {t('conflicts', { list: action.preview.conflicts.map((c) => c.title).join(', ') })}
        </p>
      ) : null}
      {action.error ? <p className={s.error}>{action.error.detail}</p> : null}
      <div className={s.row}>
        {proposed ? (
          <>
            <Button
              size="sm"
              icon={<Check size={14} />}
              loading={confirm.isPending}
              onClick={() => confirm.mutate()}
            >
              {t('confirm')}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              icon={<X size={14} />}
              loading={reject.isPending}
              onClick={() => reject.mutate()}
            >
              {t('reject')}
            </Button>
          </>
        ) : null}
        {action.status === 'EXECUTED' && link ? (
          <Link to={link} className={s.open}>
            {t('open')}
          </Link>
        ) : null}
        {action.status === 'EXECUTED' &&
        action.action_type !== 'CREATE_SUBTASKS' &&
        action.action_type !== 'RESCHEDULE_EVENT' ? (
          <Button
            size="sm"
            variant="ghost"
            icon={<Undo2 size={14} />}
            loading={revert.isPending}
            onClick={() => revert.mutate()}
          >
            {t('revert')}
          </Button>
        ) : null}
      </div>
      {error ? <Alert>{errorMessage(error)}</Alert> : null}
    </div>
  );
}
