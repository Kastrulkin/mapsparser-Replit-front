import { BarChart3, CalendarClock, ChevronRight, DatabaseZap } from 'lucide-react';

export type DataHealth = {
  status?: 'fresh' | 'due' | 'stale' | 'missing' | string;
  source?: string;
  source_updated_at?: string | null;
  age_days?: number | null;
  record_count?: number;
};

export type GrowthLoop = {
  mission_id?: string;
  status?: string;
  data_health_status?: string;
  analytics_level?: { level?: string; label?: string; next_unlock?: string | null };
  rhythm?: { active_weeks?: number; status?: string; label?: string };
};

type GrowthLoopPanelProps = {
  growthLoop?: GrowthLoop | null;
  dataHealth?: DataHealth | null;
  analyticsLevel?: { level?: string; label?: string; next_unlock?: string | null } | null;
  rhythm?: { active_weeks?: number; status?: string; label?: string } | null;
  onOpenImport: () => void;
  showImportAction?: boolean;
};

const freshnessCopy = (health?: DataHealth | null) => {
  switch (health?.status) {
    case 'fresh': return { label: 'Данные свежие', detail: 'Аналитика опирается на последние загруженные данные.', tone: 'text-emerald-300' };
    case 'due': return { label: 'Скоро обновить данные', detail: 'Новая загрузка поможет сохранить актуальную картину.', tone: 'text-amber-300' };
    case 'stale': return { label: 'Данные устарели', detail: 'Загрузите свежую сводку, чтобы решения не опирались на прошлый период.', tone: 'text-amber-300' };
    default: return { label: 'Данных пока нет', detail: 'Загрузите первую финансовую сводку, чтобы открыть аналитику.', tone: 'text-zinc-300' };
  }
};

const sourceLabel = (value?: string) => {
  const normalized = `${value || ''}`.trim().toLowerCase();
  if (normalized.includes('yclients')) return 'YCLIENTS';
  if (normalized.includes('altegio')) return 'Altegio';
  if (normalized === 'manual') return 'ввод вручную';
  if (normalized === 'calculated') return 'расчёт ЛокалОС';
  if (normalized === 'import' || normalized === 'file') return 'загруженный файл';
  return value || 'источник ещё не указан';
};

export const GrowthLoopPanel = ({ growthLoop, dataHealth, analyticsLevel, rhythm: suppliedRhythm, onOpenImport, showImportAction = true }: GrowthLoopPanelProps) => {
  const analytics = analyticsLevel || growthLoop?.analytics_level || (dataHealth?.status === 'fresh' || dataHealth?.status === 'due'
    ? { label: 'Базовая аналитика', next_unlock: 'Регулярно добавляйте продажи и расходы, чтобы видеть больше точек роста.' }
    : { label: 'Нужны данные', next_unlock: 'Загрузите первую финансовую сводку, чтобы открыть аналитику.' });
  const rhythm = suppliedRhythm || growthLoop?.rhythm;
  if (!analytics && !rhythm && !dataHealth) return null;
  const freshness = freshnessCopy(dataHealth);
  const needsImport = dataHealth?.status === 'missing' || dataHealth?.status === 'stale' || !dataHealth;
  const unlock = analytics.next_unlock || (needsImport ? 'Загрузите первую финансовую сводку, чтобы открыть аналитику.' : 'Продолжайте регулярно добавлять данные — появятся новые точки роста.');

  return (
    <section className="mt-4 overflow-hidden rounded-[22px] bg-white/[0.035] shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
      <div className="p-4">
        <div className="flex items-center gap-2"><DatabaseZap className="h-4 w-4 text-primary" /><h2 className="text-balance text-sm font-semibold">Ритм роста</h2></div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="min-w-0 rounded-[14px] bg-black/20 p-3">
            <small className="flex items-center gap-1.5 text-[10px] text-zinc-600"><DatabaseZap className="h-3.5 w-3.5" />Свежесть</small>
            <b className={`mt-2 block text-pretty text-xs ${freshness.tone}`}>{freshness.label}</b>
            <small className="mt-1 block text-pretty text-[10px] leading-4 text-zinc-600">
              {dataHealth?.age_days !== null && dataHealth?.age_days !== undefined ? `${dataHealth.age_days} дн. с обновления` : freshness.detail}
              {dataHealth?.source ? ` · ${sourceLabel(dataHealth.source)}` : ''}
            </small>
          </div>
          <div className="min-w-0 rounded-[14px] bg-black/20 p-3">
            <small className="flex items-center gap-1.5 text-[10px] text-zinc-600"><CalendarClock className="h-3.5 w-3.5" />Ритм</small>
            <b className="mt-2 block text-pretty text-xs text-zinc-200">{rhythm?.label || 'Ритм ещё не начат'}</b>
            <small className="mt-1 block text-pretty text-[10px] leading-4 text-zinc-600">{rhythm?.active_weeks ? `${rhythm.active_weeks} нед. с данными за 8 недель` : 'Регулярные загрузки покажут динамику.'}</small>
          </div>
        </div>
        <div className="mt-3 rounded-[14px] bg-primary/[0.08] p-3">
          <small className="flex items-center gap-1.5 text-[10px] text-primary"><BarChart3 className="h-3.5 w-3.5" />Аналитика</small>
          <b className="mt-1 block text-xs text-zinc-200">{analytics?.label || 'Нужны данные'}</b>
          <p className="mt-1 text-pretty text-[10px] leading-4 text-zinc-500">{unlock}</p>
        </div>
        {needsImport && showImportAction ? <button type="button" onClick={onOpenImport} className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-white/[0.06] px-3 text-xs font-semibold text-zinc-100 shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-[background-color,transform] active:scale-[0.96]">Загрузить финансовую сводку<ChevronRight className="h-4 w-4" /></button> : null}
      </div>
    </section>
  );
};
