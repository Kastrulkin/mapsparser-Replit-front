import { useId, type MouseEventHandler, type ReactNode, type RefObject } from 'react';
import { Sparkles, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import './CardServiceList.css';

type ServiceStatus = { label: string; className: string };

export function CardServiceWorkspace({ queue, detail }: { queue: ReactNode; detail?: ReactNode }) {
  return <div className="w-full [container-type:inline-size]">
    <div className={cn(detail && 'card-service-columns')}>
      <div className={cn('min-w-0', detail && 'card-service-queue bg-slate-50/70')}>{queue}</div>
      {detail && <div className="card-service-detail min-w-0 bg-white p-3">{detail}</div>}
    </div>
  </div>;
}

export function CardServiceList({ heading, description, count, children }: {
  heading?: string;
  description?: string;
  count: number;
  children: ReactNode;
}) {
  return <>
    {heading && <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
      <div>
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{heading}</div>
        {description && <div className="mt-1 text-sm text-slate-500">{description}</div>}
      </div>
      <div className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{count}</div>
    </div>}
    <div className="space-y-2 p-2">{children}</div>
  </>;
}

export function CardServiceRow({ title, status, subtitle, footer, selected, dimmed, controls, onClick, buttonRef }: {
  title: string;
  status: ServiceStatus;
  subtitle?: ReactNode;
  footer?: ReactNode;
  selected?: boolean;
  dimmed?: boolean;
  controls?: string;
  onClick: MouseEventHandler<HTMLButtonElement>;
  buttonRef?: RefObject<HTMLButtonElement | null>;
}) {
  return <button
    type="button"
    ref={buttonRef}
    aria-pressed={selected}
    aria-controls={controls}
    onClick={onClick}
    className={cn(
      'w-full rounded-2xl border px-4 py-3 text-left transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
      selected
        ? 'border-slate-300 bg-slate-950 text-white shadow-md ring-2 ring-slate-950/10'
        : 'border-slate-100 bg-white text-slate-900 hover:border-slate-200 hover:bg-slate-50',
      dimmed && 'opacity-55 blur-[0.35px] hover:opacity-90 hover:blur-0',
    )}
  >
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className={cn('text-sm font-semibold', controls ? 'break-words' : 'truncate', selected ? 'text-white' : 'text-slate-950')}>{title}</div>
        {subtitle && <div className={cn('mt-1 flex flex-wrap items-center gap-1.5 text-xs', selected ? 'text-slate-300' : 'text-slate-500')}>{subtitle}</div>}
      </div>
      <span className={cn('shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold', status.className)}>{status.label}</span>
    </div>
    {footer && <div className={cn('mt-3 flex items-center justify-between gap-2 text-xs', selected ? 'text-slate-300' : 'text-slate-500')}>{footer}</div>}
  </button>;
}

export function CardServiceDetail({ id, focusRef, title, status, badges, metadata, description,
  descriptionLabel = 'Текущее описание', keywords, actions, onClose, children }: {
  id?: string;
  focusRef?: RefObject<HTMLElement | null>;
  title: string;
  status: ServiceStatus;
  badges?: ReactNode;
  metadata?: ReactNode;
  description?: string;
  descriptionLabel?: string;
  keywords?: string[];
  actions?: ReactNode;
  onClose: () => void;
  children?: ReactNode;
}) {
  const titleId = useId();
  return <section id={id} ref={focusRef} tabIndex={focusRef ? -1 : undefined} aria-labelledby={titleId}
    className="space-y-4 rounded-[1.75rem] border border-slate-200/90 bg-white p-4 shadow-[0_24px_70px_rgba(15,23,42,0.10)] ring-1 ring-white focus:outline-none">
    <div className={cn('space-y-3', children && 'border-b border-slate-100 pb-4')}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
            <span className={cn('rounded-full border px-2 py-0.5 text-[11px] font-semibold', status.className)}>{status.label}</span>
            {badges}
          </div>
          <h3 id={titleId} className="max-w-4xl break-words text-xl font-semibold leading-tight tracking-tight text-slate-950">{title}</h3>
          {metadata && <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">{metadata}</div>}
        </div>
        <Button type="button" variant="ghost" onClick={onClose} aria-label="Закрыть карточку услуги"
          className="shrink-0 text-slate-400 hover:bg-slate-100 hover:text-slate-900">
          <X className="h-4 w-4" />
        </Button>
      </div>
      {(description || keywords) && <div className="space-y-3 rounded-2xl bg-slate-50/80 px-3 py-3 ring-1 ring-slate-100">
        {description && <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{descriptionLabel}</div>
          <p className="mt-1 max-h-56 overflow-y-auto whitespace-pre-line break-words pr-1 text-sm leading-6 text-slate-700">{description}</p>
        </div>}
        {keywords && <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">SEO-запросы</div>
          <div className="mt-1 flex flex-wrap gap-1">
            {keywords.slice(0, 3).map(keyword => <span key={keyword} title={keyword}
              className="max-w-[13rem] truncate rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">{keyword}</span>)}
            {keywords.length > 3 && <span title={keywords.slice(3).join(', ')} className="rounded-full border bg-white px-2 py-0.5 text-[11px] text-slate-500">+{keywords.length - 3}</span>}
            {!keywords.length && <span className="text-xs text-slate-500">ещё не подобраны</span>}
          </div>
        </div>}
      </div>}
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
    {children}
  </section>;
}

export function CardServiceDraft({ title, children }: { title: string; children: ReactNode }) {
  return <div className="rounded-2xl border border-slate-200 bg-white p-3">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
      <Sparkles className="h-3.5 w-3.5" />
      {title}
    </div>
    {children}
  </div>;
}
