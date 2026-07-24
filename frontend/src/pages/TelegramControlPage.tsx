import { FormEvent, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertCircle, ArrowLeft, Bot, Building2, CalendarDays, Camera, Check, ChevronRight, CircleEllipsis,
  ClipboardCheck, Copy, CreditCard, FileText, LayoutGrid, Loader2, MapPinned,
  MessageCircle, Network, PackageCheck, Pencil, RefreshCw, Search, Send, Settings, ShieldCheck,
  Sparkles, Star, Trash2, Upload, Users, WandSparkles,
} from 'lucide-react';
import localOsLogo from '@/assets/images/logo.png';

type Scope = {
  kind: 'platform' | 'network' | 'business';
  id?: string | null;
  name?: string;
  business_ids?: string[];
  can_switch?: boolean;
};

type AttentionItem = {
  id?: string;
  title?: string;
  description?: string;
  count?: number;
  status?: string;
  severity?: string;
  progress?: number | null;
  action_unavailable_reason?: string;
  target_scope?: { id?: string };
};

type Metric = {
  key?: string;
  label?: string;
  value?: string | number | null;
  source?: string;
  source_label?: string;
  updated_at?: string;
};

type Summary = {
  scope?: Scope;
  attention_items?: AttentionItem[];
  metrics?: Metric[];
  data_warnings?: string[];
};

type Catalog = {
  platform?: Scope | null;
  networks?: Array<{ id?: string; name?: string; locations_count?: number }>;
  businesses?: Array<{ id?: string; name?: string; address?: string; network_name?: string }>;
  total_choices?: number;
};

type Bootstrap = {
  success?: boolean;
  error?: string;
  selected_scope?: Scope;
  summary?: Summary;
  catalog?: Catalog;
  web_session_token?: string;
  navigation?: NavigationItem[];
};

type NavigationItem = { key: string; label: string; group: 'primary' | 'more'; status: 'available' | 'read_only' | 'hidden' };

type Workspace = {
  items?: AttentionItem[];
  counts?: { attention?: number; total?: number };
  summary?: Summary;
  data_warnings?: string[];
};

type Review = {
  id: string;
  business_id?: string;
  location_name?: string;
  source?: string;
  rating?: number;
  author_name?: string;
  text?: string;
  response_text?: string;
  published_at?: string;
  loaded_at?: string;
  updated_at?: string;
  reply_draft_id?: string;
  reply_draft_text?: string;
  reply_draft_status?: string;
};

type ReviewResult = {
  items?: Review[];
  counts?: { total?: number; unanswered?: number; drafts?: number };
  cursor?: string | null;
  filters?: { sources?: string[]; ratings?: number[]; locations?: Array<{ id: string; name: string }> };
};

type OperatorMessage = { id?: string; role: 'user' | 'operator'; text: string; status?: string; capability?: string; created_at?: string; screen?: string };
type ActionPreview = { action_id: string; estimated_credits?: number; is_mass_action?: boolean; external_effects?: boolean; target_businesses?: Array<{ id: string; name: string }>; objects?: Array<{ id?: string; author_name?: string; business_name?: string }> };
type ModuleItem = { id?: string; business_id?: string; kind?: string; title?: string; subtitle?: string; business_name?: string; status?: string; rating?: number; reviews_count?: number; seo_score?: number; price?: string; category?: string; source?: string; updated_at?: string; amount?: string | number; transaction_type?: string; selected_channel?: string; run_id?: string; run_status?: string; error_text?: string; provider_sources?: string[]; parse_status?: string; parse_source?: string; parse_updated_at?: string; refresh_cost_credits?: number; scheduled_refresh_cost_credits?: number; review_sync_enabled?: boolean; review_sync_interval_hours?: number; review_sync_schedule_mode?: string; review_sync_schedule_days?: number[]; review_sync_schedule_time?: string; review_sync_next_run_at?: string; review_sync_last_run_at?: string; review_sync_last_status?: string; plan_id?: string; plan_title?: string; plan_period_days?: number; scheduled_for?: string; content_type?: string; draft_text?: string };
type NotificationPreferences = { daily_digest?: boolean; reviews?: boolean; tasks?: boolean; errors?: boolean; agent_results?: boolean };
type ModuleData = { items?: ModuleItem[]; counts?: { total?: number }; as_of?: string; data_warnings?: string[]; status?: string; preferences?: NotificationPreferences; filters?: { period_days?: number[]; density?: string[] } };
type Tab = 'today' | 'tasks' | 'reviews' | 'operator' | 'more';

type TelegramWebApp = {
  initData?: string;
  ready?: () => void;
  expand?: () => void;
  openTelegramLink?: (url: string) => void;
  BackButton?: { show: () => void; hide: () => void; onClick: (callback: () => void) => void; offClick: (callback: () => void) => void };
};

declare global {
  interface Window { Telegram?: { WebApp?: TelegramWebApp } }
}

const previewBootstrap: Bootstrap = {
  success: true,
  selected_scope: { kind: 'business', id: 'preview', name: 'Весёлая расчёска', business_ids: ['preview'], can_switch: true },
  summary: {
    attention_items: [
      { id: 'reviews_unanswered', title: '50 отзывов ждут ответа', description: 'LocalOS собрал их в одну очередь.', count: 50, severity: 'high' },
      { id: 'drafts', title: '12 черновиков готовы', description: 'Нужно проверить тон и подтвердить.', count: 12, severity: 'medium' },
    ],
    metrics: [
      { key: 'map', label: 'На карте', value: 296, source_label: 'Яндекс Карты', updated_at: new Date().toISOString() },
      { key: 'loaded', label: 'В LocalOS', value: 164, source_label: 'Отзывы LocalOS', updated_at: new Date().toISOString() },
    ],
  },
  catalog: {
    platform: { kind: 'platform', name: 'Вся платформа' },
    networks: [{ id: 'network', name: 'Сеть «Весёлая расчёска»', locations_count: 2 }],
    businesses: [{ id: 'preview', name: 'Весёлая расчёска', address: 'Москва, Тверская, 7' }], total_choices: 3,
  },
  navigation: [
    { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
    { key: 'tasks', label: 'Задачи', group: 'primary', status: 'available' },
    { key: 'reviews', label: 'Отзывы', group: 'primary', status: 'available' },
    { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' },
    { key: 'cards', label: 'Карточки', group: 'more', status: 'read_only' },
    { key: 'content', label: 'Контент', group: 'more', status: 'available' },
    { key: 'services', label: 'Услуги', group: 'more', status: 'available' },
    { key: 'finance', label: 'Финансы', group: 'more', status: 'available' },
  ],
};

const previewReviews: Review[] = [
  { id: '1', business_id: 'preview', location_name: 'Весёлая расчёска', source: 'Яндекс', rating: 5, author_name: 'Анна К.', text: 'Очень понравилась стрижка и отношение мастера. Обязательно вернусь!', published_at: new Date().toISOString() },
  { id: '2', business_id: 'preview', location_name: 'Весёлая расчёска', source: '2ГИС', rating: 3, author_name: 'Игорь', text: 'Пришлось ждать почти 20 минут, но результат хороший.', published_at: new Date().toISOString(), reply_draft_text: 'Игорь, спасибо, что поделились. Извините за ожидание.', reply_draft_id: 'd2' },
];

const previewModules: Record<string, ModuleData> = {
  cards: { items: [{ id: 'preview', title: 'Весёлая расчёска', subtitle: 'Москва, Тверская, 7', status: 'fresh', provider_sources: ['yandex', '2gis'], rating: 4.8, reviews_count: 296, seo_score: 82, parse_updated_at: new Date().toISOString() }] },
  content: { items: [{ id: 'content-1', plan_id: 'plan-preview', title: 'Как выбрать уход после окрашивания', subtitle: 'Черновик ещё не подготовлен', business_name: 'Весёлая расчёска', status: 'planned', plan_title: 'Контент-план · август', scheduled_for: '2026-08-02', content_type: 'news', draft_text: '' }, { id: 'content-2', plan_id: 'plan-preview', title: 'Летнее восстановление волос', subtitle: 'После солнца волосам особенно нужен бережный уход. Подготовили несколько рекомендаций от мастеров.', business_name: 'Весёлая расчёска', status: 'draft_generated', plan_title: 'Контент-план · август', scheduled_for: '2026-08-05', content_type: 'news', draft_text: 'После солнца волосам особенно нужен бережный уход. Подготовили несколько рекомендаций от мастеров.' }] },
  services: { items: [{ id: 'service-1', title: 'Женская стрижка', subtitle: 'Стрижка с консультацией мастера и укладкой.', business_name: 'Весёлая расчёска', status: 'active', price: 'от 2 900 ₽', category: 'Стрижки' }] },
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };
const webApp = () => window.Telegram?.WebApp;
const isPreview = () => ['localhost', '127.0.0.1'].includes(window.location.hostname) && new URLSearchParams(window.location.search).get('preview') === '1';

const readJson = async <T,>(response: Response): Promise<T> => {
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error('Сервис временно вернул некорректный ответ. Попробуйте ещё раз.');
  }
  if (!response.ok || payload?.success === false) throw new Error(payload?.error || 'Не удалось выполнить запрос.');
  return payload;
};

const scopeQuery = (scope?: Scope) => {
  const params = new URLSearchParams();
  if (scope?.kind) params.set('scope_type', scope.kind);
  if (scope?.id) params.set('scope_id', scope.id);
  return params;
};

const authHeaders = () => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${window.sessionStorage.getItem('localos_mini_session') || ''}` });
const authOnlyHeaders = () => ({ Authorization: `Bearer ${window.sessionStorage.getItem('localos_mini_session') || ''}` });
const isTab = (value: string | null): value is Tab => Boolean(value && ['today', 'tasks', 'reviews', 'operator', 'more'].includes(value));

export const TelegramControlPage = () => {
  const preview = isPreview();
  const initData = webApp()?.initData || '';
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(preview ? previewBootstrap : null);
  const [workspace, setWorkspace] = useState<Workspace | null>(preview ? { items: previewBootstrap.summary?.attention_items, summary: previewBootstrap.summary } : null);
  const [tab, setTab] = useState<Tab>('today');
  const [module, setModule] = useState('');
  const [loading, setLoading] = useState(!preview);
  const [slowLoading, setSlowLoading] = useState(false);
  const [error, setError] = useState('');
  const [picker, setPicker] = useState(false);
  const [search, setSearch] = useState('');
  const [taskFilter, setTaskFilter] = useState('attention');
  const [reviewStatus, setReviewStatus] = useState('unanswered');
  const [reviewSource, setReviewSource] = useState('');
  const [reviewRating, setReviewRating] = useState('');
  const [reviewLocation, setReviewLocation] = useState('');
  const [deepLinkReviewId] = useState(() => new URLSearchParams(window.location.search).get('item_type') === 'review' ? new URLSearchParams(window.location.search).get('item_id') || '' : '');
  const [selectedReviews, setSelectedReviews] = useState<string[]>([]);
  const [actionPreview, setActionPreview] = useState<ActionPreview | null>(null);
  const [reviews, setReviews] = useState<ReviewResult>(preview ? { items: previewReviews, counts: { total: 164, unanswered: 50, drafts: 12 } } : {});
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [command, setCommand] = useState('');
  const [operatorBusy, setOperatorBusy] = useState(false);
  const [reviewActionBusy, setReviewActionBusy] = useState('');
  const [messages, setMessages] = useState<OperatorMessage[]>([]);
  const [historyLoadedFor, setHistoryLoadedFor] = useState('');
  const [moduleData, setModuleData] = useState<ModuleData>({});
  const [moduleLoading, setModuleLoading] = useState(false);
  const [moduleSaving, setModuleSaving] = useState(false);
  const [moduleActionBusy, setModuleActionBusy] = useState('');

  const scope = bootstrap?.selected_scope || bootstrap?.summary?.scope;
  const summary = workspace?.summary || bootstrap?.summary;
  const tasks = workspace?.items?.length ? workspace.items : summary?.attention_items || [];
  const catalog = bootstrap?.catalog;
  const hasSwitcher = Boolean(scope?.can_switch || Number(catalog?.total_choices || 0) > 1);
  const moreNavigation = (bootstrap?.navigation || []).filter((item) => item.group === 'more' && item.status !== 'hidden');
  const showMore = moreNavigation.length > 0;

  const loadWorkspace = async (nextScope?: Scope) => {
    if (preview) return;
    const params = scopeQuery(nextScope || scope);
    const result = await fetch(`/api/operator/mobile/workspace?${params.toString()}`, { headers: authHeaders() }).then(readJson<Workspace>);
    setWorkspace(result);
  };

  const loadBootstrap = async (query = '') => {
    if (preview) return;
    if (!initData) { setLoading(false); return; }
    const timer = window.setTimeout(() => setSlowLoading(true), 400);
    try {
      const result = await fetch('/api/operator/telegram/bootstrap', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: initData, q: query, scope_type: new URLSearchParams(window.location.search).get('scope_type'), scope_id: new URLSearchParams(window.location.search).get('scope_id') }),
      }).then(readJson<Bootstrap>);
      if (result.web_session_token) window.sessionStorage.setItem('localos_mini_session', result.web_session_token);
      setBootstrap(result);
      if (!query) await loadWorkspace(result.selected_scope);
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось открыть LocalOS.');
    } finally {
      window.clearTimeout(timer); setSlowLoading(false); setLoading(false);
    }
  };

  useEffect(() => { webApp()?.ready?.(); webApp()?.expand?.(); void loadBootstrap(); }, []);
  useEffect(() => {
    if (!picker || !initData) return;
    const timer = window.setTimeout(() => void loadBootstrap(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [picker, search]);

  useEffect(() => {
    const back = webApp()?.BackButton;
    if (!back) return;
    const goBack = () => { if (module) setModule(''); else if (picker) setPicker(false); else setTab('today'); };
    if (module || picker || tab !== 'today') { back.show(); back.onClick(goBack); } else back.hide();
    return () => back.offClick(goBack);
  }, [module, picker, tab]);

  const chooseScope = async (kind: string, id?: string | null) => {
    if (preview) { setPicker(false); return; }
    setLoading(true);
    try {
      const result = await fetch('/api/operator/telegram/scope', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: initData, scope_type: kind, scope_id: id || null }),
      }).then(readJson<Bootstrap>);
      setBootstrap((current) => ({ ...current, ...result, catalog: current?.catalog }));
      await loadWorkspace(result.selected_scope);
      setPicker(false); setTab('today'); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сменить бизнес.'); }
    finally { setLoading(false); }
  };

  const loadReviews = async (status = reviewStatus, append = false) => {
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
      setReviews((current) => ({ ...result, items: append ? [...(current.items || []), ...(result.items || [])] : result.items }));
      setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить отзывы.'); }
    finally { setReviewsLoading(false); }
  };

  useEffect(() => { if (tab === 'reviews') void loadReviews(reviewStatus); }, [tab, reviewStatus, reviewSource, reviewRating, reviewLocation, scope?.kind, scope?.id]);

  const loadOperatorHistory = async () => {
    if (preview || scope?.kind !== 'business' || !scope.id) return;
    const scopeKey = `${scope.kind}:${scope.id}`;
    if (historyLoadedFor === scopeKey) return;
    try {
      const params = scopeQuery(scope);
      const result = await fetch(`/api/operator/mobile/operator/history?${params.toString()}`, { headers: authHeaders() }).then(readJson<{ items?: Array<{ id?: string; role?: string; content?: string; status?: string; capability?: string; created_at?: string; result_json?: { mobile_route?: { screen?: string } } }> }>);
      setMessages((result.items || []).map((item) => ({ id: item.id, role: item.role === 'user' ? 'user' : 'operator', text: item.content || '', status: item.status, capability: item.capability, created_at: item.created_at, screen: item.result_json?.mobile_route?.screen })));
      setHistoryLoadedFor(scopeKey);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить историю.'); }
  };

  useEffect(() => { if (tab === 'operator') void loadOperatorHistory(); }, [tab, scope?.kind, scope?.id]);

  const loadModule = async (moduleKey = module) => {
    if (!moduleKey || preview) return;
    setModuleLoading(true);
    const params = scopeQuery(scope);
    await fetch(`/api/operator/mobile/modules/${moduleKey}?${params.toString()}`, { headers: authHeaders() })
      .then(readJson<ModuleData>)
      .then((result) => { setModuleData(result); setError(''); })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить раздел.'))
      .finally(() => setModuleLoading(false));
  };

  useEffect(() => {
    if (!module) return;
    if (preview) { setModuleData(previewModules[module] || {}); return; }
    void loadModule(module);
  }, [module, scope?.kind, scope?.id]);

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
      await loadModule('content'); setError('');
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
      await loadModule('content'); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить контент.'); }
    finally { setModuleActionBusy(''); }
  };

  useEffect(() => {
    if (!bootstrap) return;
    const params = new URLSearchParams(window.location.search);
    const requested = params.get('screen');
    const allowed = new Set((bootstrap.navigation || []).filter((item) => item.status !== 'hidden').map((item) => item.key));
    if (isTab(requested) && allowed.has(requested)) setTab(requested);
    if (requested && allowed.has(requested) && !isTab(requested)) { setTab('more'); setModule(requested); }
    if (requested === 'reviews') {
      const status = params.get('status');
      const rating = params.get('rating');
      if (status && ['unanswered', 'drafts', 'answered', 'all'].includes(status)) setReviewStatus(status);
      if (rating && ['1', '2', '3', '4', '5'].includes(rating)) setReviewRating(rating);
    }
  }, [bootstrap?.selected_scope?.kind, bootstrap?.selected_scope?.id]);

  const openTask = (item: AttentionItem) => {
    if (item.target_scope?.id) { void chooseScope('business', item.target_scope.id); return; }
    if (String(item.id || '').includes('review')) setTab('reviews'); else setTab('tasks');
  };

  const askOperator = async (event: FormEvent) => {
    event.preventDefault();
    const text = command.trim();
    if (!text) return;
    if (scope?.kind !== 'business' || !scope.id) { setPicker(true); setError('Для команды выберите одну точку.'); return; }
    setMessages((current) => [...current, { role: 'user', text }]); setCommand(''); setOperatorBusy(true); setTab('operator');
    try {
      const result = await fetch('/api/operator/chat', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ business_id: scope.id, message: text, channel: 'telegram_mini_app' }),
      }).then(readJson<{ operator_result?: { chat_response?: string; summary?: string; status?: string; capability?: string; mobile_route?: { screen?: string } } }>);
      setMessages((current) => [...current, { role: 'operator', text: result.operator_result?.chat_response || result.operator_result?.summary || 'Готово. Результат добавлен в задачи.', status: result.operator_result?.status, capability: result.operator_result?.capability, screen: result.operator_result?.mobile_route?.screen }]);
      await loadWorkspace();
    } catch (requestError) { setMessages((current) => [...current, { role: 'operator', text: requestError instanceof Error ? requestError.message : 'Не смог разобрать запрос.' }]); }
    finally { setOperatorBusy(false); }
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
      }).then(readJson<{ preview?: ActionPreview }>);
      setActionPreview(result.preview || null); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось собрать preview.'); }
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
    <main className="min-h-[100dvh] bg-zinc-950 text-zinc-100 antialiased selection:bg-primary/30">
      <div className="pointer-events-none fixed inset-x-0 top-0 h-72 bg-[radial-gradient(circle_at_top,rgba(255,92,51,0.16),transparent_68%)]" />
      <div className="relative mx-auto min-h-[100dvh] max-w-xl pb-[calc(92px+env(safe-area-inset-bottom))]">
        <TopBar scope={scope} hasSwitcher={hasSwitcher} onSwitch={() => setPicker(true)} />
        {error ? <div className="mx-4 mb-4 flex gap-3 rounded-2xl bg-rose-500/10 p-4 text-sm text-rose-100 ring-1 ring-inset ring-rose-400/20"><AlertCircle className="h-5 w-5 shrink-0" />{error}</div> : null}
        <AnimatePresence initial={false} mode="wait">
          <motion.div key={`${tab}-${module}-${picker}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring}>
            {picker ? <ScopePicker catalog={catalog} search={search} setSearch={setSearch} choose={chooseScope} /> : null}
            {!picker && tab === 'today' ? <Today summary={summary} tasks={tasks} command={command} setCommand={setCommand} ask={askOperator} openTask={openTask} /> : null}
            {!picker && tab === 'tasks' ? <Tasks items={tasks} filter={taskFilter} setFilter={setTaskFilter} openTask={openTask} /> : null}
            {!picker && tab === 'reviews' ? <Reviews result={reviews} summary={summary} status={reviewStatus} setStatus={setReviewStatus} source={reviewSource} setSource={setReviewSource} rating={reviewRating} setRating={setReviewRating} location={reviewLocation} setLocation={setReviewLocation} selected={selectedReviews} setSelected={setSelectedReviews} loading={reviewsLoading} actionBusy={reviewActionBusy} generate={generateReviewReply} updateDraft={updateReviewDraft} markPublished={markReviewPublished} prepareSelected={() => void prepareSelectedReviews(selectedReviews)} loadMore={() => void loadReviews(reviewStatus, true)} /> : null}
            {!picker && tab === 'operator' ? <Operator messages={messages} busy={operatorBusy} command={command} setCommand={setCommand} ask={askOperator} openScreen={(screen) => { if (isTab(screen) && screen !== 'more') setTab(screen); }} /> : null}
            {!picker && tab === 'more' && !module ? <More navigation={moreNavigation} onOpen={setModule} /> : null}
            {!picker && tab === 'more' && module ? <ModuleScreen module={module} scope={scope} data={moduleData} loading={moduleLoading} saving={moduleSaving} actionBusy={moduleActionBusy} saveNotifications={saveNotifications} updateService={updateService} generateContentDraft={generateContentDraft} updateContentItem={updateContentItem} reload={() => loadModule(module)} back={() => setModule('')} /> : null}
          </motion.div>
        </AnimatePresence>
        <AnimatePresence initial={false}>{actionPreview ? <ActionPreviewSheet preview={actionPreview} busy={reviewActionBusy === 'bulk'} confirm={() => void confirmSelectedReviews()} cancel={() => setActionPreview(null)} /> : null}</AnimatePresence>
        {!picker ? <BottomNav current={tab} showMore={showMore} setCurrent={(next) => { setModule(''); setTab(next); }} /> : null}
      </div>
    </main>
  );
};

const TopBar = ({ scope, hasSwitcher, onSwitch }: { scope?: Scope; hasSwitcher: boolean; onSwitch: () => void }) => {
  const Icon = scope?.kind === 'platform' ? ShieldCheck : scope?.kind === 'network' ? Network : Building2;
  const meta = scope?.kind === 'network' ? `${scope.business_ids?.length || 0} точек` : scope?.kind === 'platform' ? 'Вся платформа' : 'Ваш бизнес';
  return <header className="px-4 pb-4 pt-[calc(16px+env(safe-area-inset-top))]">
    <div className="mb-4 flex items-center justify-between"><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-zinc-500"><span className="relative h-8 w-8 overflow-hidden rounded-[11px] bg-white shadow-[0_10px_28px_rgba(255,92,51,0.24)] ring-1 ring-inset ring-white/10"><img src={localOsLogo} alt="" className="absolute -left-3 -top-2 h-14 w-14 max-w-none outline outline-1 -outline-offset-1 outline-white/10" /></span>LocalOS</div><span className="flex items-center gap-2 rounded-full bg-white/[0.05] px-3 py-2 text-[11px] text-zinc-400 ring-1 ring-inset ring-white/[0.07]"><i className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Работает</span></div>
    <button type="button" onClick={onSwitch} disabled={!hasSwitcher} className="flex min-h-14 w-full items-center gap-3 rounded-[20px] bg-white/[0.045] px-3 text-left ring-1 ring-inset ring-white/[0.075] transition-[background-color,transform] active:scale-[0.96] disabled:active:scale-100"><span className="grid h-11 w-11 place-items-center rounded-[14px] bg-primary/15 text-primary"><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-[15px]">{scope?.name || 'LocalOS'}</b><small className="text-xs text-zinc-500">{meta}</small></span>{hasSwitcher ? <ChevronRight className="h-5 w-5 text-zinc-600" /> : null}</button>
  </header>;
};

const Today = ({ summary, tasks, command, setCommand, ask, openTask }: { summary?: Summary; tasks: AttentionItem[]; command: string; setCommand: (value: string) => void; ask: (event: FormEvent) => void; openTask: (item: AttentionItem) => void }) => {
  const primary = tasks[0];
  return <div className="px-4">
    <section className="rounded-[28px] bg-gradient-to-b from-zinc-900 to-zinc-900/70 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)] ring-1 ring-inset ring-white/[0.08]"><div className="flex items-center gap-2 text-xs text-zinc-500"><Sparkles className="h-4 w-4 text-primary" />LocalOS уже разобрался</div><div className="mt-4 flex items-start gap-4"><div className="min-w-0 flex-1"><h1 className="text-balance text-[26px] font-semibold leading-8 tracking-[-0.045em]">{primary?.title || 'Всё под контролем'}</h1><p className="mt-2 text-pretty text-sm leading-6 text-zinc-400">{primary?.description || 'Новых решений от вас сейчас не требуется.'}</p></div>{primary?.count ? <b className="rounded-2xl bg-primary/15 px-3 py-2 text-xl tabular-nums text-primary">{primary.count}</b> : <Check className="h-8 w-8 text-emerald-400" />}</div>{primary ? <PrimaryButton onClick={() => openTask(primary)}>Перейти к решению</PrimaryButton> : null}</section>
    <form onSubmit={ask} className="mt-3 rounded-[22px] bg-white/[0.04] p-3 ring-1 ring-inset ring-white/[0.07]"><label className="px-1 text-xs font-medium text-zinc-500">Что сделать?</label><div className="mt-2 flex gap-2"><input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Например: подготовь ответы" className="min-h-12 min-w-0 flex-1 rounded-2xl bg-black/20 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" /><button aria-label="Отправить" className="grid h-12 w-12 place-items-center rounded-2xl bg-primary text-white transition-transform active:scale-[0.96]"><Send className="h-4 w-4" /></button></div><p className="px-1 pt-2 text-[11px] leading-4 text-zinc-600">Опишите задачу. Внешние действия всегда попросят подтверждение.</p></form>
    {tasks.slice(1, 3).map((item) => <TaskRow key={item.id || item.title} item={item} onClick={() => openTask(item)} />)}
    <section className="mt-6"><h2 className="text-lg font-semibold tracking-[-0.025em]">Что уже сделано</h2><div className="mt-3 grid grid-cols-2 gap-2">{(summary?.metrics || []).slice(0, 4).map((metric) => <div key={metric.key} className="rounded-[20px] bg-white/[0.035] p-4 ring-1 ring-inset ring-white/[0.06]"><small className="text-zinc-600">{metric.label}</small><b className="mt-1 block text-2xl tabular-nums">{metric.value ?? '—'}</b><span className="mt-1 block truncate text-[10px] text-zinc-700">{metric.source_label || metric.source || 'LocalOS'}</span></div>)}</div></section>
  </div>;
};

const Tasks = ({ items, filter, setFilter, openTask }: { items: AttentionItem[]; filter: string; setFilter: (value: string) => void; openTask: (item: AttentionItem) => void }) => {
  const visible = items.filter((item) => filter === 'done' ? item.status === 'completed' : filter === 'working' ? item.status === 'in_progress' : item.status === 'needs_attention' || !item.status);
  return <Screen title="Задачи" subtitle="Одна очередь: решения, фоновая работа и готовые результаты."><Segments value={filter} setValue={setFilter} options={[['attention', 'Нужно решить'], ['working', 'В работе'], ['done', 'Готово']]} />{visible.length ? visible.map((item) => <TaskRow key={item.id || item.title} item={item} onClick={() => openTask(item)} />) : <Empty icon={ClipboardCheck} title="Здесь пусто" text="LocalOS покажет здесь задачи, когда появится реальная работа." />}</Screen>;
};

type ReviewsProps = {
  result: ReviewResult; summary?: Summary; status: string; setStatus: (value: string) => void;
  source: string; setSource: (value: string) => void; rating: string; setRating: (value: string) => void;
  location: string; setLocation: (value: string) => void; selected: string[]; setSelected: (value: string[]) => void;
  loading: boolean; actionBusy: string; generate: (review: Review, confirmed: boolean) => Promise<void>;
  updateDraft: (review: Review, text: string) => Promise<void>; markPublished: (review: Review) => Promise<void>;
  prepareSelected: () => void; loadMore: () => void;
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
  return <article className={`mb-3 rounded-[24px] p-4 ring-1 ring-inset transition-[background-color,box-shadow] ${selected ? 'bg-primary/[0.075] ring-primary/30' : 'bg-white/[0.04] ring-white/[0.07]'}`}><div className="flex items-start gap-3"><button type="button" aria-label={selected ? 'Убрать из выбранных' : 'Выбрать отзыв'} aria-pressed={selected} onClick={toggle} className={`grid h-11 w-11 shrink-0 place-items-center rounded-[14px] text-sm font-bold active:scale-[0.96] ${selected ? 'bg-primary text-white' : 'bg-amber-400/10 text-amber-300'}`}>{selected ? <Check className="h-5 w-5" /> : review.rating || '—'}</button><div className="min-w-0 flex-1"><b className="block truncate">{review.author_name || 'Гость'}</b><small className="block truncate text-zinc-600">{[review.source, review.location_name].filter(Boolean).join(' · ')}</small><small className="mt-1 block text-[11px] font-medium text-zinc-400">Отзыв от {review.published_at ? new Date(review.published_at).toLocaleString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'дата не указана источником'}</small></div></div><p className="mt-4 whitespace-pre-wrap text-pretty text-sm leading-6 text-zinc-300">{review.text || 'Клиент оставил оценку без текста.'}</p>{review.response_text ? <ResponseBox label="Опубликованный ответ" text={review.response_text} /> : review.reply_draft_text ? <div className="mt-4 rounded-[18px] bg-black/20 p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex min-h-11 items-center justify-between"><small className="font-semibold text-primary">Черновик LocalOS</small><div className="flex"><button type="button" onClick={() => setEditing((value) => !value)} className="min-h-11 px-3 text-xs font-semibold text-zinc-400">{editing ? 'Отмена' : 'Изменить'}</button><button type="button" aria-label="Скопировать" onClick={() => void navigator.clipboard.writeText(draftText)} className="grid h-11 w-11 place-items-center text-zinc-500 active:scale-[0.96]"><Copy className="h-4 w-4" /></button></div></div>{editing ? <><textarea value={draftText} onChange={(event) => setDraftText(event.target.value)} className="min-h-32 w-full resize-none rounded-2xl bg-white/[0.04] p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><button disabled={busy} onClick={() => void updateDraft(review, draftText)} className="mt-2 min-h-11 w-full rounded-2xl bg-primary text-sm font-semibold disabled:opacity-50">{busy ? 'Сохраняем…' : 'Сохранить черновик'}</button></> : <><p className="text-sm leading-6 text-zinc-300">{draftText}</p><button type="button" disabled={busy} onClick={() => void markPublished(review)} className="mt-3 min-h-11 w-full rounded-2xl bg-white/[0.045] text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96] disabled:opacity-50">{busy ? 'Сохраняем…' : 'Я опубликовал ответ вручную'}</button></>}</div> : <button disabled={busy} onClick={() => void generate(review, false)} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-primary/12 text-sm font-semibold text-primary ring-1 ring-inset ring-primary/20 active:scale-[0.96] disabled:opacity-50"><WandSparkles className="h-4 w-4" />{busy ? 'Проверяем…' : 'Подготовить ответ'}</button>}</article>;
};

const MetricMini = ({ label, value, accent = false }: { label: string; value?: string | number | null; accent?: boolean }) => <div className="min-w-0 px-1 py-1"><b className={`block truncate text-xl tabular-nums ${accent ? 'text-primary' : 'text-zinc-200'}`}>{value ?? '—'}</b><small className="block truncate text-[10px] text-zinc-600">{label}</small></div>;
const FilterSelect = ({ label, value, setValue, options }: { label: string; value: string; setValue: (value: string) => void; options: string[][] }) => <label className="block text-[11px] text-zinc-600"><span className="mb-1 block px-1">{label}</span><select value={value} onChange={(event) => setValue(event.target.value)} className="min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-xs text-zinc-300 outline-none ring-1 ring-inset ring-white/[0.07]"><option value="">Все</option>{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label>;

const ActionPreviewSheet = ({ preview, busy, confirm, cancel }: { preview: ActionPreview; busy: boolean; confirm: () => void; cancel: () => void }) => <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-black/65 px-3 pb-[calc(12px+env(safe-area-inset-bottom))] backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} onClick={cancel}><motion.section role="dialog" aria-modal="true" aria-labelledby="preview-title" onClick={(event) => event.stopPropagation()} className="w-full max-w-xl rounded-[28px] bg-zinc-900 p-5 text-zinc-100 shadow-[0_28px_100px_rgba(0,0,0,0.7)] ring-1 ring-inset ring-white/[0.1]" initial={{ y: 32 }} animate={{ y: 0 }} exit={{ y: 24 }} transition={spring}><div className="mx-auto mb-5 h-1 w-10 rounded-full bg-white/15" /><div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-[14px] bg-primary/12 text-primary"><ShieldCheck className="h-5 w-5" /></span><div><h2 id="preview-title" className="text-lg font-semibold tracking-[-0.025em]">Проверка перед запуском</h2><p className="mt-0.5 text-xs text-zinc-500">LocalOS ничего не выполнит без подтверждения</p></div></div><div className="mt-5 grid grid-cols-2 gap-2"><div className="rounded-[18px] bg-white/[0.04] p-3 ring-1 ring-inset ring-white/[0.06]"><small className="text-zinc-600">Отзывов</small><b className="mt-1 block text-xl tabular-nums">{preview.objects?.length || 0}</b></div><div className="rounded-[18px] bg-white/[0.04] p-3 ring-1 ring-inset ring-white/[0.06]"><small className="text-zinc-600">Стоимость</small><b className="mt-1 block text-xl tabular-nums">{preview.estimated_credits || 0} кр.</b></div></div><div className="mt-3 rounded-[18px] bg-white/[0.03] p-3 text-xs leading-5 text-zinc-400 ring-1 ring-inset ring-white/[0.06]"><b className="text-zinc-200">Будет сделано:</b> LocalOS подготовит черновики для проверки. На карты ничего не публикуется.</div>{preview.target_businesses?.length ? <p className="mt-3 text-xs text-zinc-500">Точки: {preview.target_businesses.map((item) => item.name).join(', ')}</p> : null}<div className="mt-5 flex gap-2"><button type="button" disabled={busy} onClick={cancel} className="min-h-12 flex-1 rounded-2xl bg-white/[0.05] text-sm font-semibold ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Отмена</button><button type="button" disabled={busy} onClick={confirm} className="flex min-h-12 flex-1 items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <WandSparkles className="h-4 w-4" />}{busy ? 'Готовим…' : 'Подтвердить'}</button></div></motion.section></motion.div>;

const ResponseBox = ({ label, text }: { label: string; text: string }) => <div className="mt-4 rounded-[18px] bg-black/20 p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex items-center justify-between"><small className="font-semibold text-primary">{label}</small><button type="button" aria-label="Скопировать" onClick={() => void navigator.clipboard.writeText(text)} className="grid h-11 w-11 place-items-center text-zinc-500 active:scale-[0.96]"><Copy className="h-4 w-4" /></button></div><p className="text-sm leading-6 text-zinc-300">{text}</p></div>;

const Operator = ({ messages, busy, command, setCommand, ask, openScreen }: { messages: OperatorMessage[]; busy: boolean; command: string; setCommand: (value: string) => void; ask: (event: FormEvent) => void; openScreen: (screen: string) => void }) => <Screen title="Оператор" subtitle="Опишите, какой результат нужен. LocalOS разберётся, что открыть или подготовить."><div className="min-h-[42vh] space-y-3">{messages.length ? messages.map((message, index) => <div key={message.id || `${message.role}-${index}`} className={`max-w-[88%] rounded-[20px] px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'ml-auto bg-primary text-white' : 'bg-white/[0.05] text-zinc-300 ring-1 ring-inset ring-white/[0.07]'}`}><p className="whitespace-pre-wrap">{message.text}</p>{message.role === 'operator' && message.status === 'completed' ? <small className="mt-2 block text-[10px] text-zinc-600">Готово</small> : null}{message.role === 'operator' && message.screen && ['today', 'tasks', 'reviews'].includes(message.screen) ? <button type="button" onClick={() => openScreen(message.screen || 'tasks')} className="mt-3 min-h-11 w-full rounded-[14px] bg-white/[0.05] text-xs font-semibold text-zinc-200 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Открыть результат</button> : null}</div>) : <Empty icon={Bot} title="Что поручить?" text="Например: «Подготовь ответы на плохие отзывы» или «Проверь свежесть карточки»." />}{busy ? <div className="flex items-center gap-2 text-sm text-zinc-500"><Loader2 className="h-4 w-4 animate-spin text-primary motion-reduce:animate-none" />Разбираюсь и собираю результат…</div> : null}</div><form onSubmit={ask} className="sticky bottom-24 mt-4 flex gap-2 rounded-[20px] bg-zinc-900 p-2 ring-1 ring-inset ring-white/[0.08]"><input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Напишите задачу" className="min-h-12 min-w-0 flex-1 bg-transparent px-3 text-sm outline-none placeholder:text-zinc-700" /><button aria-label="Отправить задачу" className="grid h-12 w-12 place-items-center rounded-2xl bg-primary active:scale-[0.96]"><Send className="h-4 w-4" /></button></form></Screen>;

const moduleIcons: Record<string, typeof Star> = { cards: MapPinned, content: FileText, services: LayoutGrid, finance: CreditCard, partnerships: Users, agents: Bot, settings: Settings, diagnostics: ShieldCheck };
const More = ({ navigation, onOpen }: { navigation: NavigationItem[]; onOpen: (key: string) => void }) => <Screen title="Ещё" subtitle="Только готовые рабочие разделы."><div className="grid grid-cols-2 gap-2">{navigation.map((item) => { const Icon = moduleIcons[item.key] || CircleEllipsis; return <button key={item.key} onClick={() => onOpen(item.key)} className="min-h-32 rounded-[22px] bg-white/[0.04] p-4 text-left ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] active:scale-[0.96]"><span className="grid h-10 w-10 place-items-center rounded-[14px] bg-primary/12 text-primary"><Icon className="h-5 w-5" /></span><b className="mt-4 block text-sm">{item.label}</b><small className="mt-1 block leading-4 text-zinc-600">{item.status === 'read_only' ? 'Просмотр данных' : moduleNames[item.key]?.[1]}</small></button>; })}</div></Screen>;

const moduleNames: Record<string, [string, string]> = {
  cards: ['Карточки', 'Актуальность данных и ошибки подключений.'], content: ['Контент', 'Планы, новости, посты и готовые черновики.'], services: ['Услуги', 'Список, цены и предложения по улучшению.'],
  finance: ['Финансы', 'KPI, импорты и финансовые предупреждения.'], partnerships: ['Партнёрства', 'Лиды, черновики, ответы и контроль отправок.'], agents: ['ИИ-сотрудники', 'Состояние, история и результаты фоновой работы.'], settings: ['Настройки', 'Уведомления, подключения, тариф и доступ.'], diagnostics: ['Диагностика', 'Технические очереди и ошибки — только для суперадмина.'],
};

type ModuleScreenProps = {
  module: string; scope?: Scope; data: ModuleData; loading: boolean; saving: boolean; actionBusy: string;
  saveNotifications: (preferences: NotificationPreferences) => Promise<void>;
  updateService: (item: ModuleItem, values: { name: string; description: string; price: string; category: string }) => Promise<void>;
  generateContentDraft: (item: ModuleItem) => Promise<void>;
  updateContentItem: (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void>;
  reload: () => Promise<void>;
  back: () => void;
};

const ModuleScreen = ({ module, scope, data, loading, saving, actionBusy, saveNotifications, updateService, generateContentDraft, updateContentItem, reload, back }: ModuleScreenProps) => {
  const content = moduleNames[module] || ['Раздел', 'Рабочая очередь LocalOS.'];
  return <Screen title={content[0]} subtitle={content[1]} action={<button aria-label="Назад" onClick={back} className="grid h-11 w-11 place-items-center rounded-2xl bg-white/[0.05] ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"><ArrowLeft className="h-4 w-4" /></button>}>
    {loading ? <ReviewSkeleton /> : module === 'settings' ? <NotificationSettings preferences={data.preferences || {}} saving={saving} save={saveNotifications} /> : module === 'cards' ? <CardsModule scope={scope} items={data.items || []} reload={reload} /> : module === 'content' ? <ContentModule scope={scope} items={data.items || []} filters={data.filters} busy={actionBusy} generate={generateContentDraft} update={updateContentItem} reload={reload} /> : module === 'services' ? <ServicesModule scope={scope} items={data.items || []} busy={actionBusy} update={updateService} reload={reload} /> : module === 'finance' ? <FinanceModule scope={scope} items={data.items || []} reload={reload} /> : <GenericModule module={module} items={data.items || []} />}
  </Screen>;
};

const providerName = (value: string) => value.includes('2gis') || value.includes('two') || value.includes('2_gis') ? '2ГИС' : value.includes('yandex') ? 'Яндекс' : value;
const dateLabel = (value?: string) => value ? new Date(value).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'ещё не обновлялась';
const contentDateKey = (value?: string) => {
  const raw = String(value || '').trim();
  const match = raw.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match?.[1]) return match[1];
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return '';
  return [parsed.getUTCFullYear(), String(parsed.getUTCMonth() + 1).padStart(2, '0'), String(parsed.getUTCDate()).padStart(2, '0')].join('-');
};
const contentDateLabel = (value?: string, withWeekday = false) => {
  const key = contentDateKey(value);
  if (!key) return 'Без даты';
  return new Date(`${key}T12:00:00`).toLocaleDateString('ru-RU', withWeekday ? { weekday: 'long', day: 'numeric', month: 'long' } : { day: 'numeric', month: 'long' });
};
const monthlyRefreshCost = (interval: string, cost: number) => Math.ceil((30 * 24) / Math.max(Number(interval) || 24, 1)) * cost;

const CardsModule = ({ scope, items, reload }: { scope?: Scope; items: ModuleItem[]; reload: () => Promise<void> }) => {
  const [editing, setEditing] = useState('');
  const [interval, setInterval] = useState('24');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const saveSchedule = async (item: ModuleItem, enabled: boolean) => {
    setBusy(item.id || 'schedule');
    try {
      await fetch('/api/operator/mobile/cards/schedule', { method: 'PUT', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, business_id: item.business_id || item.id, enabled, interval_hours: Number(interval) }) }).then(readJson);
      await reload(); setEditing(''); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить график.'); }
    finally { setBusy(''); }
  };
  return <div>
    <div className="mb-4 rounded-[22px] bg-primary/[0.08] p-4 ring-1 ring-inset ring-primary/15"><div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-primary/15 text-primary"><RefreshCw className="h-5 w-5" /></span><div><b className="block text-sm">Данные из Яндекса и 2ГИС</b><p className="mt-1 text-xs leading-5 text-zinc-500">LocalOS проверяет карточки по вашему графику и показывает, когда данные были собраны в последний раз.</p></div></div></div>
    {error ? <InlineError text={error} /> : null}
    {items.length ? <div className="space-y-2">{items.map((item) => <article key={item.id} className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><b className="block text-sm leading-5">{item.title || item.business_name}</b><small className="mt-1 block truncate text-zinc-600">{item.subtitle || item.business_name}</small></div><StatusPill value={item.status} /></div><div className="mt-4 flex flex-wrap gap-2">{(item.provider_sources || []).filter(Boolean).map((source) => <span key={source} className="rounded-full bg-white/[0.05] px-3 py-1.5 text-[11px] font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07]">{providerName(source)}</span>)}</div><div className="mt-4 grid grid-cols-3 gap-2 text-center"><MetricMini label="Рейтинг" value={item.rating} /><MetricMini label="Отзывы" value={item.reviews_count} /><MetricMini label="SEO" value={item.seo_score} /></div><div className="mt-4 rounded-[16px] bg-black/20 p-3 text-xs leading-5 ring-1 ring-inset ring-white/[0.05]"><p className="text-zinc-400">Последняя проверка: <b className="font-medium text-zinc-200">{dateLabel(item.parse_updated_at || item.review_sync_last_run_at || item.updated_at)}</b></p><p className="mt-1 text-zinc-400">{item.review_sync_enabled ? <>Следующее обновление: <b className="font-medium text-zinc-200">{dateLabel(item.review_sync_next_run_at)}</b></> : 'Автоматическое обновление выключено'}</p><p className="mt-1 text-zinc-600">Одно обновление — {item.refresh_cost_credits || 10} кредитов</p></div>{editing === item.id ? <div className="mt-3 rounded-[18px] bg-white/[0.035] p-3 ring-1 ring-inset ring-white/[0.06]"><label className="text-[11px] text-zinc-500">Как часто проверять<select value={interval} onChange={(event) => setInterval(event.target.value)} className="mt-2 min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-sm text-zinc-200 ring-1 ring-inset ring-white/[0.07]"><option value="24">Каждый день</option><option value="48">Раз в 2 дня</option><option value="168">Раз в неделю</option><option value="336">Раз в 2 недели</option></select></label><p className="mt-3 text-pretty text-[11px] leading-5 text-zinc-500">Чем чаще проверка, тем быстрее LocalOS заметит новые отзывы и изменения в карточке. Но кредиты будут расходоваться быстрее: при этом графике — до <b className="font-semibold tabular-nums text-zinc-300">{monthlyRefreshCost(interval, item.refresh_cost_credits || 10)} кредитов за 30 дней</b>.</p><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" disabled={busy === item.id} onClick={() => void saveSchedule(item, false)} className="min-h-11 rounded-[14px] bg-white/[0.05] text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Выключить</button><button type="button" disabled={busy === item.id} onClick={() => void saveSchedule(item, true)} className="min-h-11 rounded-[14px] bg-primary text-xs font-semibold active:scale-[0.96]">{busy === item.id ? 'Сохраняем…' : 'Сохранить график'}</button></div></div> : <button type="button" onClick={() => { setInterval(String(item.review_sync_interval_hours || 24)); setEditing(item.id || 'schedule'); }} className="mt-3 min-h-11 w-full rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"><Settings className="mr-2 inline h-4 w-4" />Настроить график</button>}</article>)}</div> : <Empty icon={MapPinned} title="Карточки не подключены" text="Добавьте ссылки на Яндекс и 2ГИС в настройках бизнеса — после этого LocalOS начнёт следить за обновлениями." />}
  </div>;
};

const ContentModule = ({ scope, items, filters, busy, generate, update, reload }: { scope?: Scope; items: ModuleItem[]; filters?: ModuleData['filters']; busy: string; generate: (item: ModuleItem) => Promise<void>; update: (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void>; reload: () => Promise<void> }) => {
  const [editing, setEditing] = useState('');
  const [view, setView] = useState('calendar');
  const [generating, setGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [planAction, setPlanAction] = useState('');
  const [error, setError] = useState('');
  const allowedPeriods = (filters?.period_days || [14, 30]).filter((value) => Number.isFinite(value) && value > 0);
  const [periodDays, setPeriodDays] = useState(() => allowedPeriods.includes(30) ? 30 : allowedPeriods[0] || 30);
  const [density, setDensity] = useState('standard');
  const planTitle = items.find((item) => item.plan_title)?.plan_title;
  const planId = items.find((item) => item.plan_id)?.plan_id;
  useEffect(() => {
    if (!generating) return;
    const interval = window.setInterval(() => setGenerationProgress((value) => Math.min(92, value + 3)), 220);
    return () => window.clearInterval(interval);
  }, [generating]);
  const generatePlan = async () => {
    const startedAt = Date.now();
    setGenerating(true); setGenerationProgress(12); setError('');
    try {
      await fetch('/api/operator/mobile/content/plans/generate', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, business_id: scope?.kind === 'business' ? scope.id : null, period_days: periodDays, density }) }).then(readJson);
      const remaining = Math.max(0, 6800 - (Date.now() - startedAt));
      if (remaining) await new Promise<void>((resolve) => window.setTimeout(resolve, remaining));
      setGenerationProgress(100);
      await new Promise<void>((resolve) => window.setTimeout(resolve, 850));
      await reload(); setPlanAction(''); setView('calendar'); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось подготовить план.'); }
    finally { setGenerating(false); }
  };
  const deletePlan = async () => { if (!planId) return; setGenerating(true); try { await fetch(`/api/operator/mobile/content/plans/${planId}`, { method: 'DELETE', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, business_id: scope?.kind === 'business' ? scope.id : null }) }).then(readJson); await reload(); setPlanAction(''); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось удалить план.'); } finally { setGenerating(false); } };
  return <AnimatePresence initial={false} mode="wait">
    {generating ? <ContentPlanProgress key="progress" progress={generationProgress} periodDays={periodDays} density={density} /> : <motion.div key="content" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring}>
      {planTitle ? <section className="mb-3 rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><small className="text-zinc-600">Текущий контент-план</small><b className="mt-1 block text-balance text-base">{planTitle}</b><p className="mt-2 text-pretty text-xs text-zinc-500"><span className="tabular-nums">{items.length}</span> публикаций{items[0]?.plan_period_days ? <> · <span className="tabular-nums">{items[0].plan_period_days}</span> дней</> : null}</p></div><button type="button" aria-label="Дополнительные действия с планом" aria-expanded={planAction === 'menu'} onClick={() => setPlanAction(planAction === 'menu' ? '' : 'menu')} className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-white/[0.05] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]"><CircleEllipsis className="h-5 w-5" /></button></div><div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto] gap-2"><button type="button" onClick={() => { setView('posts'); setEditing(''); }} className="flex min-h-11 items-center justify-center gap-2 rounded-[14px] bg-primary px-3 text-xs font-semibold text-white shadow-[0_10px_24px_rgba(255,92,51,0.2)] transition-transform active:scale-[0.96]"><Pencil className="h-4 w-4" />Редактировать публикации</button><button type="button" onClick={() => setPlanAction('new')} className="min-h-11 rounded-[14px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]">Новый план</button></div>{planAction === 'menu' ? <div className="mt-3"><button type="button" onClick={() => setPlanAction('delete')} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-rose-500/[0.08] px-3 text-xs font-semibold text-rose-300 ring-1 ring-inset ring-rose-400/15 transition-transform active:scale-[0.96]"><Trash2 className="h-4 w-4" />Удалить текущий план</button></div> : null}{planAction === 'delete' ? <div className="mt-3 rounded-[18px] bg-rose-500/[0.07] p-3 ring-1 ring-inset ring-rose-400/15"><p className="text-pretty text-xs leading-5 text-rose-100/80">План и все его публикации будут удалены из LocalOS. Это действие нельзя отменить.</p><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" onClick={() => setPlanAction('')} className="min-h-11 rounded-[14px] bg-white/[0.05] text-xs font-semibold transition-transform active:scale-[0.96]">Оставить</button><button type="button" onClick={() => void deletePlan()} className="min-h-11 rounded-[14px] bg-rose-500 text-xs font-semibold text-white transition-transform active:scale-[0.96]">Удалить план</button></div></div> : null}</section> : null}
      {error ? <InlineError text={error} /> : null}
      {(!items.length || planAction === 'new') && scope?.kind === 'business' ? <ContentPlanSetup periods={allowedPeriods} periodDays={periodDays} setPeriodDays={setPeriodDays} density={density} setDensity={setDensity} existingPlan={Boolean(items.length)} cancel={items.length ? () => setPlanAction('') : undefined} generate={() => void generatePlan()} /> : null}
      {scope?.kind !== 'business' && !items.length ? <Empty icon={Building2} title="Выберите одну точку" text="Сеть можно анализировать целиком, но календарь создаётся для конкретного бизнеса." /> : null}
      {items.length && planAction !== 'new' ? <><Segments value={view} setValue={setView} options={[[ 'calendar', 'Календарь' ], [ 'posts', 'Посты' ]]} />{view === 'calendar' ? <ContentCalendar items={items} open={(id) => { setView('posts'); setEditing(id); }} /> : <div className="space-y-2">{items.map((item) => <ContentItemCard key={item.id} item={item} editing={editing === item.id} busy={busy === item.id} setEditing={() => setEditing(editing === item.id ? '' : item.id || '')} generate={generate} update={async (values) => { await update(item, values); setEditing(''); }} />)}</div>}</> : null}
    </motion.div>}
  </AnimatePresence>;
};

const ContentPlanSetup = ({ periods, periodDays, setPeriodDays, density, setDensity, existingPlan, cancel, generate }: { periods: number[]; periodDays: number; setPeriodDays: (value: number) => void; density: string; setDensity: (value: string) => void; existingPlan: boolean; cancel?: () => void; generate: () => void }) => {
  const weekly = density === 'light' ? 1 : density === 'active' ? 3 : 2;
  const estimate = Math.max(4, Math.round(periodDays / 7 * weekly));
  return <section className="mb-4 rounded-[26px] bg-gradient-to-b from-primary/[0.09] to-white/[0.035] p-4 shadow-[0_18px_60px_rgba(0,0,0,0.24)] ring-1 ring-inset ring-primary/15"><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/15 text-primary"><WandSparkles className="h-5 w-5" /></span><div><h2 className="text-balance text-base font-semibold">{existingPlan ? 'Настройте новый план' : 'LocalOS соберёт план за вас'}</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">Выберите горизонт и темп. Мы сверим услуги, спрос и карточку, затем расставим темы по календарю.</p></div></div><div className="mt-5"><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-zinc-600">Период</p><div className="grid grid-flow-col auto-cols-fr gap-2">{periods.map((days) => <button type="button" key={days} aria-pressed={periodDays === days} onClick={() => setPeriodDays(days)} className={`min-h-12 rounded-[15px] px-3 text-sm font-semibold tabular-nums ring-1 ring-inset transition-[background-color,color,transform,box-shadow] active:scale-[0.96] ${periodDays === days ? 'bg-primary text-white shadow-[0_10px_26px_rgba(255,92,51,0.2)] ring-primary' : 'bg-black/20 text-zinc-400 ring-white/[0.07]'}`}>{days} дней</button>)}</div></div><div className="mt-4"><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-zinc-600">Темп публикаций</p><div className="grid grid-cols-3 gap-2">{[['light', '1 в неделю'], ['standard', '2 в неделю'], ['active', '3 в неделю']].map(([key, label]) => <button type="button" key={key} aria-pressed={density === key} onClick={() => setDensity(key)} className={`min-h-12 rounded-[15px] px-2 text-[11px] font-semibold ring-1 ring-inset transition-[background-color,color,transform] active:scale-[0.96] ${density === key ? 'bg-white/[0.1] text-white ring-white/15' : 'bg-black/15 text-zinc-600 ring-white/[0.06]'}`}>{label}</button>)}</div></div><div className="mt-4 flex items-center justify-between rounded-[16px] bg-black/20 px-3 py-3 ring-1 ring-inset ring-white/[0.05]"><span className="text-xs text-zinc-500">Будет подготовлено</span><b className="text-sm tabular-nums text-zinc-200">около {estimate} публикаций</b></div><p className="mt-3 text-pretty text-[11px] leading-5 text-zinc-600">Ничего не публикуется автоматически. Сначала вы увидите календарь и сможете изменить каждую тему.</p><div className={`mt-4 grid gap-2 ${cancel ? 'grid-cols-[auto_minmax(0,1fr)]' : 'grid-cols-1'}`}>{cancel ? <button type="button" onClick={cancel} className="min-h-12 rounded-[16px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]">Отмена</button> : null}<button type="button" onClick={generate} className="flex min-h-12 items-center justify-center gap-2 rounded-[16px] bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96]"><WandSparkles className="h-4 w-4" />Собрать план на {periodDays} дней</button></div></section>;
};

const ContentPlanProgress = ({ progress, periodDays, density }: { progress: number; periodDays: number; density: string }) => {
  const stages = [['Сверяем услуги и карточку', 10], ['Отбираем темы для бизнеса', 34], ['Расставляем даты', 58], ['Собираем календарь', 82]];
  const weekly = density === 'light' ? 1 : density === 'active' ? 3 : 2;
  const estimate = Math.max(4, Math.round(periodDays / 7 * weekly));
  const complete = progress === 100;
  return <motion.section aria-live="polite" key="generation" initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0, y: -5, filter: 'blur(4px)' }} transition={spring} className={`rounded-[28px] bg-gradient-to-b p-5 shadow-[0_28px_90px_rgba(0,0,0,0.42)] ring-1 ring-inset transition-[background-color,box-shadow] ${complete ? 'from-emerald-950/60 to-zinc-900 ring-emerald-400/15' : 'from-zinc-900 to-zinc-900/70 ring-white/[0.08]'}`}><div className="flex items-start gap-3"><span className={`relative grid h-12 w-12 shrink-0 place-items-center rounded-[16px] ${complete ? 'bg-emerald-400/15 text-emerald-300' : 'bg-primary/15 text-primary'}`}><AnimatePresence initial={false} mode="popLayout">{complete ? <motion.span key="complete" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><Check className="h-5 w-5" /></motion.span> : <motion.span key="working" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><Sparkles className="h-5 w-5" /></motion.span>}</AnimatePresence>{complete ? null : <span className="absolute inset-0 animate-ping rounded-[16px] ring-1 ring-primary/25 motion-reduce:animate-none" />}</span><div className="min-w-0 flex-1"><small className={`font-semibold uppercase tracking-[0.13em] ${complete ? 'text-emerald-300' : 'text-primary'}`}>{complete ? 'Готово' : 'LocalOS работает'}</small><h2 className="mt-1 text-balance text-xl font-semibold tracking-[-0.035em]">{complete ? 'План готов — всё разложено по датам' : 'Собираем ваш контент-план'}</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">{complete ? <>Открываем календарь с <span className="tabular-nums">{estimate}</span> публикациями.</> : <>Анализируем данные и готовим около <span className="tabular-nums">{estimate}</span> публикаций на <span className="tabular-nums">{periodDays}</span> дней.</>}</p></div></div><div className="mt-6 h-2 overflow-hidden rounded-full bg-white/[0.06]"><motion.div className={`h-full rounded-full ${complete ? 'bg-emerald-400' : 'bg-primary'}`} animate={{ width: `${progress}%` }} transition={spring} /></div><div className="mt-2 flex items-center justify-between text-[11px]"><span className="text-zinc-600">{complete ? 'Календарь уже готов' : 'Можно оставить экран открытым'}</span><b className={`${complete ? 'text-emerald-300' : 'text-zinc-300'} tabular-nums`}>{progress}%</b></div><div className="mt-5 space-y-2">{stages.map(([label, threshold], index) => { const done = progress >= Number(threshold) + 18 || complete; const active = progress >= Number(threshold) && !done; return <motion.div key={String(label)} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring, delay: index * 0.08 }} className={`flex min-h-12 items-center gap-3 rounded-[16px] px-3 ring-1 ring-inset transition-[background-color,color,box-shadow] ${done ? 'bg-emerald-500/[0.07] text-zinc-200 ring-emerald-400/10' : active ? 'bg-primary/[0.08] text-white ring-primary/20' : 'bg-white/[0.025] text-zinc-600 ring-white/[0.05]'}`}><span className="relative grid h-8 w-8 shrink-0 place-items-center rounded-[11px] bg-black/20"><AnimatePresence initial={false} mode="popLayout">{done ? <motion.span key="done" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><Check className="h-4 w-4 text-emerald-300" /></motion.span> : active ? <motion.span key="active" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><Loader2 className="h-4 w-4 animate-spin text-primary motion-reduce:animate-none" /></motion.span> : <motion.span key="waiting" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><span className="block h-1.5 w-1.5 rounded-full bg-zinc-700" /></motion.span>}</AnimatePresence></span><span className="text-xs font-medium">{label}</span></motion.div>; })}</div></motion.section>;
};

const ContentCalendar = ({ items, open }: { items: ModuleItem[]; open: (id: string) => void }) => {
  const groups = items.reduce<Record<string, ModuleItem[]>>((result, item) => { const key = contentDateKey(item.scheduled_for) || 'Без даты'; result[key] = [...(result[key] || []), item]; return result; }, {});
  return <div className="space-y-3">{Object.entries(groups).map(([date, dayItems]) => <section key={date} className="rounded-[22px] bg-white/[0.035] p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex items-center gap-2 px-1 pb-2"><CalendarDays className="h-4 w-4 text-primary" /><b className="text-balance text-sm capitalize">{contentDateLabel(date, true)}</b></div>{dayItems.map((item) => <button type="button" key={item.id} onClick={() => open(item.id || '')} className="mt-1 flex min-h-14 w-full items-center gap-3 rounded-[16px] bg-black/20 px-3 text-left transition-transform active:scale-[0.96]"><span className={`h-2.5 w-2.5 rounded-full ${item.draft_text ? 'bg-emerald-400' : 'bg-amber-400'}`} /><span className="min-w-0 flex-1"><b className="block truncate text-xs">{item.title}</b><small className="block truncate text-zinc-600">{item.draft_text ? 'Черновик готов' : 'Нужно подготовить текст'}</small></span><ChevronRight className="h-4 w-4 text-zinc-700" /></button>)}</section>)}</div>;
};

const ContentItemCard = ({ item, editing, busy, setEditing, generate, update }: { item: ModuleItem; editing: boolean; busy: boolean; setEditing: () => void; generate: (item: ModuleItem) => Promise<void>; update: (values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void> }) => {
  const [theme, setTheme] = useState(item.title || '');
  const [draft, setDraft] = useState(item.draft_text || '');
  const [scheduled, setScheduled] = useState(contentDateKey(item.scheduled_for));
  useEffect(() => { setTheme(item.title || ''); setDraft(item.draft_text || ''); setScheduled(contentDateKey(item.scheduled_for)); }, [item.title, item.draft_text, item.scheduled_for]);
  return <article className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><small className="text-[10px] font-semibold uppercase tracking-[0.12em] text-primary">{contentDateLabel(item.scheduled_for)} · {item.content_type || 'публикация'}</small><b className="mt-1 block text-sm leading-5">{item.title}</b><small className="mt-1 block truncate text-zinc-600">{item.business_name}</small></div><StatusPill value={item.status} /></div>{editing ? <div className="mt-4 space-y-2"><input value={theme} onChange={(event) => setTheme(event.target.value)} aria-label="Тема публикации" className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><input type="date" value={scheduled} onChange={(event) => setScheduled(event.target.value)} aria-label="Дата публикации" className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-sm text-zinc-300 outline-none ring-1 ring-inset ring-white/[0.07]" /><textarea value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="Текст публикации" rows={6} className="w-full rounded-[14px] bg-black/20 p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" />{draft.trim() ? null : <button type="button" disabled={busy} onClick={() => void generate(item)} className="flex min-h-12 w-full items-center justify-center gap-2 rounded-[14px] bg-primary/15 px-3 text-sm font-semibold text-primary ring-1 ring-inset ring-primary/20 transition-transform active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <WandSparkles className="h-4 w-4" />}{busy ? 'Готовим черновик…' : 'Создать черновик'}</button>}<button type="button" disabled={busy} onClick={() => void update({ theme, draft_text: draft, scheduled_for: scheduled })} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-primary text-xs font-semibold transition-transform active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}Сохранить</button></div> : <><p className="mt-3 line-clamp-5 whitespace-pre-wrap text-sm leading-6 text-zinc-400">{item.draft_text || item.subtitle}</p>{item.draft_text ? <button type="button" disabled={busy} onClick={setEditing} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-white/[0.055] text-xs font-semibold text-zinc-200 ring-1 ring-inset ring-white/[0.08] transition-transform active:scale-[0.96] disabled:opacity-50"><Pencil className="h-4 w-4" />Редактировать</button> : <div className="mt-4 grid grid-cols-2 gap-2"><button type="button" disabled={busy} onClick={setEditing} className="flex min-h-11 items-center justify-center gap-2 rounded-[14px] bg-white/[0.05] px-3 text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96] disabled:opacity-50"><Pencil className="h-4 w-4" />Изменить</button><button type="button" disabled={busy} onClick={() => void generate(item)} className="flex min-h-11 items-center justify-center gap-2 rounded-[14px] bg-primary/15 px-3 text-xs font-semibold text-primary ring-1 ring-inset ring-primary/20 transition-transform active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <WandSparkles className="h-4 w-4" />}Черновик</button></div>}</>}</article>;
};

const ServicesModule = ({ scope, items, busy, update, reload }: { scope?: Scope; items: ModuleItem[]; busy: string; update: (item: ModuleItem, values: { name: string; description: string; price: string; category: string }) => Promise<void>; reload: () => Promise<void> }) => {
  const [editing, setEditing] = useState('');
  const [analysis, setAnalysis] = useState<{ action_id?: string; mode: string; estimated_credits?: number; service_count?: number; analysis?: { before_count?: number; after_count?: number; groups?: unknown[] } } | null>(null);
  const [running, setRunning] = useState('');
  const [error, setError] = useState('');
  const run = async (mode: string, confirmed = false) => { setRunning(mode); try { const result = await fetch('/api/operator/mobile/services/analyze', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, business_id: scope?.kind === 'business' ? scope.id : null, mode, confirmed, action_id: confirmed ? analysis?.action_id : null }) }).then(readJson<{ action_id?: string; mode?: string; estimated_credits?: number; service_count?: number; analysis?: { before_count?: number; after_count?: number; groups?: unknown[] }; result?: { created_count?: number; archived_count?: number } } >); if (confirmed) { setAnalysis(null); await reload(); } else setAnalysis({ mode, ...result }); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проанализировать услуги.'); } finally { setRunning(''); } };
  return <div><div className="mb-3 grid grid-cols-2 gap-2"><button type="button" disabled={Boolean(running) || scope?.kind !== 'business'} onClick={() => void run('optimize')} className="min-h-20 rounded-[20px] bg-primary/[0.1] p-3 text-left ring-1 ring-inset ring-primary/20 active:scale-[0.96] disabled:opacity-45"><WandSparkles className="h-5 w-5 text-primary" /><b className="mt-2 block text-xs">Улучшить услуги</b><small className="mt-1 block text-[10px] leading-4 text-zinc-600">Названия и описания</small></button><button type="button" disabled={Boolean(running) || scope?.kind !== 'business'} onClick={() => void run('compress')} className="min-h-20 rounded-[20px] bg-white/[0.04] p-3 text-left ring-1 ring-inset ring-white/[0.07] active:scale-[0.96] disabled:opacity-45"><PackageCheck className="h-5 w-5 text-primary" /><b className="mt-2 block text-xs">Сократить меню</b><small className="mt-1 block text-[10px] leading-4 text-zinc-600">Объединить повторы</small></button></div>{scope?.kind !== 'business' ? <p className="mb-3 text-xs text-zinc-600">Для изменений выберите конкретную точку.</p> : null}{error ? <InlineError text={error} /> : null}{analysis ? <section className="mb-3 rounded-[22px] bg-zinc-900 p-4 ring-1 ring-inset ring-primary/25"><b className="text-sm">{analysis.mode === 'compress' ? 'Проверим сокращение меню' : 'Подготовим улучшения'}</b><p className="mt-2 text-xs leading-5 text-zinc-400">{analysis.mode === 'compress' ? `Сейчас ${analysis.analysis?.before_count || items.length} позиций, после объединения останется около ${analysis.analysis?.after_count || items.length}. Исходные позиции будут перенесены в архив LocalOS.` : `LocalOS подготовит варианты для ${analysis.service_count || items.length} услуг. Стоимость — до ${analysis.estimated_credits || 0} кредитов.`}</p><p className="mt-2 text-[11px] text-zinc-600">На Яндекс и 2ГИС изменения не отправляются.</p><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" onClick={() => setAnalysis(null)} className="min-h-11 rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07]">Отмена</button><button type="button" disabled={Boolean(running)} onClick={() => void run(analysis.mode, true)} className="min-h-11 rounded-[14px] bg-primary text-xs font-semibold">{running ? 'Выполняем…' : 'Подтвердить'}</button></div></section> : null}{items.length ? <div className="space-y-2">{items.map((item) => <ServiceItemCard key={item.id} item={item} editing={editing === item.id} busy={busy === item.id} setEditing={() => setEditing(editing === item.id ? '' : item.id || '')} update={async (values) => { await update(item, values); setEditing(''); }} />)}</div> : <Empty icon={LayoutGrid} title="Услуги не добавлены" text="Добавьте первую услугу, чтобы LocalOS мог проверить название, описание и цену." />}</div>;
};

const ServiceItemCard = ({ item, editing, busy, setEditing, update }: { item: ModuleItem; editing: boolean; busy: boolean; setEditing: () => void; update: (values: { name: string; description: string; price: string; category: string }) => Promise<void> }) => {
  const [name, setName] = useState(item.title || '');
  const [description, setDescription] = useState(item.subtitle || '');
  const [price, setPrice] = useState(item.price || '');
  const [category, setCategory] = useState(item.category || '');
  return <article className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><b className="block text-sm leading-5">{item.title}</b><small className="mt-1 block truncate text-zinc-600">{[item.business_name, item.category].filter(Boolean).join(' · ')}</small><small className="mt-1 block text-[10px] text-zinc-700">{item.source ? `Получено из ${providerName(item.source)}` : 'Добавлено в LocalOS'} · обновлено {dateLabel(item.updated_at)}</small></div><StatusPill value={item.status} /></div>{editing ? <div className="mt-4 space-y-2"><input value={name} onChange={(event) => setName(event.target.value)} aria-label="Название услуги" className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><div className="grid grid-cols-2 gap-2"><input value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Категория услуги" placeholder="Категория" className="min-h-11 min-w-0 rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07]" /><input value={price} onChange={(event) => setPrice(event.target.value)} aria-label="Цена услуги" placeholder="Цена" className="min-h-11 min-w-0 rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07]" /></div><textarea value={description} onChange={(event) => setDescription(event.target.value)} aria-label="Описание услуги" rows={4} className="w-full rounded-[14px] bg-black/20 p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><button type="button" disabled={busy} onClick={() => void update({ name, description, price, category })} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-primary text-xs font-semibold active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}Сохранить изменения</button></div> : <><p className="mt-3 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-zinc-400">{item.subtitle}</p><div className="mt-3 flex items-center justify-between"><b className="text-sm tabular-nums text-zinc-200">{item.price || 'Цена не указана'}</b><button type="button" onClick={setEditing} className="flex min-h-11 items-center gap-2 rounded-[14px] bg-white/[0.055] px-4 text-xs font-semibold ring-1 ring-inset ring-white/[0.08] active:scale-[0.96]"><Pencil className="h-4 w-4" />Изменить</button></div></>}</article>;
};

type RecognizedSale = { id?: string; transaction_date?: string; amount?: number; title?: string; sale_type?: 'service' | 'upsell' | 'cross_sell'; notes?: string };
const saleTypeLabel = (value?: string) => value === 'upsell' ? 'Допродажа' : value === 'cross_sell' ? 'Кросс-продажа · товар' : 'Услуга';

const FinanceModule = ({ scope, items, reload }: { scope?: Scope; items: ModuleItem[]; reload: () => Promise<void> }) => {
  const [text, setText] = useState(''); const [file, setFile] = useState<File | null>(null); const [sales, setSales] = useState<RecognizedSale[]>([]); const [busy, setBusy] = useState(''); const [error, setError] = useState(''); const [success, setSuccess] = useState(''); const [actionId, setActionId] = useState('');
  const recognize = async () => { setBusy('recognize'); setSuccess(''); try { let options: RequestInit; if (file) { const body = new FormData(); body.append('file', file); body.append('scope_type', scope?.kind || 'business'); body.append('scope_id', scope?.id || ''); if (scope?.kind === 'business' && scope.id) body.append('business_id', scope.id); options = { method: 'POST', headers: authOnlyHeaders(), body }; } else options = { method: 'POST', headers: authHeaders(), body: JSON.stringify({ text, scope_type: scope?.kind, scope_id: scope?.id || null, business_id: scope?.kind === 'business' ? scope.id : null }) }; const result = await fetch('/api/operator/mobile/finance/recognize', options).then(readJson<{ transactions?: RecognizedSale[] }>); const recognized = (result.transactions || []).map((item, index) => ({ ...item, id: item.id || `sale-${index}` })); setSales(recognized); setActionId(''); setError(recognized.length ? '' : 'Не нашли сумму и состав заказа. Добавьте название услуги и сумму или загрузите более чёткое фото.'); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось распознать продажи.'); } finally { setBusy(''); } };
  const prepare = async () => { setBusy('preview'); try { const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'finance.sales_import', input: { business_id: scope?.kind === 'business' ? scope.id : null, transactions: sales } }) }).then(readJson<{ preview?: ActionPreview }>); setActionId(result.preview?.action_id || ''); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось подготовить загрузку.'); } finally { setBusy(''); } };
  const confirm = async () => { if (!actionId) return; setBusy('confirm'); try { const result = await fetch(`/api/operator/mobile/actions/${actionId}/confirm`, { method: 'POST', headers: authHeaders(), body: '{}' }).then(readJson<{ operator_result?: { created_count?: number } }>); const createdCount = Number(result.operator_result?.created_count || sales.length); setSales([]); setText(''); setFile(null); setActionId(''); setError(''); setSuccess(createdCount === 1 ? 'Заказ записан в LocalOS' : `Записано заказов: ${createdCount}`); await reload(); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось добавить продажи.'); } finally { setBusy(''); } };
  return <div>{scope?.kind !== 'business' ? <InlineError text="Для загрузки продаж сначала выберите конкретный бизнес." /> : <section className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><b className="text-sm">Записать выполненный заказ</b><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">Опишите заказ или загрузите фото либо документ. Сначала LocalOS покажет распознанные услуги и сумму — запись появится только после вашего подтверждения.</p><textarea value={text} onChange={(event) => { setText(event.target.value); setFile(null); setSuccess(''); }} rows={5} placeholder={'Например:\n24.07 Стрижка 2 900\nШампунь 850 — товар'} className="mt-3 w-full resize-none rounded-[16px] bg-black/20 p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" /><div className="mt-2 grid grid-cols-2 gap-2"><label className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07]"><Camera className="h-4 w-4" />Фото<input type="file" accept="image/*" capture="environment" className="sr-only" onChange={(event) => { setFile(event.target.files?.[0] || null); setText(''); setSuccess(''); }} /></label><label className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07]"><Upload className="h-4 w-4" />Документ<input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,image/*" className="sr-only" onChange={(event) => { setFile(event.target.files?.[0] || null); setText(''); setSuccess(''); }} /></label></div>{file ? <p className="mt-2 truncate text-xs text-primary">Выбран файл: {file.name}</p> : null}<button type="button" disabled={busy !== '' || (!text.trim() && !file)} onClick={() => void recognize()} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold transition-transform active:scale-[0.96] disabled:opacity-45">{busy === 'recognize' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Sparkles className="h-4 w-4" />}{busy === 'recognize' ? 'Разбираем заказ…' : 'Распознать заказ'}</button></section>}{success ? <div className="mt-3 flex items-center gap-3 rounded-[18px] bg-emerald-500/10 p-4 text-sm font-medium text-emerald-200 ring-1 ring-inset ring-emerald-400/20"><Check className="h-5 w-5 shrink-0" />{success}</div> : null}{error ? <InlineError text={error} /> : null}{sales.length ? <section className="mt-3 rounded-[22px] bg-zinc-900 p-4 ring-1 ring-inset ring-primary/25"><div className="flex items-center justify-between"><b className="text-sm">Найдено позиций: <span className="tabular-nums text-primary">{sales.length}</span></b><small className="text-zinc-600">Проверьте перед записью</small></div><div className="mt-3 space-y-2">{sales.map((sale, index) => <div key={sale.id || index} className="rounded-[16px] bg-black/20 p-3"><div className="flex gap-2"><input value={sale.title || ''} onChange={(event) => setSales((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, title: event.target.value } : item))} className="min-h-11 min-w-0 flex-1 rounded-[12px] bg-white/[0.04] px-3 text-xs ring-1 ring-inset ring-white/[0.06]" /><input inputMode="decimal" value={sale.amount || ''} onChange={(event) => setSales((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, amount: Number(event.target.value) } : item))} className="min-h-11 w-24 rounded-[12px] bg-white/[0.04] px-3 text-right text-xs tabular-nums ring-1 ring-inset ring-white/[0.06]" /></div><select value={sale.sale_type || 'service'} onChange={(event) => setSales((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, sale_type: event.target.value === 'upsell' ? 'upsell' : event.target.value === 'cross_sell' ? 'cross_sell' : 'service' } : item))} className="mt-2 min-h-11 w-full rounded-[12px] bg-zinc-900 px-3 text-xs ring-1 ring-inset ring-white/[0.06]"><option value="service">Услуга</option><option value="upsell">Допродажа</option><option value="cross_sell">Кросс-продажа · товар</option></select><small className="mt-1 block text-zinc-700">{sale.transaction_date || 'Дата не распознана'} · {saleTypeLabel(sale.sale_type)}</small></div>)}</div>{actionId ? <div className="mt-3 rounded-[16px] bg-primary/[0.08] p-3 text-xs leading-5 text-zinc-400">Будет записано позиций: <span className="tabular-nums">{sales.length}</span>. Внешние системы не изменятся.<button type="button" disabled={busy !== ''} onClick={() => void confirm()} className="mt-3 min-h-11 w-full rounded-[14px] bg-primary font-semibold text-white transition-transform active:scale-[0.96]">{busy === 'confirm' ? 'Записываем…' : 'Подтвердить и записать'}</button></div> : <button type="button" disabled={busy !== ''} onClick={() => void prepare()} className="mt-3 min-h-12 w-full rounded-2xl bg-primary text-sm font-semibold transition-transform active:scale-[0.96]">Проверить перед записью</button>}</section> : null}{items.length ? <div className="mt-5"><h2 className="mb-2 text-sm font-semibold">Последние операции</h2><GenericModule module="finance" items={items} /></div> : null}</div>;
};

const GenericModule = ({ module, items }: { module: string; items: ModuleItem[] }) => items.length ? <div className="space-y-2">{items.map((item) => <article key={item.id} className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><b className="block text-sm leading-5">{item.title || 'Без названия'}</b><small className="mt-1 block truncate text-zinc-600">{[item.business_name, item.category].filter(Boolean).join(' · ')}</small></div><StatusPill value={item.run_status || item.status} /></div>{item.subtitle ? <p className="mt-3 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-zinc-400">{item.subtitle}</p> : null}{item.error_text ? <p className="mt-3 rounded-[14px] bg-rose-500/10 p-3 text-xs leading-5 text-rose-200">{item.error_text}</p> : null}<div className="mt-3 flex flex-wrap gap-3 text-[11px] text-zinc-600">{item.amount !== undefined ? <span className={`tabular-nums ${item.transaction_type === 'income' ? 'text-emerald-300' : 'text-zinc-300'}`}>{item.transaction_type === 'income' ? '+' : '−'}{item.amount} ₽</span> : null}{item.selected_channel ? <span>Канал: <b className="text-zinc-300">{item.selected_channel}</b></span> : null}</div></article>)}</div> : <Empty icon={moduleIcons[module] || CircleEllipsis} title="Пока пусто" text="Когда LocalOS получит реальные данные, они появятся здесь. Ничего выдуманного не показываем." />;

const NotificationSettings = ({ preferences, saving, save }: { preferences: NotificationPreferences; saving: boolean; save: (preferences: NotificationPreferences) => Promise<void> }) => {
  const [value, setValue] = useState<NotificationPreferences>(preferences);
  useEffect(() => setValue(preferences), [preferences]);
  const rows: Array<[keyof NotificationPreferences, string, string]> = [['daily_digest', 'Утреннее саммари', 'Только реальные задачи'], ['reviews', 'Новые отзывы', 'Когда нужен ответ'], ['tasks', 'Решения', 'Черновики и подтверждения'], ['errors', 'Ошибки', 'Точка или интеграция требует внимания'], ['agent_results', 'ИИ-сотрудники', 'Результат готов к review']];
  return <div><div className="space-y-2">{rows.map(([key, title, description]) => <label key={key} className="flex min-h-16 items-center gap-3 rounded-[20px] bg-white/[0.04] px-4 ring-1 ring-inset ring-white/[0.07]"><span className="min-w-0 flex-1"><b className="block text-sm">{title}</b><small className="mt-1 block text-zinc-600">{description}</small></span><input type="checkbox" checked={Boolean(value[key])} onChange={(event) => setValue((current) => ({ ...current, [key]: event.target.checked }))} className="h-6 w-6 accent-primary" /></label>)}</div><button disabled={saving} onClick={() => void save(value)} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold active:scale-[0.96] disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}{saving ? 'Сохраняем…' : 'Сохранить'}</button></div>;
};

const StatusPill = ({ value }: { value?: string }) => <span className="shrink-0 rounded-full bg-white/[0.05] px-2.5 py-1 text-[10px] text-zinc-500 ring-1 ring-inset ring-white/[0.06]">{value === 'active' ? 'Активна' : value === 'archived' ? 'Архив' : value === 'approved' || value === 'completed' ? 'Готово' : value === 'draft' || value === 'draft_generated' || value === 'edited' ? 'Черновик' : value === 'planned' ? 'Запланировано' : value === 'fresh' ? 'Актуально' : value === 'running' || value === 'processing' ? 'В работе' : value === 'failed' || value === 'error' ? 'Ошибка' : value || 'Данные'}</span>;

const ScopePicker = ({ catalog, search, setSearch, choose }: { catalog?: Catalog; search: string; setSearch: (value: string) => void; choose: (kind: string, id?: string | null) => void }) => <Screen title="Где работаем?" subtitle="Выбор сохранится для следующего запуска."><label className="relative block"><Search className="absolute left-4 top-4 h-4 w-4 text-zinc-600" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название, город или адрес" className="min-h-12 w-full rounded-2xl bg-white/[0.05] pl-11 pr-4 text-sm outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label><div className="mt-4 space-y-2">{catalog?.platform ? <ScopeRow icon={ShieldCheck} label="Вся платформа" meta="Операционная картина LocalOS" onClick={() => void choose('platform')} /> : null}{catalog?.networks?.map((item) => <ScopeRow key={item.id} icon={Network} label={item.name || 'Сеть'} meta={`${item.locations_count || 0} точек`} onClick={() => void choose('network', item.id)} />)}{catalog?.businesses?.map((item) => <ScopeRow key={item.id} icon={Building2} label={item.name || 'Бизнес'} meta={[item.network_name, item.address].filter(Boolean).join(' · ')} onClick={() => void choose('business', item.id)} />)}</div></Screen>;

const BottomNav = ({ current, showMore, setCurrent }: { current: Tab; showMore: boolean; setCurrent: (tab: Tab) => void }) => { const items: Array<[Tab, string, typeof Sparkles]> = [['today', 'Сегодня', Sparkles], ['tasks', 'Задачи', ClipboardCheck], ['reviews', 'Отзывы', MessageCircle], ['operator', 'Оператор', Bot]]; if (showMore) items.push(['more', 'Ещё', CircleEllipsis]); return <nav className="fixed inset-x-0 bottom-0 z-20 mx-auto max-w-xl border-t border-white/[0.07] bg-zinc-950/90 px-2 pb-[calc(8px+env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl"> <div className="grid grid-flow-col auto-cols-fr">{items.map(([key, label, Icon]) => <button key={key} onClick={() => setCurrent(key)} className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-[16px] text-[10px] transition-[color,transform,background-color] active:scale-[0.96] ${current === key ? 'bg-primary/10 text-primary' : 'text-zinc-600'}`}><Icon className="h-5 w-5" /><span>{label}</span></button>)}</div></nav>; };

const Screen = ({ title, subtitle, children, action }: { title: string; subtitle: string; children: React.ReactNode; action?: React.ReactNode }) => <section className="px-4"><div className="mb-5 flex items-start gap-3"><div className="min-w-0 flex-1"><h1 className="text-balance text-2xl font-semibold tracking-[-0.04em]">{title}</h1><p className="mt-1 text-pretty text-sm leading-6 text-zinc-500">{subtitle}</p></div>{action}</div>{children}</section>;
const PrimaryButton = ({ children, onClick }: { children: React.ReactNode; onClick: () => void }) => <button onClick={onClick} className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96]">{children}<ChevronRight className="h-4 w-4" /></button>;
const TaskRow = ({ item, onClick }: { item: AttentionItem; onClick: () => void }) => <button onClick={onClick} className="mt-2 flex min-h-16 w-full items-center gap-3 rounded-[20px] bg-white/[0.035] px-4 py-3 text-left ring-1 ring-inset ring-white/[0.06] active:scale-[0.98]"><span className={`h-2.5 w-2.5 rounded-full ${item.severity === 'high' ? 'bg-rose-400' : item.severity === 'medium' ? 'bg-amber-400' : 'bg-emerald-400'}`} /><span className="min-w-0 flex-1"><b className="block truncate text-sm">{item.title || 'Задача'}</b><small className="mt-1 block truncate text-zinc-600">{item.description}</small>{item.progress !== undefined && item.progress !== null ? <span className="mt-2 block h-1 overflow-hidden rounded-full bg-white/[0.06]"><i className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(item.progress, 100))}%` }} /></span> : item.action_unavailable_reason ? <small className="mt-1 block truncate text-amber-300/70">{item.action_unavailable_reason}</small> : null}</span>{item.count ? <b className="tabular-nums text-zinc-400">{item.count}</b> : null}<ChevronRight className="h-4 w-4 text-zinc-700" /></button>;
const Segments = ({ value, setValue, options }: { value: string; setValue: (value: string) => void; options: string[][] }) => <div className="mb-4 flex gap-1 overflow-x-auto rounded-[18px] bg-white/[0.035] p-1 ring-1 ring-inset ring-white/[0.06]">{options.map(([key, label]) => <button key={key} onClick={() => setValue(key)} className={`min-h-11 flex-1 whitespace-nowrap rounded-[14px] px-3 text-xs font-semibold transition-[background-color,color,transform] active:scale-[0.96] ${value === key ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-600'}`}>{label}</button>)}</div>;
const ScopeRow = ({ icon: Icon, label, meta, onClick }: { icon: typeof Star; label: string; meta: string; onClick: () => void }) => <button onClick={onClick} className="flex min-h-16 w-full items-center gap-3 rounded-[20px] bg-white/[0.04] px-3 text-left ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"><span className="grid h-10 w-10 place-items-center rounded-[14px] bg-primary/12 text-primary"><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-sm">{label}</b><small className="block truncate text-zinc-600">{meta}</small></span><ChevronRight className="h-4 w-4 text-zinc-700" /></button>;
const Empty = ({ icon: Icon, title, text }: { icon: typeof Star; title: string; text: string }) => <div className="mt-4 rounded-[24px] bg-white/[0.025] px-6 py-10 text-center ring-1 ring-inset ring-white/[0.06]"><Icon className="mx-auto h-7 w-7 text-zinc-700" /><h3 className="mt-3 font-semibold">{title}</h3><p className="mx-auto mt-2 max-w-xs text-pretty text-sm leading-6 text-zinc-600">{text}</p></div>;
const InlineError = ({ text }: { text: string }) => <div className="mb-3 flex gap-2 rounded-[16px] bg-rose-500/10 p-3 text-xs leading-5 text-rose-100 ring-1 ring-inset ring-rose-400/20"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{text}</div>;
const ReviewSkeleton = () => <div className="space-y-3">{[1, 2, 3].map((item) => <div key={item} className="h-44 animate-pulse rounded-[24px] bg-white/[0.04] motion-reduce:animate-none" />)}</div>;
const LoadingScreen = ({ slow }: { slow: boolean }) => <main className="grid min-h-[100dvh] place-items-center bg-zinc-950 px-8 text-center text-white"><div><span className="relative mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-zinc-900 ring-1 ring-inset ring-white/[0.08]"><Sparkles className="h-7 w-7 text-primary" /></span><h1 className="mt-6 text-xl font-semibold tracking-[-0.03em]">Собираем ваш рабочий день</h1>{slow ? <p className="mt-3 text-sm text-zinc-500">Сверяем задачи и источники…</p> : null}</div></main>;
const TelegramGate = () => <main className="grid min-h-[100dvh] place-items-center bg-zinc-950 p-6 text-center text-white"><div className="max-w-sm"><span className="mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-primary/12 text-primary ring-1 ring-inset ring-primary/20"><Send className="h-7 w-7" /></span><h1 className="mt-6 text-balance text-2xl font-semibold tracking-[-0.04em]">Откройте LocalOS в Telegram</h1><p className="mt-3 text-pretty text-sm leading-6 text-zinc-500">Вернитесь в чат с LocalOS и нажмите постоянную кнопку приложения внизу экрана.</p><a href="https://t.me/LocalOspro_bot" className="mt-6 flex min-h-12 items-center justify-center rounded-2xl bg-primary px-5 text-sm font-semibold text-white active:scale-[0.96]">Открыть бота</a></div></main>;

export default TelegramControlPage;
