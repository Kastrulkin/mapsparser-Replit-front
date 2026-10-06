import { AlertCircle, BadgeCheck, Coins, Loader2, Mail, MessageSquare, Search, Send, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';

export type GroupAction = { kind: 'link' | 'control' | 'draft_resume'; label: string; href?: string; action?: string; job_id?: string };
export type GroupPresentation = {
  phase: 'companies' | 'letters' | 'sending' | 'replies';
  status: string; label: string; reason?: string | null; active: boolean;
  next_action: GroupAction; send_mode?: string;
  metrics: { found: number; eligible: number; target?: number | null; needs_decision: number; awaiting_check?: number; prepared: number; queued: number; sent: number; replies: number };
  expenses: { charged?: number | null; estimate?: number | null; estimate_only?: boolean };
};

export function OutreachGroupCard({ name, presentation, busy, onAction }: {
  name: string; presentation?: GroupPresentation; busy?: boolean; onAction?: (action: GroupAction) => void;
}) {
  if (!presentation) return <div role="status"><strong>{name}</strong><p className="text-sm text-muted-foreground">Обновляем состояние группы…</p></div>;
  const p = presentation;
  const phases = [{ id: 'companies', label: 'Компании', Icon: Users }, { id: 'letters', label: 'Письма', Icon: Mail }, { id: 'sending', label: 'Отправка', Icon: Send }, { id: 'replies', label: 'Ответы', Icon: MessageSquare }];
  const counters = p.phase === 'companies'
    ? [{ label: 'Найдено кандидатов', value: p.metrics.found, Icon: Search }, { label: 'Подтверждены · цель', value: p.metrics.target == null ? String(p.metrics.eligible) : `${p.metrics.eligible} / ${p.metrics.target}`, Icon: BadgeCheck }, { label: 'Нужно решение', value: p.metrics.needs_decision, Icon: AlertCircle }]
    : [{ label: 'Письма готовы', value: p.metrics.prepared, Icon: Mail }, { label: 'Отправлено', value: p.metrics.sent, Icon: Send }, { label: 'Ответы', value: p.metrics.replies, Icon: MessageSquare }];
  return <div className="space-y-3">
    <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="font-semibold">{name}</h3><span role="status" aria-live="polite" className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm">{p.active && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}{p.label}</span></div>
    <ol className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4" aria-label="Этапы аутрича">{phases.map(({ id, label, Icon }) => <li key={id} aria-current={id === p.phase ? 'step' : undefined} className={id === p.phase ? 'flex items-center gap-2 rounded-md bg-muted px-2 py-2 font-semibold' : 'flex items-center gap-2 px-2 py-2 text-muted-foreground'}><Icon className="h-4 w-4" aria-hidden="true" />{label}</li>)}</ol>
    <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">{counters.map(({ label, value, Icon }) => <div key={label} className="flex items-center gap-3"><Icon className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" /><div><dt className="text-xs text-muted-foreground">{label}</dt><dd className="text-xl font-semibold tabular-nums">{value}</dd></div></div>)}</dl>
    {p.phase === 'companies' && !!p.metrics.awaiting_check && <p className="text-sm text-muted-foreground">Компания и контакт ещё не проверены: {p.metrics.awaiting_check}.</p>}
    {p.reason && <p className="flex items-start gap-2 text-sm" role="note"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{p.reason}</p>}
    {p.phase === 'sending' && <p className="text-sm text-muted-foreground">{p.send_mode === 'automatic_authorized' ? 'Автоматическая отправка по согласованным правилам' : 'Отправка после проверки и подтверждения'} · В очереди: {p.metrics.queued}</p>}
    <p className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground"><Coins className="h-4 w-4" aria-hidden="true" /><span>Списано: {p.expenses.charged == null ? 'уточняется' : `${p.expenses.charged} кр.`}</span>{p.expenses.estimate != null && <span>· {p.expenses.estimate_only ? 'оценка до' : 'лимит'} {p.expenses.estimate} кр.</span>}</p>
    {p.next_action.kind === 'link' && p.next_action.href ? <Button asChild><a href={p.next_action.href}>{p.next_action.label}</a></Button> : onAction && <Button disabled={busy} onClick={() => onAction(p.next_action)}>{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}{p.next_action.label}</Button>}
  </div>;
}
