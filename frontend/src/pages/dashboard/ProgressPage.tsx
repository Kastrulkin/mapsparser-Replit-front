import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  BadgeDollarSign,
  Bot,
  CheckCircle2,
  ChevronDown,
  Circle,
  Clock3,
  FileText,
  Handshake,
  MapPinned,
  RefreshCw,
  Sparkles,
  X,
  type LucideIcon,
} from 'lucide-react';

import CardAuditPanel from '@/components/CardAuditPanel';
import MapParseTable from '@/components/MapParseTable';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type GrowthAreaKey = 'maps' | 'content' | 'partnerships' | 'automation' | 'upsells';
type GrowthAreaStatus = 'not_started' | 'in_progress' | 'healthy' | 'needs_attention' | 'unavailable';

type GrowthAction = {
  title: string;
  reason: string;
  expected_outcome: string;
  cta_label: string;
  cta_url: string;
  estimated_effect?: {
    kind: string;
    label: string;
    amount?: number;
    currency?: string;
    source?: string;
  } | null;
};

type GrowthMilestone = {
  key: string;
  label: string;
  status: 'done' | 'next';
  achieved_at?: string | null;
  evidence?: string;
};

type GrowthArea = {
  key: GrowthAreaKey;
  label: string;
  status: GrowthAreaStatus;
  summary: string;
  problem?: string | null;
  expected_outcome: string;
  action: GrowthAction;
  progress: { completed: number; total: number };
  milestones: GrowthMilestone[];
  metrics: Array<{ label: string; value: string | number }>;
};

type GrowthAchievement = {
  key: string;
  area: GrowthAreaKey;
  title: string;
  description: string;
  occurred_at: string;
};

type GrowthOverview = {
  summary: {
    completed_milestones: number;
    total_milestones: number;
    active_areas: number;
    needs_attention: number;
    completed_last_30_days: number;
    locations_count: number;
  };
  focus_action: GrowthAction | null;
  areas: GrowthArea[];
  recent_achievements: GrowthAchievement[];
  scope?: {
    business_id: string;
    business_name: string;
    is_network: boolean;
    locations: Array<{ id: string; name: string }>;
  };
  generated_at: string;
};

type ParseStatus = 'idle' | 'queued' | 'processing' | 'completed' | 'done' | 'error';

type DashboardContext = {
  currentBusinessId?: string | null;
};

const AREA_ICONS: Record<GrowthAreaKey, LucideIcon> = {
  maps: MapPinned,
  content: FileText,
  partnerships: Handshake,
  automation: Bot,
  upsells: BadgeDollarSign,
};

const STATUS_COPY: Record<GrowthAreaStatus, { label: string; className: string }> = {
  healthy: { label: 'Работает', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  in_progress: { label: 'В процессе', className: 'border-sky-200 bg-sky-50 text-sky-700' },
  needs_attention: { label: 'Нужно внимание', className: 'border-amber-200 bg-amber-50 text-amber-800' },
  not_started: { label: 'Не начато', className: 'border-slate-200 bg-slate-50 text-slate-600' },
  unavailable: { label: 'Нет данных', className: 'border-rose-200 bg-rose-50 text-rose-700' },
};

const formatDate = (value?: string | null) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(date).replace(/\.$/, '');
};

const formatMoney = (value: number) =>
  new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value);

const achievementStorageKey = (businessId: string) => `localos:growth-achievements:${businessId}`;

const readSeenAchievements = (businessId: string) => {
  try {
    const value = localStorage.getItem(achievementStorageKey(businessId));
    if (!value) return null;
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return null;
    return parsed.filter((item) => typeof item === 'string');
  } catch {
    return null;
  }
};

const saveSeenAchievements = (businessId: string, keys: string[]) => {
  try {
    localStorage.setItem(achievementStorageKey(businessId), JSON.stringify(keys));
  } catch {
    // The progress screen remains usable when browser storage is unavailable.
  }
};

const AreaRow = ({
  area,
  expanded,
  onToggle,
  onOpen,
  details,
}: {
  area: GrowthArea;
  expanded: boolean;
  onToggle: () => void;
  onOpen: (url: string) => void;
  details?: ReactNode;
}) => {
  const Icon = AREA_ICONS[area.key];
  const status = STATUS_COPY[area.status];
  const progressValue = area.progress.total > 0
    ? Math.round((area.progress.completed / area.progress.total) * 100)
    : 0;

  return (
    <div className="border-b border-slate-200 last:border-b-0">
      <button
        type="button"
        data-tour-target={`progress-area-${area.key}`}
        onClick={onToggle}
        aria-expanded={expanded}
        className="grid w-full gap-4 px-4 py-5 text-left transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-inset md:grid-cols-[minmax(220px,0.9fr)_minmax(260px,1.4fr)_minmax(180px,0.7fr)_44px] md:items-center md:px-6"
      >
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-slate-950">{area.label}</div>
            <div className={cn('mt-1 inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold', status.className)}>
              {status.label}
            </div>
          </div>
        </div>

        <div className="min-w-0">
          <div className="text-sm leading-6 text-slate-700">{area.summary}</div>
          {area.problem ? <div className="mt-1 text-xs leading-5 text-amber-800">{area.problem}</div> : null}
        </div>

        <div className="min-w-0">
          <div className="flex items-center justify-between gap-3 text-xs font-medium text-slate-500">
            <span>Сделано</span>
            <span className="tabular-nums">{area.progress.completed} из {area.progress.total}</span>
          </div>
          <Progress value={progressValue} className="mt-2 h-2" />
        </div>

        <span className="flex h-11 w-11 items-center justify-center justify-self-end rounded-lg text-slate-500">
          <ChevronDown className={cn('h-5 w-5 transition-transform duration-200', expanded && 'rotate-180')} />
        </span>
      </button>

      {expanded ? (
        <div className="border-t border-slate-100 bg-slate-50/70 px-4 py-5 md:px-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Путь</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {area.milestones.map((milestone) => (
                  <div key={milestone.key} className="flex min-w-0 gap-2 rounded-lg border border-slate-200 bg-white px-3 py-3">
                    {milestone.status === 'done' ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    ) : (
                      <Circle className="mt-0.5 h-4 w-4 shrink-0 text-slate-300" />
                    )}
                    <div className="min-w-0">
                      <div className="text-sm font-medium leading-5 text-slate-800">{milestone.label}</div>
                      {milestone.status === 'done' && milestone.evidence ? (
                        <div className="mt-1 text-xs leading-5 text-slate-500">{milestone.evidence}</div>
                      ) : null}
                      {milestone.status === 'done' && milestone.achieved_at ? (
                        <div className="mt-1 text-xs tabular-nums text-slate-400">{formatDate(milestone.achieved_at)}</div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-l-0 border-slate-200 lg:border-l lg:pl-6">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Что даст следующий шаг</div>
              <p className="mt-2 text-sm leading-6 text-slate-700">{area.expected_outcome}</p>
              {area.action.estimated_effect?.amount ? (
                <div className="mt-2 text-sm font-medium tabular-nums text-emerald-700">
                  {area.action.estimated_effect.label}: {formatMoney(area.action.estimated_effect.amount)} ₽
                </div>
              ) : null}
              <Button type="button" variant="outline" className="mt-4 w-full sm:w-auto" onClick={() => onOpen(area.action.cta_url)}>
                {area.action.cta_label}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </div>
          {details ? <div className="mt-5 border-t border-slate-200 pt-5">{details}</div> : null}
        </div>
      ) : null}
    </div>
  );
};

export const ProgressPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { currentBusinessId } = useOutletContext<DashboardContext>();
  const [overviewData, setOverviewData] = useState<GrowthOverview | null>(null);
  const [overviewBusinessId, setOverviewBusinessId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedArea, setExpandedArea] = useState<GrowthAreaKey | null>(null);
  const [celebration, setCelebration] = useState<GrowthAchievement | null>(null);
  const [overviewRefreshKey, setOverviewRefreshKey] = useState(0);
  const [auditRefreshKey, setAuditRefreshKey] = useState(0);
  const [showFullAudit, setShowFullAudit] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedAuditBusinessId, setSelectedAuditBusinessId] = useState<string | null>(null);
  const [parseStatus, setParseStatus] = useState<ParseStatus>('idle');
  const parseStatusRef = useRef<ParseStatus>('idle');
  const auditSectionRef = useRef<HTMLElement | null>(null);
  const requestedMapsSection = searchParams.get('section') === 'maps';
  const requestedAudit = requestedMapsSection && searchParams.get('audit') === 'open';
  const overview = overviewBusinessId === currentBusinessId ? overviewData : null;

  useEffect(() => {
    if (!currentBusinessId) {
      setOverviewData(null);
      setOverviewBusinessId(null);
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void newAuth.makeRequest(
      `/business/${currentBusinessId}/growth-overview`,
      { method: 'GET', signal: controller.signal },
    ).then((data: GrowthOverview) => {
      if (controller.signal.aborted) return;
      setOverviewData(data);
      setOverviewBusinessId(currentBusinessId);
      const focusArea = data.areas.find((area) => area.action.cta_url === data.focus_action?.cta_url);
      setExpandedArea((current) => current ?? focusArea?.key ?? data.areas[0]?.key ?? null);

      const locations = data.scope?.locations || [];
      setSelectedAuditBusinessId((current) => {
        if (locations.some((location) => location.id === current)) return current;
        return locations[0]?.id || currentBusinessId;
      });

      const achievementKeys = data.recent_achievements.map((item) => item.key);
      const seenKeys = readSeenAchievements(currentBusinessId);
      if (seenKeys === null) {
        saveSeenAchievements(currentBusinessId, achievementKeys);
      } else {
        const freshAchievement = data.recent_achievements.find((item) => !seenKeys.includes(item.key));
        if (freshAchievement) setCelebration(freshAchievement);
        saveSeenAchievements(currentBusinessId, Array.from(new Set([...seenKeys, ...achievementKeys])));
      }
    }).catch((requestError) => {
      if (controller.signal.aborted) return;
      const message = requestError instanceof Error ? requestError.message : 'Не удалось загрузить прогресс бизнеса';
      setError(message);
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });

    return () => controller.abort();
  }, [currentBusinessId, overviewRefreshKey]);

  useEffect(() => {
    setCelebration(null);
    setExpandedArea(requestedMapsSection ? 'maps' : null);
    setShowFullAudit(requestedAudit);
    setHistoryOpen(false);
    setSelectedAuditBusinessId(null);
    setParseStatus('idle');
    parseStatusRef.current = 'idle';
  }, [currentBusinessId]);

  useEffect(() => {
    if (requestedMapsSection) setExpandedArea('maps');
    setShowFullAudit(requestedAudit);
  }, [requestedMapsSection, requestedAudit]);

  useEffect(() => {
    const parseBusinessId = selectedAuditBusinessId || currentBusinessId;
    if (!parseBusinessId) return undefined;

    const controller = new AbortController();
    let timer: number | undefined;
    parseStatusRef.current = 'idle';

    const loadParseStatus = async () => {
      try {
        const data: { success?: boolean; status?: string } = await newAuth.makeRequest(
          `/business/${parseBusinessId}/parse-status`,
          { method: 'GET', signal: controller.signal },
        );
        if (controller.signal.aborted || data.success === false) return;
        const rawStatus = String(data.status || 'idle').trim().toLowerCase();
        let nextStatus: ParseStatus = 'idle';
        if (rawStatus === 'pending' || rawStatus === 'queued') nextStatus = 'queued';
        if (rawStatus === 'processing') nextStatus = 'processing';
        if (rawStatus === 'completed') nextStatus = 'completed';
        if (rawStatus === 'done') nextStatus = 'done';
        if (rawStatus === 'error' || rawStatus === 'captcha') nextStatus = 'error';

        const previousStatus = parseStatusRef.current;
        const wasActive = previousStatus === 'queued' || previousStatus === 'processing';
        const isFinished = nextStatus === 'completed' || nextStatus === 'done';
        parseStatusRef.current = nextStatus;
        setParseStatus(nextStatus);

        if (wasActive && isFinished) {
          setAuditRefreshKey((value) => value + 1);
          setOverviewRefreshKey((value) => value + 1);
        }
        if (nextStatus === 'queued' || nextStatus === 'processing') {
          timer = window.setTimeout(() => void loadParseStatus(), 10000);
        }
      } catch {
        if (!controller.signal.aborted) setParseStatus('error');
      }
    };

    void loadParseStatus();
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [currentBusinessId, selectedAuditBusinessId]);

  useEffect(() => {
    if (!showFullAudit || !overview) return undefined;
    const frame = window.requestAnimationFrame(() => {
      auditSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      auditSectionRef.current?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [showFullAudit, overview]);

  useEffect(() => {
    if (!celebration) return;
    const timeout = window.setTimeout(() => setCelebration(null), 7000);
    return () => window.clearTimeout(timeout);
  }, [celebration]);

  const refreshAll = () => {
    setOverviewRefreshKey((value) => value + 1);
    setAuditRefreshKey((value) => value + 1);
  };

  const openFullAudit = () => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('section', 'maps');
    nextParams.set('audit', 'open');
    setExpandedArea('maps');
    setShowFullAudit(true);
    setSearchParams(nextParams, { replace: true });
  };

  const closeFullAudit = () => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('section', 'maps');
    nextParams.delete('audit');
    setShowFullAudit(false);
    setHistoryOpen(false);
    setSearchParams(nextParams, { replace: true });
  };

  const overallProgress = useMemo(() => {
    if (!overview?.summary.total_milestones) return 0;
    return Math.round((overview.summary.completed_milestones / overview.summary.total_milestones) * 100);
  }, [overview]);
  const mapsArea = overview?.areas.find((area) => area.key === 'maps') || null;
  const mapAuditMilestone = mapsArea?.milestones.find((milestone) => milestone.key === 'map_audited');
  const networkLocations = overview?.scope?.locations || [];
  const selectedAuditLocation = networkLocations.find((location) => location.id === selectedAuditBusinessId);

  if (!currentBusinessId) {
    return (
      <div className="space-y-6">
        <DashboardPageHeader title="Прогресс бизнеса" description="Выберите бизнес, чтобы увидеть сделанное и следующий шаг." />
      </div>
    );
  }

  if (loading && !overview) {
    return (
      <div className="space-y-6" aria-busy="true">
        <DashboardPageHeader title="Прогресс бизнеса" description="Собираем подтверждённые результаты из рабочих разделов LocalOS." />
        <div className="h-36 animate-pulse rounded-xl bg-slate-100" />
        <div className="h-80 animate-pulse rounded-xl bg-slate-100" />
      </div>
    );
  }

  if (!overview) {
    return (
      <div className="space-y-6">
        <DashboardPageHeader title="Прогресс бизнеса" description="Общая картина выполненной работы и следующих действий." />
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-700" />
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold text-amber-950">Не удалось собрать общую картину</h2>
              <p className="mt-1 text-sm leading-6 text-amber-900">{error || 'Попробуйте обновить данные.'}</p>
              <Button type="button" variant="outline" className="mt-4 active:scale-[0.96] transition-transform" onClick={refreshAll}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Повторить
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-tour-target="progress-overview">
      <DashboardPageHeader
        eyebrow="Картина бизнеса"
        title="Прогресс бизнеса"
        description="Что уже сделано, где нужна помощь и какой шаг даст следующий практический результат."
        actions={(
          <Button type="button" variant="outline" onClick={refreshAll} disabled={loading} className="active:scale-[0.96] transition-transform">
            <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
            Обновить
          </Button>
        )}
      />

      {error ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="status">
          <span>Новая сводка пока не загрузилась. Показываем предыдущие подтверждённые данные.</span>
          <button type="button" onClick={refreshAll} className="min-h-10 font-semibold underline underline-offset-2">Повторить</button>
        </div>
      ) : null}

      {celebration ? (
        <div className="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-top-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4" role="status">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="font-semibold text-emerald-950">Новый результат: {celebration.title}</div>
              <div className="mt-1 text-sm leading-6 text-emerald-800">{celebration.description}</div>
            </div>
          </div>
        </div>
      ) : null}

      <section className="grid gap-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.55fr)] lg:p-6">
        <div data-tour-target="progress-summary">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Подтверждённый путь</div>
          <div className="mt-3 flex flex-wrap items-end gap-x-4 gap-y-2">
            <div className="text-3xl font-semibold tabular-nums text-slate-950">
              {overview.summary.completed_milestones} из {overview.summary.total_milestones}
            </div>
            <div className="pb-1 text-sm text-slate-600">шагов подтверждены реальными данными</div>
          </div>
          <Progress value={overallProgress} className="mt-4 h-3" />
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
            <span><strong className="tabular-nums text-slate-950">{overview.summary.completed_last_30_days}</strong> результатов за 30 дней</span>
            <span><strong className="tabular-nums text-slate-950">{overview.summary.active_areas}</strong> направлений начаты</span>
            {overview.summary.needs_attention > 0 ? (
              <span className="text-amber-800"><strong className="tabular-nums">{overview.summary.needs_attention}</strong> требуют внимания</span>
            ) : null}
          </div>
        </div>

        <div className="border-t border-slate-200 pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0" data-tour-target="progress-focus-action">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">Сейчас важнее всего</div>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">{overview.focus_action?.title || 'Продолжайте работу'}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{overview.focus_action?.reason}</p>
          {overview.focus_action ? (
            <>
              <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
                <strong>Результат:</strong> {overview.focus_action.expected_outcome}
              </div>
              {overview.focus_action.estimated_effect?.amount ? (
                <div className="mt-2 text-sm font-medium tabular-nums text-emerald-700">
                  {overview.focus_action.estimated_effect.label}: {formatMoney(overview.focus_action.estimated_effect.amount)} ₽
                </div>
              ) : null}
              <Button type="button" className="mt-4 w-full bg-orange-500 text-white hover:bg-orange-600" onClick={() => navigate(overview.focus_action?.cta_url || '/dashboard/progress')}>
                {overview.focus_action.cta_label}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </>
          ) : null}
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-4 py-4 md:px-6" data-tour-target="progress-areas">
          <h2 className="text-lg font-semibold text-slate-950">Направления роста</h2>
          <p className="mt-1 text-sm text-slate-600">Откройте направление, чтобы увидеть сделанное и следующий шаг.</p>
        </div>
        {overview.areas.map((area) => (
          <AreaRow
            key={area.key}
            area={area}
            expanded={expandedArea === area.key}
            onToggle={() => setExpandedArea((current) => current === area.key ? null : area.key)}
            onOpen={navigate}
            details={area.key === 'maps' ? (
              <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Текущий аудит</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {area.metrics.map((metric) => (
                      <div key={metric.label} className="rounded-lg bg-white px-3 py-2 shadow-sm ring-1 ring-slate-200">
                        <div className="text-xs text-slate-500">{metric.label}</div>
                        <div className="mt-0.5 font-semibold tabular-nums text-slate-900">{metric.value}</div>
                      </div>
                    ))}
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-600">
                    {mapAuditMilestone?.status === 'done'
                      ? `Аудит готов${mapAuditMilestone.achieved_at ? ` и обновлён ${formatDate(mapAuditMilestone.achieved_at)}` : ''}. Откройте его, чтобы увидеть факты и приоритеты карточки.`
                      : 'Полный аудит появится здесь после первого успешного сбора данных.'}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={openFullAudit}
                  className="w-full active:scale-[0.96] transition-transform md:w-auto"
                >
                  Посмотреть полный аудит
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            ) : undefined}
          />
        ))}
      </section>

      {showFullAudit ? (
        <section
          ref={auditSectionRef}
          tabIndex={-1}
          aria-labelledby="full-audit-title"
          className="scroll-mt-6 space-y-4 outline-none"
        >
          <div className="flex flex-col gap-4 rounded-xl bg-slate-950 px-5 py-5 text-white shadow-sm md:flex-row md:items-center md:justify-between md:px-6">
            <div className="min-w-0">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Карты и репутация</div>
              <h2 id="full-audit-title" className="mt-1 text-xl font-semibold text-balance">Полный аудит карточки</h2>
              <p className="mt-1 text-sm leading-6 text-pretty text-slate-300">
                {selectedAuditLocation ? `Точка: ${selectedAuditLocation.name}. ` : ''}Данные, причины проблем и конкретные действия.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {networkLocations.length > 1 ? (
                <Select value={selectedAuditBusinessId || networkLocations[0]?.id} onValueChange={setSelectedAuditBusinessId}>
                  <SelectTrigger className="min-h-10 w-full border-white/20 bg-white text-slate-950 md:w-[260px]" aria-label="Выбрать точку для аудита">
                    <SelectValue placeholder="Выберите точку" />
                  </SelectTrigger>
                  <SelectContent>
                    {networkLocations.map((location) => (
                      <SelectItem key={location.id} value={location.id}>{location.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : null}
              <button
                type="button"
                onClick={closeFullAudit}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-slate-300 transition-[background-color,color,transform] hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 active:scale-[0.96]"
                aria-label="Скрыть полный аудит"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {parseStatus === 'queued' || parseStatus === 'processing' ? (
            <div className="flex items-center gap-2 rounded-lg bg-sky-50 px-4 py-3 text-sm text-sky-800" role="status">
              <RefreshCw className="h-4 w-4 motion-safe:animate-spin" />
              {parseStatus === 'queued' ? 'Сбор данных ждёт запуска. Текущий аудит остаётся доступен.' : 'Собираем свежие данные. Текущий аудит остаётся на экране.'}
            </div>
          ) : null}

          <CardAuditPanel
            businessId={selectedAuditBusinessId || currentBusinessId}
            refreshKey={auditRefreshKey}
            onRetry={() => setAuditRefreshKey((value) => value + 1)}
          />

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <button
              type="button"
              onClick={() => setHistoryOpen((current) => !current)}
              aria-expanded={historyOpen}
              className="flex min-h-12 w-full items-center justify-between gap-3 px-4 py-3 text-left font-semibold text-slate-900 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-orange-500 md:px-6"
            >
              <span>История обновлений карточки</span>
              <ChevronDown className={cn('h-5 w-5 shrink-0 text-slate-500 transition-transform duration-200', historyOpen && 'rotate-180')} />
            </button>
            {historyOpen ? (
              <div className="border-t border-slate-200 p-3 md:p-4">
                <MapParseTable
                  businessId={selectedAuditBusinessId || currentBusinessId}
                  refreshKey={auditRefreshKey}
                  onRetry={() => setAuditRefreshKey((value) => value + 1)}
                  embedded
                />
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:p-6" data-tour-target="progress-recent-results">
        <div className="flex items-center gap-2">
          <Clock3 className="h-5 w-5 text-slate-500" />
          <h2 className="text-lg font-semibold text-slate-950">Недавние результаты</h2>
        </div>
        {overview.recent_achievements.length > 0 ? (
          <div className="mt-4 divide-y divide-slate-100">
            {overview.recent_achievements.map((item) => {
              const Icon = AREA_ICONS[item.area];
              return (
                <div key={item.key} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-slate-900">{item.title}</div>
                    <div className="mt-0.5 text-sm leading-5 text-slate-600">{item.description}</div>
                  </div>
                  <div className="shrink-0 text-xs tabular-nums text-slate-400">{formatDate(item.occurred_at)}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-4 rounded-lg bg-slate-50 px-4 py-5 text-sm leading-6 text-slate-600">
            Здесь появятся подтверждённые результаты: готовый аудит, контент-план, найденные партнёры, выполненные задачи и внедрённые допродажи.
          </div>
        )}
      </section>

    </div>
  );
};
