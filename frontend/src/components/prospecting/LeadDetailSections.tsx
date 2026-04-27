import { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const toneClassMap: Record<string, string> = {
  default: 'border-slate-200 bg-white',
  muted: 'border-gray-200 bg-gray-50',
  info: 'border-sky-200 bg-sky-50',
  success: 'border-emerald-200 bg-emerald-50',
  warning: 'border-amber-200 bg-amber-50',
  danger: 'border-rose-200 bg-rose-50',
};

type LeadDetailSectionProps = {
  title: string;
  description?: string;
  tone?: 'default' | 'muted' | 'info' | 'success' | 'warning' | 'danger';
  children: ReactNode;
  className?: string;
};

export function LeadDetailSection({
  title,
  description,
  tone = 'default',
  children,
  className,
}: LeadDetailSectionProps) {
  return (
    <div className={cn('rounded-xl border p-4 space-y-3', toneClassMap[tone] || toneClassMap.default, className)}>
      <div>
        <div className="text-sm font-semibold text-foreground">{title}</div>
        {description ? <div className="mt-1 text-xs text-muted-foreground">{description}</div> : null}
      </div>
      {children}
    </div>
  );
}

type LeadDetailMetaItem = {
  label: string;
  value: ReactNode;
};

type LeadDetailMetaListProps = {
  items: LeadDetailMetaItem[];
  columns?: 1 | 2;
  className?: string;
};

export function LeadDetailMetaList({
  items,
  columns = 1,
  className,
}: LeadDetailMetaListProps) {
  const visibleItems = items.filter((item) => item.value !== null && item.value !== undefined && item.value !== '');
  if (visibleItems.length === 0) {
    return <div className="text-sm text-muted-foreground">Данных пока нет.</div>;
  }

  return (
    <div className={cn('grid gap-3', columns === 2 ? 'md:grid-cols-2' : 'grid-cols-1', className)}>
      {visibleItems.map((item) => (
        <div key={item.label} className="space-y-1">
          <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{item.label}</div>
          <div className="text-sm text-foreground break-words">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

type LeadDetailChipListProps = {
  items: string[];
  emptyText?: string;
  className?: string;
};

export function LeadDetailChipList({
  items,
  emptyText = 'Нет данных.',
  className,
}: LeadDetailChipListProps) {
  const normalizedItems = items
    .map((item) => String(item || '').trim())
    .filter(Boolean);
  if (normalizedItems.length === 0) {
    return <div className="text-sm text-muted-foreground">{emptyText}</div>;
  }

  return (
    <div className={cn('flex flex-wrap gap-1.5', className)}>
      {normalizedItems.map((item) => (
        <span
          key={item}
          className="inline-flex items-center rounded-full border border-gray-300 bg-white px-2 py-0.5 text-[11px] text-gray-700"
        >
          {item}
        </span>
      ))}
    </div>
  );
}
