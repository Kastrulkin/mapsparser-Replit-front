import { AlertCircle, BadgeCheck, Coins, Loader2, Mail, MessageSquare, Search, Send, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';

export type GroupAction = { kind: 'link' | 'control' | 'draft_resume'; label: string; href?: string; action?: string; job_id?: string };
export type GroupPresentation = {
  phase: 'companies' | 'letters' | 'sending' | 'replies';
  status: string; label: string; reason?: string | null; active: boolean;
  next_action: GroupAction; send_mode?: string; updated_at?: string;
  achievements?: { id: string; label: string; count: number }[];
  substeps?: { id: string; label: string; status: string; processed: number; remaining?: number; total?: number; detail?: string }[];
  reply_sync?: { configured: boolean; needs_attention: boolean; last_checked_at?: string | null };
  metrics: { found: number; eligible: number; target?: number | null; needs_decision: number; awaiting_check?: number; prepared: number; queued: number; sent: number; replies: number };
  expenses: { charged?: number | null; estimate?: number | null; estimate_only?: boolean };
};

export function OutreachGroupCard({ name, presentation, busy, onAction, compact = false }: {
  name: string; presentation?: GroupPresentation; busy?: boolean; onAction?: (action: GroupAction) => void; compact?: boolean;
}) {
  if (!presentation) return <div role="status"><strong>{name}</strong><p className="text-sm text-muted-foreground">Обновляем состояние группы…</p></div>;
  const p = presentation;
  const phases = [{ id: 'companies', label: 'Компании', Icon: Users }, { id: 'letters', label: 'Письма', Icon: Mail }, { id: 'sending', label: 'Отправка', Icon: Send }, { id: 'replies', label: 'Ответы', Icon: MessageSquare }];
  const currentStep = p.phase === "companies" && p.status === "running" ? p.substeps?.find(step => step.status === "running") : undefined;
  const counters = p.phase === 'companies'
    ? [{ label: compact ? 'Найдено' : 'Найдено кандидатов', value: p.metrics.found, Icon: Search }, { label: compact ? 'Подходят · цель' : 'Подтверждены · цель', value: p.metrics.target == null ? String(p.metrics.eligible) : `${p.metrics.eligible} / ${p.metrics.target}`, Icon: BadgeCheck }, { label: 'Нужно решение', value: p.metrics.needs_decision, Icon: AlertCircle }]
    : [{ label: 'Письма готовы', value: p.metrics.prepared, Icon: Mail }, { label: 'Отправлено', value: p.metrics.sent, Icon: Send }, { label: 'Ответы', value: p.metrics.replies, Icon: MessageSquare }];
  return <div className="space-y-3">
    <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="font-semibold">{name}</h3><span role="status" aria-live="polite" className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm">{p.active && p.status === 'running' && <Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" />}{p.label}</span></div>
    {!compact && <ol className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4" aria-label="Этапы аутрича">{phases.map(({ id, label, Icon }) => <li key={id} aria-current={id === p.phase ? 'step' : undefined} className={id === p.phase ? 'flex items-center gap-2 rounded-md bg-muted px-2 py-2 font-semibold' : 'flex items-center gap-2 px-2 py-2 text-muted-foreground'}><Icon className="h-4 w-4" aria-hidden="true" />{label}</li>)}</ol>}
    {currentStep && <div className="rounded-md border-l-2 border-primary bg-muted/50 px-3 py-2" role="status" aria-live="polite"><p className="flex items-center gap-2 text-sm font-medium"><Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" />{currentStep.label}</p><p className="mt-1 text-xs text-muted-foreground">{currentStep.detail || 'Работа выполняется'}{currentStep.total ? ` · ${currentStep.processed} из ${currentStep.total}` : ''}</p></div>}
    {!compact && !!p.substeps?.length && p.phase === 'companies' && <details><summary className="cursor-pointer text-sm text-muted-foreground">Поиск, контакты и проверка</summary><ol aria-label="Работа с компаниями" className="grid gap-2 sm:grid-cols-3">{p.substeps.map(step => <li key={step.id} className={step.status === "running" ? "rounded-md border border-primary/40 bg-muted/50 p-3 motion-safe:animate-in motion-safe:fade-in" : "rounded-md border p-3"}>
      <div className="flex items-center gap-2 text-sm font-medium">{step.status === 'running' ? <Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" /> : step.status === 'completed' ? <BadgeCheck className="h-4 w-4" aria-hidden="true" /> : <Search className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}{step.label}</div>
      <p className="mt-1 text-xs text-muted-foreground">{step.status === 'running' ? 'Выполняется' : step.status === 'completed' ? 'Завершено' : step.status === 'queued' ? 'Ожидает запуска' : step.status === 'paused' ? 'На паузе' : 'Ещё не начато'}{step.total ? ` · ${step.processed} из ${step.total}` : step.processed ? ` · ${step.processed}` : ''}</p>
      {step.detail && <p className="mt-1 text-xs text-muted-foreground">{step.detail}</p>}
    </li>)}</ol></details>}
    <dl className={compact ? "grid grid-cols-3 gap-3" : "grid grid-cols-1 gap-3 sm:grid-cols-3"}>{counters.map(({ label, value, Icon }) => <div key={label} className={compact ? "flex flex-col items-start gap-1 sm:flex-row sm:items-center sm:gap-3" : "flex items-center gap-3"}><Icon className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" /><div><dt className="text-xs text-muted-foreground">{label}</dt><dd key={value} className="text-xl font-semibold tabular-nums motion-safe:animate-in motion-safe:fade-in">{value}</dd></div></div>)}</dl>
    {!compact && !!p.achievements?.length && <ul aria-label="Результаты работы" className="space-y-1.5 border-t pt-3">{p.achievements.map(item => <li key={item.id} className="flex items-center gap-2 text-sm"><BadgeCheck className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" /><span>{item.label}</span><strong key={item.count} className="ml-auto font-medium tabular-nums motion-safe:animate-in motion-safe:fade-in">{item.count}</strong></li>)}</ul>}
    {!compact && p.phase === 'companies' && !!p.metrics.awaiting_check && <p className="text-sm text-muted-foreground">Компания и контакт ещё не проверены: {p.metrics.awaiting_check}.</p>}
    {compact && <details><summary className="min-h-10 cursor-pointer py-2 text-sm text-muted-foreground">Подробности работы</summary><div className="space-y-2 py-2 text-sm text-muted-foreground">
      {p.substeps?.map(step => <p key={step.id}>{step.label}: {step.status === 'completed' ? 'завершено' : step.status === 'running' ? 'выполняется' : step.status === 'queued' ? 'ожидает запуска' : step.status === 'paused' ? 'на паузе' : 'ещё не начато'} · {step.processed}{step.total ? ` из ${step.total}` : ''}{step.detail ? ` · ${step.detail}` : ''}</p>)}
      {p.achievements?.map(item => <p key={item.id}>{item.label}: {item.count}</p>)}
      {p.updated_at && <p>Обновлено: {new Date(p.updated_at).toLocaleTimeString()}</p>}
    </div></details>}
    {p.reason && <p className="flex items-start gap-2 text-sm" role="note"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{p.reason}</p>}
    {p.phase === 'sending' && <p className="text-sm text-muted-foreground">{p.send_mode === 'automatic_authorized' ? 'Автоматическая отправка по согласованным правилам' : 'Отправка после проверки и подтверждения'} · В очереди: {p.metrics.queued}</p>}
    <p className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground"><Coins className="h-4 w-4" aria-hidden="true" /><span>Списано: {p.expenses.charged == null ? 'уточняется' : `${p.expenses.charged} кр.`}</span>{p.expenses.estimate != null && <span>· {p.expenses.estimate_only ? 'оценка до' : 'лимит'} {p.expenses.estimate} кр.</span>}</p>
    {p.reply_sync && (p.phase === 'sending' || p.phase === 'replies') && <p className="text-xs text-muted-foreground" role="status">{!p.reply_sync.configured ? 'Проверка ответов не подключена' : p.reply_sync.needs_attention ? 'Проверка ответов требует внимания' : 'Ответы проверяются автоматически'}{p.reply_sync.last_checked_at && ` · Последняя проверка: ${new Date(p.reply_sync.last_checked_at).toLocaleString()}`}</p>}
    {!compact && p.updated_at && <p className="text-xs text-muted-foreground">Обновлено: {new Date(p.updated_at).toLocaleTimeString()}</p>}
    {p.next_action.kind === 'link' && p.next_action.href ? <Button asChild><a href={p.next_action.href}>{p.next_action.label}</a></Button> : onAction && <Button disabled={busy} onClick={() => onAction(p.next_action)}>{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}{p.next_action.label}</Button>}
  </div>;
}
