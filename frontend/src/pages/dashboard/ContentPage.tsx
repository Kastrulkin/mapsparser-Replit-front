import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import {
  AlertCircle,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  ImageIcon,
  Eye,
  FileText,
  Lightbulb,
  Loader2,
  Plus,
  Sparkles,
  Star,
  Upload,
  Wand2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { API_URL } from '@/config/api';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type DashboardBusiness = {
  id: string;
  name?: string;
};

type DashboardOutletContext = {
  currentBusinessId?: string | null;
  currentBusiness?: DashboardBusiness | null;
};

type ScopeOption = {
  scope_type: string;
  scope_target_id: string;
  label: string;
  is_current?: boolean;
};

type ContentPlanContext = {
  scope?: {
    scope_options?: ScopeOption[];
  };
};

type PlanItem = {
  id: string;
  scheduled_for?: string;
  theme?: string;
  goal?: string;
  draft_text?: string;
  status?: string;
  content_type?: string;
  metadata_json?: Record<string, unknown>;
};

type PlanPayload = {
  id: string;
  title?: string;
  period_days?: number;
  scope_type?: string;
  scope_target_id?: string;
  period_start?: string;
  period_end?: string;
  items?: PlanItem[];
  items_count?: number;
  needs_draft_count?: number;
  ready_count?: number;
};

type SocialPost = {
  id: string;
  content_plan_item_id?: string;
  platform?: string;
  platform_label?: string;
  status?: string;
  scheduled_for?: string;
  published_at?: string;
  platform_text?: string;
  base_text?: string;
  last_error?: string;
  publish_mode?: string;
  external_account_id?: string;
  metadata_json?: {
    platform_rule_readiness?: {
      label?: string;
      message?: string;
      action_label?: string;
      severity?: string;
      status?: string;
    };
    queue_preflight_action_label?: string;
    queue_preflight_message_ru?: string;
  };
};

type SocialSummary = {
  total?: number;
  needs_review?: number;
  scheduled?: number;
  needs_supervised_publish?: number;
  needs_manual_publish?: number;
  published?: number;
  failed?: number;
};

type PhotoAsset = {
  id?: string;
  original_url?: string;
  category?: string;
  quality_score?: number;
  freshness_score?: number;
  orientation?: string;
  suitable_platforms?: string[];
  analysis_status?: string;
  analysis_error?: string;
  last_used_at?: string;
  metadata_json?: Record<string, unknown>;
  why?: string;
};

type MediaCoverage = {
  coverage_percent?: number;
  missing_text?: string;
  total_assets?: number;
  missing?: { key?: string; label?: string }[];
};

type MediaRecommendation = {
  status?: string;
  title?: string;
  message?: string;
  selected_asset?: PhotoAsset | null;
  alternatives?: PhotoAsset[];
  coverage?: {
    coverage_percent?: number;
    missing_text?: string;
    total_assets?: number;
  };
  platform_hints?: string[];
};

type CalendarView = 'month' | 'week' | 'list';
type ContentSection = 'calendar' | 'media';
type MediaFilter = 'all' | 'maps' | 'posts' | 'weak';
type ModalStep = 'setup' | 'preview';

type CreatePlanDraft = {
  goal: string;
  frequency: string;
  periodDays: number;
  contentTypes: Record<string, boolean>;
  channels: Record<string, boolean>;
};

const CONTENT_VIEW_STORAGE_KEY = 'localos_content_view_v1';
const CONTENT_SECTION_STORAGE_KEY = 'localos_content_section_v1';
const PLAN_GENERATION_MIN_DURATION_MS = 6500;

const CHANNELS = [
  { key: 'yandex_maps', label: 'Яндекс', mode: 'controlled' },
  { key: 'two_gis', label: '2ГИС', mode: 'controlled' },
  { key: 'google_business', label: 'Google', mode: 'api' },
  { key: 'telegram', label: 'Telegram', mode: 'api' },
  { key: 'vk', label: 'VK', mode: 'api' },
  { key: 'instagram', label: 'Instagram', mode: 'api' },
  { key: 'facebook', label: 'Facebook', mode: 'api' },
];

const CONTENT_TYPES = [
  { key: 'news', label: 'Новости' },
  { key: 'promos', label: 'Акции' },
  { key: 'faq', label: 'FAQ' },
  { key: 'reviews', label: 'Отзывы' },
  { key: 'cases', label: 'Кейсы' },
  { key: 'stories', label: 'Истории' },
  { key: 'seasonal', label: 'Сезонные публикации' },
  { key: 'reminders', label: 'Напоминания' },
];

const DEFAULT_CREATE_DRAFT: CreatePlanDraft = {
  goal: 'leads',
  frequency: 'standard',
  periodDays: 30,
  contentTypes: {
    news: true,
    promos: true,
    faq: true,
    reviews: true,
    cases: true,
    stories: true,
    seasonal: true,
    reminders: false,
  },
  channels: {
    yandex_maps: true,
    two_gis: true,
    google_business: true,
    telegram: true,
    vk: true,
    instagram: true,
    facebook: true,
  },
};

const normalizeIsoDate = (value?: string) => {
  const rawValue = String(value || '').trim();
  if (!rawValue) return '';
  if (/^\d{4}-\d{2}-\d{2}/.test(rawValue)) return rawValue.slice(0, 10);
  const parsed = new Date(rawValue);
  return Number.isNaN(parsed.getTime()) ? '' : toIsoDate(parsed);
};

const formatDate = (value?: string) => {
  if (!value) return 'Дата не выбрана';
  const normalized = normalizeIsoDate(value);
  const date = normalized ? new Date(`${normalized}T00:00:00`) : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(date);
};

const toIsoDate = (date: Date) => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const getMonthDays = (anchor: Date) => {
  const firstDay = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const start = new Date(firstDay);
  const dayOffset = (firstDay.getDay() + 6) % 7;
  start.setDate(firstDay.getDate() - dayOffset);
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
};

const getWeekDays = (anchor: Date) => {
  const start = new Date(anchor);
  const dayOffset = (anchor.getDay() + 6) % 7;
  start.setDate(anchor.getDate() - dayOffset);
  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
};

const getItemDateKey = (item: PlanItem) => normalizeIsoDate(item.scheduled_for);

const itemGenerationSource = (item?: PlanItem | null) => String(item?.metadata_json?.generation_source || '').trim();

const itemHasText = (item: PlanItem) => String(item.draft_text || '').trim().length > 0;

const itemHasUsableText = (item: PlanItem) => itemHasText(item) && itemGenerationSource(item) !== 'fallback';

const getPostStatusLabel = (status?: string) => {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'published') return 'Опубликовано';
  if (normalized === 'queued') return 'Запланировано';
  if (normalized === 'approved') return 'Утверждено';
  if (normalized === 'needs_review') return 'Нужно проверить';
  if (normalized === 'needs_supervised_publish') return 'Нужно разместить';
  if (normalized === 'needs_manual_publish') return 'Нужно разместить';
  if (normalized === 'failed') return 'Не удалось';
  return 'Черновик';
};

const getPostNextAction = (post: SocialPost) => {
  const normalized = String(post.status || '').toLowerCase();
  if (normalized === 'needs_review') return 'Проверьте текст и нажмите «Утвердить».';
  if (normalized === 'approved') return 'Можно поставить в расписание.';
  if (normalized === 'queued') return 'Ждёт своей даты.';
  if (normalized === 'publishing') return 'Публикуем сейчас.';
  if (normalized === 'published') return 'Публикация вышла.';
  if (normalized === 'needs_supervised_publish') return 'Откройте контролируемое размещение.';
  if (normalized === 'needs_manual_publish') return 'Нужно разместить вручную.';
  if (normalized === 'failed') return post.last_error || 'Нужно обновить подключение или попробовать снова.';
  return 'Сначала проверьте текст.';
};

const getChannelStatusLabel = (status?: string) => {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'approved') return 'Текст готов';
  return getPostStatusLabel(status);
};

const getChannelNextAction = (post: SocialPost) => {
  const readiness = getPostPlatformReadiness(post);
  if (readiness?.message) return readiness.message;
  const normalized = String(post.status || '').toLowerCase();
  if (normalized === 'approved') return 'Можно планировать. Подключение проверим перед публикацией.';
  if (normalized === 'queued') return 'Запланировано. Если канал не подключён, появится понятный шаг.';
  return getPostNextAction(post);
};

const getPostPlatformReadiness = (post: SocialPost) => {
  const metadata = post.metadata_json || {};
  const readiness = metadata.platform_rule_readiness;
  if (readiness && typeof readiness === 'object') return readiness;
  const message = String(metadata.queue_preflight_message_ru || '').trim();
  const actionLabel = String(metadata.queue_preflight_action_label || '').trim();
  if (message || actionLabel) {
    return {
      label: actionLabel || 'Что сделать',
      message,
      action_label: actionLabel,
      severity: 'blocking',
    };
  }
  return null;
};

const getChannelStatusDisplay = (post: SocialPost) => {
  const readiness = getPostPlatformReadiness(post);
  const normalized = String(post.status || '').toLowerCase();
  if (readiness?.label && !['queued', 'published'].includes(normalized)) return readiness.label;
  return getChannelStatusLabel(post.status);
};

const getPrimaryBlockedPostMessage = (posts: SocialPost[]) => {
  const blockedPost = posts.find((post) => isAutomaticSendBlockedStatus(post.status) || isPlatformRuleBlocked(post));
  if (!blockedPost) return '';
  const readiness = getPostPlatformReadiness(blockedPost);
  if (readiness?.message) return readiness.message;
  return String(blockedPost.last_error || '').trim();
};

const isAutomaticSendBlockedStatus = (status?: string) => {
  const normalized = String(status || '').toLowerCase();
  return normalized === 'needs_manual_publish' || normalized === 'failed';
};

const isPlatformRuleBlocked = (post: SocialPost) => {
  const readiness = getPostPlatformReadiness(post);
  return Boolean(readiness && String(readiness.severity || '').toLowerCase() === 'blocking');
};

const isQueuedOrHandledStatus = (status?: string) => {
  const normalized = String(status || '').toLowerCase();
  return normalized === 'queued' || normalized === 'needs_supervised_publish' || normalized === 'published';
};

const getItemStatusLabel = (item: PlanItem, posts: SocialPost[]) => {
  if (posts.some((post) => String(post.status || '') === 'failed')) return 'Не удалось';
  if (posts.some((post) => String(post.status || '') === 'needs_supervised_publish' || String(post.status || '') === 'needs_manual_publish')) {
    return 'Нужно разместить';
  }
  if (posts.some((post) => String(post.status || '') === 'needs_review')) return 'Нужно проверить';
  if (posts.some((post) => String(post.status || '') === 'queued')) return 'Запланировано';
  if (posts.length > 0 && posts.every((post) => String(post.status || '') === 'published')) return 'Опубликовано';
  if (itemHasUsableText(item)) return 'Нужно проверить';
  return 'Черновик';
};

const getCalendarItemState = (item: PlanItem, posts: SocialPost[]) => {
  const statuses = posts.map((post) => String(post.status || '').toLowerCase());
  if (statuses.includes('failed')) {
    return { status: 'Не удалось', action: 'Исправить' };
  }
  if (statuses.includes('needs_supervised_publish') || statuses.includes('needs_manual_publish')) {
    return { status: 'Текст утверждён', action: 'Нужно разместить' };
  }
  if (statuses.includes('queued')) {
    return { status: 'Запланировано', action: 'Ждёт даты' };
  }
  if (posts.length > 0 && statuses.every((status) => status === 'published')) {
    return { status: 'Опубликовано', action: 'Готово' };
  }
  if (statuses.includes('approved')) {
    return { status: 'Текст утверждён', action: 'Выберите каналы' };
  }
  if (statuses.includes('needs_review')) {
    return { status: 'Текст готов', action: 'Утвердить текст' };
  }
  if (itemHasUsableText(item)) {
    return { status: 'Текст готов', action: 'Подготовить каналы' };
  }
  return { status: 'Черновик', action: 'Написать текст' };
};

const getStatusClassName = (label: string) => {
  if (label === 'Опубликовано') return 'bg-emerald-50 text-emerald-700 ring-emerald-100';
  if (label === 'Запланировано') return 'bg-blue-50 text-blue-700 ring-blue-100';
  if (label === 'Утверждено') return 'bg-violet-50 text-violet-700 ring-violet-100';
  if (label === 'Текст утверждён') return 'bg-emerald-50 text-emerald-700 ring-emerald-100';
  if (label === 'Текст готов') return 'bg-sky-50 text-sky-700 ring-sky-100';
  if (label === 'Выберите каналы') return 'bg-amber-50 text-amber-800 ring-amber-100';
  if (label === 'Утвердить текст') return 'bg-amber-50 text-amber-800 ring-amber-100';
  if (label === 'Подготовить каналы') return 'bg-slate-100 text-slate-700 ring-slate-200';
  if (label === 'Написать текст') return 'bg-slate-100 text-slate-600 ring-slate-200';
  if (label === 'Ждёт даты') return 'bg-blue-50 text-blue-700 ring-blue-100';
  if (label === 'Готово') return 'bg-emerald-50 text-emerald-700 ring-emerald-100';
  if (label === 'Исправить') return 'bg-red-50 text-red-700 ring-red-100';
  if (label === 'Нужно проверить') return 'bg-amber-50 text-amber-800 ring-amber-100';
  if (label === 'Нужно фото') return 'bg-amber-50 text-amber-800 ring-amber-100';
  if (label === 'Фото лучше добавить') return 'bg-amber-50 text-amber-800 ring-amber-100';
  if (label === 'Нужен другой формат') return 'bg-red-50 text-red-700 ring-red-100';
  if (label === 'Сократите текст') return 'bg-red-50 text-red-700 ring-red-100';
  if (label === 'Сократите подпись') return 'bg-red-50 text-red-700 ring-red-100';
  if (label === 'Нужно разместить') return 'bg-orange-50 text-orange-800 ring-orange-100';
  if (label === 'Не удалось') return 'bg-red-50 text-red-700 ring-red-100';
  return 'bg-slate-100 text-slate-600 ring-slate-200';
};

const getSelectedCount = (values: Record<string, boolean>) => Object.values(values).filter(Boolean).length;

const PLATFORM_LABELS: Record<string, string> = {
  facebook: 'Facebook',
  google_business: 'Google',
  instagram: 'Instagram',
  telegram: 'Telegram',
  two_gis: '2ГИС',
  vk: 'VK',
  yandex_maps: 'Яндекс',
};

const PHOTO_CATEGORY_LABELS: Record<string, string> = {
  atmosphere: 'Атмосфера',
  child: 'Ребёнок',
  children: 'Дети',
  classroom: 'Учебное пространство',
  details: 'Детали',
  entrance: 'Вход и вывеска',
  event: 'Событие',
  events: 'События',
  facade: 'Фасад',
  interior: 'Интерьер',
  interior_team_process: 'Интерьер, команда и процесс',
  people: 'Люди',
  process: 'Процесс',
  product: 'Продукт',
  result: 'Результат',
  service: 'Услуга',
  signboard: 'Вывеска',
  team: 'Команда',
  unknown: 'Фото бизнеса',
  workspace: 'Рабочее пространство',
};

const PHOTO_CATEGORY_PART_LABELS: Record<string, string> = {
  atmosphere: 'атмосфера',
  child: 'ребёнок',
  children: 'дети',
  classroom: 'учебное пространство',
  details: 'детали',
  entrance: 'вход',
  event: 'событие',
  events: 'события',
  facade: 'фасад',
  interior: 'интерьер',
  people: 'люди',
  process: 'процесс',
  product: 'продукт',
  result: 'результат',
  service: 'услуга',
  signboard: 'вывеска',
  team: 'команда',
  workspace: 'рабочее пространство',
};

const formatPlatformLabel = (value?: string) => {
  const key = String(value || '').trim();
  if (!key) return 'Канал';
  return PLATFORM_LABELS[key] || key;
};

const formatPhotoCategoryLabel = (value?: string) => {
  const key = String(value || '').trim();
  if (!key) return 'Фото бизнеса';
  if (PHOTO_CATEGORY_LABELS[key]) return PHOTO_CATEGORY_LABELS[key];
  const parts = key
    .split('_')
    .map((part) => PHOTO_CATEGORY_PART_LABELS[part] || part)
    .filter(Boolean);
  if (parts.length === 0) return 'Фото бизнеса';
  if (parts.length === 1) return parts[0][0]?.toUpperCase() + parts[0].slice(1);
  return `${parts.slice(0, -1).join(', ')} и ${parts[parts.length - 1]}`.replace(/^./, (letter) => letter.toUpperCase());
};

const groupPostsByItem = (posts: SocialPost[]) => {
  return posts.reduce<Record<string, SocialPost[]>>((acc, post) => {
    const itemId = String(post.content_plan_item_id || '').trim();
    if (!itemId) return acc;
    acc[itemId] = [...(acc[itemId] || []), post];
    return acc;
  }, {});
};

const platformShortLabel = (post: SocialPost) => {
  const label = String(post.platform_label || post.platform || '').trim();
  return formatPlatformLabel(label);
};

export function ContentPage() {
  const navigate = useNavigate();
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardOutletContext>();
  const [context, setContext] = useState<ContentPlanContext | null>(null);
  const [plans, setPlans] = useState<PlanPayload[]>([]);
  const [currentPlan, setCurrentPlan] = useState<PlanPayload | null>(null);
  const [socialPosts, setSocialPosts] = useState<SocialPost[]>([]);
  const [socialSummary, setSocialSummary] = useState<SocialSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyAction, setBusyAction] = useState('');
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [view, setView] = useState<CalendarView>(() => {
    if (typeof window === 'undefined') return 'month';
    const saved = window.localStorage.getItem(CONTENT_VIEW_STORAGE_KEY);
    return saved === 'week' || saved === 'list' || saved === 'month' ? saved : 'month';
  });
  const [section, setSection] = useState<ContentSection>(() => {
    if (typeof window === 'undefined') return 'calendar';
    const saved = window.localStorage.getItem(CONTENT_SECTION_STORAGE_KEY);
    return saved === 'media' ? 'media' : 'calendar';
  });
  const [selectedItemId, setSelectedItemId] = useState('');
  const [channelDetailsOpen, setChannelDetailsOpen] = useState(false);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [themeEdits, setThemeEdits] = useState<Record<string, string>>({});
  const [dateEdits, setDateEdits] = useState<Record<string, string>>({});
  const [mediaRecommendations, setMediaRecommendations] = useState<Record<string, MediaRecommendation>>({});
  const [mediaLoadingItemId, setMediaLoadingItemId] = useState('');
  const [mediaAssets, setMediaAssets] = useState<PhotoAsset[]>([]);
  const [mediaCoverage, setMediaCoverage] = useState<MediaCoverage | null>(null);
  const [mediaLoading, setMediaLoading] = useState(false);
  const [mediaUploading, setMediaUploading] = useState(false);
  const [mediaUploadProgress, setMediaUploadProgress] = useState('');
  const [mediaAnalyzingId, setMediaAnalyzingId] = useState('');
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>('all');
  const [mediaError, setMediaError] = useState('');
  const [mediaActionMessage, setMediaActionMessage] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [createStep, setCreateStep] = useState<ModalStep>('setup');
  const [createDraft, setCreateDraft] = useState<CreatePlanDraft>(DEFAULT_CREATE_DRAFT);
  const [generating, setGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationCards, setGenerationCards] = useState(0);
  const mediaUploadInputRef = useRef<HTMLInputElement | null>(null);

  const items = useMemo(() => currentPlan?.items || [], [currentPlan]);
  const postsByItem = useMemo(() => groupPostsByItem(socialPosts), [socialPosts]);
  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedItemId) || null,
    [items, selectedItemId],
  );
  const selectedPosts = selectedItem ? postsByItem[selectedItem.id] || [] : [];
  const selectedScopeOption = useMemo(() => {
    const options = context?.scope?.scope_options || [];
    return options.find((option) => option.is_current) || options[0] || null;
  }, [context]);

  const filledDays = useMemo(() => {
    const filled = new Set(items.filter((item) => itemHasUsableText(item)).map(getItemDateKey).filter(Boolean));
    return filled.size;
  }, [items]);
  const totalDays = Number(currentPlan?.period_days || 30);
  const needsReviewCount = Number(socialSummary?.needs_review || 0) || items.filter((item) => itemHasUsableText(item) && getItemStatusLabel(item, postsByItem[item.id] || []) === 'Нужно проверить').length;
  const nextItem = useMemo(() => {
    const today = toIsoDate(new Date());
    return [...items]
      .filter((item) => getItemDateKey(item) >= today)
      .sort((left, right) => getItemDateKey(left).localeCompare(getItemDateKey(right)))[0] || null;
  }, [items]);
  const nearestReviewItem = useMemo(() => {
    const today = toIsoDate(new Date());
    return [...items]
      .filter((item) => {
        const status = getItemStatusLabel(item, postsByItem[item.id] || []);
        return status === 'Нужно проверить' || status === 'Черновик' || getItemDateKey(item) >= today;
      })
      .sort((left, right) => getItemDateKey(left).localeCompare(getItemDateKey(right)))[0] || null;
  }, [items, postsByItem]);
  const reviewReadyPosts = useMemo(
    () => socialPosts.filter((post) => String(post.status || '') === 'needs_review'),
    [socialPosts],
  );
  const approvedPosts = useMemo(
    () => socialPosts.filter((post) => String(post.status || '') === 'approved'),
    [socialPosts],
  );
  const monthDays = useMemo(() => getMonthDays(new Date()), []);
  const weekDays = useMemo(() => getWeekDays(new Date()), []);
  const visibleDays = view === 'week' ? weekDays : monthDays;
  const calendarItemsByDate = useMemo(() => {
    return items.reduce<Record<string, PlanItem[]>>((acc, item) => {
      const key = getItemDateKey(item);
      if (!key) return acc;
      acc[key] = [...(acc[key] || []), item];
      return acc;
    }, {});
  }, [items]);
  const filteredMediaAssets = useMemo(() => {
    const mapPlatforms = new Set(['yandex_maps', 'two_gis', 'google_business']);
    const postPlatforms = new Set(['telegram', 'vk', 'instagram', 'facebook']);
    return mediaAssets.filter((asset) => {
      const platforms = Array.isArray(asset.suitable_platforms) ? asset.suitable_platforms : [];
      const quality = Number(asset.quality_score || 0);
      if (mediaFilter === 'maps') return platforms.some((platform) => mapPlatforms.has(platform)) || ['entrance', 'interior', 'result', 'process'].includes(String(asset.category || ''));
      if (mediaFilter === 'posts') return platforms.some((platform) => postPlatforms.has(platform)) || quality >= 45;
      if (mediaFilter === 'weak') return quality > 0 && quality < 45 || String(asset.analysis_status || '') === 'analysis_failed';
      return true;
    });
  }, [mediaAssets, mediaFilter]);

  const loadSocialPosts = async (planId: string) => {
    const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}/social-posts`, { method: 'GET' });
    const posts = Array.isArray(response.posts) ? response.posts : [];
    setSocialPosts(posts);
    setSocialSummary(response.summary || null);
    return posts;
  };

  const loadCurrentPlan = async (planId: string) => {
    const planResponse = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}`, { method: 'GET' });
    const plan = planResponse.plan || null;
    setCurrentPlan(plan);
    if (plan?.id) {
      await loadSocialPosts(plan.id);
    }
    return plan;
  };

  const loadContent = async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    setError('');
    try {
      const contextResponse = await newAuth.makeRequest(`/content-plans/context?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      setContext(contextResponse.context || null);
      const plansResponse = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      const nextPlans = Array.isArray(plansResponse.plans) ? plansResponse.plans : [];
      setPlans(nextPlans);
      if (nextPlans.length > 0) {
        await loadCurrentPlan(nextPlans[0].id);
      } else {
        setCurrentPlan(null);
        setSocialPosts([]);
        setSocialSummary(null);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить контент');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadContent();
  }, [currentBusinessId]);

  useEffect(() => {
    setChannelDetailsOpen(false);
  }, [selectedItemId]);

  useEffect(() => {
    if (!selectedItemId || !currentBusinessId) return;
    if (mediaRecommendations[selectedItemId]) return;
    void loadMediaRecommendation(selectedItemId);
  }, [selectedItemId, currentBusinessId]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(CONTENT_VIEW_STORAGE_KEY, view);
  }, [view]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(CONTENT_SECTION_STORAGE_KEY, section);
  }, [section]);

  useEffect(() => {
    if (section !== 'media' || !currentBusinessId) return;
    void loadMediaAssets();
  }, [section, currentBusinessId]);

  useEffect(() => {
    if (!generating) return;
    const interval = window.setInterval(() => {
      setGenerationProgress((value) => Math.min(value + 7, 92));
      setGenerationCards((value) => Math.min(value + 2, 28));
    }, 420);
    return () => window.clearInterval(interval);
  }, [generating]);

  const openItem = (item: PlanItem) => {
    setError('');
    setActionMessage('');
    setSelectedItemId(item.id);
    setDraftEdits((prev) => ({ ...prev, [item.id]: String(item.draft_text || '') }));
    setThemeEdits((prev) => ({ ...prev, [item.id]: String(item.theme || item.goal || '') }));
    setDateEdits((prev) => ({ ...prev, [item.id]: getItemDateKey(item) }));
  };

  const loadMediaRecommendation = async (itemId: string) => {
    if (!currentBusinessId || !itemId) return;
    setMediaLoadingItemId(itemId);
    try {
      const response = await newAuth.makeRequest(`/media-intelligence/posts/${encodeURIComponent(itemId)}/recommendation?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      if (response?.recommendation) {
        setMediaRecommendations((prev) => ({ ...prev, [itemId]: response.recommendation }));
      }
    } catch (mediaError) {
      setMediaRecommendations((prev) => ({
        ...prev,
        [itemId]: {
          status: 'unavailable',
          title: 'Фото пока не подобрано',
          message: mediaError instanceof Error ? mediaError.message : 'LocalOS не смог проверить фото для публикации.',
        },
      }));
    } finally {
      setMediaLoadingItemId('');
    }
  };

  const photoImageSrc = (asset: PhotoAsset) => {
    const url = String(asset.original_url || '').trim();
    if (!url) return '';
    if (url.startsWith('/')) return url;
    return url;
  };

  const loadMediaAssets = async () => {
    if (!currentBusinessId) return;
    setMediaLoading(true);
    setMediaError('');
    try {
      const response = await newAuth.makeRequest(`/media-intelligence/photos?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      setMediaAssets(Array.isArray(response.photos) ? response.photos : []);
      setMediaCoverage(response.coverage || null);
    } catch (mediaLoadError) {
      setMediaError(mediaLoadError instanceof Error ? mediaLoadError.message : 'Не удалось загрузить медиатеку');
    } finally {
      setMediaLoading(false);
    }
  };

  const analyzeMediaAsset = async (assetId?: string) => {
    if (!currentBusinessId || !assetId) return;
    setMediaAnalyzingId(assetId);
    setMediaError('');
    try {
      await newAuth.makeRequest(`/media-intelligence/photos/${encodeURIComponent(assetId)}/analyze`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      await loadMediaAssets();
      setMediaActionMessage('Фото проанализировано. LocalOS учтёт его в рекомендациях к публикациям.');
    } catch (analyzeError) {
      setMediaError(analyzeError instanceof Error ? analyzeError.message : 'Не удалось проанализировать фото');
      await loadMediaAssets();
    } finally {
      setMediaAnalyzingId('');
    }
  };

  const uploadSingleMediaPhoto = async (file: File) => {
    if (!currentBusinessId) throw new Error('Бизнес не выбран');
    const formData = new FormData();
    formData.append('business_id', currentBusinessId);
    formData.append('file', file);
    const token = window.localStorage.getItem('auth_token') || '';
    const response = await fetch(`${API_URL}/api/media-intelligence/photos/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: formData,
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || data.message || `Не удалось загрузить ${file.name}`);
    }
    return data.photo as PhotoAsset;
  };

  const uploadMediaPhotos = async (fileList?: FileList | null) => {
    if (!currentBusinessId || !fileList || fileList.length === 0) return;
    const files = Array.from(fileList).filter((file) => file.type.startsWith('image/'));
    if (files.length === 0) {
      setMediaError('Выберите фото для загрузки');
      return;
    }
    setMediaUploading(true);
    setMediaError('');
    setMediaActionMessage('');
    setMediaUploadProgress('');
    const uploaded: PhotoAsset[] = [];
    const failed: string[] = [];
    try {
      for (const [index, file] of files.entries()) {
        setMediaUploadProgress(`Загружаем ${index + 1} из ${files.length}`);
        try {
          const photo = await uploadSingleMediaPhoto(file);
          uploaded.push(photo);
          setMediaUploadProgress(`Анализируем ${index + 1} из ${files.length}`);
          await analyzeMediaAsset(photo?.id);
        } catch (uploadError) {
          failed.push(`${file.name}: ${uploadError instanceof Error ? uploadError.message : 'не удалось загрузить'}`);
        }
      }
      await loadMediaAssets();
      if (failed.length > 0) {
        setMediaError(`Загружено ${uploaded.length} из ${files.length}. Не удалось: ${failed.slice(0, 3).join('; ')}${failed.length > 3 ? '...' : ''}`);
      } else {
        setMediaActionMessage(`Загружено и проанализировано фото: ${uploaded.length}. LocalOS учтёт их в рекомендациях к публикациям.`);
      }
    } finally {
      setMediaUploading(false);
      setMediaUploadProgress('');
      if (mediaUploadInputRef.current) {
        mediaUploadInputRef.current.value = '';
      }
    }
  };

  const recordSelectedPhotoUsage = async () => {
    if (!selectedItem || !currentBusinessId) return;
    const recommendation = mediaRecommendations[selectedItem.id];
    const assetId = recommendation?.selected_asset?.id;
    if (!assetId) {
      setError('Сначала загрузите или выберите подходящее фото.');
      return;
    }
    setBusyAction('photo-usage');
    setError('');
    try {
      await newAuth.makeRequest(`/media-intelligence/photos/${encodeURIComponent(assetId)}/usage`, {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          usage_type: 'publication',
          target_id: selectedItem.id,
          metadata: {
            source: 'content_publication_drawer',
            theme: selectedItem.theme || selectedItem.goal || '',
          },
        }),
      });
      setActionMessage('Фото сохранено для публикации. Повторный анализ и списание кредитов не нужны.');
      await loadMediaRecommendation(selectedItem.id);
      if (section === 'media') await loadMediaAssets();
    } catch (usageError) {
      setError(usageError instanceof Error ? usageError.message : 'Не удалось сохранить фото для публикации');
    } finally {
      setBusyAction('');
    }
  };

  const saveSelectedItem = async () => {
    if (!selectedItem) return;
    setBusyAction('save');
    setError('');
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(selectedItem.id)}`, {
        method: 'PUT',
        body: JSON.stringify({
          theme: themeEdits[selectedItem.id],
          scheduled_for: dateEdits[selectedItem.id],
          draft_text: draftEdits[selectedItem.id],
        }),
      });
      const plan = response.plan || null;
      setCurrentPlan(plan);
      if (plan?.id) await loadSocialPosts(plan.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Не удалось сохранить публикацию');
    } finally {
      setBusyAction('');
    }
  };

  const generateSelectedDraft = async () => {
    if (!selectedItem) return;
    setBusyAction('generate-draft');
    setError('');
    setActionMessage('');
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(selectedItem.id)}/generate-draft`, {
        method: 'POST',
        body: JSON.stringify({ language: 'ru' }),
      });
      const plan = response.plan || null;
      setCurrentPlan(plan);
      if (plan?.id) await loadSocialPosts(plan.id);
      const refreshedItem = Array.isArray(plan?.items)
        ? plan.items.find((nextItem: PlanItem) => nextItem.id === selectedItem.id)
        : null;
      setDraftEdits((prev) => ({ ...prev, [selectedItem.id]: String(refreshedItem?.draft_text || '') }));
      const generation = response.generation || {};
      const refreshedText = String(refreshedItem?.draft_text || '').trim();
      const refreshedGenerationSource = itemGenerationSource(refreshedItem);
      const hasGeneratedText = Boolean(refreshedText) && refreshedGenerationSource !== 'fallback';
      if (generation.success === false || generation.source === 'fallback' || !hasGeneratedText) {
        setActionMessage('');
        setError(String(generation.message || 'Не удалось написать текст. Попробуйте ещё раз.'));
      } else {
        setActionMessage(String(generation.message || 'Текст готов. Проверьте его и утвердите публикацию.'));
      }
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : 'Не удалось сгенерировать текст');
    } finally {
      setBusyAction('');
    }
  };

  const openNearestReview = () => {
    const target = nearestReviewItem || nextItem || items[0];
    if (!target) return;
    openItem(target);
  };

  const approveReadyPosts = async () => {
    if (!currentPlan?.id || reviewReadyPosts.length === 0) return;
    setBusyAction('bulk-approve');
    setError('');
    setActionMessage('');
    try {
      await newAuth.makeRequest('/social-posts/bulk-approve', {
        method: 'POST',
        body: JSON.stringify({ post_ids: reviewReadyPosts.map((post) => post.id) }),
      });
      await loadSocialPosts(currentPlan.id);
      setActionMessage(`Утверждено публикаций: ${reviewReadyPosts.length}. Следующий шаг — запланировать.`);
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : 'Не удалось утвердить публикации');
    } finally {
      setBusyAction('');
    }
  };

  const queueApprovedPosts = async () => {
    if (!currentPlan?.id || approvedPosts.length === 0) return;
    setBusyAction('bulk-queue');
    setError('');
    setActionMessage('');
    try {
      await newAuth.makeRequest('/social-posts/bulk-queue', {
        method: 'POST',
        body: JSON.stringify({ post_ids: approvedPosts.map((post) => post.id) }),
      });
      await loadSocialPosts(currentPlan.id);
      setActionMessage(`Запланировано публикаций: ${approvedPosts.length}. LocalOS выполнит их по датам.`);
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : 'Не удалось поставить публикации в расписание');
    } finally {
      setBusyAction('');
    }
  };

  const prepareSelectedItem = async () => {
    if (!selectedItem || !currentPlan?.id) return [];
    setBusyAction('prepare');
    setError('');
    try {
      await newAuth.makeRequest('/content-plans/social-posts/bulk-prepare', {
        method: 'POST',
        body: JSON.stringify({ item_ids: [selectedItem.id] }),
      });
      return await loadSocialPosts(currentPlan.id);
    } catch (prepareError) {
      setError(prepareError instanceof Error ? prepareError.message : 'Не удалось подготовить каналы');
      return [];
    } finally {
      setBusyAction('');
    }
  };

  const approveSelectedItem = async () => {
    if (!selectedItem || !currentPlan?.id) return;
    setBusyAction('approve');
    setError('');
    try {
      let posts = postsByItem[selectedItem.id] || [];
      if (posts.length === 0) {
        const preparedPosts = await prepareSelectedItem();
        posts = preparedPosts.filter((post) => post.content_plan_item_id === selectedItem.id);
      }
      const postIds = posts.map((post) => post.id).filter(Boolean);
      if (postIds.length === 0) return;
      await newAuth.makeRequest('/social-posts/bulk-approve', {
        method: 'POST',
        body: JSON.stringify({ post_ids: postIds }),
      });
      await loadSocialPosts(currentPlan.id);
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : 'Не удалось утвердить публикации');
    } finally {
      setBusyAction('');
    }
  };

  const queueSelectedItem = async () => {
    if (!selectedItem || !currentPlan?.id) return;
    setBusyAction('queue');
    setError('');
    setActionMessage('');
    try {
      const posts = postsByItem[selectedItem.id] || [];
      const postIds = posts
        .filter((post) => String(post.status || '').toLowerCase() === 'approved')
        .map((post) => post.id)
        .filter(Boolean);
      if (postIds.length === 0) {
        if (posts.length === 0) {
          setError('Сначала нажмите «Подготовить каналы». После этого LocalOS создаст варианты для площадок.');
        } else if (posts.some((post) => String(post.status || '').toLowerCase() === 'needs_review')) {
          setError('Сначала проверьте текст и нажмите «Утвердить». После этого появится расписание.');
        } else if (posts.some((post) => isAutomaticSendBlockedStatus(post.status) || isPlatformRuleBlocked(post))) {
          const blockedPosts = posts.filter((post) => isAutomaticSendBlockedStatus(post.status) || isPlatformRuleBlocked(post));
          const blockedLabels = blockedPosts.map((post) => platformShortLabel(post)).filter(Boolean).join(', ');
          const firstError = getPrimaryBlockedPostMessage(blockedPosts);
          setError(
            firstError
              ? `${blockedLabels || 'Каналы'} не готовы: ${firstError}`
              : `${blockedLabels || 'Каналы'} не готовы. Подключите API-каналы или используйте контролируемое размещение.`,
          );
        } else if (posts.some((post) => isQueuedOrHandledStatus(post.status))) {
          setError('Эта публикация уже поставлена в расписание или ждёт контролируемого размещения.');
        } else {
          setError('Сначала выберите и подготовьте каналы для этой публикации.');
        }
        return;
      }
      const response = await newAuth.makeRequest('/social-posts/bulk-queue', {
        method: 'POST',
        body: JSON.stringify({ post_ids: postIds }),
      });
      const queuedPosts = Array.isArray(response.posts) ? response.posts : [];
      const blockedPosts = queuedPosts.filter((post: SocialPost) => isAutomaticSendBlockedStatus(post.status) || isPlatformRuleBlocked(post));
      const handledPosts = queuedPosts.filter((post: SocialPost) => isQueuedOrHandledStatus(post.status));
      await loadSocialPosts(currentPlan.id);
      if (blockedPosts.length > 0) {
        const blockedLabels = blockedPosts.map((post: SocialPost) => platformShortLabel(post)).filter(Boolean).join(', ');
        const firstError = getPrimaryBlockedPostMessage(blockedPosts);
        setError(
          firstError
            ? `${blockedLabels || 'Каналы'} не готовы: ${firstError}`
            : `${blockedLabels || 'Каналы'} не готовы. Сначала подключите API-ключи, выберите канал или разрешите контролируемое размещение.`,
        );
        return;
      }
      if (handledPosts.length > 0) {
        setActionMessage(`Отправка запланирована: ${handledPosts.length}.`);
      }
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : 'Не удалось поставить в расписание');
    } finally {
      setBusyAction('');
    }
  };

  const createPlan = async () => {
    if (!currentBusinessId) return;
    const generationStartedAt = Date.now();
    setGenerating(true);
    setCreateOpen(false);
    setGenerationProgress(8);
    setGenerationCards(2);
    setError('');
    try {
      const response = await newAuth.makeRequest('/content-plans/generate', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          scope_type: selectedScopeOption?.scope_type || 'single_business',
          scope_target_id: selectedScopeOption?.scope_target_id || currentBusinessId,
          period_days: createDraft.periodDays,
          density: createDraft.frequency === 'active' ? 'active' : createDraft.frequency === 'light' ? 'light' : 'standard',
          content_mix: {
            services: true,
            seo: true,
            sales: Boolean(createDraft.contentTypes.promos),
            audit: Boolean(createDraft.contentTypes.faq || createDraft.contentTypes.reviews),
            seasonal: Boolean(createDraft.contentTypes.seasonal),
          },
        }),
      });
      const plan = response.plan || null;
      setCurrentPlan(plan);
      if (plan?.id) {
        await loadSocialPosts(plan.id);
      }
      const plansResponse = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      setPlans(Array.isArray(plansResponse.plans) ? plansResponse.plans : []);
      const elapsed = Date.now() - generationStartedAt;
      const remainingDelay = Math.max(750, PLAN_GENERATION_MIN_DURATION_MS - elapsed);
      window.setTimeout(() => {
        setGenerationProgress(100);
        setGenerationCards(Math.max(32, createDraft.periodDays));
        setGenerating(false);
      }, remainingDelay);
    } catch (createError) {
      setGenerating(false);
      setError(createError instanceof Error ? createError.message : 'Не удалось создать план');
    }
  };

  const toggleContentType = (key: string) => {
    setCreateDraft((prev) => ({
      ...prev,
      contentTypes: { ...prev.contentTypes, [key]: !prev.contentTypes[key] },
    }));
  };

  const toggleChannel = (key: string) => {
    setCreateDraft((prev) => ({
      ...prev,
      channels: { ...prev.channels, [key]: !prev.channels[key] },
    }));
  };

  const renderPlanModal = () => (
    <Dialog open={createOpen} onOpenChange={setCreateOpen}>
      <DialogContent className="max-w-3xl rounded-3xl border-slate-200 p-0">
        <div className="p-6">
          <DialogHeader>
            <DialogTitle className="text-2xl">Создать контент-план</DialogTitle>
            <DialogDescription>
              LocalOS подготовит публикации для месяца. Наружу ничего не отправится без проверки.
            </DialogDescription>
          </DialogHeader>

          {createStep === 'setup' ? (
            <div className="mt-6 grid gap-5">
              <div>
                <div className="text-sm font-semibold text-slate-900">Цель</div>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {[
                    ['leads', 'Получать заявки'],
                    ['awareness', 'Напоминать о себе'],
                    ['promos', 'Продвигать акции'],
                    ['presence', 'Поддерживать активность'],
                  ].map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setCreateDraft((prev) => ({ ...prev, goal: key }))}
                      className={cn(
                        'rounded-2xl border px-4 py-3 text-left text-sm font-medium transition-colors',
                        createDraft.goal === key ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Частота</div>
                  <div className="mt-2 grid gap-2">
                    {[
                      ['light', '2 раза в неделю'],
                      ['standard', '3 раза в неделю'],
                      ['active', 'Ежедневно'],
                    ].map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setCreateDraft((prev) => ({ ...prev, frequency: key }))}
                        className={cn(
                          'rounded-2xl border px-4 py-3 text-left text-sm transition-colors',
                          createDraft.frequency === key ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900">Период</div>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {[14, 30, 60, 90, 180, 365].map((days) => (
                      <button
                        key={days}
                        type="button"
                        onClick={() => setCreateDraft((prev) => ({ ...prev, periodDays: days }))}
                        className={cn(
                          'rounded-2xl border px-3 py-3 text-sm font-medium transition-colors',
                          createDraft.periodDays === days ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
                        )}
                      >
                        {days} дн.
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <div className="text-sm font-semibold text-slate-900">Что создавать</div>
                <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {CONTENT_TYPES.map((type) => (
                    <button
                      key={type.key}
                      type="button"
                      onClick={() => toggleContentType(type.key)}
                      className={cn(
                        'flex items-center gap-2 rounded-2xl border px-3 py-3 text-sm transition-colors',
                        createDraft.contentTypes[type.key] ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                      )}
                    >
                      <Check className={cn('h-4 w-4', createDraft.contentTypes[type.key] ? 'opacity-100' : 'opacity-20')} />
                      {type.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-6 grid gap-5">
              <div>
                <div className="text-sm font-semibold text-slate-900">Каналы</div>
                <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {CHANNELS.map((channel) => (
                    <button
                      key={channel.key}
                      type="button"
                      onClick={() => toggleChannel(channel.key)}
                      className={cn(
                        'rounded-2xl border px-4 py-3 text-left transition-colors',
                        createDraft.channels[channel.key] ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
                      )}
                    >
                      <div className="flex items-center justify-between gap-3 text-sm font-semibold">
                        <span>{channel.label}</span>
                        {createDraft.channels[channel.key] ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4 opacity-40" />}
                      </div>
                      <div className={cn('mt-1 text-xs', createDraft.channels[channel.key] ? 'text-slate-300' : 'text-slate-500')}>
                        {channel.mode === 'controlled' ? 'Контролируемое размещение' : 'После подключения'}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
              <div className="rounded-3xl bg-slate-950 p-5 text-white">
                <div className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-400">Будет создано</div>
                <div className="mt-3 text-3xl font-semibold">
                  около {Math.max(8, Math.round(createDraft.periodDays * (createDraft.frequency === 'active' ? 1 : createDraft.frequency === 'light' ? 0.35 : 0.55)))} публикаций
                </div>
                <div className="mt-4 grid gap-2 text-sm text-slate-300 sm:grid-cols-3">
                  <div className="rounded-2xl bg-white/10 px-3 py-3">{getSelectedCount(createDraft.contentTypes)} типов контента</div>
                  <div className="rounded-2xl bg-white/10 px-3 py-3">{getSelectedCount(createDraft.channels)} каналов</div>
                  <div className="rounded-2xl bg-white/10 px-3 py-3">{createDraft.periodDays} дней</div>
                </div>
              </div>
            </div>
          )}
        </div>
        <DialogFooter className="border-t border-slate-100 px-6 py-4">
          {createStep === 'preview' ? (
            <Button type="button" variant="outline" onClick={() => setCreateStep('setup')}>
              Назад
            </Button>
          ) : null}
          {createStep === 'setup' ? (
            <Button type="button" onClick={() => setCreateStep('preview')} className="bg-slate-950 text-white hover:bg-slate-800">
              Далее
            </Button>
          ) : (
            <Button type="button" onClick={createPlan} className="bg-slate-950 text-white hover:bg-slate-800">
              Создать план
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const renderCalendarCard = (item: PlanItem) => {
    const posts = postsByItem[item.id] || [];
    const calendarState = getCalendarItemState(item, posts);
    const channels = posts.slice(0, 3).map(platformShortLabel);
    return (
      <button
        key={item.id}
        type="button"
        onClick={() => openItem(item)}
        className="w-full rounded-xl border border-slate-200 bg-white px-2.5 py-2 text-left shadow-sm transition hover:border-slate-300 hover:shadow-md"
      >
        <div className="line-clamp-2 text-xs font-semibold leading-4 text-slate-950">
          {item.theme || item.goal || 'Публикация'}
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {(channels.length ? channels : ['Контент']).map((channel) => (
            <span key={channel} className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
              {channel}
            </span>
          ))}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          <span className={cn('inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1', getStatusClassName(calendarState.status))}>
            {calendarState.status}
          </span>
          <span className={cn('inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1', getStatusClassName(calendarState.action))}>
            {calendarState.action}
          </span>
        </div>
      </button>
    );
  };

  const renderCalendar = () => (
    <div className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-2xl border border-slate-200 bg-slate-200">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => (
          <div key={day} className="bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            {day}
          </div>
        ))}
        {visibleDays.map((day) => {
          const key = toIsoDate(day);
          const dayItems = calendarItemsByDate[key] || [];
          const isCurrentMonth = day.getMonth() === new Date().getMonth();
          return (
            <div
              key={key}
              className={cn(
                'min-h-[150px] bg-white p-2',
                !isCurrentMonth && view === 'month' ? 'bg-slate-50/70 text-slate-400' : '',
              )}
            >
              <div className="mb-2 text-xs font-semibold text-slate-500">
                {day.getDate()}
              </div>
              <div className="space-y-2">
                {dayItems.slice(0, 3).map(renderCalendarCard)}
                {dayItems.length > 3 ? (
                  <div className="rounded-xl bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                    ещё {dayItems.length - 3}
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderList = () => (
    <div className="rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm">
      <div className="divide-y divide-slate-100">
        {items.map((item) => {
          const posts = postsByItem[item.id] || [];
          const calendarState = getCalendarItemState(item, posts);
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => openItem(item)}
              className="flex w-full flex-col gap-3 px-3 py-4 text-left transition hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <div className="text-sm font-semibold text-slate-950">{item.theme || item.goal || 'Публикация'}</div>
                <div className="mt-1 text-sm text-slate-500">{formatDate(item.scheduled_for)} · {(posts.length || getSelectedCount(createDraft.channels))} каналов</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className={cn('inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1', getStatusClassName(calendarState.status))}>
                  {calendarState.status}
                </span>
                <span className={cn('inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1', getStatusClassName(calendarState.action))}>
                  {calendarState.action}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );

  const renderEmptyState = () => (
    <div className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm">
      <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
            <Sparkles className="h-4 w-4" />
            ИИ-маркетолог
          </div>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-slate-950">
            Ваш календарь пока пуст
          </h1>
          <p className="mt-4 max-w-xl text-base leading-7 text-slate-600">
            LocalOS может подготовить месяц публикаций для карт и соцсетей. Вы увидите готовый календарь, а потом быстро проверите важное.
          </p>
          <Button type="button" onClick={() => setCreateOpen(true)} className="mt-6 rounded-2xl bg-slate-950 px-5 py-6 text-base text-white hover:bg-slate-800">
            Создать первый план
          </Button>
        </div>
        <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-4 opacity-70">
          <div className="grid grid-cols-7 gap-2">
            {Array.from({ length: 28 }, (_, index) => (
              <div key={index} className="min-h-20 rounded-2xl bg-white p-2 shadow-sm">
                <div className="text-xs font-semibold text-slate-300">{index + 1}</div>
                {[2, 4, 7, 9, 12, 15, 18, 22, 25].includes(index) ? (
                  <div className="mt-2 rounded-xl bg-slate-900/10 px-2 py-1 text-[10px] font-semibold text-slate-500">
                    Пост готов
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const renderGenerating = () => (
    <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
      <div className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">Подготавливаем контент</div>
            <div className="mt-3 text-3xl font-semibold text-slate-950">{generationCards} из {Math.max(32, createDraft.periodDays)} публикаций</div>
          </div>
          <div className="text-sm font-medium text-slate-500">{generationProgress}%</div>
        </div>
        <Progress value={generationProgress} className="mt-5 h-3 bg-slate-100" />
        <div className="mt-6 grid grid-cols-7 gap-2">
          {Array.from({ length: 35 }, (_, index) => {
            const filled = index < generationCards;
            return (
              <div key={index} className="min-h-24 rounded-2xl border border-slate-200 bg-slate-50 p-2">
                <div className="text-xs font-semibold text-slate-300">{index + 1}</div>
                {filled ? (
                  <div className="mt-2 animate-in fade-in slide-in-from-bottom-1 rounded-xl bg-slate-950 px-2 py-1.5 text-[10px] font-semibold text-white">
                    Публикация
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
      <div className="rounded-[28px] border border-slate-200 bg-slate-950 p-5 text-white shadow-sm">
        <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">Что делает ИИ</div>
        <div className="mt-5 space-y-4 text-sm">
          {[
            ['Анализируем отзывы', generationProgress > 10],
            ['Проверяем праздники', generationProgress > 24],
            ['Анализируем конкурентов', generationProgress > 38],
            ['Подбираем темы', generationProgress > 52],
            ['Пишем публикации', generationProgress > 66],
          ].map(([label, done]) => (
            <div key={String(label)} className="flex items-center gap-3">
              {done ? <CheckCircle2 className="h-5 w-5 text-emerald-300" /> : <Loader2 className="h-5 w-5 animate-spin text-slate-500" />}
              <span className={done ? 'text-white' : 'text-slate-400'}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderAiSidebar = () => (
    <aside className="space-y-4">
      <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">Сегодня</div>
        <div className="mt-4 space-y-3">
          <Insight icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} text={`Создано ${items.filter(itemHasUsableText).length} публикаций`} />
          <Insight icon={<AlertCircle className="h-4 w-4 text-amber-600" />} text={`Требует проверки ${needsReviewCount}`} />
          <Insight icon={<Lightbulb className="h-4 w-4 text-blue-600" />} text="Предлагаю публикацию к ближайшему событию" detail="Потому что сезонные темы обычно дают больше поводов написать." />
          <Insight icon={<Star className="h-4 w-4 text-violet-600" />} text="Проверьте акции конкурентов" detail="Если рядом появилась акция, стоит ответить своим предложением." />
          <Insight icon={<Eye className="h-4 w-4 text-slate-600" />} text="Стоит обновить фотографии" detail="Визуальные посты лучше работают в картах." />
        </div>
      </div>
      <div className="rounded-[28px] border border-slate-200 bg-slate-950 p-5 text-white shadow-sm">
        <div className="text-sm font-semibold text-slate-300">Следующее действие</div>
        <div className="mt-2 text-xl font-semibold">
          {needsReviewCount > 0 ? 'Проверить публикации' : nextItem ? 'Ближайшая публикация готова' : 'Создать план'}
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          {needsReviewCount > 0
            ? 'Осталось быстро посмотреть тексты и подтвердить готовые публикации.'
            : nextItem
              ? `${formatDate(nextItem.scheduled_for)} выйдет следующая публикация.`
              : 'LocalOS подготовит календарь за вас.'}
        </p>
      </div>
    </aside>
  );

  const renderMediaLibrary = () => (
    <div className="space-y-5">
      <main className="space-y-5">
        <div className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">Медиатека</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Фото для карт и постов</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                Загрузите фото бизнеса. LocalOS подскажет, что подходит для публикаций, а чего не хватает.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                ref={mediaUploadInputRef}
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(event) => { void uploadMediaPhotos(event.target.files); }}
              />
              <Button
                type="button"
                onClick={() => mediaUploadInputRef.current?.click()}
                disabled={mediaUploading}
                className="rounded-2xl bg-slate-950 px-5 py-6 text-white hover:bg-slate-800"
              >
                {mediaUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                {mediaUploading ? mediaUploadProgress || 'Загружаем...' : 'Загрузить фото'}
              </Button>
              <Button type="button" variant="outline" onClick={loadMediaAssets} disabled={mediaLoading} className="rounded-2xl px-5 py-6">
                {mediaLoading ? 'Обновляем...' : 'Обновить'}
              </Button>
            </div>
          </div>
          <div className="mt-6 grid gap-3 md:grid-cols-3 xl:grid-cols-[1.1fr_1fr_1.1fr]">
            <div className="rounded-3xl bg-slate-950 p-5 text-white">
              <div className="text-sm text-slate-400">Покрытие</div>
              <div className="mt-2 text-4xl font-semibold tabular-nums">{Number(mediaCoverage?.coverage_percent || 0)}%</div>
              <div className="mt-2 text-sm leading-6 text-slate-300">{mediaCoverage?.missing_text || 'Загрузите фото, чтобы увидеть покрытие.'}</div>
            </div>
            <div className="rounded-3xl bg-slate-50 p-5">
              <div className="text-sm text-slate-500">Фото</div>
              <div className="mt-2 text-4xl font-semibold text-slate-950 tabular-nums">{mediaAssets.length}</div>
              <div className="mt-2 text-sm leading-6 text-slate-500">Используются для рекомендаций в публикациях.</div>
            </div>
            <div className="rounded-3xl bg-amber-50 p-5">
              <div className="text-sm text-amber-800">Что доснять</div>
              <div className="mt-2 text-sm leading-6 text-amber-900">
                {mediaCoverage?.missing_text || 'Вход, команда, процесс и результат помогают закрыть карты и соцсети.'}
              </div>
            </div>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {[
              'Анализируем фото один раз',
              'Подбираем лучшее к публикации',
              'Повторное использование без списания',
            ].map((text) => (
              <div key={text} className="rounded-2xl bg-slate-50 px-4 py-3 text-sm font-medium leading-5 text-slate-600">
                {text}
              </div>
            ))}
          </div>
        </div>

        {mediaError ? (
          <div className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-800">
            {mediaError}
          </div>
        ) : null}
        {mediaActionMessage ? (
          <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
            {mediaActionMessage}
          </div>
        ) : null}

        <div className="rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm">
          <div className="flex flex-wrap gap-2">
            {[
              ['all', `Все · ${mediaAssets.length}`],
              ['maps', 'Для карт'],
              ['posts', 'Для постов'],
              ['weak', 'Лучше заменить'],
            ].map(([key, label]) => (
              <button
                key={String(key)}
                type="button"
                onClick={() => setMediaFilter(key === 'maps' ? 'maps' : key === 'posts' ? 'posts' : key === 'weak' ? 'weak' : 'all')}
                className={cn(
                  'min-h-10 rounded-2xl px-4 py-2 text-sm font-semibold transition-colors',
                  mediaFilter === key ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {mediaLoading ? (
          <div className="rounded-[28px] border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 shadow-sm">
            Загружаем медиатеку...
          </div>
        ) : filteredMediaAssets.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {filteredMediaAssets.map((asset) => {
              const imageSrc = photoImageSrc(asset);
              const quality = Number(asset.quality_score || 0);
              const status = String(asset.analysis_status || 'not_analyzed');
              return (
                <div key={asset.id} className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
                  {imageSrc ? (
                    <AuthenticatedImage src={imageSrc} alt="Фото бизнеса" className="h-48 w-full object-cover ring-1 ring-black/10" />
                  ) : (
                    <div className="flex h-48 items-center justify-center bg-slate-100 text-slate-400">
                      <ImageIcon className="h-8 w-8" />
                    </div>
                  )}
                  <div className="space-y-3 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-950">{formatPhotoCategoryLabel(asset.category)}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          {status === 'analyzed' ? 'Проанализировано' : status === 'analysis_failed' ? 'Не удалось проанализировать' : 'Ждёт анализа'}
                        </div>
                      </div>
                      <span className={cn('rounded-full px-2.5 py-1 text-xs font-semibold ring-1', quality >= 55 ? 'bg-emerald-50 text-emerald-700 ring-emerald-100' : quality > 0 ? 'bg-amber-50 text-amber-800 ring-amber-100' : 'bg-slate-100 text-slate-600 ring-slate-200')}>
                        {quality > 0 ? `${quality}%` : 'новое'}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {(asset.suitable_platforms || []).slice(0, 4).map((platform) => (
                        <span key={platform} className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600">
                          {formatPlatformLabel(platform)}
                        </span>
                      ))}
                      {(asset.suitable_platforms || []).length === 0 ? (
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600">каналы появятся после анализа</span>
                      ) : null}
                    </div>
                    {status !== 'analyzed' ? (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => { void analyzeMediaAsset(asset.id); }}
                        disabled={mediaAnalyzingId === asset.id}
                        className="w-full rounded-2xl"
                      >
                        {mediaAnalyzingId === asset.id ? 'Анализируем...' : 'Проанализировать'}
                      </Button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-[32px] border border-dashed border-slate-200 bg-white p-8 shadow-sm">
            <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
                  <ImageIcon className="h-4 w-4" />
                  Фото ещё не загружены
                </div>
                <h3 className="mt-4 text-2xl font-semibold text-slate-950">Начните с 10 реальных фото</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  Лучше всего подойдут вход, интерьер, процесс, результат, команда и живые детали. Анализ списывает 2 кредита за новое фото.
                </p>
                <Button type="button" onClick={() => mediaUploadInputRef.current?.click()} disabled={mediaUploading} className="mt-5 rounded-2xl bg-slate-950 px-5 py-6 text-white hover:bg-slate-800 disabled:bg-slate-300">
                  {mediaUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                  {mediaUploading ? mediaUploadProgress || 'Загружаем...' : 'Загрузить фото'}
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-3 opacity-70">
                {['вход', 'процесс', 'результат', 'команда', 'интерьер', 'детали'].map((label) => (
                  <div key={label} className="flex h-28 items-end rounded-3xl bg-slate-100 p-3 text-xs font-semibold text-slate-500">
                    {label}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );

  const renderDrawer = () => {
    const item = selectedItem;
    const hasPosts = selectedPosts.length > 0;
    const failedPost = selectedPosts.find((post) => String(post.status || '') === 'failed');
    const currentDraftText = String(draftEdits[item?.id || ''] ?? item?.draft_text ?? '').trim();
    const hasFallbackDraft = itemGenerationSource(item) === 'fallback';
    const hasDraftText = Boolean(currentDraftText) && itemGenerationSource(item) !== 'fallback';
    const channelCount = hasPosts ? selectedPosts.length : CHANNELS.length;
    const needsReviewChannelCount = selectedPosts.filter((post) => getChannelStatusLabel(post.status) === 'Нужно проверить').length;
    const readyTextChannelCount = selectedPosts.filter((post) => getChannelStatusLabel(post.status) === 'Текст готов').length;
    const approvedPostCount = selectedPosts.filter((post) => String(post.status || '').toLowerCase() === 'approved').length;
    const scheduledPostCount = selectedPosts.filter((post) => isQueuedOrHandledStatus(post.status)).length;
    const blockedChannelCount = selectedPosts.filter((post) => isAutomaticSendBlockedStatus(post.status)).length;
    const scheduleAlreadyHandled = scheduledPostCount > 0 && approvedPostCount === 0 && needsReviewChannelCount === 0;
    const canQueueSelectedItem = approvedPostCount > 0 && needsReviewChannelCount === 0;
    const queueNeedsAttention = hasPosts && !canQueueSelectedItem && !scheduleAlreadyHandled;
    const canApproveSelectedItem = hasDraftText && (!hasPosts || needsReviewChannelCount > 0);
    const approveButtonLabel = busyAction === 'approve'
      ? 'Утверждаем...'
      : canApproveSelectedItem
        ? 'Утвердить'
        : 'Текст утверждён';
    const queueButtonLabel = busyAction === 'queue'
      ? 'Ставим...'
      : scheduledPostCount > 0 && approvedPostCount === 0
        ? 'Запланировано'
        : 'Запланировать отправку';
    const queueTooltip = 'Отправляет автоматически через выбранные каналы. Если канал не подключён или не выбран, LocalOS покажет, что нужно настроить.';
    const queueHelpText = canQueueSelectedItem
      ? 'Если выбранные каналы не подключены, LocalOS покажет, что нужно настроить перед отправкой.'
      : !hasPosts
        ? 'Сначала нажмите «Подготовить каналы», чтобы LocalOS создал варианты для площадок.'
        : needsReviewChannelCount > 0
          ? 'Следующий шаг: проверьте текст и нажмите «Утвердить». После этого появится расписание.'
          : blockedChannelCount > 0
            ? 'Автоотправка не запланирована: часть каналов требует подключения, ручного действия или контролируемого размещения.'
            : scheduleAlreadyHandled
              ? 'Публикация уже стоит в расписании или ждёт контролируемого размещения.'
              : 'Сейчас нет каналов, готовых к отправке. Подготовьте каналы или проверьте их состояние.';
    const channelSummary = hasPosts
      ? needsReviewChannelCount > 0
        ? `Нужно проверить: ${needsReviewChannelCount}`
        : readyTextChannelCount > 0
          ? `Текст готов: ${readyTextChannelCount}`
          : `${channelCount} каналов в плане`
      : `${channelCount} каналов после подготовки`;
    const channelDetailsId = item ? `content-channels-${item.id}` : 'content-channels';
    const mediaRecommendation = item ? mediaRecommendations[item.id] : null;
    const selectedPhoto = mediaRecommendation?.selected_asset || null;
    return (
      <Sheet open={Boolean(item)} onOpenChange={(open) => { if (!open) setSelectedItemId(''); }}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-4xl">
          {item ? (
            <div className="grid min-h-full gap-6 lg:grid-cols-[1fr_300px]">
              <div>
                <SheetHeader>
                  <SheetTitle className="text-2xl">Публикация</SheetTitle>
                  <SheetDescription>Текст, предпросмотр и подтверждение перед выходом наружу.</SheetDescription>
                </SheetHeader>
                <div className="mt-6 space-y-4">
                  <Input
                    value={themeEdits[item.id] ?? item.theme ?? item.goal ?? ''}
                    onChange={(event: React.ChangeEvent<HTMLInputElement>) => setThemeEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                    className="h-12 rounded-2xl border-slate-200 text-base font-semibold"
                  />
                  <div className="flex flex-col gap-3 rounded-3xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">
                        {hasDraftText ? 'Текст уже есть' : 'Текста ещё нет'}
                      </div>
                      <div className="mt-1 text-sm text-slate-500">
                        {hasDraftText
                          ? 'Можно поправить вручную или попросить LocalOS написать заново.'
                          : hasFallbackDraft
                            ? 'ИИ не смог подготовить хороший текст с первого раза. Попробуйте ещё раз.'
                            : 'LocalOS напишет новость по теме из контент-плана.'}
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant={hasDraftText ? 'outline' : 'default'}
                      onClick={generateSelectedDraft}
                      disabled={Boolean(busyAction)}
                      className={cn('rounded-2xl', !hasDraftText ? 'bg-slate-950 text-white hover:bg-slate-800' : '')}
                    >
                      {busyAction === 'generate-draft' ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Пишем...
                        </>
                      ) : (
                        <>
                          <Wand2 className="mr-2 h-4 w-4" />
                          {hasDraftText ? 'Сгенерировать заново' : 'Сгенерировать текст'}
                        </>
                      )}
                    </Button>
                  </div>
                  <Textarea
                    value={draftEdits[item.id] ?? item.draft_text ?? ''}
                    onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setDraftEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                    className="min-h-[260px] rounded-2xl border-slate-200 text-base leading-7"
                    placeholder="Текст публикации"
                  />
                  <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                    <div className="mb-3 text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Preview</div>
                    <div className="rounded-2xl bg-white p-4 text-sm leading-6 text-slate-700 shadow-sm">
                      {draftEdits[item.id] || item.draft_text || 'Здесь появится текст, который увидит клиент.'}
                    </div>
                  </div>
                  <div className="rounded-3xl border border-slate-200 bg-white p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">
                          <ImageIcon className="h-4 w-4" />
                          Фото
                        </div>
                        <div className="mt-2 text-lg font-semibold text-slate-950">
                          {mediaLoadingItemId === item.id ? 'Подбираем фото...' : mediaRecommendation?.title || 'Фото не выбрано'}
                        </div>
                        <div className="mt-1 text-sm leading-6 text-slate-500">
                          {mediaLoadingItemId === item.id
                            ? 'LocalOS смотрит доступные фото и подскажет, что лучше использовать.'
                            : mediaRecommendation?.message || 'Добавьте фото к бизнесу, и LocalOS подскажет лучший визуал для публикации.'}
                        </div>
                      </div>
                      <Button type="button" variant="outline" onClick={() => { void loadMediaRecommendation(item.id); }} disabled={mediaLoadingItemId === item.id} className="shrink-0 rounded-2xl">
                        {mediaLoadingItemId === item.id ? 'Проверяем...' : 'Обновить'}
                      </Button>
                    </div>
                    {selectedPhoto?.original_url ? (
                      <div className="mt-4 grid gap-4 sm:grid-cols-[140px_1fr]">
                        <AuthenticatedImage src={photoImageSrc(selectedPhoto)} alt="Подобранное фото" className="h-32 w-full rounded-2xl object-cover shadow-sm ring-1 ring-black/10" />
                        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                          <div className="font-semibold text-slate-900">Почему подходит</div>
                          <div className="mt-1 leading-6">{selectedPhoto.why || mediaRecommendation?.message || 'Фото подходит по задаче публикации.'}</div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">качество {Math.round(Number(selectedPhoto.quality_score || 0))}%</span>
                            {selectedPhoto.category ? <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">{formatPhotoCategoryLabel(selectedPhoto.category)}</span> : null}
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={recordSelectedPhotoUsage}
                            disabled={busyAction === 'photo-usage'}
                            className="mt-3 rounded-2xl bg-white"
                          >
                            {busyAction === 'photo-usage' ? 'Сохраняем...' : 'Использовать фото'}
                          </Button>
                        </div>
                      </div>
                    ) : null}
                    {Array.isArray(mediaRecommendation?.alternatives) && mediaRecommendation.alternatives.length > 0 ? (
                      <div className="mt-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Альтернативы</div>
                        <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
                          {mediaRecommendation.alternatives.slice(0, 3).map((asset) => (
                            <div key={asset.id} className="w-28 shrink-0 rounded-2xl bg-slate-50 p-2">
                              {photoImageSrc(asset) ? (
                                <AuthenticatedImage src={photoImageSrc(asset)} alt="Альтернативное фото" className="h-20 w-full rounded-xl object-cover ring-1 ring-black/10" />
                              ) : (
                                <div className="flex h-20 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
                                  <ImageIcon className="h-5 w-5" />
                                </div>
                              )}
                              <div className="mt-1 truncate text-[11px] font-medium text-slate-600">{formatPhotoCategoryLabel(asset.category)}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {mediaRecommendation?.coverage?.missing_text ? (
                      <div className="mt-4 rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                        {mediaRecommendation.coverage.missing_text}
                      </div>
                    ) : null}
                    {Array.isArray(mediaRecommendation?.platform_hints) && mediaRecommendation.platform_hints.length > 0 ? (
                      <div className="mt-3 space-y-1 text-xs leading-5 text-slate-500">
                        {mediaRecommendation.platform_hints.slice(0, 2).map((hint) => (
                          <div key={hint}>• {hint}</div>
                        ))}
                      </div>
                    ) : null}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setSection('media');
                        setSelectedItemId('');
                      }}
                      className="mt-4 rounded-2xl"
                    >
                      Открыть медиатеку
                    </Button>
                  </div>
                  {failedPost ? (
                    <div className="rounded-3xl border border-red-100 bg-red-50 p-4 text-sm text-red-800">
                      <div className="font-semibold">Не удалось опубликовать</div>
                      <div className="mt-1">{failedPost.last_error || 'Подключение требует внимания.'}</div>
                      <Button type="button" variant="outline" onClick={() => navigate('/dashboard/settings')} className="mt-3 border-red-200 bg-white text-red-800 hover:bg-red-100">
                        Обновить подключение
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="space-y-4">
                <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="text-sm font-semibold text-slate-950">Детали</div>
                  <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Дата
                    <Input
                      type="date"
                      value={dateEdits[item.id] ?? getItemDateKey(item)}
                      onChange={(event: React.ChangeEvent<HTMLInputElement>) => setDateEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                      className="mt-2 rounded-2xl"
                    />
                  </label>
                  <div className="mt-4">
                    <button
                      type="button"
                      onClick={() => setChannelDetailsOpen((open) => !open)}
                      aria-expanded={channelDetailsOpen}
                      aria-controls={channelDetailsId}
                      className="flex min-h-10 w-full items-center justify-between gap-3 rounded-2xl bg-slate-50 px-3 py-2 text-left transition-colors hover:bg-slate-100"
                    >
                      <span>
                        <span className="block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Каналы</span>
                        <span className="mt-0.5 block text-sm font-semibold text-slate-900">{channelSummary}</span>
                      </span>
                      <ChevronDown className={cn('h-4 w-4 shrink-0 text-slate-500 transition-transform', channelDetailsOpen ? 'rotate-180' : '')} />
                    </button>
                    {channelDetailsOpen ? (
                      hasPosts ? (
                        <div id={channelDetailsId} className="mt-2 space-y-2">
                          {selectedPosts.map((post) => {
                            const statusLabel = getChannelStatusDisplay(post);
                            const readiness = getPostPlatformReadiness(post);
                            return (
                              <div key={post.id} className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-sm font-semibold text-slate-900">{platformShortLabel(post)}</span>
                                  <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1', getStatusClassName(statusLabel))}>
                                    {statusLabel}
                                  </span>
                                </div>
                                <div className="mt-1 text-xs leading-5 text-slate-500">{getChannelNextAction(post)}</div>
                                {readiness?.action_label && isPlatformRuleBlocked(post) ? (
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                      if (readiness.action_label === 'Добавить фото' || readiness.action_label === 'Заменить фото' || readiness.action_label === 'Выбрать фото') {
                                        setSection('media');
                                        setSelectedItemId('');
                                      } else {
                                        navigate('/dashboard/settings');
                                      }
                                    }}
                                    className="mt-2 h-8 rounded-xl bg-white px-3 text-xs"
                                  >
                                    {readiness.action_label}
                                  </Button>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div id={channelDetailsId} className="mt-2 flex flex-wrap gap-2">
                          {CHANNELS.map((channel) => (
                            <span key={channel.key} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                              {channel.label}
                            </span>
                          ))}
                        </div>
                      )
                    ) : null}
                  </div>
                  {!hasPosts ? (
                    <div className="mt-4">
                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Статус</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <span className={cn('rounded-full px-3 py-1 text-xs font-semibold ring-1', getStatusClassName(itemHasUsableText(item) ? 'Нужно проверить' : 'Черновик'))}>
                          {itemHasUsableText(item) ? 'Нужно проверить' : 'Черновик'}
                        </span>
                      </div>
                    </div>
                  ) : null}
                </div>
                <div className="grid gap-2">
                  <Button type="button" variant="outline" onClick={saveSelectedItem} disabled={Boolean(busyAction)} className="rounded-2xl">
                    {busyAction === 'save' ? 'Сохраняем...' : 'Сохранить'}
                  </Button>
                  <Button type="button" variant="outline" onClick={prepareSelectedItem} disabled={Boolean(busyAction)} className="rounded-2xl">
                    {busyAction === 'prepare' ? 'Готовим...' : 'Подготовить каналы'}
                  </Button>
                  <Button
                    type="button"
                    onClick={approveSelectedItem}
                    disabled={Boolean(busyAction) || !canApproveSelectedItem}
                    className="rounded-2xl bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-500"
                  >
                    {approveButtonLabel}
                  </Button>
                  <TooltipProvider delayDuration={150}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="block">
                          <Button
                            type="button"
                            onClick={queueSelectedItem}
                            disabled={Boolean(busyAction) || scheduleAlreadyHandled}
                            className={cn(
                              'w-full rounded-2xl text-white disabled:bg-slate-200 disabled:text-slate-500',
                              canQueueSelectedItem
                                ? 'bg-emerald-600 hover:bg-emerald-700'
                                : 'bg-slate-950 hover:bg-slate-800',
                            )}
                          >
                            {queueButtonLabel}
                          </Button>
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-[260px] text-sm leading-5">
                        {queueTooltip}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                {queueNeedsAttention ? (
                  <div className="rounded-2xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                    <div className="font-semibold">Отправка пока не запланирована</div>
                    <div className="mt-1">{queueHelpText}</div>
                  </div>
                ) : null}
                {error ? (
                  <div className="rounded-2xl border border-red-100 bg-red-50 px-3 py-2 text-xs leading-5 text-red-800">
                    <div className="font-semibold">Что нужно сделать</div>
                    <div className="mt-1">{error}</div>
                  </div>
                ) : null}
                {actionMessage ? (
                  <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs font-medium leading-5 text-emerald-800">
                    {actionMessage}
                  </div>
                ) : null}
                <p className="text-xs leading-5 text-slate-500">
                  {queueHelpText}
                </p>
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    );
  };

  if (!currentBusinessId) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white p-8 text-slate-600">
          Сначала выберите бизнес, чтобы открыть контент.
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1500px] space-y-6 px-4 py-6">
      {renderPlanModal()}
      {renderDrawer()}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">LocalOS Content</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">Контент</h1>
          <p className="mt-1 text-sm text-slate-500">{currentBusiness?.name || 'Единый календарь публикаций'}</p>
        </div>
        <Button type="button" onClick={() => { setCreateStep('setup'); setCreateOpen(true); }} className="rounded-2xl bg-slate-950 px-5 py-6 text-white hover:bg-slate-800">
          <Plus className="mr-2 h-4 w-4" />
          Создать новый план
        </Button>
      </div>

      <div className="inline-flex rounded-2xl bg-slate-100 p-1">
        {[
          ['calendar', 'Календарь', CalendarDays],
          ['media', 'Медиатека', ImageIcon],
        ].map(([key, label, Icon]) => (
          <button
            key={String(key)}
            type="button"
            onClick={() => setSection(key === 'media' ? 'media' : 'calendar')}
            className={cn(
              'inline-flex min-h-10 items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors',
              section === key ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-950',
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {error ? (
        <div className="flex items-center justify-between gap-3 rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-800">
          <span>{error}</span>
          <Button type="button" variant="outline" onClick={() => { void loadContent(); }} className="border-red-200 bg-white text-red-800 hover:bg-red-100">
            Повторить
          </Button>
        </div>
      ) : null}

      {actionMessage ? (
        <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
          {actionMessage}
        </div>
      ) : null}

      {section === 'media' ? renderMediaLibrary() : null}

      {section === 'calendar' && generating ? renderGenerating() : null}

      {section === 'calendar' && !generating && !loading && items.length === 0 ? renderEmptyState() : null}

      {section === 'calendar' && !generating && (loading || items.length > 0) ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
          <main className="space-y-5">
            <div className="rounded-[32px] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-2xl">
                  <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">Результат работы ИИ</div>
                  <h2 className="mt-3 text-4xl font-semibold tracking-tight">
                    {filledDays > 0 ? 'Контент готов' : 'Готовим календарь'}
                  </h2>
                  <div className="mt-4 max-w-xl text-lg text-slate-300">
                    {filledDays} из {totalDays} дней заполнены
                  </div>
                  <Progress value={Math.min(100, Math.round((filledDays / Math.max(totalDays, 1)) * 100))} className="mt-5 h-3 bg-white/10" />
                </div>
                <div className="rounded-3xl bg-white/10 px-5 py-4">
                  <div className="text-sm text-slate-400">Следующая публикация</div>
                  <div className="mt-1 text-2xl font-semibold">{nextItem ? formatDate(nextItem.scheduled_for) : 'нет даты'}</div>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
              <div className="space-y-4">
                <div>
                  <div className="text-sm font-semibold text-slate-950">Что сделать сейчас</div>
                  <div className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
                    Быстро проверьте ближайшее, подтвердите готовое и закройте раздел.
                  </div>
                </div>
                <div className="grid w-full min-w-0 gap-2 md:grid-cols-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={openNearestReview}
                    disabled={!items.length || Boolean(busyAction)}
                    className="h-12 min-w-0 justify-center gap-2 rounded-2xl border-slate-200 bg-white px-4 text-slate-800 transition-transform hover:bg-slate-50 active:scale-[0.96]"
                  >
                    <Eye className="h-4 w-4 shrink-0" />
                    <span className="truncate">Проверить ближайшие</span>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={approveReadyPosts}
                    disabled={reviewReadyPosts.length === 0 || Boolean(busyAction)}
                    className="h-12 min-w-0 justify-center gap-2 rounded-2xl border-slate-200 bg-white px-4 text-slate-800 transition-transform hover:bg-slate-50 active:scale-[0.96] disabled:opacity-45"
                  >
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    <span className="truncate">
                      {busyAction === 'bulk-approve' ? 'Утверждаем...' : `Утвердить готовое · ${reviewReadyPosts.length}`}
                    </span>
                  </Button>
                  <Button
                    type="button"
                    onClick={queueApprovedPosts}
                    disabled={approvedPosts.length === 0 || Boolean(busyAction)}
                    className="h-12 min-w-0 justify-center gap-2 rounded-2xl bg-slate-950 px-4 text-white transition-transform hover:bg-slate-800 active:scale-[0.96] disabled:bg-slate-300"
                  >
                    <CalendarDays className="h-4 w-4 shrink-0" />
                    <span className="truncate">
                      {busyAction === 'bulk-queue' ? 'Планируем...' : `Запланировать · ${approvedPosts.length}`}
                    </span>
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3 rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
              <div className="inline-flex rounded-2xl bg-slate-100 p-1">
                {[
                  ['month', 'Месяц', CalendarDays],
                  ['week', 'Неделя', Clock3],
                  ['list', 'Список', FileText],
                ].map(([key, label, Icon]) => (
                  <button
                    key={String(key)}
                    type="button"
                    onClick={() => setView(key === 'week' ? 'week' : key === 'list' ? 'list' : 'month')}
                    className={cn(
                      'inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors',
                      view === key ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-950',
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </button>
                ))}
              </div>
              <div className="text-sm font-medium text-slate-500">
                {needsReviewCount > 0 ? `Нужно проверить: ${needsReviewCount}` : 'Ближайшие публикации под контролем'}
              </div>
            </div>

            {view === 'list' ? renderList() : renderCalendar()}
          </main>
          {renderAiSidebar()}
        </div>
      ) : null}
    </div>
  );
}

function AuthenticatedImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
  const [resolvedSrc, setResolvedSrc] = useState(() => (src.startsWith('/api/') ? '' : src));

  useEffect(() => {
    if (!src || !src.startsWith('/api/')) {
      setResolvedSrc(src);
      return undefined;
    }
    setResolvedSrc('');
    let cancelled = false;
    let objectUrl = '';
    const loadImage = async () => {
      const token = window.localStorage.getItem('auth_token') || '';
      const response = await fetch(`${API_URL}${src}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!response.ok) return;
      const blob = await response.blob();
      if (cancelled) return;
      objectUrl = URL.createObjectURL(blob);
      setResolvedSrc(objectUrl);
    };
    void loadImage();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (!resolvedSrc) {
    return (
      <div className={cn('flex items-center justify-center bg-slate-100 text-slate-400', className)}>
        <ImageIcon className="h-5 w-5" />
      </div>
    );
  }
  return <img src={resolvedSrc} alt={alt} className={className} />;
}

function Insight({ icon, text, detail }: { icon: React.ReactNode; text: string; detail?: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 px-3 py-3">
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{icon}</div>
        <div>
          <div className="text-sm font-semibold text-slate-900">{text}</div>
          {detail ? <div className="mt-1 text-xs leading-5 text-slate-500">{detail}</div> : null}
        </div>
      </div>
    </div>
  );
}

export default ContentPage;
