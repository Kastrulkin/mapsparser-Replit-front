import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertCircle, ArrowLeft, BarChart3, Bot, Building2, CalendarDays, Camera, Check, ChevronLeft, ChevronRight, CircleEllipsis,
  ClipboardCheck, Copy, CreditCard, FileText, LayoutGrid, Loader2, MapPinned,
  MessageCircle, Network, PackageCheck, Pencil, Radio, RefreshCw, Search, Send, Settings, ShieldCheck,
  Sparkles, Star, Trash2, TrendingDown, TrendingUp, Upload, Users, WandSparkles, X,
} from 'lucide-react';
import localOsLogo from '@/assets/images/logo.png';
import { PartnershipsMobileModule } from '@/components/telegram/PartnershipsMobileModule';
import { CompaniesMobileModule } from '@/components/telegram/CompaniesMobileModule';
import { CommunitySourcesMobileModule } from '@/components/telegram/CommunitySourcesMobileModule';
import { CommunityFeedMobile } from '@/components/telegram/CommunityFeedMobile';
import AgentsMobileModule from '@/components/telegram/AgentsMobileModule';
import DiagnosticsMobileModule from '@/components/telegram/DiagnosticsMobileModule';
import FinanceCrmMobilePanel from '@/components/telegram/FinanceCrmMobilePanel';
import ActionPreviewSheet, { type MobileActionPreview } from '@/components/telegram/ActionPreviewSheet';
import JobProgressSheet from '@/components/telegram/JobProgressSheet';
import MobileShell from '@/components/telegram/MobileShell';
import { ScopeProvider, useMobileScope, type MobileScope } from '@/components/telegram/ScopeProvider';
import { ProgressMobileModule, type ProgressPayload } from '@/components/telegram/ProgressMobileModule';
import { TodayMobileV2, type TodayPayload } from '@/components/telegram/TodayMobileV2';
import GrowthNavigation from '@/components/telegram/GrowthNavigation';
import LeadJourneyOnboarding from '@/components/telegram/LeadJourneyOnboarding';
import { JourneyActionCard } from '@/components/journey/JourneyActionCard';
import { clearLeadJourneyToken, saveLeadJourneyToken, type JourneyAction, type LeadJourneyKey } from '@/lib/leadJourney';
import { cancelMobileJob, confirmMobileAction, loadMobileJob, mobileAuthHeaders, mobileJsonHeaders, mobileScopeQuery, readMobileJson, retryMobileJob, type MobileJob } from '@/lib/mobileDataClient';
import { resolveMobileRoute } from '@/lib/mobileDeepLinkRouter';
import { resolveMobileAttentionScreen } from '@/lib/mobileTaskRouter';

type AttentionItem = {
  id?: string;
  title?: string;
  description?: string;
  count?: number;
  status?: string;
  severity?: string;
  progress?: number | null;
  action_unavailable_reason?: string;
  category?: string;
  screen?: string;
  cta?: { href?: string };
  target_scope?: { kind?: string; id?: string };
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
  scope?: MobileScope;
  attention_items?: AttentionItem[];
  metrics?: Metric[];
  data_warnings?: string[];
};

type Catalog = {
  platform?: MobileScope | null;
  networks?: NetworkCatalogItem[];
  businesses?: BusinessCatalogItem[];
  total_choices?: number;
  business_cursor?: string;
  next_business_cursor?: string | null;
  has_more_businesses?: boolean;
};

export type NetworkCatalogItem = { id?: string; name?: string; locations_count?: number };
export type BusinessCatalogItem = { id?: string; name?: string; address?: string; network_id?: string | null; network_name?: string | null };
type NetworkLocationsResult = {
  items?: BusinessCatalogItem[];
  counts?: { total?: number };
  cursor?: string | null;
};

type Bootstrap = {
  success?: boolean;
  error?: string;
  user?: { id?: string; name?: string; is_superadmin?: boolean };
  selected_scope?: MobileScope;
  summary?: Summary;
  catalog?: Catalog;
  web_session_token?: string;
  navigation?: NavigationItem[];
  today_v2_enabled?: boolean;
  resolved_deep_link?: { screen?: string; item_type?: string | null; item_id?: string | null; filters?: Record<string, string>; fallback_applied?: boolean };
  active_job?: MobileJob | null;
};

type NavigationItem = {
  key: string;
  label: string;
  group: 'primary' | 'more';
  status: 'available' | 'read_only' | 'hidden';
  reason?: string;
  available_actions?: string[];
  supported_scopes?: string[];
  deep_link_targets?: string[];
  version?: number;
};

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

type OperatorMessage = {
  id?: string;
  role: 'user' | 'operator';
  text: string;
  status?: string;
  capability?: string;
  created_at?: string;
  screen?: string;
  action_id?: string;
  action_error?: string;
};
type OperatorActionDecision = 'confirm' | 'reject';
type ModuleItem = { id?: string; business_id?: string; kind?: string; title?: string; subtitle?: string; business_name?: string; status?: string; rating?: number; reviews_count?: number; seo_score?: number; price?: string; category?: string; source?: string; updated_at?: string; amount?: string | number; previous_amount?: string | number; unit?: string; metric_key?: string; period_label?: string; day?: string; orders_count?: number; transaction_type?: string; selected_channel?: string; run_id?: string; run_status?: string; error_text?: string; provider_sources?: string[]; parse_status?: string; parse_source?: string; parse_updated_at?: string; refresh_cost_credits?: number; scheduled_refresh_cost_credits?: number; review_sync_enabled?: boolean; review_sync_interval_hours?: number; review_sync_schedule_mode?: string; review_sync_schedule_days?: number[]; review_sync_schedule_time?: string; review_sync_next_run_at?: string; review_sync_last_run_at?: string; review_sync_last_status?: string; plan_id?: string; plan_title?: string; plan_period_days?: number; scheduled_for?: string; content_type?: string; draft_text?: string };
type NotificationPreferences = { daily_digest?: boolean; reviews?: boolean; tasks?: boolean; errors?: boolean; agent_results?: boolean; finance_rhythm?: boolean; content_publications?: boolean };
type FinanceValue = string | number | boolean | null | undefined;
type FinanceRecommendation = { code?: string; title?: string; text?: string; severity?: string; target_metric?: string | null; data_needed?: string[] };
type FinanceDashboardMobile = {
  period?: { start_date?: string; end_date?: string };
  kpis?: Record<string, FinanceValue>;
  explanations?: Record<string, string>;
  statuses?: Record<string, string>;
  data_quality?: { score?: number; missing?: string[]; approximate?: string[]; precise?: string[] };
  recommendations?: FinanceRecommendation[];
  action_logs?: Array<{ action_key?: string; status?: string; completed_at?: string | null }>;
  action_impact?: { completed_actions_count?: number; deltas?: Array<{ metric?: string; current?: FinanceValue; previous?: FinanceValue; delta?: FinanceValue; direction?: string }> };
  period_history?: Array<{ label?: string; period_start?: string; period_end?: string; revenue?: FinanceValue; operating_margin?: FinanceValue; no_show_rate?: FinanceValue; rebooking_rate?: FinanceValue; workplace_occupancy?: FinanceValue }>;
  services?: Array<Record<string, FinanceValue>>;
  staff?: Array<Record<string, FinanceValue>>;
  workplaces?: Array<Record<string, FinanceValue>>;
};
type ModuleData = { items?: ModuleItem[]; counts?: { total?: number }; as_of?: string; data_warnings?: string[]; status?: string; preferences?: NotificationPreferences; available_actions?: Array<{ key?: string; label?: string }>; filters?: { period_days?: number[]; density?: string[] }; finance_dashboard?: FinanceDashboardMobile };
type Tab = 'today' | 'tasks' | 'feed' | 'reviews' | 'progress' | 'operator' | 'more' | 'menu';

type TelegramWebApp = {
  initData?: string;
  initDataUnsafe?: { start_param?: string };
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
  user: { id: 'preview', name: 'Алексей' },
  today_v2_enabled: true,
  selected_scope: { kind: 'business', id: 'preview', name: 'Весёлая расчёска · Центр', business_ids: ['preview'], can_switch: true, parent_scope: { kind: 'network', id: 'network', name: 'Сеть «Весёлая расчёска»' } },
  summary: {
    attention_items: [
      { id: 'reviews_unanswered', title: '50 отзывов ждут ответа', description: 'ЛокалОС собрал их в одну очередь.', count: 50, severity: 'high' },
      { id: 'drafts', title: '12 черновиков готовы', description: 'Нужно проверить тон и подтвердить.', count: 12, severity: 'medium' },
    ],
    metrics: [
      { key: 'map', label: 'На карте', value: 296, source_label: 'Яндекс Карты', updated_at: new Date().toISOString() },
      { key: 'loaded', label: 'В ЛокалОС', value: 164, source_label: 'Отзывы ЛокалОС', updated_at: new Date().toISOString() },
    ],
  },
  catalog: {
    platform: { kind: 'platform', name: 'Вся платформа' },
    networks: [{ id: 'network', name: 'Сеть «Весёлая расчёска»', locations_count: 2 }],
    businesses: [
      { id: 'preview', name: 'Весёлая расчёска · Центр', address: 'Москва, Тверская, 7', network_id: 'network', network_name: 'Сеть «Весёлая расчёска»' },
      { id: 'preview-2', name: 'Весёлая расчёска · Север', address: 'Москва, Лесная, 4', network_id: 'network', network_name: 'Сеть «Весёлая расчёска»' },
    ], total_choices: 3,
  },
  navigation: [
    { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
    { key: 'tasks', label: 'В работе', group: 'primary', status: 'available' },
    { key: 'reviews', label: 'Отзывы', group: 'more', status: 'available' },
    { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' },
    { key: 'progress', label: 'Прогресс', group: 'primary', status: 'available' },
    { key: 'cards', label: 'Карточки', group: 'more', status: 'read_only' },
    { key: 'content', label: 'Контент', group: 'more', status: 'available' },
    { key: 'influencers', label: 'Инфлюенсеры', group: 'more', status: 'available' },
    { key: 'partnerships', label: 'Партнёрства', group: 'more', status: 'available' },
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
  finance: { items: [{ id: 'finance-1', title: 'Стрижка', amount: 2900, transaction_type: 'income', updated_at: new Date().toISOString() }] },
};

const previewFinanceDashboard: FinanceDashboardMobile = {
  period: { start_date: '2026-04-01', end_date: '2026-07-24' },
  kpis: { revenue: 10100000, average_ticket: 2961, operating_profit: 3333000, operating_margin: 0.33, workplace_occupancy: 0.702, idle_workplace_hours: 3147, rebooking_rate: 0.389, no_show_rate: 0.047 },
  statuses: { operating_margin: 'green', workplace_occupancy: 'green', rebooking_rate: 'red' },
  data_quality: { score: 100, missing: [], approximate: [], precise: ['выручка', 'расходы', 'загрузка'] },
  recommendations: [{ code: 'rebooking', target_metric: 'rebooking_rate', title: 'Клиенты уходят без следующей записи', text: 'Добавьте мягкое предложение следующего визита перед выходом клиента.', severity: 'high' }],
  action_impact: { completed_actions_count: 0, deltas: [] },
  period_history: [{ label: 'апр.', period_start: '2026-04-01', period_end: '2026-04-30', revenue: 2850000 }, { label: 'май', period_start: '2026-05-01', period_end: '2026-05-31', revenue: 3250000 }, { label: 'июнь', period_start: '2026-06-01', period_end: '2026-06-30', revenue: 3600000 }, { label: 'июль', period_start: '2026-07-01', period_end: '2026-07-24', revenue: 400000 }],
  services: [{ service_name: 'Женская стрижка', category: 'Стрижки', revenue: 420000, visits_count: 42, avg_price: 10000 }],
  staff: [{ staff_name: 'Анна', role: 'Стилист', revenue: 520000, visits_count: 58, occupancy: 0.76 }],
  workplaces: [{ name: 'Кресло 1', type: 'Кресло', revenue: 520000, occupancy: 0.76, idle_hours: 45 }],
};

const previewToday: TodayPayload = {
  scope: previewBootstrap.selected_scope,
  focus_action: {
    id: 'reviews_unanswered',
    title: 'Ответьте на четыре новых отзыва',
    reason: 'Клиенты уже ждут реакции, а ЛокалОС собрал отзывы в одну очередь.',
    expected_outcome: 'Клиенты увидят, что бизнес внимательно относится к обратной связи.',
    cta_label: 'Открыть отзывы',
    screen: 'reviews',
    count: 4,
  },
  active_work: [{ id: 'work-1', title: 'Обновляет данные карточки', stage: 'Собирает данные Яндекса и 2ГИС', progress: 65, screen: 'cards', business_name: 'Весёлая расчёска' }],
  changes_24h: [{ id: 'change-1', title: 'Загружено новых отзывов: 6', description: 'Отзывы появились в ЛокалОС после последнего сбора данных.', source: 'Отзывы с карт', occurred_at: new Date().toISOString(), screen: 'reviews' }],
  community_pulse: [{ id: 'pulse-1', title: 'Подорожание красителей', description: 'За сутки тема повторилась в 21 сообщении из 3 источников.', message_count: 21, sources_count: 3, source_name: 'Beauty Owners Chat', source_url: 'https://t.me/', last_discussed_at: new Date().toISOString() }],
  completed_results: [{ id: 'result-1', title: 'Подготовлено два черновика публикаций', description: 'Тексты готовы к проверке — публикации ещё не выполнялись.', source: 'Контент ЛокалОС', occurred_at: new Date().toISOString(), screen: 'content' }],
  progress_summary: { completed_milestones: 7, total_milestones: 15, percent: 47 },
  as_of: new Date().toISOString(),
};

const previewProgress: ProgressPayload = {
  status: 'available',
  focus_action: previewToday.focus_action,
  summary: { completed_milestones: 7, total_milestones: 15, active_areas: 4, needs_attention: 2, completed_last_30_days: 5, percent: 47 },
  areas: [
    { key: 'maps', label: 'Карты и репутация', status: 'needs_attention', summary: 'Карточка обновляется, новые отзывы ждут ответа.', problem: 'Без ответа осталось четыре отзыва.', progress: { completed: 3, total: 4 }, milestones: [{ key: 'map-linked', label: 'Карточка подключена', status: 'done', evidence: 'Яндекс и 2ГИС доступны ЛокалОС.' }, { key: 'reviews', label: 'Ответить на новые отзывы', status: 'next' }], action: { cta_label: 'Открыть отзывы', screen: 'reviews' } },
    { key: 'content', label: 'Контент', status: 'in_progress', summary: 'План создан, два черновика готовы.', progress: { completed: 2, total: 3 }, milestones: [{ key: 'plan', label: 'Контент-план создан', status: 'done' }, { key: 'publish', label: 'Подтвердить первую публикацию', status: 'next' }], action: { cta_label: 'Открыть контент', screen: 'content' } },
  ],
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };
const webApp = () => window.Telegram?.WebApp;
const isPreview = () => ['localhost', '127.0.0.1'].includes(window.location.hostname) && new URLSearchParams(window.location.search).get('preview') === '1';

const readJson = readMobileJson;
const scopeQuery = mobileScopeQuery;
const authHeaders = mobileJsonHeaders;
const authOnlyHeaders = mobileAuthHeaders;
const isTab = (value: string | null): value is Tab => Boolean(value && ['today', 'tasks', 'feed', 'reviews', 'progress', 'operator', 'more', 'menu'].includes(value));

export const TelegramControlPage = () => {
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

  useEffect(() => { webApp()?.ready?.(); webApp()?.expand?.(); void loadBootstrap(); }, []);

  useEffect(() => {
    if (!onboardingKey) return;
    const forced = new URLSearchParams(window.location.search).get('onboarding') === '1';
    if (preview && !forced) return;
    let completed = false;
    try { completed = window.localStorage.getItem(onboardingKey) === 'completed'; } catch { completed = false; }
    setShowOnboarding(forced || !completed);
  }, [onboardingKey, preview]);

  useEffect(() => {
    if (!restoredJob?.id || restoredJob.terminal) return;
    const timer = window.setInterval(() => {
      void loadMobileJob(restoredJob.id || '', scope).then((result) => {
        setRestoredJob(result.job || null);
        if (result.job?.terminal) void loadWorkspace();
      }).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [restoredJob?.id, restoredJob?.terminal, scope?.kind, scope?.id]);

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
    const timer = window.setTimeout(() => void loadBootstrap(search.trim(), '', false, true, requestVersion), 250);
    return () => window.clearTimeout(timer);
  }, [initData, picker, pickerNetwork, search]);

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

  useEffect(() => {
    if (!picker || !pickerNetwork?.id) return;
    const requestVersion = networkLocationSearchVersion.current + 1;
    networkLocationSearchVersion.current = requestVersion;
    const timer = window.setTimeout(() => void loadNetworkLocations(pickerNetwork, networkSearch, '', false, requestVersion), 200);
    return () => window.clearTimeout(timer);
  }, [picker, pickerNetwork, networkSearch]);

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

  useEffect(() => { if (tab === 'reviews') void loadReviews(reviewStatus); }, [tab, reviewStatus, reviewSource, reviewRating, reviewLocation, scope?.kind, scope?.id]);

  const loadOperatorHistory = async () => {
    if (preview || !scope?.kind) return;
    const scopeKey = `${scope.kind}:${scope.id || 'all'}`;
    if (historyLoadedFor === scopeKey) return;
    try {
      const params = scopeQuery(scope);
      const result = await fetch(`/api/operator/mobile/operator/history?${params.toString()}`, { headers: authHeaders() }).then(readJson<{ items?: Array<{ id?: string; role?: string; content?: string; status?: string; capability?: string; created_at?: string; result_json?: { mobile_route?: { screen?: string }; approval?: { action_id?: string } } }> }>);
      setMessages((result.items || []).map((item) => ({
        id: item.id,
        role: item.role === 'user' ? 'user' : 'operator',
        text: item.content || '',
        status: item.status,
        capability: item.capability,
        created_at: item.created_at,
        screen: item.result_json?.mobile_route?.screen,
        action_id: item.status === 'approval_required' ? item.result_json?.approval?.action_id : undefined,
      })));
      setHistoryLoadedFor(scopeKey);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить историю.'); }
  };

  useEffect(() => { if (tab === 'operator') void loadOperatorHistory(); }, [tab, scope?.kind, scope?.id]);

  const loadModule = async (moduleKey = module, quietly = false, requestVersion = scopeRequestVersion.current) => {
    if (!moduleKey || preview) return;
    if (!quietly) setModuleLoading(true);
    if (moduleKey === 'company' || moduleKey === 'companies' || moduleKey === 'community_sources') { setModuleLoading(false); setError(''); return; }
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

  useEffect(() => {
    const destination = module || (tab === 'progress' ? 'progress' : '');
    if (!destination) return;
    if (preview) { setModuleData(previewModules[destination] || {}); return; }
    void loadModule(destination);
  }, [module, tab, scope?.kind, scope?.id]);

  useEffect(() => {
    if (tab !== 'today' || !bootstrap?.today_v2_enabled) return;
    const interval = todayData?.active_work?.length ? 20000 : 300000;
    const timer = window.setInterval(() => void loadToday(scope, true, true), interval);
    return () => window.clearInterval(timer);
  }, [tab, bootstrap?.today_v2_enabled, scope?.kind, scope?.id, todayData?.active_work?.length]);

  useEffect(() => {
    if (tab !== 'tasks' || !hasActiveTasks) return;
    const timer = window.setInterval(() => void loadWorkspace(scope), 15000);
    return () => window.clearInterval(timer);
  }, [tab, scope?.kind, scope?.id, hasActiveTasks]);

  useEffect(() => {
    const scopeKey = `${scope?.kind || ''}:${scope?.id || ''}`;
    if (tab !== 'today' || !bootstrap?.today_v2_enabled || !todayData?.as_of || trackedTodayScope.current === scopeKey) return;
    trackedTodayScope.current = scopeKey;
    trackMobileInteraction('today_open');
  }, [tab, bootstrap?.today_v2_enabled, scope?.kind, scope?.id, todayData?.as_of]);

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
    if (requestedEntry?.status === 'read_only' && requestedEntry.reason?.toLowerCase().includes('оплат')) {
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
  }, [bootstrap?.selected_scope?.kind, bootstrap?.selected_scope?.id, bootstrap?.resolved_deep_link?.screen]);

  const openMobileTarget = (screen = 'tasks', targetScope?: { kind?: string; id?: string }) => {
    if (screen === 'influencers') {
      setCommand('Найди локальных авторов для моего бизнеса и подготовь первый вариант сотрудничества');
      setModule('');
      setTab('operator');
      return;
    }
    const destination = screen === 'analytics' || screen === 'finance_import' ? 'finance' : screen;
    const navigationEntry = bootstrap?.navigation?.find((item) => item.key === destination);
    if (navigationEntry?.status === 'read_only' && navigationEntry.reason?.toLowerCase().includes('оплат')) {
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
    else if (direction === 'influencers') {
      setCommand('Найди локальных авторов для моего бизнеса и подготовь первый вариант сотрудничества');
      openMobileTarget('operator');
    }
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

  const askOperator = async (event: FormEvent) => {
    event.preventDefault();
    const text = command.trim();
    if (!text) return;
    if (scope?.kind !== 'business' || !scope.id) { setPicker(true); setError('Для команды выберите одну точку.'); return; }
    setMessages((current) => [...current, { role: 'user', text }]); setCommand(''); setOperatorBusy(true); setTab('operator');
    try {
      const result = await fetch('/api/operator/chat', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ business_id: scope.id, message: text, channel: 'telegram_mini_app' }),
      }).then(readJson<{ operator_result?: { chat_response?: string; summary?: string; status?: string; capability?: string; mobile_route?: { screen?: string }; approval?: { action_id?: string } } }>);
      setMessages((current) => [...current, {
        role: 'operator',
        text: result.operator_result?.chat_response || result.operator_result?.summary || 'Готово. Результат добавлен в задачи.',
        status: result.operator_result?.status,
        capability: result.operator_result?.capability,
        screen: result.operator_result?.mobile_route?.screen,
        action_id: result.operator_result?.approval?.action_id,
      }]);
      await loadWorkspace();
    } catch (requestError) { setMessages((current) => [...current, { role: 'operator', text: requestError instanceof Error ? requestError.message : 'Не смог разобрать запрос.' }]); }
    finally { setOperatorBusy(false); }
  };

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
            {!picker && tab === 'today' ? <>{journeyAction && scope?.kind === 'business' && scope.id ? <div className="px-4 pb-4"><JourneyActionCard action={journeyAction} businessId={scope.id} surface="telegram_mini_app" dark onUpdated={() => void loadJourneyAction(journeyAction.id, scope.id)} /></div> : null}{bootstrap?.today_v2_enabled !== false ? <TodayMobileV2 data={todayData} loading={todayLoading} slowLoading={todaySlowLoading} command={command} setCommand={setCommand} ask={askOperator} openTarget={openMobileTarget} openProgress={() => openMobileTarget(scope?.kind === 'platform' ? 'tasks' : 'progress')} openSources={scope?.kind === 'business' ? () => openMobileTarget('community_sources') : undefined} track={trackMobileInteraction} trackProduct={trackProductEvent} openFinanceImport={() => openMobileTarget('finance_import')} refresh={() => void loadToday(scope, true, true)} /> : <Today summary={summary} tasks={tasks} command={command} setCommand={setCommand} ask={askOperator} openTask={openTask} />}</> : null}
            {!picker && tab === 'tasks' ? <Tasks items={tasks} filter={taskFilter} setFilter={setTaskFilter} openTask={openTask} /> : null}
            {!picker && tab === 'feed' ? <CommunityFeedMobile scope={scope} preview={preview} openSources={scope?.kind === 'business' ? () => openMobileTarget('community_sources') : undefined} /> : null}
            {!picker && tab === 'reviews' ? <Reviews result={reviews} summary={summary} status={reviewStatus} setStatus={setReviewStatus} source={reviewSource} setSource={setReviewSource} rating={reviewRating} setRating={setReviewRating} location={reviewLocation} setLocation={setReviewLocation} selected={selectedReviews} setSelected={setSelectedReviews} loading={reviewsLoading} actionBusy={reviewActionBusy} generate={generateReviewReply} updateDraft={updateReviewDraft} markPublished={markReviewPublished} prepareSelected={() => void prepareSelectedReviews(selectedReviews)} loadMore={() => void loadReviews(reviewStatus, true)} /> : null}
            {!picker && tab === 'progress' ? <Screen title="Прогресс" subtitle="Выполненные шаги, текущие проблемы и одно следующее действие."><ProgressMobileModule data={progressData} loading={progressLoading} openTarget={openMobileTarget} track={trackMobileInteraction} trackProduct={trackProductEvent} /></Screen> : null}
            {!picker && tab === 'operator' ? <Operator messages={messages} busy={operatorBusy} actionBusy={operatorActionBusy} command={command} setCommand={setCommand} ask={askOperator} resolveAction={resolveOperatorAction} openScreen={openMobileTarget} /> : null}
            {!picker && tab === 'more' && !module ? <More navigation={visibleNavigation} onOpen={openMobileTarget} openProgress={() => openMobileTarget('progress')} onLocked={setPaywall} restartTour={() => setShowOnboarding(true)} /> : null}
            {!picker && tab === 'menu' ? <UtilityMenu navigation={visibleNavigation} onOpen={openMobileTarget} /> : null}
            {!picker && tab === 'more' && module ? <ModuleScreen module={module} focusItemId={deepLinkItemId} scope={scope} data={moduleData} loading={moduleLoading} progressData={progressData} progressLoading={progressLoading} saving={moduleSaving} actionBusy={moduleActionBusy} saveNotifications={saveNotifications} updateService={updateService} generateContentDraft={generateContentDraft} updateContentItem={updateContentItem} reload={() => loadModule(module)} openTarget={openMobileTarget} track={trackMobileInteraction} trackProduct={trackProductEvent} openTasks={() => { setModule(''); setTab('tasks'); }} requestCrm={createCrmRequest} back={() => setModule('')} /> : null}
          </motion.div>
        </AnimatePresence>
      </MobileShell>
    </ScopeProvider>
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
  const publishedAt = review.published_at ? new Date(review.published_at) : null;
  const publishedAtLabel = publishedAt && !Number.isNaN(publishedAt.getTime())
    ? publishedAt.toLocaleString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'дата не указана источником';
  return <article className={`mb-3 rounded-[24px] p-4 ring-1 ring-inset transition-[background-color,box-shadow] ${selected ? 'bg-primary/[0.075] ring-primary/30' : 'bg-white/[0.04] ring-white/[0.07]'}`}><div className="flex items-start gap-3"><button type="button" aria-label={selected ? 'Убрать из выбранных' : 'Выбрать отзыв'} aria-pressed={selected} onClick={toggle} className={`grid h-11 w-11 shrink-0 place-items-center rounded-[14px] text-sm font-bold active:scale-[0.96] ${selected ? 'bg-primary text-white' : 'bg-amber-400/10 text-amber-300'}`}>{selected ? <Check className="h-5 w-5" /> : review.rating || '—'}</button><div className="min-w-0 flex-1"><b className="block truncate">{review.author_name || 'Гость'}</b><small className="block truncate text-zinc-600">{[review.source, review.location_name].filter(Boolean).join(' · ')}</small><small className="mt-1 block text-[11px] font-medium text-zinc-400">Отзыв от {publishedAtLabel}</small></div></div><p className="mt-4 whitespace-pre-wrap text-pretty text-sm leading-6 text-zinc-300">{review.text || 'Клиент оставил оценку без текста.'}</p>{review.response_text ? <ResponseBox label="Опубликованный ответ" text={review.response_text} /> : review.reply_draft_text ? <div className="mt-4 rounded-[18px] bg-black/20 p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex min-h-11 items-center justify-between"><small className="font-semibold text-primary">Черновик ЛокалОС</small><div className="flex"><button type="button" onClick={() => setEditing((value) => !value)} className="min-h-11 px-3 text-xs font-semibold text-zinc-400">{editing ? 'Отмена' : 'Изменить'}</button><button type="button" aria-label="Скопировать" onClick={() => void navigator.clipboard.writeText(draftText)} className="grid h-11 w-11 place-items-center text-zinc-500 active:scale-[0.96]"><Copy className="h-4 w-4" /></button></div></div>{editing ? <><textarea value={draftText} onChange={(event) => setDraftText(event.target.value)} className="min-h-32 w-full resize-none rounded-2xl bg-white/[0.04] p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><button disabled={busy} onClick={() => void updateDraft(review, draftText)} className="mt-2 min-h-11 w-full rounded-2xl bg-primary text-sm font-semibold disabled:opacity-50">{busy ? 'Сохраняем…' : 'Сохранить черновик'}</button></> : <><p className="text-sm leading-6 text-zinc-300">{draftText}</p><button type="button" disabled={busy} onClick={() => void markPublished(review)} className="mt-3 min-h-11 w-full rounded-2xl bg-white/[0.045] text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96] disabled:opacity-50">{busy ? 'Сохраняем…' : 'Я опубликовал ответ вручную'}</button></>}</div> : <button disabled={busy} onClick={() => void generate(review, false)} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-primary/12 text-sm font-semibold text-primary ring-1 ring-inset ring-primary/20 active:scale-[0.96] disabled:opacity-50"><WandSparkles className="h-4 w-4" />{busy ? 'Проверяем…' : 'Подготовить ответ'}</button>}</article>;
};

const MetricMini = ({ label, value, accent = false }: { label: string; value?: string | number | null; accent?: boolean }) => <div className="min-w-0 px-1 py-1"><b className={`block truncate text-xl tabular-nums ${accent ? 'text-primary' : 'text-zinc-200'}`}>{value ?? '—'}</b><small className="block truncate text-[10px] text-zinc-600">{label}</small></div>;
const FilterSelect = ({ label, value, setValue, options }: { label: string; value: string; setValue: (value: string) => void; options: string[][] }) => <label className="block text-[11px] text-zinc-600"><span className="mb-1 block px-1">{label}</span><select value={value} onChange={(event) => setValue(event.target.value)} className="min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-xs text-zinc-300 outline-none ring-1 ring-inset ring-white/[0.07]"><option value="">Все</option>{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label>;

const ResponseBox = ({ label, text }: { label: string; text: string }) => <div className="mt-4 rounded-[18px] bg-black/20 p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex items-center justify-between"><small className="font-semibold text-primary">{label}</small><button type="button" aria-label="Скопировать" onClick={() => void navigator.clipboard.writeText(text)} className="grid h-11 w-11 place-items-center text-zinc-500 active:scale-[0.96]"><Copy className="h-4 w-4" /></button></div><p className="text-sm leading-6 text-zinc-300">{text}</p></div>;

const Operator = ({ messages, busy, actionBusy, command, setCommand, ask, resolveAction, openScreen }: {
  messages: OperatorMessage[];
  busy: boolean;
  actionBusy: { actionId: string; decision: OperatorActionDecision } | null;
  command: string;
  setCommand: (value: string) => void;
  ask: (event: FormEvent) => void;
  resolveAction: (actionId: string, decision: OperatorActionDecision) => void;
  openScreen: (screen: string) => void;
}) => <Screen title="Оператор" subtitle="Напишите задачу обычными словами. Результат появится здесь или в нужном разделе.">
  <div className="min-h-[42vh] space-y-3">
    {messages.length ? messages.map((message, index) => {
      const resolving = Boolean(message.action_id && actionBusy?.actionId === message.action_id);
      return <div key={message.id || `${message.role}-${index}`} className={`max-w-[88%] rounded-[20px] px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'ml-auto bg-primary text-white' : 'bg-white/[0.05] text-zinc-300 ring-1 ring-inset ring-white/[0.07]'}`}>
        <p className="whitespace-pre-wrap text-pretty">{message.text}</p>
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
  <form onSubmit={ask} className="sticky bottom-24 mt-4 flex gap-2 rounded-[20px] bg-zinc-900 p-2 ring-1 ring-inset ring-white/[0.08]"><input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Напишите задачу" className="min-h-12 min-w-0 flex-1 bg-transparent px-3 text-sm outline-none placeholder:text-zinc-700" /><button aria-label="Отправить задачу" className="grid h-12 w-12 place-items-center rounded-2xl bg-primary transition-transform active:scale-[0.96]"><Send className="h-4 w-4" /></button></form>
</Screen>;

const SubscriptionPaywall = ({ item, close }: { item: NavigationItem; close: () => void }) => <div className="fixed inset-0 z-50 flex items-end bg-black/70 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Раздел доступен после оплаты"><div className="w-full rounded-[28px] bg-zinc-900 p-5 shadow-2xl ring-1 ring-inset ring-white/[0.08]"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/15 text-primary"><CreditCard className="h-5 w-5" /></span><h2 className="mt-4 text-xl font-semibold">{item.label} доступен после оплаты</h2><p className="mt-2 text-sm leading-6 text-zinc-500">{item.reason || 'Подключите тариф для выбранной точки.'}</p><a href="/dashboard/billing" className="mt-5 flex min-h-12 w-full items-center justify-center rounded-2xl bg-primary px-4 text-sm font-semibold text-white">Перейти к оплате</a><button type="button" onClick={close} className="mt-2 min-h-12 w-full rounded-2xl bg-white/[0.04] text-sm font-semibold text-zinc-400">Закрыть</button></div></div>;

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
  finance: ['Финансы', 'Выручка, прибыль, средний чек, загрузка и динамика.'], finance_import: ['Загрузить финансовую сводку', 'Сначала проверьте распознанные данные. В аналитику они попадут только после подтверждения.'], analytics: ['Финансы', 'Выручка, заказы и динамика по выбранному периоду.'], partnerships: ['Партнёрства', 'Кандидаты, предложения, отправки, ответы и отчёт.'], company: ['Моя компания', 'Локации, карты, контакты, публичные услуги, аудиты и история.'], companies: ['Компании', 'Клиенты, лиды, партнёры, локации и история публичных данных.'], agents: ['Работа ЛокалОС', 'Запуски, текущие этапы, результаты и ошибки.'], settings: ['Настройки и подключения', 'Уведомления, источники, тариф и доступ.'], diagnostics: ['Диагностика', 'Ошибки парсеров, интеграций и фоновых задач.'],
  community_sources: ['Источники Ленты', 'Публичные Telegram-каналы и открытые группы, из которых ЛокалОС собирает ленту и главные темы.'],
};

type ModuleScreenProps = {
  module: string; focusItemId?: string; scope?: MobileScope; data: ModuleData; loading: boolean; progressData?: ProgressPayload | null; progressLoading: boolean; saving: boolean; actionBusy: string;
  saveNotifications: (preferences: NotificationPreferences) => Promise<void>;
  updateService: (item: ModuleItem, values: { name: string; description: string; price: string; category: string }) => Promise<void>;
  generateContentDraft: (item: ModuleItem) => Promise<void>;
  updateContentItem: (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void>;
  reload: () => Promise<void>;
  openTarget: (screen?: string, targetScope?: { kind?: string; id?: string }) => void;
  track: (eventName: string, target?: string) => void;
  trackProduct: (eventName: 'mission_open' | 'statistics_flow_opened' | 'statistics_preview_created' | 'statistics_preview_confirmed' | 'crm_request_created', objectId?: string) => void;
  openTasks: () => void;
  requestCrm: (values: { crmName: string; crmUrl: string; contact: string; comment: string }) => Promise<void>;
  back: () => void;
};

const ModuleScreen = ({ module, focusItemId, scope, data, loading, progressData, progressLoading, saving, actionBusy, saveNotifications, updateService, generateContentDraft, updateContentItem, reload, openTarget, track, trackProduct, openTasks, requestCrm, back }: ModuleScreenProps) => {
  const content = moduleNames[module] || ['Раздел', 'Данные и доступные действия.'];
  return <Screen title={content[0]} subtitle={content[1]} action={<button aria-label="Назад" onClick={back} className="grid h-11 w-11 place-items-center rounded-2xl bg-white/[0.05] ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"><ArrowLeft className="h-4 w-4" /></button>}>
    {module === 'companies' || module === 'company' ? <CompaniesMobileModule businessId={module === 'company' && scope?.kind === 'business' ? scope.id : null} /> : module === 'community_sources' ? <CommunitySourcesMobileModule businessId={scope?.kind === 'business' ? scope.id : null} /> : module === 'progress' ? <ProgressMobileModule data={progressData} loading={progressLoading} openTarget={openTarget} track={track} trackProduct={trackProduct} /> : loading ? <ReviewSkeleton /> : module === 'settings' ? <NotificationSettings preferences={data.preferences || {}} saving={saving} save={saveNotifications} /> : module === 'cards' ? <CardsModule scope={scope} items={data.items || []} reload={reload} /> : module === 'content' ? <ContentModule focusItemId={focusItemId} scope={scope} items={data.items || []} filters={data.filters} busy={actionBusy} generate={generateContentDraft} update={updateContentItem} reload={reload} /> : module === 'services' ? <ServicesModule focusItemId={focusItemId} scope={scope} items={data.items || []} busy={actionBusy} update={updateService} reload={reload} /> : module === 'finance' || module === 'finance_import' ? <FinanceModule scope={scope} items={data.items || []} reload={reload} openTasks={openTasks} requestCrm={requestCrm} initialSection={module === 'finance_import' ? 'import' : 'overview'} trackProduct={trackProduct} /> : module === 'partnerships' ? <PartnershipsMobileModule scope={scope} /> : module === 'agents' ? <AgentsMobileModule items={data.items || []} scope={scope} reload={reload} canRun={Boolean(data.available_actions?.some((action) => action.key === 'agents.run'))} /> : module === 'diagnostics' ? <DiagnosticsMobileModule items={data.items || []} scope={scope} reload={reload} /> : module === 'analytics' ? <AnalyticsModule items={data.items || []} /> : <ModuleUnavailable />}
  </Screen>;
};

const providerName = (value: string) => value.includes('2gis') || value.includes('two') || value.includes('2_gis') ? '2ГИС' : value.includes('yandex') ? 'Яндекс' : value;
const dateLabel = (value?: string) => {
  if (!value) return 'дата неизвестна';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'дата неизвестна'
    : date.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
};
const contentDateKey = (value?: string) => {
  const raw = String(value || '').trim();
  const match = raw.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match?.[1]) {
    const [year, month, day] = match[1].split('-').map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    if (parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day) return match[1];
    return '';
  }
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

const CardsModule = ({ scope, items, reload }: { scope?: MobileScope; items: ModuleItem[]; reload: () => Promise<void> }) => {
  const [editing, setEditing] = useState('');
  const [interval, setInterval] = useState('24');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<MobileActionPreview | null>(null);
  const [refreshPreview, setRefreshPreview] = useState<MobileActionPreview | null>(null);
  const [activeJob, setActiveJob] = useState<MobileJob | null>(null);
  const saveSchedule = async (item: ModuleItem, enabled: boolean) => {
    setBusy(item.id || 'schedule');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'cards.schedule.update', input: { business_id: item.business_id || item.id, enabled, interval_hours: Number(interval) } }) }).then(readJson<{ preview?: MobileActionPreview }>);
      setPreview(result.preview || null); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить график.'); }
    finally { setBusy(''); }
  };
  const confirmSchedule = async () => {
    if (!preview?.action_id) return;
    setBusy(preview.action_id);
    try {
      await fetch(`/api/operator/mobile/actions/${preview.action_id}/confirm`, { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }) }).then(readJson);
      setPreview(null); await reload(); setEditing(''); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить график.'); }
    finally { setBusy(''); }
  };
  const prepareRefresh = async (item: ModuleItem) => {
    setBusy(`refresh:${item.id || ''}`); setError('');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'cards.refresh', input: { business_id: item.business_id || item.id, source: 'all' } }) }).then(readJson<{ preview?: MobileActionPreview }>);
      setRefreshPreview(result.preview || null);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить обновление.'); }
    finally { setBusy(''); }
  };
  const confirmRefresh = async () => {
    if (!refreshPreview?.action_id) return;
    setBusy(refreshPreview.action_id); setError('');
    try {
      const result = await confirmMobileAction(refreshPreview.action_id, scope);
      const jobId = String(result.operator_result?.job_id || '');
      setRefreshPreview(null);
      if (jobId) {
        const loaded = await loadMobileJob(jobId, scope);
        setActiveJob(loaded.job || null);
      }
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось запустить обновление.'); }
    finally { setBusy(''); }
  };
  useEffect(() => {
    if (!activeJob?.id || activeJob.terminal) return;
    const timer = window.setInterval(() => {
      void loadMobileJob(activeJob.id || '', scope).then((result) => {
        setActiveJob(result.job || null);
        if (result.job?.status === 'completed') void reload();
      }).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeJob?.id, activeJob?.terminal, scope?.kind, scope?.id]);
  return <div>
    <div className="mb-4 rounded-[22px] bg-primary/[0.08] p-4 ring-1 ring-inset ring-primary/15"><div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-primary/15 text-primary"><RefreshCw className="h-5 w-5" /></span><div><b className="block text-sm">Данные из Яндекса и 2ГИС</b><p className="mt-1 text-xs leading-5 text-zinc-500">ЛокалОС проверяет карточки по вашему графику и показывает, когда данные были собраны в последний раз.</p></div></div></div>
    {error ? <InlineError text={error} /> : null}
    {items.length ? <div className="space-y-2">{items.map((item) => <article key={item.id} className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><b className="block text-sm leading-5">{item.title || item.business_name}</b><small className="mt-1 block truncate text-zinc-600">{item.subtitle || item.business_name}</small></div><StatusPill value={item.status} /></div><div className="mt-4 flex flex-wrap gap-2">{(item.provider_sources || []).filter(Boolean).map((source) => <span key={source} className="rounded-full bg-white/[0.05] px-3 py-1.5 text-[11px] font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07]">{providerName(source)}</span>)}</div><div className="mt-4 grid grid-cols-3 gap-2 text-center"><MetricMini label="Рейтинг" value={item.rating} /><MetricMini label="Отзывы" value={item.reviews_count} /><MetricMini label="SEO" value={item.seo_score} /></div><div className="mt-4 rounded-[16px] bg-black/20 p-3 text-xs leading-5 ring-1 ring-inset ring-white/[0.05]"><p className="text-zinc-400">Последняя проверка: <b className="font-medium text-zinc-200">{dateLabel(item.parse_updated_at || item.review_sync_last_run_at || item.updated_at)}</b></p><p className="mt-1 text-zinc-400">{item.review_sync_enabled ? <>Следующее обновление: <b className="font-medium text-zinc-200">{dateLabel(item.review_sync_next_run_at)}</b></> : 'Автоматическое обновление выключено'}</p><p className="mt-1 text-zinc-600">Одно обновление — {item.refresh_cost_credits || 10} кредитов</p></div>{editing === item.id ? <div className="mt-3 rounded-[18px] bg-white/[0.035] p-3 ring-1 ring-inset ring-white/[0.06]"><label className="text-[11px] text-zinc-500">Как часто проверять<select value={interval} onChange={(event) => setInterval(event.target.value)} className="mt-2 min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-sm text-zinc-200 ring-1 ring-inset ring-white/[0.07]"><option value="24">Каждый день</option><option value="48">Раз в 2 дня</option><option value="168">Раз в неделю</option><option value="336">Раз в 2 недели</option></select></label><p className="mt-3 text-pretty text-[11px] leading-5 text-zinc-500">Чем чаще проверка, тем быстрее ЛокалОС заметит новые отзывы и изменения в карточке. Но кредиты будут расходоваться быстрее: при этом графике — до <b className="font-semibold tabular-nums text-zinc-300">{monthlyRefreshCost(interval, item.refresh_cost_credits || 10)} кредитов за 30 дней</b>.</p><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" disabled={busy === item.id} onClick={() => void saveSchedule(item, false)} className="min-h-11 rounded-[14px] bg-white/[0.05] text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Выключить</button><button type="button" disabled={busy === item.id} onClick={() => void saveSchedule(item, true)} className="min-h-11 rounded-[14px] bg-primary text-xs font-semibold active:scale-[0.96]">{busy === item.id ? 'Сохраняем…' : 'Сохранить график'}</button></div></div> : <div className="mt-3 grid grid-cols-2 gap-2"><button type="button" onClick={() => { setInterval(String(item.review_sync_interval_hours || 24)); setEditing(item.id || 'schedule'); }} className="min-h-11 rounded-[14px] bg-white/[0.05] px-3 text-xs font-semibold ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]"><Settings className="mr-1.5 inline h-4 w-4" />График</button><button type="button" disabled={Boolean(busy)} onClick={() => void prepareRefresh(item)} className="min-h-11 rounded-[14px] bg-primary px-3 text-xs font-semibold text-white transition-transform active:scale-[0.96] disabled:opacity-50"><RefreshCw className="mr-1.5 inline h-4 w-4" />Обновить</button></div>}</article>)}</div> : <Empty icon={MapPinned} title="Карточки не подключены" text="Добавьте ссылки на Яндекс и 2ГИС в настройках бизнеса — после этого ЛокалОС начнёт следить за обновлениями." />}
    <ActionPreviewSheet preview={preview} busy={Boolean(busy)} confirmLabel="Сохранить график" onCancel={() => setPreview(null)} onConfirm={() => void confirmSchedule()} />
    <ActionPreviewSheet preview={refreshPreview} busy={Boolean(busy)} confirmLabel="Обновить карточки" onCancel={() => setRefreshPreview(null)} onConfirm={() => void confirmRefresh()} />
    <JobProgressSheet job={activeJob} onClose={() => { setActiveJob(null); if (activeJob?.status === 'completed') void reload(); }} />
  </div>;
};

const ContentModule = ({ focusItemId, scope, items, filters, busy, generate, update, reload }: { focusItemId?: string; scope?: MobileScope; items: ModuleItem[]; filters?: ModuleData['filters']; busy: string; generate: (item: ModuleItem) => Promise<void>; update: (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void>; reload: () => Promise<void> }) => {
  const [editing, setEditing] = useState('');
  const [contentSection, setContentSection] = useState('calendar');
  const [generating, setGenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [planAction, setPlanAction] = useState('');
  const [error, setError] = useState('');
  const [deletePreview, setDeletePreview] = useState<MobileActionPreview | null>(null);
  const [generatePreview, setGeneratePreview] = useState<MobileActionPreview | null>(null);
  const [draftPreview, setDraftPreview] = useState<MobileActionPreview | null>(null);
  const [draftItem, setDraftItem] = useState<ModuleItem | null>(null);
  const [activeJob, setActiveJob] = useState<MobileJob | null>(null);
  const [jobBusy, setJobBusy] = useState(false);
  const allowedPeriods = (filters?.period_days || [14, 30]).filter((value) => Number.isFinite(value) && value > 0);
  const [periodDays, setPeriodDays] = useState(() => allowedPeriods.includes(30) ? 30 : allowedPeriods[0] || 30);
  const [density, setDensity] = useState('standard');
  const calendarRef = useRef<HTMLDivElement | null>(null);
  const postsRef = useRef<HTMLDivElement | null>(null);
  const planTitle = items.find((item) => item.plan_title)?.plan_title;
  const planId = items.find((item) => item.plan_id)?.plan_id;
  useEffect(() => {
    if (!focusItemId || !items.some((item) => item.id === focusItemId)) return;
    setContentSection('posts');
    setEditing(focusItemId);
    window.requestAnimationFrame(() => document.getElementById(`content-item-${focusItemId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }, [focusItemId, items]);
  const scrollTo = (section: 'calendar' | 'posts') => {
    setContentSection(section);
    const target = section === 'calendar' ? calendarRef.current : postsRef.current;
    window.requestAnimationFrame(() => target?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };
  const scrollToDate = (date: string) => {
    setContentSection('posts');
    window.requestAnimationFrame(() => document.getElementById(`content-day-${date}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };
  const prepareGeneratePlan = async () => {
    setGenerating(true); setError('');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'content.plan.generate', input: { business_id: scope?.kind === 'business' ? scope.id : null, period_days: periodDays, density } }) }).then(readJson<{ preview?: MobileActionPreview }>);
      setGeneratePreview(result.preview || null);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось подготовить план.'); }
    finally { setGenerating(false); }
  };
  const confirmGeneratePlan = async () => {
    if (!generatePreview?.action_id) return;
    setGenerating(true); setError('');
    try {
      const result = await confirmMobileAction(generatePreview.action_id, scope);
      const job = result.operator_result?.job;
      const jobId = String(result.operator_result?.job_id || job?.id || '');
      setGeneratePreview(null);
      if (job) setActiveJob(job);
      else if (jobId) {
        const loaded = await loadMobileJob(jobId, scope);
        setActiveJob(loaded.job || null);
      }
      setPlanAction('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось запустить сборку плана.'); }
    finally { setGenerating(false); }
  };
  const prepareDraft = async (item: ModuleItem) => {
    if (!item.id) return;
    if (item.id.startsWith('content-')) { await generate(item); return; }
    setDraftItem(item); setError('');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'content.item.generate', input: { item_id: item.id } }) }).then(readJson<{ preview?: MobileActionPreview }>);
      setDraftPreview(result.preview || null);
    } catch (requestError) { setDraftItem(null); setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить генерацию текста.'); }
  };
  const confirmDraft = async () => {
    if (!draftPreview?.action_id || !draftItem?.id) return;
    setJobBusy(true); setError('');
    try {
      const result = await confirmMobileAction(draftPreview.action_id, scope);
      const job = result.operator_result?.job;
      const jobId = String(result.operator_result?.job_id || job?.id || '');
      setDraftPreview(null);
      if (job) setActiveJob(job);
      else if (jobId) {
        const loaded = await loadMobileJob(jobId, scope);
        setActiveJob(loaded.job || null);
      }
      setContentSection('posts');
      setEditing(draftItem.id);
      setDraftItem(null);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось запустить подготовку текста.'); }
    finally { setJobBusy(false); }
  };
  useEffect(() => {
    if (!activeJob?.id || activeJob.terminal) return;
    const timer = window.setInterval(() => {
      void loadMobileJob(activeJob.id || '', scope).then((result) => {
        const nextJob = result.job || null;
        setActiveJob(nextJob);
        if (nextJob?.status === 'completed') void reload();
      }).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeJob?.id, activeJob?.terminal, scope?.kind, scope?.id]);
  const retryJob = async () => {
    if (!activeJob?.id) return;
    setJobBusy(true);
    try { const result = await retryMobileJob(activeJob.id, scope); setActiveJob(result.job || null); setError(''); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось повторить задачу.'); }
    finally { setJobBusy(false); }
  };
  const cancelJob = async () => {
    if (!activeJob?.id) return;
    setJobBusy(true);
    try { const result = await cancelMobileJob(activeJob.id, scope); setActiveJob(result.job || null); setError(''); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось остановить задачу.'); }
    finally { setJobBusy(false); }
  };
  const prepareDeletePlan = async () => { if (!planId) return; setDeleting(true); try { const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'content.plan.delete', input: { plan_id: planId, business_id: scope?.kind === 'business' ? scope.id : null } }) }).then(readJson<{ preview?: MobileActionPreview }>); setDeletePreview(result.preview || null); setPlanAction(''); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить удаление плана.'); } finally { setDeleting(false); } };
  const confirmDeletePlan = async () => { if (!deletePreview?.action_id) return; setDeleting(true); try { await fetch(`/api/operator/mobile/actions/${deletePreview.action_id}/confirm`, { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }) }).then(readJson); setDeletePreview(null); await reload(); setPlanAction(''); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось удалить план.'); } finally { setDeleting(false); } };
  return <><AnimatePresence initial={false} mode="wait">
    <motion.div key="content" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring}>
      {planTitle ? <section className="mb-3 rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><small className="text-zinc-600">Текущий контент-план</small><b className="mt-1 block text-balance text-base">{planTitle}</b><p className="mt-2 text-pretty text-xs text-zinc-500"><span className="tabular-nums">{items.length}</span> публикаций{items[0]?.plan_period_days ? <> · <span className="tabular-nums">{items[0].plan_period_days}</span> дней</> : null}</p></div><button type="button" aria-label="Дополнительные действия с планом" aria-expanded={planAction === 'menu'} onClick={() => setPlanAction(planAction === 'menu' ? '' : 'menu')} className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-white/[0.05] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]"><CircleEllipsis className="h-5 w-5" /></button></div><div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto] gap-2"><button type="button" onClick={() => { setEditing(''); scrollTo('posts'); }} className="flex min-h-11 items-center justify-center gap-2 rounded-[14px] bg-primary px-3 text-xs font-semibold text-white shadow-[0_10px_24px_rgba(255,92,51,0.2)] transition-transform active:scale-[0.96]"><Pencil className="h-4 w-4" />Редактировать публикации</button><button type="button" onClick={() => setPlanAction('new')} className="min-h-11 rounded-[14px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]">Новый план</button></div>{planAction === 'menu' ? <div className="mt-3"><button type="button" disabled={deleting} onClick={() => void prepareDeletePlan()} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-rose-500/[0.08] px-3 text-xs font-semibold text-rose-300 ring-1 ring-inset ring-rose-400/15 transition-transform active:scale-[0.96] disabled:opacity-50">{deleting ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Trash2 className="h-4 w-4" />}{deleting ? 'Проверяем…' : 'Удалить текущий план'}</button></div> : null}</section> : null}
      {error ? <InlineError text={error} /> : null}
      {(!items.length || planAction === 'new') && scope?.kind === 'business' ? <ContentPlanSetup periods={allowedPeriods} periodDays={periodDays} setPeriodDays={setPeriodDays} density={density} setDensity={setDensity} existingPlan={Boolean(items.length)} cancel={items.length ? () => setPlanAction('') : undefined} generate={() => void prepareGeneratePlan()} /> : null}
      {scope?.kind !== 'business' && !items.length ? <Empty icon={Building2} title="Выберите одну точку" text="Сеть можно анализировать целиком, но календарь создаётся для конкретного бизнеса." /> : null}
      {items.length && planAction !== 'new' ? <><div role="navigation" aria-label="Разделы контент-плана" className="sticky top-2 z-10 mb-3 grid grid-cols-2 rounded-[20px] bg-zinc-900/90 p-1 shadow-[0_12px_38px_rgba(0,0,0,0.34)] ring-1 ring-inset ring-white/[0.08] backdrop-blur-xl"><button type="button" aria-current={contentSection === 'calendar' ? 'page' : undefined} onClick={() => scrollTo('calendar')} className={`min-h-11 rounded-[16px] text-sm font-semibold transition-[background-color,color,transform,box-shadow] active:scale-[0.96] ${contentSection === 'calendar' ? 'bg-white/[0.1] text-white shadow-[0_4px_14px_rgba(0,0,0,0.24)]' : 'text-zinc-500'}`}>Календарь</button><button type="button" aria-current={contentSection === 'posts' ? 'page' : undefined} onClick={() => scrollTo('posts')} className={`min-h-11 rounded-[16px] text-sm font-semibold transition-[background-color,color,transform,box-shadow] active:scale-[0.96] ${contentSection === 'posts' ? 'bg-white/[0.1] text-white shadow-[0_4px_14px_rgba(0,0,0,0.24)]' : 'text-zinc-500'}`}>Посты <span className="ml-1 tabular-nums text-[11px] opacity-60">{items.length}</span></button></div><div ref={calendarRef} className="scroll-mt-20"><ContentCalendar items={items} openDate={scrollToDate} /></div><ContentPostList postsRef={postsRef} items={items} editing={editing} busy={busy} setEditing={setEditing} generate={prepareDraft} update={update} /></> : null}
    </motion.div>
  </AnimatePresence><ActionPreviewSheet preview={deletePreview} busy={deleting} confirmLabel="Удалить план" onCancel={() => setDeletePreview(null)} onConfirm={() => void confirmDeletePlan()} /><ActionPreviewSheet preview={generatePreview} busy={generating} confirmLabel="Собрать план" onCancel={() => setGeneratePreview(null)} onConfirm={() => void confirmGeneratePlan()} /><ActionPreviewSheet preview={draftPreview} busy={jobBusy} confirmLabel="Создать текст" onCancel={() => { setDraftPreview(null); setDraftItem(null); }} onConfirm={() => void confirmDraft()} /><JobProgressSheet job={activeJob} busy={jobBusy} onClose={() => { setActiveJob(null); if (activeJob?.status === 'completed') void reload(); }} onRetry={() => void retryJob()} onCancel={() => void cancelJob()} /></>;
};

const ContentPlanSetup = ({ periods, periodDays, setPeriodDays, density, setDensity, existingPlan, cancel, generate }: { periods: number[]; periodDays: number; setPeriodDays: (value: number) => void; density: string; setDensity: (value: string) => void; existingPlan: boolean; cancel?: () => void; generate: () => void }) => {
  const weekly = density === 'light' ? 1 : density === 'active' ? 3 : 2;
  const estimate = Math.max(4, Math.round(periodDays / 7 * weekly));
  return <section className="mb-4 rounded-[26px] bg-gradient-to-b from-primary/[0.09] to-white/[0.035] p-4 shadow-[0_18px_60px_rgba(0,0,0,0.24)] ring-1 ring-inset ring-primary/15"><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/15 text-primary"><WandSparkles className="h-5 w-5" /></span><div><h2 className="text-balance text-base font-semibold">{existingPlan ? 'Настройте новый план' : 'ЛокалОС соберёт план за вас'}</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">Выберите горизонт и темп. Мы сверим услуги, спрос и карточку, затем расставим темы по календарю.</p></div></div><div className="mt-5"><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-zinc-600">Период</p><div className="grid grid-flow-col auto-cols-fr gap-2">{periods.map((days) => <button type="button" key={days} aria-pressed={periodDays === days} onClick={() => setPeriodDays(days)} className={`min-h-12 rounded-[15px] px-3 text-sm font-semibold tabular-nums ring-1 ring-inset transition-[background-color,color,transform,box-shadow] active:scale-[0.96] ${periodDays === days ? 'bg-primary text-white shadow-[0_10px_26px_rgba(255,92,51,0.2)] ring-primary' : 'bg-black/20 text-zinc-400 ring-white/[0.07]'}`}>{days} дней</button>)}</div></div><div className="mt-4"><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-zinc-600">Темп публикаций</p><div className="grid grid-cols-3 gap-2">{[['light', '1 в неделю'], ['standard', '2 в неделю'], ['active', '3 в неделю']].map(([key, label]) => <button type="button" key={key} aria-pressed={density === key} onClick={() => setDensity(key)} className={`min-h-12 rounded-[15px] px-2 text-[11px] font-semibold ring-1 ring-inset transition-[background-color,color,transform] active:scale-[0.96] ${density === key ? 'bg-white/[0.1] text-white ring-white/15' : 'bg-black/15 text-zinc-600 ring-white/[0.06]'}`}>{label}</button>)}</div></div><div className="mt-4 flex items-center justify-between rounded-[16px] bg-black/20 px-3 py-3 ring-1 ring-inset ring-white/[0.05]"><span className="text-xs text-zinc-500">Будет подготовлено</span><b className="text-sm tabular-nums text-zinc-200">около {estimate} публикаций</b></div><p className="mt-3 text-pretty text-[11px] leading-5 text-zinc-600">Ничего не публикуется автоматически. Сначала вы увидите календарь и сможете изменить каждую тему.</p><div className={`mt-4 grid gap-2 ${cancel ? 'grid-cols-[auto_minmax(0,1fr)]' : 'grid-cols-1'}`}>{cancel ? <button type="button" onClick={cancel} className="min-h-12 rounded-[16px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]">Отмена</button> : null}<button type="button" onClick={generate} className="flex min-h-12 items-center justify-center gap-2 rounded-[16px] bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96]"><WandSparkles className="h-4 w-4" />Собрать план на {periodDays} дней</button></div></section>;
};

const calendarMonthStart = (items: ModuleItem[]) => {
  const firstDate = items.map((item) => contentDateKey(item.scheduled_for)).filter(Boolean).sort()[0];
  const date = firstDate ? new Date(`${firstDate}T12:00:00`) : new Date();
  return new Date(date.getFullYear(), date.getMonth(), 1);
};

const calendarKey = (year: number, month: number, day: number) => [year, String(month + 1).padStart(2, '0'), String(day).padStart(2, '0')].join('-');

const ContentCalendar = ({ items, openDate }: { items: ModuleItem[]; openDate: (date: string) => void }) => {
  const [month, setMonth] = useState(() => calendarMonthStart(items));
  const [selectedDate, setSelectedDate] = useState(() => items.map((item) => contentDateKey(item.scheduled_for)).filter(Boolean).sort()[0] || '');
  const itemsByDate = useMemo(() => items.reduce<Record<string, ModuleItem[]>>((result, item) => {
    const key = contentDateKey(item.scheduled_for);
    if (key) result[key] = [...(result[key] || []), item];
    return result;
  }, {}), [items]);
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  const firstWeekday = (new Date(year, monthIndex, 1).getDay() + 6) % 7;
  const dayCount = new Date(year, monthIndex + 1, 0).getDate();
  const cellCount = Math.ceil((firstWeekday + dayCount) / 7) * 7;
  const todayKey = contentDateKey(new Date().toISOString());
  const moveMonth = (offset: number) => setMonth(new Date(year, monthIndex + offset, 1));
  return <section className="rounded-[26px] bg-white/[0.04] p-4 shadow-[0_18px_54px_rgba(0,0,0,0.24)] ring-1 ring-inset ring-white/[0.07]">
    <div className="flex min-h-11 items-center justify-between"><div><small className="block text-[10px] font-semibold uppercase tracking-[0.13em] text-primary">Контент-календарь</small><h2 className="mt-1 text-balance text-lg font-semibold capitalize tracking-[-0.025em]">{month.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}</h2></div><div className="flex gap-1"><button type="button" aria-label="Предыдущий месяц" onClick={() => moveMonth(-1)} className="grid h-11 w-11 place-items-center rounded-[14px] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] active:scale-[0.96] active:bg-white/[0.06]"><ChevronLeft className="h-5 w-5" /></button><button type="button" aria-label="Следующий месяц" onClick={() => moveMonth(1)} className="grid h-11 w-11 place-items-center rounded-[14px] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] active:scale-[0.96] active:bg-white/[0.06]"><ChevronRight className="h-5 w-5" /></button></div></div>
    <div className="mt-5 grid grid-cols-7 text-center">{['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => <span key={day} className="pb-2 text-[10px] font-semibold uppercase text-zinc-600">{day}</span>)}</div>
    <div className="grid grid-cols-7">{Array.from({ length: cellCount }, (_, index) => {
      const day = index - firstWeekday + 1;
      if (day < 1 || day > dayCount) return <span key={`empty-${index}`} className="h-12" aria-hidden="true" />;
      const key = calendarKey(year, monthIndex, day);
      const dayItems = itemsByDate[key] || [];
      const selected = selectedDate === key;
      const today = todayKey === key;
      const readyCount = dayItems.filter((item) => Boolean(item.draft_text?.trim())).length;
      return <button type="button" key={key} aria-label={`${day} ${month.toLocaleDateString('ru-RU', { month: 'long' })}${dayItems.length ? `, публикаций: ${dayItems.length}` : ', публикаций нет'}`} aria-pressed={selected} onClick={() => { setSelectedDate(key); if (dayItems.length) openDate(key); }} className="group relative grid h-12 min-w-0 place-items-center rounded-[14px] transition-[background-color,color,transform] active:scale-[0.96]"><span className={`grid h-9 w-9 place-items-center rounded-full text-sm font-medium tabular-nums transition-[background-color,color,box-shadow] ${selected ? 'bg-primary text-white shadow-[0_6px_18px_rgba(255,92,51,0.32)]' : today ? 'text-primary ring-1 ring-inset ring-primary/50' : dayItems.length ? 'text-zinc-100' : 'text-zinc-600 group-active:bg-white/[0.05]'}`}>{day}</span>{dayItems.length ? <span className="absolute bottom-0.5 flex gap-0.5" aria-hidden="true">{Array.from({ length: Math.min(dayItems.length, 3) }, (_, dot) => <span key={dot} className={`h-1 w-1 rounded-full ${readyCount > dot ? 'bg-emerald-400' : 'bg-amber-400'}`} />)}</span> : null}</button>;
    })}</div>
    <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 border-t border-white/[0.06] pt-3 text-[10px] text-zinc-500"><span className="flex items-center gap-1.5"><i className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Текст готов</span><span className="flex items-center gap-1.5"><i className="h-1.5 w-1.5 rounded-full bg-amber-400" />Нужно подготовить</span><span className="ml-auto tabular-nums">{items.length} публикаций</span></div>
  </section>;
};

const ContentPostList = ({ postsRef, items, editing, busy, setEditing, generate, update }: { postsRef: { current: HTMLDivElement | null }; items: ModuleItem[]; editing: string; busy: string; setEditing: (id: string) => void; generate: (item: ModuleItem) => Promise<void>; update: (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void> }) => {
  const groups = items.reduce<Record<string, ModuleItem[]>>((result, item) => {
    const key = contentDateKey(item.scheduled_for) || 'undated';
    result[key] = [...(result[key] || []), item];
    return result;
  }, {});
  const orderedGroups = Object.entries(groups).sort(([left], [right]) => left === 'undated' ? 1 : right === 'undated' ? -1 : left.localeCompare(right));
  return <div ref={postsRef} className="scroll-mt-20 pt-6"><div className="mb-3 flex items-end justify-between px-1"><div><small className="text-[10px] font-semibold uppercase tracking-[0.13em] text-primary">Публикации</small><h2 className="mt-1 text-lg font-semibold tracking-[-0.025em]">Посты по плану</h2></div><span className="text-xs tabular-nums text-zinc-500">{items.length}</span></div><div className="space-y-5">{orderedGroups.map(([date, dayItems]) => <section id={`content-day-${date}`} key={date} className="scroll-mt-20"><div className="mb-2 flex items-center gap-2 px-1"><CalendarDays className="h-4 w-4 text-primary" /><b className="text-sm capitalize text-zinc-300">{date === 'undated' ? 'Без даты' : contentDateLabel(date, true)}</b><span className="ml-auto text-[10px] tabular-nums text-zinc-600">{dayItems.length}</span></div><div className="space-y-2">{dayItems.map((item) => <ContentItemCard key={item.id} item={item} editing={editing === item.id} busy={busy === item.id} setEditing={() => setEditing(editing === item.id ? '' : item.id || '')} generate={generate} update={async (values) => { await update(item, values); setEditing(''); }} />)}</div></section>)}</div></div>;
};

const ContentDraftProgress = ({ ready }: { ready: boolean }) => {
  return <motion.div aria-live="polite" initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} transition={spring} className={`rounded-[18px] p-4 ring-1 ring-inset transition-[background-color,box-shadow] ${ready ? 'bg-emerald-500/[0.08] ring-emerald-400/15' : 'bg-primary/[0.08] ring-primary/20'}`}><div className="flex items-center gap-3"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-[14px] ${ready ? 'bg-emerald-400/15 text-emerald-300' : 'bg-primary/15 text-primary'}`}><AnimatePresence initial={false} mode="popLayout">{ready ? <motion.span key="done" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><Check className="h-5 w-5" /></motion.span> : <motion.span key="work" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><Sparkles className="h-5 w-5" /></motion.span>}</AnimatePresence></span><div className="min-w-0 flex-1"><b className="block text-balance text-sm">{ready ? 'Черновик готов' : 'ЛокалОС готовит текст'}</b><small className="mt-1 block text-pretty text-zinc-500">{ready ? 'Проверьте формулировки перед публикацией.' : 'Можно закрыть экран — результат сохранится в публикации.'}</small></div></div>{ready ? null : <div className="relative mt-3 h-1.5 overflow-hidden rounded-full bg-black/20"><motion.span className="absolute inset-y-0 w-1/3 rounded-full bg-primary" animate={{ x: ['-110%', '310%'] }} transition={{ duration: 1.1, repeat: Number.POSITIVE_INFINITY, ease: 'easeInOut' }} /></div>}</motion.div>;
};

const ContentItemCard = ({ item, editing, busy, setEditing, generate, update }: { item: ModuleItem; editing: boolean; busy: boolean; setEditing: () => void; generate: (item: ModuleItem) => Promise<void>; update: (values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void> }) => {
  const [theme, setTheme] = useState(item.title || '');
  const [draft, setDraft] = useState(item.draft_text || '');
  const [scheduled, setScheduled] = useState(contentDateKey(item.scheduled_for));
  const hasDraft = Boolean(item.draft_text?.trim());
  useEffect(() => { setTheme(item.title || ''); setDraft(item.draft_text || ''); setScheduled(contentDateKey(item.scheduled_for)); }, [item.title, item.draft_text, item.scheduled_for]);
  return <article id={`content-item-${item.id || ''}`} className={`scroll-mt-24 rounded-[22px] p-4 ring-1 ring-inset ${hasDraft ? 'bg-emerald-500/[0.025] ring-emerald-400/10' : 'bg-white/[0.04] ring-white/[0.07]'}`}><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><small className="text-[10px] font-semibold uppercase tracking-[0.12em] text-primary">{contentDateLabel(item.scheduled_for)} · {item.content_type || 'публикация'}</small><b className="mt-1 block text-sm leading-5">{item.title}</b><small className="mt-1 block truncate text-zinc-600">{item.business_name}</small></div><span className={`flex min-h-8 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-[10px] font-semibold ring-1 ring-inset ${hasDraft ? 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/15' : 'bg-amber-400/[0.08] text-amber-300 ring-amber-400/15'}`}>{hasDraft ? <Check className="h-3.5 w-3.5" /> : <WandSparkles className="h-3.5 w-3.5" />}{hasDraft ? 'Текст готов' : 'Нужен текст'}</span></div>{editing ? <div className="mt-4 space-y-2"><input value={theme} onChange={(event) => setTheme(event.target.value)} aria-label="Тема публикации" className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><input type="date" value={scheduled} onChange={(event) => setScheduled(event.target.value)} aria-label="Дата публикации" className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-sm text-zinc-300 outline-none ring-1 ring-inset ring-white/[0.07]" /><textarea value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="Текст публикации" rows={6} className="w-full rounded-[14px] bg-black/20 p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" />{busy ? <ContentDraftProgress ready={Boolean(draft.trim())} /> : draft.trim() ? null : <button type="button" onClick={() => void generate(item)} className="flex min-h-12 w-full items-center justify-center gap-2 rounded-[14px] bg-primary/15 px-3 text-sm font-semibold text-primary ring-1 ring-inset ring-primary/20 transition-transform active:scale-[0.96]"><WandSparkles className="h-4 w-4" />Создать текст</button>}<button type="button" disabled={busy} onClick={() => void update({ theme, draft_text: draft, scheduled_for: scheduled })} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-primary text-xs font-semibold transition-transform active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}Сохранить</button></div> : <>{hasDraft ? <div className="mt-4"><small className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-300/80"><Check className="h-3.5 w-3.5" />Черновик ЛокалОС</small><p className="mt-2 line-clamp-6 whitespace-pre-wrap text-pretty text-sm leading-6 text-zinc-300">{item.draft_text}</p></div> : <div className="mt-4 rounded-[16px] bg-amber-400/[0.045] p-3 ring-1 ring-inset ring-amber-400/10"><small className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-300/80"><WandSparkles className="h-3.5 w-3.5" />Задача из контент-плана</small><p className="mt-2 line-clamp-5 whitespace-pre-wrap text-pretty text-sm leading-6 text-zinc-500">{item.subtitle || 'Есть тема, но текст ещё не создан.'}</p></div>}{hasDraft ? <button type="button" disabled={busy} onClick={setEditing} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-white/[0.055] text-xs font-semibold text-zinc-200 ring-1 ring-inset ring-white/[0.08] transition-transform active:scale-[0.96] disabled:opacity-50"><Pencil className="h-4 w-4" />Редактировать текст</button> : <div className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-2"><button type="button" disabled={busy} onClick={setEditing} className="flex min-h-12 items-center justify-center gap-2 rounded-[14px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96] disabled:opacity-50"><Pencil className="h-4 w-4" />Тема</button><button type="button" disabled={busy} onClick={() => { setEditing(); void generate(item); }} className="flex min-h-12 items-center justify-center gap-2 rounded-[14px] bg-primary px-3 text-sm font-semibold text-white shadow-[0_10px_28px_rgba(255,92,51,0.2)] transition-transform active:scale-[0.96] disabled:opacity-50"><WandSparkles className="h-4 w-4" />Создать текст</button></div>}</>}</article>;
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

type RecognizedSale = { id?: string; transaction_date?: string; amount?: number; title?: string; sale_type?: 'service' | 'upsell' | 'cross_sell'; notes?: string };
const saleTypeLabel = (value?: string) => value === 'upsell' ? 'Допродажа' : value === 'cross_sell' ? 'Кросс-продажа · товар' : 'Услуга';

const financeDate = (date: Date) => date.toISOString().slice(0, 10);
const defaultFinancePeriod = () => { const end = new Date(); const start = new Date(end); start.setMonth(start.getMonth() - 3); start.setDate(1); return { start: financeDate(start), end: financeDate(end) }; };
const financePeriod = (preset: string) => { const end = new Date(); const start = new Date(end); if (preset === 'last_30_days') start.setDate(start.getDate() - 29); else if (preset === 'current_month') start.setDate(1); else if (preset === 'previous_month') { start.setMonth(start.getMonth() - 1, 1); end.setDate(1); end.setDate(0); } else if (preset === 'last_year') { start.setFullYear(start.getFullYear() - 1); start.setDate(start.getDate() + 1); } else return defaultFinancePeriod(); return { start: financeDate(start), end: financeDate(end) }; };
const financeNumeric = (value: FinanceValue) => { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
const financeMoney = (value: FinanceValue) => value === null || value === undefined ? 'Нет данных' : `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(financeNumeric(value))} ₽`;
const financePercent = (value: FinanceValue) => { if (value === null || value === undefined) return 'Нет данных'; const numeric = financeNumeric(value); const percent = Math.abs(numeric) <= 1 ? numeric * 100 : numeric; return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(percent)}%`; };
const financeText = (row: Record<string, FinanceValue>, keys: string[], fallback = '—') => { for (const key of keys) { const value = row[key]; if (value !== null && value !== undefined && String(value).trim()) return String(value); } return fallback; };

const FinanceModule = ({ scope, items, reload, openTasks, requestCrm, initialSection = 'overview', trackProduct }: { scope?: MobileScope; items: ModuleItem[]; reload: () => Promise<void>; openTasks: () => void; requestCrm: (values: { crmName: string; crmUrl: string; contact: string; comment: string }) => Promise<void>; initialSection?: string; trackProduct: (eventName: 'mission_open' | 'statistics_flow_opened' | 'statistics_preview_created' | 'statistics_preview_confirmed' | 'crm_request_created', objectId?: string) => void }) => {
  const preview = isPreview();
  const [section, setSection] = useState(initialSection);
  const [dashboard, setDashboard] = useState<FinanceDashboardMobile | null>(preview ? previewFinanceDashboard : null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState('');
  const [periodPreset, setPeriodPreset] = useState('last_3_months');
  const [period, setPeriod] = useState(defaultFinancePeriod);
  const businessId = scope?.kind === 'business' ? scope.id || '' : '';
  const loadDashboard = async () => {
    if (preview) return;
    if (!businessId) return;
    setDashboardLoading(true);
    try {
      const params = new URLSearchParams({ business_id: businessId });
      if (periodPreset === 'all_time') params.set('range', 'all'); else { params.set('from', period.start); params.set('to', period.end); }
      const result = await fetch(`/api/finance/dashboard?${params.toString()}`, { headers: authOnlyHeaders() }).then(readJson<FinanceDashboardMobile>);
      setDashboard(result); setDashboardError('');
    } catch (requestError) { setDashboardError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить финансовый обзор.'); }
    finally { setDashboardLoading(false); }
  };
  // Dashboard reload is intentionally keyed only by the selected business and period.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void loadDashboard(); }, [businessId, period.start, period.end, periodPreset]);
  useEffect(() => setSection(initialSection), [initialSection]);
  const changePeriod = (preset: string) => { setPeriodPreset(preset); if (preset !== 'all_time' && preset !== 'custom') setPeriod(financePeriod(preset)); };
  const refreshAll = async () => { await Promise.all([loadDashboard(), reload()]); };
  if (!businessId) return <Empty icon={Building2} title="Выберите одну точку" text="Финансовый учёт, команда и рабочие места ведутся для конкретного бизнеса." />;
  const tabs = [['overview', 'Обзор'], ['entry', 'Ввести'], ['services', 'Услуги'], ['staff', 'Команда'], ['workplaces', 'Места'], ['import', 'Импорт']];
  return <div>
    <div className="-mx-4 mb-4 overflow-x-auto px-4 [scrollbar-width:none]"><div role="tablist" aria-label="Разделы финансов" className="flex w-max gap-1 rounded-[18px] bg-white/[0.04] p-1 ring-1 ring-inset ring-white/[0.07]">{tabs.map(([key, label]) => <button type="button" role="tab" key={key} aria-selected={section === key} onClick={() => setSection(key)} className={`min-h-11 rounded-[14px] px-4 text-xs font-semibold transition-[background-color,color,transform,box-shadow] active:scale-[0.96] ${section === key ? 'bg-white/[0.11] text-white shadow-[0_5px_16px_rgba(0,0,0,0.24)]' : 'text-zinc-600'}`}>{label}</button>)}</div></div>
    {section === 'overview' ? <><div className="mb-3 flex items-center gap-2 rounded-[18px] bg-white/[0.035] p-2 ring-1 ring-inset ring-white/[0.06]"><select aria-label="Период аналитики" value={periodPreset} onChange={(event) => changePeriod(event.target.value)} className="min-h-11 min-w-0 flex-1 rounded-[13px] bg-zinc-900 px-3 text-xs text-zinc-300 outline-none"><option value="last_30_days">30 дней</option><option value="last_3_months">3 месяца</option><option value="current_month">Текущий месяц</option><option value="previous_month">Прошлый месяц</option><option value="last_year">Год</option><option value="all_time">Всё время</option><option value="custom">Свой период</option></select><button type="button" aria-label="Обновить аналитику" disabled={dashboardLoading} onClick={() => void refreshAll()} className="grid h-11 w-11 shrink-0 place-items-center rounded-[13px] text-zinc-400 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"><RefreshCw className={`h-4 w-4 ${dashboardLoading ? 'animate-spin motion-reduce:animate-none' : ''}`} /></button></div>{periodPreset === 'custom' ? <div className="mb-3 grid grid-cols-2 gap-2"><input type="date" value={period.start} onChange={(event) => setPeriod((current) => ({ ...current, start: event.target.value }))} className="min-h-11 rounded-[14px] bg-zinc-900 px-3 text-xs ring-1 ring-inset ring-white/[0.07]" /><input type="date" value={period.end} onChange={(event) => setPeriod((current) => ({ ...current, end: event.target.value }))} className="min-h-11 rounded-[14px] bg-zinc-900 px-3 text-xs ring-1 ring-inset ring-white/[0.07]" /></div> : null}{dashboardError ? <InlineError text={dashboardError} /> : null}{dashboardLoading && !dashboard ? <ReviewSkeleton /> : <FinanceOverview dashboard={dashboard} openTasks={openTasks} openEntry={() => setSection('entry')} />}</> : null}
    {section === 'entry' ? <div className="space-y-4"><FinanceManualForm mode="entry" businessId={businessId} dashboard={dashboard} reload={refreshAll} /><FinanceSalesModule scope={scope} items={items} reload={refreshAll} /></div> : null}
    {section === 'services' ? <FinanceRecordsSection mode="service" title="Услуги" rows={dashboard?.services || []} businessId={businessId} dashboard={dashboard} reload={refreshAll} /> : null}
    {section === 'staff' ? <FinanceRecordsSection mode="staff" title="Команда" rows={dashboard?.staff || []} businessId={businessId} dashboard={dashboard} reload={refreshAll} /> : null}
    {section === 'workplaces' ? <FinanceRecordsSection mode="workplace" title="Рабочие места" rows={dashboard?.workplaces || []} businessId={businessId} dashboard={dashboard} reload={refreshAll} /> : null}
    {section === 'import' ? <FinanceTools businessId={businessId} dashboard={dashboard} reload={refreshAll} requestCrm={requestCrm} trackProduct={trackProduct} /> : null}
  </div>;
};

const FinanceOverview = ({ dashboard, openTasks, openEntry }: { dashboard: FinanceDashboardMobile | null; openTasks: () => void; openEntry: () => void }) => {
  const [impactOpen, setImpactOpen] = useState(false);
  if (!dashboard) return <Empty icon={BarChart3} title="Финансовых данных пока нет" text="Добавьте выручку и расходы — ЛокалОС сразу соберёт первый управленческий обзор." />;
  const kpis = dashboard.kpis || {};
  const history = dashboard.period_history || [];
  const maxRevenue = Math.max(...history.map((item) => financeNumeric(item.revenue)), 1);
  const recommendations = dashboard.recommendations || [];
  const recommendationFor = (markers: string[]) => recommendations.find((item) => markers.some((marker) => `${item.code || ''} ${item.target_metric || ''} ${item.title || ''}`.toLowerCase().includes(marker)));
  const attention = [
    ['Неявки', financePercent(kpis.no_show_rate), recommendationFor(['no_show', 'неяв'])?.title || 'Потери из-за несостоявшихся визитов', 'Окна заняты в расписании, но не приносят деньги.'],
    ['Повторная запись', financePercent(kpis.rebooking_rate), recommendationFor(['rebooking', 'повтор'])?.title || 'Клиенты уходят без следующей записи', 'Будущая выручка не закрепляется заранее.'],
    ['Загрузка рабочих мест', financePercent(kpis.workplace_occupancy), recommendationFor(['workplace', 'occupancy', 'загруз'])?.title || 'Часть рабочих часов простаивает', 'Кресла и кабинеты есть, но часть времени не монетизируется.'],
  ];
  const next = recommendations[0];
  return <div className="space-y-3">
    <div className="flex flex-wrap items-center gap-2 text-[10px]"><span className="rounded-full bg-white/[0.05] px-3 py-2 text-zinc-400 ring-1 ring-inset ring-white/[0.06]">{dashboard.period?.start_date || '—'} — {dashboard.period?.end_date || '—'}</span><span className="rounded-full bg-white/[0.05] px-3 py-2 tabular-nums text-zinc-400 ring-1 ring-inset ring-white/[0.06]">Качество {dashboard.data_quality?.score ?? '—'}/100</span></div>
    <section className="rounded-[24px] bg-gradient-to-br from-primary/[0.12] to-white/[0.035] p-5 ring-1 ring-inset ring-primary/15"><small className="font-semibold uppercase tracking-[0.13em] text-primary">Выручка</small><b className="mt-2 block text-3xl tracking-[-0.045em] tabular-nums">{financeMoney(kpis.revenue)}</b><p className="mt-2 text-xs text-zinc-500">Средний чек: <span className="tabular-nums text-zinc-300">{financeMoney(kpis.average_ticket)}</span></p></section>
    <div className="grid grid-cols-3 gap-2"><FinanceKpi label="Прибыль" value={financeMoney(kpis.operating_profit)} hint={kpis.operating_margin === null || kpis.operating_margin === undefined ? 'Нужны расходы' : `Маржа ${financePercent(kpis.operating_margin)}`} status={dashboard.statuses?.operating_margin} /><FinanceKpi label="Загрузка" value={financePercent(kpis.workplace_occupancy)} hint={kpis.idle_workplace_hours === null || kpis.idle_workplace_hours === undefined ? 'Нужны часы' : `Простой ${financeNumeric(kpis.idle_workplace_hours)} ч`} status={dashboard.statuses?.workplace_occupancy} /><FinanceKpi label="Повторная" value={financePercent(kpis.rebooking_rate)} hint="Следующий визит" status={dashboard.statuses?.rebooking_rate} /></div>
    <section className="rounded-[24px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start justify-between"><div><b className="text-sm">Динамика выручки</b><small className="mt-1 block text-zinc-600">По выбранному периоду</small></div><BarChart3 className="h-5 w-5 text-primary" /></div>{history.length ? <><div className="mt-5 flex h-32 items-end gap-2">{history.map((item) => { const value = financeNumeric(item.revenue); const height = value ? Math.max(8, value / maxRevenue * 100) : 3; return <div key={`${item.period_start}-${item.label}`} className="flex h-full min-w-0 flex-1 items-end" title={`${item.label || ''}: ${financeMoney(value)}`}><motion.span initial={{ height: 3 }} animate={{ height: `${height}%` }} transition={spring} className="w-full rounded-t-[6px] bg-gradient-to-t from-primary/45 to-primary" /></div>; })}</div><div className="mt-2 flex justify-between text-[10px] text-zinc-700"><span>{history[0]?.label}</span><span>{history[history.length - 1]?.label}</span></div></> : <p className="mt-4 rounded-[16px] bg-black/20 p-4 text-center text-xs leading-5 text-zinc-600">График появится после ввода выручки.</p>}</section>
    <section className="rounded-[24px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start justify-between gap-3"><div><b className="text-sm">На что смотреть в первую очередь</b><p className="mt-1 text-xs leading-5 text-zinc-600">Три показателя, которые быстрее всего влияют на деньги.</p></div><button type="button" onClick={openTasks} className="min-h-11 rounded-[14px] bg-white/[0.05] px-3 text-xs font-semibold ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Задачи</button></div><div className="mt-3 divide-y divide-white/[0.06]">{attention.map(([title, value, problem, impact]) => <div key={title} className="py-3"><div className="flex items-baseline justify-between gap-3"><b className="text-xs">{title}</b><span className="text-xs tabular-nums text-primary">{value}</span></div><p className="mt-1 text-xs text-zinc-400">{problem}</p><small className="mt-1 block leading-4 text-zinc-700">{impact}</small></div>)}</div></section>
    <section className="rounded-[20px] bg-white/[0.035] ring-1 ring-inset ring-white/[0.07]"><button type="button" aria-expanded={impactOpen} onClick={() => setImpactOpen((value) => !value)} className="flex min-h-16 w-full items-center gap-3 px-4 text-left"><span className="min-w-0 flex-1"><b className="block text-sm">Что изменилось после действий</b><small className="mt-1 block text-zinc-600">Отмечено действий: {dashboard.action_impact?.completed_actions_count || 0}</small></span><ChevronRight className={`h-4 w-4 text-zinc-600 transition-transform ${impactOpen ? 'rotate-90' : ''}`} /></button><AnimatePresence initial={false}>{impactOpen ? <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={spring} className="overflow-hidden"><div className="space-y-2 border-t border-white/[0.06] p-4">{dashboard.action_impact?.deltas?.length ? dashboard.action_impact.deltas.map((item) => <div key={item.metric} className="flex items-center justify-between rounded-[14px] bg-black/20 p-3 text-xs"><span className="text-zinc-400">{String(item.metric || '').replaceAll('_', ' ')}</span><b className="tabular-nums">{financeNumeric(item.delta) > 0 ? '+' : ''}{financeNumeric(item.delta)}</b></div>) : <p className="text-xs leading-5 text-zinc-600">Сравнение появится после выполненных действий и следующего сопоставимого периода.</p>}</div></motion.div> : null}</AnimatePresence></section>
    <section className="rounded-[24px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><small className="font-semibold uppercase tracking-[0.13em] text-primary">Ближайший шаг</small><b className="mt-2 block text-balance text-sm">{next?.title || 'Дозаполнить финансовые данные'}</b><p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">{next?.text || 'Добавьте выручку, расходы и данные команды, чтобы ЛокалОС мог найти точки роста.'}</p><button type="button" onClick={next ? openTasks : openEntry} className="mt-4 min-h-12 w-full rounded-[15px] bg-primary text-sm font-semibold shadow-[0_10px_28px_rgba(255,92,51,0.2)] active:scale-[0.96]">{next ? 'Открыть задачи' : 'Ввести данные'}</button></section>
  </div>;
};

const FinanceKpi = ({ label, value, hint, status }: { label: string; value: string; hint: string; status?: string }) => <article className={`min-w-0 rounded-[18px] bg-white/[0.04] p-3 ring-1 ring-inset ${status === 'red' ? 'ring-rose-400/20' : status === 'green' ? 'ring-emerald-400/20' : 'ring-white/[0.07]'}`}><small className="block truncate text-[9px] font-semibold uppercase tracking-[0.09em] text-zinc-600">{label}</small><b className="mt-3 block truncate text-sm tabular-nums">{value}</b><small className="mt-1 block truncate text-[9px] text-zinc-700">{hint}</small></article>;

const FinanceSalesModule = ({ scope, items, reload }: { scope?: MobileScope; items: ModuleItem[]; reload: () => Promise<void> }) => {
  const [text, setText] = useState(''); const [file, setFile] = useState<File | null>(null); const [sales, setSales] = useState<RecognizedSale[]>([]); const [busy, setBusy] = useState(''); const [error, setError] = useState(''); const [success, setSuccess] = useState(''); const [actionId, setActionId] = useState('');
  const recognize = async () => { setBusy('recognize'); setSuccess(''); try { let options: RequestInit; if (file) { const body = new FormData(); body.append('file', file); body.append('scope_type', scope?.kind || 'business'); body.append('scope_id', scope?.id || ''); if (scope?.kind === 'business' && scope.id) body.append('business_id', scope.id); options = { method: 'POST', headers: authOnlyHeaders(), body }; } else options = { method: 'POST', headers: authHeaders(), body: JSON.stringify({ text, scope_type: scope?.kind, scope_id: scope?.id || null, business_id: scope?.kind === 'business' ? scope.id : null }) }; const result = await fetch('/api/operator/mobile/finance/recognize', options).then(readJson<{ transactions?: RecognizedSale[] }>); const recognized = (result.transactions || []).map((item, index) => ({ ...item, id: item.id || `sale-${index}` })); setSales(recognized); setActionId(recognized.length ? 'ready' : ''); setError(recognized.length ? '' : 'Не нашли сумму и состав заказа. Добавьте название услуги и сумму или загрузите более чёткое фото.'); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось распознать продажи.'); } finally { setBusy(''); } };
  const confirm = async () => { if (!sales.length) return; setBusy('confirm'); try { const previewResult = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'finance.sales_import', input: { business_id: scope?.kind === 'business' ? scope.id : null, transactions: sales } }) }).then(readJson<{ preview?: MobileActionPreview }>); const nextActionId = previewResult.preview?.action_id || ''; if (!nextActionId) throw new Error('Не удалось подготовить запись заказа.'); const result = await fetch(`/api/operator/mobile/actions/${nextActionId}/confirm`, { method: 'POST', headers: authHeaders(), body: '{}' }).then(readJson<{ operator_result?: { created_count?: number } }>); const createdCount = Number(result.operator_result?.created_count || sales.length); setSales([]); setText(''); setFile(null); setActionId(''); setError(''); setSuccess(createdCount === 1 ? 'Заказ записан в ЛокалОС' : `Записано заказов: ${createdCount}`); await reload(); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось добавить продажи.'); } finally { setBusy(''); } };
  const prepare = confirm;
  return <div>{scope?.kind !== 'business' ? <InlineError text="Для загрузки продаж сначала выберите конкретный бизнес." /> : <section className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><b className="text-sm">Записать выполненный заказ</b><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">Опишите заказ или загрузите фото либо документ. Сначала ЛокалОС покажет распознанные услуги и сумму — запись появится только после вашего подтверждения.</p><textarea value={text} onChange={(event) => { setText(event.target.value); setFile(null); setSuccess(''); }} rows={5} placeholder={'Например:\n24.07 Стрижка 2 900\nШампунь 850 — товар'} className="mt-3 w-full resize-none rounded-[16px] bg-black/20 p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" /><div className="mt-2 grid grid-cols-2 gap-2"><label className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07]"><Camera className="h-4 w-4" />Фото<input type="file" accept="image/*" capture="environment" className="sr-only" onChange={(event) => { setFile(event.target.files?.[0] || null); setText(''); setSuccess(''); }} /></label><label className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07]"><Upload className="h-4 w-4" />Документ<input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,image/*" className="sr-only" onChange={(event) => { setFile(event.target.files?.[0] || null); setText(''); setSuccess(''); }} /></label></div>{file ? <p className="mt-2 truncate text-xs text-primary">Выбран файл: {file.name}</p> : null}<button type="button" disabled={busy !== '' || (!text.trim() && !file)} onClick={() => void recognize()} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold transition-transform active:scale-[0.96] disabled:opacity-45">{busy === 'recognize' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Sparkles className="h-4 w-4" />}{busy === 'recognize' ? 'Разбираем заказ…' : 'Распознать заказ'}</button></section>}{success ? <div className="mt-3 flex items-center gap-3 rounded-[18px] bg-emerald-500/10 p-4 text-sm font-medium text-emerald-200 ring-1 ring-inset ring-emerald-400/20"><Check className="h-5 w-5 shrink-0" />{success}</div> : null}{error ? <InlineError text={error} /> : null}{sales.length ? <section className="mt-3 rounded-[22px] bg-zinc-900 p-4 ring-1 ring-inset ring-primary/25"><div className="flex items-center justify-between"><b className="text-sm">Найдено позиций: <span className="tabular-nums text-primary">{sales.length}</span></b><small className="text-zinc-600">Проверьте перед записью</small></div><div className="mt-3 space-y-2">{sales.map((sale, index) => <div key={sale.id || index} className="rounded-[16px] bg-black/20 p-3"><div className="flex gap-2"><input value={sale.title || ''} onChange={(event) => setSales((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, title: event.target.value } : item))} className="min-h-11 min-w-0 flex-1 rounded-[12px] bg-white/[0.04] px-3 text-xs ring-1 ring-inset ring-white/[0.06]" /><input inputMode="decimal" value={sale.amount || ''} onChange={(event) => setSales((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, amount: Number(event.target.value) } : item))} className="min-h-11 w-24 rounded-[12px] bg-white/[0.04] px-3 text-right text-xs tabular-nums ring-1 ring-inset ring-white/[0.06]" /></div><select value={sale.sale_type || 'service'} onChange={(event) => setSales((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, sale_type: event.target.value === 'upsell' ? 'upsell' : event.target.value === 'cross_sell' ? 'cross_sell' : 'service' } : item))} className="mt-2 min-h-11 w-full rounded-[12px] bg-zinc-900 px-3 text-xs ring-1 ring-inset ring-white/[0.06]"><option value="service">Услуга</option><option value="upsell">Допродажа</option><option value="cross_sell">Кросс-продажа · товар</option></select><small className="mt-1 block text-zinc-700">{sale.transaction_date || 'Дата не распознана'} · {saleTypeLabel(sale.sale_type)}</small></div>)}</div>{actionId ? <div className="mt-3 rounded-[16px] bg-primary/[0.08] p-3 text-xs leading-5 text-zinc-400">Будет записано позиций: <span className="tabular-nums">{sales.length}</span>. Внешние системы не изменятся.<button type="button" disabled={busy !== ''} onClick={() => void confirm()} className="mt-3 min-h-11 w-full rounded-[14px] bg-primary font-semibold text-white transition-transform active:scale-[0.96]">{busy === 'confirm' ? 'Записываем…' : 'Подтвердить и записать'}</button></div> : <button type="button" disabled={busy !== ''} onClick={() => void prepare()} className="mt-3 min-h-12 w-full rounded-2xl bg-primary text-sm font-semibold transition-transform active:scale-[0.96]">Проверить перед записью</button>}</section> : null}{items.length ? <div className="mt-5"><h2 className="mb-2 text-sm font-semibold">Последние операции</h2><FinanceHistoryList items={items} /></div> : null}</div>;
};

type FinanceManualMode = 'entry' | 'service' | 'staff' | 'workplace';
const financeManualFields: Record<FinanceManualMode, Array<[string, string, string]>> = {
  entry: [['revenue', 'Выручка', '₽'], ['rent', 'Аренда', '₽'], ['payroll', 'ФОТ', '₽'], ['materials', 'Материалы', '₽'], ['marketing', 'Маркетинг', '₽'], ['taxes', 'Налоги', '₽']],
  service: [['service_name', 'Название услуги', 'Текст'], ['category', 'Категория', 'Текст'], ['revenue', 'Выручка', '₽'], ['visits_count', 'Визиты', 'Количество'], ['avg_price', 'Средняя цена', '₽'], ['duration_minutes', 'Длительность, мин', 'Минуты'], ['material_cost', 'Материалы', '₽'], ['staff_payout', 'Выплата мастеру', '₽']],
  staff: [['staff_name', 'Сотрудник', 'Имя'], ['role', 'Роль', 'Текст'], ['revenue', 'Выручка', '₽'], ['visits_count', 'Визиты', 'Количество'], ['booked_hours', 'Занято часов', 'Часы'], ['available_hours', 'Доступно часов', 'Часы'], ['no_show_count', 'Неявки', 'Количество'], ['rebooking_count', 'Повторные записи', 'Количество']],
  workplace: [['name', 'Название места', 'Кресло или кабинет'], ['available_hours', 'Доступно часов', 'Часы'], ['booked_hours', 'Занято часов', 'Часы'], ['revenue', 'Выручка', '₽'], ['gross_profit', 'Валовая прибыль', '₽']],
};

const FinanceManualForm = ({ mode, businessId, dashboard, reload }: { mode: FinanceManualMode; businessId: string; dashboard: FinanceDashboardMobile | null; reload: () => Promise<void> }) => {
  const [values, setValues] = useState<Record<string, string>>({});
  const [entryDate, setEntryDate] = useState(financeDate(new Date()));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const periodStart = dashboard?.period?.start_date || defaultFinancePeriod().start;
  const periodEnd = dashboard?.period?.end_date || defaultFinancePeriod().end;
  const serviceOptions = dashboard?.services || [];
  const save = async () => {
    setBusy(true); setMessage('');
    const entries = mode === 'entry' ? [['revenue', 'revenue', 'sales'], ['rent', 'expense', 'rent'], ['payroll', 'expense', 'payroll'], ['materials', 'expense', 'materials'], ['marketing', 'expense', 'marketing'], ['taxes', 'expense', 'taxes']].filter(([key]) => financeNumeric(values[key]) > 0).map(([key, type, category]) => ({ date: entryDate, type, category, amount: financeNumeric(values[key]), comment: `Статистика за день ${entryDate}` })) : [];
    const services = mode === 'service' ? [{ service_name: values.service_name || 'Услуга', category: values.category || '', revenue: financeNumeric(values.revenue), visits_count: financeNumeric(values.visits_count), avg_price: financeNumeric(values.avg_price), duration_minutes: financeNumeric(values.duration_minutes), material_cost: financeNumeric(values.material_cost), staff_payout: financeNumeric(values.staff_payout) }] : [];
    const staff = mode === 'staff' ? [{ staff_name: values.staff_name || 'Сотрудник', role: values.role || '', revenue: financeNumeric(values.revenue), visits_count: financeNumeric(values.visits_count), booked_minutes: financeNumeric(values.booked_hours) * 60, available_minutes: financeNumeric(values.available_hours) * 60, no_show_count: financeNumeric(values.no_show_count), rebooking_count: financeNumeric(values.rebooking_count) }] : [];
    const workplaces = mode === 'workplace' ? [{ client_key: values.name || 'workplace', name: values.name || 'Рабочее место', type: values.type || 'other', is_active: true }] : [];
    const workplaceMetrics = mode === 'workplace' ? [{ workplace_client_key: values.name || 'workplace', period_start: periodStart, period_end: periodEnd, available_minutes: financeNumeric(values.available_hours) * 60, booked_minutes: financeNumeric(values.booked_hours) * 60, revenue: financeNumeric(values.revenue), gross_profit: financeNumeric(values.gross_profit) }] : [];
    try {
      await fetch('/api/finance/manual-entry', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ business_id: businessId, period_start: mode === 'entry' ? entryDate : periodStart, period_end: mode === 'entry' ? entryDate : periodEnd, entries, services, staff, workplaces, workplace_metrics: workplaceMetrics }) }).then(readJson);
      setValues({}); setMessage('Сохранено — показатели пересчитаны'); await reload();
    } catch (requestError) { setMessage(requestError instanceof Error ? requestError.message : 'Не удалось сохранить данные.'); }
    finally { setBusy(false); }
  };
  const labels: Record<FinanceManualMode, string> = { entry: 'Добавить доходы и расходы', service: 'Добавить показатели услуги', staff: 'Добавить показатели сотрудника', workplace: 'Добавить рабочее место' };
  const selectService = (name: string) => { const selected = serviceOptions.find((item) => String(item.service_name || '') === name); setValues((current) => ({ ...current, service_name: name, category: String(selected?.category || ''), avg_price: selected?.catalog_price === null || selected?.catalog_price === undefined ? current.avg_price || '' : String(selected.catalog_price) })); };
  return <section className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><b className="text-sm">{labels[mode]}</b><p className="mt-1 text-xs leading-5 text-zinc-600">{mode === 'service' ? 'Выберите услугу из карточки — отдельный список в финансах не создаётся. ' : ''}{mode === 'entry' ? 'Внесите итоги одного дня. ' : `Период: ${periodStart} — ${periodEnd}. `}После сохранения ЛокалОС сразу пересчитает обзор.</p>{mode === 'entry' ? <label className="mt-4 block text-[10px] text-zinc-600"><span className="mb-1 block px-1">Дата</span><input type="date" value={entryDate} onChange={(event) => setEntryDate(event.target.value)} className="min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-xs text-zinc-200 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /></label> : null}<div className="mt-4 grid grid-cols-2 gap-2">{financeManualFields[mode].map(([key, label, placeholder], index) => <label key={key} className={`${index < 2 && mode !== 'entry' ? 'col-span-2' : ''} text-[10px] text-zinc-600`}><span className="mb-1 block px-1">{label}</span>{mode === 'service' && key === 'service_name' ? <select value={values.service_name || ''} onChange={(event) => selectService(event.target.value)} className="min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-xs text-zinc-200 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50"><option value="">Выберите услугу из карточки</option>{serviceOptions.map((item, serviceIndex) => <option key={`${item.service_id || item.service_name}-${serviceIndex}`} value={String(item.service_name || '')}>{String(item.service_name || 'Услуга')}</option>)}</select> : <input inputMode={['service_name', 'category', 'staff_name', 'role', 'name'].includes(key) ? 'text' : 'decimal'} value={values[key] || ''} placeholder={placeholder} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-xs text-zinc-200 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" />}</label>)}{mode === 'workplace' ? <label className="col-span-2 text-[10px] text-zinc-600"><span className="mb-1 block px-1">Тип</span><select value={values.type || 'other'} onChange={(event) => setValues((current) => ({ ...current, type: event.target.value }))} className="min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-xs ring-1 ring-inset ring-white/[0.07]"><option value="hair_chair">Кресло</option><option value="beauty_room">Кабинет</option><option value="table">Стол</option><option value="other">Другое</option></select></label> : null}</div>{message ? <p className={`mt-3 text-xs ${message.startsWith('Сохранено') ? 'text-emerald-300' : 'text-rose-300'}`}>{message}</p> : null}<button type="button" disabled={busy || !entryDate || !Object.values(values).some((value) => value.trim()) || (mode === 'service' && !values.service_name)} onClick={() => void save()} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-[15px] bg-primary text-sm font-semibold active:scale-[0.96] disabled:opacity-45">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}{busy ? 'Сохраняем…' : mode === 'entry' ? 'Записать итоги дня' : 'Сохранить и пересчитать'}</button></section>;
};

const FinanceRecordsSection = ({ mode, title, rows, businessId, dashboard, reload }: { mode: Exclude<FinanceManualMode, 'entry'>; title: string; rows: Array<Record<string, FinanceValue>>; businessId: string; dashboard: FinanceDashboardMobile | null; reload: () => Promise<void> }) => {
  const details = (row: Record<string, FinanceValue>) => mode === 'service' ? row.has_finance_data === false ? [`Цена в карточке ${financeMoney(row.catalog_price)}`, 'Нет продаж за период'] : [`Выручка ${financeMoney(row.revenue)}`, `Продаж ${financeText(row, ['visits_count'], '0')}`, `Цена ${financeMoney(row.avg_price)}`] : mode === 'staff' ? [`Выручка ${financeMoney(row.revenue)}`, `Визиты ${financeText(row, ['visits_count'], '0')}`, `Загрузка ${financePercent(row.occupancy)}`] : [`Выручка ${financeMoney(row.revenue)}`, `Загрузка ${financePercent(row.occupancy)}`, `Простой ${financeText(row, ['idle_hours'], '0')} ч`];
  const rowTitle = (row: Record<string, FinanceValue>) => mode === 'service' ? financeText(row, ['service_name', 'name'], 'Услуга') : mode === 'staff' ? financeText(row, ['staff_name', 'name'], 'Сотрудник') : financeText(row, ['name', 'workplace_name'], 'Рабочее место');
  return <div className="space-y-4"><section><div className="mb-3 flex items-end justify-between px-1"><div><small className="text-[10px] font-semibold uppercase tracking-[0.13em] text-primary">{mode === 'service' ? 'Услуги из карточки' : 'Показатели'}</small><h2 className="mt-1 text-lg font-semibold">{title}</h2></div><span className="text-xs tabular-nums text-zinc-600">{rows.length}</span></div>{rows.length ? <div className="space-y-2">{rows.map((row, index) => <article key={`${rowTitle(row)}-${index}`} className="rounded-[20px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><b className="block text-sm">{rowTitle(row)}</b><small className="mt-1 block text-zinc-600">{mode === 'service' ? financeText(row, ['category'], 'Без категории') : mode === 'staff' ? financeText(row, ['role'], 'Роль не указана') : financeText(row, ['type'], 'Тип не указан')}</small></div>{mode === 'service' ? <span className={`shrink-0 rounded-full px-2 py-1 text-[9px] font-semibold ${row.has_finance_data === false ? 'bg-zinc-800 text-zinc-500' : 'bg-emerald-500/10 text-emerald-300'}`}>{row.has_finance_data === false ? 'Нет продаж' : 'Рассчитано'}</span> : null}</div><div className="mt-3 flex flex-wrap gap-2">{details(row).map((detail) => <span key={detail} className="rounded-full bg-black/20 px-3 py-2 text-[10px] tabular-nums text-zinc-400 ring-1 ring-inset ring-white/[0.05]">{detail}</span>)}</div>{mode === 'service' ? <small className="mt-3 block text-[10px] text-zinc-700">Источник: {financeText(row, ['source'], 'ЛокалОС')} · обновлено {dateLabel(String(row.updated_at || ''))}</small> : null}</article>)}</div> : <Empty icon={mode === 'staff' ? Users : mode === 'workplace' ? Building2 : LayoutGrid} title={`${title} пока не добавлены`} text={mode === 'service' ? 'Добавьте услуги в карточку бизнеса — здесь появится тот же список.' : 'Добавьте первые показатели — они сразу появятся в финансовом обзоре.'} />}</section><FinanceManualForm mode={mode} businessId={businessId} dashboard={dashboard} reload={reload} /></div>;
};

type FinanceImportPreview = { file_name?: string; rows_total?: number; valid_rows?: number; failed_rows?: number; rows_imported?: number; rows_skipped?: number; rows_failed?: number; mapping?: Record<string, string>; preview?: Array<Record<string, FinanceValue>>; errors?: Array<{ row?: number; errors?: string[] }> };
const FinanceImport = ({ businessId, dashboard, reload, preferredProfile, trackProduct }: { businessId: string; dashboard: FinanceDashboardMobile | null; reload: () => Promise<void>; preferredProfile?: string; trackProduct: (eventName: 'statistics_preview_created' | 'statistics_preview_confirmed', objectId?: string) => void }) => {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<FinanceImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mappingDirty, setMappingDirty] = useState(false);
  const [templateProfile, setTemplateProfile] = useState(preferredProfile || 'manual');
  const [templates, setTemplates] = useState<Record<string, { label?: string }>>({});
  const [imports, setImports] = useState<Array<{ id?: string; file_name?: string; status?: string; rows_total?: number; rows_imported?: number; rows_skipped?: number; rows_failed?: number; created_at?: string }>>([]);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const loadMetadata = async () => { try { const [templateResult, importResult] = await Promise.all([fetch('/api/finance/import-templates').then(readJson<{ templates?: Record<string, { label?: string }> }>), fetch(`/api/finance/imports?business_id=${businessId}`, { headers: authOnlyHeaders() }).then(readJson<{ imports?: typeof imports }>) ]); setTemplates(templateResult.templates || {}); setImports(importResult.imports || []); } catch (requestError) { setMessage(requestError instanceof Error ? requestError.message : 'Не удалось загрузить историю импорта.'); } };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void loadMetadata(); }, [businessId]);
  useEffect(() => { if (preferredProfile) setTemplateProfile(preferredProfile); }, [preferredProfile]);
  const request = async (endpoint: string) => { if (!file) return null; const body = new FormData(); body.append('file', file); body.append('business_id', businessId); body.append('mapping', JSON.stringify(mapping)); body.append('period_start', dashboard?.period?.start_date || defaultFinancePeriod().start); body.append('period_end', dashboard?.period?.end_date || defaultFinancePeriod().end); return fetch(endpoint, { method: 'POST', headers: authOnlyHeaders(), body }).then(readJson<FinanceImportPreview>); };
  const inspect = async () => { setBusy('preview'); setMessage(''); try { const result = await request('/api/finance/import-preview'); setPreview(result); setMapping(result?.mapping || {}); setMappingDirty(false); trackProduct('statistics_preview_created', file?.name); } catch (requestError) { setMessage(requestError instanceof Error ? requestError.message : 'Не удалось проверить файл.'); } finally { setBusy(''); } };
  const confirm = async () => { if (mappingDirty) { setMessage('После изменения колонок нужно ещё раз проверить файл.'); return; } setBusy('confirm'); setMessage(''); try { const result = await request('/api/finance/import-file'); trackProduct('statistics_preview_confirmed', file?.name); setMessage(`Импортировано: ${result?.rows_imported || 0}. Дубли: ${result?.rows_skipped || 0}. Ошибки: ${result?.rows_failed || 0}.`); setPreview(null); setFile(null); await Promise.all([reload(), loadMetadata()]); } catch (requestError) { setMessage(requestError instanceof Error ? requestError.message : 'Не удалось импортировать файл.'); } finally { setBusy(''); } };
  return <div id="finance-file-import" className="scroll-mt-24"><section className="rounded-[24px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><span className="grid h-11 w-11 place-items-center rounded-[15px] bg-primary/15 text-primary"><Upload className="h-5 w-5" /></span><b className="mt-4 block text-base">Импорт финансовых данных</b><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">Загрузите CSV, Excel или таблицу. Сначала ЛокалОС покажет распознанные строки и ошибки — без подтверждения данные не запишутся.</p><div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto] gap-2"><select aria-label="Тип шаблона" value={templateProfile} onChange={(event) => setTemplateProfile(event.target.value)} className="min-h-11 min-w-0 rounded-[14px] bg-zinc-900 px-3 text-xs ring-1 ring-inset ring-white/[0.07]">{Object.entries(templates).map(([key, value]) => <option key={key} value={key}>{value.label || key}</option>)}</select><a href={`/api/finance/import-template?profile=${templateProfile}`} target="_blank" rel="noreferrer" className="flex min-h-11 items-center rounded-[14px] bg-white/[0.05] px-3 text-xs font-semibold ring-1 ring-inset ring-white/[0.07]">Шаблон</a></div><label className="mt-3 flex min-h-14 cursor-pointer items-center justify-center rounded-[16px] bg-black/20 px-4 text-center text-xs font-semibold ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"><FileText className="mr-2 h-4 w-4" />{file?.name || 'Выбрать файл'}<input type="file" accept=".csv,.tsv,.txt,.xlsx,.xls" className="sr-only" onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); setMapping({}); setMessage(''); }} /></label><button type="button" disabled={!file || Boolean(busy)} onClick={() => void inspect()} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-[15px] bg-primary text-sm font-semibold active:scale-[0.96] disabled:opacity-45">{busy === 'preview' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Search className="h-4 w-4" />}{busy === 'preview' ? 'Проверяем строки…' : 'Проверить перед импортом'}</button></section>{message ? <p className={`mt-3 rounded-[16px] p-3 text-xs ${message.startsWith('Импортировано') ? 'bg-emerald-500/10 text-emerald-200' : 'bg-rose-500/10 text-rose-200'}`}>{message}</p> : null}{preview ? <section className="mt-3 rounded-[24px] bg-zinc-900 p-4 ring-1 ring-inset ring-primary/25"><b className="text-sm">Проверка файла</b><div className="mt-3 grid grid-cols-3 gap-2"><MetricMini label="Всего" value={preview.rows_total} /><MetricMini label="Готово" value={preview.valid_rows} accent /><MetricMini label="Ошибки" value={preview.failed_rows} /></div>{Object.keys(mapping).length ? <div className="mt-3 rounded-[16px] bg-black/20 p-3"><small className="font-semibold text-zinc-400">Сопоставление колонок</small><div className="mt-2 space-y-2">{Object.entries(mapping).map(([target, source]) => <label key={target} className="flex items-center gap-2 text-[10px] text-zinc-600"><span className="min-w-0 flex-1 truncate">{target}</span><input value={source} onChange={(event) => { setMapping((current) => ({ ...current, [target]: event.target.value })); setMappingDirty(true); }} className="min-h-11 w-36 rounded-[12px] bg-white/[0.04] px-3 text-xs text-zinc-300 ring-1 ring-inset ring-white/[0.06]" /></label>)}</div></div> : null}{preview.preview?.length ? <div className="mt-3 max-h-64 space-y-2 overflow-y-auto">{preview.preview.map((row, index) => <div key={index} className="rounded-[14px] bg-black/20 p-3 text-[10px] leading-4 text-zinc-500">{Object.entries(row).slice(0, 5).map(([key, value]) => <div key={key} className="flex justify-between gap-3"><span>{key}</span><span className="max-w-[60%] truncate text-zinc-300">{String(value ?? '')}</span></div>)}</div>)}</div> : null}<button type="button" disabled={Boolean(busy) || !preview.valid_rows} onClick={() => void confirm()} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-[15px] bg-primary text-sm font-semibold active:scale-[0.96] disabled:opacity-45">{busy === 'confirm' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}{busy === 'confirm' ? 'Импортируем…' : mappingDirty ? 'Снова проверить файл' : `Подтвердить ${preview.valid_rows || 0} строк`}</button></section> : null}{imports.length ? <section className="mt-4 rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><b className="text-sm">История импорта</b><div className="mt-3 space-y-2">{imports.slice(0, 5).map((item) => <div key={item.id} className="rounded-[14px] bg-black/20 p-3"><div className="flex items-center justify-between gap-2"><span className="truncate text-xs text-zinc-300">{item.file_name || 'Импорт'}</span><StatusPill value={item.status} /></div><small className="mt-1 block tabular-nums text-zinc-700">Импортировано {item.rows_imported || 0} · Дубли {item.rows_skipped || 0} · Ошибки {item.rows_failed || 0}</small></div>)}</div></section> : null}</div>;
};

type FinanceThreshold = { metric_key?: string; label?: string; unit?: string; source?: string; green_min?: FinanceValue; green_max?: FinanceValue; yellow_min?: FinanceValue; yellow_max?: FinanceValue; red_rule?: string };
type FinanceTransaction = { id?: string; transaction_date?: string | null; amount?: number; services?: string[] | null; notes?: string | null; client_type?: string | null };

const FinanceTools = ({ businessId, dashboard, reload, requestCrm, trackProduct }: { businessId: string; dashboard: FinanceDashboardMobile | null; reload: () => Promise<void>; requestCrm: (values: { crmName: string; crmUrl: string; contact: string; comment: string }) => Promise<void>; trackProduct: (eventName: 'mission_open' | 'statistics_flow_opened' | 'statistics_preview_created' | 'statistics_preview_confirmed' | 'crm_request_created', objectId?: string) => void }) => {
  const [preferredProfile, setPreferredProfile] = useState('');
  const [crmRequest, setCrmRequest] = useState<{ crm_name?: string; status?: string } | null>(null);
  useEffect(() => { void fetch(`/api/business/${businessId}/crm-integration-requests`, { headers: authOnlyHeaders() }).then(readJson<{ requests?: Array<{ crm_name?: string; status?: string }> }>).then((result) => setCrmRequest(result.requests?.[0] || null)).catch(() => setCrmRequest(null)); }, [businessId]);
  const openYclientsImport = () => {
    setPreferredProfile('yclients_stats');
    window.requestAnimationFrame(() => document.getElementById('finance-file-import')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };
  const submitCrm = async (values: { crmName: string; crmUrl: string; contact: string; comment: string }) => { await requestCrm(values); setCrmRequest({ crm_name: values.crmName, status: 'open' }); };
  return <div className="space-y-4"><FinanceCrmMobilePanel onOpenFileImport={openYclientsImport} onRequestCrm={submitCrm} currentRequest={crmRequest} /><FinanceImport businessId={businessId} dashboard={dashboard} reload={reload} preferredProfile={preferredProfile} trackProduct={trackProduct} /><FinanceThresholds businessId={businessId} reload={reload} /><FinanceRoi businessId={businessId} /><FinanceTransactions businessId={businessId} reload={reload} /></div>;
};

const FinanceThresholds = ({ businessId, reload }: { businessId: string; reload: () => Promise<void> }) => {
  const [thresholds, setThresholds] = useState<Record<string, FinanceThreshold>>({});
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const load = async () => { try { const result = await fetch(`/api/finance/thresholds?business_id=${businessId}`, { headers: authOnlyHeaders() }).then(readJson<{ thresholds?: Record<string, FinanceThreshold> }>); setThresholds(result.thresholds || {}); } catch (requestError) { setMessage(requestError instanceof Error ? requestError.message : 'Не удалось загрузить нормы.'); } };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [businessId]);
  const keys = Object.keys(thresholds);
  const update = (key: string, field: keyof FinanceThreshold, value: string) => setThresholds((current) => ({ ...current, [key]: { ...(current[key] || {}), metric_key: key, [field]: value.trim() === '' ? null : field === 'red_rule' ? value : Number(value) } }));
  const save = async () => { setBusy(true); try { const result = await fetch('/api/finance/thresholds', { method: 'PUT', headers: authHeaders(), body: JSON.stringify({ business_id: businessId, thresholds: keys.map((key) => ({ ...(thresholds[key] || {}), metric_key: key })) }) }).then(readJson<{ thresholds?: Record<string, FinanceThreshold> }>); setThresholds(result.thresholds || {}); setMessage('Нормы сохранены, рекомендации пересчитаны'); await reload(); } catch (requestError) { setMessage(requestError instanceof Error ? requestError.message : 'Не удалось сохранить нормы.'); } finally { setBusy(false); } };
  const reset = async () => { setBusy(true); try { const result = await fetch('/api/finance/thresholds/reset', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ business_id: businessId }) }).then(readJson<{ thresholds?: Record<string, FinanceThreshold> }>); setThresholds(result.thresholds || {}); setMessage('Возвращены базовые нормы'); await reload(); } catch (requestError) { setMessage(requestError instanceof Error ? requestError.message : 'Не удалось сбросить нормы.'); } finally { setBusy(false); } };
  return <section className="rounded-[22px] bg-white/[0.04] ring-1 ring-inset ring-white/[0.07]"><button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex min-h-20 w-full items-center gap-3 p-4 text-left"><span className="grid h-11 w-11 place-items-center rounded-[14px] bg-primary/12 text-primary"><Settings className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block text-sm">Нормы KPI</b><small className="mt-1 block text-zinc-600">{keys.length} показателей · свои нормы: {keys.filter((key) => thresholds[key]?.source === 'custom').length}</small></span><ChevronRight className={`h-4 w-4 text-zinc-600 transition-transform ${open ? 'rotate-90' : ''}`} /></button><AnimatePresence initial={false}>{open ? <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={spring} className="overflow-hidden"><div className="space-y-3 border-t border-white/[0.06] p-4">{keys.map((key) => { const item = thresholds[key] || {}; return <div key={key} className="rounded-[16px] bg-black/20 p-3"><div className="flex items-center justify-between gap-2"><b className="text-xs">{item.label || key.replaceAll('_', ' ')}</b><small className="text-zinc-700">{item.source === 'custom' ? 'Своя' : 'Базовая'}</small></div><div className="mt-3 grid grid-cols-2 gap-2">{[['green_min', 'Зелёная от'], ['green_max', 'Зелёная до'], ['yellow_min', 'Жёлтая от'], ['yellow_max', 'Жёлтая до']].map(([field, label]) => <label key={field} className="text-[9px] text-zinc-600">{label}<input inputMode="decimal" value={String(item[field === 'green_min' ? 'green_min' : field === 'green_max' ? 'green_max' : field === 'yellow_min' ? 'yellow_min' : 'yellow_max'] ?? '')} onChange={(event) => update(key, field === 'green_min' ? 'green_min' : field === 'green_max' ? 'green_max' : field === 'yellow_min' ? 'yellow_min' : 'yellow_max', event.target.value)} className="mt-1 min-h-11 w-full rounded-[12px] bg-white/[0.04] px-3 text-xs ring-1 ring-inset ring-white/[0.06]" /></label>)}</div><label className="mt-2 block text-[9px] text-zinc-600">Правило красной зоны<input value={item.red_rule || ''} onChange={(event) => update(key, 'red_rule', event.target.value)} className="mt-1 min-h-11 w-full rounded-[12px] bg-white/[0.04] px-3 text-xs ring-1 ring-inset ring-white/[0.06]" /></label></div>; })}{message ? <p className="text-xs text-zinc-400">{message}</p> : null}<div className="grid grid-cols-2 gap-2"><button type="button" disabled={busy} onClick={() => void reset()} className="min-h-11 rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07]">Сбросить</button><button type="button" disabled={busy} onClick={() => void save()} className="min-h-11 rounded-[14px] bg-primary text-xs font-semibold">{busy ? 'Сохраняем…' : 'Сохранить'}</button></div></div></motion.div> : null}</AnimatePresence></section>;
};

const FinanceRoi = ({ businessId }: { businessId: string }) => {
  const today = financeDate(new Date());
  const [values, setValues] = useState({ investment_amount: '', returns_amount: '', period_start: today, period_end: today });
  const [roi, setRoi] = useState(0);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const load = async () => { try { const params = new URLSearchParams({ business_id: businessId }); const result = await fetch(`/api/finance/roi?${params.toString()}`, { headers: authOnlyHeaders() }).then(readJson<{ roi?: { investment_amount?: number; returns_amount?: number; roi_percentage?: number; period_start?: string | null; period_end?: string | null } }>); const value = result.roi; if (value) { setValues({ investment_amount: String(value.investment_amount || ''), returns_amount: String(value.returns_amount || ''), period_start: value.period_start || today, period_end: value.period_end || today }); setRoi(value.roi_percentage || 0); } } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить ROI.'); } };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [businessId]);
  const save = async () => { setBusy(true); try { const result = await fetch('/api/finance/roi', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ business_id: businessId, investment_amount: financeNumeric(values.investment_amount), returns_amount: financeNumeric(values.returns_amount), period_start: values.period_start, period_end: values.period_end }) }).then(readJson<{ roi?: { roi_percentage?: number } }>); setRoi(result.roi?.roi_percentage || 0); setOpen(false); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось рассчитать ROI.'); } finally { setBusy(false); } };
  return <section className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-center justify-between"><div><b className="text-sm">Окупаемость вложений</b><p className="mt-1 text-xs text-zinc-600">ROI за выбранный период</p></div><b className={`text-xl tabular-nums ${roi >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(roi)}%</b></div>{open ? <div className="mt-4 grid grid-cols-2 gap-2"><FinanceSmallInput label="Вложения" value={values.investment_amount} setValue={(value) => setValues((current) => ({ ...current, investment_amount: value }))} /><FinanceSmallInput label="Возврат" value={values.returns_amount} setValue={(value) => setValues((current) => ({ ...current, returns_amount: value }))} /><label className="text-[10px] text-zinc-600">Начало<input type="date" value={values.period_start} onChange={(event) => setValues((current) => ({ ...current, period_start: event.target.value }))} className="mt-1 min-h-11 w-full rounded-[12px] bg-zinc-900 px-2 text-xs ring-1 ring-inset ring-white/[0.06]" /></label><label className="text-[10px] text-zinc-600">Конец<input type="date" value={values.period_end} onChange={(event) => setValues((current) => ({ ...current, period_end: event.target.value }))} className="mt-1 min-h-11 w-full rounded-[12px] bg-zinc-900 px-2 text-xs ring-1 ring-inset ring-white/[0.06]" /></label><button type="button" disabled={busy} onClick={() => void save()} className="col-span-2 min-h-11 rounded-[14px] bg-primary text-xs font-semibold">{busy ? 'Считаем…' : 'Рассчитать и сохранить'}</button></div> : <button type="button" onClick={() => setOpen(true)} className="mt-3 min-h-11 w-full rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07]">Изменить расчёт</button>}{error ? <p className="mt-2 text-xs text-rose-300">{error}</p> : null}</section>;
};

const FinanceSmallInput = ({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) => <label className="text-[10px] text-zinc-600">{label}<input inputMode="decimal" value={value} onChange={(event) => setValue(event.target.value)} className="mt-1 min-h-11 w-full rounded-[12px] bg-black/20 px-3 text-xs ring-1 ring-inset ring-white/[0.06]" /></label>;

const FinanceTransactions = ({ businessId, reload }: { businessId: string; reload: () => Promise<void> }) => {
  const [rows, setRows] = useState<FinanceTransaction[]>([]);
  const [editing, setEditing] = useState('');
  const [deleting, setDeleting] = useState('');
  const [deletePreview, setDeletePreview] = useState<MobileActionPreview | null>(null);
  const [form, setForm] = useState({ transaction_date: '', amount: '', services: '', notes: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = async () => { try { const result = await fetch(`/api/finance/transactions?business_id=${businessId}&limit=100`, { headers: authOnlyHeaders() }).then(readJson<{ transactions?: FinanceTransaction[] }>); setRows(result.transactions || []); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить операции.'); } };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [businessId]);
  const edit = (row: FinanceTransaction) => { setEditing(row.id || ''); setDeleting(''); setDeletePreview(null); setForm({ transaction_date: row.transaction_date || '', amount: String(row.amount || ''), services: row.services?.join(', ') || '', notes: row.notes || '' }); };
  const save = async () => { if (!editing) return; setBusy(true); try { await fetch(`/api/finance/transaction/${editing}`, { method: 'PUT', headers: authHeaders(), body: JSON.stringify({ transaction_date: form.transaction_date || null, amount: financeNumeric(form.amount), services: form.services.split(',').map((item) => item.trim()).filter(Boolean), notes: form.notes }) }).then(readJson); setEditing(''); await Promise.all([load(), reload()]); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить операцию.'); } finally { setBusy(false); } };
  const prepareDelete = async (row: FinanceTransaction) => { if (!row.id) return; setBusy(true); try { const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: 'business', scope_id: businessId, capability: 'finance.transaction.delete', input: { business_id: businessId, transaction_id: row.id } }) }).then(readJson<{ preview?: MobileActionPreview }>); if (!result.preview?.action_id) throw new Error('Не удалось проверить операцию.'); setDeletePreview(result.preview); setDeleting(row.id); setEditing(''); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить операцию.'); } finally { setBusy(false); } };
  const remove = async () => { if (!deleting || !deletePreview?.action_id) return; setBusy(true); try { await fetch(`/api/operator/mobile/actions/${deletePreview.action_id}/confirm`, { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: 'business', scope_id: businessId }) }).then(readJson); setDeleting(''); setDeletePreview(null); await Promise.all([load(), reload()]); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось удалить операцию.'); } finally { setBusy(false); } };
  return <section className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-end justify-between"><div><b className="text-sm">Журнал операций</b><p className="mt-1 text-xs text-zinc-600">До 100 последних записей</p></div><span className="text-xs tabular-nums text-zinc-600">{rows.length}</span></div>{error ? <p className="mt-3 text-xs text-rose-300">{error}</p> : null}<div className="mt-3 space-y-2">{rows.length ? rows.map((row) => <article key={row.id} className="rounded-[16px] bg-black/20 p-3">{editing === row.id ? <div className="space-y-2"><div className="grid grid-cols-2 gap-2"><input type="date" value={form.transaction_date} onChange={(event) => setForm((current) => ({ ...current, transaction_date: event.target.value }))} className="min-h-11 rounded-[12px] bg-white/[0.04] px-2 text-xs ring-1 ring-inset ring-white/[0.06]" /><input inputMode="decimal" value={form.amount} onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))} className="min-h-11 rounded-[12px] bg-white/[0.04] px-3 text-xs ring-1 ring-inset ring-white/[0.06]" /></div><input value={form.services} onChange={(event) => setForm((current) => ({ ...current, services: event.target.value }))} placeholder="Услуги через запятую" className="min-h-11 w-full rounded-[12px] bg-white/[0.04] px-3 text-xs ring-1 ring-inset ring-white/[0.06]" /><input value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Комментарий" className="min-h-11 w-full rounded-[12px] bg-white/[0.04] px-3 text-xs ring-1 ring-inset ring-white/[0.06]" /><div className="grid grid-cols-2 gap-2"><button type="button" onClick={() => setEditing('')} className="min-h-11 rounded-[12px] bg-white/[0.05] text-xs">Отмена</button><button type="button" disabled={busy} onClick={() => void save()} className="min-h-11 rounded-[12px] bg-primary text-xs font-semibold">Сохранить</button></div></div> : deleting === row.id ? <div><p className="text-xs leading-5 text-rose-200">Удалить операцию на {financeMoney(row.amount)}? Это изменит финансовую аналитику.</p><p className="mt-2 text-[10px] text-zinc-600">Стоимость: {deletePreview?.estimated_credits || 0} кредитов · бизнес: {deletePreview?.target_businesses?.[0]?.name || 'текущий'}</p><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" onClick={() => { setDeleting(''); setDeletePreview(null); }} className="min-h-11 rounded-[12px] bg-white/[0.05] text-xs">Оставить</button><button type="button" disabled={busy} onClick={() => void remove()} className="min-h-11 rounded-[12px] bg-rose-500 text-xs font-semibold">Подтвердить удаление</button></div></div> : <><div className="flex items-start justify-between gap-3"><div className="min-w-0"><b className="block truncate text-xs">{row.services?.join(', ') || row.notes || 'Операция'}</b><small className="mt-1 block text-zinc-700">{row.transaction_date || 'Без даты'}</small></div><b className="shrink-0 text-sm tabular-nums">{financeMoney(row.amount)}</b></div><div className="mt-2 flex justify-end"><button type="button" onClick={() => edit(row)} className="min-h-11 px-3 text-xs text-zinc-400">Изменить</button><button type="button" disabled={busy} onClick={() => void prepareDelete(row)} className="min-h-11 px-3 text-xs text-rose-300">Удалить</button></div></>}</article>) : <p className="rounded-[14px] bg-black/20 p-4 text-center text-xs text-zinc-600">Операций пока нет.</p>}</div></section>;
};

const AnalyticsModule = ({ items }: { items: ModuleItem[] }) => {
  const metrics = items.filter((item) => item.kind === 'analytics_metric');
  const days = items.filter((item) => item.kind === 'analytics_day');
  const maxRevenue = Math.max(...days.map((item) => Number(item.amount || 0)), 1);
  const formatValue = (item: ModuleItem) => {
    const value = Number(item.amount || 0);
    if (item.unit === '₽') return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value)} ₽`;
    return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value);
  };
  const change = (item: ModuleItem) => {
    const current = Number(item.amount || 0);
    const previous = Number(item.previous_amount || 0);
    if (!previous) return null;
    return Math.round(((current - previous) / previous) * 100);
  };

  return metrics.length ? (
    <div>
      <div className="grid grid-cols-2 gap-2">
        {metrics.map((item, index) => {
          const delta = change(item);
          const DeltaIcon = delta !== null && delta < 0 ? TrendingDown : TrendingUp;
          return (
            <motion.article
              key={item.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...spring, delay: index * 0.08 }}
              className={`${index === 0 ? 'col-span-2' : ''} rounded-[22px] bg-white/[0.04] p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.07)]`}
            >
              <small className="text-pretty text-zinc-600">{item.title}</small>
              <b className="mt-2 block text-balance text-2xl tracking-[-0.04em] tabular-nums text-zinc-100">{formatValue(item)}</b>
              <div className="mt-2 flex min-h-5 items-center gap-1.5 text-[11px]">
                {delta === null ? <span className="text-zinc-700">Появится сравнение с прошлым периодом</span> : <><DeltaIcon className={`h-3.5 w-3.5 ${delta < 0 ? 'text-rose-300' : 'text-emerald-300'}`} /><span className={`tabular-nums ${delta < 0 ? 'text-rose-300' : 'text-emerald-300'}`}>{delta > 0 ? '+' : ''}{delta}%</span><span className="text-zinc-700">к прошлым 30 дням</span></>}
              </div>
            </motion.article>
          );
        })}
      </div>
      <section className="mt-3 rounded-[24px] bg-zinc-900 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
        <div className="flex items-start justify-between gap-3">
          <div><b className="block text-sm">Выручка по дням</b><small className="mt-1 block text-pretty text-zinc-600">Последние 14 дней по записанным заказам</small></div>
          <BarChart3 className="h-5 w-5 shrink-0 text-primary" />
        </div>
        <div className="mt-5 flex h-32 items-end gap-1.5" aria-label="График выручки за 14 дней">
          {days.map((item) => {
            const value = Number(item.amount || 0);
            const height = value > 0 ? Math.max(12, Math.round((value / maxRevenue) * 100)) : 4;
            const label = item.day ? new Date(`${item.day}T12:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '';
            return <div key={item.id} className="flex h-full min-w-0 flex-1 items-end" title={`${label}: ${formatValue({ ...item, unit: '₽' })}`}><motion.div initial={{ height: 4, opacity: 0.35 }} animate={{ height: `${height}%`, opacity: value > 0 ? 1 : 0.35 }} transition={spring} className="w-full min-w-1 rounded-t-[5px] bg-primary" /></div>;
          })}
        </div>
        <div className="mt-2 flex justify-between text-[10px] text-zinc-700"><span>{days[0]?.day ? new Date(`${days[0].day}T12:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : ''}</span><span>{days[days.length - 1]?.day ? new Date(`${days[days.length - 1].day}T12:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : ''}</span></div>
      </section>
      {Number(metrics[0]?.amount || 0) === 0 ? <p className="mt-3 rounded-[18px] bg-primary/[0.08] p-4 text-pretty text-xs leading-5 text-zinc-400 ring-1 ring-inset ring-primary/15">Добавьте выполненные заказы в разделе «Финансы» — здесь появятся выручка, средний чек и динамика.</p> : null}
    </div>
  ) : <Empty icon={BarChart3} title="Аналитика собирается" text="Добавьте первые продажи — ЛокалОС покажет выручку, заказы и динамику по дням." />;
};

const FinanceHistoryList = ({ items }: { items: ModuleItem[] }) => <div className="space-y-2">{items.map((item) => <article key={item.id} className="flex min-h-16 items-center gap-3 rounded-[20px] bg-white/[0.04] px-4 ring-1 ring-inset ring-white/[0.07]"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-[14px] ${item.transaction_type === 'income' ? 'bg-emerald-400/10 text-emerald-300' : 'bg-white/[0.05] text-zinc-400'}`}><CreditCard className="h-4 w-4" /></span><div className="min-w-0 flex-1"><b className="block truncate text-sm">{item.title || item.subtitle || 'Операция'}</b><small className="mt-1 block truncate text-zinc-600">{item.updated_at ? dateLabel(item.updated_at) : item.business_name}</small></div>{item.amount !== undefined ? <b className={`shrink-0 text-sm tabular-nums ${item.transaction_type === 'income' ? 'text-emerald-300' : 'text-zinc-300'}`}>{item.transaction_type === 'income' ? '+' : '−'}{item.amount} ₽</b> : null}</article>)}</div>;

const ModuleUnavailable = () => <Empty icon={CircleEllipsis} title="Раздел пока недоступен" text="ЛокалОС скрыл незавершённый сценарий, чтобы не показывать пустые кнопки и фиктивные данные." />;

const NotificationSettings = ({ preferences, saving, save }: { preferences: NotificationPreferences; saving: boolean; save: (preferences: NotificationPreferences) => Promise<void> }) => {
  const [value, setValue] = useState<NotificationPreferences>(preferences);
  useEffect(() => setValue(preferences), [preferences]);
  const rows: Array<[keyof NotificationPreferences, string, string]> = [['daily_digest', 'Утренняя сводка', 'Задачи и изменения за сутки'], ['content_publications', 'Публикации', 'Готовые тексты для ручного размещения'], ['finance_rhythm', 'Ритм статистики', 'Один раз перед сроком и один — после'], ['reviews', 'Новые отзывы', 'Когда нужен ответ'], ['tasks', 'Решения', 'Черновики и подтверждения'], ['errors', 'Ошибки', 'Точка или подключение требует внимания'], ['agent_results', 'Результаты ЛокалОС', 'Новый результат готов к проверке']];
  return <div><div className="space-y-2">{rows.map(([key, title, description]) => <label key={key} className="flex min-h-16 items-center gap-3 rounded-[20px] bg-white/[0.04] px-4 ring-1 ring-inset ring-white/[0.07]"><span className="min-w-0 flex-1"><b className="block text-sm">{title}</b><small className="mt-1 block text-zinc-600">{description}</small></span><input type="checkbox" checked={Boolean(value[key])} onChange={(event) => setValue((current) => ({ ...current, [key]: event.target.checked }))} className="h-6 w-6 accent-primary" /></label>)}</div><button disabled={saving} onClick={() => void save(value)} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold active:scale-[0.96] disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}{saving ? 'Сохраняем…' : 'Сохранить'}</button></div>;
};

const StatusPill = ({ value }: { value?: string }) => <span className="shrink-0 rounded-full bg-white/[0.05] px-2.5 py-1 text-[10px] text-zinc-500 ring-1 ring-inset ring-white/[0.06]">{value === 'active' ? 'Активна' : value === 'archived' ? 'Архив' : value === 'approved' || value === 'completed' ? 'Готово' : value === 'draft' || value === 'draft_generated' || value === 'edited' ? 'Черновик' : value === 'planned' ? 'Запланировано' : value === 'fresh' ? 'Актуально' : value === 'running' || value === 'processing' ? 'В работе' : value === 'failed' || value === 'error' ? 'Ошибка' : value || 'Данные'}</span>;

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
  const activeKey: Tab = current === 'reviews' ? 'more' : current === 'operator' || current === 'feed' ? 'menu' : current === 'tasks' ? 'today' : current;
  const items: Array<[Tab, string, typeof Sparkles]> = [['today', 'Сегодня', Sparkles], ['more', 'Пути роста', LayoutGrid], ['progress', 'Результаты', TrendingUp], ['menu', 'Ещё', CircleEllipsis]];
  return <nav aria-label="Главное меню" className="fixed inset-x-0 bottom-0 z-20 mx-auto max-w-xl border-t border-white/[0.07] bg-zinc-950/90 px-2 pb-[calc(8px+env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl"><div className="grid grid-flow-col auto-cols-fr">{items.map(([key, label, Icon]) => <button key={key} type="button" aria-current={activeKey === key ? 'page' : undefined} onClick={() => setCurrent(key)} className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-[16px] text-[10px] transition-[color,transform,background-color] duration-150 active:scale-[0.96] ${activeKey === key ? 'bg-primary/10 text-primary' : 'text-zinc-600'}`}><Icon className="h-5 w-5" /><span>{label}</span></button>)}</div></nav>;
};

const Screen = ({ title, subtitle, children, action }: { title: string; subtitle: string; children: React.ReactNode; action?: React.ReactNode }) => <section className="px-4"><div className="mb-5 flex items-start gap-3"><div className="min-w-0 flex-1"><h1 className="text-balance text-2xl font-semibold tracking-[-0.04em]">{title}</h1><p className="mt-1 text-pretty text-sm leading-6 text-zinc-500">{subtitle}</p></div>{action}</div>{children}</section>;
const PrimaryButton = ({ children, onClick }: { children: React.ReactNode; onClick: () => void }) => <button onClick={onClick} className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96]">{children}<ChevronRight className="h-4 w-4" /></button>;
const TaskRow = ({ item, onClick }: { item: AttentionItem; onClick: () => void }) => <button onClick={onClick} className="mt-2 flex min-h-16 w-full items-center gap-3 rounded-[20px] bg-white/[0.035] px-4 py-3 text-left ring-1 ring-inset ring-white/[0.06] active:scale-[0.98]"><span className={`h-2.5 w-2.5 rounded-full ${item.severity === 'high' ? 'bg-rose-400' : item.severity === 'medium' ? 'bg-amber-400' : 'bg-emerald-400'}`} /><span className="min-w-0 flex-1"><b className="block truncate text-sm">{item.title || 'Задача'}</b><small className="mt-1 block truncate text-zinc-600">{item.description}</small>{item.progress !== undefined && item.progress !== null ? <span className="mt-2 block h-1 overflow-hidden rounded-full bg-white/[0.06]"><i className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(item.progress, 100))}%` }} /></span> : item.action_unavailable_reason ? <small className="mt-1 block truncate text-amber-300/70">{item.action_unavailable_reason}</small> : null}</span>{item.count ? <b className="tabular-nums text-zinc-400">{item.count}</b> : null}<ChevronRight className="h-4 w-4 text-zinc-700" /></button>;
const Segments = ({ value, setValue, options }: { value: string; setValue: (value: string) => void; options: string[][] }) => <div className="mb-4 flex gap-1 overflow-x-auto rounded-[18px] bg-white/[0.035] p-1 ring-1 ring-inset ring-white/[0.06]">{options.map(([key, label]) => <button key={key} onClick={() => setValue(key)} className={`min-h-11 flex-1 whitespace-nowrap rounded-[14px] px-3 text-xs font-semibold transition-[background-color,color,transform] active:scale-[0.96] ${value === key ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-600'}`}>{label}</button>)}</div>;
const ScopeRow = ({ icon: Icon, label, meta, selected = false, onClick }: { icon: typeof Star; label: string; meta: string; selected?: boolean; onClick: () => void }) => <button onClick={onClick} className={`flex min-h-16 w-full items-center gap-3 rounded-[20px] px-3 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-[background-color,transform] active:scale-[0.96] ${selected ? 'bg-primary/12' : 'bg-white/[0.04]'}`}><span className="grid h-10 w-10 place-items-center rounded-[14px] bg-primary/12 text-primary"><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-sm">{label}</b><small className="block truncate text-zinc-600">{meta}</small></span>{selected ? <Check className="h-4 w-4 text-primary" /> : <ChevronRight className="h-4 w-4 text-zinc-700" />}</button>;
const Empty = ({ icon: Icon, title, text }: { icon: typeof Star; title: string; text: string }) => <div className="mt-4 rounded-[24px] bg-white/[0.025] px-6 py-10 text-center ring-1 ring-inset ring-white/[0.06]"><Icon className="mx-auto h-7 w-7 text-zinc-700" /><h3 className="mt-3 font-semibold">{title}</h3><p className="mx-auto mt-2 max-w-xs text-pretty text-sm leading-6 text-zinc-600">{text}</p></div>;
const InlineError = ({ text }: { text: string }) => <div className="mb-3 flex gap-2 rounded-[16px] bg-rose-500/10 p-3 text-xs leading-5 text-rose-100 ring-1 ring-inset ring-rose-400/20"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{text}</div>;
const ReviewSkeleton = () => <div className="space-y-3">{[1, 2, 3].map((item) => <div key={item} className="h-44 animate-pulse rounded-[24px] bg-white/[0.04] motion-reduce:animate-none" />)}</div>;
const LoadingScreen = ({ slow }: { slow: boolean }) => <main className="grid min-h-[100dvh] place-items-center bg-zinc-950 px-8 text-center text-white"><div><span className="relative mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-zinc-900 ring-1 ring-inset ring-white/[0.08]"><Sparkles className="h-7 w-7 text-primary" /></span><h1 className="mt-6 text-xl font-semibold tracking-[-0.03em]">Собираем ваш рабочий день</h1>{slow ? <p className="mt-3 text-sm text-zinc-500">Сверяем задачи и источники…</p> : null}</div></main>;
const TelegramGate = () => <main className="grid min-h-[100dvh] place-items-center bg-zinc-950 p-6 text-center text-white"><div className="max-w-sm"><span className="mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-primary/12 text-primary ring-1 ring-inset ring-primary/20"><Send className="h-7 w-7" /></span><h1 className="mt-6 text-balance text-2xl font-semibold tracking-[-0.04em]">Откройте ЛокалОС в Telegram</h1><p className="mt-3 text-pretty text-sm leading-6 text-zinc-500">Вернитесь в чат с ЛокалОС и нажмите постоянную кнопку приложения внизу экрана.</p><a href="https://t.me/LocalOspro_bot" className="mt-6 flex min-h-12 items-center justify-center rounded-2xl bg-primary px-5 text-sm font-semibold text-white active:scale-[0.96]">Открыть бота</a></div></main>;

export default TelegramControlPage;
