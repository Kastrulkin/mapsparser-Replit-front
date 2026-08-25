import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import { AnimatePresence, motion, type Transition } from 'framer-motion';
import {
  AlertCircle,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Copy,
  Download,
  ImageIcon,
  Eye,
  FileText,
  Lightbulb,
  Loader2,
  MessageCircleQuestion,
  Plus,
  Sparkles,
  Star,
  Trash2,
  Upload,
  Wand2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { AudienceInsights } from '@/components/AudienceInsights';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { API_URL } from '@/config/api';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';
import { useLanguage } from '@/i18n/LanguageContext';
import { fillContentCalendarTemplate, getContentCalendarCopy, getDemoContentCalendarThemes, localizeContentCalendarStatus } from '@/i18n/contentCalendarCopy';
import { getContentWorkspaceControlsCopy, getContentWorkspaceCopy } from '@/i18n/contentWorkspaceCopy';
import { localizeDemoBusinessName } from './operatorPageCopy';
import { DemoContentPlanPage } from './demo/DemoContentPlanPage';

type DashboardBusiness = {
  id: string;
  name?: string;
};

type DashboardOutletContext = {
  currentBusinessId?: string | null;
  currentBusiness?: DashboardBusiness | null;
  demoMode?: boolean;
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
  subscription?: {
    allowed_horizons?: number[];
    tier?: string;
  };
};

type PlanItem = {
  id: string;
  business_id?: string;
  scheduled_for?: string;
  theme?: string;
  goal?: string;
  draft_text?: string;
  status?: string;
  content_type?: string;
  metadata_json?: {
    generation_source?: string;
    selected_channels?: string[];
    brief_answers?: Record<string, string>;
    content_brief_v1?: ContentBrief;
    content_generation_v2?: {
      selected_variant_id?: string;
      variants?: GenerationAlternative[];
    };
  };
};

type ContentSource = { id?: string; label?: string; fact?: string; type?: string };
type ContentBrief = {
  event?: string;
  confirmed_details?: string[];
  audience?: string;
  main_idea?: string;
  expected_action?: string;
  complete?: boolean;
  missing_fields?: string[];
  questions?: string[];
  sources?: ContentSource[];
};
type GenerationAlternative = { id?: string; angle?: string; text?: string; score?: number; quality_passed?: boolean };
type GenerationDetails = {
  status?: 'generated' | 'needs_context' | 'failed';
  message?: string;
  source?: string;
  action?: {
    type?: string;
    label?: string;
    target?: string;
  };
  missing_fields?: string[];
  questions?: string[];
  brief?: ContentBrief;
  sources?: ContentSource[];
  alternatives?: GenerationAlternative[];
};
type VoiceExample = { id: string; text: string; business_id?: string; platform?: string };
type VoiceProfile = {
  summary?: string;
  preferences?: {
    business_description?: string;
    audience_description?: string;
    [key: string]: unknown;
  };
  status?: string;
  version?: number;
  examples?: VoiceExample[];
  learning_suggestion?: { text?: string } | null;
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
  generated_plan_json?: {
    selected_channels?: string[];
    meta?: {
      selected_channels?: string[];
    };
  };
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
  provider_post_id?: string;
  provider_post_url?: string;
  views?: number;
  reach?: number;
  likes?: number;
  comments?: number;
  shares?: number;
  clicks?: number;
  inquiries?: number;
  leads?: number;
  metadata_json?: {
    variant_source?: 'ai' | 'deterministic' | 'manual';
    variant_status?: 'current' | 'stale' | 'failed';
    manually_edited?: boolean;
    platform_rules_version?: string;
    adaptation_error?: string;
    platform_rule_readiness?: {
      label?: string;
      message?: string;
      action_label?: string;
      severity?: string;
      status?: string;
    };
    queue_preflight_action_label?: string;
    queue_preflight_message_ru?: string;
    manual_publish_handoff?: {
      target_url?: string;
      copy_ready_text?: string;
    };
    supervised_publish?: {
      target_url?: string;
      copy_ready_text?: string;
    };
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

type PhotoAnalysisQuota = {
  network_id?: string;
  granted_analyses?: number;
  consumed_analyses?: number;
  reserved_analyses?: number;
  remaining_analyses?: number;
};

type PhotoAnalysisResult = {
  success?: boolean;
  status?: string;
  charged_credits?: number;
  billing_source?: string;
  photo_quota?: PhotoAnalysisQuota | null;
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
type ContentSection = 'calendar' | 'media' | 'audience';
type MediaFilter = 'all' | 'maps' | 'posts' | 'weak';
type ModalStep = 'setup' | 'preview';
type ContentSetupStep = 'business' | 'audience' | 'voice';

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
const DEFAULT_PLAN_PERIODS = [30];

const russianCountLabel = (value: number, forms: [string, string, string]) => {
  const absoluteValue = Math.abs(value);
  const lastTwoDigits = absoluteValue % 100;
  if (lastTwoDigits >= 11 && lastTwoDigits <= 14) return forms[2];
  const lastDigit = absoluteValue % 10;
  if (lastDigit === 1) return forms[0];
  if (lastDigit >= 2 && lastDigit <= 4) return forms[1];
  return forms[2];
};

const buildPhotoAnalysisCostMessage = (
  chargedCredits: number,
  includedAnalyses = 0,
  cachedAnalyses = 0,
) => {
  const details = [`Списано: ${chargedCredits} ${russianCountLabel(chargedCredits, ['кредит', 'кредита', 'кредитов'])}.`];
  if (includedAnalyses > 0) {
    details.push(`В пакет вошло: ${includedAnalyses} ${russianCountLabel(includedAnalyses, ['анализ', 'анализа', 'анализов'])}.`);
  }
  if (cachedAnalyses > 0) {
    details.push(`Повторный анализ не потребовался для ${cachedAnalyses} фото.`);
  }
  return details.join(' ');
};

const isInsufficientPhotoCreditsError = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error || '');
  const normalized = message.trim().toLowerCase();
  return normalized.includes('недостаточно кредитов') || normalized.includes('insufficient credit');
};

const CHANNELS = [
  { key: 'yandex_maps', label: 'Яндекс', mode: 'controlled' },
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
    google_business: true,
    telegram: true,
    vk: true,
    instagram: true,
    facebook: true,
  },
};

const CONTENT_FREQUENCY_PER_WEEK: Record<string, number> = {
  light: 2,
  standard: 3,
  active: 7,
};

const plannedPublicationCount = (periodDays: number, frequency: string) => {
  const publicationsPerWeek = CONTENT_FREQUENCY_PER_WEEK[frequency] || CONTENT_FREQUENCY_PER_WEEK.standard;
  return Math.max(4, Math.round(periodDays / 7 * publicationsPerWeek));
};

const buildChannelSelection = (selectedChannels?: string[]) => {
  const selected = new Set((selectedChannels || []).map((value) => String(value || '').trim()).filter(Boolean));
  return CHANNELS.reduce<Record<string, boolean>>((result, channel) => {
    result[channel.key] = selected.size === 0 || selected.has(channel.key);
    return result;
  }, {});
};

const selectedChannelsFromPlan = (plan?: PlanPayload | null) => {
  const direct = plan?.generated_plan_json?.selected_channels;
  const nested = plan?.generated_plan_json?.meta?.selected_channels;
  const channels = Array.isArray(direct) ? direct : Array.isArray(nested) ? nested : [];
  return channels.map((value) => String(value || '').trim()).filter(Boolean);
};

const selectedChannelsFromItem = (item?: PlanItem | null) => {
  const channels = item?.metadata_json?.selected_channels;
  if (!Array.isArray(channels)) return [];
  const allowedChannels = new Set(CHANNELS.map((channel) => channel.key));
  return channels
    .map((value) => String(value || '').trim())
    .filter((value, index, values) => allowedChannels.has(value) && values.indexOf(value) === index);
};

const selectedChannelKeys = (selection: Record<string, boolean>) => (
  CHANNELS.filter((channel) => Boolean(selection[channel.key])).map((channel) => channel.key)
);

const sameSelectedChannels = (left: string[], right: string[]) => (
  left.length === right.length && left.every((channel) => right.includes(channel))
);

const summarizeSocialPosts = (posts: SocialPost[]): SocialSummary => ({
  total: posts.length,
  needs_review: posts.filter((post) => post.status === 'needs_review').length,
  scheduled: posts.filter((post) => post.status === 'queued' || post.status === 'publishing').length,
  needs_supervised_publish: posts.filter((post) => post.status === 'needs_supervised_publish').length,
  needs_manual_publish: posts.filter((post) => post.status === 'needs_manual_publish').length,
  published: posts.filter((post) => post.status === 'published').length,
  failed: posts.filter((post) => post.status === 'failed').length,
});

const resolveItemSelectedChannels = (item: PlanItem | null, posts: SocialPost[], plan: PlanPayload | null) => {
  const itemChannels = selectedChannelsFromItem(item);
  if (itemChannels.length > 0) return itemChannels;
  const postChannels = CHANNELS
    .map((channel) => channel.key)
    .filter((channel) => posts.some((post) => String(post.platform || '').trim() === channel));
  if (postChannels.length > 0) return postChannels;
  return selectedChannelsFromPlan(plan);
};

const normalizeIsoDate = (value?: string) => {
  const rawValue = String(value || '').trim();
  if (!rawValue) return '';
  if (/^\d{4}-\d{2}-\d{2}/.test(rawValue)) return rawValue.slice(0, 10);
  const parsed = new Date(rawValue);
  return Number.isNaN(parsed.getTime()) ? '' : toIsoDate(parsed);
};

const DATE_LOCALES = { ru: 'ru-RU', en: 'en-US', fr: 'fr-FR', es: 'es-ES', el: 'el-GR', de: 'de-DE', th: 'th-TH', ar: 'ar', ha: 'ha-NG', tr: 'tr-TR' };

const formatDate = (value: string | undefined, language: keyof typeof DATE_LOCALES = 'ru') => {
  if (!value) return '';
  const normalized = normalizeIsoDate(value);
  const date = normalized ? new Date(`${normalized}T00:00:00`) : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(DATE_LOCALES[language], { day: 'numeric', month: 'short' }).format(date);
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
  const variantStatus = String(post.metadata_json?.variant_status || '').toLowerCase();
  const variantSource = String(post.metadata_json?.variant_source || '').toLowerCase();
  if (variantStatus === 'stale') return 'Общий текст изменился. Проверьте сохранённую версию этого канала.';
  const readiness = getPostPlatformReadiness(post);
  if (readiness?.message) return readiness.message;
  const normalized = String(post.status || '').toLowerCase();
  if (normalized === 'needs_review' && variantSource === 'ai') return 'Текст адаптирован для этой площадки. Проверьте его перед подтверждением.';
  if (normalized === 'needs_review' && variantSource === 'deterministic') return 'Проверьте версию: автоматическая адаптация была недоступна.';
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
  const variantStatus = String(post.metadata_json?.variant_status || '').toLowerCase();
  const variantSource = String(post.metadata_json?.variant_source || '').toLowerCase();
  if (variantStatus === 'stale') return 'Версия устарела';
  const readiness = getPostPlatformReadiness(post);
  const normalized = String(post.status || '').toLowerCase();
  if (readiness?.label && !['queued', 'published'].includes(normalized)) return readiness.label;
  if (normalized === 'needs_review' && variantSource) return 'Версия готова';
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

const workingContentPlans = (values: PlanPayload[]) => values.filter(
  (plan) => String(plan.plan_status || '').toLowerCase() !== 'archived',
);

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

const placementTargetUrl = (post: SocialPost) => String(
  post.metadata_json?.supervised_publish?.target_url
  || post.metadata_json?.manual_publish_handoff?.target_url
  || '',
).trim();

const draftFeedbackSpring: Transition = { type: 'spring', duration: 0.3, bounce: 0 };

const DraftGenerationFeedback = ({ ready }: { ready: boolean }) => {
  const [progress, setProgress] = useState(12);
  useEffect(() => {
    if (ready) { setProgress(100); return; }
    const interval = window.setInterval(() => setProgress((value) => Math.min(92, value + 4)), 220);
    return () => window.clearInterval(interval);
  }, [ready]);
  const stage = progress < 38 ? 'Изучаем тему и данные бизнеса' : progress < 72 ? 'Собираем полезный текст' : progress < 100 ? 'Проверяем тон и факты' : 'Текст готов к вашей проверке';
  return <motion.div aria-live="polite" initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} transition={draftFeedbackSpring} className={`rounded-2xl px-4 py-3 shadow-[0_0_0_1px_rgba(148,163,184,0.16),0_12px_32px_rgba(15,23,42,0.06)] transition-[background-color,box-shadow] ${ready ? 'bg-emerald-50' : 'bg-orange-50'}`}><div className="flex items-center gap-3"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${ready ? 'bg-emerald-100 text-emerald-700' : 'bg-orange-100 text-orange-700'}`}><AnimatePresence initial={false} mode="popLayout">{ready ? <motion.span key="done" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={draftFeedbackSpring}><Check className="h-5 w-5" /></motion.span> : <motion.span key="work" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={draftFeedbackSpring}><Sparkles className="h-5 w-5" /></motion.span>}</AnimatePresence></span><div className="min-w-0 flex-1"><div className="text-sm font-semibold text-slate-950">{ready ? 'Готово — можно редактировать' : 'LocalOS готовит черновик'}</div><div className="mt-1 text-xs text-slate-600">{stage}</div></div><b className={`tabular-nums text-xs ${ready ? 'text-emerald-700' : 'text-orange-700'}`}>{progress}%</b></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/80"><motion.div className={`h-full rounded-full ${ready ? 'bg-emerald-500' : 'bg-orange-500'}`} animate={{ width: `${progress}%` }} transition={draftFeedbackSpring} /></div></motion.div>;
};

function ContentWorkspace() {
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = useLanguage();
  const contentCopy = getContentWorkspaceCopy(language);
  const calendarCopy = getContentCalendarCopy(language);
  const contentControls = getContentWorkspaceControlsCopy(language);
  const { currentBusinessId, currentBusiness, demoMode } = useOutletContext<DashboardOutletContext>();
  const [context, setContext] = useState<ContentPlanContext | null>(null);
  const [plans, setPlans] = useState<PlanPayload[]>([]);
  const [currentPlan, setCurrentPlan] = useState<PlanPayload | null>(null);
  const [socialPosts, setSocialPosts] = useState<SocialPost[]>([]);
  const [socialSummary, setSocialSummary] = useState<SocialSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyAction, setBusyAction] = useState('');
  const [draftGenerationReady, setDraftGenerationReady] = useState(false);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [view, setView] = useState<CalendarView>(() => {
    if (typeof window === 'undefined') return 'month';
    const saved = window.localStorage.getItem(CONTENT_VIEW_STORAGE_KEY);
    return saved === 'week' || saved === 'list' || saved === 'month' ? saved : 'month';
  });
  const [section, setSection] = useState<ContentSection>(() => {
    if (typeof window === 'undefined') return 'calendar';
    const requested = new URLSearchParams(window.location.search).get('section');
    if (requested === 'media' || requested === 'audience' || requested === 'calendar') return requested;
    const saved = window.localStorage.getItem(CONTENT_SECTION_STORAGE_KEY);
    return saved === 'media' || saved === 'audience' ? saved : 'calendar';
  });
  const [selectedItemId, setSelectedItemId] = useState('');
  const [manualContentConfirmed, setManualContentConfirmed] = useState<Record<string, boolean>>({});
  const [channelDetailsOpen, setChannelDetailsOpen] = useState(false);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [themeEdits, setThemeEdits] = useState<Record<string, string>>({});
  const [dateEdits, setDateEdits] = useState<Record<string, string>>({});
  const [generationDetails, setGenerationDetails] = useState<Record<string, GenerationDetails>>({});
  const [briefAnswers, setBriefAnswers] = useState<Record<string, Record<string, string>>>({});
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [voiceProfile, setVoiceProfile] = useState<VoiceProfile | null>(null);
  const [voiceSummary, setVoiceSummary] = useState('');
  const [businessDescription, setBusinessDescription] = useState('');
  const [audienceDescription, setAudienceDescription] = useState('');
  const [contentSetupStep, setContentSetupStep] = useState<ContentSetupStep>('business');
  const [voiceExampleInput, setVoiceExampleInput] = useState('');
  const [publicationChannels, setPublicationChannels] = useState<Record<string, boolean>>(() => buildChannelSelection());
  const [platformTextEdits, setPlatformTextEdits] = useState<Record<string, string>>({});
  const [editingPlatformPostId, setEditingPlatformPostId] = useState('');
  const [mediaRecommendations, setMediaRecommendations] = useState<Record<string, MediaRecommendation>>({});
  const [mediaLoadingItemId, setMediaLoadingItemId] = useState('');
  const [mediaAssets, setMediaAssets] = useState<PhotoAsset[]>([]);
  const [mediaCoverage, setMediaCoverage] = useState<MediaCoverage | null>(null);
  const [photoAnalysisQuota, setPhotoAnalysisQuota] = useState<PhotoAnalysisQuota | null>(null);
  const [mediaLoading, setMediaLoading] = useState(false);
  const publicationDetailsRef = useRef<HTMLDivElement | null>(null);
  const [mediaUploading, setMediaUploading] = useState(false);
  const contentLoadSequenceRef = useRef(0);
  const [mediaUploadProgress, setMediaUploadProgress] = useState('');
  const [mediaAnalyzingId, setMediaAnalyzingId] = useState('');
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>('all');
  const [mediaError, setMediaError] = useState('');
  const [mediaActionMessage, setMediaActionMessage] = useState('');
  const [mediaAttentionMessage, setMediaAttentionMessage] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [deletePlanOpen, setDeletePlanOpen] = useState(false);
  const [createStep, setCreateStep] = useState<ModalStep>('setup');
  const [createDraft, setCreateDraft] = useState<CreatePlanDraft>(DEFAULT_CREATE_DRAFT);
  const [generating, setGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationCards, setGenerationCards] = useState(0);
  const mediaUploadInputRef = useRef<HTMLInputElement | null>(null);

  const demoCalendarThemes = getDemoContentCalendarThemes(language);
  const items = useMemo(() => {
    const planItems = currentPlan?.items || [];
    if (!demoMode || language === 'ru') return planItems;
    return planItems.map((item, index) => ({
      ...item,
      theme: demoCalendarThemes[index % demoCalendarThemes.length] || calendarCopy.publication,
    }));
  }, [calendarCopy.publication, currentPlan, demoCalendarThemes, demoMode, language]);
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
  const allowedPlanPeriods = useMemo(() => {
    const rawPeriods = context?.subscription?.allowed_horizons;
    const periods = Array.isArray(rawPeriods)
      ? rawPeriods.map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0)
      : [];
    return periods.length > 0 ? Array.from(new Set(periods)).sort((left, right) => left - right) : DEFAULT_PLAN_PERIODS;
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

  const loadSocialPosts = async (planId: string, loadSequence?: number, itemIds?: Set<string>) => {
    const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}/social-posts`, { method: 'GET' });
    const rawPosts: SocialPost[] = Array.isArray(response.posts) ? response.posts : [];
    const publicationPlatforms = new Set(CHANNELS.map((channel) => channel.key));
    const visibleItemIds = itemIds || new Set((currentPlan?.items || []).map((item) => item.id));
    const posts = rawPosts.filter((post) => (
      publicationPlatforms.has(String(post.platform || ''))
      && (visibleItemIds.size === 0 || visibleItemIds.has(String(post.content_plan_item_id || '')))
    ));
    if (loadSequence !== undefined && loadSequence !== contentLoadSequenceRef.current) return posts;
    setSocialPosts(posts);
    setSocialSummary(summarizeSocialPosts(posts));
    return posts;
  };

  const loadCurrentPlan = async (planId: string, loadSequence?: number) => {
    const planResponse = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}`, { method: 'GET' });
    const rawPlan: PlanPayload | null = planResponse.plan || null;
    if (loadSequence !== undefined && loadSequence !== contentLoadSequenceRef.current) return null;
    const rawItems = Array.isArray(rawPlan?.items) ? rawPlan.items : [];
    const hasLocationItems = rawItems.some((item) => Boolean(String(item.business_id || '').trim()));
    const visibleItems = hasLocationItems
      ? rawItems.filter((item) => String(item.business_id || '').trim() === String(currentBusinessId || '').trim())
      : rawItems;
    const plan = rawPlan ? { ...rawPlan, items: visibleItems } : null;
    setCurrentPlan(plan);
    if (plan?.id) {
      await loadSocialPosts(plan.id, loadSequence, new Set(visibleItems.map((item) => item.id)));
    }
    return plan;
  };

  const loadContent = async () => {
    const loadSequence = contentLoadSequenceRef.current + 1;
    contentLoadSequenceRef.current = loadSequence;
    setCurrentPlan(null);
    setSocialPosts([]);
    setSocialSummary(null);
    setSelectedItemId('');
    if (!currentBusinessId) {
      setContext(null);
      setPlans([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const contextResponse = await newAuth.makeRequest(`/content-plans/context?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      if (loadSequence !== contentLoadSequenceRef.current) return;
      setContext(contextResponse.context || null);
      const plansResponse = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      if (loadSequence !== contentLoadSequenceRef.current) return;
      const nextPlans = workingContentPlans(Array.isArray(plansResponse.plans) ? plansResponse.plans : []);
      setPlans(nextPlans);
      if (nextPlans.length > 0) {
        await loadCurrentPlan(nextPlans[0].id, loadSequence);
      } else {
        setCurrentPlan(null);
        setSocialPosts([]);
        setSocialSummary(null);
      }
    } catch (loadError) {
      if (loadSequence === contentLoadSequenceRef.current) {
        setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить контент');
      }
    } finally {
      if (loadSequence === contentLoadSequenceRef.current) setLoading(false);
    }
  };

  const openVoiceSettings = async () => {
    if (!currentBusinessId) return;
    setContentSetupStep('business');
    setVoiceOpen(true);
    setVoiceLoading(true);
    try {
      const response = await newAuth.makeRequest(`/content-voice?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      const profile = response.profile || null;
      setVoiceProfile(profile);
      setVoiceSummary(String(profile?.summary || ''));
      setBusinessDescription(String(profile?.preferences?.business_description || ''));
      setAudienceDescription(String(profile?.preferences?.audience_description || ''));
    } catch (voiceError) {
      setError(voiceError instanceof Error ? voiceError.message : 'Не удалось загрузить стиль публикаций');
    } finally {
      setVoiceLoading(false);
    }
  };

  const addVoiceExample = async () => {
    const text = voiceExampleInput.trim();
    if (!currentBusinessId || !text) return;
    setVoiceLoading(true);
    try {
      await newAuth.makeRequest('/content-voice/examples', {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId, text, origin: 'manual', quality_status: 'reference' }),
      });
      setVoiceExampleInput('');
      await openVoiceSettings();
    } catch (voiceError) {
      setError(voiceError instanceof Error ? voiceError.message : 'Не удалось добавить пример');
      setVoiceLoading(false);
    }
  };

  const deleteVoiceExample = async (exampleId: string) => {
    setVoiceLoading(true);
    try {
      await newAuth.makeRequest(`/content-voice/examples/${encodeURIComponent(exampleId)}`, { method: 'DELETE' });
      await openVoiceSettings();
    } catch (voiceError) {
      setError(voiceError instanceof Error ? voiceError.message : 'Не удалось удалить пример');
      setVoiceLoading(false);
    }
  };

  const saveVoiceProfile = async () => {
    if (!currentBusinessId) return;
    setVoiceLoading(true);
    try {
      const response = await newAuth.makeRequest('/content-voice', {
        method: 'PATCH',
        body: JSON.stringify({
          business_id: currentBusinessId,
          summary: voiceSummary,
          preferences: {
            ...(voiceProfile?.preferences || {}),
            business_description: businessDescription.trim(),
            audience_description: audienceDescription.trim(),
          },
          confirm: true,
        }),
      });
      setVoiceProfile(response.profile || null);
      setVoiceOpen(false);
      setActionMessage('Настройки контента сохранены. LocalOS будет учитывать их в новых текстах.');
    } catch (voiceError) {
      setError(voiceError instanceof Error ? voiceError.message : 'Не удалось сохранить стиль');
    } finally {
      setVoiceLoading(false);
    }
  };

  useEffect(() => {
    void loadContent();
  }, [currentBusinessId]);

  useEffect(() => {
    setChannelDetailsOpen(false);
    setEditingPlatformPostId('');
  }, [selectedItemId]);

  useEffect(() => {
    if (!selectedItemId) return;
    const item = items.find((candidate) => candidate.id === selectedItemId) || null;
    const itemPosts = item ? postsByItem[item.id] || [] : [];
    setPublicationChannels(buildChannelSelection(resolveItemSelectedChannels(item, itemPosts, currentPlan)));
  }, [currentPlan, items, postsByItem, selectedItemId]);

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
    const requested = new URLSearchParams(location.search).get('section');
    if (requested === 'media' || requested === 'audience' || requested === 'calendar') {
      setSection(requested);
    }
  }, [location.search]);

  useEffect(() => {
    if (section !== 'media' || !currentBusinessId) return;
    void loadMediaAssets();
  }, [section, currentBusinessId]);

  useEffect(() => {
    setCreateDraft((prev) => {
      if (allowedPlanPeriods.includes(prev.periodDays)) return prev;
      return { ...prev, periodDays: allowedPlanPeriods[0] || 30 };
    });
  }, [allowedPlanPeriods]);

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
    setPublicationChannels(buildChannelSelection(resolveItemSelectedChannels(item, postsByItem[item.id] || [], currentPlan)));
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

  const loadOriginalPhotoBlob = async (asset: PhotoAsset) => {
    const assetId = String(asset.id || '').trim();
    if (!assetId) throw new Error('Сначала выберите фото для публикации');
    const token = newAuth.getToken() || '';
    const response = await fetch(`${API_URL}/api/media-intelligence/photos/${encodeURIComponent(assetId)}/file?variant=original`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) throw new Error('Не удалось получить исходное фото');
    const blob = await response.blob();
    if (!blob.type.startsWith('image/')) throw new Error('Исходный файл не является изображением');
    return blob;
  };

  const photoFileExtension = (blob: Blob) => {
    if (blob.type === 'image/png') return 'png';
    if (blob.type === 'image/webp') return 'webp';
    return 'jpg';
  };

  const savePhotoBlob = (asset: PhotoAsset, blob: Blob) => {
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = `localos-photo-${String(asset.id || 'original')}.${photoFileExtension(blob)}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  };

  const downloadOriginalPhoto = async (asset: PhotoAsset) => {
    setBusyAction('photo-download');
    setError('');
    try {
      const blob = await loadOriginalPhotoBlob(asset);
      savePhotoBlob(asset, blob);
      setActionMessage('Исходное фото скачано без уменьшения качества.');
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : 'Не удалось скачать фото');
    } finally {
      setBusyAction('');
    }
  };

  const copyOriginalPhoto = async (asset: PhotoAsset) => {
    setBusyAction('photo-copy');
    setError('');
    let originalBlob: Blob | null = null;
    try {
      originalBlob = await loadOriginalPhotoBlob(asset);
      if (!navigator.clipboard?.write || typeof ClipboardItem === 'undefined') {
        savePhotoBlob(asset, originalBlob);
        setActionMessage('Браузер не умеет копировать изображения. Исходное фото скачано без уменьшения качества.');
        return;
      }
      await navigator.clipboard.write([new ClipboardItem({ [originalBlob.type]: originalBlob })]);
      setActionMessage('Исходное фото скопировано. Его можно вставить при ручном размещении.');
    } catch (copyError) {
      if (originalBlob) {
        savePhotoBlob(asset, originalBlob);
        setActionMessage('Буфер обмена не принял изображение. Исходное фото скачано без уменьшения качества.');
        return;
      }
      setError(copyError instanceof Error ? copyError.message : 'Не удалось скопировать фото');
    } finally {
      setBusyAction('');
    }
  };

  const loadMediaAssets = async () => {
    if (!currentBusinessId) return;
    setMediaLoading(true);
    setMediaError('');
    setPhotoAnalysisQuota(null);
    try {
      const response = await newAuth.makeRequest(`/media-intelligence/photos?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      setMediaAssets(Array.isArray(response.photos) ? response.photos : []);
      setMediaCoverage(response.coverage || null);
      setPhotoAnalysisQuota(response.photo_quota || null);
    } catch (mediaLoadError) {
      setMediaError(mediaLoadError instanceof Error ? mediaLoadError.message : 'Не удалось загрузить медиатеку');
    } finally {
      setMediaLoading(false);
    }
  };

  const requestMediaAssetAnalysis = async (assetId?: string): Promise<PhotoAnalysisResult> => {
    if (!currentBusinessId || !assetId) throw new Error('Фото не выбрано');
    return newAuth.makeRequest(`/media-intelligence/photos/${encodeURIComponent(assetId)}/analyze`, {
      method: 'POST',
      body: JSON.stringify({ business_id: currentBusinessId }),
    });
  };

  const analyzeMediaAsset = async (assetId?: string) => {
    if (!currentBusinessId || !assetId) return;
    setMediaAnalyzingId(assetId);
    setMediaError('');
    try {
      const result = await requestMediaAssetAnalysis(assetId);
      await loadMediaAssets();
      const includedAnalyses = result.billing_source === 'network_photo_quota' ? 1 : 0;
      const cachedAnalyses = result.billing_source === 'cache' || result.status === 'cached' ? 1 : 0;
      setMediaActionMessage(`Фото проанализировано. ${buildPhotoAnalysisCostMessage(Number(result.charged_credits || 0), includedAnalyses, cachedAnalyses)}`);
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
    const token = newAuth.getToken() || '';
    const response = await fetch(`${API_URL}/api/media-intelligence/photos/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: formData,
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || data.message || `Не удалось загрузить ${file.name}`);
    }
    return data.photo && typeof data.photo === 'object' ? data.photo : {};
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
    setMediaAttentionMessage('');
    setMediaUploadProgress('');
    const uploaded: PhotoAsset[] = [];
    let analyzedCount = 0;
    let chargedCredits = 0;
    let includedAnalyses = 0;
    let cachedAnalyses = 0;
    let waitingForCreditsCount = 0;
    const failed: string[] = [];
    try {
      for (const [index, file] of files.entries()) {
        let photoUploaded = false;
        setMediaUploadProgress(`Загружаем ${index + 1} из ${files.length}`);
        try {
          const photo = await uploadSingleMediaPhoto(file);
          uploaded.push(photo);
          photoUploaded = true;
          setMediaUploadProgress(`Анализируем ${index + 1} из ${files.length}`);
          const analysis = await requestMediaAssetAnalysis(photo?.id);
          analyzedCount += 1;
          chargedCredits += Number(analysis.charged_credits || 0);
          if (analysis.billing_source === 'network_photo_quota') includedAnalyses += 1;
          if (analysis.billing_source === 'cache' || analysis.status === 'cached') cachedAnalyses += 1;
        } catch (uploadError) {
          if (photoUploaded && isInsufficientPhotoCreditsError(uploadError)) {
            waitingForCreditsCount += 1;
          } else {
            failed.push(`${file.name}: ${uploadError instanceof Error ? uploadError.message : 'не удалось загрузить'}`);
          }
        }
      }
      await loadMediaAssets();
      const resultSummary = `Фото загружены: ${uploaded.length} из ${files.length}. Проанализировано: ${analyzedCount}. ${buildPhotoAnalysisCostMessage(chargedCredits, includedAnalyses, cachedAnalyses)}`;
      if (waitingForCreditsCount > 0) {
        setMediaAttentionMessage(`${resultSummary} Кредиты закончились. Ждут анализа: ${waitingForCreditsCount} фото. Файлы сохранены. Пополните баланс и запустите анализ в медиатеке.`);
      }
      if (failed.length > 0) {
        setMediaError(`${resultSummary} Не удалось обработать: ${failed.slice(0, 3).join('; ')}${failed.length > 3 ? '...' : ''}`);
      } else if (waitingForCreditsCount === 0) {
        setMediaActionMessage(resultSummary);
      }
    } finally {
      setMediaUploading(false);
      setMediaUploadProgress('');
      if (mediaUploadInputRef.current) {
        mediaUploadInputRef.current.value = '';
      }
    }
  };

  const recordPhotoUsage = async (assetId: string) => {
    if (!selectedItem || !currentBusinessId) return;
    if (!assetId) {
      setError('Сначала загрузите или выберите подходящее фото.');
      return;
    }
    setBusyAction('photo-usage');
    setError('');
    try {
      const response = await newAuth.makeRequest(`/media-intelligence/photos/${encodeURIComponent(assetId)}/usage`, {
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
      const approvalsReset = Number(response.approvals_reset || 0);
      setActionMessage(
        approvalsReset > 0
          ? `Фото сохранено. Проверьте итоговый вид и подтвердите публикации заново: ${approvalsReset}.`
          : 'Фото сохранено для публикации. Повторный анализ и списание кредитов не нужны.',
      );
      await loadMediaRecommendation(selectedItem.id);
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      if (section === 'media') await loadMediaAssets();
    } catch (usageError) {
      setError(usageError instanceof Error ? usageError.message : 'Не удалось сохранить фото для публикации');
    } finally {
      setBusyAction('');
    }
  };

  const recordSelectedPhotoUsage = async () => {
    if (!selectedItem) return;
    const recommendation = mediaRecommendations[selectedItem.id];
    await recordPhotoUsage(String(recommendation?.selected_asset?.id || ''));
  };

  const saveSelectedItem = async () => {
    if (!selectedItem) return;
    setBusyAction('save');
    setError('');
    setActionMessage('');
    try {
      const selectedPlatforms = selectedChannelKeys(publicationChannels);
      if (selectedPlatforms.length === 0) {
        setError('Выберите хотя бы один канал публикации.');
        return;
      }
      const storedPlatforms = resolveItemSelectedChannels(selectedItem, selectedPosts, currentPlan);
      const channelsChanged = !sameSelectedChannels(selectedPlatforms, storedPlatforms);
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(selectedItem.id)}`, {
        method: 'PUT',
        body: JSON.stringify({
          theme: themeEdits[selectedItem.id],
          scheduled_for: dateEdits[selectedItem.id],
          draft_text: draftEdits[selectedItem.id],
          selected_channels: selectedPlatforms,
        }),
      });
      const plan = response.plan || null;
      setCurrentPlan(plan);
      if (channelsChanged && selectedPosts.length > 0) {
        await newAuth.makeRequest('/content-plans/social-posts/bulk-prepare', {
          method: 'POST',
          body: JSON.stringify({
            item_ids: [selectedItem.id],
            platforms: selectedPlatforms,
            replace_platforms: true,
          }),
        });
      }
      if (plan?.id) await loadSocialPosts(plan.id);
      setActionMessage('Изменения сохранены.');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Не удалось сохранить публикацию');
    } finally {
      setBusyAction('');
    }
  };

  const generateSelectedDraft = async () => {
    if (!selectedItem) return;
    const startedAt = Date.now();
    setBusyAction('generate-draft');
    setDraftGenerationReady(false);
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
      const generation: GenerationDetails & { success?: boolean; source?: string } = response.generation || {};
      setGenerationDetails((previous) => ({ ...previous, [selectedItem.id]: generation }));
      if (generation.status === 'needs_context') {
        setBriefAnswers((previous) => ({
          ...previous,
          [selectedItem.id]: {
            ...(refreshedItem?.metadata_json?.brief_answers || {}),
            ...(previous[selectedItem.id] || {}),
          },
        }));
        setActionMessage('');
        return;
      }
      const remaining = Math.max(0, 1200 - (Date.now() - startedAt));
      if (remaining) await new Promise<void>((resolve) => window.setTimeout(resolve, remaining));
      const refreshedText = String(refreshedItem?.draft_text || '').trim();
      const refreshedGenerationSource = itemGenerationSource(refreshedItem);
      const hasGeneratedText = Boolean(refreshedText) && refreshedGenerationSource !== 'fallback';
      if (generation.success === false || generation.source === 'fallback' || !hasGeneratedText) {
        setActionMessage('');
        setError(String(generation.message || 'Не удалось написать текст. Попробуйте ещё раз.'));
      } else {
        setDraftGenerationReady(true);
        setActionMessage(String(generation.message || 'Текст готов. Проверьте его и утвердите публикацию.'));
        await new Promise<void>((resolve) => window.setTimeout(resolve, 700));
      }
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : 'Не удалось сгенерировать текст');
    } finally {
      setBusyAction('');
      setDraftGenerationReady(false);
    }
  };

  const saveBriefAndGenerate = async () => {
    if (!selectedItem) return;
    setBusyAction('save-context');
    setError('');
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(selectedItem.id)}`, {
        method: 'PUT',
        body: JSON.stringify({ brief_answers: briefAnswers[selectedItem.id] || {} }),
      });
      if (response.plan) setCurrentPlan(response.plan);
      setBusyAction('');
      await generateSelectedDraft();
    } catch (contextError) {
      setError(contextError instanceof Error ? contextError.message : 'Не удалось сохранить детали');
      setBusyAction('');
    }
  };

  const selectDraftVariant = async (variant: GenerationAlternative) => {
    if (!selectedItem || !variant.id) return;
    setBusyAction(`variant-${variant.id}`);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(selectedItem.id)}`, {
        method: 'PUT',
        body: JSON.stringify({ selected_variant_id: variant.id }),
      });
      const plan = response.plan || null;
      setCurrentPlan(plan);
      const refreshedItem = Array.isArray(plan?.items) ? plan.items.find((nextItem: PlanItem) => nextItem.id === selectedItem.id) : null;
      setDraftEdits((previous) => ({ ...previous, [selectedItem.id]: String(refreshedItem?.draft_text || variant.text || '') }));
      setActionMessage(`Выбран подход «${variant.angle || 'Другой вариант'}». Проверьте текст перед утверждением.`);
    } catch (variantError) {
      setError(variantError instanceof Error ? variantError.message : 'Не удалось выбрать вариант');
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

  const prepareSelectedItem = async (forceVariants = false) => {
    if (!selectedItem || !currentPlan?.id) return [];
    setBusyAction('prepare');
    setError('');
    try {
      const selectedPlatforms = selectedChannelKeys(publicationChannels);
      if (selectedPlatforms.length === 0) {
        setError('Выберите хотя бы один канал публикации.');
        return [];
      }
      const saveResponse = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(selectedItem.id)}`, {
        method: 'PUT',
        body: JSON.stringify({
          theme: themeEdits[selectedItem.id] ?? selectedItem.theme ?? '',
          scheduled_for: dateEdits[selectedItem.id] ?? selectedItem.scheduled_for ?? '',
          draft_text: draftEdits[selectedItem.id] ?? selectedItem.draft_text ?? '',
          selected_channels: selectedPlatforms,
        }),
      });
      if (saveResponse.plan) setCurrentPlan(saveResponse.plan);
      const response = await newAuth.makeRequest('/content-plans/social-posts/bulk-prepare', {
        method: 'POST',
        body: JSON.stringify({
          item_ids: [selectedItem.id],
          platforms: selectedPlatforms,
          replace_platforms: true,
          force_variants: forceVariants,
        }),
      });
      const removed = Array.isArray(response.removed_platforms) ? response.removed_platforms.length : 0;
      const preserved = Array.isArray(response.preserved_platforms) ? response.preserved_platforms.length : 0;
      setActionMessage(
        preserved > 0
          ? `Версии обновлены. Запланированные или опубликованные тексты сохранены: ${preserved}.`
          : removed > 0
            ? `Версии обновлены. Ненужные черновики убраны: ${removed}.`
            : forceVariants
              ? `Автоматические версии обновлены: ${selectedPlatforms.length}. Ручные правки сохранены.`
              : `Подготовлено версий для каналов: ${selectedPlatforms.length}.`,
      );
      return await loadSocialPosts(currentPlan.id);
    } catch (prepareError) {
      setError(prepareError instanceof Error ? prepareError.message : 'Не удалось подготовить каналы');
      return [];
    } finally {
      setBusyAction('');
    }
  };

  const savePlatformText = async (post: SocialPost) => {
    if (!currentPlan?.id || !post.id) return;
    setBusyAction(`platform-text-${post.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}`, {
        method: 'PATCH',
        body: JSON.stringify({
          platform_text: platformTextEdits[post.id] ?? post.platform_text ?? '',
          base_text: post.base_text || draftEdits[selectedItem?.id || ''] || '',
        }),
      });
      await loadSocialPosts(currentPlan.id);
      setEditingPlatformPostId('');
      setActionMessage(`${platformShortLabel(post)}: текст сохранён. Проверьте и подтвердите публикацию.`);
    } catch (platformError) {
      setError(platformError instanceof Error ? platformError.message : 'Не удалось сохранить текст канала');
    } finally {
      setBusyAction('');
    }
  };

  const recordPublishedResult = async (post: SocialPost, eventType: 'inquiry' | 'lead') => {
    if (!currentPlan?.id) return;
    setBusyAction(`result-${post.id}-${eventType}`);
    setError('');
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/attribution-events`, {
        method: 'POST',
        body: JSON.stringify({ event_type: eventType, value: 1, event_source: 'manual' }),
      });
      await loadSocialPosts(currentPlan.id);
      setActionMessage(eventType === 'lead' ? 'Заявка сохранена и попадёт в корректировку следующего плана.' : 'Обращение сохранено и попадёт в корректировку следующего плана.');
    } catch (resultError) {
      setError(resultError instanceof Error ? resultError.message : 'Не удалось сохранить результат');
    } finally {
      setBusyAction('');
    }
  };

  const markPlacementPublished = async (post: SocialPost) => {
    if (!currentPlan?.id) return;
    const providerPostUrl = typeof window === 'undefined'
      ? ''
      : window.prompt('Вставьте ссылку на опубликованный пост. Если площадка не даёт ссылку, оставьте поле пустым.', '') ?? '';
    setBusyAction(`manual-published-${post.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/mark-manual-published`, {
        method: 'POST',
        body: JSON.stringify({
          provider_post_url: providerPostUrl.trim(),
          content_confirmed: Boolean(manualContentConfirmed[post.id]),
        }),
      });
      await loadSocialPosts(currentPlan.id);
      setActionMessage(`${platformShortLabel(post)}: публикация отмечена размещённой.`);
    } catch (markError) {
      setError(markError instanceof Error ? markError.message : 'Не удалось отметить размещение');
    } finally {
      setBusyAction('');
    }
  };

  const openManualPublish = async (post: SocialPost) => {
    if (!currentPlan?.id) return;
    setBusyAction(`manual-publish-${post.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/use-manual-publish`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Ручное размещение выбрано в контент-плане.' }),
      });
      await loadSocialPosts(currentPlan.id);
      setActionMessage(`${platformShortLabel(post)}: подготовлено для ручного размещения.`);
      setChannelDetailsOpen(true);
    } catch (manualError) {
      setError(manualError instanceof Error ? manualError.message : 'Не удалось выбрать ручное размещение');
    } finally {
      setBusyAction('');
    }
  };

  const approveSelectedItem = async () => {
    if (!selectedItem || !currentPlan?.id) return;
    setBusyAction('approve');
    setError('');
    setActionMessage('');
    try {
      const currentDraftText = String(draftEdits[selectedItem.id] ?? selectedItem.draft_text ?? '');
      const currentTheme = String(themeEdits[selectedItem.id] ?? selectedItem.theme ?? '');
      const currentDate = String(dateEdits[selectedItem.id] ?? selectedItem.scheduled_for ?? '');
      const selectedPlatforms = selectedChannelKeys(publicationChannels);
      if (selectedPlatforms.length === 0) {
        setError('Выберите хотя бы один канал публикации.');
        return;
      }
      const storedPlatforms = resolveItemSelectedChannels(selectedItem, selectedPosts, currentPlan);
      const channelsChanged = !sameSelectedChannels(selectedPlatforms, storedPlatforms);
      const draftChanged = currentDraftText !== String(selectedItem.draft_text ?? '');
      const itemChanged = draftChanged
        || currentTheme !== String(selectedItem.theme ?? '')
        || normalizeIsoDate(currentDate) !== normalizeIsoDate(selectedItem.scheduled_for)
        || channelsChanged;

      if (itemChanged) {
        const saveResponse = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(selectedItem.id)}`, {
          method: 'PUT',
          body: JSON.stringify({
            theme: currentTheme,
            scheduled_for: currentDate,
            draft_text: currentDraftText,
            selected_channels: selectedPlatforms,
          }),
        });
        if (saveResponse.plan) setCurrentPlan(saveResponse.plan);
      }

      let posts = postsByItem[selectedItem.id] || [];
      if (posts.length === 0 || itemChanged) {
        const prepareResponse = await newAuth.makeRequest('/content-plans/social-posts/bulk-prepare', {
          method: 'POST',
          body: JSON.stringify({
            item_ids: [selectedItem.id],
            platforms: selectedPlatforms,
            replace_platforms: true,
          }),
        });
        posts = Array.isArray(prepareResponse.posts)
          ? prepareResponse.posts.filter((post: SocialPost) => post.content_plan_item_id === selectedItem.id)
          : [];
      }
      const postIds = posts
        .filter((post) => !['queued', 'publishing', 'published'].includes(String(post.status || '').toLowerCase()))
        .map((post) => post.id)
        .filter(Boolean);
      if (postIds.length === 0) return;
      const approveResponse = await newAuth.makeRequest('/social-posts/bulk-approve', {
        method: 'POST',
        body: JSON.stringify({ post_ids: postIds }),
      });
      const failedApprovals = Array.isArray(approveResponse.failed) ? approveResponse.failed : [];
      if (failedApprovals.length > 0) {
        throw new Error(String(failedApprovals[0]?.error || 'Не удалось утвердить публикации'));
      }
      await loadSocialPosts(currentPlan.id);
      setActionMessage(itemChanged ? 'Изменения сохранены, публикации утверждены.' : 'Публикации утверждены.');
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
          setError('Сначала подготовьте версии для каналов. После этого их можно проверить и утвердить.');
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
    if (getSelectedCount(createDraft.channels) === 0) {
      setError('Выберите хотя бы один канал для контент-плана.');
      return;
    }
    const generationStartedAt = Date.now();
    const normalizedPeriodDays = allowedPlanPeriods.includes(createDraft.periodDays)
      ? createDraft.periodDays
      : allowedPlanPeriods[0] || 30;
    setGenerating(true);
    setCreateOpen(false);
    setGenerationProgress(8);
    setGenerationCards(2);
    setCreateDraft((prev) => ({ ...prev, periodDays: normalizedPeriodDays }));
    setError('');
    try {
      const response = await newAuth.makeRequest('/content-plans/generate', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          scope_type: selectedScopeOption?.scope_type || 'single_business',
          scope_target_id: selectedScopeOption?.scope_target_id || currentBusinessId,
          period_days: normalizedPeriodDays,
          density: createDraft.frequency === 'active' ? 'active' : createDraft.frequency === 'light' ? 'light' : 'standard',
          content_mix: {
            services: true,
            seo: true,
            sales: Boolean(createDraft.contentTypes.promos),
            audit: Boolean(createDraft.contentTypes.faq || createDraft.contentTypes.reviews),
            seasonal: Boolean(createDraft.contentTypes.seasonal),
            channels: CHANNELS.filter((channel) => createDraft.channels[channel.key]).map((channel) => channel.key),
          },
        }),
      });
      const plan = response.plan || null;
      setCurrentPlan(plan);
      if (plan?.id) {
        await loadSocialPosts(plan.id);
      }
      const plansResponse = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      setPlans(workingContentPlans(Array.isArray(plansResponse.plans) ? plansResponse.plans : []));
      const elapsed = Date.now() - generationStartedAt;
      const remainingDelay = Math.max(750, PLAN_GENERATION_MIN_DURATION_MS - elapsed);
      window.setTimeout(() => {
        setGenerationProgress(100);
        setGenerationCards(Math.max(32, normalizedPeriodDays));
        setGenerating(false);
      }, remainingDelay);
    } catch (createError) {
      setGenerating(false);
      setError(createError instanceof Error ? createError.message : 'Не удалось создать план');
    }
  };

  const deleteCurrentPlan = async () => {
    if (!currentBusinessId || !currentPlan?.id) return;
    setBusyAction('delete-plan');
    setError('');
    setActionMessage('');
    try {
      await newAuth.makeRequest(`/content-plans/${encodeURIComponent(currentPlan.id)}`, { method: 'DELETE' });
      const plansResponse = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      const nextPlans = workingContentPlans(Array.isArray(plansResponse.plans) ? plansResponse.plans : []);
      setPlans(nextPlans);
      setSelectedItemId('');
      setSocialPosts([]);
      setSocialSummary(null);
      setDeletePlanOpen(false);
      const nextPlan = nextPlans.find((plan) => plan.id !== currentPlan.id) || nextPlans[0] || null;
      if (nextPlan?.id) {
        await loadCurrentPlan(nextPlan.id);
      } else {
        setCurrentPlan(null);
      }
      setActionMessage('Контент-план удалён.');
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Не удалось удалить контент-план');
    } finally {
      setBusyAction('');
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

  const togglePublicationChannel = (key: string) => {
    setPublicationChannels((previous) => ({ ...previous, [key]: !previous[key] }));
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
                    {allowedPlanPeriods.map((days) => (
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
                  <div className="mt-2 text-xs leading-5 text-slate-500">
                    Доступно по текущему тарифу.
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
                  {plannedPublicationCount(createDraft.periodDays, createDraft.frequency)} публикаций
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
            <Button type="button" onClick={createPlan} disabled={getSelectedCount(createDraft.channels) === 0} className="bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-500">
              Создать план
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const renderDeletePlanDialog = () => (
    <Dialog open={deletePlanOpen} onOpenChange={setDeletePlanOpen}>
      <DialogContent className="max-w-lg rounded-3xl border-slate-200">
        <DialogHeader>
          <DialogTitle>Удалить контент-план?</DialogTitle>
          <DialogDescription>
            План «{currentPlan?.title || 'Контент-план'}» и все его публикации будут удалены из календаря. Уже опубликованные внешние посты это действие не удаляет.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={() => setDeletePlanOpen(false)} disabled={busyAction === 'delete-plan'}>
            Оставить
          </Button>
          <Button
            type="button"
            onClick={deleteCurrentPlan}
            disabled={busyAction === 'delete-plan'}
            className="bg-red-600 text-white hover:bg-red-700"
          >
            {busyAction === 'delete-plan' ? 'Удаляем...' : 'Удалить план'}
          </Button>
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
        className="w-full min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white px-2.5 py-2 text-left shadow-sm transition-[border-color,box-shadow] hover:border-slate-300 hover:shadow-md"
      >
        <div className="line-clamp-2 break-words text-xs font-semibold leading-4 text-slate-950 [overflow-wrap:anywhere]">
          {item.theme || item.goal || calendarCopy.publication}
        </div>
        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
          {(channels.length ? channels : [calendarCopy.content]).map((channel) => (
            <span key={channel} className="inline-flex max-w-full min-w-0 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium leading-4 text-slate-600 [overflow-wrap:anywhere]">
              {channel}
            </span>
          ))}
        </div>
        <div className="mt-1.5 flex min-w-0 flex-wrap gap-1">
          <span className={cn('inline-flex max-w-full min-w-0 items-center justify-center whitespace-normal break-words rounded-full px-1.5 py-0.5 text-center text-[10px] font-semibold leading-4 ring-1 [overflow-wrap:anywhere]', getStatusClassName(calendarState.status))}>
            {localizeContentCalendarStatus(calendarState.status, calendarCopy)}
          </span>
          <span className={cn('inline-flex max-w-full min-w-0 items-center justify-center whitespace-normal break-words rounded-full px-1.5 py-0.5 text-center text-[10px] font-semibold leading-4 ring-1 [overflow-wrap:anywhere]', getStatusClassName(calendarState.action))}>
            {localizeContentCalendarStatus(calendarState.action, calendarCopy)}
          </span>
        </div>
      </button>
    );
  };

  const renderCalendar = () => (
    <div className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-2xl border border-slate-200 bg-slate-200">
        {calendarCopy.weekdays.map((day) => (
          <div key={day} className="min-w-0 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
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
                'min-w-0 overflow-hidden min-h-[150px] bg-white p-2',
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
                    {calendarCopy.more} {dayItems.length - 3}
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
              className="flex w-full min-w-0 flex-col gap-3 overflow-hidden px-3 py-4 text-left transition-colors hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <div className="break-words text-sm font-semibold text-slate-950 [overflow-wrap:anywhere]">{item.theme || item.goal || calendarCopy.publication}</div>
                <div className="mt-1 text-sm text-slate-500">{formatDate(item.scheduled_for, language)} · {(posts.length || getSelectedCount(createDraft.channels))} {calendarCopy.channels}</div>
              </div>
              <div className="flex min-w-0 max-w-full flex-wrap gap-2 sm:justify-end">
                <span className={cn('inline-flex max-w-full min-w-0 items-center justify-center whitespace-normal break-words rounded-full px-3 py-1 text-center text-xs font-semibold ring-1 [overflow-wrap:anywhere]', getStatusClassName(calendarState.status))}>
                  {localizeContentCalendarStatus(calendarState.status, calendarCopy)}
                </span>
                <span className={cn('inline-flex max-w-full min-w-0 items-center justify-center whitespace-normal break-words rounded-full px-3 py-1 text-center text-xs font-semibold ring-1 [overflow-wrap:anywhere]', getStatusClassName(calendarState.action))}>
                  {localizeContentCalendarStatus(calendarState.action, calendarCopy)}
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
        <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{calendarCopy.today}</div>
        <div className="mt-4 space-y-3">
          <Insight icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} text={`${calendarCopy.createdPosts}: ${items.filter(itemHasUsableText).length}`} />
          <Insight icon={<AlertCircle className="h-4 w-4 text-amber-600" />} text={`${calendarCopy.requiresReview}: ${needsReviewCount}`} />
          <Insight icon={<Lightbulb className="h-4 w-4 text-blue-600" />} text={calendarCopy.eventSuggestion} detail={calendarCopy.eventReason} />
          <Insight icon={<Star className="h-4 w-4 text-violet-600" />} text={calendarCopy.competitorSuggestion} detail={calendarCopy.competitorReason} />
          <Insight icon={<Eye className="h-4 w-4 text-slate-600" />} text={calendarCopy.photoSuggestion} detail={calendarCopy.photoReason} />
        </div>
      </div>
      <div className="rounded-[28px] border border-slate-200 bg-slate-950 p-5 text-white shadow-sm">
        <div className="text-sm font-semibold text-slate-300">{calendarCopy.nextAction}</div>
        <div className="mt-2 text-xl font-semibold">
          {needsReviewCount > 0 ? calendarCopy.reviewPosts : nextItem ? calendarCopy.nearestReady : calendarCopy.createPlan}
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          {needsReviewCount > 0
            ? calendarCopy.reviewHint
            : nextItem
              ? fillContentCalendarTemplate(calendarCopy.nextHint, { date: formatDate(nextItem.scheduled_for, language) })
              : calendarCopy.prepareHint}
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
              {photoAnalysisQuota ? (
                <p className="mt-2 text-sm font-medium text-emerald-700">
                  Для сети доступно бесплатно: <span className="tabular-nums">{Number(photoAnalysisQuota.remaining_analyses || 0)}</span> из <span className="tabular-nums">{Number(photoAnalysisQuota.granted_analyses || 0)}</span> анализов фото.
                </p>
              ) : null}
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
        {mediaAttentionMessage ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium leading-6 text-amber-900">
            {mediaAttentionMessage}
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
    const hasUnsavedDraftChanges = Boolean(item)
      && String(draftEdits[item.id] ?? item.draft_text ?? '') !== String(item.draft_text ?? '');
    const currentItemChannels = selectedChannelKeys(publicationChannels);
    const storedItemChannels = resolveItemSelectedChannels(item, selectedPosts, currentPlan);
    const hasUnsavedItemChanges = Boolean(item) && (
      hasUnsavedDraftChanges
      || String(themeEdits[item.id] ?? item.theme ?? '') !== String(item.theme ?? '')
      || normalizeIsoDate(dateEdits[item.id] ?? item.scheduled_for) !== normalizeIsoDate(item.scheduled_for)
      || !sameSelectedChannels(currentItemChannels, storedItemChannels)
    );
    const hasFallbackDraft = itemGenerationSource(item) === 'fallback';
    const hasDraftText = Boolean(currentDraftText) && itemGenerationSource(item) !== 'fallback';
    const storedBrief = item?.metadata_json?.content_brief_v1;
    const storedAlternatives = item?.metadata_json?.content_generation_v2?.variants?.filter((variant) => variant.quality_passed) || [];
    const generation = item ? generationDetails[item.id] || {
      status: itemGenerationSource(item) === 'needs_context' ? 'needs_context' : hasDraftText ? 'generated' : undefined,
      brief: storedBrief,
      missing_fields: storedBrief?.missing_fields,
      questions: storedBrief?.questions,
      sources: storedBrief?.sources,
      alternatives: storedAlternatives,
    } : {};
    const needsContext = generation.status === 'needs_context'
      || generation.source === 'needs_context'
      || itemGenerationSource(item) === 'needs_context';
    const generationBrief = generation.brief || storedBrief;
    const generationSources = generation.sources || generationBrief?.sources || [];
    const generationAlternatives = (generation.alternatives || storedAlternatives).filter((variant) => variant.quality_passed !== false);
    const selectedChannelCount = getSelectedCount(publicationChannels);
    const channelCount = hasPosts ? selectedPosts.length : selectedChannelCount;
    const needsReviewChannelCount = selectedPosts.filter((post) => getChannelStatusLabel(post.status) === 'Нужно проверить').length;
    const readyTextChannelCount = selectedPosts.filter((post) => getChannelStatusLabel(post.status) === 'Текст готов').length;
    const approvedPostCount = selectedPosts.filter((post) => String(post.status || '').toLowerCase() === 'approved').length;
    const scheduledPostCount = selectedPosts.filter((post) => isQueuedOrHandledStatus(post.status)).length;
    const blockedChannelCount = selectedPosts.filter((post) => isAutomaticSendBlockedStatus(post.status)).length;
    const scheduleAlreadyHandled = scheduledPostCount > 0 && approvedPostCount === 0 && needsReviewChannelCount === 0;
    const canQueueSelectedItem = approvedPostCount > 0 && needsReviewChannelCount === 0;
    const queueNeedsAttention = hasPosts && !canQueueSelectedItem && !scheduleAlreadyHandled;
    const needsPlatformPreparation = hasDraftText && (!hasPosts || hasUnsavedItemChanges);
    const canApproveSelectedItem = hasDraftText
      && hasPosts
      && !hasUnsavedItemChanges
      && needsReviewChannelCount > 0;
    const approveButtonLabel = busyAction === 'approve'
      ? 'Утверждаем...'
      : hasUnsavedDraftChanges && canApproveSelectedItem
        ? 'Сохранить и утвердить'
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
        ? 'Сначала подготовьте версии для каналов, чтобы проверить тексты для каждой площадки.'
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
      : selectedChannelCount > 0
        ? `Выбрано: ${selectedChannelCount}`
        : 'Выберите каналы';
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
                      {busyAction === 'generate-draft'
                        ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        : <Wand2 className="mr-2 h-4 w-4" />}
                      <span translate="no" className="notranslate">
                        {busyAction === 'generate-draft'
                          ? 'Пишем...'
                          : hasDraftText
                            ? 'Сгенерировать заново'
                            : 'Сгенерировать текст'}
                      </span>
                    </Button>
                  </div>
                  {busyAction === 'generate-draft' ? <DraftGenerationFeedback ready={draftGenerationReady} /> : null}
                  {needsContext ? (
                    <div
                      ref={publicationDetailsRef}
                      id="publication-details"
                      tabIndex={-1}
                      className="scroll-mt-6 rounded-[24px] bg-amber-50 p-4 outline-none shadow-[inset_0_0_0_1px_rgba(245,158,11,0.16)] focus-visible:ring-2 focus-visible:ring-amber-500"
                    >
                      <div className="flex items-start gap-3">
                        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-amber-100 text-amber-800"><Lightbulb className="h-5 w-5" /></span>
                        <div>
                          <div className="text-sm font-semibold text-amber-950">Нужно немного конкретики</div>
                          <p className="mt-1 text-pretty text-sm leading-6 text-amber-900">LocalOS не будет заполнять пробелы общими рекламными фразами.</p>
                        </div>
                      </div>
                      <div className="mt-4 space-y-3">
                        {(generation.missing_fields || []).slice(0, 3).map((field, index) => (
                          <label key={field} className="block">
                            <span className="text-sm font-medium text-amber-950">{(generation.questions || [])[index] || 'Добавьте подтверждённую деталь'}</span>
                            <Input
                              value={briefAnswers[item.id]?.[field] ?? item.metadata_json?.brief_answers?.[field] ?? ''}
                              onChange={(event) => setBriefAnswers((previous) => ({
                                ...previous,
                                [item.id]: {
                                  ...(item.metadata_json?.brief_answers || {}),
                                  ...(previous[item.id] || {}),
                                  [field]: event.target.value,
                                },
                              }))}
                              className="mt-2 min-h-11 rounded-xl border-amber-200 bg-white"
                            />
                          </label>
                        ))}
                      </div>
                      <Button type="button" onClick={() => { void saveBriefAndGenerate(); }} disabled={Boolean(busyAction)} className="mt-4 min-h-11 rounded-2xl bg-amber-900 text-white hover:bg-amber-800 active:scale-[0.96] transition-transform">
                        {busyAction === 'save-context' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}
                        Сохранить и подготовить текст
                      </Button>
                    </div>
                  ) : null}
                  <Textarea
                    value={draftEdits[item.id] ?? item.draft_text ?? ''}
                    onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setDraftEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                    className="min-h-[260px] rounded-2xl border-slate-200 text-base leading-7"
                    placeholder="Текст публикации"
                  />
                  {generationAlternatives.length > 1 ? (
                    <details className="rounded-2xl bg-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
                      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 text-sm font-semibold text-slate-800">
                        Другой подход <ChevronDown className="h-4 w-4 text-slate-400" />
                      </summary>
                      <div className="space-y-2 px-3 pb-3">
                        {generationAlternatives.map((variant) => (
                          <button key={variant.id} type="button" onClick={() => { void selectDraftVariant(variant); }} className="w-full rounded-2xl bg-slate-50 p-3 text-left transition-colors hover:bg-slate-100 active:scale-[0.96] transition-transform">
                            <span className="text-sm font-semibold text-slate-900">{variant.angle || 'Другой вариант'}</span>
                            <span className="mt-1 line-clamp-3 block text-pretty text-sm leading-6 text-slate-600">{variant.text}</span>
                          </button>
                        ))}
                      </div>
                    </details>
                  ) : null}
                  {generationBrief ? (
                    <details className="rounded-2xl bg-slate-50 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]">
                      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 text-sm font-semibold text-slate-700">
                        На чём основан текст <span className="text-xs font-normal text-slate-500">{generationSources.length} источника</span>
                      </summary>
                      <div className="space-y-3 px-4 pb-4 text-sm leading-6 text-slate-600">
                        {generationBrief.event ? <p><b className="text-slate-900">Инфоповод:</b> {generationBrief.event}</p> : null}
                        {generationBrief.main_idea ? <p><b className="text-slate-900">Главная мысль:</b> {generationBrief.main_idea}</p> : null}
                        {generationBrief.expected_action ? <p><b className="text-slate-900">Ожидаемое действие:</b> {generationBrief.expected_action}</p> : null}
                        <div className="flex flex-wrap gap-2">
                          {generationSources.map((source) => <span key={source.id || source.label} title={source.fact} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">{source.label || 'Источник'}</span>)}
                        </div>
                      </div>
                    </details>
                  ) : null}
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
                          <div className="mt-2 flex flex-wrap gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => { void downloadOriginalPhoto(selectedPhoto); }}
                              disabled={Boolean(busyAction)}
                              className="min-h-10 rounded-xl bg-white px-3 text-xs"
                            >
                              <Download className="mr-2 h-4 w-4" />
                              {busyAction === 'photo-download' ? 'Скачиваем...' : 'Скачать оригинал'}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => { void copyOriginalPhoto(selectedPhoto); }}
                              disabled={Boolean(busyAction)}
                              className="min-h-10 rounded-xl bg-white px-3 text-xs"
                            >
                              <Copy className="mr-2 h-4 w-4" />
                              {busyAction === 'photo-copy' ? 'Копируем...' : 'Скопировать фото'}
                            </Button>
                          </div>
                        </div>
                      </div>
                    ) : null}
                    {Array.isArray(mediaRecommendation?.alternatives) && mediaRecommendation.alternatives.length > 0 ? (
                      <div className="mt-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Альтернативы</div>
                        <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
                          {mediaRecommendation.alternatives.slice(0, 3).map((asset) => (
                            <button
                              key={asset.id}
                              type="button"
                              onClick={() => { void recordPhotoUsage(String(asset.id || '')); }}
                              disabled={busyAction === 'photo-usage'}
                              aria-label={`Выбрать фото: ${formatPhotoCategoryLabel(asset.category)}`}
                              className="w-28 shrink-0 rounded-2xl bg-slate-50 p-2 text-left transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 disabled:opacity-50"
                            >
                              {photoImageSrc(asset) ? (
                                <AuthenticatedImage src={photoImageSrc(asset)} alt="Альтернативное фото" className="h-20 w-full rounded-xl object-cover ring-1 ring-black/10" />
                              ) : (
                                <div className="flex h-20 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
                                  <ImageIcon className="h-5 w-5" />
                                </div>
                              )}
                              <div className="mt-1 truncate text-[11px] font-medium text-slate-600">{formatPhotoCategoryLabel(asset.category)}</div>
                              <div className="mt-1 text-[11px] font-semibold text-slate-900">Выбрать</div>
                            </button>
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
                      <div id={channelDetailsId} className="mt-3 space-y-3">
                        <div>
                          <div className="mb-2 text-xs font-medium text-slate-500">Куда должна выйти публикация</div>
                          <div className="flex flex-wrap gap-2">
                            {CHANNELS.map((channel) => {
                              const selected = Boolean(publicationChannels[channel.key]);
                              return (
                                <button
                                  key={channel.key}
                                  type="button"
                                  onClick={() => togglePublicationChannel(channel.key)}
                                  aria-pressed={selected}
                                  className={cn(
                                    'inline-flex min-h-10 items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold ring-1 transition-colors active:scale-[0.96] transition-transform',
                                    selected
                                      ? 'bg-slate-950 text-white ring-slate-950'
                                      : 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-100',
                                  )}
                                >
                                  <Check className={cn('h-3.5 w-3.5', selected ? 'opacity-100' : 'opacity-20')} />
                                  {channel.label}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                        {hasPosts ? (
                          <div className="space-y-2 border-t border-slate-100 pt-3">
                            {selectedPosts.map((post) => {
                              const statusLabel = getChannelStatusDisplay(post);
                              const readiness = getPostPlatformReadiness(post);
                              const normalizedPostStatus = String(post.status || '').toLowerCase();
                              const canEditPlatformText = !['queued', 'publishing', 'published'].includes(String(post.status || '').toLowerCase());
                              const canChooseManualPublish = ['approved', 'queued', 'failed', 'needs_supervised_publish'].includes(normalizedPostStatus);
                              const isEditing = editingPlatformPostId === post.id;
                              return (
                                <div key={post.id} className="rounded-2xl bg-slate-50 px-3 py-3 ring-1 ring-slate-100">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-sm font-semibold text-slate-900">{platformShortLabel(post)}</span>
                                    <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1', getStatusClassName(statusLabel))}>
                                      {statusLabel}
                                    </span>
                                  </div>
                                  <div className="mt-1 text-xs leading-5 text-slate-500">{getChannelNextAction(post)}</div>
                                  {post.platform_text ? (
                                    <div className="mt-3 whitespace-pre-line rounded-xl bg-white px-3 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-100 line-clamp-5">
                                      {post.platform_text}
                                    </div>
                                  ) : null}
                                  {String(post.status || '').toLowerCase() === 'published' ? (
                                    <div className="mt-3 rounded-xl bg-white p-3 ring-1 ring-slate-100">
                                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600 tabular-nums">
                                        <span>Просмотры {Number(post.views || post.reach || 0)}</span>
                                        <span>Реакции {Number(post.likes || 0) + Number(post.comments || 0) + Number(post.shares || 0)}</span>
                                        <span>Обращения {Number(post.inquiries || 0)}</span>
                                        <span>Заявки {Number(post.leads || 0)}</span>
                                      </div>
                                      <div className="mt-2 flex flex-wrap gap-2">
                                        <Button type="button" variant="outline" size="sm" onClick={() => { void recordPublishedResult(post, 'inquiry'); }} disabled={Boolean(busyAction)} className="min-h-10 rounded-xl px-3 text-xs active:scale-[0.96] transition-transform">
                                          + Обращение
                                        </Button>
                                        <Button type="button" variant="outline" size="sm" onClick={() => { void recordPublishedResult(post, 'lead'); }} disabled={Boolean(busyAction)} className="min-h-10 rounded-xl px-3 text-xs active:scale-[0.96] transition-transform">
                                          + Заявка
                                        </Button>
                                        {post.provider_post_url ? (
                                          <a href={post.provider_post_url} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center rounded-xl px-3 text-xs font-semibold text-sky-700 hover:bg-sky-50">
                                            Открыть пост
                                          </a>
                                        ) : null}
                                      </div>
                                    </div>
                                  ) : null}
                                  {['needs_manual_publish', 'needs_supervised_publish'].includes(String(post.status || '').toLowerCase()) ? (
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      <label className="flex w-full cursor-pointer items-start gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-700">
                                        <input
                                          type="checkbox"
                                          checked={Boolean(manualContentConfirmed[post.id])}
                                          onChange={(event) => setManualContentConfirmed((prev) => ({
                                            ...prev,
                                            [post.id]: event.target.checked,
                                          }))}
                                          disabled={Boolean(busyAction)}
                                          className="mt-0.5 h-4 w-4 shrink-0"
                                        />
                                        <span>Проверил на площадке: текст и выбранные фото отображаются правильно.</span>
                                      </label>
                                      {placementTargetUrl(post) ? (
                                        <a href={placementTargetUrl(post)} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center rounded-xl bg-white px-3 text-xs font-semibold text-sky-700 ring-1 ring-slate-200 hover:bg-sky-50">
                                          Открыть размещение
                                        </a>
                                      ) : null}
                                      <Button type="button" variant="outline" size="sm" onClick={() => { void navigator.clipboard?.writeText(post.platform_text || post.base_text || ''); setActionMessage('Текст скопирован.'); }} className="min-h-10 rounded-xl bg-white px-3 text-xs">
                                        Скопировать текст
                                      </Button>
                                      {selectedPhoto?.id ? (
                                        <>
                                          <Button type="button" variant="outline" size="sm" onClick={() => { void downloadOriginalPhoto(selectedPhoto); }} disabled={Boolean(busyAction)} className="min-h-10 rounded-xl bg-white px-3 text-xs">
                                            <Download className="mr-2 h-4 w-4" />
                                            Скачать фото
                                          </Button>
                                          <Button type="button" variant="outline" size="sm" onClick={() => { void copyOriginalPhoto(selectedPhoto); }} disabled={Boolean(busyAction)} className="min-h-10 rounded-xl bg-white px-3 text-xs">
                                            <Copy className="mr-2 h-4 w-4" />
                                            Скопировать фото
                                          </Button>
                                        </>
                                      ) : null}
                                      <Button type="button" variant="outline" size="sm" onClick={() => { void markPlacementPublished(post); }} disabled={Boolean(busyAction) || !manualContentConfirmed[post.id]} className="min-h-10 rounded-xl bg-white px-3 text-xs active:scale-[0.96] transition-transform">
                                        Отметить размещённым
                                      </Button>
                                    </div>
                                  ) : null}
                                  {canChooseManualPublish ? (
                                    <div className="mt-3">
                                      <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() => { void openManualPublish(post); }}
                                        disabled={Boolean(busyAction)}
                                        className="min-h-10 rounded-xl bg-white px-3 text-xs active:scale-[0.96] transition-transform"
                                      >
                                        {busyAction === `manual-publish-${post.id}` ? 'Готовим...' : 'Разместить вручную'}
                                      </Button>
                                    </div>
                                  ) : null}
                                  {isEditing ? (
                                    <div className="mt-3 space-y-2">
                                      <Textarea
                                        value={platformTextEdits[post.id] ?? post.platform_text ?? ''}
                                        onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setPlatformTextEdits((previous) => ({ ...previous, [post.id]: event.target.value }))}
                                        className="min-h-32 rounded-xl bg-white text-sm leading-6"
                                      />
                                      <div className="flex gap-2">
                                        <Button type="button" size="sm" onClick={() => { void savePlatformText(post); }} disabled={busyAction === `platform-text-${post.id}`} className="min-h-10 rounded-xl bg-slate-950 px-3 text-white active:scale-[0.96] transition-transform">
                                          {busyAction === `platform-text-${post.id}` ? 'Сохраняем...' : 'Сохранить текст'}
                                        </Button>
                                        <Button type="button" size="sm" variant="outline" onClick={() => setEditingPlatformPostId('')} className="min-h-10 rounded-xl bg-white px-3">
                                          Отмена
                                        </Button>
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      {canEditPlatformText ? (
                                        <Button
                                          type="button"
                                          variant="outline"
                                          size="sm"
                                          onClick={() => {
                                            setPlatformTextEdits((previous) => ({ ...previous, [post.id]: previous[post.id] ?? post.platform_text ?? '' }));
                                            setEditingPlatformPostId(post.id);
                                          }}
                                          className="min-h-10 rounded-xl bg-white px-3 text-xs"
                                        >
                                          Изменить текст
                                        </Button>
                                      ) : null}
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
                                          className="min-h-10 rounded-xl bg-white px-3 text-xs"
                                        >
                                          {readiness.action_label}
                                        </Button>
                                      ) : null}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                            {selectedPosts.some((post) => (
                              !['queued', 'publishing', 'published'].includes(String(post.status || '').toLowerCase())
                              && !post.metadata_json?.manually_edited
                            )) ? (
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => { void prepareSelectedItem(true); }}
                                disabled={Boolean(busyAction)}
                                className="min-h-10 w-full rounded-xl bg-white px-3 text-xs"
                              >
                                {busyAction === 'prepare' ? 'Обновляем версии...' : 'Переписать автоматические версии'}
                              </Button>
                            ) : null}
                          </div>
                        ) : (
                          <div className="border-t border-slate-100 pt-3 text-xs leading-5 text-slate-500">
                            LocalOS создаст только выбранные варианты. Наружу ничего не отправится.
                          </div>
                        )}
                      </div>
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
                  {needsPlatformPreparation ? (
                    <Button type="button" onClick={() => { void prepareSelectedItem(); }} disabled={Boolean(busyAction)} className="min-h-12 rounded-2xl bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-500 active:scale-[0.96] transition-transform">
                      {busyAction === 'prepare'
                        ? 'Подготавливаем версии...'
                        : hasPosts
                          ? 'Обновить версии для каналов'
                          : 'Подготовить версии для каналов'}
                    </Button>
                  ) : hasUnsavedItemChanges ? (
                    <Button type="button" variant="outline" onClick={saveSelectedItem} disabled={Boolean(busyAction)} className="min-h-11 rounded-2xl active:scale-[0.96] transition-transform">
                      {busyAction === 'save' ? 'Сохраняем...' : 'Сохранить изменения'}
                    </Button>
                  ) : null}
                  {canApproveSelectedItem && !needsContext ? (
                    <Button
                      type="button"
                      onClick={approveSelectedItem}
                      disabled={Boolean(busyAction)}
                      className="min-h-12 rounded-2xl bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-500 active:scale-[0.96] transition-transform"
                    >
                      {approveButtonLabel}
                    </Button>
                  ) : null}
                  {canQueueSelectedItem || scheduleAlreadyHandled ? <TooltipProvider delayDuration={150}>
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
                  </TooltipProvider> : null}
                </div>
                {queueNeedsAttention ? (
                  <div className="rounded-2xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                    <div className="font-semibold">Отправка пока не запланирована</div>
                    <div className="mt-1">{queueHelpText}</div>
                  </div>
                ) : null}
                {needsContext ? (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs leading-5 text-amber-950">
                    <div className="font-semibold">Нужно добавить детали</div>
                    <div className="mt-1">
                      {generation.message || 'Ответьте на несколько вопросов, чтобы LocalOS подготовил конкретный текст.'}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        publicationDetailsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        window.setTimeout(() => {
                          const firstInput = publicationDetailsRef.current?.querySelector<HTMLInputElement>('input');
                          firstInput?.focus();
                        }, 350);
                      }}
                      className="mt-2 inline-flex min-h-9 items-center font-semibold text-amber-950 underline decoration-amber-400 underline-offset-4 hover:decoration-amber-700 focus-visible:rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                    >
                      {generation.action?.label || 'Добавить детали'}
                    </button>
                  </div>
                ) : error ? (
                  <div className="rounded-2xl border border-red-100 bg-red-50 px-3 py-2 text-xs leading-5 text-red-800">
                    <div className="font-semibold">Что нужно сделать</div>
                    <div className="mt-1">{error}</div>
                    {hasPosts ? (
                      <button
                        type="button"
                        onClick={() => setChannelDetailsOpen(true)}
                        className="mt-2 inline-flex min-h-9 items-center font-semibold underline decoration-red-300 underline-offset-4 hover:decoration-red-700 focus-visible:rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                      >
                        Показать каналы
                      </button>
                    ) : null}
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

  const contentSetupSteps: { key: ContentSetupStep; label: string }[] = [
    { key: 'business', label: 'О бизнесе' },
    { key: 'audience', label: 'О клиентах' },
    { key: 'voice', label: 'Как писать' },
  ];
  const contentSetupStepIndex = contentSetupSteps.findIndex((step) => step.key === contentSetupStep);

  const renderVoiceDialog = () => (
    <Dialog open={voiceOpen} onOpenChange={setVoiceOpen}>
      <DialogContent className="max-h-[88vh] overflow-y-auto rounded-[28px] sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="text-balance text-2xl">Настроить контент</DialogTitle>
          <DialogDescription className="text-pretty">
            Три коротких шага, чтобы тексты были похожи на вас и понятны вашим клиентам.
          </DialogDescription>
        </DialogHeader>
        {voiceLoading && !voiceProfile ? (
          <div className="flex min-h-32 items-center justify-center text-sm text-slate-500"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Загружаем настройки...</div>
        ) : (
          <div className="space-y-5 py-2">
            <div className="grid grid-cols-3 gap-2" aria-label="Шаги настройки контента">
              {contentSetupSteps.map((step, index) => (
                <button
                  key={step.key}
                  type="button"
                  onClick={() => setContentSetupStep(step.key)}
                  className={cn(
                    'min-h-12 rounded-2xl px-2 py-2 text-xs font-semibold transition-colors',
                    contentSetupStep === step.key ? 'bg-slate-950 text-white' : index < contentSetupStepIndex ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
                  )}
                >
                  <span className="block text-[11px] opacity-70">Шаг {index + 1}</span>
                  {step.label}
                </button>
              ))}
            </div>

            {contentSetupStep === 'business' ? (
              <div>
                <div className="text-sm font-semibold text-slate-900">Что важно знать о бизнесе</div>
                <p className="mt-1 text-sm leading-6 text-slate-600">Коротко: чем вы занимаетесь, чем отличаетесь и что нельзя искажать в текстах.</p>
                <Textarea value={businessDescription} onChange={(event) => setBusinessDescription(event.target.value)} placeholder="Например: культурный центр для жителей района; главное — реальная афиша и конкретные события" className="mt-3 min-h-36 rounded-2xl" />
              </div>
            ) : null}

            {contentSetupStep === 'audience' ? (
              <div>
                <div className="text-sm font-semibold text-slate-900">Кто ваши клиенты</div>
                <p className="mt-1 text-sm leading-6 text-slate-600">Опишите их ситуации, вопросы и причины выбрать вас. Не нужны сложные сегменты.</p>
                <Textarea value={audienceDescription} onChange={(event) => setAudienceDescription(event.target.value)} placeholder="Например: жители района, которые ищут интересные события рядом с домом и хотят заранее знать дату и формат" className="mt-3 min-h-36 rounded-2xl" />
              </div>
            ) : null}

            {contentSetupStep === 'voice' ? (
              <div className="space-y-5">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Как должны звучать тексты</div>
                  <Textarea value={voiceSummary} onChange={(event) => setVoiceSummary(event.target.value)} placeholder="Например: конкретно, тепло, без рекламных вопросов" className="mt-2 min-h-28 rounded-2xl" />
                </div>
                <details className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <summary className="cursor-pointer text-sm font-semibold text-slate-900">Примеры понравившихся постов · {(voiceProfile?.examples || []).length}</summary>
                  <div className="mt-4">
                    <Textarea value={voiceExampleInput} onChange={(event) => setVoiceExampleInput(event.target.value)} placeholder="Вставьте полный текст публикации" className="min-h-28 rounded-2xl bg-white" />
                    <Button type="button" variant="outline" onClick={() => { void addVoiceExample(); }} disabled={voiceLoading || voiceExampleInput.trim().length < 20} className="mt-2 min-h-11 rounded-2xl bg-white active:scale-[0.96] transition-transform"><Plus className="mr-2 h-4 w-4" />Добавить пример</Button>
                    {(voiceProfile?.examples || []).length > 0 ? (
                      <div className="mt-3 max-h-48 space-y-2 overflow-y-auto">
                        {(voiceProfile?.examples || []).map((example) => (
                          <div key={example.id} className="flex items-start gap-3 rounded-2xl bg-white p-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]">
                            <p className="line-clamp-3 min-w-0 flex-1 text-pretty text-sm leading-6 text-slate-600">{example.text}</p>
                            <button type="button" onClick={() => { void deleteVoiceExample(example.id); }} className="grid min-h-10 min-w-10 place-items-center rounded-xl text-slate-400 transition-colors hover:bg-slate-50 hover:text-red-600" aria-label="Удалить пример"><Trash2 className="h-4 w-4" /></button>
                          </div>
                        ))}
                      </div>
                    ) : <p className="mt-3 text-xs leading-5 text-slate-600">Можно начать без примеров и добавить их позже.</p>}
                  </div>
                </details>
                {voiceProfile?.learning_suggestion?.text ? <div className="rounded-2xl bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-900">{voiceProfile.learning_suggestion.text}</div> : null}
              </div>
            ) : null}
          </div>
        )}
        <DialogFooter>
          {contentSetupStepIndex > 0 ? <Button type="button" variant="outline" onClick={() => setContentSetupStep(contentSetupSteps[contentSetupStepIndex - 1].key)} className="min-h-11 rounded-2xl">Назад</Button> : <Button type="button" variant="outline" onClick={() => setVoiceOpen(false)} className="min-h-11 rounded-2xl">Закрыть</Button>}
          {contentSetupStepIndex < contentSetupSteps.length - 1 ? (
            <Button type="button" onClick={() => setContentSetupStep(contentSetupSteps[contentSetupStepIndex + 1].key)} className="min-h-11 rounded-2xl bg-slate-950 text-white active:scale-[0.96] transition-transform">Дальше</Button>
          ) : (
            <Button type="button" onClick={() => { void saveVoiceProfile(); }} disabled={voiceLoading || !voiceSummary.trim()} className="min-h-11 rounded-2xl bg-slate-950 text-white active:scale-[0.96] transition-transform">Сохранить</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

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
      {renderDeletePlanDialog()}
      {renderVoiceDialog()}
      {renderDrawer()}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{contentCopy.eyebrow}</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">{contentCopy.title}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {localizeDemoBusinessName(currentBusiness?.name || contentCopy.fallbackSubtitle, language)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => { void openVoiceSettings(); }} className="min-h-12 rounded-2xl bg-white px-4 active:scale-[0.96] transition-transform">
            <Star className="mr-2 h-4 w-4" />{contentControls.configureContent}
          </Button>
          <Button type="button" onClick={() => { setCreateStep('setup'); setCreateOpen(true); }} className="min-h-12 rounded-2xl bg-slate-950 px-5 text-white hover:bg-slate-800 active:scale-[0.96] transition-transform">
            <Plus className="mr-2 h-4 w-4" />{contentCopy.createPlan}
          </Button>
        </div>
      </div>

      <div className="inline-flex rounded-2xl bg-slate-100 p-1">
        {[
          ['calendar', contentCopy.calendar, CalendarDays],
          ['media', contentCopy.media, ImageIcon],
          ['audience', contentCopy.audience, MessageCircleQuestion],
        ].map(([key, label, Icon]) => (
          <button
            key={String(key)}
            type="button"
            onClick={() => setSection(key === 'media' || key === 'audience' ? key : 'calendar')}
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

      {section === 'audience' ? <AudienceInsights businessId={currentBusinessId} /> : null}

      {section === 'calendar' && generating ? renderGenerating() : null}

      {section === 'calendar' && !generating && !loading && items.length === 0 ? renderEmptyState() : null}

      {section === 'calendar' && !generating && (loading || items.length > 0) ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_340px]" data-tour-target="content-calendar">
          <main className="space-y-5">
            <div className="rounded-[32px] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-2xl">
                  <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">{calendarCopy.aiResult}</div>
                  <h2 className="mt-3 text-4xl font-semibold tracking-tight">
                    {filledDays > 0 ? calendarCopy.contentReady : calendarCopy.preparingCalendar}
                  </h2>
                  <div className="mt-4 max-w-xl text-lg text-slate-300">
                    {fillContentCalendarTemplate(calendarCopy.filledDays, { filled: filledDays, total: totalDays })}
                  </div>
                  <Progress value={Math.min(100, Math.round((filledDays / Math.max(totalDays, 1)) * 100))} className="mt-5 h-3 bg-white/10" />
                </div>
                <div className="rounded-3xl bg-white/10 px-5 py-4">
                  <div className="text-sm text-slate-400">{calendarCopy.nextPublication}</div>
                  <div className="mt-1 text-2xl font-semibold">{nextItem ? formatDate(nextItem.scheduled_for, language) : calendarCopy.noDate}</div>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
              <div className="space-y-4">
                <div>
                  <div className="text-sm font-semibold text-slate-950">{calendarCopy.whatNow}</div>
                  <div className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
                    {calendarCopy.whatNowHint}
                  </div>
                </div>
                <div className="grid w-full min-w-0 gap-2 md:grid-cols-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={openNearestReview}
                    disabled={!items.length || Boolean(busyAction)}
                    className="h-12 min-w-0 justify-center gap-2 rounded-2xl border-slate-200 bg-white px-4 text-slate-800 transition-transform hover:bg-slate-50 active:scale-[0.96]"
                  >
                    <Eye className="h-4 w-4 shrink-0" />
                    <span className="truncate">{calendarCopy.reviewNearest}</span>
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
                      {busyAction === 'bulk-approve' ? calendarCopy.approving : `${calendarCopy.approveReady} · ${reviewReadyPosts.length}`}
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
                      {busyAction === 'bulk-queue' ? calendarCopy.scheduling : `${calendarCopy.schedule} · ${approvedPosts.length}`}
                    </span>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setDeletePlanOpen(true)}
                    disabled={!currentPlan?.id || Boolean(busyAction)}
                    className="h-12 min-w-0 justify-center gap-2 rounded-2xl border-red-100 bg-white px-4 text-red-700 transition-transform hover:bg-red-50 hover:text-red-800 active:scale-[0.96] disabled:opacity-45"
                  >
                    <Trash2 className="h-4 w-4 shrink-0" />
                    <span className="truncate">{calendarCopy.deletePlan}</span>
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3 rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
              <div className="inline-flex rounded-2xl bg-slate-100 p-1">
                {[
                  ['month', calendarCopy.month, CalendarDays],
                  ['week', calendarCopy.week, Clock3],
                  ['list', calendarCopy.list, FileText],
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
                {needsReviewCount > 0 ? `${calendarCopy.needsReview}: ${needsReviewCount}` : calendarCopy.underControl}
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

export function ContentPage() {
  const { demoMode } = useOutletContext<DashboardOutletContext>();
  return demoMode ? <DemoContentPlanPage /> : <ContentWorkspace />;
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
      const token = newAuth.getToken() || '';
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
