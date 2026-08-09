import { AlertTriangle, BarChart3, Building2, CalendarClock, ChevronRight, DatabaseZap } from 'lucide-react';

export type AnalyticsLevel = { level?: string; label?: string; next_unlock?: string | null };
export type GrowthRhythm = { active_weeks?: number; status?: string; label?: string };

export type DataHealth = {
  status?: 'fresh' | 'due' | 'stale' | 'missing' | string;
  source?: string;
  source_updated_at?: string | null;
  age_days?: number | null;
  record_count?: number;
  coverage?: string[];
  missing?: string[];
};

export type LocationHealth = DataHealth & {
  business_id?: string;
  location_name?: string;
  analytics_level?: AnalyticsLevel | null;
  rhythm?: GrowthRhythm | null;
};

export type LocationSummary = { total?: number; fresh?: number; due?: number; stale?: number; missing?: number };

export type AnalyticsModule = {
  key?: string;
  label?: string;
  status?: 'ready' | 'available' | 'locked' | string;
  next_unlock?: string | null;
  ready_locations?: number;
  total_locations?: number;
};

export type LocationBreakdown = {
  business_id?: string;
  business_name?: string;
  data_health?: DataHealth | null;
  analytics_level?: AnalyticsLevel | null;
  rhythm?: GrowthRhythm | null;
  analytics_modules?: AnalyticsModule[];
};

export type ProblemLocation = {
  business_id?: string;
  business_name?: string;
  data_health_status?: string;
  problem_areas?: string[];
  target_scope?: { kind?: string; id?: string };
  focus_action?: { screen?: string; cta_url?: string } | null;
};

export type NetworkSummary = {
  locations_count?: number;
  problem_locations_count?: number;
  healthy_locations_count?: number;
  finance?: LocationSummary | null;
};

export type GrowthLoop = {
  mission_id?: string;
  status?: string;
  data_health_status?: string;
  analytics_level?: AnalyticsLevel;
  rhythm?: GrowthRhythm;
};

type GrowthLoopPanelProps = {
  growthLoop?: GrowthLoop | null;
  dataHealth?: DataHealth | null;
  analyticsLevel?: AnalyticsLevel | null;
  rhythm?: GrowthRhythm | null;
  scopeKind?: string;
  analyticsModules?: AnalyticsModule[];
  networkSummary?: NetworkSummary | null;
  problemLocations?: ProblemLocation[];
  locationBreakdown?: LocationBreakdown[];
  onOpenImport: () => void;
  onOpenLocation?: (businessId: string, screen: string) => void;
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

const locationStatus = (status?: string) => {
  if (status === 'stale') return { label: 'Устарели', tone: 'text-amber-300 bg-amber-400/10' };
  if (status === 'due') return { label: 'Скоро обновить', tone: 'text-amber-200 bg-amber-400/10' };
  if (status === 'fresh') return { label: 'Свежие', tone: 'text-emerald-300 bg-emerald-400/10' };
  return { label: 'Нет данных', tone: 'text-zinc-400 bg-white/[0.05]' };
};

const problemScreen = (problem: ProblemLocation) => {
  if (problem.focus_action?.screen) return problem.focus_action.screen;
  const url = `${problem.focus_action?.cta_url || ''}`;
  if (url.includes('/card') || url.includes('/profile')) return 'cards';
  if (url.includes('/content')) return 'content';
  if (url.includes('/partnership')) return 'partnerships';
  if (url.includes('/agent')) return 'agents';
  if (url.includes('/average-ticket')) return 'finance';
  if (url.includes('/finance')) return 'finance_import';
  const area = problem.problem_areas?.[0];
  if (area === 'maps') return 'cards';
  if (area === 'content') return 'content';
  if (area === 'partnerships') return 'partnerships';
  if (area === 'automation') return 'agents';
  if (area === 'upsells') return 'finance';
  return ['missing', 'stale', 'due'].includes(problem.data_health_status || '') ? 'finance_import' : 'tasks';
};

export const GrowthLoopPanel = ({ growthLoop, dataHealth, analyticsLevel, rhythm: suppliedRhythm, scopeKind, analyticsModules = [], networkSummary, problemLocations = [], locationBreakdown = [], onOpenImport, onOpenLocation, showImportAction = true }: GrowthLoopPanelProps) => {
  const analytics = analyticsLevel || growthLoop?.analytics_level || (dataHealth?.status === 'fresh' || dataHealth?.status === 'due'
    ? { label: 'Базовая аналитика', next_unlock: 'Регулярно добавляйте продажи и расходы, чтобы видеть больше точек роста.' }
    : { label: 'Нужны данные', next_unlock: 'Загрузите первую финансовую сводку, чтобы открыть аналитику.' });
  const rhythm = suppliedRhythm || growthLoop?.rhythm;
  if (!analytics && !rhythm && !dataHealth) return null;
  const freshness = freshnessCopy(dataHealth);
  const needsImport = dataHealth?.status === 'missing' || dataHealth?.status === 'stale' || !dataHealth;
  const unlock = analytics.next_unlock || (needsImport ? 'Загрузите первую финансовую сводку, чтобы открыть аналитику.' : 'Продолжайте регулярно добавлять данные — появятся новые точки роста.');
  const isNetwork = scopeKind === 'network' || Number(networkSummary?.locations_count || 0) > 1;
  const financeSummary = networkSummary?.finance;
  const problems = problemLocations.slice(0, 5).map((problem) => ({
    problem,
    detail: locationBreakdown.find((item) => item.business_id === problem.business_id),
  }));

  return (
    <section className="mt-4 overflow-hidden rounded-[22px] bg-white/[0.035] shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
      <div className="p-4">
        <div className="flex items-center gap-2"><DatabaseZap className="h-4 w-4 text-primary" /><h2 className="text-balance text-sm font-semibold">Ритм роста</h2></div>
        {isNetwork ? <div className="mt-3 rounded-[14px] bg-black/20 p-3">
          <div className="flex items-center gap-2"><Building2 className="h-4 w-4 text-primary" /><b className="text-xs text-zinc-200">Сводка сети</b><span className="ml-auto text-xs tabular-nums text-zinc-500">{networkSummary?.locations_count || financeSummary?.total || 0} точек</span></div>
          <div className="mt-3 grid grid-cols-4 gap-1 text-center">
            {[[financeSummary?.fresh, 'Свежие'], [financeSummary?.due, 'Скоро'], [financeSummary?.stale, 'Устарели'], [financeSummary?.missing, 'Нет данных']].map(([value, label]) => <div key={label} className="min-w-0"><b className="block tabular-nums text-zinc-200">{value || 0}</b><small className="block truncate text-[9px] text-zinc-600">{label}</small></div>)}
          </div>
        </div> : null}
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
        {analyticsModules.length ? <div className="mt-3 grid gap-2">
          {analyticsModules.map((module) => <div key={module.key || module.label} className="flex min-h-11 items-center gap-3 rounded-[14px] bg-black/20 px-3 py-2">
            <span className="min-w-0 flex-1"><b className="block truncate text-[11px] text-zinc-300">{module.label || 'Раздел аналитики'}</b>{module.status !== 'ready' && module.next_unlock ? <small className="mt-0.5 block truncate text-[9px] text-zinc-600">{module.next_unlock}</small> : null}</span>
            <small className={`shrink-0 rounded-full px-2 py-1 text-[9px] ${module.status === 'ready' ? 'bg-emerald-400/10 text-emerald-300' : module.status === 'available' ? 'bg-amber-400/10 text-amber-200' : 'bg-white/[0.05] text-zinc-500'}`}>{module.status === 'ready' ? 'Готово' : module.status === 'available' ? (module.total_locations ? `${module.ready_locations || 0}/${module.total_locations}` : 'Обновить') : 'Нужны данные'}</small>
          </div>)}
        </div> : null}
        {isNetwork && problems.length ? <div className="mt-4">
          <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-300" /><b className="text-xs text-zinc-300">Точки, которым нужны данные</b><span className="ml-auto text-[10px] tabular-nums text-zinc-600">до 5</span></div>
          <div className="mt-2 divide-y divide-white/[0.055]">
            {problems.map(({ problem, detail }) => {
              const status = locationStatus(problem.data_health_status || detail?.data_health?.status);
              const businessId = problem.target_scope?.id || problem.business_id;
              const content = <><span className="min-w-0 flex-1"><span className="flex items-center gap-2"><b className="truncate text-xs text-zinc-200">{problem.business_name || detail?.business_name || 'Точка'}</b><small className={`shrink-0 rounded-full px-2 py-1 text-[9px] ${status.tone}`}>{status.label}</small></span><small className="mt-1 block truncate text-[10px] text-zinc-600">{detail?.rhythm?.label || 'Ритм ещё не начат'} · {detail?.analytics_level?.label || 'Нужны данные'}</small>{detail?.analytics_level?.next_unlock ? <small className="mt-1 block text-pretty text-[10px] leading-4 text-zinc-700">{detail.analytics_level.next_unlock}</small> : null}</span>{businessId && onOpenLocation ? <ChevronRight className="h-4 w-4 shrink-0 text-zinc-700" /> : null}</>;
              return businessId && onOpenLocation ? <button key={businessId} type="button" onClick={() => onOpenLocation(businessId, problemScreen(problem))} className="flex min-h-14 w-full items-center gap-3 py-3 text-left transition-transform active:scale-[0.96]">{content}</button> : <div key={businessId || problem.business_name} className="flex min-h-14 items-center gap-3 py-3">{content}</div>;
            })}
          </div>
        </div> : null}
        {needsImport && showImportAction && !isNetwork ? <button type="button" onClick={onOpenImport} className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-white/[0.06] px-3 text-xs font-semibold text-zinc-100 shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-[background-color,transform] active:scale-[0.96]">Загрузить финансовую сводку<ChevronRight className="h-4 w-4" /></button> : null}
      </div>
    </section>
  );
};
