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
	X,
	type LucideIcon,
} from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate, useOutletContext, useSearchParams } from 'react-router-dom';

import CardAuditPanel from '@/components/CardAuditPanel';
import type { ControlScope } from '@/components/DashboardLayout';
import MapParseTable from '@/components/MapParseTable';
import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { DataHealthRhythmStrip, type GrowthDataHealth } from '@/components/growth/DataHealthRhythmStrip';
import { ManagedCardGrowthPanel, type ManagedCardGrowth } from '@/components/growth/ManagedCardGrowthPanel';
import { managedCardGrowthCopyForLanguage, managedEvidence, managedFactLabel, managedProviderLabel, managedStateLabel } from '@/components/growth/managedCardGrowthCopy';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLanguage, type Language } from '@/i18n/LanguageContext.logic';
import { HttpError, newAuth } from '@/lib/auth_new';
import { trackProductEvent } from '@/lib/productEvents';
import { cn } from '@/lib/utils';
import { NetworkDashboardPage } from './network/NetworkDashboardPage';
import {
	localizedAnalyticsLevel,
	localizedAnalyticsModule,
	localizedAnalyticsNext,
	localizedGrowthArea,
	localizedGrowthMetric,
	localizedGrowthMilestone,
	localizedGrowthStatus,
	localizedGrowthText,
	localizedProgressBusinessName,
	localizedRhythm,
	progressPageCopyForLanguage,
	progressRuntimeCopyForLanguage,
	type ProgressPageCopy,
} from './progressPageCopy';

type GrowthAreaKey = 'maps' | 'content' | 'partnerships' | 'automation' | 'upsells';
type GrowthAreaStatus = 'not_started' | 'in_progress' | 'healthy' | 'needs_attention' | 'unavailable';

type GrowthAction = {
  id?: string;
  title: string;
  reason: string;
  expected_outcome: string;
  cta_label: string;
  cta_url?: string;
  provider?: string | null;
  provider_label?: string | null;
  fact?: string;
  gate?: number;
  gate_label?: string;
  copy_code?: string | null;
  copy_params?: { goal?: string; benchmark_median?: number };
  screen?: string;
  target_scope?: { kind?: string; id?: string };
  affected_business_ids?: string[];
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

type GrowthOverview = ManagedCardGrowth & {
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
  recent_results?: GrowthAchievement[];
  as_of?: string;
  growth_loop?: {
    mission_id?: string;
    focus?: GrowthAction;
    current_mission?: GrowthAction;
    mission?: GrowthAction;
  };
  data_health?: GrowthDataHealth | null;
  analytics_level?: { level?: string; label?: string; next_unlock?: string | null } | null;
  analytics_modules?: Array<{ key?: string; label?: string; status?: string; next_unlock?: string | null }>;
  data_rhythm?: { coverage?: number; completed_periods_8w?: number; next_due_at?: string | null } | null;
  rhythm?: { label?: string; active_weeks?: number; status?: string } | null;
  network_summary?: { locations_count?: number; problem_locations_count?: number; healthy_locations_count?: number } | null;
  problem_locations?: Array<{ business_id: string; business_name: string; data_health_status?: string; problem_areas?: string[]; focus_action?: GrowthAction | null }>;
  location_breakdown?: Array<{ business_id: string; business_name: string }>;
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
  controlScope?: ControlScope | null;
  onControlScopeChange?: (scope: ControlScope) => void;
  onBusinessChange?: (businessId: string) => void;
};

const screenRoute = (screen?: string) => ({ cards: '/dashboard/card', reviews: '/dashboard/card?tab=reviews', content: '/dashboard/content', finance: '/dashboard/finance', partnerships: '/dashboard/partnerships', agents: '/dashboard/agents', progress: '/dashboard/progress', operator: '/dashboard/operator' }[screen || ''] || '/dashboard/progress');

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

const formatDate = (value: string | null | undefined, language: Language) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(language, { day: 'numeric', month: 'short', year: 'numeric' }).format(date).replace(/\.$/, '');
};

const AreaRow = ({ area, expanded, onToggle, onOpen, details, language, copy }: {
  area: GrowthArea;
  expanded: boolean;
  onToggle: () => void;
  onOpen: (action: GrowthAction) => void;
  details?: ReactNode;
  language: Language;
  copy: ProgressPageCopy;
}) => {
  const Icon = AREA_ICONS[area.key];
  const status = STATUS_COPY[area.status];
  const summary = localizedGrowthText(language, area.summary);
  return (
    <div className="border-b border-border last:border-b-0">
      <button type="button" id={`progress-area-${area.key}`} data-tour-target={`progress-area-${area.key}`} onClick={onToggle}
        aria-expanded={expanded} aria-controls={`progress-details-${area.key}`}
        className="grid min-h-11 w-full grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-4 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_auto] lg:items-center md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Icon className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="min-w-0">
            <div className="font-semibold text-foreground">{localizedGrowthArea(language, area.key, area.label)}</div>
            <span className={cn('mt-1 inline-flex rounded-full border px-2 py-0.5 text-xs font-medium', status.className)}>
              {localizedGrowthStatus(language, area.status, status.label)}
            </span>
          </div>
        </div>
        <p className="col-span-2 row-start-2 min-w-0 break-words text-sm leading-6 text-muted-foreground lg:col-span-1 lg:col-start-2 lg:row-start-1">
          {language === 'ru' && area.key === 'automation' ? summary.replace(/^Агентов:/, 'ИИ-сотрудников:') : summary}
        </p>
        <ChevronDown className={cn('col-start-2 row-start-1 h-5 w-5 self-center text-muted-foreground transition-transform motion-reduce:transition-none lg:col-start-3', expanded && 'rotate-180')} aria-hidden="true" />
      </button>
      <div id={`progress-details-${area.key}`} hidden={!expanded}>
        {expanded ? <div className="space-y-5 border-t border-border bg-muted/30 px-4 py-5 md:px-6">
          {area.milestones.length > 0 ? <div>
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
              <h3 className="font-semibold">{copy.path}</h3>
              <span className="tabular-nums text-muted-foreground">{area.progress.completed} {copy.of} {area.progress.total} {copy.confirmedSteps}</span>
            </div>
            <ul className="mt-3 divide-y divide-border">
              {area.milestones.map((milestone) => <li key={milestone.key} className="flex min-w-0 gap-3 py-3">
                {milestone.status === 'done' ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" aria-hidden="true" /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap justify-between gap-2 text-sm">
                    <span>{localizedGrowthMilestone(language, milestone.key, milestone.label)}</span>
                    <span className="text-muted-foreground">{milestone.status === 'done' ? copy.completed : localizedGrowthStatus(language, 'not_started', 'Не начато')}</span>
                  </div>
                  {milestone.status === 'done' && milestone.evidence ? <p className="mt-1 break-words text-xs text-muted-foreground">{localizedGrowthText(language, milestone.evidence)}</p> : null}
                  {milestone.status === 'done' && milestone.achieved_at ? <p className="mt-1 text-xs tabular-nums text-muted-foreground">{formatDate(milestone.achieved_at, language)}</p> : null}
                </div>
              </li>)}
            </ul>
          </div> : null}
          {area.metrics.length > 0 ? <dl className="flex flex-wrap gap-x-6 gap-y-3">
            {area.metrics.map((metric) => <div key={metric.label}>
              <dt className="text-xs text-muted-foreground">{localizedGrowthMetric(language, metric.label)}</dt>
              <dd className="mt-1 text-sm font-semibold tabular-nums">{localizedGrowthText(language, String(metric.value))}</dd>
            </div>)}
          </dl> : null}
          {area.problem ? <p className="text-sm leading-6 text-amber-800">{localizedGrowthText(language, area.problem)}</p> : null}
          {details || <div className="space-y-3">
            <p className="text-sm leading-6 text-muted-foreground">{localizedGrowthText(language, area.expected_outcome)}</p>
            {(area.action.cta_url || area.action.screen) && area.status !== 'unavailable' ? <Button type="button" variant="outline" className="min-h-11 w-full sm:w-auto" onClick={() => onOpen(area.action)}>
              {localizedGrowthText(language, area.action.cta_label)}<ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
            </Button> : null}
          </div>}
        </div> : null}
      </div>
    </div>
  );
};

export const ProgressPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { currentBusinessId, controlScope, onControlScopeChange, onBusinessChange } = useOutletContext<DashboardContext>();
  const { language } = useLanguage();
  const copy = progressPageCopyForLanguage(language);
  const runtime = progressRuntimeCopyForLanguage(language);
  const managedCopy = managedCardGrowthCopyForLanguage(language);
  const [overviewData, setOverviewData] = useState<GrowthOverview | null>(null);
  const [overviewBusinessId, setOverviewBusinessId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedArea, setExpandedArea] = useState<GrowthAreaKey | null>(null);
  const [overviewRefreshKey, setOverviewRefreshKey] = useState(0);
  const [auditRefreshKey, setAuditRefreshKey] = useState(0);
  const [showFullAudit, setShowFullAudit] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedAuditBusinessId, setSelectedAuditBusinessId] = useState<string | null>(null);
  const [parseStatus, setParseStatus] = useState<ParseStatus>('idle');
  const [networkOpen, setNetworkOpen] = useState(false);
  const [reportDataOpen, setReportDataOpen] = useState(false);
  const [stagesOpen, setStagesOpen] = useState(false);
  const parseStatusRef = useRef<ParseStatus>('idle');
  const auditSectionRef = useRef<HTMLElement | null>(null);
  const requestedMapsSection = searchParams.get('section') === 'maps';
  const requestedAudit = requestedMapsSection && searchParams.get('audit') === 'open';
  const scopeId = controlScope?.id || currentBusinessId;
  const scopeKind = controlScope?.kind || 'business';
  const scopeKey = `${scopeKind}:${scopeId || ''}`;
  const overview = overviewBusinessId === scopeKey ? overviewData : null;

  useEffect(() => {
    if (!scopeId) {
      setOverviewData(null);
      setOverviewBusinessId(null);
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void newAuth.makeRequest(
      `/operator/progress?${new URLSearchParams({ scope_type: scopeKind, scope_id: scopeId }).toString()}`,
      { method: 'GET', signal: controller.signal },
    ).then((data: GrowthOverview) => {
      if (controller.signal.aborted) return;
      if (!data?.summary || !Array.isArray(data.areas)) {
        throw new Error(copy.loadErrorTitle);
      }
      const normalizedData: GrowthOverview = {
        ...data,
        areas: data.areas.map((area) => ({
          ...area,
          milestones: Array.isArray(area.milestones) ? area.milestones : [],
          metrics: Array.isArray(area.metrics) ? area.metrics : [],
        })),
        recent_achievements: Array.isArray(data.recent_achievements) ? data.recent_achievements : Array.isArray(data.recent_results) ? data.recent_results : [],
        generated_at: data.generated_at || data.as_of || '',
        problem_locations: Array.isArray(data.problem_locations) ? data.problem_locations : [],
        analytics_modules: Array.isArray(data.analytics_modules) ? data.analytics_modules : [],
        scope: data.scope ? { ...data.scope, locations: Array.isArray(data.scope.locations) ? data.scope.locations : [] } : data.scope,
      };
      setOverviewData(normalizedData);
      setOverviewBusinessId(scopeKey);
      const locations = normalizedData.scope?.locations || [];
      setSelectedAuditBusinessId((current) => {
        if (locations.some((location) => location.id === current)) return current;
        return locations[0]?.id || currentBusinessId;
      });

    }).catch((requestError) => {
      if (controller.signal.aborted) return;
      if (requestError instanceof HttpError && [401, 403, 404].includes(requestError.status ?? 0)) {
        setOverviewData(null);
        setOverviewBusinessId(null);
        setExpandedArea(null);
        setShowFullAudit(false);
        setHistoryOpen(false);
        setNetworkOpen(false);
        setReportDataOpen(false);
        setStagesOpen(false);
      }
      const message = requestError instanceof Error ? requestError.message : copy.loadErrorTitle;
      setError(message);
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });

    return () => controller.abort();
  }, [copy.loadErrorTitle, currentBusinessId, overviewRefreshKey, scopeId, scopeKey, scopeKind]);

  useEffect(() => {
    setExpandedArea(requestedMapsSection ? 'maps' : null);
    setShowFullAudit(requestedAudit);
    setHistoryOpen(false);
    setNetworkOpen(false);
    setReportDataOpen(false);
    setStagesOpen(false);
    setSelectedAuditBusinessId(null);
    setParseStatus('idle');
    parseStatusRef.current = 'idle';
  }, [currentBusinessId, requestedAudit, requestedMapsSection, scopeKey]);

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
  }, [currentBusinessId, scopeKey, selectedAuditBusinessId]);

  useEffect(() => {
    if (!showFullAudit || !overview) return undefined;
    const frame = window.requestAnimationFrame(() => {
      auditSectionRef.current?.scrollIntoView({ behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
      auditSectionRef.current?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [showFullAudit, overview]);

  useEffect(() => {
    trackProductEvent({ eventName: 'progress_open', businessId: currentBusinessId });
  }, [currentBusinessId]);

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

  const mapsArea = overview?.areas.find((area) => area.key === 'maps') || null;
  const mapAuditMilestone = mapsArea?.milestones.find((milestone) => milestone.key === 'map_audited');
  const networkLocations = overview?.scope?.locations || [];
  const recentAchievements = (overview?.recent_achievements || [])
    .filter((item) => item.occurred_at && !Number.isNaN(Date.parse(item.occurred_at)))
    .slice().sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at)).slice(0, 8);
  const selectedAuditLocation = networkLocations.find((location) => location.id === selectedAuditBusinessId);
  const selectedManagedLocation = overview?.card_state?.locations?.find((location) => location.business_id === (selectedAuditBusinessId || currentBusinessId));
  const hasManagedCardGrowth = Boolean(overview?.card_state);
  const providers = overview?.card_state?.locations?.flatMap((location) => location.providers) || [];
  const sourcesBlocked = providers.length > 0 && providers.every((provider) => provider.source_state === 'blocked');
  const currentMission = overview?.focus_action || overview?.growth_loop?.focus || overview?.growth_loop?.current_mission || overview?.growth_loop?.mission || null;
  const areas: GrowthArea[] = overview?.areas.slice() || [];
  if (!mapsArea && hasManagedCardGrowth) {
    areas.unshift({
      key: 'maps', label: copy.mapsAndReputation,
      status: overview?.card_state?.status === 'healthy' ? 'healthy' : 'needs_attention',
      summary: copy.currentAudit, expected_outcome: '',
      action: currentMission && (currentMission.provider || currentMission.screen === 'cards' || currentMission.screen === 'reviews' || currentMission.cta_url?.startsWith('/dashboard/card'))
        ? currentMission : { title: '', reason: '', expected_outcome: '', cta_label: '' },
      progress: { completed: 0, total: 0 }, milestones: [], metrics: [],
    });
  }
  const areaOrder: GrowthAreaKey[] = ['maps', 'content', 'partnerships', 'automation', 'upsells'];
  areas.sort((a, b) => areaOrder.indexOf(a.key) - areaOrder.indexOf(b.key));
  const attentionArea = areas.find((area) => area.status === 'needs_attention');
  const updatedAt = overview?.generated_at && !Number.isNaN(Date.parse(overview.generated_at))
    ? new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(overview.generated_at)) : '';
  const openProblemLocation = (location: NonNullable<GrowthOverview['problem_locations']>[number]) => {
    onBusinessChange?.(location.business_id);
    onControlScopeChange?.({ kind: 'business', id: location.business_id, name: location.business_name });
    navigate(location.focus_action?.cta_url || screenRoute(location.focus_action?.screen));
  };
  const openAreaAction = (action: GrowthAction) => {
    if (action.target_scope?.kind === 'business' && action.target_scope.id) {
      const targetName = overview.location_breakdown?.find((location) => location.business_id === action.target_scope?.id)?.business_name || runtime.networkLocation;
      onBusinessChange?.(action.target_scope.id);
      onControlScopeChange?.({ kind: 'business', id: action.target_scope.id, name: targetName });
    }
    navigate(action.cta_url || screenRoute(action.screen));
  };

  if (!currentBusinessId) {
    return (
      <div className="space-y-6">
        <DashboardPageHeader title={copy.title} description={copy.selectBusinessDescription} />
      </div>
    );
  }

  if (loading && !overview) {
    return (
      <div className="space-y-6" aria-busy="true">
        <DashboardPageHeader title={copy.title} description={copy.loadingDescription} />
        <div className="h-36 animate-pulse rounded-xl bg-slate-100" />
        <div className="h-80 animate-pulse rounded-xl bg-slate-100" />
      </div>
    );
  }

  if (!overview) {
    return (
      <div className="space-y-6">
        <DashboardPageHeader title={copy.title} description={copy.fallbackDescription} />
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-700" />
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold text-amber-950">{copy.loadErrorTitle}</h2>
              <p className="mt-1 text-sm leading-6 text-amber-900">{localizedGrowthText(language, error) || copy.loadErrorDescription}</p>
              <Button type="button" variant="outline" className="mt-4 active:scale-[0.96] transition-transform" onClick={refreshAll}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {copy.retry}
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
        title={copy.title}
        description={copy.description}
        actions={(
          <Button type="button" variant="outline" onClick={refreshAll} disabled={loading} className="active:scale-[0.96] transition-transform">
            <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
            {copy.refresh}
          </Button>
        )}
      />

      {updatedAt ? <p className="text-xs tabular-nums text-muted-foreground">{copy.reportUpdated}: <time dateTime={overview.generated_at}>{updatedAt}</time></p> : null}

      {error ? <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="status">
        <span>{copy.staleData}</span>
        <Button type="button" variant="ghost" onClick={refreshAll}>{copy.retry}</Button>
      </div> : null}

      <section data-tour-target="progress-summary" aria-label={copy.title} className="rounded-xl border border-border bg-card px-4 py-5 md:px-6">
        <dl className="grid gap-5 sm:grid-cols-3">
          {[{ value: overview.summary.completed_last_30_days, label: copy.resultsIn30Days },
            { value: overview.summary.active_areas, label: copy.activeAreas },
            { value: overview.summary.needs_attention, label: copy.needAttention }].map((item) => <div key={item.label} className="flex items-center justify-between gap-3 sm:block">
              <dt className="text-sm text-muted-foreground sm:min-h-10">{item.label}</dt>
              <dd className="text-3xl font-semibold tabular-nums sm:mt-2">{item.value ?? '—'}</dd>
            </div>)}
        </dl>
        <details className="mt-5 border-t border-border pt-3" open={stagesOpen} onToggle={(event) => setStagesOpen(event.currentTarget.open)}>
          <summary className="min-h-11 cursor-pointer py-3 text-sm text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{copy.confirmedPath}</summary>
          {stagesOpen ? <div className="pb-2 text-sm">
            <p><strong className="tabular-nums">{overview.summary.completed_milestones} {copy.of} {overview.summary.total_milestones}</strong> {copy.confirmedSteps}</p>
            <Progress value={overview.summary.total_milestones > 0 ? 100 * overview.summary.completed_milestones / overview.summary.total_milestones : 0} className="mt-3 h-2" />
          </div> : null}
        </details>
      </section>

      {attentionArea ? <div data-tour-target="progress-focus-action" className="flex flex-wrap items-center justify-between gap-3 text-sm" role="status">
        <span className="flex items-center gap-2 text-amber-800"><AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {localizedGrowthArea(language, attentionArea.key, attentionArea.label)}: {localizedGrowthStatus(language, attentionArea.status, 'Нужно внимание')}
        </span>
        <Button type="button" variant="outline" className="min-h-11" onClick={() => { setExpandedArea(attentionArea.key); document.getElementById(`progress-area-${attentionArea.key}`)?.focus(); }}>
          {copy.inspectArea}<ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
        </Button>
      </div> : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card" aria-labelledby="progress-areas-title">
        <div className="border-b border-border px-4 py-4 md:px-6" data-tour-target="progress-areas">
          <h2 id="progress-areas-title" className="text-lg font-semibold">{copy.growthAreas}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{copy.growthAreasDescription}</p>
        </div>
        {areas.length ? areas.map((area) => <AreaRow key={area.key} area={area}
          expanded={expandedArea === area.key} onToggle={() => setExpandedArea((current) => current === area.key ? null : area.key)}
          onOpen={openAreaAction} language={language} copy={copy}
          details={area.key === 'maps' ? <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{mapAuditMilestone?.status === 'done' ? `${copy.auditReady}${mapAuditMilestone.achieved_at ? ` · ${formatDate(mapAuditMilestone.achieved_at, language)}` : ''}` : copy.auditPending}</p>
            {sourcesBlocked || area.status === 'unavailable' ? <p className="text-sm text-amber-800">{managedCopy.sourceBlocked}</p> : mapAuditMilestone?.status === 'done' ? (
              <Button type="button" variant="outline" className="min-h-11 w-full sm:w-auto" onClick={openFullAudit}>{copy.viewFullAudit}<ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" /></Button>
            ) : (area.action.cta_url || area.action.screen) ? (
              <Button type="button" variant="outline" className="min-h-11 w-full sm:w-auto" onClick={() => openAreaAction(area.action)}>{localizedGrowthText(language, area.action.cta_label)}<ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" /></Button>
            ) : null}
            {hasManagedCardGrowth ? <ManagedCardGrowthPanel embedded key={scopeKey} businessId={currentBusinessId} growth={overview} onUpdated={refreshAll} canEditGoal={scopeKind === 'business' && area.status !== 'unavailable'} /> : null}
          </div> : undefined}
        />) : <p className="px-4 py-5 text-sm text-muted-foreground md:px-6">{copy.noAreas}</p>}
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
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{copy.mapsAndReputation}</div>
              <h2 id="full-audit-title" className="mt-1 text-xl font-semibold text-balance">{copy.fullAudit}</h2>
              <p className="mt-1 text-sm leading-6 text-pretty text-slate-300">
                {selectedAuditLocation ? (
                  <span>{copy.location}: {localizedProgressBusinessName(language, selectedAuditLocation.name)}. </span>
                ) : null}
                <span>{copy.auditDescription}</span>
              </p>
            </div>
            <div className="flex items-center gap-2">
              {networkLocations.length > 1 ? (
                <Select value={selectedAuditBusinessId || networkLocations[0]?.id} onValueChange={setSelectedAuditBusinessId}>
                  <SelectTrigger className="min-h-10 w-full border-white/20 bg-white text-slate-950 md:w-[260px]" aria-label={copy.selectAuditLocation}>
                    <SelectValue placeholder={copy.selectLocation} />
                  </SelectTrigger>
                  <SelectContent>
                    {networkLocations.map((location) => (
                      <SelectItem key={location.id} value={location.id}>{localizedProgressBusinessName(language, location.name)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : null}
              <button
                type="button"
                onClick={closeFullAudit}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-slate-300 transition-[background-color,color,transform] hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 active:scale-[0.96]"
                aria-label={copy.hideFullAudit}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {parseStatus === 'queued' || parseStatus === 'processing' ? (
            <div className="flex items-center gap-2 rounded-lg bg-sky-50 px-4 py-3 text-sm text-sky-800" role="status">
              <RefreshCw className="h-4 w-4 motion-safe:animate-spin" />
              {parseStatus === 'queued' ? copy.parseQueued : copy.parseProcessing}
            </div>
          ) : null}

          {selectedManagedLocation?.providers.length ? (
            <section className="overflow-hidden rounded-xl border border-slate-200 bg-white" aria-label={managedCopy.auditState}>
              <div className="border-b border-slate-200 px-5 py-4 md:px-6">
                <h3 className="font-semibold text-slate-950">{managedCopy.auditState}</h3>
                <p className="mt-1 text-sm leading-6 text-slate-600">{managedCopy.auditDescription}</p>
              </div>
              <div className="divide-y divide-slate-200">
                {selectedManagedLocation.providers.map((provider) => (
                  <details key={provider.provider} className="px-5 py-4 md:px-6">
                    <summary className="flex min-h-10 cursor-pointer list-none items-center justify-between gap-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500">
                      <span className="font-semibold text-slate-950">{managedProviderLabel(provider.provider, provider.provider_label)}</span>
                      <span className="text-xs text-slate-500">{managedCopy.snapshot(formatDate(provider.observed_at, language) || managedCopy.snapshotMissing)}</span>
                    </summary>
                    <div className="mt-3 divide-y divide-slate-100 border-y border-slate-100">
                      {Object.entries(provider.facts).map(([factName, fact]) => (
                        <div key={factName} className="grid gap-1 py-3 text-sm md:grid-cols-[minmax(140px,0.45fr)_minmax(130px,0.35fr)_minmax(0,1fr)] md:gap-4">
                          <span className="font-medium text-slate-800">{managedFactLabel(language, factName)}</span>
                          <span className={fact.state === 'missing' || fact.state === 'blocked' ? 'text-amber-800' : 'text-slate-600'}>{managedStateLabel(language, fact.state)}</span>
                          <span className="text-slate-500">{managedEvidence(language, fact.evidence_code, fact.evidence) || `${managedCopy.source}: ${fact.source || managedProviderLabel(provider.provider, provider.provider_label)}`}</span>
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            </section>
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
              <span>{copy.cardHistory}</span>
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
          <h2 className="text-lg font-semibold text-slate-950">{copy.recentResults}</h2>
        </div>
        {recentAchievements.length > 0 ? (
          <div className="mt-4 divide-y divide-slate-100">
            {recentAchievements.map((item) => {
              const Icon = AREA_ICONS[item.area];
              return (
                <div key={item.key} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-slate-900">{localizedGrowthMilestone(language, item.key.split(':').pop() || '', item.title)}</div>
                    <div className="mt-0.5 text-sm leading-5 text-slate-600">{localizedGrowthText(language, item.description)}</div>
                  </div>
                  <div className="shrink-0 text-xs tabular-nums text-slate-400">{formatDate(item.occurred_at, language)}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-4 rounded-lg bg-slate-50 px-4 py-5 text-sm leading-6 text-slate-600">
            {copy.recentResultsEmpty}
          </div>
        )}
      </section>

      <details className="rounded-xl border border-border bg-card px-4 md:px-6" open={reportDataOpen} onToggle={(event) => setReportDataOpen(event.currentTarget.open)}>
        <summary className="min-h-11 cursor-pointer py-4 font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{copy.reportData}{' · '}<span className="ml-3 text-sm font-normal text-muted-foreground">{['fresh', 'due', 'ready'].includes(overview.data_health?.status || '') ? runtime.ready : overview.data_health?.status === 'stale' ? runtime.update : overview.data_health?.status === 'missing' ? runtime.needsData : '—'}</span></summary>
        {reportDataOpen ? <div className="space-y-4 border-t border-border py-4">
          <DataHealthRhythmStrip dataHealth={overview.data_health} onImport={() => navigate('/dashboard/finance?tab=import')} compact />
          {(overview.analytics_level?.label || overview.rhythm?.label) ? <p className="text-sm text-muted-foreground">{runtime.analytics}: {localizedAnalyticsLevel(language, overview.analytics_level?.level, overview.analytics_level?.label) || runtime.needsData} · {runtime.rhythm}: {localizedRhythm(language, overview.rhythm?.status, overview.rhythm?.label) || runtime.needsData}</p> : null}
          {overview.analytics_level?.next_unlock ? <p className="text-sm text-muted-foreground">{localizedAnalyticsNext(language, overview.analytics_level.level, overview.analytics_level.next_unlock)}</p> : null}
          {overview.analytics_modules?.length ? <ul className="space-y-2 text-sm text-muted-foreground">{overview.analytics_modules.map((module) => <li key={module.key || module.label}>{localizedAnalyticsModule(language, module.key, module.label)}: {module.status === 'ready' ? runtime.ready : module.status === 'available' ? runtime.update : runtime.needsData}</li>)}</ul> : null}
        </div> : null}
      </details>

      {scopeKind === 'network' ? <details className="rounded-xl border border-border bg-card px-4 md:px-6" open={networkOpen} onToggle={(event) => setNetworkOpen(event.currentTarget.open)}>
        <summary className="min-h-11 cursor-pointer py-4 font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{copy.networkDetails}</summary>
        {networkOpen ? <div className="space-y-4 border-t border-border py-4">
          {overview.network_summary ? <p className="text-sm text-muted-foreground">{overview.network_summary.locations_count} {runtime.networkLocations} · {overview.network_summary.problem_locations_count} {runtime.attention}</p> : null}
          {overview.problem_locations?.length ? <div className="flex flex-wrap gap-2">{overview.problem_locations.map((location) => <Button key={location.business_id} type="button" variant="outline" className="min-h-11 whitespace-normal text-left" onClick={() => openProblemLocation(location)}>{location.business_name}<ArrowRight className="ml-2 h-4 w-4 shrink-0" aria-hidden="true" /></Button>)}</div> : null}
          <NetworkDashboardPage embedded businessId={currentBusinessId} />
        </div> : null}
      </details> : null}

      <Button type="button" variant="outline" className="min-h-11" onClick={() => navigate('/dashboard/today')}>{copy.today}<ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" /></Button>
    </div>
  );
};
