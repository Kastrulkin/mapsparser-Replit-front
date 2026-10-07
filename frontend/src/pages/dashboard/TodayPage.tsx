import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { ArrowRight, Bot, CheckCircle2, Clock3, Radio, RefreshCw, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { DashboardEmptyState, DashboardPageHeader, DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';
import type { ControlScope } from '@/components/DashboardLayout';
import { useLanguage, type Language } from '@/i18n/LanguageContext';
import { fillTodayTemplate, getTodayPageCopy, type TodayPageCopy } from '@/i18n/todayPageCopy';
import { clearLeadJourneyIntent, getLeadJourneyDirection, readLeadJourneyIntent, readLeadJourneyToken, resolveStoredLeadJourney } from '@/lib/leadJourney';
import { localizedFocusAction, localizedGrowthText } from './progressPageCopy';
import { JourneyActionCard } from '@/components/journey/JourneyActionCard';
import { featureFlags } from '@/config/featureFlags';
import type { JourneyAction } from '@/lib/leadJourney';

type DashboardContext = { currentBusinessId?: string | null; controlScope?: ControlScope | null; onControlScopeChange?: (scope: ControlScope) => void; onBusinessChange?: (businessId: string) => void };

type Mission = { id?: string; title: string; reason: string; expected_outcome: string; cta_label: string; screen?: string; cta_url?: string; target_scope?: { kind?: string; id?: string } };
type TodayItem = { id: string; title: string; description?: string; stage?: string; source?: string; occurred_at?: string; progress?: number | null; screen?: string; business_id?: string; business_name?: string };
type ProblemLocation = { business_id: string; business_name: string; problem?: string; data_health_status?: string; focus_action?: Mission | null };
type TodayOverview = {
  focus_action?: Mission | null;
  journey_actions?: JourneyAction[];
  data_health?: { status?: string; source?: string; source_label?: string; source_updated_at?: string | null; updated_at?: string | null; last_updated_at?: string | null; stale?: boolean; is_stale?: boolean; missing?: string[] } | null;
  active_work?: TodayItem[];
  changes_24h?: TodayItem[];
  community_pulse?: TodayItem[];
  completed_results?: TodayItem[];
  network_summary?: { locations_count?: number; problem_locations_count?: number; healthy_locations_count?: number; finance?: { missing?: number; stale?: number; due?: number; fresh?: number } } | null;
  problem_locations?: ProblemLocation[];
  data_rhythm?: { status?: string; coverage?: number; completed_periods_8w?: number; next_due_at?: string | null } | null;
  analytics_modules?: Array<{ key?: string; label?: string; status?: string; next_unlock?: string | null }>;
};

const screenRoute = (screen?: string) => ({
  cards: '/dashboard/card', reviews: '/dashboard/card?tab=reviews', content: '/dashboard/content', services: '/dashboard/card?tab=services', finance: '/dashboard/finance', partnerships: '/dashboard/partnerships', agents: '/dashboard/agents', settings: '/dashboard/settings', progress: '/dashboard/progress', operator: '/dashboard/operator',
}[screen || ''] || '/dashboard/progress');

const missionRoute = (mission?: Mission | null) => {
  if (mission?.screen) return screenRoute(mission.screen);
  if (mission?.cta_url?.startsWith('/dashboard/')) return mission.cta_url;
  return '/dashboard/progress';
};

const missionCopy = (language: Language, mission: Mission | null | undefined, copy: TodayPageCopy) => {
  if (!mission) return null;
  if (mission.id === 'growth:finance' || mission.title === 'Обновите финансовые данные') {
    return {
      ...mission,
      title: copy.financeTitle,
      reason: copy.financeReason,
      expected_outcome: copy.financeOutcome,
      cta_label: copy.uploadData,
    };
  }
  return {
    ...mission,
    title: localizedFocusAction(language, mission.id, 'title', mission.title),
    reason: localizedFocusAction(language, mission.id, 'reason', mission.reason),
    expected_outcome: localizedFocusAction(language, mission.id, 'outcome', mission.expected_outcome),
    cta_label: localizedFocusAction(language, mission.id, 'cta', mission.cta_label),
  };
};

const analyticsModuleLabels: Record<Language, Record<string, string>> = {
  ru: { sales: 'Продажи и средний чек', services: 'Услуги и допродажи', capacity: 'Загрузка команды' },
  en: { sales: 'Sales and average sale', services: 'Services and upsells', capacity: 'Team capacity' },
  fr: { sales: 'Ventes et panier moyen', services: 'Services et ventes additionnelles', capacity: 'Charge de l’équipe' },
  es: { sales: 'Ventas y ticket medio', services: 'Servicios y ventas adicionales', capacity: 'Ocupación del equipo' },
  el: { sales: 'Πωλήσεις και μέση αξία συναλλαγής', services: 'Υπηρεσίες και πρόσθετες πωλήσεις', capacity: 'Φόρτος ομάδας' },
  de: { sales: 'Umsatz und Durchschnittsbon', services: 'Leistungen und Zusatzverkäufe', capacity: 'Teamauslastung' },
  th: { sales: 'ยอดขายและยอดเฉลี่ย', services: 'บริการและการขายเพิ่ม', capacity: 'ความหนาแน่นของทีม' },
  ar: { sales: 'المبيعات ومتوسط الفاتورة', services: 'الخدمات والمبيعات الإضافية', capacity: 'إشغال الفريق' },
  ha: { sales: 'Tallace-tallace da matsakaicin sayayya', services: 'Ayyuka da ƙarin sayarwa', capacity: 'Yawan aikin ma’aikata' },
  tr: { sales: 'Satışlar ve ortalama sepet', services: 'Hizmetler ve ek satışlar', capacity: 'Ekip kapasitesi' },
};

const analyticsLabel = (language: Language, copy: TodayPageCopy, key?: string, fallback?: string) => {
  if (key === 'trend') return copy.trend;
  if (key && analyticsModuleLabels[language][key]) return analyticsModuleLabels[language][key];
  return fallback || copy.analytics;
};

const analyticsStatus = (copy: TodayPageCopy, status?: string) => {
  if (status === 'ready') return copy.ready;
  if (status === 'available') return copy.updateSummary;
  return copy.uploadSummary;
};

const dataSourceLabel = (copy: TodayPageCopy, source?: string) => {
  if (!source || source === 'unknown') return copy.unknownSource;
  return source;
};

const resultSourceLabel = (copy: TodayPageCopy, source?: string) => {
  if (source === 'Прогресс LocalOS') return copy.resultHistory;
  return source;
};

const localeByLanguage: Record<Language, string> = { ru: 'ru-RU', en: 'en-GB', fr: 'fr-FR', es: 'es-ES', el: 'el-GR', de: 'de-DE', th: 'th-TH', ar: 'ar', ha: 'ha-NG', tr: 'tr-TR' };

const formatDate = (language: Language, value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : new Intl.DateTimeFormat(localeByLanguage[language], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date);
};

export const TodayPage = () => {
  const navigate = useNavigate();
  const { language } = useLanguage();
  const copy = getTodayPageCopy(language);
  const { currentBusinessId, controlScope, onControlScopeChange, onBusinessChange } = useOutletContext<DashboardContext>();
  const [overview, setOverview] = useState<TodayOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [journeyIntent, setJourneyIntent] = useState(() => readLeadJourneyIntent());
  const requestSequence = useRef(0);

  const load = () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    if (!currentBusinessId) {
      setOverview(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(false);
    const params = new URLSearchParams({ scope_type: controlScope?.kind || 'business', scope_id: controlScope?.id || currentBusinessId });
    let request: Promise<TodayOverview>;
    try {
      request = newAuth.makeRequest(`/operator/today?${params.toString()}`, { method: 'GET' });
    } catch {
      if (requestSequence.current === requestId) {
        setError(true);
        setLoading(false);
      }
      return;
    }
    void request
      .then((data: TodayOverview) => {
        if (requestSequence.current === requestId) setOverview(data);
      })
      .catch(() => {
        if (requestSequence.current === requestId) setError(true);
      })
      .finally(() => {
        if (requestSequence.current === requestId) setLoading(false);
      });
  };

  useEffect(() => { load(); }, [currentBusinessId, controlScope?.id, controlScope?.kind]);

  useEffect(() => {
    if (!featureFlags.journeyPostAuthRedirect || !currentBusinessId) return;
    const token = readLeadJourneyToken();
    if (!token) return;
    void resolveStoredLeadJourney(currentBusinessId)
      .then((resolved) => {
        if (resolved) {
          setJourneyIntent(null);
          navigate(resolved.route, { replace: true });
        }
      })
      .catch(() => {
        // Keep the token so a temporary API or connectivity failure can be retried.
      });
  }, [currentBusinessId]);

  const openItem = (itemMission?: Mission | null, businessId?: string, businessName?: string) => {
    if (businessId && controlScope?.kind === 'network') {
      onBusinessChange?.(businessId);
      onControlScopeChange?.({ kind: 'business', id: businessId, name: businessName || copy.locationName });
    }
    navigate(missionRoute(itemMission));
  };

  const openMission = () => {
    const target = mission?.target_scope;
    if (target?.kind === 'business' && target.id) {
      onBusinessChange?.(target.id);
      onControlScopeChange?.({ kind: 'business', id: target.id, name: copy.locationName });
    }
    navigate(missionRoute(mission));
  };

  const mission = missionCopy(language, overview?.focus_action, copy);
  const journeyActions = overview?.journey_actions || [];
  const journeyDirection = getLeadJourneyDirection(journeyIntent);
  const activeWork = useMemo(() => (overview?.active_work || []).slice(0, 3), [overview?.active_work]);
  const changes = overview?.changes_24h?.slice(0, 3) || [];
  const completedResults = overview?.completed_results?.slice(0, 3) || [];
  const communityPulse = overview?.community_pulse?.slice(0, 2) || [];
  const networkSummary = overview?.network_summary;
  const problemLocations = overview?.problem_locations?.slice(0, 5) || [];
  const dataRhythm = overview?.data_rhythm;
  const analyticsModules = overview?.analytics_modules || [];
  const dataHealth = overview?.data_health;
  const dataNeedsAttention = Boolean(['missing', 'stale', 'due'].includes(dataHealth?.status || '') || dataHealth?.stale || dataHealth?.is_stale || dataHealth?.missing?.length);

  if (!currentBusinessId) return <DashboardEmptyState title={copy.selectBusiness} description={copy.selectBusinessHint} />;

  if (loading && !overview) {
    return <div className="space-y-6" aria-busy="true" data-tour-target="today-overview"><DashboardPageHeader eyebrow="LocalOS" title={copy.title} description={copy.loading} /><div className="h-44 animate-pulse rounded-3xl bg-slate-100" /><div className="h-72 animate-pulse rounded-3xl bg-slate-100" /></div>;
  }

  if (error && !overview) {
    return <div className="space-y-6" data-tour-target="today-overview"><DashboardPageHeader eyebrow="LocalOS" title={copy.title} description={copy.loadError} /><DashboardEmptyState title={copy.unavailable} description={copy.retryHint} action={<Button type="button" onClick={load} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className="h-4 w-4" />{copy.retry}</Button>} /></div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-10" data-tour-target="today-overview">
      <DashboardPageHeader eyebrow={controlScope?.kind === 'network' ? copy.networkEyebrow : 'LocalOS'} title={copy.title} description={copy.description} icon={Clock3} actions={<Button type="button" variant="outline" onClick={load} disabled={loading} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />{copy.refresh}</Button>} />

      {journeyDirection && !journeyActions.length ? (
        <section className="rounded-3xl border border-orange-200 bg-orange-50 p-5 shadow-sm sm:p-6">
          <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
            <div><div className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">Вы выбрали до регистрации</div><h2 className="mt-2 text-balance text-xl font-semibold text-slate-950">{journeyDirection.resultTitle}</h2><p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-600">Продолжите с готового первого действия. После него LocalOS зафиксирует статус или результат и предложит следующий конкретный шаг.</p></div>
            <Button type="button" onClick={() => { clearLeadJourneyIntent(); setJourneyIntent(null); navigate(journeyDirection.dashboardRoute); }} className="min-h-11 gap-2">Завершить действие<ArrowRight className="h-4 w-4" /></Button>
          </div>
        </section>
      ) : null}

      {journeyActions.length ? <section aria-label="Текущие действия" className="space-y-3">{journeyActions.slice(0, 3).map((action) => <JourneyActionCard key={action.id} action={action} businessId={currentBusinessId} onUpdated={load} />)}</section> : <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)] lg:items-center">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">{copy.now}</div>
            <h2 className="mt-2 text-balance text-2xl font-semibold text-slate-950">{mission?.title || copy.openTasks}</h2>
            <p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-600">{mission?.reason || copy.noUrgent}</p>
            {mission ? <div className="mt-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"><strong>{copy.after}</strong> {mission.expected_outcome}</div> : null}
          </div>
          <Button type="button" onClick={openMission} className="min-h-11 w-full gap-2 transition-transform active:scale-[0.96] lg:w-auto lg:justify-self-end">{mission?.cta_label || copy.openProgress}<ArrowRight className="h-4 w-4" /></Button>
        </div>
      </section>}

      <div className="grid gap-2 rounded-2xl bg-slate-50 p-3 text-xs text-slate-600 sm:grid-cols-3" aria-label="Рабочий цикл LocalOS">
        <span className="rounded-xl bg-white px-3 py-2"><strong className="block text-slate-950">1. Действие</strong>Выполните или подтвердите готовый шаг.</span>
        <span className="rounded-xl bg-white px-3 py-2"><strong className="block text-slate-950">2. Статус или результат</strong>LocalOS проверит, что произошло.</span>
        <span className="rounded-xl bg-white px-3 py-2"><strong className="block text-slate-950">3. Следующий шаг</strong>Получите конкретное продолжение по факту.</span>
      </div>

      {controlScope?.kind === 'network' && networkSummary ? (
        <DashboardSection title={copy.locationsTitle} description={copy.locationsHint}>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 px-4 py-3"><strong className="block text-2xl tabular-nums text-slate-950">{networkSummary.locations_count || 0}</strong><span className="text-sm text-slate-600">{copy.locations}</span></div>
            <div className="rounded-2xl bg-emerald-50 px-4 py-3"><strong className="block text-2xl tabular-nums text-emerald-800">{networkSummary.healthy_locations_count || 0}</strong><span className="text-sm text-emerald-900">{copy.healthy}</span></div>
            <div className="rounded-2xl bg-amber-50 px-4 py-3"><strong className="block text-2xl tabular-nums text-amber-800">{networkSummary.problem_locations_count || 0}</strong><span className="text-sm text-amber-900">{copy.attention}</span></div>
          </div>
          {problemLocations.length ? <div className="mt-4 divide-y divide-slate-100">{problemLocations.map((location) => (
            <button key={location.business_id} type="button" onClick={() => openItem(location.focus_action, location.business_id, location.business_name)} className="flex min-h-16 w-full items-center gap-3 py-3 text-left transition-transform active:scale-[0.96]">
              <span className="min-w-0 flex-1"><strong className="block text-sm text-slate-950">{location.business_name}</strong><span className="mt-1 block text-pretty text-sm text-slate-600">{location.problem ? localizedGrowthText(language, location.problem) : copy.locationAttention}</span></span>
              <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" />
            </button>
          ))}</div> : <p className="mt-4 text-sm text-emerald-800">{copy.allHealthy}</p>}
        </DashboardSection>
      ) : null}

      {dataRhythm || analyticsModules.length ? (
        <DashboardSection title={copy.dataTitle} description={copy.dataHint}>
          {dataRhythm ? <div className="rounded-2xl bg-slate-50 px-4 py-3"><div className="flex items-center justify-between gap-3 text-sm"><span className="text-slate-600">{copy.coverage}</span><strong className="tabular-nums text-slate-950">{dataRhythm.coverage || 0}%</strong></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-orange-500" style={{ width: `${Math.min(100, Math.max(0, dataRhythm.coverage || 0))}%` }} /></div><p className="mt-2 text-sm text-slate-600">{fillTodayTemplate(copy.summaries, { count: dataRhythm.completed_periods_8w || 0 })}{formatDate(language, dataRhythm.next_due_at) ? ` · ${fillTodayTemplate(copy.nextSummary, { date: formatDate(language, dataRhythm.next_due_at) || '' })}` : ''}</p></div> : null}
          {analyticsModules.length ? <div className="mt-3 flex flex-wrap gap-2">{analyticsModules.map((module) => <span key={module.key || module.label} className={cn('rounded-full px-3 py-1.5 text-sm', module.status === 'ready' ? 'bg-emerald-50 text-emerald-800' : module.status === 'available' ? 'bg-amber-50 text-amber-900' : 'bg-slate-100 text-slate-600')}>{analyticsLabel(language, copy, module.key, module.label)}: {analyticsStatus(copy, module.status)}</span>)}</div> : null}
        </DashboardSection>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <DashboardSection title={copy.changesTitle} description={copy.changesHint}>
          {changes.length ? <div className="divide-y divide-slate-100">{changes.map((item) => <div key={item.id} className="flex gap-3 py-3 first:pt-0 last:pb-0"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><div className="font-medium text-slate-950">{localizedGrowthText(language, item.title)}</div><p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{localizedGrowthText(language, item.description)}</p>{formatDate(language, item.occurred_at) ? <div className="mt-1 text-xs tabular-nums text-slate-400">{formatDate(language, item.occurred_at)}</div> : null}</div></div>)}</div> : <p className="text-sm leading-6 text-slate-600">{copy.noChanges}</p>}
        </DashboardSection>

        <DashboardSection title={copy.workTitle} description={copy.workHint}>
          {activeWork.length ? <div className="space-y-3">{activeWork.map((item) => <button key={item.id} type="button" onClick={() => openItem({ title: item.title, reason: '', expected_outcome: '', cta_label: '', screen: item.screen }, item.business_id, item.business_name)} className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-left transition-transform active:scale-[0.96]"><div className="flex items-start gap-2"><Bot className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><div className="min-w-0 flex-1"><div className="font-medium text-slate-950">{localizedGrowthText(language, item.title)}</div><p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{[item.business_name, localizedGrowthText(language, item.stage || item.description)].filter(Boolean).join(' · ')}</p></div>{item.progress == null ? null : <span className="text-sm tabular-nums text-slate-500">{item.progress}%</span>}</div></button>)}</div> : <p className="text-sm leading-6 text-slate-600">{copy.noWork}</p>}
        </DashboardSection>
      </div>

      {completedResults.length ? <DashboardSection title={copy.readyTitle} description={copy.readyHint}><div className="divide-y divide-slate-100">{completedResults.map((item) => <div key={item.id} className="flex gap-3 py-3 first:pt-0 last:pb-0"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><div className="font-medium text-slate-950">{localizedGrowthText(language, item.title)}</div>{item.description ? <p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{localizedGrowthText(language, item.description)}</p> : null}{item.source ? <div className="mt-1 text-xs text-slate-500">{copy.source} {resultSourceLabel(copy, item.source)}</div> : null}</div></div>)}</div></DashboardSection> : null}

      {communityPulse.length ? <DashboardSection title={copy.pulseTitle} description={copy.pulseHint}><div className="space-y-3">{communityPulse.map((item) => <div key={item.id} className="flex gap-3 rounded-2xl bg-slate-50 px-4 py-3"><Radio className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><div className="min-w-0"><div className="font-medium text-slate-950">{item.title}</div>{item.description ? <p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.description}</p> : null}{item.source ? <div className="mt-1 text-xs text-slate-500">{copy.source} {item.source}</div> : null}</div></div>)}</div></DashboardSection> : null}

      {dataHealth ? <div className={cn('flex items-start gap-3 rounded-2xl px-4 py-3 text-sm shadow-[0_0_0_1px_rgba(15,23,42,0.08)]', dataNeedsAttention ? 'bg-amber-50 text-amber-950' : 'bg-slate-50 text-slate-700')}><TriangleAlert className={cn('mt-0.5 h-5 w-5 shrink-0', dataNeedsAttention ? 'text-amber-700' : 'text-slate-500')} /><div><span className="font-semibold">{copy.financeSource}</span> {localizedGrowthText(language, dataSourceLabel(copy, dataHealth.source_label || dataHealth.source))}{formatDate(language, dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at) ? <span className="tabular-nums"> · {fillTodayTemplate(copy.updated, { date: formatDate(language, dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at) || '' })}</span> : null}{dataNeedsAttention && dataHealth.missing?.length ? <span> · {fillTodayTemplate(copy.add, { items: dataHealth.missing.map((item) => localizedGrowthText(language, item)).join(', ') })}</span> : null}</div></div> : null}

      <DashboardSection title={copy.allTasksTitle} description={copy.allTasksHint}>
        <Button type="button" variant="outline" onClick={() => navigate('/dashboard/progress')} className="min-h-11 gap-2 transition-transform active:scale-[0.96]">{copy.openProgress}<ArrowRight className="h-4 w-4" /></Button>
      </DashboardSection>
    </div>
  );
};
