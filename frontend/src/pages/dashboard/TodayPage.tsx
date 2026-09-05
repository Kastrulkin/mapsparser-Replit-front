import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { ArrowRight, Bot, CheckCircle2, ChevronDown, Clock3, Radio, RefreshCw, TriangleAlert } from 'lucide-react';

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

type Mission = { id?: string; title: string; reason: string; expected_outcome: string; cta_label: string; screen?: string; cta_url?: string; plan_id?: string; item_id?: string; target_scope?: { kind?: string; id?: string } };
type TodayItem = { id: string; title: string; description?: string; stage?: string; source?: string; occurred_at?: string; progress?: number | null; screen?: string; business_id?: string; business_name?: string; flow?: TodayPreference['primary_flow']; urgency?: 'urgent' | 'normal'; due_at?: string | null; preview?: string | null; action?: { label?: string; url?: string }; freshness?: { as_of?: string; status?: string }; reason_code?: string; message_code?: string; params?: Record<string, unknown> };
type TodayPreference = {
  scope_type: 'business' | 'network';
  scope_id: string;
  primary_flow: 'overview' | 'content' | 'influencers' | 'partnerships' | 'maps' | 'upsells' | 'automation';
  suggestions_enabled: boolean;
  revision: number;
  updated_at?: string | null;
  previous_flow?: string | null;
  can_undo?: boolean;
  available_flows?: Array<'overview' | 'content' | 'influencers' | 'partnerships' | 'maps' | 'upsells' | 'automation'>;
};
type PriorityProposal = { id: string; flow: TodayPreference['primary_flow']; active_days: number; confirmed_actions: number; reason_code: 'activity_shift' };
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
  preference?: TodayPreference;
  priority_proposal?: PriorityProposal | null;
  work_sections?: { needs_decision?: TodayItem[]; continue_work?: TodayItem[]; results?: TodayItem[] };
  work_source_states?: Partial<Record<'content' | 'influencers' | 'automation', { status?: 'live' | 'error' | 'unavailable'; as_of?: string }>>;
};

const screenRoute = (screen?: string) => ({
  cards: '/dashboard/card', reviews: '/dashboard/card?tab=reviews&review_filter=needs_reply', content: '/dashboard/content', services: '/dashboard/card?tab=services', finance: '/dashboard/finance', partnerships: '/dashboard/partnerships', agents: '/dashboard/agents', settings: '/dashboard/settings', progress: '/dashboard/progress', operator: '/dashboard/operator',
}[screen || ''] || '/dashboard/progress');

const missionRoute = (mission?: Mission | null) => {
  if (mission?.cta_url?.startsWith('/dashboard/')) return mission.cta_url;
  if (mission?.screen === 'content' && mission.item_id && mission.id?.startsWith('content_story_facts:')) {
    const params = new URLSearchParams();
    if (mission.plan_id) params.set('plan_id', mission.plan_id);
    params.set('item_id', mission.item_id);
    params.set('focus', 'story_facts');
    return `/dashboard/content?${params.toString()}`;
  }
  if (mission?.screen) return screenRoute(mission.screen);
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

const flowRoute: Record<TodayPreference['primary_flow'], string> = { overview: '/dashboard/today', content: '/dashboard/content', influencers: '/dashboard/influencers', partnerships: '/dashboard/partnerships', maps: '/dashboard/card', upsells: '/dashboard/average-ticket', automation: '/dashboard/agents' };
const flowOrder: TodayPreference['primary_flow'][] = ['overview', 'content', 'influencers', 'partnerships', 'maps', 'upsells', 'automation'];
const flowLabels: Record<Language, Record<TodayPreference['primary_flow'], string>> = {
  ru: { overview: 'Обзор', content: 'Контент', influencers: 'Инфлюенсеры', partnerships: 'Партнёрства', maps: 'Карты', upsells: 'Допродажи', automation: 'Автоматизация' },
  en: { overview: 'Overview', content: 'Content', influencers: 'Creators', partnerships: 'Partnerships', maps: 'Maps', upsells: 'Upsells', automation: 'Automation' },
  fr: { overview: 'Aperçu', content: 'Contenu', influencers: 'Créateurs', partnerships: 'Partenariats', maps: 'Cartes', upsells: 'Ventes additionnelles', automation: 'Automatisation' },
  es: { overview: 'Resumen', content: 'Contenido', influencers: 'Creadores', partnerships: 'Alianzas', maps: 'Mapas', upsells: 'Ventas adicionales', automation: 'Automatización' },
  el: { overview: 'Επισκόπηση', content: 'Περιεχόμενο', influencers: 'Δημιουργοί', partnerships: 'Συνεργασίες', maps: 'Χάρτες', upsells: 'Πρόσθετες πωλήσεις', automation: 'Αυτοματοποίηση' },
  de: { overview: 'Übersicht', content: 'Inhalte', influencers: 'Creator', partnerships: 'Partnerschaften', maps: 'Karten', upsells: 'Zusatzverkäufe', automation: 'Automatisierung' },
  th: { overview: 'ภาพรวม', content: 'คอนเทนต์', influencers: 'ครีเอเตอร์', partnerships: 'พาร์ทเนอร์', maps: 'แผนที่', upsells: 'การขายเพิ่ม', automation: 'งานอัตโนมัติ' },
  ar: { overview: 'نظرة عامة', content: 'المحتوى', influencers: 'صناع المحتوى', partnerships: 'الشراكات', maps: 'الخرائط', upsells: 'المبيعات الإضافية', automation: 'الأتمتة' },
  ha: { overview: 'Bayani', content: 'Abun ciki', influencers: 'Masu ƙirƙira', partnerships: 'Haɗin gwiwa', maps: 'Taswira', upsells: 'Ƙarin tallace-tallace', automation: 'Aiki ta atomatik' },
  tr: { overview: 'Genel bakış', content: 'İçerik', influencers: 'İçerik üreticileri', partnerships: 'Ortaklıklar', maps: 'Haritalar', upsells: 'Ek satışlar', automation: 'Otomasyon' },
};

export const TodayPage = () => {
  const navigate = useNavigate();
  const { language } = useLanguage();
  const copy = getTodayPageCopy(language);
  const { currentBusinessId, controlScope, onControlScopeChange, onBusinessChange } = useOutletContext<DashboardContext>();
  const [overview, setOverview] = useState<TodayOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [preferenceSaving, setPreferenceSaving] = useState(false);
  const [journeyIntent, setJourneyIntent] = useState(() => readLeadJourneyIntent());
  const requestSequence = useRef(0);
  const loadedScope = useRef<string | null>(null);
  const scopeKey = currentBusinessId ? `${controlScope?.kind || 'business'}:${controlScope?.id || currentBusinessId}` : null;

  const load = () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    if (!currentBusinessId) {
      setOverview(null);
      loadedScope.current = null;
      setLoading(false);
      return;
    }
    if (loadedScope.current !== scopeKey) {
      setOverview(null);
      loadedScope.current = scopeKey;
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
        // Keep the last confirmed summary visible during a transient refresh error.
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

  const openItem = (itemMission?: Mission | null, businessId?: string, businessName?: string, url?: string) => {
    if (businessId && controlScope?.kind === 'network') {
      onBusinessChange?.(businessId);
      onControlScopeChange?.({ kind: 'business', id: businessId, name: businessName || copy.locationName });
    }
    navigate(url?.startsWith('/dashboard/') ? url : missionRoute(itemMission));
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
  const activeWork = useMemo(() => (overview?.work_sections?.continue_work || overview?.active_work || []).slice(0, 3), [overview?.active_work, overview?.work_sections?.continue_work]);
  const changes = overview?.changes_24h?.slice(0, 3) || [];
  const completedResults = (overview?.work_sections?.results || overview?.completed_results || []).slice(0, 3);
  const needsDecision = (overview?.work_sections?.needs_decision || []).slice(0, 3);
  const primaryItem = needsDecision[0] || activeWork[0] || null;
  const remainingNeedsDecision = primaryItem && needsDecision[0]?.id === primaryItem.id ? needsDecision.slice(1) : needsDecision;
  const remainingActiveWork = primaryItem && activeWork[0]?.id === primaryItem.id ? activeWork.slice(1) : activeWork;
  const availableFlows = overview?.preference?.available_flows || flowOrder;
  const unavailableSources = Object.entries(overview?.work_source_states || {}).filter(([, state]) => state?.status === 'error');
  const communityPulse = overview?.community_pulse?.slice(0, 2) || [];
  const networkSummary = overview?.network_summary;
  const problemLocations = overview?.problem_locations?.slice(0, 5) || [];
  const dataRhythm = overview?.data_rhythm;
  const analyticsModules = overview?.analytics_modules || [];
  const dataHealth = overview?.data_health;
  const hasDataOverview = Boolean(dataRhythm || analyticsModules.length);
  const dataNeedsAttention = Boolean(['missing', 'stale', 'due'].includes(dataHealth?.status || '') || dataHealth?.stale || dataHealth?.is_stale || dataHealth?.missing?.length);
  const preferenceCopy = language === 'ru'
    ? { configure: 'Настроить основной раздел', undo: 'Отменить последнее изменение', disableSuggestions: 'Не предлагать смену раздела', enableSuggestions: 'Снова включить предложения', proposalTitle: 'Вы стали чаще работать с', proposalDescription: 'Поставить этот раздел первым среди обычных задач? Срочные решения останутся выше.', accept: 'Поставить первым', decline: 'Не сейчас', snooze: 'Напомнить позже' }
    : { configure: 'Set main section', undo: 'Undo last change', disableSuggestions: 'Stop suggesting a section change', enableSuggestions: 'Enable suggestions again', proposalTitle: 'You have been working more often with', proposalDescription: 'Put this section first among regular work? Urgent decisions will stay above it.', accept: 'Put first', decline: 'Not now', snooze: 'Remind me later' };

  const updatePreference = async (action: 'set' | 'accept' | 'decline' | 'snooze' | 'opt_out' | 'enable' | 'undo', options: { primary_flow?: TodayPreference['primary_flow']; proposal_id?: string } = {}) => {
    const preference = overview?.preference;
    if (!preference || preferenceSaving) return;
    setPreferenceSaving(true);
    try {
      const params = new URLSearchParams({ scope_type: preference.scope_type, scope_id: preference.scope_id });
      const response = await newAuth.makeRequest(`/operator/today/preference?${params.toString()}`, {
        method: 'POST',
        body: JSON.stringify({ action, expected_revision: preference.revision, ...options }),
      });
      const payload: { preference?: TodayPreference; priority_proposal?: PriorityProposal | null } = response;
      if (scopeKey !== `${preference.scope_type}:${preference.scope_id}`) return;
      setOverview((current) => current && current.preference?.scope_type === preference.scope_type && current.preference.scope_id === preference.scope_id
        ? { ...current, preference: payload.preference || current.preference, priority_proposal: payload.priority_proposal ?? current.priority_proposal }
        : current);
    } catch {
      // A revision conflict or transient error leaves the confirmed view intact; refresh resolves it.
      setError(true);
    } finally {
      setPreferenceSaving(false);
    }
  };

  if (!currentBusinessId) return <DashboardEmptyState title={copy.selectBusiness} description={copy.selectBusinessHint} />;

  if (loading && !overview) {
    return <div className="space-y-6" aria-busy="true" data-tour-target="today-overview"><DashboardPageHeader eyebrow="LocalOS" title={copy.title} description={copy.loading} /><div className="h-44 animate-pulse rounded-3xl bg-slate-100" /><div className="h-72 animate-pulse rounded-3xl bg-slate-100" /></div>;
  }

  if (error && !overview) {
    return <div className="space-y-6" data-tour-target="today-overview"><DashboardPageHeader eyebrow="LocalOS" title={copy.title} description={copy.loadError} /><DashboardEmptyState title={copy.unavailable} description={copy.retryHint} action={<Button type="button" onClick={load} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className="h-4 w-4" />{copy.retry}</Button>} /></div>;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5 pb-10" data-tour-target="today-overview">
      <DashboardPageHeader eyebrow={controlScope?.kind === 'network' ? copy.networkEyebrow : 'LocalOS'} title={copy.title} description={copy.description} icon={Clock3} actions={<Button type="button" variant="outline" onClick={load} disabled={loading} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />{copy.refresh}</Button>} />

      {error && overview ? <div role="status" className="flex items-center justify-between gap-3 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-950"><span>{copy.retryHint}</span><Button type="button" size="sm" variant="outline" onClick={load} disabled={loading}>{copy.retry}</Button></div> : null}

      {unavailableSources.length ? <div role="status" className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-950">Часть рабочих данных временно недоступна: {unavailableSources.map(([flow]) => flow).join(', ')}. Остальные задачи показаны без изменений.</div> : null}

      {primaryItem ? <section className="rounded-[28px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_18px_50px_-36px_rgba(15,23,42,0.45)] sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"><div className="min-w-0"><div className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">{copy.now}</div><h2 className="mt-2 text-balance text-2xl font-semibold text-slate-950">{localizedGrowthText(language, primaryItem.title)}</h2><p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-600">{localizedGrowthText(language, primaryItem.description || primaryItem.stage || copy.noUrgent)}</p></div><Button type="button" onClick={() => openItem({ title: primaryItem.title, reason: '', expected_outcome: '', cta_label: '', screen: primaryItem.screen }, primaryItem.business_id, primaryItem.business_name, primaryItem.action?.url)} className="min-h-11 w-full gap-2 transition-transform active:scale-[0.96] lg:w-auto lg:justify-self-end">{primaryItem.action?.label || copy.openTasks}<ArrowRight className="h-4 w-4" /></Button></div>
      </section> : journeyActions.length ? <section aria-label="Текущее действие"><JourneyActionCard action={journeyActions[0]} businessId={currentBusinessId} onUpdated={load} /></section> : journeyDirection ? <section className="rounded-[28px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_18px_50px_-36px_rgba(15,23,42,0.45)] sm:p-6"><div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"><div><div className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">{copy.now}</div><h2 className="mt-2 text-balance text-2xl font-semibold text-slate-950">{journeyDirection.today.title}</h2><p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-600">{journeyDirection.today.description}</p></div><Button type="button" onClick={() => { clearLeadJourneyIntent(); setJourneyIntent(null); navigate(journeyDirection.dashboardRoute); }} className="min-h-11 gap-2">{journeyDirection.today.cta}<ArrowRight className="h-4 w-4" /></Button></div></section> : <section className="rounded-[28px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_18px_50px_-36px_rgba(15,23,42,0.45)] sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">{copy.now}</div>
            <h2 className="mt-2 text-balance text-2xl font-semibold text-slate-950">{mission?.title || copy.openTasks}</h2>
            <p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-600">{mission?.reason || copy.noUrgent}</p>
            {mission?.expected_outcome ? <p className="mt-3 flex max-w-3xl items-start gap-2 text-xs leading-5 text-slate-500"><ArrowRight className="mt-0.5 h-4 w-4 shrink-0" /><span><strong className="text-slate-700">{copy.after}</strong> {mission.expected_outcome}</span></p> : null}
          </div>
          <Button type="button" onClick={openMission} className="min-h-11 w-full gap-2 transition-transform active:scale-[0.96] lg:w-auto lg:justify-self-end">{mission?.cta_label || copy.openProgress}<ArrowRight className="h-4 w-4" /></Button>
        </div>
      </section>}

      {overview?.preference ? <details className="group rounded-2xl bg-white px-4 py-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]"><summary className="flex min-h-10 cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-slate-700 marker:hidden [&::-webkit-details-marker]:hidden"><span>{preferenceCopy.configure}: {flowLabels[language][overview.preference.primary_flow]}</span><ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></summary><div className="mt-3 border-t border-slate-100 pt-3"><div className="flex flex-wrap gap-2">{availableFlows.map((flow) => <Button key={flow} type="button" size="sm" variant={flow === overview.preference?.primary_flow ? 'default' : 'outline'} disabled={preferenceSaving} onClick={() => updatePreference('set', { primary_flow: flow })}>{flowLabels[language][flow]}</Button>)}</div><div className="mt-3 flex flex-wrap gap-2">{overview.preference.can_undo ? <Button type="button" size="sm" variant="outline" disabled={preferenceSaving} onClick={() => updatePreference('undo')}>{preferenceCopy.undo}</Button> : null}{overview.preference.suggestions_enabled ? <Button type="button" size="sm" variant="ghost" disabled={preferenceSaving} onClick={() => updatePreference('opt_out')}>{preferenceCopy.disableSuggestions}</Button> : <Button type="button" size="sm" variant="outline" disabled={preferenceSaving} onClick={() => updatePreference('enable')}>{preferenceCopy.enableSuggestions}</Button>}</div></div></details> : null}

      {overview?.priority_proposal && overview.preference?.suggestions_enabled ? <section className="rounded-2xl bg-slate-50 p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]"><p className="text-sm font-semibold text-slate-950">{preferenceCopy.proposalTitle} «{flowLabels[language][overview.priority_proposal.flow]}»</p><p className="mt-1 text-sm text-slate-600">{preferenceCopy.proposalDescription}</p><div className="mt-3 flex flex-wrap gap-2"><Button type="button" size="sm" disabled={preferenceSaving} onClick={() => updatePreference('accept', { proposal_id: overview.priority_proposal?.id })}>{preferenceCopy.accept}</Button><Button type="button" size="sm" variant="outline" disabled={preferenceSaving} onClick={() => updatePreference('decline', { proposal_id: overview.priority_proposal?.id })}>{preferenceCopy.decline}</Button><Button type="button" size="sm" variant="ghost" disabled={preferenceSaving} onClick={() => updatePreference('snooze', { proposal_id: overview.priority_proposal?.id })}>{preferenceCopy.snooze}</Button></div></section> : null}

      {remainingNeedsDecision.length ? <DashboardSection title={language === 'ru' ? 'Требует решения' : 'Needs your decision'} description={language === 'ru' ? 'Проверьте подготовленный результат и выберите следующий шаг.' : 'Review the prepared result and choose the next step.'}><div className="space-y-3">{remainingNeedsDecision.map((item) => <button key={item.id} type="button" onClick={() => openItem({ title: item.title, reason: '', expected_outcome: '', cta_label: '', screen: item.screen }, item.business_id, item.business_name, item.action?.url)} className="w-full rounded-2xl bg-amber-50 px-4 py-3 text-left transition-transform active:scale-[0.96]"><strong className="block text-sm text-slate-950">{localizedGrowthText(language, item.title)}</strong>{item.description ? <span className="mt-1 block text-sm text-slate-600">{localizedGrowthText(language, item.description)}</span> : null}</button>)}</div></DashboardSection> : null}

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

      {hasDataOverview ? (
        <details className="group overflow-hidden rounded-3xl bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">
          <summary className="flex min-h-16 cursor-pointer list-none items-center gap-3 px-5 py-3 marker:hidden [&::-webkit-details-marker]:hidden">
            <div className="min-w-0 flex-1"><h2 className="font-semibold text-slate-950">{copy.dataTitle}</h2><p className="mt-0.5 text-sm text-slate-500">{dataRhythm ? fillTodayTemplate(copy.summaries, { count: dataRhythm.completed_periods_8w || 0 }) : copy.dataHint}</p></div>
            {dataRhythm ? <strong className="shrink-0 tabular-nums text-slate-700">{dataRhythm.coverage || 0}%</strong> : null}
            <ChevronDown className="h-5 w-5 shrink-0 text-slate-400 transition-transform duration-200 group-open:rotate-180" />
          </summary>
          <div className="border-t border-slate-100 px-5 py-4">
            <p className="mb-4 max-w-3xl text-sm leading-6 text-slate-600">{copy.dataHint}</p>
            {dataRhythm ? <div className="rounded-2xl bg-slate-50 px-4 py-3"><div className="flex items-center justify-between gap-3 text-sm"><span className="text-slate-600">{copy.coverage}</span><strong className="tabular-nums text-slate-950">{dataRhythm.coverage || 0}%</strong></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-orange-500" style={{ width: `${Math.min(100, Math.max(0, dataRhythm.coverage || 0))}%` }} /></div><p className="mt-2 text-sm text-slate-600">{fillTodayTemplate(copy.summaries, { count: dataRhythm.completed_periods_8w || 0 })}{formatDate(language, dataRhythm.next_due_at) ? ` · ${fillTodayTemplate(copy.nextSummary, { date: formatDate(language, dataRhythm.next_due_at) || '' })}` : ''}</p></div> : null}
            {analyticsModules.length ? <div className="mt-3 flex flex-wrap gap-2">{analyticsModules.map((module) => <span key={module.key || module.label} className={cn('rounded-full px-3 py-1.5 text-sm', module.status === 'ready' ? 'bg-emerald-50 text-emerald-800' : module.status === 'available' ? 'bg-amber-50 text-amber-900' : 'bg-slate-100 text-slate-600')}>{analyticsLabel(language, copy, module.key, module.label)}: {analyticsStatus(copy, module.status)}</span>)}</div> : null}
            {dataHealth ? <div className={cn('mt-3 flex items-start gap-3 rounded-2xl px-4 py-3 text-sm', dataNeedsAttention ? 'bg-amber-50 text-amber-950' : 'bg-slate-50 text-slate-700')}><TriangleAlert className={cn('mt-0.5 h-5 w-5 shrink-0', dataNeedsAttention ? 'text-amber-700' : 'text-slate-500')} /><div><span className="font-semibold">{copy.financeSource}</span> {localizedGrowthText(language, dataSourceLabel(copy, dataHealth.source_label || dataHealth.source))}{formatDate(language, dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at) ? <span className="tabular-nums"> · {fillTodayTemplate(copy.updated, { date: formatDate(language, dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at) || '' })}</span> : null}{dataNeedsAttention && dataHealth.missing?.length ? <span> · {fillTodayTemplate(copy.add, { items: dataHealth.missing.map((item) => localizedGrowthText(language, item)).join(', ') })}</span> : null}</div></div> : null}
          </div>
        </details>
      ) : null}

      {changes.length || remainingActiveWork.length ? <div className="grid gap-5 lg:grid-cols-2">
        {changes.length ? <DashboardSection title={copy.changesTitle} description={copy.changesHint}>
          {changes.length ? <div className="divide-y divide-slate-100">{changes.map((item) => <div key={item.id} className="flex gap-3 py-3 first:pt-0 last:pb-0"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><div className="font-medium text-slate-950">{localizedGrowthText(language, item.title)}</div><p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{localizedGrowthText(language, item.description)}</p>{formatDate(language, item.occurred_at) ? <div className="mt-1 text-xs tabular-nums text-slate-400">{formatDate(language, item.occurred_at)}</div> : null}</div></div>)}</div> : <p className="text-sm leading-6 text-slate-600">{copy.noChanges}</p>}
        </DashboardSection> : null}

        {remainingActiveWork.length ? <DashboardSection title={copy.workTitle} description={copy.workHint}>
          {remainingActiveWork.length ? <div className="space-y-3">{remainingActiveWork.map((item) => <button key={item.id} type="button" onClick={() => openItem({ title: item.title, reason: '', expected_outcome: '', cta_label: '', screen: item.screen }, item.business_id, item.business_name, item.action?.url)} className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-left transition-transform active:scale-[0.96]"><div className="flex items-start gap-2"><Bot className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><div className="min-w-0 flex-1"><div className="font-medium text-slate-950">{localizedGrowthText(language, item.title)}</div><p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{[item.business_name, localizedGrowthText(language, item.stage || item.description)].filter(Boolean).join(' · ')}</p></div>{item.progress == null ? null : <span className="text-sm tabular-nums text-slate-500">{item.progress}%</span>}</div></button>)}</div> : <p className="text-sm leading-6 text-slate-600">{copy.noWork}</p>}
        </DashboardSection> : null}
      </div> : !primaryItem && !journeyActions.length && !journeyDirection ? <div className="flex min-h-14 items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600"><CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" /><span>{copy.noWork}</span></div> : null}

      {completedResults.length ? <details className="group overflow-hidden rounded-3xl bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.08)]"><summary className="flex min-h-16 cursor-pointer list-none items-center gap-3 px-5 py-3 marker:hidden [&::-webkit-details-marker]:hidden"><CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" /><span className="min-w-0 flex-1 font-semibold text-slate-950">{copy.readyTitle}</span><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold tabular-nums text-emerald-800">{completedResults.length}</span><ChevronDown className="h-5 w-5 shrink-0 text-slate-400 transition-transform duration-200 group-open:rotate-180" /></summary><div className="border-t border-slate-100 px-5 py-4"><p className="mb-3 text-sm leading-6 text-slate-600">{copy.readyHint}</p><div className="divide-y divide-slate-100">{completedResults.map((item) => <div key={item.id} className="flex gap-3 py-3 first:pt-0 last:pb-0"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><div className="font-medium text-slate-950">{localizedGrowthText(language, item.title)}</div>{item.description ? <p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{localizedGrowthText(language, item.description)}</p> : null}{item.source ? <div className="mt-1 text-xs text-slate-500">{copy.source} {resultSourceLabel(copy, item.source)}</div> : null}</div></div>)}</div></div></details> : null}

      {communityPulse.length ? <DashboardSection title={copy.pulseTitle} description={copy.pulseHint}><div className="space-y-3">{communityPulse.map((item) => <div key={item.id} className="flex gap-3 rounded-2xl bg-slate-50 px-4 py-3"><Radio className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><div className="min-w-0"><div className="font-medium text-slate-950">{item.title}</div>{item.description ? <p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.description}</p> : null}{item.source ? <div className="mt-1 text-xs text-slate-500">{copy.source} {item.source}</div> : null}</div></div>)}</div></DashboardSection> : null}

      {dataHealth && !hasDataOverview ? <div className={cn('flex items-start gap-3 rounded-2xl px-4 py-3 text-sm shadow-[0_0_0_1px_rgba(15,23,42,0.08)]', dataNeedsAttention ? 'bg-amber-50 text-amber-950' : 'bg-slate-50 text-slate-700')}><TriangleAlert className={cn('mt-0.5 h-5 w-5 shrink-0', dataNeedsAttention ? 'text-amber-700' : 'text-slate-500')} /><div><span className="font-semibold">{copy.financeSource}</span> {localizedGrowthText(language, dataSourceLabel(copy, dataHealth.source_label || dataHealth.source))}{formatDate(language, dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at) ? <span className="tabular-nums"> · {fillTodayTemplate(copy.updated, { date: formatDate(language, dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at) || '' })}</span> : null}{dataNeedsAttention && dataHealth.missing?.length ? <span> · {fillTodayTemplate(copy.add, { items: dataHealth.missing.map((item) => localizedGrowthText(language, item)).join(', ') })}</span> : null}</div></div> : null}

      {mission || journeyActions.length ? <div className="flex justify-end border-t border-slate-200 pt-4"><Button type="button" variant="outline" onClick={() => navigate('/dashboard/progress')} className="min-h-11 gap-2 transition-transform active:scale-[0.96]">{copy.openProgress}<ArrowRight className="h-4 w-4" /></Button></div> : null}
    </div>
  );
};
