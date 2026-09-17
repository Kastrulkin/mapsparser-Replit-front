import localOsLogo from '@/assets/images/logo.png';
import { JourneyActionCard } from '@/components/journey/JourneyActionCard';
import { OperatorSpeech, OperatorVoiceInput, VoiceSubmission } from '@/components/operator/OperatorVoice';
import { waitForOperatorResult } from '@/components/operator/OperatorVoice.logic';
import ActionPreviewSheet, { type MobileActionPreview } from '@/components/telegram/ActionPreviewSheet';
import JobProgressSheet from '@/components/telegram/JobProgressSheet';
import MobileShell from '@/components/telegram/MobileShell';
import type { ProgressPayload } from '@/components/telegram/ProgressMobileModule';
import { ScopeProvider } from '@/components/telegram/ScopeProvider';
import { useMobileScope, type MobileScope } from '@/components/telegram/ScopeProvider.logic';
import type { TodayPayload } from '@/components/telegram/TodayMobileV2';
import { useMobileJobPolling } from '@/components/telegram/useMobileJobPolling';
import { CardsModule } from '@/features/telegram/CardsModule';
import { ContentModule } from '@/features/telegram/ContentModule';
import { AnalyticsModule, FinanceModule } from '@/features/telegram/FinanceModule';
import { dateLabel, isPreview, providerName } from '@/features/telegram/format';
import { spring } from '@/features/telegram/motion';
import { previewBootstrap, previewModules, previewProgress, previewReviews, previewToday } from '@/features/telegram/preview';
import { Empty, FilterSelect, InlineError, MetricMini, ReviewSkeleton, Screen, Segments, StatusPill } from '@/features/telegram/shared';
import type { AttentionItem, Bootstrap, BusinessCatalogItem, Catalog, ModuleData, ModuleItem, ModuleScreenProps, NavigationItem, NetworkCatalogItem, NetworkLocationsResult, NotificationPreferences, OperatorActionDecision, OperatorMessage, Review, ReviewResult, ReviewsProps, Summary, Tab, TelegramWebApp, Workspace } from '@/features/telegram/types';
import { useLatestCallback } from '@/hooks/useLatestCallback';
import { clearLeadJourneyToken, saveLeadJourneyToken, type JourneyAction, type LeadJourneyKey } from '@/lib/leadJourney';
import { cancelMobileJob, confirmMobileAction, mobileAuthHeaders, mobileJsonHeaders, mobileScopeQuery, readMobileJson, retryMobileJob, type MobileJob } from '@/lib/mobileDataClient';
import { resolveMobileRoute } from '@/lib/mobileDeepLinkRouter';
import { resolveMobileAttentionScreen } from '@/lib/mobileTaskRouter';
import { AnimatePresence, motion } from 'framer-motion';
import {
	ArrowLeft,
	Bot, Building2,
	Check,
	ChevronRight, CircleEllipsis,
	ClipboardCheck, Copy, CreditCard,
	LayoutGrid, Loader2, MapPinned,
	MessageCircle, Network, PackageCheck, Pencil, Radio,
	Search, Send,
	ShieldCheck,
	Sparkles, Star,
	TrendingUp,
	WandSparkles, X
} from 'lucide-react';
import { FormEvent, Suspense, lazy, useEffect, useRef, useState } from 'react';

const BusinessInputSettings = lazy(() => import('@/components/operator/BusinessInputSettings').then((module) => ({ default: module.BusinessInputSettings })));
const ContentRules = lazy(() => import('@/components/operator/ContentRules').then((module) => ({ default: module.ContentRules })));
const WorkJournal = lazy(() => import('@/components/WorkJournal').then((module) => ({ default: module.WorkJournal })));
const OperatorWorkdayInput = lazy(() => import('@/components/operator/OperatorWorkdayInput').then((module) => ({ default: module.OperatorWorkdayInput })));
const PartnershipsMobileModule = lazy(() => import('@/components/telegram/PartnershipsMobileModule').then((module) => ({ default: module.PartnershipsMobileModule })));
const CompaniesMobileModule = lazy(() => import('@/components/telegram/CompaniesMobileModule').then((module) => ({ default: module.CompaniesMobileModule })));
const CommunitySourcesMobileModule = lazy(() => import('@/components/telegram/CommunitySourcesMobileModule').then((module) => ({ default: module.CommunitySourcesMobileModule })));
const CommunityFeedMobile = lazy(() => import('@/components/telegram/CommunityFeedMobile'));
const AgentsMobileModule = lazy(() => import('@/components/telegram/AgentsMobileModule'));
const DiagnosticsMobileModule = lazy(() => import('@/components/telegram/DiagnosticsMobileModule'));
const InfluencersMobileModule = lazy(() => import('@/components/telegram/InfluencersMobileModule'));
const ProgressMobileModule = lazy(() => import('@/components/telegram/ProgressMobileModule').then((module) => ({ default: module.ProgressMobileModule })));
const TodayMobileV2 = lazy(() => import('@/components/telegram/TodayMobileV2').then((module) => ({ default: module.TodayMobileV2 })));
const GrowthNavigation = lazy(() => import('@/components/telegram/GrowthNavigation'));
const LeadJourneyOnboarding = lazy(() => import('@/components/telegram/LeadJourneyOnboarding'));

declare global {
  interface Window { Telegram?: { WebApp?: TelegramWebApp } }
}


const webApp = () => window.Telegram?.WebApp;

const readJson = readMobileJson;
const scopeQuery = mobileScopeQuery;
const authHeaders = mobileJsonHeaders;
const authOnlyHeaders = mobileAuthHeaders;
const isTab = (value: string | null): value is Tab => Boolean(value && ['today', 'tasks', 'feed', 'reviews', 'progress', 'operator', 'more', 'menu'].includes(value));

export const TelegramControlWorkspace = () => {
  const preview = isPreview();
  const initData = webApp()?.initData || '';
  const launchParams = new URLSearchParams(window.location.search);
  const rawJourneyParam = launchParams.get('journey_token') || launchParams.get('tgWebAppStartParam') || webApp()?.initDataUnsafe?.start_param || '';
  const journeyToken = rawJourneyParam.startsWith('journey_') ? rawJourneyParam.slice(8) : /^[A-Za-z0-9_-]{32,}$/.test(rawJourneyParam) ? rawJourneyParam : '';
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(preview ? previewBootstrap : null);
  const [workspace, setWorkspace] = useState<Workspace | null>(preview ? { items: previewBootstrap.summary?.attention_items, summary: previewBootstrap.summary } : null);
  const [todayData, setTodayData] = useState<TodayPayload | null>(preview ? previewToday : null);
  const [todayLoading, setTodayLoading] = useState(!preview);
  const [todaySlowLoading, setTodaySlowLoading] = useState(false);
  const [progressData, setProgressData] = useState<ProgressPayload | null>(preview ? previewProgress : null);
  const [progressLoading, setProgressLoading] = useState(false);
  const [tab, setTab] = useState<Tab>('today');
  const [module, setModule] = useState('');
  const [loading, setLoading] = useState(!preview);
  const [slowLoading, setSlowLoading] = useState(false);
  const [error, setError] = useState('');
  const [picker, setPicker] = useState(false);
  const [pickerNetwork, setPickerNetwork] = useState<NetworkCatalogItem | null>(null);
  const [networkLocations, setNetworkLocations] = useState<NetworkLocationsResult>({});
  const [networkLocationsLoading, setNetworkLocationsLoading] = useState(false);
  const [networkSearch, setNetworkSearch] = useState('');
  const [search, setSearch] = useState('');
  const [taskFilter, setTaskFilter] = useState('attention');
  const [reviewStatus, setReviewStatus] = useState('unanswered');
  const [reviewSource, setReviewSource] = useState('');
  const [reviewRating, setReviewRating] = useState('');
  const [reviewLocation, setReviewLocation] = useState('');
  const [deepLinkReviewId, setDeepLinkReviewId] = useState('');
  const [deepLinkItemId, setDeepLinkItemId] = useState('');
  const [selectedReviews, setSelectedReviews] = useState<string[]>([]);
  const [actionPreview, setActionPreview] = useState<MobileActionPreview | null>(null);
  const [reviews, setReviews] = useState<ReviewResult>(preview ? { items: previewReviews, counts: { total: 164, unanswered: 50, drafts: 12 } } : {});
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [command, setCommand] = useState('');
  const [operatorBusy, setOperatorBusy] = useState(false);
  const [operatorActionBusy, setOperatorActionBusy] = useState<{ actionId: string; decision: OperatorActionDecision } | null>(null);
  const [reviewActionBusy, setReviewActionBusy] = useState('');
  const [messages, setMessages] = useState<OperatorMessage[]>([]);
  const [historyLoadedFor, setHistoryLoadedFor] = useState('');
  const [operatorConversationId, setOperatorConversationId] = useState<string | null>(null);
  const operatorSending = useRef(false);
  const operatorHistoryVersion = useRef(0);
  const pendingOperatorRequest = useRef({ businessId: "", text: "", id: "" });
  const [moduleData, setModuleData] = useState<ModuleData>({});
  const [moduleLoading, setModuleLoading] = useState(false);
  const [moduleSaving, setModuleSaving] = useState(false);
  const [moduleActionBusy, setModuleActionBusy] = useState('');
  const [restoredJob, setRestoredJob] = useState<MobileJob | null>(null);
  const [restoredJobBusy, setRestoredJobBusy] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [paywall, setPaywall] = useState<NavigationItem | null>(null);
  const [journeyAction, setJourneyAction] = useState<JourneyAction | null>(null);
  const trackedTodayScope = useRef('');
  const scopeRequestVersion = useRef(0);
  const catalogSearchVersion = useRef(0);
  const networkLocationSearchVersion = useRef(0);

  const scope = bootstrap?.selected_scope || bootstrap?.summary?.scope;
  const summary = workspace?.summary || bootstrap?.summary;
  const tasks = workspace?.items?.length ? workspace.items : summary?.attention_items || [];
  const hasActiveTasks = tasks.some((item) => item.status === 'in_progress');
  const catalog = bootstrap?.catalog;
  const hasSwitcher = Boolean(scope?.can_switch || Number(catalog?.total_choices || 0) > 1);
  const visibleNavigation = (bootstrap?.navigation || []).filter((item) => item.status !== 'hidden' && item.key !== 'analytics');

  const onboardingKey = bootstrap?.user?.id ? `localos-mini-onboarding-v3:${bootstrap.user.id}` : '';
  const finishOnboarding = () => {
    if (onboardingKey) {
      try { window.localStorage.setItem(onboardingKey, 'completed'); } catch { /* WebView may block persistent storage. */ }
    }
    setShowOnboarding(false);
    trackMobileInteraction('onboarding_completed');
  };

  const loadWorkspace = async (nextScope?: MobileScope, requestVersion = scopeRequestVersion.current) => {
    if (preview) return;
    const params = scopeQuery(nextScope || scope);
    const result = await fetch(`/api/operator/mobile/workspace?${params.toString()}`, { headers: authHeaders() }).then(readJson<Workspace>);
    if (requestVersion !== scopeRequestVersion.current) return;
    setWorkspace(result);
  };

  const loadToday = async (nextScope?: MobileScope, enabled = bootstrap?.today_v2_enabled !== false, quietly = false, requestVersion = scopeRequestVersion.current) => {
    if (preview || !enabled) return;
    if (!quietly) setTodayLoading(true);
    const timer = window.setTimeout(() => { if (requestVersion === scopeRequestVersion.current) setTodaySlowLoading(true); }, 400);
    try {
      const params = scopeQuery(nextScope || scope);
      const result = await fetch(`/api/operator/mobile/today?${params.toString()}`, { headers: authHeaders() }).then(readJson<TodayPayload>);
      if (requestVersion !== scopeRequestVersion.current) return;
      setTodayData(result); setError('');
    } catch (requestError) {
      if (!quietly && requestVersion === scopeRequestVersion.current) setError(requestError instanceof Error ? requestError.message : 'Не удалось собрать картину дня.');
    } finally {
      window.clearTimeout(timer);
      if (requestVersion === scopeRequestVersion.current) {
        setTodaySlowLoading(false);
        if (!quietly) setTodayLoading(false);
      }
    }
  };

  const trackMobileInteraction = (eventName: string, target = '') => {
    if (preview) return;
    void fetch('/api/operator/mobile/interaction', {
      method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, event_name: eventName, screen: tab, target }),
    }).catch(() => undefined);
  };

  const trackProductEvent = (eventName: 'mission_open' | 'statistics_flow_opened' | 'statistics_preview_created' | 'statistics_preview_confirmed' | 'crm_request_created', objectId?: string) => {
    if (preview || scope?.kind !== 'business' || !scope.id) return;
    void fetch('/api/product/events', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ event_name: eventName, business_id: scope.id, surface: 'telegram_mini_app', object_type: objectId ? 'growth_action' : undefined, object_id: objectId }),
      keepalive: true,
    }).catch(() => undefined);
  };

  const loadJourneyAction = async (actionId: string, businessId: string) => {
    if (!actionId || !businessId) return;
    const response = await fetch(`/api/journey-actions/${encodeURIComponent(actionId)}?business_id=${encodeURIComponent(businessId)}`, { headers: authHeaders() }).then(readJson<{ action?: JourneyAction }>);
    setJourneyAction(response.action || null);
  };

  const loadBootstrap = async (query = '', cursor = '', appendCatalog = false, catalogOnly = false, requestedVersion?: number) => {
    if (preview) return;
    if (!initData) { setLoading(false); return; }
    const requestVersion = catalogOnly ? requestedVersion ?? catalogSearchVersion.current + 1 : 0;
    if (catalogOnly && requestedVersion === undefined) catalogSearchVersion.current = requestVersion;
    const timer = catalogOnly ? undefined : window.setTimeout(() => setSlowLoading(true), 400);
    try {
      const deepLink = new URLSearchParams(window.location.search);
      const filters: Record<string, string> = {};
      deepLink.forEach((value, key) => {
        if (key.startsWith('filter_')) filters[key.slice(7)] = value;
      });
      const result = await fetch('/api/operator/telegram/bootstrap', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
          init_data: initData,
          q: query,
          cursor,
          scope_type: deepLink.get('scope_type'),
          scope_id: deepLink.get('scope_id'),
          screen: deepLink.get('screen'),
          item_type: deepLink.get('item_type'),
          item_id: deepLink.get('item_id'),
          filters,
        }),
      }).then(readJson<Bootstrap>);
      if (catalogOnly && requestVersion !== catalogSearchVersion.current) return;
      if (result.web_session_token) window.sessionStorage.setItem('localos_mini_session', result.web_session_token);
      if (!catalogOnly && journeyToken && result.selected_scope?.kind === 'business' && result.selected_scope.id) {
        saveLeadJourneyToken(journeyToken);
        try {
          const claimed = await fetch('/api/journeys/claim', {
            method: 'POST', headers: authHeaders(),
            body: JSON.stringify({ token: journeyToken, business_id: result.selected_scope.id, surface: 'telegram_mini_app' }),
          }).then(readJson<{ action?: JourneyAction }>);
          setJourneyAction(claimed.action || null);
          if (claimed.action) result.resolved_deep_link = { screen: 'today', item_type: 'journey_action', item_id: claimed.action.id };
          clearLeadJourneyToken();
        } catch {
          // Keep the token so the same journey can be resumed in web or retried in Mini App.
        }
      }
      if (!catalogOnly && result.resolved_deep_link?.item_type === 'journey_action' && result.resolved_deep_link.item_id && result.selected_scope?.kind === 'business' && result.selected_scope.id) {
        await loadJourneyAction(result.resolved_deep_link.item_id, result.selected_scope.id);
      }
      if (appendCatalog) {
        setBootstrap((current) => ({
          ...current,
          catalog: {
            ...result.catalog,
            platform: current?.catalog?.platform || result.catalog?.platform,
            networks: current?.catalog?.networks || result.catalog?.networks,
            businesses: [...(current?.catalog?.businesses || []), ...(result.catalog?.businesses || [])],
          },
        }));
      } else if (catalogOnly) {
        setBootstrap((current) => ({ ...current, catalog: result.catalog }));
      } else {
        setBootstrap(result);
        setRestoredJob(result.active_job || null);
      }
      if (!catalogOnly && !query && !cursor) await Promise.all([loadWorkspace(result.selected_scope), loadToday(result.selected_scope, result.today_v2_enabled !== false)]);
      setError('');
    } catch (requestError) {
      if (!catalogOnly || requestVersion === catalogSearchVersion.current) setError(requestError instanceof Error ? requestError.message : 'Не удалось открыть ЛокалОС.');
    } finally {
      if (timer !== undefined) window.clearTimeout(timer);
      if (!catalogOnly) { setSlowLoading(false); setLoading(false); }
    }
  };

  const loadBootstrapEffect = useLatestCallback(loadBootstrap);
  const loadTodayEffect = useLatestCallback(loadToday);
  const loadWorkspaceEffect = useLatestCallback(loadWorkspace);
  const trackMobileInteractionEffect = useLatestCallback(trackMobileInteraction);

  useEffect(() => { webApp()?.ready?.(); webApp()?.expand?.(); void loadBootstrapEffect(); }, [loadBootstrapEffect]);

  useEffect(() => {
    if (!onboardingKey) return;
    const forced = new URLSearchParams(window.location.search).get('onboarding') === '1';
    if (preview && !forced) return;
    let completed = false;
    try { completed = window.localStorage.getItem(onboardingKey) === 'completed'; } catch { completed = false; }
    setShowOnboarding(forced || !completed);
  }, [onboardingKey, preview]);

  useMobileJobPolling({ job: restoredJob, scope, onJob: setRestoredJob, onComplete: () => void loadWorkspaceEffect() });

  const retryRestoredJob = async () => {
    if (!restoredJob?.id) return;
    setRestoredJobBusy(true);
    try { const result = await retryMobileJob(restoredJob.id, scope); setRestoredJob(result.job || null); setError(''); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось повторить задачу.'); }
    finally { setRestoredJobBusy(false); }
  };

  const cancelRestoredJob = async () => {
    if (!restoredJob?.id) return;
    setRestoredJobBusy(true);
    try { const result = await cancelMobileJob(restoredJob.id, scope); setRestoredJob(result.job || null); setError(''); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось остановить задачу.'); }
    finally { setRestoredJobBusy(false); }
  };
  useEffect(() => {
    if (!picker || !initData) return;
    if (pickerNetwork) return;
    const requestVersion = catalogSearchVersion.current + 1;
    catalogSearchVersion.current = requestVersion;
    const timer = window.setTimeout(() => void loadBootstrapEffect(search.trim(), '', false, true, requestVersion), 250);
    return () => window.clearTimeout(timer);
  }, [initData, loadBootstrapEffect, picker, pickerNetwork, search]);

  const loadNetworkLocations = async (network: NetworkCatalogItem, query = '', cursor = '', append = false, requestedVersion?: number) => {
    if (!network.id) return;
    const requestVersion = requestedVersion ?? networkLocationSearchVersion.current + 1;
    if (requestedVersion === undefined) networkLocationSearchVersion.current = requestVersion;
    if (preview) {
      const items = (catalog?.businesses || []).filter((item) => item.network_id === network.id);
      setNetworkLocations({ items, counts: { total: items.length }, cursor: null });
      return;
    }
    setNetworkLocationsLoading(true);
    try {
      const params = new URLSearchParams({ network_id: network.id });
      if (query.trim()) params.set('q', query.trim());
      if (cursor) params.set('cursor', cursor);
      const result = await fetch(`/api/operator/mobile/network-locations?${params.toString()}`, { headers: authOnlyHeaders() }).then(readJson<NetworkLocationsResult>);
      if (requestVersion !== networkLocationSearchVersion.current) return;
      setNetworkLocations((current) => ({
        ...result,
        items: append ? [...(current.items || []), ...(result.items || [])] : result.items,
      }));
      setError('');
    } catch (requestError) {
      if (requestVersion === networkLocationSearchVersion.current) setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить точки сети.');
    } finally {
      if (requestVersion === networkLocationSearchVersion.current) setNetworkLocationsLoading(false);
    }
  };

  const loadNetworkLocationsEffect = useLatestCallback(loadNetworkLocations);

  useEffect(() => {
    if (!picker || !pickerNetwork?.id) return;
    const requestVersion = networkLocationSearchVersion.current + 1;
    networkLocationSearchVersion.current = requestVersion;
    const timer = window.setTimeout(() => void loadNetworkLocationsEffect(pickerNetwork, networkSearch, '', false, requestVersion), 200);
    return () => window.clearTimeout(timer);
  }, [loadNetworkLocationsEffect, picker, pickerNetwork, networkSearch]);

  useEffect(() => {
    const back = webApp()?.BackButton;
    if (!back) return;
    const goBack = () => { if (module) setModule(''); else if (pickerNetwork) setPickerNetwork(null); else if (picker) setPicker(false); else setTab('today'); };
    if (showOnboarding) back.hide();
    else if (module || picker || tab !== 'today') { back.show(); back.onClick(goBack); } else back.hide();
    return () => back.offClick(goBack);
  }, [module, picker, pickerNetwork, showOnboarding, tab]);

  const chooseScope = async (kind: string, id?: string | null) => {
    if (preview) { setPicker(false); setPickerNetwork(null); return true; }
    const requestVersion = scopeRequestVersion.current + 1;
    scopeRequestVersion.current = requestVersion;
    setLoading(true);
    try {
      const result = await fetch('/api/operator/telegram/scope', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: initData, scope_type: kind, scope_id: id || null }),
      }).then(readJson<Bootstrap>);
      if (requestVersion !== scopeRequestVersion.current) return false;
      const scopeChanged = result.selected_scope?.kind !== scope?.kind || (result.selected_scope?.id || null) !== (scope?.id || null);
      if (scopeChanged) {
        setSelectedReviews([]);
        setActionPreview(null);
        setReviewLocation('');
        setDeepLinkReviewId('');
        setDeepLinkItemId('');
        setRestoredJob(result.active_job || null);
        setRestoredJobBusy(false);
      }
      setBootstrap((current) => ({ ...current, ...result, resolved_deep_link: result.resolved_deep_link, catalog: current?.catalog }));
      await Promise.all([
        loadWorkspace(result.selected_scope, requestVersion),
        loadToday(result.selected_scope, result.today_v2_enabled !== false, false, requestVersion),
      ]);
      if (requestVersion !== scopeRequestVersion.current) return false;
      setProgressData(null);
      setPicker(false); setPickerNetwork(null); setNetworkSearch(''); setTab('today'); setError('');
      return true;
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сменить бизнес.'); return false; }
    finally { setLoading(false); }
  };

  const openScopeSwitcher = () => {
    setSearch('');
    setNetworkSearch('');
    const parent = scope?.parent_scope;
    const networkId = scope?.kind === 'network' ? scope.id : parent?.id;
    const knownNetwork = (catalog?.networks || []).find((item) => item.id === networkId);
    if (networkId) {
      setPickerNetwork(knownNetwork || {
        id: networkId,
        name: scope?.kind === 'network' ? scope.name : parent?.name,
        locations_count: scope?.kind === 'network' ? scope.business_ids?.length : undefined,
      });
    } else {
      setPickerNetwork(null);
    }
    setPicker(true);
  };

  const loadReviews = async (status = reviewStatus, append = false, requestVersion = scopeRequestVersion.current) => {
    if (bootstrap?.navigation?.find((item) => item.key === 'reviews')?.status === 'read_only') return;
    if (preview) { setReviews({ items: previewReviews, counts: { total: 164, unanswered: 50, drafts: 12 } }); return; }
    setReviewsLoading(true);
    try {
      const params = scopeQuery(scope); params.set('status', status); params.set('limit', '20');
      if (reviewSource) params.set('source', reviewSource);
      if (reviewRating) params.set('rating', reviewRating);
      if (reviewLocation) params.set('location_id', reviewLocation);
      if (deepLinkReviewId) params.set('review_id', deepLinkReviewId);
      if (append && reviews.cursor) params.set('cursor', reviews.cursor);
      const result = await fetch(`/api/operator/mobile/reviews?${params.toString()}`, { headers: authHeaders() }).then(readJson<ReviewResult>);
      if (requestVersion !== scopeRequestVersion.current) return;
      setReviews((current) => ({ ...result, items: append ? [...(current.items || []), ...(result.items || [])] : result.items }));
      setError('');
    } catch (requestError) {
      if (requestVersion === scopeRequestVersion.current) setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить отзывы.');
    } finally {
      if (requestVersion === scopeRequestVersion.current) setReviewsLoading(false);
    }
  };

  const loadReviewsEffect = useLatestCallback(loadReviews);

  useEffect(() => { if (tab === 'reviews') void loadReviewsEffect(reviewStatus); }, [loadReviewsEffect, tab, reviewStatus, reviewSource, reviewRating, reviewLocation, scope?.kind, scope?.id]);

  useEffect(() => {
    operatorHistoryVersion.current++;
    setMessages([]); setOperatorConversationId(null); setHistoryLoadedFor(''); setOperatorBusy(false);
  }, [scope?.kind, scope?.id]);
  const loadOperatorHistory = async () => {
    if (preview || scope?.kind !== 'business' || !scope.id) return;
    const scopeKey = `${scope.kind}:${scope.id}`;
    if (historyLoadedFor === scopeKey) return;
    const version = scopeRequestVersion.current;
    const historyVersion = operatorHistoryVersion.current;
    try {
      const params = scopeQuery(scope);
      const result = await fetch(`/api/operator/mobile/operator/history?${params}`, { headers: authHeaders() }).then(readJson<{ conversation?: { id?: string }; items?: Array<{ id?: string; role?: string; content?: string; status?: string; capability?: string; result_json?: { input_type?: string; mobile_route?: { screen?: string }; approval?: { action_id?: string } } }> }>);
      if (version !== scopeRequestVersion.current || historyVersion !== operatorHistoryVersion.current) return;
      setOperatorConversationId(result.conversation?.id || null);
      setMessages((result.items || []).map((item) => ({ id: item.id, role: item.role === 'user' ? 'user' : 'operator', text: item.content || '', status: item.status, capability: item.capability, screen: item.result_json?.mobile_route?.screen, action_id: item.result_json?.approval?.action_id })));
      setHistoryLoadedFor(scopeKey);
    } catch (failure) { if (version === scopeRequestVersion.current) setError(failure instanceof Error ? failure.message : 'Не удалось загрузить историю.'); }
  };
  const loadOperatorHistoryEffect = useLatestCallback(loadOperatorHistory);
  useEffect(() => { if (tab === 'operator') void loadOperatorHistoryEffect(); }, [loadOperatorHistoryEffect, tab, scope?.kind, scope?.id]);

  const loadModule = async (moduleKey = module, quietly = false, requestVersion = scopeRequestVersion.current) => {
    if (!moduleKey || preview) return;
    const navigationKey = moduleKey === 'finance_import' || moduleKey === 'analytics' ? 'finance' : moduleKey;
    const navigationEntry = bootstrap?.navigation?.find((item) => item.key === navigationKey);
    if (navigationEntry?.status === 'read_only' && navigationEntry.preview_available && !['influencers', 'partnerships'].includes(navigationKey)) {
      setModuleData({ status: 'payment_required', access: navigationEntry, items: [], preview: { title: 'Посмотрите, как работает раздел', summary: navigationEntry.reason, skeleton_count: 3 } });
      setModuleLoading(false);
      setProgressLoading(false);
      setError('');
      return;
    }
    if (!quietly) setModuleLoading(true);
    if (moduleKey === 'work_journal' || moduleKey === 'company' || moduleKey === 'companies' || moduleKey === 'community_sources' || moduleKey === 'influencers') { setModuleLoading(false); setError(''); return; }
    const params = scopeQuery(scope);
    if (moduleKey === 'progress') {
      if (!quietly) setProgressLoading(true);
      await fetch(`/api/operator/mobile/progress?${params.toString()}`, { headers: authHeaders() })
        .then(readJson<ProgressPayload>)
        .then((result) => { if (requestVersion === scopeRequestVersion.current) { setProgressData(result); setError(''); } })
        .catch((requestError) => { if (requestVersion === scopeRequestVersion.current) setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить прогресс.'); })
        .finally(() => { if (!quietly && requestVersion === scopeRequestVersion.current) { setModuleLoading(false); setProgressLoading(false); } });
      return;
    }
    const load = (key: string) => fetch(`/api/operator/mobile/modules/${key}?${params.toString()}`, { headers: authHeaders() }).then(readJson<ModuleData>);
    await load(moduleKey === 'finance_import' ? 'finance' : moduleKey)
      .then((result) => { if (requestVersion === scopeRequestVersion.current) { setModuleData(result); setError(''); } })
      .catch((requestError) => { if (requestVersion === scopeRequestVersion.current) setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить раздел.'); })
      .finally(() => { if (!quietly && requestVersion === scopeRequestVersion.current) setModuleLoading(false); });
  };

  const loadModuleEffect = useLatestCallback(loadModule);

  useEffect(() => {
    const destination = module || (tab === 'progress' ? 'progress' : '');
    if (!destination) return;
    if (preview) { setModuleData(previewModules[destination] || {}); return; }
    void loadModuleEffect(destination);
  }, [loadModuleEffect, module, preview, tab, scope?.kind, scope?.id]);

  useEffect(() => {
    if (tab !== 'today' || !bootstrap?.today_v2_enabled) return;
    const interval = todayData?.active_work?.length ? 20000 : 300000;
    const timer = window.setInterval(() => void loadTodayEffect(scope, true, true), interval);
    return () => window.clearInterval(timer);
  }, [loadTodayEffect, tab, bootstrap?.today_v2_enabled, scope, todayData?.active_work?.length]);

  useEffect(() => {
    if (tab !== 'tasks' || !hasActiveTasks) return;
    const timer = window.setInterval(() => void loadWorkspaceEffect(scope), 15000);
    return () => window.clearInterval(timer);
  }, [hasActiveTasks, loadWorkspaceEffect, scope, tab]);

  useEffect(() => {
    const scopeKey = `${scope?.kind || ''}:${scope?.id || ''}`;
    if (tab !== 'today' || !bootstrap?.today_v2_enabled || !todayData?.as_of || trackedTodayScope.current === scopeKey) return;
    trackedTodayScope.current = scopeKey;
    trackMobileInteractionEffect('today_open');
  }, [bootstrap?.today_v2_enabled, scope?.id, scope?.kind, tab, todayData?.as_of, trackMobileInteractionEffect]);

  const updateService = async (item: ModuleItem, values: { name: string; description: string; price: string; category: string }) => {
    if (!item.id || preview) return;
    setModuleActionBusy(item.id);
    try {
      await fetch(`/api/operator/mobile/services/${item.id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify({ ...values, scope_type: scope?.kind, scope_id: scope?.id || null }),
      }).then(readJson<{ item?: ModuleItem }>);
      await loadModule('services'); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить услугу.'); }
    finally { setModuleActionBusy(''); }
  };

  const generateContentDraft = async (item: ModuleItem) => {
    if (!item.id || preview) return;
    setModuleActionBusy(item.id);
    try {
      await fetch(`/api/operator/mobile/content/items/${item.id}/generate-draft`, {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }),
      }).then(readJson<{ plan?: unknown }>);
      await loadModule('content', true);
      setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось подготовить черновик.'); }
    finally { setModuleActionBusy(''); }
  };

  const updateContentItem = async (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => {
    if (!item.id || preview) return;
    setModuleActionBusy(item.id);
    try {
      await fetch(`/api/operator/mobile/content/items/${item.id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify({ ...values, scope_type: scope?.kind, scope_id: scope?.id || null }),
      }).then(readJson<{ plan?: unknown }>);
      await loadModule('content', true); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить контент.'); }
    finally { setModuleActionBusy(''); }
  };

  useEffect(() => {
    if (!bootstrap) return;
    const requestedScreen = bootstrap.resolved_deep_link?.screen === 'analytics' ? 'finance' : bootstrap.resolved_deep_link?.screen;
    const requestedEntry = bootstrap.navigation?.find((item) => item.key === requestedScreen);
    if (requestedEntry?.status === 'read_only' && !requestedEntry.preview_available && requestedEntry.reason?.toLowerCase().includes('тариф')) {
      setPaywall(requestedEntry);
      setTab('today');
      setModule('');
      return;
    }
    const route = resolveMobileRoute(bootstrap.resolved_deep_link, bootstrap.navigation || []);
    setTab(route.tab);
    setModule(route.module);
    if (route.tab === 'reviews') {
      const status = route.filters.status;
      const rating = route.filters.rating;
      if (status && ['unanswered', 'drafts', 'answered', 'all'].includes(status)) setReviewStatus(status);
      if (rating && ['1', '2', '3', '4', '5'].includes(rating)) setReviewRating(rating);
      setDeepLinkReviewId(route.reviewId);
    }
    setDeepLinkItemId(route.itemId);
  }, [bootstrap]);

  const openMobileTarget = (screen = 'tasks', targetScope?: { kind?: string; id?: string }) => {
    const destination = screen === 'analytics' || screen === 'finance_import' ? 'finance' : screen;
    const navigationEntry = bootstrap?.navigation?.find((item) => item.key === destination);
    if (navigationEntry?.status === 'read_only' && !navigationEntry.preview_available && navigationEntry.reason?.toLowerCase().includes('тариф')) {
      setPaywall(navigationEntry);
      return;
    }
    const navigate = () => {
      if (isTab(screen)) { setModule(''); setTab(screen); return; }
      const moduleTarget = screen === 'analytics' ? 'finance' : screen;
      setTab('more'); setModule(moduleTarget || 'tasks');
    };
    if (targetScope?.id && (targetScope.id !== scope?.id || targetScope.kind !== scope?.kind)) {
      void chooseScope(targetScope.kind || 'business', targetScope.id).then((changed) => { if (changed) navigate(); });
      return;
    }
    navigate();
  };

  const completeLeadJourneyOnboarding = (direction?: LeadJourneyKey) => {
    finishOnboarding();
    if (direction === 'maps') openMobileTarget('cards');
    else if (direction === 'content') openMobileTarget('content');
    else if (direction === 'partnerships') openMobileTarget('partnerships');
    else if (direction === 'influencers') openMobileTarget('influencers');
  };

  const createCrmRequest = async ({ crmName, crmUrl, contact, comment }: { crmName: string; crmUrl: string; contact: string; comment: string }) => {
    if (scope?.kind !== 'business' || !scope.id) throw new Error('Для запроса выберите одну точку.');
    if (preview) return;
    await fetch(`/api/business/${scope.id}/crm-integration-requests`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ crm_name: crmName, crm_url: crmUrl, contact, note: comment, scope_type: scope.kind, scope_id: scope.id }),
    }).then(readJson<unknown>);
    trackProductEvent('crm_request_created', crmName);
  };

  const openTask = (item: AttentionItem) => {
    openMobileTarget(resolveMobileAttentionScreen(item), item.target_scope);
  };

  const sendOperator = async (text: string, source?: VoiceSubmission) => {
    if (!text.trim() || operatorSending.current) return;
    if (scope?.kind !== 'business' || !scope.id) { setPicker(true); setError('Для команды выберите одну точку.'); return; }
    const version = scopeRequestVersion.current;
    if (pendingOperatorRequest.current.businessId !== scope.id || pendingOperatorRequest.current.text !== text) pendingOperatorRequest.current = { businessId: scope.id, text, id: crypto.randomUUID() };
    operatorHistoryVersion.current++;
    operatorSending.current = true; setOperatorBusy(true); setTab('operator');
    try {
      const result = await fetch('/api/operator/chat', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ business_id: scope.id, message: text, channel: 'telegram_mini_app', conversation_id: operatorConversationId, request_id: pendingOperatorRequest.current.id, ...source }),
      }).then(readJson<{ conversation_id?: string; operator_result?: { async_job_id?: string; message_id?: string; input_type?: string; chat_response?: string; summary?: string; status?: string; capability?: string; mobile_route?: { screen?: string }; approval?: { action_id?: string } } }>);
      if (version !== scopeRequestVersion.current) return;
      if(result.operator_result)result.operator_result=await waitForOperatorResult(result.operator_result,scope.id,authOnlyHeaders,()=>version===scopeRequestVersion.current);
      if(version!==scopeRequestVersion.current)return;
      pendingOperatorRequest.current = { businessId: "", text: "", id: "" };
      setOperatorConversationId(result.conversation_id || null);
      setMessages((current) => [...current, { role: 'user', text }, { role: 'operator', id: result.operator_result?.message_id,
        input_type: result.operator_result?.input_type, text: result.operator_result?.chat_response || result.operator_result?.summary || 'Проверьте результат в заданиях.',
        status: result.operator_result?.status, capability: result.operator_result?.capability, screen: result.operator_result?.mobile_route?.screen, action_id: result.operator_result?.approval?.action_id }]);
      setCommand(''); await loadWorkspace();
    } catch (failure) {
      if (version !== scopeRequestVersion.current) return;
      if (source) throw failure;
      setError(failure instanceof Error ? failure.message : 'Не удалось отправить запрос.');
    } finally { operatorSending.current = false; if (version === scopeRequestVersion.current) setOperatorBusy(false); }
  };
  const askOperator = async (event: FormEvent) => { event.preventDefault(); await sendOperator(command); };

  const resolveOperatorAction = async (actionId: string, decision: OperatorActionDecision) => {
    if (scope?.kind !== 'business' || !scope.id || operatorActionBusy) return;
    setOperatorActionBusy({ actionId, decision });
    setMessages((current) => current.map((item) => item.action_id === actionId ? { ...item, action_error: undefined } : item));
    try {
      const result = await fetch(`/api/operator/actions/${encodeURIComponent(actionId)}/${decision === 'confirm' ? 'confirm' : 'reject'}`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ business_id: scope.id }),
      }).then(readJson<{ operator_result?: { chat_response?: string; summary?: string; status?: string } }>);
      const operatorResult = result.operator_result;
      setMessages((current) => current.map((item) => item.action_id === actionId ? {
        ...item,
        text: operatorResult?.chat_response || operatorResult?.summary || (decision === 'confirm' ? 'Действие выполнено.' : 'Действие отклонено.'),
        status: operatorResult?.status || (decision === 'confirm' ? 'completed' : 'rejected'),
        action_id: undefined,
        action_error: undefined,
      } : item));
      await loadWorkspace();
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Не удалось обработать решение.';
      setMessages((current) => current.map((item) => item.action_id === actionId ? { ...item, action_error: message } : item));
    } finally {
      setOperatorActionBusy(null);
    }
  };

  const prepareSelectedReviews = async (reviewIds: string[]) => {
    if (!reviewIds.length) return;
    if (preview) {
      setActionPreview({ action_id: 'preview-action', estimated_credits: reviewIds.length, is_mass_action: reviewIds.length > 1, external_effects: false, target_businesses: [{ id: 'preview', name: 'Весёлая расчёска' }], objects: previewReviews.filter((item) => reviewIds.includes(item.id)).map((item) => ({ id: item.id, author_name: item.author_name, business_name: item.location_name })) });
      return;
    }
    setReviewActionBusy('bulk');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'review_replies.generate', input: { review_ids: reviewIds } }),
      }).then(readJson<{ preview?: MobileActionPreview }>);
      setActionPreview(result.preview || null); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось подготовить проверку перед действием.'); }
    finally { setReviewActionBusy(''); }
  };

  const confirmSelectedReviews = async () => {
    if (!actionPreview?.action_id) return;
    if (preview) { setActionPreview(null); setSelectedReviews([]); return; }
    setReviewActionBusy('bulk');
    try {
      await fetch(`/api/operator/mobile/actions/${actionPreview.action_id}/confirm`, { method: 'POST', headers: authHeaders(), body: '{}' }).then(readJson<{ operator_result?: unknown }>);
      setActionPreview(null); setSelectedReviews([]); await loadReviews(reviewStatus); await loadWorkspace(); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Действие не выполнено.'); }
    finally { setReviewActionBusy(''); }
  };

  const generateReviewReply = async (review: Review, confirmed: boolean) => {
    if (preview) return;
    if (!confirmed) await prepareSelectedReviews([review.id]);
    else await confirmSelectedReviews();
  };

  const updateReviewDraft = async (review: Review, replyText: string) => {
    if (preview || !review.reply_draft_id) return;
    setReviewActionBusy(review.id);
    try {
      await fetch(`/api/operator/mobile/review-drafts/${review.reply_draft_id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify({ reply_text: replyText, scope_type: scope?.kind, scope_id: scope?.id || null }),
      }).then(readJson<{ draft?: unknown }>);
      await loadReviews(reviewStatus);
      setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить черновик.'); }
    finally { setReviewActionBusy(''); }
  };

  const markReviewPublished = async (review: Review) => {
    if (preview || !review.reply_draft_id) return;
    setReviewActionBusy(review.id);
    try {
      await fetch(`/api/operator/mobile/review-drafts/${review.reply_draft_id}/mark-manual-published`, {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }),
      }).then(readJson<{ manual_publish?: unknown }>);
      await loadReviews(reviewStatus); await loadWorkspace(); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось отметить публикацию.'); }
    finally { setReviewActionBusy(''); }
  };

  const saveNotifications = async (preferences: NotificationPreferences) => {
    if (preview) { setModuleData((current) => ({ ...current, preferences })); return; }
    setModuleSaving(true);
    try {
      const result = await fetch('/api/operator/mobile/settings/notifications', {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, notifications: preferences }),
      }).then(readJson<{ preferences?: NotificationPreferences } >);
      setModuleData((current) => ({ ...current, preferences: result.preferences || preferences }));
      setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить настройки.'); }
    finally { setModuleSaving(false); }
  };

  if (!initData && !preview) return <TelegramGate />;
  if (loading && !bootstrap) return <LoadingScreen slow={slowLoading} />;

  return (
    <Suspense fallback={<LoadingScreen slow={false} />}>
      <ScopeProvider value={{ scope, hasSwitcher, openSwitcher: openScopeSwitcher }}>
      <MobileShell
        header={<TopBar />}
        error={error}
        overlay={<><ActionPreviewSheet preview={actionPreview} busy={reviewActionBusy === 'bulk'} confirmLabel="Подготовить ответы" onConfirm={() => void confirmSelectedReviews()} onCancel={() => setActionPreview(null)} /><JobProgressSheet job={restoredJob} busy={restoredJobBusy} onClose={() => setRestoredJob(null)} onRetry={() => void retryRestoredJob()} onCancel={() => void cancelRestoredJob()} />{paywall ? <SubscriptionPaywall item={paywall} close={() => setPaywall(null)} /> : null}{showOnboarding ? <LeadJourneyOnboarding onFinish={completeLeadJourneyOnboarding} /> : null}</>}
        navigation={!picker && !showOnboarding ? <BottomNav current={tab} setCurrent={(next) => openMobileTarget(next)} /> : null}
      >
        <AnimatePresence initial={false} mode="wait">
          <motion.div key={`${tab}-${module}-${picker}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring}>
            {picker && pickerNetwork ? <NetworkScopePicker network={pickerNetwork} currentScope={scope} locations={networkLocations.items || []} total={networkLocations.counts?.total || 0} nextCursor={networkLocations.cursor} search={networkSearch} setSearch={setNetworkSearch} loading={networkLocationsLoading} choose={chooseScope} back={() => { setPickerNetwork(null); setNetworkSearch(''); }} loadMore={() => void loadNetworkLocations(pickerNetwork, networkSearch, networkLocations.cursor || '', true)} /> : null}
            {picker && !pickerNetwork ? <ScopePicker catalog={catalog} search={search} setSearch={setSearch} choose={chooseScope} openNetwork={(network) => { setPickerNetwork(network); setNetworkSearch(''); }} loadMore={() => void loadBootstrap(search.trim(), catalog?.next_business_cursor || '', true, true)} /> : null}
            {!picker && tab === 'today' ? <>{journeyAction && scope?.kind === 'business' && scope.id ? <div className="px-4 pb-4"><JourneyActionCard action={journeyAction} businessId={scope.id} surface="telegram_mini_app" dark onUpdated={(nextAction) => {
              if (nextAction) setJourneyAction(nextAction);
              else void loadJourneyAction(journeyAction.id, scope.id || '');
              void loadToday(scope, true, true);
            }} /></div> : null}{bootstrap?.today_v2_enabled !== false ? <TodayMobileV2 data={todayData} loading={todayLoading} slowLoading={todaySlowLoading} command={command} setCommand={setCommand} ask={askOperator} openTarget={openMobileTarget} openProgress={() => openMobileTarget(scope?.kind === 'platform' ? 'tasks' : 'progress')} openSources={scope?.kind === 'business' ? () => openMobileTarget('community_sources') : undefined} track={trackMobileInteraction} trackProduct={trackProductEvent} openFinanceImport={() => openMobileTarget('finance_import')} refresh={() => void loadToday(scope, true, true)} /> : <Today summary={summary} tasks={tasks} command={command} setCommand={setCommand} ask={askOperator} openTask={openTask} />}</> : null}
            {!picker && tab === 'tasks' ? <Tasks items={tasks} filter={taskFilter} setFilter={setTaskFilter} openTask={openTask} /> : null}
            {!picker && tab === 'feed' ? bootstrap?.navigation?.find((item) => item.key === 'feed')?.status === 'read_only' ? <Screen title="Лента" subtitle="Главные темы и сигналы из вашей индустрии."><LockedModulePreview item={bootstrap.navigation.find((item) => item.key === 'feed')} /></Screen> : <CommunityFeedMobile scope={scope} preview={preview} openSources={scope?.kind === 'business' ? () => openMobileTarget('community_sources') : undefined} openTarget={openMobileTarget} /> : null}
            {!picker && tab === 'reviews' ? bootstrap?.navigation?.find((item) => item.key === 'reviews')?.status === 'read_only' ? <Screen title="Отзывы" subtitle="Новые отзывы и подготовленные ответы."><LockedModulePreview item={bootstrap.navigation.find((item) => item.key === 'reviews')} /></Screen> : <Reviews result={reviews} summary={summary} status={reviewStatus} setStatus={setReviewStatus} source={reviewSource} setSource={setReviewSource} rating={reviewRating} setRating={setReviewRating} location={reviewLocation} setLocation={setReviewLocation} selected={selectedReviews} setSelected={setSelectedReviews} loading={reviewsLoading} actionBusy={reviewActionBusy} generate={generateReviewReply} updateDraft={updateReviewDraft} markPublished={markReviewPublished} prepareSelected={() => void prepareSelectedReviews(selectedReviews)} loadMore={() => void loadReviews(reviewStatus, true)} /> : null}
            {!picker && tab === 'progress' ? <Screen title="Прогресс" subtitle="Выполненные шаги, текущие проблемы и одно следующее действие.">{bootstrap?.navigation?.find((item) => item.key === 'progress')?.status === 'read_only' ? <LockedModulePreview item={bootstrap.navigation.find((item) => item.key === 'progress')} /> : <ProgressMobileModule data={progressData} loading={progressLoading} openTarget={openMobileTarget} track={trackMobileInteraction} trackProduct={trackProductEvent} />}</Screen> : null}
            {!picker && tab === 'operator' ? bootstrap?.navigation?.find((item) => item.key === 'operator')?.status === 'read_only' ? <Screen title="Оператор" subtitle="Поручения, согласования и результаты работы."><LockedModulePreview item={bootstrap.navigation.find((item) => item.key === 'operator')} /></Screen> : <Operator businessId={scope?.kind === 'business' ? scope.id || '' : ''} conversationId={operatorConversationId} onConversation={setOperatorConversationId} sendVoice={sendOperator} messages={messages} busy={operatorBusy} actionBusy={operatorActionBusy} command={command} setCommand={setCommand} ask={askOperator} resolveAction={resolveOperatorAction} openScreen={openMobileTarget} /> : null}
            {!picker && tab === 'more' && !module ? <More navigation={visibleNavigation} onOpen={openMobileTarget} openProgress={() => openMobileTarget('progress')} onLocked={setPaywall} restartTour={() => setShowOnboarding(true)} /> : null}
            {!picker && tab === 'menu' ? <UtilityMenu navigation={visibleNavigation} onOpen={openMobileTarget} /> : null}
            {!picker && tab === 'more' && module === 'settings' && scope?.kind === 'business' && scope.id ? <><BusinessInputSettings key={scope.id} businessId={scope.id} headers={authOnlyHeaders} /><ContentRules key={`rules-${scope.id}`} businessId={scope.id} headers={authOnlyHeaders} /></> : null}
            {!picker && tab === 'more' && module ? <ModuleScreen module={module} focusItemId={deepLinkItemId} scope={scope} access={bootstrap?.navigation?.find((item) => item.key === (module === 'finance_import' || module === 'analytics' ? 'finance' : module))} data={moduleData} loading={moduleLoading} progressData={progressData} progressLoading={progressLoading} saving={moduleSaving} actionBusy={moduleActionBusy} saveNotifications={saveNotifications} updateService={updateService} generateContentDraft={generateContentDraft} updateContentItem={updateContentItem} reload={() => loadModule(module)} openTarget={openMobileTarget} track={trackMobileInteraction} trackProduct={trackProductEvent} openTasks={() => { setModule(''); setTab('tasks'); }} requestCrm={createCrmRequest} back={() => setModule('')} /> : null}
          </motion.div>
        </AnimatePresence>
      </MobileShell>
      </ScopeProvider>
    </Suspense>
  );
};

const TopBar = () => {
  const { scope, hasSwitcher, openSwitcher } = useMobileScope();
  const Icon = scope?.kind === 'platform' ? ShieldCheck : scope?.kind === 'network' ? Network : Building2;
  const networkCount = scope?.business_ids?.length || 0;
  const meta = scope?.kind === 'network'
    ? `Саммари сети · ${locationCountLabel(networkCount)}`
    : scope?.kind === 'platform'
      ? 'Вся платформа'
      : scope?.parent_scope?.id
        ? 'Точка сети · Сменить точку'
        : 'Ваш бизнес';
  return <header className="px-4 pb-4 pt-[calc(16px+env(safe-area-inset-top))]">
    <div className="mb-4 flex items-center justify-between"><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-zinc-500"><span className="relative h-8 w-8 overflow-hidden rounded-[11px] bg-white shadow-[0_10px_28px_rgba(255,92,51,0.24)] ring-1 ring-inset ring-white/10"><img src={localOsLogo} alt="" className="absolute -left-3 -top-2 h-14 w-14 max-w-none outline outline-1 -outline-offset-1 outline-white/10" /></span>ЛокалОС</div><span className="flex items-center gap-2 rounded-full bg-white/[0.05] px-3 py-2 text-[11px] text-zinc-400 ring-1 ring-inset ring-white/[0.07]"><i className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Работает</span></div>
    <button type="button" onClick={openSwitcher} disabled={!hasSwitcher} className="flex min-h-14 w-full items-center gap-3 rounded-[20px] bg-white/[0.045] px-3 text-left ring-1 ring-inset ring-white/[0.075] transition-[background-color,transform] active:scale-[0.96] disabled:active:scale-100"><span className="grid h-11 w-11 place-items-center rounded-[14px] bg-primary/15 text-primary"><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-[15px]">{scope?.name || 'ЛокалОС'}</b><small className="text-xs text-zinc-500">{meta}</small></span>{hasSwitcher ? <ChevronRight className="h-5 w-5 text-zinc-600" /> : null}</button>
  </header>;
};

const Today = ({ summary, tasks, command, setCommand, ask, openTask }: { summary?: Summary; tasks: AttentionItem[]; command: string; setCommand: (value: string) => void; ask: (event: FormEvent) => void; openTask: (item: AttentionItem) => void }) => {
  const primary = tasks[0];
  return <div className="px-4">
    <section className="rounded-[28px] bg-gradient-to-b from-zinc-900 to-zinc-900/70 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)] ring-1 ring-inset ring-white/[0.08]"><div className="flex items-center gap-2 text-xs text-zinc-500"><Sparkles className="h-4 w-4 text-primary" />Главное на сегодня</div><div className="mt-4 flex items-start gap-4"><div className="min-w-0 flex-1"><h1 className="text-balance text-[26px] font-semibold leading-8 tracking-[-0.045em]">{primary?.title || 'Новых задач нет'}</h1><p className="mt-2 text-pretty text-sm leading-6 text-zinc-400">{primary?.description || 'По последним загруженным данным решений от вас сейчас не требуется.'}</p></div>{primary?.count ? <b className="rounded-2xl bg-primary/15 px-3 py-2 text-xl tabular-nums text-primary">{primary.count}</b> : <Check className="h-8 w-8 text-emerald-400" />}</div>{primary ? <PrimaryButton onClick={() => openTask(primary)}>Открыть задачу</PrimaryButton> : null}</section>
  <form onSubmit={ask} className="mt-3 rounded-[22px] bg-white/[0.04] p-3 ring-1 ring-inset ring-white/[0.07]"><label className="px-1 text-xs font-medium text-zinc-500">Что сделать?</label><div className="mt-2 flex gap-2"><input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Например: подготовь ответы" className="min-h-12 min-w-0 flex-1 rounded-2xl bg-black/20 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" /><button aria-label="Отправить" className="grid h-12 w-12 place-items-center rounded-2xl bg-primary text-white transition-transform active:scale-[0.96]"><Send className="h-4 w-4" /></button></div><p className="px-1 pt-2 text-[11px] leading-4 text-zinc-600">Опишите задачу. Внешние действия всегда попросят подтверждение.</p></form>
    {tasks.slice(1, 3).map((item) => <TaskRow key={item.id || item.title} item={item} onClick={() => openTask(item)} />)}
    <section className="mt-6"><h2 className="text-lg font-semibold tracking-[-0.025em]">Что уже сделано</h2><div className="mt-3 grid grid-cols-2 gap-2">{(summary?.metrics || []).slice(0, 4).map((metric) => <div key={metric.key} className="rounded-[20px] bg-white/[0.035] p-4 ring-1 ring-inset ring-white/[0.06]"><small className="text-zinc-600">{metric.label}</small><b className="mt-1 block text-2xl tabular-nums">{metric.value ?? '—'}</b><span className="mt-1 block truncate text-[10px] text-zinc-700">{metric.source_label || metric.source || 'ЛокалОС'}</span></div>)}</div></section>
  </div>;
};

const Tasks = ({ items, filter, setFilter, openTask }: { items: AttentionItem[]; filter: string; setFilter: (value: string) => void; openTask: (item: AttentionItem) => void }) => {
  const visible = items.filter((item) => filter === 'done' ? item.status === 'completed' : filter === 'working' ? item.status === 'in_progress' : item.status === 'needs_attention' || !item.status);
  return <Screen title="В работе" subtitle="Задачи, которые ждут вашего решения, выполняются или уже завершены."><Segments value={filter} setValue={setFilter} options={[['attention', 'Нужно решить'], ['working', 'Выполняется'], ['done', 'Готово']]} />{visible.length ? visible.map((item) => <TaskRow key={item.id || item.title} item={item} onClick={() => openTask(item)} />) : <Empty icon={ClipboardCheck} title={filter === 'attention' ? 'Решений не требуется' : filter === 'working' ? 'Сейчас ничего не выполняется' : 'Готовые результаты появятся здесь'} text={filter === 'attention' ? 'Здесь появятся только задачи, для которых нужно ваше решение.' : 'Когда состояние изменится, список обновится автоматически.'} />}</Screen>;
};

const Reviews = ({ result, summary, status, setStatus, source, setSource, rating, setRating, location, setLocation, selected, setSelected, loading, actionBusy, generate, updateDraft, markPublished, prepareSelected, loadMore }: ReviewsProps) => {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const metrics = summary?.metrics || [];
  const mapTotal = metrics.find((item) => item.key === 'map_reviews_total' || item.key === 'map')?.value;
  const loadedTotal = result.counts?.total ?? metrics.find((item) => item.key === 'reviews_loaded' || item.key === 'loaded')?.value;
  const toggle = (id: string) => setSelected(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id].slice(0, 5));
  const activeFilters = [source, rating, location].filter(Boolean).length;
  return <Screen title="Отзывы" subtitle="Каждое число раскрывается до конкретных клиентов и точек.">
    {mapTotal !== undefined || loadedTotal !== undefined ? <div className="mb-3 grid grid-cols-3 gap-2 rounded-[22px] bg-white/[0.035] p-3 ring-1 ring-inset ring-white/[0.06]"><MetricMini label="На карте" value={mapTotal} /><MetricMini label="Загружено" value={loadedTotal} /><MetricMini label="Без ответа" value={result.counts?.unanswered} accent /></div> : null}
    <Segments value={status} setValue={(value) => { setSelected([]); setStatus(value); }} options={[[ 'unanswered', `Без ответа ${result.counts?.unanswered || 0}` ], [ 'drafts', `Черновики ${result.counts?.drafts || 0}` ], [ 'all', 'Все' ]]} />
    <button type="button" onClick={() => setFiltersOpen((value) => !value)} className="mb-3 flex min-h-11 w-full items-center justify-between rounded-2xl bg-white/[0.035] px-4 text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.06] active:scale-[0.96]"><span>Фильтры{activeFilters ? ` · ${activeFilters}` : ''}</span><ChevronRight className={`h-4 w-4 transition-transform ${filtersOpen ? 'rotate-90' : ''}`} /></button>
    <AnimatePresence initial={false}>{filtersOpen ? <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={spring} className="mb-3 overflow-hidden"><div className="grid grid-cols-2 gap-2 rounded-[22px] bg-white/[0.025] p-3 ring-1 ring-inset ring-white/[0.06]"><FilterSelect label="Источник" value={source} setValue={setSource} options={(result.filters?.sources || []).map((item) => [item, item])} /><FilterSelect label="Оценка" value={rating} setValue={setRating} options={[1, 2, 3, 4, 5].map((item) => [String(item), `${item} ★`])} /><div className="col-span-2"><FilterSelect label="Точка" value={location} setValue={setLocation} options={(result.filters?.locations || []).map((item) => [item.id, item.name])} /></div></div></motion.div> : null}</AnimatePresence>
    {selected.length ? <div className="sticky top-2 z-10 mb-3 flex min-h-14 items-center gap-3 rounded-[20px] bg-zinc-900/95 px-3 shadow-2xl ring-1 ring-inset ring-primary/25 backdrop-blur-xl"><b className="flex-1 text-sm tabular-nums">Выбрано: {selected.length}</b><button type="button" onClick={() => setSelected([])} className="min-h-11 px-3 text-xs text-zinc-500">Сбросить</button><button type="button" disabled={actionBusy === 'bulk'} onClick={prepareSelected} className="min-h-11 rounded-[14px] bg-primary px-4 text-xs font-semibold disabled:opacity-50">Подготовить</button></div> : null}
    {loading ? <ReviewSkeleton /> : result.items?.length ? result.items.map((review) => <ReviewCard key={review.id} review={review} selected={selected.includes(review.id)} toggle={() => toggle(review.id)} busy={actionBusy === review.id || actionBusy === 'bulk'} generate={generate} updateDraft={updateDraft} markPublished={markPublished} />) : <Empty icon={MessageCircle} title="Отзывов нет" text="В этом фильтре пока нет отзывов. Измените фильтры или вернитесь позже." />}
    {result.cursor ? <button onClick={loadMore} className="mt-3 min-h-12 w-full rounded-2xl bg-white/[0.05] text-sm font-semibold ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Показать ещё</button> : null}
  </Screen>;
};

const ReviewCard = ({ review, selected, toggle, busy, generate, updateDraft, markPublished }: { review: Review; selected: boolean; toggle: () => void; busy: boolean; generate: (review: Review, confirmed: boolean) => Promise<void>; updateDraft: (review: Review, text: string) => Promise<void>; markPublished: (review: Review) => Promise<void> }) => {
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(review.reply_draft_text || '');
  useEffect(() => setDraftText(review.reply_draft_text || ''), [review.reply_draft_text]);
  const publishedAt = review.published_at ? new Date(review.published_at) : null;
  const publishedAtLabel = publishedAt && !Number.isNaN(publishedAt.getTime())
    ? publishedAt.toLocaleString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'дата не указана источником';
  return <article className={`mb-3 rounded-[24px] p-4 ring-1 ring-inset transition-[background-color,box-shadow] ${selected ? 'bg-primary/[0.075] ring-primary/30' : 'bg-white/[0.04] ring-white/[0.07]'}`}><div className="flex items-start gap-3"><button type="button" aria-label={selected ? 'Убрать из выбранных' : 'Выбрать отзыв'} aria-pressed={selected} onClick={toggle} className={`grid h-11 w-11 shrink-0 place-items-center rounded-[14px] text-sm font-bold active:scale-[0.96] ${selected ? 'bg-primary text-white' : 'bg-amber-400/10 text-amber-300'}`}>{selected ? <Check className="h-5 w-5" /> : review.rating || '—'}</button><div className="min-w-0 flex-1"><b className="block truncate">{review.author_name || 'Гость'}</b><small className="block truncate text-zinc-600">{[review.source, review.location_name].filter(Boolean).join(' · ')}</small><small className="mt-1 block text-[11px] font-medium text-zinc-400">Отзыв от {publishedAtLabel}</small></div></div><p className="mt-4 whitespace-pre-wrap text-pretty text-sm leading-6 text-zinc-300">{review.text || 'Клиент оставил оценку без текста.'}</p>{review.response_text ? <ResponseBox label="Опубликованный ответ" text={review.response_text} /> : review.reply_draft_text ? <div className="mt-4 rounded-[18px] bg-black/20 p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex min-h-11 items-center justify-between"><small className="font-semibold text-primary">Черновик ЛокалОС</small><div className="flex"><button type="button" onClick={() => setEditing((value) => !value)} className="min-h-11 px-3 text-xs font-semibold text-zinc-400">{editing ? 'Отмена' : 'Изменить'}</button><button type="button" aria-label="Скопировать" onClick={() => void navigator.clipboard.writeText(draftText)} className="grid h-11 w-11 place-items-center text-zinc-500 active:scale-[0.96]"><Copy className="h-4 w-4" /></button></div></div>{editing ? <><textarea value={draftText} onChange={(event) => setDraftText(event.target.value)} className="min-h-32 w-full resize-none rounded-2xl bg-white/[0.04] p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><button disabled={busy} onClick={() => void updateDraft(review, draftText)} className="mt-2 min-h-11 w-full rounded-2xl bg-primary text-sm font-semibold disabled:opacity-50">{busy ? 'Сохраняем…' : 'Сохранить черновик'}</button></> : <><p className="text-sm leading-6 text-zinc-300">{draftText}</p><button type="button" disabled={busy} onClick={() => void markPublished(review)} className="mt-3 min-h-11 w-full rounded-2xl bg-white/[0.045] text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96] disabled:opacity-50">{busy ? 'Сохраняем…' : 'Я опубликовал ответ вручную'}</button></>}</div> : <button disabled={busy} onClick={() => void generate(review, false)} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-primary/12 text-sm font-semibold text-primary ring-1 ring-inset ring-primary/20 active:scale-[0.96] disabled:opacity-50"><WandSparkles className="h-4 w-4" />{busy ? 'Проверяем…' : 'Подготовить ответ'}</button>}</article>;
};

const ResponseBox = ({ label, text }: { label: string; text: string }) => <div className="mt-4 rounded-[18px] bg-black/20 p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex items-center justify-between"><small className="font-semibold text-primary">{label}</small><button type="button" aria-label="Скопировать" onClick={() => void navigator.clipboard.writeText(text)} className="grid h-11 w-11 place-items-center text-zinc-500 active:scale-[0.96]"><Copy className="h-4 w-4" /></button></div><p className="text-sm leading-6 text-zinc-300">{text}</p></div>;

const Operator = ({ businessId, conversationId, onConversation, sendVoice, messages, busy, actionBusy, command, setCommand, ask, resolveAction, openScreen }: {
  businessId: string; conversationId: string | null; onConversation: (id: string) => void; sendVoice: (text: string, source?: VoiceSubmission) => Promise<void>;
  messages: OperatorMessage[];
  busy: boolean;
  actionBusy: { actionId: string; decision: OperatorActionDecision } | null;
  command: string;
  setCommand: (value: string) => void;
  ask: (event: FormEvent) => void;
  resolveAction: (actionId: string, decision: OperatorActionDecision) => void;
  openScreen: (screen: string) => void;
}) => <Screen title="Оператор" subtitle="Напишите задачу обычными словами. Результат появится здесь или в нужном разделе.">
  {businessId && <button type="button" onClick={() => openScreen('settings')} className="text-sm text-primary underline">Город и валюта — в «Профиль и бизнес»</button>}
  <div className="min-h-[42vh] space-y-3">
    {messages.length ? messages.map((message, index) => {
      const resolving = Boolean(message.action_id && actionBusy?.actionId === message.action_id);
      return <div key={message.id || `${message.role}-${index}`} className={`max-w-[88%] rounded-[20px] px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'ml-auto bg-primary text-white' : 'bg-white/[0.05] text-zinc-300 ring-1 ring-inset ring-white/[0.07]'}`}>
        <p className="whitespace-pre-wrap text-pretty">{message.text}</p>
        {businessId && message.role === 'operator' && message.id && <OperatorSpeech key={`${businessId}:${message.id}`} businessId={businessId} messageId={message.id} prepare={message.input_type === 'voice'} headers={authOnlyHeaders} />}
        {message.role === 'operator' && message.status === 'completed' ? <small className="mt-2 flex items-center gap-1 text-[10px] text-emerald-400"><Check className="h-3 w-3" />Готово</small> : null}
        {message.role === 'operator' && message.status === 'rejected' ? <small className="mt-2 flex items-center gap-1 text-[10px] text-zinc-500"><X className="h-3 w-3" />Отклонено</small> : null}
        {message.role === 'operator' && message.status === 'approval_required' && message.action_id ? <div className="mt-3 rounded-[18px] bg-black/20 p-2 ring-1 ring-inset ring-amber-300/15">
          <div className="flex items-center gap-2 px-1 pb-2 text-[11px] leading-4 text-amber-200/80"><ShieldCheck className="h-4 w-4 shrink-0" />Проверьте действие: оно не выполнится без вашего решения.</div>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" disabled={Boolean(actionBusy)} onClick={() => resolveAction(message.action_id || '', 'reject')} className="flex min-h-11 items-center justify-center gap-2 rounded-[14px] bg-white/[0.055] px-3 text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.08] transition-[background-color,transform] active:scale-[0.96] disabled:opacity-50 disabled:active:scale-100">{resolving && actionBusy?.decision === 'reject' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <X className="h-4 w-4" />}Отклонить</button>
            <button type="button" disabled={Boolean(actionBusy)} onClick={() => resolveAction(message.action_id || '', 'confirm')} className="flex min-h-11 items-center justify-center gap-2 rounded-[14px] bg-primary px-3 text-xs font-semibold text-white shadow-[0_10px_30px_rgba(255,92,51,0.2)] transition-[filter,transform] active:scale-[0.96] disabled:opacity-50 disabled:active:scale-100">{resolving && actionBusy?.decision === 'confirm' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}Подтвердить</button>
          </div>
          {message.action_error ? <p role="alert" className="mt-2 px-1 text-pretty text-[11px] leading-4 text-red-300">{message.action_error}</p> : null}
        </div> : null}
        {message.role === 'operator' && message.screen ? <button type="button" onClick={() => openScreen(message.screen || 'tasks')} className="mt-3 min-h-11 w-full rounded-[14px] bg-white/[0.05] text-xs font-semibold text-zinc-200 ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] active:scale-[0.96]">Открыть результат</button> : null}
      </div>;
    }) : <Empty icon={Bot} title="Что поручить?" text="Например: «Подготовь ответы на плохие отзывы» или «Проверь свежесть карточки»." />}
    {busy ? <div className="flex items-center gap-2 text-sm text-zinc-500"><Loader2 className="h-4 w-4 animate-spin text-primary motion-reduce:animate-none" />Определяю задачу и готовлю результат…</div> : null}
  </div>
    {businessId && <OperatorVoiceInput key={businessId} businessId={businessId} channel="telegram_mini_app" conversationId={conversationId} onSubmit={sendVoice} disabled={busy} headers={authOnlyHeaders} />}
    {businessId && <OperatorWorkdayInput key={`inputs:${businessId}`} businessId={businessId} channel="telegram_mini_app" conversationId={conversationId} disabled={busy} headers={authOnlyHeaders} onConversation={onConversation} />}
  <form onSubmit={ask} className="sticky bottom-24 mt-4 flex gap-2 rounded-[20px] bg-zinc-900 p-2 ring-1 ring-inset ring-white/[0.08]"><input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Напишите задачу" className="min-h-12 min-w-0 flex-1 bg-transparent px-3 text-sm outline-none placeholder:text-zinc-700" /><button aria-label="Отправить задачу" className="grid h-12 w-12 place-items-center rounded-2xl bg-primary transition-transform active:scale-[0.96]"><Send className="h-4 w-4" /></button></form>
</Screen>;

const billingHref = (item?: NavigationItem) => {
  const target = item?.billing_url || '/dashboard/profile?focus=subscription#subscription';
  const [base, hash] = target.split('#');
  const separator = base.includes('?') ? '&' : '?';
  return `${base}${separator}return_to=${encodeURIComponent(`/telegram/control?screen=${item?.key || 'today'}`)}${hash ? `#${hash}` : ''}`;
};

const SubscriptionPaywall = ({ item, close }: { item: NavigationItem; close: () => void }) => <div className="fixed inset-0 z-50 flex items-end bg-black/70 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Раздел доступен на другом тарифе"><div className="w-full rounded-[28px] bg-zinc-900 p-5 shadow-2xl ring-1 ring-inset ring-white/[0.08]"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/15 text-primary"><CreditCard className="h-5 w-5" /></span><h2 className="mt-4 text-xl font-semibold">Нужен тариф «{item.required_tier_name || 'Управление'}»</h2><p className="mt-2 text-sm leading-6 text-zinc-500">{item.reason || 'Подключите тариф для выбранной точки.'}</p><a href={billingHref(item)} className="mt-5 flex min-h-12 w-full items-center justify-center rounded-2xl bg-primary px-4 text-sm font-semibold text-white transition-transform duration-150 active:scale-[0.96]">Выбрать тариф</a><button type="button" onClick={close} className="mt-2 min-h-12 w-full rounded-2xl bg-white/[0.04] text-sm font-semibold text-zinc-400 transition-transform duration-150 active:scale-[0.96]">Закрыть</button></div></div>;

const LockedModulePreview = ({ item }: { item?: NavigationItem }) => <section className="overflow-hidden rounded-[24px] bg-gradient-to-b from-primary/[0.10] to-white/[0.035] p-5 shadow-[0_18px_54px_rgba(0,0,0,0.24),0_0_0_1px_rgba(255,92,51,0.14)]"><span className="text-xs font-semibold text-primary">Доступно на тарифе «{item?.required_tier_name || 'Управление'}»</span><h2 className="mt-3 text-balance text-xl font-semibold">Посмотрите, какой результат даст раздел</h2><p className="mt-2 text-pretty text-sm leading-6 text-zinc-500">{item?.reason || 'Полные данные и действия откроются после повышения тарифа.'}</p><div className="mt-5 space-y-2" aria-hidden="true">{[0, 1, 2].map((index) => <div key={index} className="rounded-[18px] bg-black/20 p-4 blur-[3px] select-none"><div className="h-3 w-2/3 rounded-full bg-white/15" /><div className="mt-3 h-2 w-full rounded-full bg-white/[0.08]" /><div className="mt-2 h-2 w-4/5 rounded-full bg-white/[0.08]" /></div>)}</div><a href={billingHref(item)} className="mt-5 flex min-h-12 w-full items-center justify-center rounded-2xl bg-primary px-4 text-center text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.22)] transition-transform duration-150 active:scale-[0.96]">Открыть раздел — тариф «{item?.required_tier_name || 'Управление'}»</a></section>;

const More = ({ navigation, onOpen, openProgress, onLocked, restartTour }: { navigation: NavigationItem[]; onOpen: (key: string) => void; openProgress: () => void; onLocked: (item: NavigationItem) => void; restartTour: () => void }) => {
  return <Screen title="Пути роста" subtitle="Выберите цель. Внутри будет первое действие и текущие данные.">
    <GrowthNavigation navigation={navigation} onOpen={onOpen} onOpenProgress={openProgress} onLocked={onLocked} onRestartTour={restartTour} />
  </Screen>;
};

const UtilityMenu = ({ navigation, onOpen }: { navigation: NavigationItem[]; onOpen: (key: string) => void }) => {
  const hiddenFromMenu = new Set(['today', 'progress', 'cards', 'content', 'influencers', 'partnerships']);
  const items = navigation.filter((item) => item.status !== 'hidden' && !hiddenFromMenu.has(item.key));
  return <Screen title="Ещё" subtitle="Рабочие очереди, управление и настройки.">
    <div className="space-y-2">
      {items.map((item) => <button key={item.key} type="button" onClick={() => onOpen(item.key)} className="flex min-h-14 w-full items-center gap-3 rounded-[18px] bg-white/[0.04] px-4 text-left ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] duration-150 active:scale-[0.96]"><span className="grid h-10 w-10 place-items-center rounded-[13px] bg-primary/10 text-primary"><CircleEllipsis className="h-4 w-4" /></span><span className="min-w-0 flex-1"><b className="block text-sm">{item.label}</b>{item.reason ? <small className="mt-0.5 block truncate text-zinc-600">{item.reason}</small> : null}</span><ChevronRight className="h-4 w-4 text-zinc-700" /></button>)}
    </div>
  </Screen>;
};

const moduleNames: Record<string, [string, string]> = {
  progress: ['Прогресс', 'Выполненные шаги, текущие проблемы и следующее действие.'],
  cards: ['Карточки на картах', 'Данные из Яндекса и 2ГИС, свежесть, ошибки и история обновлений.'], content: ['Контент', 'Календарь, текущий план, черновики и публикации.'], services: ['Услуги', 'Цены, описания, данные с карт и предложения по улучшению.'],
  work_journal: ['Рабочий журнал', 'Наблюдения команды и рекомендации по визитам.'],
  finance: ['Финансы', 'Выручка, прибыль, средний чек, загрузка и динамика.'], finance_import: ['Загрузить финансовую сводку', 'Сначала проверьте распознанные данные. В аналитику они попадут только после подтверждения.'], analytics: ['Финансы', 'Выручка, заказы и динамика по выбранному периоду.'], partnerships: ['Партнёрства', 'Договорённости с партнёрами и инструкции сотрудникам.'], company: ['Моя компания', 'Локации, карты, контакты, публичные услуги, аудиты и история.'], companies: ['Компании', 'Клиенты, лиды, партнёры, локации и история публичных данных.'], agents: ['Работа ЛокалОС', 'Запуски, текущие этапы, результаты и ошибки.'], settings: ['Настройки и подключения', 'Уведомления, источники, тариф и доступ.'], diagnostics: ['Диагностика', 'Ошибки парсеров, интеграций и фоновых задач.'],
  community_sources: ['Источники Ленты', 'Публичные Telegram-каналы и открытые группы, из которых ЛокалОС собирает ленту и главные темы.'], influencers: ['Инфлюенсеры', 'Подходящие локальные авторы, предложение, сообщения, размещения и результат.'],
};

const ModuleScreen = ({ module, focusItemId, scope, access, data, loading, progressData, progressLoading, saving, actionBusy, saveNotifications, updateService, generateContentDraft, updateContentItem, reload, openTarget, track, trackProduct, openTasks, requestCrm, back }: ModuleScreenProps) => {
  const content = moduleNames[module] || ['Раздел', 'Данные и доступные действия.'];
  return <Screen title={content[0]} subtitle={content[1]} action={<button aria-label="Назад" onClick={back} className="grid h-11 w-11 place-items-center rounded-2xl bg-white/[0.05] ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"><ArrowLeft className="h-4 w-4" /></button>}>
    {module === 'companies' || module === 'company' ? <CompaniesMobileModule businessId={module === 'company' && scope?.kind === 'business' ? scope.id : null} /> : module === 'community_sources' ? <CommunitySourcesMobileModule businessId={scope?.kind === 'business' ? scope.id : null} /> : module === 'influencers' ? <InfluencersMobileModule scope={scope} focusItemId={focusItemId} /> : module === 'partnerships' ? <PartnershipsMobileModule scope={scope} openBusiness={id => openTarget('partnerships', { kind: 'business', id })} /> : access?.status === 'read_only' || data.status === 'payment_required' ? <LockedModulePreview item={access || data.access} /> : module === 'progress' ? <ProgressMobileModule data={progressData} loading={progressLoading} openTarget={openTarget} track={track} trackProduct={trackProduct} /> : loading ? <ReviewSkeleton /> : module === 'settings' ? <NotificationSettings preferences={data.preferences || {}} saving={saving} save={saveNotifications} /> : module === 'cards' ? <CardsModule scope={scope} items={data.items || []} reload={reload} /> : module === 'content' ? <ContentModule focusItemId={focusItemId} scope={scope} items={data.items || []} filters={data.filters} busy={actionBusy} generate={generateContentDraft} update={updateContentItem} reload={reload} /> : module === 'services' ? <ServicesModule focusItemId={focusItemId} scope={scope} items={data.items || []} busy={actionBusy} update={updateService} reload={reload} /> : module === 'work_journal' ? <WorkJournal embedded businessId={scope?.kind === 'business' ? scope.id : null} headers={authOnlyHeaders} /> : module === 'finance' || module === 'finance_import' ? <FinanceModule scope={scope} items={data.items || []} reload={reload} openTasks={openTasks} requestCrm={requestCrm} initialSection={module === 'finance_import' ? 'import' : 'overview'} trackProduct={trackProduct} /> : module === 'agents' ? <AgentsMobileModule items={data.items || []} scope={scope} reload={reload} canRun={Boolean(data.available_actions?.some((action) => action.key === 'agents.run'))} /> : module === 'diagnostics' ? <DiagnosticsMobileModule items={data.items || []} scope={scope} reload={reload} /> : module === 'analytics' ? <AnalyticsModule items={data.items || []} /> : <ModuleUnavailable />}
  </Screen>;
};

const ServicesModule = ({ focusItemId, scope, items, busy, update, reload }: { focusItemId?: string; scope?: MobileScope; items: ModuleItem[]; busy: string; update: (item: ModuleItem, values: { name: string; description: string; price: string; category: string }) => Promise<void>; reload: () => Promise<void> }) => {
  const [editing, setEditing] = useState('');
  const [analysis, setAnalysis] = useState<(MobileActionPreview & { mode: string; service_count?: number }) | null>(null);
  const [running, setRunning] = useState('');
  const [error, setError] = useState('');
  const [itemPreview, setItemPreview] = useState<MobileActionPreview | null>(null);
  useEffect(() => {
    if (!focusItemId || !items.some((item) => item.id === focusItemId)) return;
    setEditing(focusItemId);
    window.requestAnimationFrame(() => document.getElementById(`service-item-${focusItemId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }, [focusItemId, items]);
  const run = async (mode: string, confirmed = false) => { setRunning(mode); try { if (confirmed) { if (!analysis?.action_id) throw new Error('Проверка устарела. Подготовьте её заново.'); await fetch(`/api/operator/mobile/actions/${analysis.action_id}/confirm`, { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }) }).then(readJson); setAnalysis(null); await reload(); } else { const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: `services.${mode}`, input: { business_id: scope?.kind === 'business' ? scope.id : null, request_id: window.crypto.randomUUID() } }) }).then(readJson<{ preview?: MobileActionPreview }>); if (!result.preview?.action_id) throw new Error('Не удалось подготовить проверку.'); setAnalysis({ mode, ...result.preview, service_count: result.preview.objects?.length || 0 }); } setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проанализировать услуги.'); } finally { setRunning(''); } };
  const changeActiveState = async (item: ModuleItem) => { if (!item.id) return; setRunning(item.id); try { const capability = item.status === 'archived' ? 'services.restore' : 'services.archive'; const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability, input: { service_id: item.id } }) }).then(readJson<{ preview?: MobileActionPreview }>); setItemPreview(result.preview || null); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить изменение.'); } finally { setRunning(''); } };
  const confirmActiveState = async () => { if (!itemPreview?.action_id) return; setRunning(itemPreview.action_id); try { await confirmMobileAction(itemPreview.action_id, scope); setItemPreview(null); await reload(); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось изменить услугу.'); } finally { setRunning(''); } };
  return <div><div className="mb-3 grid grid-cols-2 gap-2"><button type="button" disabled={Boolean(running) || scope?.kind !== 'business'} onClick={() => void run('optimize')} className="min-h-20 rounded-[20px] bg-primary/[0.1] p-3 text-left ring-1 ring-inset ring-primary/20 active:scale-[0.96] disabled:opacity-45"><WandSparkles className="h-5 w-5 text-primary" /><b className="mt-2 block text-xs">Улучшить услуги</b><small className="mt-1 block text-[10px] leading-4 text-zinc-600">Названия и описания</small></button><button type="button" disabled={Boolean(running) || scope?.kind !== 'business'} onClick={() => void run('compress')} className="min-h-20 rounded-[20px] bg-white/[0.04] p-3 text-left ring-1 ring-inset ring-white/[0.07] active:scale-[0.96] disabled:opacity-45"><PackageCheck className="h-5 w-5 text-primary" /><b className="mt-2 block text-xs">Сократить меню</b><small className="mt-1 block text-[10px] leading-4 text-zinc-600">Объединить повторы</small></button></div>{scope?.kind !== 'business' ? <p className="mb-3 text-xs text-zinc-600">Для изменений выберите конкретную точку.</p> : null}{error ? <InlineError text={error} /> : null}{analysis ? <section className="mb-3 rounded-[22px] bg-zinc-900 p-4 ring-1 ring-inset ring-primary/25"><b className="text-sm">{analysis.mode === 'compress' ? 'Проверим сокращение меню' : 'Подготовим улучшения'}</b><p className="mt-2 text-xs leading-5 text-zinc-400">{analysis.mode === 'compress' ? `Сейчас ${analysis.analysis?.before_count || items.length} позиций, после объединения останется около ${analysis.analysis?.after_count || items.length}. Исходные позиции будут перенесены в архив ЛокалОС.` : `ЛокалОС подготовит варианты для ${analysis.service_count || items.length} услуг. Стоимость — до ${analysis.estimated_credits || 0} кредитов.`}</p><p className="mt-2 text-[11px] text-zinc-600">На Яндекс и 2ГИС изменения не отправляются.</p><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" onClick={() => setAnalysis(null)} className="min-h-11 rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07]">Отмена</button><button type="button" disabled={Boolean(running)} onClick={() => void run(analysis.mode, true)} className="min-h-11 rounded-[14px] bg-primary text-xs font-semibold">{running ? 'Выполняем…' : 'Подтвердить'}</button></div></section> : null}{items.length ? <div className="space-y-2">{items.map((item) => <ServiceItemCard key={item.id} item={item} editing={editing === item.id} busy={busy === item.id || running === item.id} setEditing={() => setEditing(editing === item.id ? '' : item.id || '')} update={async (values) => { await update(item, values); setEditing(''); }} changeActive={() => void changeActiveState(item)} />)}</div> : <Empty icon={LayoutGrid} title="Услуги не добавлены" text="Добавьте первую услугу, чтобы ЛокалОС мог проверить название, описание и цену." />}<ActionPreviewSheet preview={itemPreview} busy={Boolean(running)} confirmLabel={itemPreview?.capability === 'services.restore' ? 'Вернуть услугу' : 'Убрать в архив'} onCancel={() => setItemPreview(null)} onConfirm={() => void confirmActiveState()} /></div>;
};

const ServiceItemCard = ({ item, editing, busy, setEditing, update, changeActive }: { item: ModuleItem; editing: boolean; busy: boolean; setEditing: () => void; update: (values: { name: string; description: string; price: string; category: string }) => Promise<void>; changeActive: () => void }) => {
  const [name, setName] = useState(item.title || '');
  const [description, setDescription] = useState(item.subtitle || '');
  const [price, setPrice] = useState(item.price || '');
  const [category, setCategory] = useState(item.category || '');
  return <article id={`service-item-${item.id || ''}`} className={`scroll-mt-24 rounded-[22px] p-4 ring-1 ring-inset ${item.status === 'archived' ? 'bg-white/[0.02] opacity-70 ring-white/[0.05]' : 'bg-white/[0.04] ring-white/[0.07]'}`}><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><b className="block text-sm leading-5">{item.title}</b><small className="mt-1 block truncate text-zinc-600">{[item.business_name, item.category].filter(Boolean).join(' · ')}</small><small className="mt-1 block text-[10px] text-zinc-700">{item.source ? `Получено из ${providerName(item.source)}` : 'Добавлено в ЛокалОС'} · {item.updated_at ? `обновлено ${dateLabel(item.updated_at)}` : 'ещё не обновлялось'}</small></div><StatusPill value={item.status} /></div>{editing ? <div className="mt-4 space-y-2"><input value={name} onChange={(event) => setName(event.target.value)} aria-label="Название услуги" className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><div className="grid grid-cols-2 gap-2"><input value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Категория услуги" placeholder="Категория" className="min-h-11 min-w-0 rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07]" /><input value={price} onChange={(event) => setPrice(event.target.value)} aria-label="Цена услуги" placeholder="Цена" className="min-h-11 min-w-0 rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07]" /></div><textarea value={description} onChange={(event) => setDescription(event.target.value)} aria-label="Описание услуги" rows={4} className="w-full rounded-[14px] bg-black/20 p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><button type="button" disabled={busy} onClick={() => void update({ name, description, price, category })} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-primary text-xs font-semibold active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}Сохранить изменения</button></div> : <><p className="mt-3 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-zinc-400">{item.subtitle}</p><div className="mt-3 flex items-center justify-between"><b className="text-sm tabular-nums text-zinc-200">{item.price || 'Цена не указана'}</b><div className="flex gap-1"><button type="button" disabled={busy} onClick={changeActive} className="min-h-11 rounded-[14px] px-3 text-xs font-semibold text-zinc-500 transition-transform active:scale-[0.96] disabled:opacity-50">{item.status === 'archived' ? 'Вернуть' : 'В архив'}</button>{item.status !== 'archived' ? <button type="button" onClick={setEditing} className="flex min-h-11 items-center gap-2 rounded-[14px] bg-white/[0.055] px-3 text-xs font-semibold ring-1 ring-inset ring-white/[0.08] active:scale-[0.96]"><Pencil className="h-4 w-4" />Изменить</button> : null}</div></div></>}</article>;
};

const ModuleUnavailable = () => <Empty icon={CircleEllipsis} title="Раздел пока недоступен" text="ЛокалОС скрыл незавершённый сценарий, чтобы не показывать пустые кнопки и фиктивные данные." />;

const NotificationSettings = ({ preferences, saving, save }: { preferences: NotificationPreferences; saving: boolean; save: (preferences: NotificationPreferences) => Promise<void> }) => {
  const [value, setValue] = useState<NotificationPreferences>(preferences);
  useEffect(() => setValue(preferences), [preferences]);
  const rows: Array<[keyof NotificationPreferences, string, string]> = [['daily_digest', 'Утренняя сводка', 'Задачи и изменения за сутки'], ['content_publications', 'Публикации', 'Готовые тексты для ручного размещения'], ['finance_rhythm', 'Ритм статистики', 'Один раз перед сроком и один — после'], ['reviews', 'Новые отзывы', 'Когда нужен ответ'], ['tasks', 'Решения', 'Черновики и подтверждения'], ['errors', 'Ошибки', 'Точка или подключение требует внимания'], ['agent_results', 'Результаты ЛокалОС', 'Новый результат готов к проверке']];
  return <div><div className="space-y-2">{rows.map(([key, title, description]) => <label key={key} className="flex min-h-16 items-center gap-3 rounded-[20px] bg-white/[0.04] px-4 ring-1 ring-inset ring-white/[0.07]"><span className="min-w-0 flex-1"><b className="block text-sm">{title}</b><small className="mt-1 block text-zinc-600">{description}</small></span><input type="checkbox" checked={Boolean(value[key])} onChange={(event) => setValue((current) => ({ ...current, [key]: event.target.checked }))} className="h-6 w-6 accent-primary" /></label>)}</div><button disabled={saving} onClick={() => void save(value)} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold active:scale-[0.96] disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}{saving ? 'Сохраняем…' : 'Сохранить'}</button></div>;
};

const locationCountLabel = (count: number) => {
  const remainder100 = count % 100;
  const remainder10 = count % 10;
  if (remainder100 >= 11 && remainder100 <= 14) return `${count} точек`;
  if (remainder10 === 1) return `${count} точка`;
  if (remainder10 >= 2 && remainder10 <= 4) return `${count} точки`;
  return `${count} точек`;
};

export const NetworkScopePicker = ({ network, currentScope, locations, total, nextCursor, search, setSearch, loading, choose, back, loadMore }: { network: NetworkCatalogItem; currentScope?: MobileScope; locations: BusinessCatalogItem[]; total: number; nextCursor?: string | null; search: string; setSearch: (value: string) => void; loading: boolean; choose: (kind: string, id?: string | null) => void; back: () => void; loadMore: () => void }) => {
  const currentIsNetwork = currentScope?.kind === 'network' && currentScope.id === network.id;
  const currentIsNetworkLocation = currentScope?.kind === 'business' && currentScope.parent_scope?.id === network.id;
  const displayedTotal = search.trim() ? total : total || network.locations_count || locations.length;
  return <Screen
    title={network.name || 'Сеть'}
    subtitle="Работайте со всей сетью или выберите одну точку."
    action={<button type="button" onClick={back} aria-label="Все бизнесы" className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-white/[0.05] text-zinc-400 shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-[background-color,transform] active:scale-[0.96]"><ArrowLeft className="h-5 w-5" /></button>}
  >
    <button type="button" onClick={() => void choose('network', network.id)} className={`flex min-h-[76px] w-full items-center gap-3 rounded-[22px] px-4 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-[background-color,transform] active:scale-[0.96] ${currentIsNetwork ? 'bg-primary/12' : 'bg-white/[0.045]'}`}>
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-primary/15 text-primary"><Network className="h-5 w-5" /></span>
      <span className="min-w-0 flex-1"><b className="block text-sm">{currentIsNetworkLocation ? 'К сводке сети' : 'Сводка сети'}</b><small className="mt-1 block text-pretty text-zinc-500">{locationCountLabel(displayedTotal)} в общей картине</small></span>
      {currentIsNetwork ? <Check className="h-5 w-5 text-primary" /> : <ChevronRight className="h-5 w-5 text-zinc-600" />}
    </button>
    <div className="mb-3 mt-6 flex items-end justify-between gap-3"><div><h2 className="text-balance text-lg font-semibold">Точки сети</h2><p className="mt-1 text-xs text-zinc-600">Данные и действия будут относиться только к выбранной точке.</p></div><span className="shrink-0 text-xs tabular-nums text-zinc-600">{displayedTotal}</span></div>
    <label className="relative block"><Search className="absolute left-4 top-4 h-4 w-4 text-zinc-600" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название или адрес точки" className="min-h-12 w-full rounded-2xl bg-white/[0.05] pl-11 pr-4 text-sm outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label>
    <div className="mt-3 space-y-2">
      {locations.map((item) => <ScopeRow key={item.id} icon={Building2} label={item.name || 'Точка'} meta={item.address || 'Адрес пока не указан'} selected={currentScope?.kind === 'business' && currentScope.id === item.id} onClick={() => void choose('business', item.id)} />)}
      {loading ? <div className="space-y-2" aria-label="Загружаем точки"><div className="h-16 animate-pulse rounded-[20px] bg-white/[0.04] motion-reduce:animate-none" /><div className="h-16 animate-pulse rounded-[20px] bg-white/[0.04] motion-reduce:animate-none" /></div> : null}
      {!loading && !locations.length ? <Empty icon={MapPinned} title="Точки не найдены" text={search ? 'Попробуйте другое название или адрес.' : 'В этой сети пока нет доступных точек.'} /> : null}
      {nextCursor ? <button type="button" onClick={loadMore} className="min-h-12 w-full rounded-2xl bg-white/[0.05] text-sm font-semibold text-zinc-300 shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-transform active:scale-[0.96]">Показать ещё</button> : null}
    </div>
  </Screen>;
};

const ScopePicker = ({ catalog, search, setSearch, choose, openNetwork, loadMore }: { catalog?: Catalog; search: string; setSearch: (value: string) => void; choose: (kind: string, id?: string | null) => void; openNetwork: (network: NetworkCatalogItem) => void; loadMore: () => void }) => <Screen title="Где работаем?" subtitle="Выбор сохранится для следующего запуска."><label className="relative block"><Search className="absolute left-4 top-4 h-4 w-4 text-zinc-600" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название, город или адрес" className="min-h-12 w-full rounded-2xl bg-white/[0.05] pl-11 pr-4 text-sm outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label><div className="mt-4 space-y-2">{catalog?.platform ? <ScopeRow icon={ShieldCheck} label="Вся платформа" meta="Операционная картина ЛокалОС" onClick={() => void choose('platform')} /> : null}{catalog?.networks?.map((item) => <ScopeRow key={item.id} icon={Network} label={item.name || 'Сеть'} meta={`${locationCountLabel(item.locations_count || 0)} · Выбрать`} onClick={() => openNetwork(item)} />)}{catalog?.businesses?.filter((item) => Boolean(search.trim()) || !item.network_id).map((item) => <ScopeRow key={item.id} icon={Building2} label={item.name || 'Бизнес'} meta={[item.network_name, item.address].filter(Boolean).join(' · ') || 'Самостоятельный бизнес'} onClick={() => void choose('business', item.id)} />)}{catalog?.has_more_businesses ? <button type="button" onClick={loadMore} className="min-h-12 w-full rounded-2xl bg-white/[0.05] text-sm font-semibold text-zinc-300 shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-transform active:scale-[0.96]">Показать ещё</button> : null}</div></Screen>;

const BottomNav = ({ current, setCurrent }: { current: Tab; setCurrent: (tab: Tab) => void }) => {
  const activeKey: Tab = current === 'reviews' ? 'more' : current === 'operator' ? 'menu' : current === 'tasks' ? 'today' : current;
  const items: Array<[Tab, string, typeof Sparkles]> = [['today', 'Сегодня', Sparkles], ['more', 'Пути', LayoutGrid], ['feed', 'Лента', Radio], ['progress', 'Результаты', TrendingUp], ['menu', 'Ещё', CircleEllipsis]];
  return <nav aria-label="Главное меню" className="fixed inset-x-0 bottom-0 z-20 mx-auto max-w-xl border-t border-white/[0.07] bg-zinc-950/90 px-2 pb-[calc(8px+env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl"><div className="grid grid-flow-col auto-cols-fr">{items.map(([key, label, Icon]) => <button key={key} type="button" aria-current={activeKey === key ? 'page' : undefined} onClick={() => setCurrent(key)} className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-[16px] text-[10px] transition-[color,transform,background-color] duration-150 active:scale-[0.96] ${activeKey === key ? 'bg-primary/10 text-primary' : 'text-zinc-600'}`}><Icon className="h-5 w-5" /><span>{label}</span></button>)}</div></nav>;
};
const PrimaryButton = ({ children, onClick }: { children: React.ReactNode; onClick: () => void }) => <button onClick={onClick} className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96]">{children}<ChevronRight className="h-4 w-4" /></button>;
const TaskRow = ({ item, onClick }: { item: AttentionItem; onClick: () => void }) => <button onClick={onClick} className="mt-2 flex min-h-16 w-full items-center gap-3 rounded-[20px] bg-white/[0.035] px-4 py-3 text-left ring-1 ring-inset ring-white/[0.06] active:scale-[0.98]"><span className={`h-2.5 w-2.5 rounded-full ${item.severity === 'high' ? 'bg-rose-400' : item.severity === 'medium' ? 'bg-amber-400' : 'bg-emerald-400'}`} /><span className="min-w-0 flex-1"><b className="block truncate text-sm">{item.title || 'Задача'}</b><small className="mt-1 block truncate text-zinc-600">{item.description}</small>{item.progress !== undefined && item.progress !== null ? <span className="mt-2 block h-1 overflow-hidden rounded-full bg-white/[0.06]"><i className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(item.progress, 100))}%` }} /></span> : item.action_unavailable_reason ? <small className="mt-1 block truncate text-amber-300/70">{item.action_unavailable_reason}</small> : null}</span>{item.count ? <b className="tabular-nums text-zinc-400">{item.count}</b> : null}<ChevronRight className="h-4 w-4 text-zinc-700" /></button>;
const ScopeRow = ({ icon: Icon, label, meta, selected = false, onClick }: { icon: typeof Star; label: string; meta: string; selected?: boolean; onClick: () => void }) => <button onClick={onClick} className={`flex min-h-16 w-full items-center gap-3 rounded-[20px] px-3 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-[background-color,transform] active:scale-[0.96] ${selected ? 'bg-primary/12' : 'bg-white/[0.04]'}`}><span className="grid h-10 w-10 place-items-center rounded-[14px] bg-primary/12 text-primary"><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-sm">{label}</b><small className="block truncate text-zinc-600">{meta}</small></span>{selected ? <Check className="h-4 w-4 text-primary" /> : <ChevronRight className="h-4 w-4 text-zinc-700" />}</button>;
const LoadingScreen = ({ slow }: { slow: boolean }) => <main className="grid min-h-[100dvh] place-items-center bg-zinc-950 px-8 text-center text-white"><div><span className="relative mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-zinc-900 ring-1 ring-inset ring-white/[0.08]"><Sparkles className="h-7 w-7 text-primary" /></span><h1 className="mt-6 text-xl font-semibold tracking-[-0.03em]">Собираем ваш рабочий день</h1>{slow ? <p className="mt-3 text-sm text-zinc-500">Сверяем задачи и источники…</p> : null}</div></main>;
const TelegramGate = () => <main className="grid min-h-[100dvh] place-items-center bg-zinc-950 p-6 text-center text-white"><div className="max-w-sm"><span className="mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-primary/12 text-primary ring-1 ring-inset ring-primary/20"><Send className="h-7 w-7" /></span><h1 className="mt-6 text-balance text-2xl font-semibold tracking-[-0.04em]">Откройте ЛокалОС в Telegram</h1><p className="mt-3 text-pretty text-sm leading-6 text-zinc-500">Вернитесь в чат с ЛокалОС и нажмите постоянную кнопку приложения внизу экрана.</p><a href="https://t.me/LocalOspro_bot" className="mt-6 flex min-h-12 items-center justify-center rounded-2xl bg-primary px-5 text-sm font-semibold text-white active:scale-[0.96]">Открыть бота</a></div></main>;

export default TelegramControlWorkspace;
