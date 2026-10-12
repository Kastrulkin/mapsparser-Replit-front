import { workCoherenceCopy } from '@/i18n/workCoherenceCopy';
import { workChatRoute, workNavigationCopy } from '@/lib/workNavigation';
import { useLatestCallback } from '@/hooks/useLatestCallback';
import { ArrowRight, ChevronDown, Clock3, RefreshCw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';

import type { ControlScope } from '@/components/DashboardLayout';
import { DashboardEmptyState, DashboardPageHeader, DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { Button } from '@/components/ui/button';
import { featureFlags } from '@/config/featureFlags';
import { useLanguage, type Language } from '@/i18n/LanguageContext.logic';
import { fillTodayTemplate, getTodayOperationalCopy, getTodayPageCopy, type TodayPageCopy } from '@/i18n/todayPageCopy';
import { todayWorkActionLabel, todayWorkDescription } from '@/i18n/todayWorkCopy';
import { newAuth } from '@/lib/auth_new';
import { readLeadJourneyToken, resolveStoredLeadJourney } from '@/lib/leadJourney';
import { cn } from '@/lib/utils';
import { todayClarityCopy } from '@/i18n/todayClarityCopy';
import { workSections, workRoute, statusKey, validDate, needsHuman } from './todayWorkModel';
import { localizedFocusAction, localizedGrowthText } from './progressPageCopy';

type DashboardContext = { currentBusinessId?: string | null; controlScope?: ControlScope | null; onControlScopeChange?: (scope: ControlScope) => void; onBusinessChange?: (businessId: string) => void };

import type { Mission, TodayItem, TodayPreference, TodayOverview, PriorityProposal } from './todayWorkModel';

const isScopeAccessError = (error: unknown) => (
  typeof error === 'object'
  && error !== null
  && 'status' in error
  && (error.status === 401 || error.status === 403 || error.status === 404)
);

const screenRoute = (screen?: string) => ({
  cards: '/dashboard/card', reviews: '/dashboard/card?tab=reviews&review_filter=needs_reply', content: '/dashboard/content', services: '/dashboard/card?tab=services', finance: '/dashboard/finance', partnerships: '/dashboard/partnerships', influencers: '/dashboard/influencers', agents: '/dashboard/agents', settings: '/dashboard/settings', average_ticket: '/dashboard/average-ticket', progress: '/dashboard/progress', operator: '/dashboard/operator',
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

  hy: { sales: "Վաճառք և միջին վաճառք", services: "Ծառայություններ և վաճառքներ", capacity: "Թիմային կարողություններ" },
  kk: { sales: "Сату және орташа есепшот", services: "Қызметтер және жоғары сатылымдар", capacity: "Пәрмен жүктелуде" },};

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

const resultSourceLabel = (copy: TodayPageCopy, source?: string) => {
  if (source === 'Прогресс LocalOS') return copy.resultHistory;
  return source;
};

const localeByLanguage: Record<Language, string> = { ru: 'ru-RU', en: 'en-GB', fr: 'fr-FR', es: 'es-ES', el: 'el-GR', de: 'de-DE', th: 'th-TH', ar: 'ar', ha: 'ha-NG', tr: 'tr-TR' ,
  hy: 'hy-AM',
  kk: 'kk-KZ',};

const validTimezone = (value?: string) => {
  if (!value) return false;
  try { new Intl.DateTimeFormat('en', { timeZone: value }).format(); return true; } catch { return false; }
};

const formatDate = (language: Language, value?: string | null, timeZone?: string) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  try { return new Intl.DateTimeFormat(localeByLanguage[language], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', ...(timeZone ? { timeZone, timeZoneName: 'short' } : {}) }).format(date); } catch { return new Intl.DateTimeFormat(localeByLanguage[language], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date); }
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

  hy: { overview: "Ընդհանուր ակնարկ", content: "Բովանդակություն", influencers: "Ստեղծողներ", partnerships: "Գործընկերություններ", maps: "Քարտեզներ", upsells: 'Upsells', automation: "Ավտոմատացում" },
  kk: { overview: "Қарау", content: "Мазмұны", influencers: "Әсер етушілер", partnerships: "Серіктестік", maps: "Карталар", upsells: "Жоғары сатылымдар", automation: "Автоматтандыру" },};

export const TodayPage = () => {
  const navigate = useNavigate();
  const { language } = useLanguage();
  const copy = getTodayPageCopy(language);
  const operationalCopy = getTodayOperationalCopy(language);
  const { currentBusinessId, controlScope, onControlScopeChange, onBusinessChange } = useOutletContext<DashboardContext>();
  const [cachedOverview, setOverview] = useState<TodayOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [accessError, setAccessError] = useState(false);
  const [preferenceSaving, setPreferenceSaving] = useState(false);
  const [expandedSections, setExpandedSections] = useState<string[]>([]);
  const requestSequence = useRef(0);
  const preferenceRequestSequence = useRef(0);
  const loadedScope = useRef<string | null>(null);
  const scopeKey = currentBusinessId ? `${controlScope?.kind || 'business'}:${controlScope?.id || currentBusinessId}` : null;
  const currentScopeKey = useRef(scopeKey);
  currentScopeKey.current = scopeKey;
  // Guard the first render of a new scope, before effects clear cached state.
  const overview = loadedScope.current === scopeKey ? cachedOverview : null;

  const load = useLatestCallback(() => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    const requestedScopeKey = scopeKey;
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
    setAccessError(false);
    const params = new URLSearchParams({ scope_type: controlScope?.kind || 'business', scope_id: controlScope?.id || currentBusinessId });
    let request: Promise<TodayOverview>;
    try {
      request = newAuth.makeRequest(`/operator/today?${params.toString()}`, { method: 'GET' });
    } catch (requestError) {
      if (isScopeAccessError(requestError)) { setOverview(null); setAccessError(true); }
      if (requestSequence.current === requestId) {
        setError(true);
        setLoading(false);
      }
      return;
    }
    void request
      .then((data: TodayOverview) => {
        if (requestSequence.current === requestId && currentScopeKey.current === requestedScopeKey) setOverview(data);
      })
      .catch((requestError: unknown) => {
        // Keep the last confirmed summary visible during a transient refresh error.
        if (requestSequence.current === requestId && currentScopeKey.current === requestedScopeKey) {
          if (isScopeAccessError(requestError)) { setOverview(null); setAccessError(true); }
          setError(true);
        }
      })
      .finally(() => {
        if (requestSequence.current === requestId && currentScopeKey.current === requestedScopeKey) setLoading(false);
      });
  });

  useEffect(() => { load(); }, [currentBusinessId, controlScope?.id, controlScope?.kind, load]);

  useEffect(() => {
    preferenceRequestSequence.current += 1;
    setPreferenceSaving(false);
    setExpandedSections([]);
  }, [scopeKey]);

  useEffect(() => {
    if (!featureFlags.journeyPostAuthRedirect || !currentBusinessId) return;
    const token = readLeadJourneyToken();
    const requestedScope = scopeKey;
    if (!token) return;
    void resolveStoredLeadJourney(currentBusinessId)
      .then((resolved) => {
        if (resolved && currentScopeKey.current === requestedScope) {
          navigate(resolved.route, { replace: true });
        }
      })
      .catch(() => {
        // Keep the token so a temporary API or connectivity failure can be retried.
      });
  }, [currentBusinessId, scopeKey, navigate]);

  const openItem = (itemMission?: Mission | null, businessId?: string, businessName?: string, url?: string) => {
    if (businessId && controlScope?.kind === 'network') {
      onBusinessChange?.(businessId);
      onControlScopeChange?.({ kind: 'business', id: businessId, name: businessName || copy.locationName });
    }
    navigate(url?.startsWith('/dashboard/') ? url : missionRoute(itemMission));
  };

  const openMission = (selectedMission?: Mission | null) => {
    const target = selectedMission?.target_scope;
    if (target?.kind === 'business' && target.id) {
      onBusinessChange?.(target.id);
      onControlScopeChange?.({ kind: 'business', id: target.id, name: copy.locationName });
    }
    navigate(missionRoute(selectedMission));
  };

  const mission = missionCopy(language, overview?.focus_action, copy);
  const emptyPrimaryMissions: Partial<Record<TodayPreference['primary_flow'], Mission>> = {
    content: { ...operationalCopy.emptyMissions.content, expected_outcome: '', cta_label: operationalCopy.emptyMissions.content.cta, screen: 'content' },
    influencers: { ...operationalCopy.emptyMissions.influencers, expected_outcome: '', cta_label: operationalCopy.emptyMissions.influencers.cta, screen: 'influencers' },
    automation: { ...operationalCopy.emptyMissions.automation, expected_outcome: '', cta_label: operationalCopy.emptyMissions.automation.cta, screen: 'agents' },
  };
  const preferredFlow = overview?.preference?.primary_flow;
  const hasPreferredWork = [...(overview?.work_sections?.needs_decision || []), ...(overview?.work_sections?.continue_work || overview?.active_work || [])]
    .some((item) => item.flow === preferredFlow);
  const hasPreferredMission = preferredFlow && mission && missionRoute(mission).split('?')[0] === flowRoute[preferredFlow];
  const emptyPrimaryMission = preferredFlow && !hasPreferredWork && !hasPreferredMission
    ? emptyPrimaryMissions[preferredFlow]
    : null;
  const displayedMission = mission || emptyPrimaryMission;
  const ui = todayClarityCopy(language);
  const observedAt = validDate(overview?.as_of) ? Date.parse(overview?.as_of || '') : Date.now();
  const sections = workSections(overview || {}, observedAt);
  const primaryItem = sections.primary;
  const journeyAction = overview?.journey_actions?.find(action => action.business_id === currentBusinessId && controlScope?.kind !== 'network' && !['completed', 'superseded', 'cancelled'].includes(action.status));
  const journeyMission: Mission | null = journeyAction ? {
    id: journeyAction.id, title: journeyAction.title, reason: journeyAction.access?.allowed === false ? journeyAction.access.reason || ui.unavailable : journeyAction.description,
    expected_outcome: '', cta_label: journeyAction.access?.allowed === false ? journeyAction.access.cta_label || ui.setup : journeyAction.cta_label,
    cta_url: journeyAction.access?.allowed === false ? journeyAction.access.cta_target?.url || '/dashboard/profile' : `${screenRoute(journeyAction.cta_target?.screen || ({ maps: 'cards', content: 'content', partnership: 'partnerships', influencer: 'influencers', automation: 'agents', average_ticket: 'average_ticket', upgrade: 'settings' }[journeyAction.flow_type]))}${screenRoute(journeyAction.cta_target?.screen || ({ maps: 'cards', average_ticket: 'average_ticket' }[journeyAction.flow_type])).includes('?') ? '&' : '?'}journey_action=${encodeURIComponent(journeyAction.id)}`,
  } : null;
  const availableFlows = overview?.preference?.available_flows || flowOrder;
  const unavailableSources = Object.entries(overview?.work_source_states || {}).filter(([, state]) => state?.status === 'error' || state?.status === 'unavailable');
  const starterFlow = availableFlows.find(flow => emptyPrimaryMissions[flow]);
  const starterMission = !unavailableSources.length && !sections.decisions.length && !sections.continuing.length && !sections.results.length && starterFlow ? emptyPrimaryMissions[starterFlow] : null;
  const nextMission = journeyMission || displayedMission || starterMission;
  const changes = overview?.changes_24h || [];
  const problemLocations = overview?.problem_locations || [];
  const dataHealth = overview?.data_health;
  const dataRhythm = overview?.data_rhythm;
  const analyticsModules = overview?.analytics_modules || [];
  const preferenceCopy = operationalCopy.preference;
  const sourceName = (source?: string) => ({ demo_grooming_network: ui.sourceDemo, manual: ui.sourceManual, yclients: 'YCLIENTS', YCLIENTS: 'YCLIENTS', 'Прогресс LocalOS': ui.sourceHistory, LocalOS: 'LocalOS' }[source || ''] || ui.sourceUnknown);
  const expand = (key: string) => setExpandedSections(current => current.includes(key) ? current.filter(value => value !== key) : [...current, key]);
  const itemLabel = (item: TodayItem, result = false) => item.action?.label && item.action.label !== 'Открыть'
    ? todayWorkActionLabel(language, item.action.label_code, item.action.label)
    : result ? ui.viewResult : needsHuman(item) ? ui.review : ui.open;
  const openWork = (item: TodayItem) => {
    const route = workRoute(item);
    if (!route) return;
    openItem(undefined, item.business_id, item.business_name, route);
  };
  const row = (item: TodayItem, result = false) => {
    const route = workRoute(item);
    const status = statusKey(item, observedAt);
    return <div key={item.id} className="min-w-0 py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-56"><h3 className="break-words text-sm font-medium text-foreground">{localizedGrowthText(language, item.title)}</h3>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {item.business_name ? <span>{item.business_name}</span> : null}
            <span className={cn(needsHuman(item) && 'font-medium text-amber-800')}>{ui[status === 'completed' ? 'completedStatus' : status]}</span>
            {formatDate(language, result ? item.occurred_at : item.due_at, item.timezone || overview?.timezone) ? <span>{result ? '' : `${ui.due}: `}{formatDate(language, result ? item.occurred_at : item.due_at, item.timezone || overview?.timezone)}{!validTimezone(item.timezone || overview?.timezone) ? ` · ${ui.deviceTime}` : ''}</span> : null}
          </div>
        </div>
        {route ? <Button type="button" variant="outline" className="min-h-11 max-w-full whitespace-normal text-left" onClick={() => openWork(item)} aria-label={`${itemLabel(item, result)}: ${item.title}`}>{itemLabel(item, result)}<ArrowRight className="ml-2 h-4 w-4 shrink-0" /></Button> : null}
        {route && item.business_id ? <Button variant="ghost" onClick={() => navigate(workChatRoute(route, item.business_id || '', item.entity_type === 'journey_action' ? item.entity_id : undefined))}>{workNavigationCopy(language).discuss}</Button> : null}
      </div>
      {!route ? <p className="mt-2 text-sm text-muted-foreground">{ui.blockedAction}</p> : null}
      {item.description || item.preview || item.source ? <details className="mt-2 text-sm"><summary className="min-h-10 cursor-pointer py-2 text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">{ui.details}</summary>
        {item.description || item.stage ? <p className="break-words leading-6 text-muted-foreground">{todayWorkDescription(language, item.message_code, localizedGrowthText(language, item.description || item.stage))}</p> : null}
        {item.preview ? <p className="mt-2 whitespace-pre-wrap break-words text-foreground">{item.preview}</p> : null}
        {item.source ? <p className="mt-2 text-xs text-muted-foreground">{copy.source} {sourceName(item.source)}</p> : null}
      </details> : null}
    </div>;
  };
  const workSection = (key: string, title: string, items: TodayItem[], empty: string, result = false) => {
    const remaining = items.filter(item => item.id !== primaryItem?.id);
    const visible = expandedSections.includes(key) ? remaining : remaining.slice(0, 3);
    return <section aria-label={title} className="border-t border-border pt-5"><h2 className="mb-4 text-lg font-semibold text-foreground">{title}</h2>{key === 'decisions' ? <p className="mb-3 text-sm text-muted-foreground">{operationalCopy.decisionDescription}</p> : null}
      {remaining.length ? <div className="divide-y divide-border">{visible.map(item => row(item, result))}</div> : <p className="text-sm leading-6 text-muted-foreground">{unavailableSources.length ? ui.unavailable : items.some(item => item.id === primaryItem?.id) ? workCoherenceCopy(language).currentWorkAbove : empty}</p>}
      {remaining.length > 3 ? <Button type="button" variant="ghost" className="mt-3 min-h-11" onClick={() => expand(key)} aria-expanded={expandedSections.includes(key)}>{expandedSections.includes(key) ? ui.details : ui.more} ({remaining.length})</Button> : null}
      {remaining.length ? <p className="mt-3 text-xs text-muted-foreground">{ui.limited}</p> : null}
    </section>;
  };

  const updatePreference = async (action: 'set' | 'accept' | 'decline' | 'snooze' | 'opt_out' | 'enable' | 'undo', options: { primary_flow?: TodayPreference['primary_flow']; proposal_id?: string } = {}) => {
    const preference = overview?.preference;
    if (!preference || preferenceSaving) return;
    const preferenceRequestId = preferenceRequestSequence.current + 1;
    preferenceRequestSequence.current = preferenceRequestId;
    const requestedScopeKey = `${preference.scope_type}:${preference.scope_id}`;
    setPreferenceSaving(true);
    try {
      const params = new URLSearchParams({ scope_type: preference.scope_type, scope_id: preference.scope_id });
      const response = await newAuth.makeRequest(`/operator/today/preference?${params.toString()}`, {
        method: 'POST',
        body: JSON.stringify({ action, expected_revision: preference.revision, ...options }),
      });
      const payload: { preference?: TodayPreference; priority_proposal?: PriorityProposal | null } = response;
      if (currentScopeKey.current !== requestedScopeKey || preferenceRequestSequence.current !== preferenceRequestId) return;
      const hasPriorityProposal = Object.prototype.hasOwnProperty.call(payload, 'priority_proposal');
      setOverview((current) => current && current.preference?.scope_type === preference.scope_type && current.preference.scope_id === preference.scope_id
        ? { ...current, preference: payload.preference || current.preference, priority_proposal: hasPriorityProposal ? payload.priority_proposal : current.priority_proposal }
        : current);
      load();
    } catch (caught) {
      if (currentScopeKey.current === requestedScopeKey && isScopeAccessError(caught)) setOverview(null);
      // A revision conflict or transient error leaves the confirmed view intact; refresh resolves it.
      if (currentScopeKey.current === requestedScopeKey && preferenceRequestSequence.current === preferenceRequestId) setError(true);
    } finally {
      if (currentScopeKey.current === requestedScopeKey && preferenceRequestSequence.current === preferenceRequestId) setPreferenceSaving(false);
    }
  };

  if (!currentBusinessId) return <DashboardEmptyState title={copy.selectBusiness} description={copy.selectBusinessHint} />;

  if (loading && !overview) {
    return <div className="space-y-6" aria-busy="true" data-tour-target="today-overview"><DashboardPageHeader eyebrow="LocalOS" title={copy.title} description={copy.loading} /><div className="h-44 animate-pulse rounded-3xl bg-slate-100" /><div className="h-72 animate-pulse rounded-3xl bg-slate-100" /></div>;
  }

  if (error && !overview) {
    return <div className="space-y-6" data-tour-target="today-overview"><DashboardPageHeader eyebrow="LocalOS" title={copy.title} description={copy.loadError} /><DashboardEmptyState title={copy.unavailable} description={accessError ? ui.accessUnavailable : copy.retryHint} action={<Button type="button" onClick={load} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className="h-4 w-4" />{copy.retry}</Button>} /></div>;
  }

  return (
    <div key={scopeKey} className="mx-auto max-w-5xl space-y-6 pb-10" data-tour-target="today-overview">
      <DashboardPageHeader title={copy.title} description={ui.description} icon={Clock3} actions={<Button type="button" variant="outline" onClick={load} disabled={loading} className="min-h-11 gap-2"><RefreshCw className={cn('h-4 w-4', loading && 'animate-spin motion-reduce:animate-none')} />{copy.refresh}</Button>} />
      {formatDate(language, overview?.as_of, overview?.timezone) ? <p className="text-xs text-muted-foreground">{ui.reportDate}: {formatDate(language, overview?.as_of, overview?.timezone)}{!validTimezone(overview?.timezone) ? ` · ${ui.deviceTime}` : ''}</p> : null}
      {error && overview ? <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-amber-50 p-4 text-sm text-amber-950"><span>{copy.retryHint}</span><Button type="button" variant="outline" onClick={load} disabled={loading}>{copy.retry}</Button></div> : null}
      {unavailableSources.length ? <p role="status" className="text-sm text-muted-foreground">{ui.sourceUnavailable}: {unavailableSources.map(([flow]) => flowLabels[language][availableFlows.find(value => value === flow) || 'overview']).join(', ')}</p> : null}
      <section aria-label={ui.next} className="rounded-2xl border border-border bg-card p-5 sm:p-6">
        <p className="text-sm font-medium text-muted-foreground">{ui.next}</p>
        <h2 className="mt-2 break-words text-xl font-semibold text-foreground">{primaryItem ? localizedGrowthText(language, primaryItem.title) : nextMission?.title || copy.openProgress}</h2>
        {primaryItem ? <>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted-foreground"><span>{ui[statusKey(primaryItem, observedAt)]}</span>{primaryItem.business_name ? <span>{primaryItem.business_name}</span> : null}{formatDate(language, primaryItem.due_at, primaryItem.timezone || overview?.timezone) ? <span>{ui.due}: {formatDate(language, primaryItem.due_at, primaryItem.timezone || overview?.timezone)}{!validTimezone(primaryItem.timezone || overview?.timezone) ? ` · ${ui.deviceTime}` : ''}</span> : null}</div>
          <p className="mt-3 break-words text-sm leading-6 text-muted-foreground">{todayWorkDescription(language, primaryItem.message_code, localizedGrowthText(language, primaryItem.description || primaryItem.stage))}</p>
          {workRoute(primaryItem) ? <Button type="button" onClick={() => openWork(primaryItem)} className="mt-4 min-h-11 w-full whitespace-normal sm:w-auto">{itemLabel(primaryItem)}<ArrowRight className="ml-2 h-4 w-4 shrink-0" /></Button> : <><p className="mt-3 text-sm text-muted-foreground">{ui.blockedAction}</p><Button type="button" className="mt-4 min-h-11" onClick={() => navigate('/dashboard/operator')}>{ui.openManagement}<ArrowRight className="ml-2 h-4 w-4" /></Button></>}
          {workRoute(primaryItem) && primaryItem.business_id ? <Button variant="ghost" className="mt-2" onClick={() => navigate(workChatRoute(workRoute(primaryItem) || '', primaryItem.business_id || '', primaryItem.entity_type === 'journey_action' ? primaryItem.entity_id : undefined))}>{workNavigationCopy(language).discuss}</Button> : null}
        </> : <>
          <p className="mt-2 break-words text-sm leading-6 text-muted-foreground">{nextMission?.reason || (unavailableSources.length ? ui.unavailable : ui.emptyDecisions)}</p>
          <Button type="button" onClick={() => openMission(nextMission)} className="mt-4 min-h-11 w-full whitespace-normal sm:w-auto">{(nextMission?.cta_url?.startsWith('/dashboard/profile') || nextMission?.screen === 'settings') && journeyAction?.access?.allowed !== false ? ui.setup : nextMission?.cta_label || copy.openProgress}<ArrowRight className="ml-2 h-4 w-4 shrink-0" /></Button>
          {nextMission?.expected_outcome ? <details className="mt-3 text-sm"><summary className="min-h-10 cursor-pointer py-2 text-muted-foreground">{ui.details}</summary><p className="text-muted-foreground">{copy.after} {nextMission.expected_outcome}</p></details> : null}
        </>}
      </section>
      {workSection('decisions', ui.decisions, sections.decisions, ui.emptyDecisions)}
      {workSection('continuing', ui.continue, sections.continuing, ui.emptyContinue)}
      {workSection('results', ui.completed, sections.results, ui.emptyResults, true)}
      <div className="space-y-3 border-t border-border pt-5">
        {changes.length ? <details className="group rounded-xl border border-border p-4"><summary className="flex min-h-11 cursor-pointer items-center justify-between gap-3 font-medium">{copy.changesTitle}<ChevronDown className="h-4 w-4 group-open:rotate-180" /></summary><p className="mb-3 text-sm text-muted-foreground">{copy.changesHint}</p><div className="divide-y divide-border">{changes.map(item => row(item))}</div></details> : <p className="text-sm text-muted-foreground">{unavailableSources.length ? ui.unavailable : copy.noChanges}</p>}
        {controlScope?.kind === 'network' ? <details className="group rounded-xl border border-border p-4"><summary className="flex min-h-11 cursor-pointer items-center justify-between gap-3 font-medium">{ui.locations} · {overview?.network_summary?.locations_count ?? '—'}<ChevronDown className="h-4 w-4 group-open:rotate-180" /></summary><p className="mt-2 text-sm text-muted-foreground">{ui.networkHint}</p><div className="mt-3 divide-y divide-border">{(expandedSections.includes('locations') ? problemLocations : problemLocations.slice(0, 3)).map(location => <button key={location.business_id} type="button" onClick={() => openItem(location.focus_action, location.business_id, location.business_name)} className="flex min-h-16 w-full items-center justify-between gap-3 py-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"><span className="min-w-0"><strong className="block break-words text-sm">{location.business_name}</strong><span className="block text-sm text-muted-foreground">{localizedGrowthText(language, location.problem || copy.locationAttention)}</span></span><ArrowRight className="h-4 w-4 shrink-0" /></button>)}</div>{problemLocations.length > 3 ? <Button type="button" variant="ghost" className="min-h-11" onClick={() => expand('locations')} aria-expanded={expandedSections.includes('locations')}>{ui.more} ({problemLocations.length})</Button> : null}</details> : null}
        {dataHealth || dataRhythm || analyticsModules.length ? <details className="group rounded-xl border border-border p-4"><summary className="flex min-h-11 cursor-pointer items-center justify-between gap-3 font-medium">{ui.data}<ChevronDown className="h-4 w-4 group-open:rotate-180" /></summary><div className="mt-3 space-y-3 text-sm text-muted-foreground"><p>{copy.dataHint}</p><p>{copy.financeSource} {sourceName(dataHealth?.source_label || dataHealth?.source)}{formatDate(language, dataHealth?.source_updated_at || dataHealth?.updated_at || dataHealth?.last_updated_at) ? ` · ${formatDate(language, dataHealth?.source_updated_at || dataHealth?.updated_at || dataHealth?.last_updated_at)}` : ''}</p>
          {dataRhythm?.completed_periods_8w != null ? <p>{fillTodayTemplate(copy.summaries, { count: dataRhythm.completed_periods_8w })}</p> : null}
          {formatDate(language, dataRhythm?.next_due_at) ? <p>{validDate(dataRhythm?.next_due_at) && Date.parse(dataRhythm?.next_due_at || '') < observedAt ? `${ui.overdue}: ${formatDate(language, dataRhythm?.next_due_at)}` : fillTodayTemplate(copy.nextSummary, { date: formatDate(language, dataRhythm?.next_due_at) || '' })} · {ui.deviceTime}</p> : null}
          {analyticsModules.map(module => <p key={module.key || module.label}>{analyticsLabel(language, copy, module.key, module.label)}: {analyticsStatus(copy, module.status)}</p>)}
          {dataHealth?.missing?.length ? <p>{fillTodayTemplate(copy.add, { items: dataHealth.missing.map(item => localizedGrowthText(language, item)).join(', ') })}</p> : null}
          {<Button type="button" variant="outline" className="min-h-11 whitespace-normal" onClick={() => navigate('/dashboard/finance')}>{ui.importData}</Button>}
        </div></details> : null}
      {overview?.preference ? <details className="group rounded-2xl bg-white px-4 py-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]"><summary className="flex min-h-10 cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-slate-700 marker:hidden [&::-webkit-details-marker]:hidden"><span>{preferenceCopy.configure}: {flowLabels[language][overview.preference.primary_flow]}</span><ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></summary><div className="mt-3 border-t border-slate-100 pt-3"><div className="flex flex-wrap gap-2">{availableFlows.map((flow) => <Button key={flow} type="button" size="sm" variant={flow === overview.preference?.primary_flow ? 'default' : 'outline'} disabled={preferenceSaving} onClick={() => updatePreference('set', { primary_flow: flow })}>{flowLabels[language][flow]}</Button>)}</div><div className="mt-3 flex flex-wrap gap-2">{emptyPrimaryMission && primaryItem ? <Button type="button" variant="outline" className="min-h-11" onClick={() => openMission(emptyPrimaryMission)}>{emptyPrimaryMission.cta_label}</Button> : null}{overview.preference.can_undo ? <Button type="button" size="sm" variant="outline" disabled={preferenceSaving} onClick={() => updatePreference('undo')}>{preferenceCopy.undo}</Button> : null}{overview.preference.suggestions_enabled ? <Button type="button" size="sm" variant="ghost" disabled={preferenceSaving} onClick={() => updatePreference('opt_out')}>{preferenceCopy.disableSuggestions}</Button> : <Button type="button" size="sm" variant="outline" disabled={preferenceSaving} onClick={() => updatePreference('enable')}>{preferenceCopy.enableSuggestions}</Button>}</div></div></details> : null}

      {overview?.priority_proposal && overview.preference?.suggestions_enabled ? <section className="rounded-2xl bg-slate-50 p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]"><p className="text-sm font-semibold text-slate-950">{preferenceCopy.proposalTitle} «{flowLabels[language][overview.priority_proposal.flow]}»</p><p className="mt-1 text-sm text-slate-600">{preferenceCopy.proposalDescription}</p><div className="mt-3 flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" disabled={preferenceSaving} onClick={() => updatePreference('accept', { proposal_id: overview.priority_proposal?.id })}>{preferenceCopy.accept}</Button><Button type="button" size="sm" variant="outline" disabled={preferenceSaving} onClick={() => updatePreference('decline', { proposal_id: overview.priority_proposal?.id })}>{preferenceCopy.decline}</Button><Button type="button" size="sm" variant="ghost" disabled={preferenceSaving} onClick={() => updatePreference('snooze', { proposal_id: overview.priority_proposal?.id })}>{preferenceCopy.snooze}</Button></div></section> : null}

        <details className="rounded-xl border border-border p-4"><summary className="min-h-11 cursor-pointer py-2 font-medium">{ui.how}</summary><p className="mt-2 text-sm leading-6 text-muted-foreground">{ui.description} {copy.after} {copy.readyHint}</p></details>
        <Button type="button" variant="outline" className="min-h-11" onClick={() => navigate('/dashboard/progress')}>{copy.openProgress}<ArrowRight className="ml-2 h-4 w-4" /></Button>
      </div>
    </div>
  );
};
