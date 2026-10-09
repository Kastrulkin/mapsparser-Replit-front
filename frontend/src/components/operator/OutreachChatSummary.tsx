import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { GroupPresentation } from '@/components/prospecting/OutreachGroupCard';

export function OutreachChatSummary({ name, presentation, onContinue, onDetails, onChange }: {
  name: string;
  presentation?: GroupPresentation;
  onContinue: (command: string) => void;
  onDetails?: () => void;
  onChange?: () => void;
}) {
  if (!presentation) return <p role="status">Обновляем результат поиска…</p>;
  const p = presentation;
  const step = p.substeps?.find(item => item.status === 'running');
  const action = p.next_action;
  const command = action.action === 'pause' ? 'Приостанови этот поиск.'
    : action.kind === 'draft_resume' ? 'Продолжи подготовку писем для этого поиска. Не отправляй письма.'
    : p.status === 'needs_attention' ? 'Покажи причину остановки этого поиска и предложи изменение условий. Ничего не запускай без подтверждения.'
    : p.metrics.eligible > 0 && p.metrics.prepared === 0 && !p.active ? 'Подготовь условия создания индивидуальных писем для подходящих компаний этого поиска. Не отправляй письма.'
    : 'Покажи условия продолжения этого поиска. Ничего не запускай без подтверждения.';
  const label = p.status === 'needs_attention' && action.kind !== 'link' ? 'Разобрать причину'
    : p.metrics.eligible > 0 && p.metrics.prepared === 0 && !p.active && action.kind !== 'link' ? 'Подготовить письма' : action.label;
  return <section className="min-w-0 space-y-2 text-sm" aria-label={`Текущая задача: ${name}`}>
    <div className="flex min-w-0 items-center justify-between gap-2">
      <h2 title={name} className="min-w-0 truncate font-semibold">{name}</h2>
      {onChange && <Button size="sm" variant="ghost" onClick={onChange}>Сменить</Button>}
    </div>
    <p role="status" className="flex items-center gap-2 font-medium">
      {p.active && <Loader2 className="h-4 w-4 shrink-0 motion-safe:animate-spin" aria-hidden="true" />}
      <span>{step ? `${step.label}${step.total ? ` · ${step.processed} из ${step.total}` : ''}` : p.label}</span>
    </p>
    {p.reason && !p.active && <p className="line-clamp-2 text-xs text-muted-foreground" title={p.reason}>{p.reason}</p>}
    <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <div className="flex gap-1"><dt>Найдено</dt><dd className="font-semibold tabular-nums text-foreground">{p.metrics.found}</dd></div>
      <div className="flex gap-1"><dt>Подходят</dt><dd className="font-semibold tabular-nums text-foreground">{p.metrics.eligible}{p.metrics.target == null ? '' : ` / ${p.metrics.target}`}</dd></div>
      <div className="flex gap-1"><dt>Письма</dt><dd className="font-semibold tabular-nums text-foreground">{p.metrics.prepared}</dd></div>
      <div className="flex gap-1"><dt>Списано</dt><dd className="tabular-nums">{p.expenses.charged == null ? 'уточняется' : `${p.expenses.charged} кр.`}</dd></div>
    </dl>
    <div className="flex flex-wrap items-center gap-2">
      {action.kind === 'link' && action.href ? <Button size="sm" variant="outline" asChild><a href={action.href}>{action.label}</a></Button>
        : <Button size="sm" variant="outline" onClick={() => onContinue(command)}>{label}</Button>}
      {onDetails && <Button size="sm" variant="ghost" onClick={onDetails}>Подробнее</Button>}
    </div>
  </section>;
}

