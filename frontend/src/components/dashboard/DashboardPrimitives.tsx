import React from 'react';
import { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/utils';

type DashboardPageHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  icon?: LucideIcon;
  actions?: React.ReactNode;
  className?: string;
};

export const DashboardPageHeader: React.FC<DashboardPageHeaderProps> = ({
  eyebrow,
  title,
  description,
  icon: Icon,
  actions,
  className,
}) => (
  <div className={cn("flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between", className)}>
    <div className="min-w-0 space-y-3">
      {eyebrow ? (
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          {eyebrow}
        </div>
      ) : null}
      <div className="flex items-start gap-4">
        {Icon ? (
          <div className="mt-1 flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-sm ring-1 ring-slate-900/10">
            <Icon className="h-6 w-6" />
          </div>
        ) : null}
        <div className="min-w-0 space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
            {title}
          </h1>
          {description ? (
            <p className="max-w-3xl text-sm leading-7 text-slate-600 sm:text-base">
              {description}
            </p>
          ) : null}
        </div>
      </div>
    </div>
    {actions ? (
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {actions}
      </div>
    ) : null}
  </div>
);

type DashboardMetricItem = {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: 'default' | 'positive' | 'warning';
};

export const DashboardCompactMetricsRow: React.FC<{
  items: DashboardMetricItem[];
  className?: string;
}> = ({ items, className }) => (
  <div className={cn("grid gap-3 md:grid-cols-2 xl:grid-cols-4", className)}>
    {items.map((item) => (
      <div
        key={item.label}
        className={cn(
          "rounded-2xl border px-4 py-4 shadow-sm",
          item.tone === 'positive'
            ? "border-emerald-200/70 bg-emerald-50/80"
            : item.tone === 'warning'
              ? "border-amber-200/80 bg-amber-50/80"
              : "border-slate-200/80 bg-white/90"
        )}
      >
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          {item.label}
        </div>
        <div className="mt-2 text-xl font-semibold tracking-tight text-slate-950">
          {item.value}
        </div>
        {item.hint ? (
          <div className="mt-1 text-sm leading-6 text-slate-600">
            {item.hint}
          </div>
        ) : null}
      </div>
    ))}
  </div>
);

export const DashboardActionPanel: React.FC<{
  title: string;
  description?: React.ReactNode;
  status?: React.ReactNode;
  actions?: React.ReactNode;
  tone?: 'default' | 'sky' | 'amber' | 'indigo';
  className?: string;
}> = ({ title, description, status, actions, tone = 'default', className }) => {
  const toneClassName =
    tone === 'sky'
      ? "border-sky-200/80 bg-sky-50/85"
      : tone === 'amber'
        ? "border-amber-200/80 bg-amber-50/85"
        : tone === 'indigo'
          ? "border-indigo-200/80 bg-indigo-50/85"
          : "border-slate-200/80 bg-white/90";

  return (
    <div className={cn("rounded-3xl border p-5 shadow-sm sm:p-6", toneClassName, className)}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-2">
          <h2 className="text-lg font-semibold text-slate-950">
            {title}
          </h2>
          {description ? (
            <div className="max-w-3xl text-sm leading-7 text-slate-700">
              {description}
            </div>
          ) : null}
          {status ? (
            <div className="rounded-2xl bg-white/70 px-4 py-3 text-sm text-slate-700 ring-1 ring-black/5">
              {status}
            </div>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            {actions}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const DashboardSection: React.FC<{
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
}> = ({ title, description, actions, children, className, contentClassName }) => (
  <section className={cn("rounded-3xl border border-slate-200/80 bg-white/92 shadow-sm", className)}>
    {(title || description || actions) ? (
      <div className="flex flex-col gap-4 border-b border-slate-100 px-6 py-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          {title ? (
            <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          ) : null}
          {description ? (
            <p className="text-sm leading-6 text-slate-600">{description}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            {actions}
          </div>
        ) : null}
      </div>
    ) : null}
    <div className={cn("px-6 py-5", contentClassName)}>
      {children}
    </div>
  </section>
);

export const DashboardEmptyState: React.FC<{
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}> = ({ title, description, action, className }) => (
  <div className={cn("rounded-3xl border border-dashed border-slate-200 bg-slate-50/80 px-6 py-10 text-center", className)}>
    <div className="mx-auto max-w-xl space-y-3">
      <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      <p className="text-sm leading-7 text-slate-600">{description}</p>
      {action ? (
        <div className="pt-2">{action}</div>
      ) : null}
    </div>
  </div>
);
