import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useOutletContext } from 'react-router-dom';
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Check,
  Clipboard,
  ExternalLink,
  Globe2,
  History,
  Plug,
  RefreshCw,
  Route,
  Settings2,
  ShieldCheck,
} from 'lucide-react';

import { DashboardPageHeader, DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { WebAnalyticsInsights } from '@/components/web-analytics/WebAnalyticsInsights';
import { WebAnalyticsWorkspace } from '@/components/web-analytics/WebAnalyticsWorkspace';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useLanguage } from '@/i18n/LanguageContext';
import { formatWebAnalyticsCopy, getWebAnalyticsCopy, type WebAnalyticsCopy } from '@/i18n/webAnalyticsCopy';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type DashboardContext = {
  currentBusinessId?: string | null;
  currentBusiness?: { web_tracking_available?: boolean } | null;
};
type Tracker = {
  public_tracker_id: string;
  embed_code: string;
  status: 'working' | 'not_detected';
  last_event_at?: string | null;
  enabled: boolean;
  allowed_domains: string[];
};
type Totals = {
  visitors?: number;
  sessions?: number;
  page_views?: number;
  conversions?: number;
  previous_visitors?: number;
  previous_sessions?: number;
  previous_page_views?: number;
  previous_conversions?: number;
};
type Metrics = {
  totals: Totals;
  top_pages: Array<{ hostname?: string; path: string; title?: string | null; visitors: number; views: number; conversions: number; average_engagement_seconds: number }>;
  traffic_sources: Array<{ source: string; source_type?: string; sessions: number }>;
  conversions: Array<{ action: string; action_type?: string; count: number }>;
  top_paths: Array<{ path: string; sessions: number }>;
  sections: Array<{ hostname?: string; path: string; key: string; label: string; position: number; views: number; visitors: number; sessions: number; reach_percent: number; average_engagement_seconds: number; exits: number }>;
  funnel: { sessions: number; target_actions: number; requires_page_groups: boolean };
  funnel_v2?: { configured: boolean; stages: Array<{ key: string; label: string; sessions: number }> };
  cta_performance?: Array<{ cta_id: string; label?: string | null; impressions: number; clicks: number; ctr_percent: number }>;
  form_funnels?: Array<{ form_id: string; starts: number; validation_errors: number; attempts: number; successes: number; submit_errors: number }>;
  confirmed_outcomes?: Array<{ event_type: string; count: number; attributed: number; revenue: number | string; currency?: string | null }>;
  devices?: Array<{ device_type: string; sessions: number; visitors: number }>;
  visitor_cohorts?: { new_visitors?: number; returning_visitors?: number };
  recommendations?: Array<{ kind: string; title: string; detail: string }>;
};

const numberValue = (value: unknown) => {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
};

const formatNumber = (value: unknown, locale: string) => new Intl.NumberFormat(locale).format(numberValue(value));

const formatDuration = (seconds: unknown) => {
  const value = Math.max(0, Math.round(numberValue(seconds)));
  if (!value) return '—';
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
};

const Comparison = ({ current, previous, copy }: { current: unknown; previous: unknown; copy: WebAnalyticsCopy }) => {
  const currentValue = numberValue(current);
  const previousValue = numberValue(previous);
  if (!previousValue) return <span className="text-slate-400">{copy.noComparison}</span>;
  const difference = Math.round(((currentValue - previousValue) / previousValue) * 100);
  const positive = difference >= 0;
  const Icon = positive ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={cn('inline-flex items-center gap-1 tabular-nums', positive ? 'text-emerald-700' : 'text-rose-700')}>
      <Icon className="h-3.5 w-3.5" />{formatWebAnalyticsCopy(copy.comparison, { value: Math.abs(difference) })}
    </span>
  );
};

const Metric = ({ label, value, previous, copy }: { label: string; value: unknown; previous: unknown; copy: WebAnalyticsCopy }) => (
  <div className="rounded-2xl bg-white px-5 py-4 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_3px_8px_rgba(15,23,42,0.04)]">
    <div className="text-sm font-medium text-slate-500">{label}</div>
    <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 tabular-nums">{formatNumber(value, copy.locale)}</div>
    <div className="mt-2 text-xs"><Comparison current={value} previous={previous} copy={copy} /></div>
  </div>
);

export const WebAnalyticsPage = () => {
  const { language } = useLanguage();
  const copy = getWebAnalyticsCopy(language);
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const [period, setPeriod] = useState(30);
  const [activeView, setActiveView] = useState('overview');
  const [tracker, setTracker] = useState<Tracker | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [domainDraft, setDomainDraft] = useState('');
  const [savingDomains, setSavingDomains] = useState(false);
  const requestSequence = useRef(0);

  const load = useCallback(async (showCheck = false) => {
    if (!currentBusinessId || currentBusiness?.web_tracking_available !== true) return;
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    if (showCheck) setChecking(true);
    else setLoading(true);
    setError('');
    try {
      const trackerResponse = await newAuth.makeRequest(`/business/${currentBusinessId}/web-tracking`);
      const metricsResponse = await newAuth.makeRequest(`/business/${currentBusinessId}/web-analytics?period=${period}`);
      if (requestSequence.current !== requestId) return;
      setTracker(trackerResponse.tracker || null);
      setDomainDraft((trackerResponse.tracker?.allowed_domains || []).join(', '));
      setMetrics(metricsResponse.metrics || null);
    } catch (loadError) {
      if (requestSequence.current !== requestId) return;
      setError(loadError instanceof Error ? loadError.message : copy.loadError);
    } finally {
      if (requestSequence.current === requestId) {
        setLoading(false);
        setChecking(false);
      }
    }
  }, [copy.loadError, currentBusinessId, currentBusiness?.web_tracking_available, period]);

  useEffect(() => { void load(); }, [load]);

  const copyCode = async () => {
    if (!tracker?.embed_code) return;
    try {
      await navigator.clipboard.writeText(tracker.embed_code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError(copy.copyError);
    }
  };

  const saveDomains = async () => {
    if (!currentBusinessId) return;
    const allowedDomains = domainDraft.split(',').map((item) => item.trim()).filter(Boolean);
    setSavingDomains(true);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/business/${currentBusinessId}/web-tracking`, {
        method: 'POST',
        body: JSON.stringify({ allowed_domains: allowedDomains }),
      });
      setTracker(response.tracker || null);
      setDomainDraft((response.tracker?.allowed_domains || []).join(', '));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveError);
    } finally {
      setSavingDomains(false);
    }
  };

  const maxSourceSessions = useMemo(
    () => Math.max(1, ...(metrics?.traffic_sources || []).map((item) => numberValue(item.sessions))),
    [metrics],
  );
  const totals = metrics?.totals || {};
  const working = tracker?.status === 'working';

  if (currentBusiness?.web_tracking_available !== true) {
    return <Navigate to="/dashboard/progress" replace />;
  }

  if (!currentBusinessId) {
    return <div className="py-12 text-center text-sm text-slate-500">{copy.selectBusiness}</div>;
  }

  return (
    <div className="space-y-6 pb-10">
      <DashboardPageHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        icon={BarChart3}
        actions={(
          <div className="inline-flex rounded-xl bg-slate-100 p-1 shadow-inner">
            {[7, 30, 90].map((days) => (
              <button
                key={days}
                type="button"
                onClick={() => setPeriod(days)}
                className={cn(
                  'min-h-10 rounded-lg px-3 text-sm font-semibold transition-[background-color,color,box-shadow,transform] duration-150 active:scale-[0.96]',
                  period === days ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800',
                )}
              >
                {formatWebAnalyticsCopy(copy.periodDays, { days })}
              </button>
            ))}
          </div>
        )}
      />

      {error ? <div role="alert" className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800 ring-1 ring-rose-200">{error}</div> : null}

      <nav aria-label="Разделы аналитики" className="flex gap-1 overflow-x-auto rounded-2xl bg-slate-100 p-1 shadow-inner">
        {[
          { key: 'overview', label: 'Результаты', icon: BarChart3 },
          { key: 'setup', label: 'Цели сайта', icon: Settings2 },
          { key: 'changes', label: 'Изменения', icon: History },
          { key: 'integration', label: 'Подключения', icon: Plug },
        ].map((item) => {
          const Icon = item.icon;
          return <button key={item.key} type="button" onClick={() => setActiveView(item.key)} className={cn('flex min-h-11 shrink-0 items-center gap-2 rounded-xl px-4 text-sm font-semibold transition-[background-color,color,box-shadow,transform] duration-150 active:scale-[0.96]', activeView === item.key ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800')}><Icon className="h-4 w-4" />{item.label}</button>;
        })}
      </nav>

      {activeView === 'overview' ? <>

      <DashboardSection
        title={working ? copy.workingTitle : copy.connectTitle}
        description={working
          ? copy.workingDescription
          : copy.connectDescription}
        actions={(
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn('inline-flex min-h-10 items-center gap-2 rounded-xl px-3 text-sm font-semibold', working ? 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600')}>
              <Activity className="h-4 w-4" />{working ? copy.statusWorking : copy.statusNotDetected}
            </span>
            <Button variant="outline" onClick={() => void load(true)} disabled={checking}>
              <RefreshCw className={cn('h-4 w-4', checking && 'animate-spin')} />{copy.checkConnection}
            </Button>
          </div>
        )}
      >
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="min-w-0">
            <div className="mb-4 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <label htmlFor="web-tracking-domains" className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <Globe2 className="h-4 w-4 text-slate-500" />{copy.allowedDomains}
              </label>
              <p className="mt-1 text-sm leading-6 text-slate-600">{copy.domainsDescription}</p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <Input
                  id="web-tracking-domains"
                  value={domainDraft}
                  onChange={(event) => setDomainDraft(event.target.value)}
                  placeholder={copy.domainPlaceholder}
                  className="min-h-10 flex-1 bg-white"
                />
                <Button variant="outline" onClick={() => void saveDomains()} disabled={savingDomains}>
                  {savingDomains ? <RefreshCw className="animate-spin" /> : <Check />}{savingDomains ? copy.savingDomains : copy.saveDomains}
                </Button>
              </div>
            </div>
            <div className="overflow-x-auto rounded-2xl bg-slate-950 p-4 shadow-inner">
              <code className="block min-w-max whitespace-pre-wrap break-all font-mono text-sm leading-6 text-slate-100">{tracker?.embed_code || (loading ? copy.preparingCode : '')}</code>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button onClick={() => void copyCode()} disabled={!tracker?.embed_code}>
                {copied ? <Check /> : <Clipboard />}{copied ? copy.codeCopied : copy.copyCode}
              </Button>
            </div>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900"><ShieldCheck className="h-4 w-4 text-emerald-600" />{copy.privacyTitle}</div>
            <p className="mt-2 text-sm leading-6 text-slate-600">{copy.privacyDescription}</p>
            <div className="mt-3 text-xs text-slate-500 tabular-nums">
              {copy.lastEvent}: {tracker?.last_event_at ? new Date(tracker.last_event_at).toLocaleString(copy.locale) : copy.noEventsYet}
            </div>
          </div>
        </div>
      </DashboardSection>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-busy={loading}>
        <Metric label={copy.visitors} value={totals.visitors} previous={totals.previous_visitors} copy={copy} />
        <Metric label={copy.sessions} value={totals.sessions} previous={totals.previous_sessions} copy={copy} />
        <Metric label={copy.pageViews} value={totals.page_views} previous={totals.previous_page_views} copy={copy} />
        <Metric label={copy.targetActions} value={totals.conversions} previous={totals.previous_conversions} copy={copy} />
      </div>

      <WebAnalyticsInsights metrics={metrics} locale={copy.locale} />

      <div className="grid gap-6 xl:grid-cols-2">
        <DashboardSection title={copy.sourcesTitle} description={copy.sourcesDescription}>
          {(metrics?.traffic_sources || []).length ? (
            <div className="space-y-4">
              {metrics?.traffic_sources.map((item) => (
                <div key={item.source}>
                  <div className="flex items-center justify-between gap-4 text-sm"><span className="font-medium text-slate-700">{copy.sourceLabels[item.source] || item.source}</span><span className="tabular-nums text-slate-500">{formatNumber(item.sessions, copy.locale)}</span></div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-slate-800" style={{ width: `${Math.max(4, (numberValue(item.sessions) / maxSourceSessions) * 100)}%` }} /></div>
                </div>
              ))}
            </div>
          ) : <p className="py-8 text-center text-sm text-slate-500">{copy.sourcesEmpty}</p>}
        </DashboardSection>

        <DashboardSection title={copy.actionsTitle} description={copy.actionsDescription}>
          {(metrics?.conversions || []).length ? (
            <div className="divide-y divide-slate-100">
              {metrics?.conversions.map((item) => (
                <div key={`${item.action_type || item.action}-${item.action}`} className="flex min-h-12 items-center justify-between gap-4 py-2"><span className="flex items-center gap-2 text-sm font-medium text-slate-700"><ExternalLink className="h-4 w-4 text-slate-400" />{copy.actionLabels[item.action_type || item.action] || item.action}</span><span className="text-lg font-semibold text-slate-950 tabular-nums">{formatNumber(item.count, copy.locale)}</span></div>
              ))}
            </div>
          ) : <p className="py-8 text-center text-sm text-slate-500">{copy.actionsEmpty}</p>}
        </DashboardSection>
      </div>

      <DashboardSection title={copy.pagesTitle} description={copy.pagesDescription} contentClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-[0.12em] text-slate-500"><tr><th className="px-6 py-3">{copy.pageColumn}</th><th className="px-4 py-3 text-right">{copy.visitorsColumn}</th><th className="px-4 py-3 text-right">{copy.viewsColumn}</th><th className="px-4 py-3 text-right">{copy.engagementColumn}</th><th className="px-6 py-3 text-right">{copy.actionsColumn}</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {(metrics?.top_pages || []).map((item) => <tr key={`${item.hostname || ''}${item.path}`}><td className="px-6 py-4"><div className="font-medium text-slate-900">{item.title || item.path}</div><div className="mt-1 text-xs text-slate-400">{item.hostname ? `${item.hostname}${item.path}` : item.path}</div></td><td className="px-4 py-4 text-right tabular-nums">{formatNumber(item.visitors, copy.locale)}</td><td className="px-4 py-4 text-right tabular-nums">{formatNumber(item.views, copy.locale)}</td><td className="px-4 py-4 text-right tabular-nums">{formatDuration(item.average_engagement_seconds)}</td><td className="px-6 py-4 text-right tabular-nums">{formatNumber(item.conversions, copy.locale)}</td></tr>)}
            </tbody>
          </table>
          {!metrics?.top_pages.length ? <p className="px-6 py-10 text-center text-sm text-slate-500">{copy.pagesEmpty}</p> : null}
        </div>
      </DashboardSection>

      <DashboardSection title={copy.sectionsTitle} description={copy.sectionsDescription} contentClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-[0.12em] text-slate-500"><tr><th className="px-6 py-3">{copy.sectionColumn}</th><th className="px-4 py-3 text-right">{copy.reachColumn}</th><th className="px-4 py-3 text-right">{copy.viewsColumn}</th><th className="px-4 py-3 text-right">{copy.engagementColumn}</th><th className="px-6 py-3 text-right">{copy.exitsColumn}</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {(metrics?.sections || []).map((item) => (
                <tr key={`${item.hostname || ''}${item.path}-${item.key}`}>
                  <td className="px-6 py-4"><div className="font-medium text-slate-900">{item.label || item.key}</div><div className="mt-1 text-xs text-slate-400">{item.hostname ? `${item.hostname}${item.path}` : item.path}</div></td>
                  <td className="px-4 py-4 text-right font-medium text-slate-700 tabular-nums">{formatNumber(item.reach_percent, copy.locale)}%</td>
                  <td className="px-4 py-4 text-right tabular-nums">{formatNumber(item.views, copy.locale)}</td>
                  <td className="px-4 py-4 text-right tabular-nums">{formatDuration(item.average_engagement_seconds)}</td>
                  <td className="px-6 py-4 text-right tabular-nums">{formatNumber(item.exits, copy.locale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!metrics?.sections?.length ? <p className="px-6 py-10 text-center text-sm text-slate-500">{copy.sectionsEmpty}</p> : null}
        </div>
      </DashboardSection>

      <DashboardSection title={copy.pathsTitle} description={copy.pathsDescription}>
        {(metrics?.top_paths || []).length ? <div className="grid gap-2 lg:grid-cols-2">{metrics?.top_paths.map((item) => <div key={item.path} className="flex gap-3 rounded-xl bg-slate-50 px-4 py-3"><Route className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" /><div className="min-w-0 flex-1"><div className="text-sm font-medium leading-6 text-slate-800">{item.path}</div><div className="mt-1 text-xs text-slate-500 tabular-nums">{formatWebAnalyticsCopy(copy.sessionsCount, { value: formatNumber(item.sessions, copy.locale) })}</div></div></div>)}</div> : <p className="py-8 text-center text-sm text-slate-500">{copy.pathsEmpty}</p>}
      </DashboardSection>
      </> : <WebAnalyticsWorkspace businessId={currentBusinessId} mode={activeView === 'changes' ? 'changes' : activeView === 'integration' ? 'integration' : 'setup'} onChanged={() => void load(true)} />}
    </div>
  );
};

export default WebAnalyticsPage;
