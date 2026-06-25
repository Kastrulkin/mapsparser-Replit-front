import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import {
  AlertCircle,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  Eye,
  FileText,
  Lightbulb,
  Loader2,
  Plus,
  Sparkles,
  Star,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Textarea } from '@/components/ui/textarea';
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

type CalendarView = 'month' | 'week' | 'list';
type ModalStep = 'setup' | 'preview';

type CreatePlanDraft = {
  goal: string;
  frequency: string;
  periodDays: number;
  contentTypes: Record<string, boolean>;
  channels: Record<string, boolean>;
};

const CONTENT_VIEW_STORAGE_KEY = 'localos_content_view_v1';

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

const formatDate = (value?: string) => {
  if (!value) return 'Дата не выбрана';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
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

const getItemDateKey = (item: PlanItem) => String(item.scheduled_for || '').slice(0, 10);

const itemHasText = (item: PlanItem) => String(item.draft_text || '').trim().length > 0;

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

const getItemStatusLabel = (item: PlanItem, posts: SocialPost[]) => {
  if (posts.some((post) => String(post.status || '') === 'failed')) return 'Не удалось';
  if (posts.some((post) => String(post.status || '') === 'needs_supervised_publish' || String(post.status || '') === 'needs_manual_publish')) {
    return 'Нужно разместить';
  }
  if (posts.some((post) => String(post.status || '') === 'needs_review')) return 'Нужно проверить';
  if (posts.some((post) => String(post.status || '') === 'queued')) return 'Запланировано';
  if (posts.length > 0 && posts.every((post) => String(post.status || '') === 'published')) return 'Опубликовано';
  if (itemHasText(item)) return 'Нужно проверить';
  return 'Черновик';
};

const getStatusClassName = (label: string) => {
  if (label === 'Опубликовано') return 'bg-emerald-50 text-emerald-700 ring-emerald-100';
  if (label === 'Запланировано') return 'bg-blue-50 text-blue-700 ring-blue-100';
  if (label === 'Утверждено') return 'bg-violet-50 text-violet-700 ring-violet-100';
  if (label === 'Нужно проверить') return 'bg-amber-50 text-amber-800 ring-amber-100';
  if (label === 'Нужно разместить') return 'bg-orange-50 text-orange-800 ring-orange-100';
  if (label === 'Не удалось') return 'bg-red-50 text-red-700 ring-red-100';
  return 'bg-slate-100 text-slate-600 ring-slate-200';
};

const getSelectedCount = (values: Record<string, boolean>) => Object.values(values).filter(Boolean).length;

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
  if (!label) return 'Канал';
  if (label === 'google_business') return 'Google';
  if (label === 'yandex_maps') return 'Яндекс';
  if (label === 'two_gis') return '2ГИС';
  return label;
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
  const [view, setView] = useState<CalendarView>(() => {
    if (typeof window === 'undefined') return 'month';
    const saved = window.localStorage.getItem(CONTENT_VIEW_STORAGE_KEY);
    return saved === 'week' || saved === 'list' || saved === 'month' ? saved : 'month';
  });
  const [selectedItemId, setSelectedItemId] = useState('');
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [themeEdits, setThemeEdits] = useState<Record<string, string>>({});
  const [dateEdits, setDateEdits] = useState<Record<string, string>>({});
  const [createOpen, setCreateOpen] = useState(false);
  const [createStep, setCreateStep] = useState<ModalStep>('setup');
  const [createDraft, setCreateDraft] = useState<CreatePlanDraft>(DEFAULT_CREATE_DRAFT);
  const [generating, setGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationCards, setGenerationCards] = useState(0);

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
    const filled = new Set(items.filter((item) => itemHasText(item)).map(getItemDateKey).filter(Boolean));
    return filled.size;
  }, [items]);
  const totalDays = Number(currentPlan?.period_days || 30);
  const needsReviewCount = Number(socialSummary?.needs_review || 0) || items.filter((item) => itemHasText(item) && getItemStatusLabel(item, postsByItem[item.id] || []) === 'Нужно проверить').length;
  const nextItem = useMemo(() => {
    const today = toIsoDate(new Date());
    return [...items]
      .filter((item) => getItemDateKey(item) >= today)
      .sort((left, right) => getItemDateKey(left).localeCompare(getItemDateKey(right)))[0] || null;
  }, [items]);
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
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(CONTENT_VIEW_STORAGE_KEY, view);
  }, [view]);

  useEffect(() => {
    if (!generating) return;
    const interval = window.setInterval(() => {
      setGenerationProgress((value) => Math.min(value + 7, 92));
      setGenerationCards((value) => Math.min(value + 2, 28));
    }, 420);
    return () => window.clearInterval(interval);
  }, [generating]);

  const openItem = (item: PlanItem) => {
    setSelectedItemId(item.id);
    setDraftEdits((prev) => ({ ...prev, [item.id]: String(item.draft_text || '') }));
    setThemeEdits((prev) => ({ ...prev, [item.id]: String(item.theme || item.goal || '') }));
    setDateEdits((prev) => ({ ...prev, [item.id]: getItemDateKey(item) }));
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
    try {
      const postIds = (postsByItem[selectedItem.id] || []).map((post) => post.id).filter(Boolean);
      if (postIds.length === 0) {
        setError('Сначала подготовьте и утвердите каналы.');
        return;
      }
      await newAuth.makeRequest('/social-posts/bulk-queue', {
        method: 'POST',
        body: JSON.stringify({ post_ids: postIds }),
      });
      await loadSocialPosts(currentPlan.id);
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : 'Не удалось поставить в расписание');
    } finally {
      setBusyAction('');
    }
  };

  const createPlan = async () => {
    if (!currentBusinessId) return;
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
      setGenerationProgress(100);
      setGenerationCards(Math.max(24, createDraft.periodDays));
      const plan = response.plan || null;
      setCurrentPlan(plan);
      if (plan?.id) {
        await loadSocialPosts(plan.id);
      }
      const plansResponse = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(currentBusinessId)}`, { method: 'GET' });
      setPlans(Array.isArray(plansResponse.plans) ? plansResponse.plans : []);
      window.setTimeout(() => {
        setGenerating(false);
      }, 750);
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
    const label = getItemStatusLabel(item, posts);
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
        <span className={cn('mt-1.5 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1', getStatusClassName(label))}>
          {label}
        </span>
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
          const label = getItemStatusLabel(item, posts);
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
              <span className={cn('inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1', getStatusClassName(label))}>
                {label}
              </span>
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
          <Insight icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} text={`Создано ${items.filter(itemHasText).length} публикаций`} />
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

  const renderDrawer = () => {
    const item = selectedItem;
    const hasPosts = selectedPosts.length > 0;
    const failedPost = selectedPosts.find((post) => String(post.status || '') === 'failed');
    return (
      <Sheet open={Boolean(item)} onOpenChange={(open) => { if (!open) setSelectedItemId(''); }}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-4xl">
          {item ? (
            <div className="grid min-h-full gap-6 lg:grid-cols-[1fr_300px]">
              <div>
                <SheetHeader>
                  <SheetTitle className="text-2xl">Публикация</SheetTitle>
                  <SheetDescription>Текст, preview и подтверждение перед выходом наружу.</SheetDescription>
                </SheetHeader>
                <div className="mt-6 space-y-4">
                  <Input
                    value={themeEdits[item.id] ?? item.theme ?? item.goal ?? ''}
                    onChange={(event: React.ChangeEvent<HTMLInputElement>) => setThemeEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                    className="h-12 rounded-2xl border-slate-200 text-base font-semibold"
                  />
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
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Каналы</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(hasPosts ? selectedPosts : CHANNELS.slice(0, 5)).map((itemOrPost) => {
                        const label = 'platform' in itemOrPost ? platformShortLabel(itemOrPost) : itemOrPost.label;
                        return (
                          <span key={label} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                            {label}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                  <div className="mt-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Статус</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(hasPosts ? selectedPosts : [{ id: 'draft', status: itemHasText(item) ? 'needs_review' : 'draft' }]).map((post) => (
                        <span key={post.id} className={cn('rounded-full px-3 py-1 text-xs font-semibold ring-1', getStatusClassName(getPostStatusLabel(post.status)))}>
                          {getPostStatusLabel(post.status)}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="grid gap-2">
                  <Button type="button" variant="outline" onClick={saveSelectedItem} disabled={Boolean(busyAction)} className="rounded-2xl">
                    {busyAction === 'save' ? 'Сохраняем...' : 'Сохранить'}
                  </Button>
                  <Button type="button" variant="outline" onClick={prepareSelectedItem} disabled={Boolean(busyAction)} className="rounded-2xl">
                    {busyAction === 'prepare' ? 'Готовим...' : 'Подготовить каналы'}
                  </Button>
                  <Button type="button" onClick={approveSelectedItem} disabled={Boolean(busyAction)} className="rounded-2xl bg-slate-950 text-white hover:bg-slate-800">
                    {busyAction === 'approve' ? 'Утверждаем...' : 'Утвердить'}
                  </Button>
                  <Button type="button" onClick={queueSelectedItem} disabled={Boolean(busyAction)} className="rounded-2xl bg-emerald-600 text-white hover:bg-emerald-700">
                    {busyAction === 'queue' ? 'Ставим...' : 'Запланировать'}
                  </Button>
                </div>
                <p className="text-xs leading-5 text-slate-500">
                  Наружу ничего не отправится без проверки и расписания. Яндекс и 2ГИС остаются контролируемым размещением.
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

      {error ? (
        <div className="flex items-center justify-between gap-3 rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-800">
          <span>{error}</span>
          <Button type="button" variant="outline" onClick={() => { void loadContent(); }} className="border-red-200 bg-white text-red-800 hover:bg-red-100">
            Повторить
          </Button>
        </div>
      ) : null}

      {generating ? renderGenerating() : null}

      {!generating && !loading && items.length === 0 ? renderEmptyState() : null}

      {!generating && (loading || items.length > 0) ? (
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
