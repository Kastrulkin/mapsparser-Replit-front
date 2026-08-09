import { ArrowRight, CheckCircle2, Clock3, DatabaseZap, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export type GrowthDataHealth = {
  status?: string;
  state?: string;
  freshness?: string;
  source?: string;
  source_label?: string;
  source_updated_at?: string | null;
  updated_at?: string | null;
  last_updated_at?: string | null;
  age_days?: number | null;
  record_count?: number;
  next_due_at?: string | null;
  missing?: string[];
  reason?: string;
  is_stale?: boolean;
  stale?: boolean;
};

type DataHealthRhythmStripProps = {
  dataHealth?: GrowthDataHealth | null;
  onImport: () => void;
  compact?: boolean;
  showImportAction?: boolean;
};

const dateLabel = (value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date);
};

const sourceLabel = (value?: string) => {
  const normalized = `${value || ''}`.trim().toLowerCase();
  if (normalized.includes('yclients')) return 'YCLIENTS';
  if (normalized.includes('altegio')) return 'Altegio';
  if (normalized === 'manual') return 'ввод вручную';
  if (normalized === 'calculated') return 'расчёт ЛокалОС';
  if (normalized === 'import' || normalized === 'file') return 'загруженный файл';
  return value || 'не указан';
};

const needsImport = (dataHealth: GrowthDataHealth) => {
  const state = `${dataHealth.status || ''} ${dataHealth.state || ''} ${dataHealth.freshness || ''}`.toLowerCase();
  return Boolean(dataHealth.stale || dataHealth.is_stale || dataHealth.missing?.length || /missing|stale|empty|unavailable|attention/.test(state));
};

export const DataHealthRhythmStrip = ({ dataHealth, onImport, compact = false, showImportAction = true }: DataHealthRhythmStripProps) => {
  if (!dataHealth) return null;
  const importNeeded = needsImport(dataHealth);
  const updatedAt = dateLabel(dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at);
  const source = dataHealth.source_label || sourceLabel(dataHealth.source);
  const missing = dataHealth.missing?.filter(Boolean) || [];
  const Icon = importNeeded ? TriangleAlert : CheckCircle2;

  return (
    <section className={cn(
      'flex flex-col gap-3 rounded-2xl bg-slate-50 px-4 py-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)] sm:flex-row sm:items-center sm:justify-between',
      compact ? 'text-sm' : 'text-sm',
    )} aria-label="Свежесть данных и ритм анализа">
      <div className="flex min-w-0 items-start gap-3">
        <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl', importNeeded ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-700')}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-semibold text-slate-950">{importNeeded ? 'Данные требуют обновления' : 'Данные готовы к анализу'}</span>
            <span className="inline-flex items-center gap-1 text-xs text-slate-500"><DatabaseZap className="h-3.5 w-3.5" />Источник: {source}</span>
            {updatedAt ? <span className="inline-flex items-center gap-1 text-xs tabular-nums text-slate-500"><Clock3 className="h-3.5 w-3.5" />{updatedAt}</span> : null}
          </div>
          <p className="mt-1 text-pretty leading-5 text-slate-600">
            {importNeeded
              ? (dataHealth.reason || (missing.length ? `Для полного отчёта добавьте: ${missing.join(', ')}.` : 'Загрузите свежую выгрузку, чтобы открыть актуальную аналитику.'))
              : 'Показатели обновляются из подтверждённого источника. Следующий шаг — проверить выводы за период.'}
          </p>
        </div>
      </div>
      {importNeeded && showImportAction ? (
        <Button type="button" onClick={onImport} className="min-h-11 shrink-0 gap-2 transition-transform active:scale-[0.96]">
          Загрузить файл YCLIENTS
          <ArrowRight className="h-4 w-4" />
        </Button>
      ) : null}
    </section>
  );
};
