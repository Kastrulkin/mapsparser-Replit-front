import React from 'react';
import { ArrowRight, CheckCircle2, HelpCircle, ShieldCheck, Sparkles, Target } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { AuditDataScope, auditScopeLabel } from './auditDisplayUtils';

export const AuditScopeBadge: React.FC<{ scope?: AuditDataScope; label?: string; className?: string }> = ({
  scope,
  label,
  className,
}) => (
  <span className={cn('inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500', className)}>
    {label || auditScopeLabel(scope)}
  </span>
);

export const AuditMetricCard: React.FC<{
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  scope?: AuditDataScope;
  tone?: 'neutral' | 'good' | 'warning' | 'risk';
}> = ({ label, value, hint, scope, tone = 'neutral' }) => (
  <div
    className={cn(
      'rounded-2xl border bg-white p-4 shadow-sm',
      tone === 'good' && 'border-emerald-100 bg-emerald-50/40',
      tone === 'warning' && 'border-amber-100 bg-amber-50/45',
      tone === 'risk' && 'border-rose-100 bg-rose-50/45',
      tone === 'neutral' && 'border-slate-200',
    )}
  >
    <div className="flex items-start justify-between gap-3">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      {scope ? <AuditScopeBadge scope={scope} /> : null}
    </div>
    <div className="mt-2 text-2xl font-bold tracking-tight text-slate-950">{value}</div>
    {hint ? <div className="mt-2 text-sm leading-5 text-slate-600">{hint}</div> : null}
  </div>
);

export const AuditHero: React.FC<{
  eyebrow?: string;
  title: string;
  summary: string;
  score?: React.ReactNode;
  scoreLabel?: string;
  healthLabel?: string;
  findings?: string[];
  meta?: Array<{ label: string; value: React.ReactNode; scope?: AuditDataScope }>;
  primaryAction?: React.ReactNode;
  secondaryAction?: React.ReactNode;
}> = ({ eyebrow, title, summary, score, scoreLabel, healthLabel, findings = [], meta = [], primaryAction, secondaryAction }) => (
  <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
    <div className="grid gap-0 lg:grid-cols-[1.35fr_0.65fr]">
      <div className="p-6 md:p-8">
        {eyebrow ? <div className="text-xs font-bold uppercase tracking-[0.22em] text-orange-500">{eyebrow}</div> : null}
        <h1 className="mt-3 max-w-3xl text-3xl font-black tracking-tight text-slate-950 md:text-5xl">{title}</h1>
        <p className="mt-4 max-w-3xl text-base leading-7 text-slate-650 md:text-lg">{summary}</p>
        {findings.length > 0 ? (
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {findings.slice(0, 3).map((item, index) => (
              <div key={`${item}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-white text-sm font-bold text-slate-950 shadow-sm">{index + 1}</div>
                <div className="text-sm leading-5 text-slate-700">{item}</div>
              </div>
            ))}
          </div>
        ) : null}
        {(primaryAction || secondaryAction) ? (
          <div className="mt-7 flex flex-wrap gap-3">
            {primaryAction}
            {secondaryAction}
          </div>
        ) : null}
      </div>
      <div className="border-t border-slate-200 bg-slate-950 p-6 text-white lg:border-l lg:border-t-0 md:p-8">
        <div className="text-xs font-bold uppercase tracking-[0.22em] text-slate-400">Итог</div>
        <div className="mt-4 flex items-end gap-2">
          <div className="text-5xl font-black tracking-tight">{score || '—'}</div>
          {score ? <div className="pb-2 text-lg font-semibold text-slate-400">/100</div> : null}
        </div>
        {healthLabel ? <div className="mt-3 inline-flex rounded-full bg-white/10 px-3 py-1 text-sm font-semibold text-white">{healthLabel}</div> : null}
        {scoreLabel ? <p className="mt-4 text-sm leading-6 text-slate-300">{scoreLabel}</p> : null}
        {meta.length > 0 ? (
          <div className="mt-6 space-y-3 border-t border-white/10 pt-5">
            {meta.map((item) => (
              <div key={item.label}>
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{item.label}</div>
                <div className="mt-1 text-sm font-semibold text-white">{item.value}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  </section>
);

export const AuditHowToRead: React.FC<{ title?: string; items: Array<{ title: string; description: string }> }> = ({
  title = 'Как читать этот аудит',
  items,
}) => (
  <section className="rounded-3xl border border-slate-200 bg-white/85 p-5 shadow-sm">
    <div className="flex items-center gap-2 text-sm font-bold text-slate-950">
      <HelpCircle className="h-4 w-4 text-slate-500" />
      {title}
    </div>
    <div className="mt-4 grid gap-3 md:grid-cols-3">
      {items.map((item) => (
        <div key={item.title} className="rounded-2xl bg-slate-50 p-4">
          <div className="text-sm font-semibold text-slate-950">{item.title}</div>
          <div className="mt-1 text-sm leading-5 text-slate-600">{item.description}</div>
        </div>
      ))}
    </div>
  </section>
);

export const AuditProblemBlock: React.FC<{
  title: string;
  priority?: string;
  problem: string;
  meaning: string;
  action: string;
  outcome: string;
  evidence?: string;
}> = ({ title, priority, problem, meaning, action, outcome, evidence }) => (
  <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-center gap-2 text-base font-bold text-slate-950">
        <Target className="h-4 w-4 text-orange-500" />
        {title}
      </div>
      {priority ? <span className="rounded-full bg-orange-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-orange-700">{priority}</span> : null}
    </div>
    <div className="mt-4 grid gap-3 md:grid-cols-2">
      <div className="rounded-2xl bg-slate-50 p-4">
        <div className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">Проблема</div>
        <div className="mt-2 text-sm leading-6 text-slate-700">{problem}</div>
        {evidence ? <div className="mt-3 text-xs leading-5 text-slate-500">Факт: {evidence}</div> : null}
      </div>
      <div className="rounded-2xl bg-amber-50/70 p-4">
        <div className="text-xs font-bold uppercase tracking-[0.18em] text-amber-700">Что это значит для бизнеса</div>
        <div className="mt-2 text-sm leading-6 text-slate-700">{meaning}</div>
      </div>
      <div className="rounded-2xl bg-emerald-50/70 p-4">
        <div className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">Что делать</div>
        <div className="mt-2 text-sm leading-6 text-slate-700">{action}</div>
      </div>
      <div className="rounded-2xl bg-sky-50/75 p-4">
        <div className="text-xs font-bold uppercase tracking-[0.18em] text-sky-700">Как понять, что стало лучше</div>
        <div className="mt-2 text-sm leading-6 text-slate-700">{outcome}</div>
      </div>
    </div>
  </article>
);

export const AuditCtaPanel: React.FC<{
  title: string;
  description: string;
  bullets?: string[];
  primaryLabel?: string;
  secondaryLabel?: string;
  onPrimary?: () => void;
  secondaryHref?: string;
}> = ({ title, description, bullets = [], primaryLabel, secondaryLabel, onPrimary, secondaryHref }) => (
  <section className="rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm md:p-8">
    <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
      <div>
        <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-[0.2em] text-orange-300">
          <Sparkles className="h-4 w-4" />
          Следующий шаг
        </div>
        <h2 className="mt-3 text-2xl font-black tracking-tight md:text-3xl">{title}</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300 md:text-base">{description}</p>
        {bullets.length > 0 ? (
          <div className="mt-5 grid gap-2 md:grid-cols-3">
            {bullets.slice(0, 3).map((item) => (
              <div key={item} className="flex items-start gap-2 text-sm text-slate-200">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                <span>{item}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      {(primaryLabel || secondaryLabel) ? (
        <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
          {primaryLabel ? (
            <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={onPrimary}>
              {primaryLabel}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          ) : null}
          {secondaryLabel && secondaryHref ? (
            <a href={secondaryHref}>
              <Button variant="outline" className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white">
                {secondaryLabel}
              </Button>
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  </section>
);
