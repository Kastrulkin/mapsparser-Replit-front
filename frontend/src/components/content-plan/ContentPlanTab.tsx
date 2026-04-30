import React, { useEffect, useMemo, useState } from 'react';
import { CalendarDays, Lock, MapPinned, Sparkles, Wand2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLanguage } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';

type ScopeOption = {
  scope_type: string;
  scope_target_id: string;
  label: string;
  city?: string;
  address?: string;
  is_parent?: boolean;
  is_current?: boolean;
};

type ContextPayload = {
  business?: {
    id?: string;
    name?: string;
    city?: string;
  };
  scope?: {
    scope_type?: string;
    scope_target_id?: string;
    scope_options?: ScopeOption[];
    selected_scope_label?: string;
    selected_scope_description?: string;
    network?: {
      is_network?: boolean;
      locations_count?: number;
      has_parent_scope?: boolean;
    };
  };
  subscription?: {
    tier?: string;
    allowed_horizons?: number[];
    automation_access?: boolean;
    reason?: string | null;
  };
  services?: Array<{ id: string; name: string }>;
  seo_keywords?: Array<{ keyword: string; views?: number }>;
  sales_signals?: Array<{ title: string; amount?: number }>;
  recent_news?: Array<{ id: string; text: string }>;
  audit_signals?: Array<{ title?: string; problem?: string }>;
  readiness?: {
    map_links_count?: number;
    has_map_links?: boolean;
    has_services?: boolean;
    has_seo_keywords?: boolean;
    has_sales_signals?: boolean;
    has_audit_signals?: boolean;
    missing_inputs?: string[];
    is_grounded_for_search?: boolean;
  };
};

type PlanItem = {
  id: string;
  scheduled_for: string;
  theme: string;
  goal: string;
  source_kind: string;
  source_ref: string;
  seo_keyword: string;
  draft_text: string;
  status: string;
  usernews_id: string;
  content_type: string;
  business_id?: string;
  location_scope?: string;
  location_label?: string;
  location_city?: string;
  location_address?: string;
};

type PlanPayload = {
  id: string;
  title: string;
  period_days: number;
  scope_type: string;
  scope_target_id: string;
  scope_target_label?: string;
  scope_target_city?: string;
  scope_target_address?: string;
  plan_status?: string;
  items: PlanItem[];
  created_at?: string;
};

const PERIOD_OPTIONS = [30, 60, 90];

const DENSITY_OPTIONS = [
  { value: 'light', labelRu: 'Спокойно', labelEn: 'Light' },
  { value: 'standard', labelRu: 'Стандартно', labelEn: 'Standard' },
  { value: 'active', labelRu: 'Активно', labelEn: 'Active' },
];

type ContentPlanTabProps = {
  businessId?: string;
};

type ContentMixKey = 'services' | 'seo' | 'sales' | 'audit' | 'seasonal';

type ContentMixState = Record<ContentMixKey, boolean>;
type ItemFilterKey = 'all' | 'needs_draft' | 'has_draft' | 'news_created';
type SignalFilterKey = 'all' | ContentMixKey;

const CONTENT_MIX_OPTIONS: Array<{ key: ContentMixKey; labelRu: string; labelEn: string }> = [
  { key: 'services', labelRu: 'Услуги', labelEn: 'Services' },
  { key: 'seo', labelRu: 'SEO', labelEn: 'SEO' },
  { key: 'sales', labelRu: 'Продажи', labelEn: 'Sales' },
  { key: 'audit', labelRu: 'Аудит', labelEn: 'Audit' },
  { key: 'seasonal', labelRu: 'Сезонность', labelEn: 'Seasonal' },
];
const ITEM_FILTER_OPTIONS: ItemFilterKey[] = ['all', 'needs_draft', 'has_draft', 'news_created'];
const SIGNAL_FILTER_OPTIONS: SignalFilterKey[] = ['all', 'seo', 'services', 'sales', 'audit', 'seasonal'];

export default function ContentPlanTab({ businessId }: ContentPlanTabProps) {
  const navigate = useNavigate();
  const { language } = useLanguage();
  const isRu = language === 'ru';
  const [context, setContext] = useState<ContextPayload | null>(null);
  const [plans, setPlans] = useState<PlanPayload[]>([]);
  const [currentPlan, setCurrentPlan] = useState<PlanPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [selectedScopeKey, setSelectedScopeKey] = useState('');
  const [selectedPeriod, setSelectedPeriod] = useState('30');
  const [selectedDensity, setSelectedDensity] = useState('standard');
  const [contentMix, setContentMix] = useState<ContentMixState>({
    services: true,
    seo: true,
    sales: true,
    audit: true,
    seasonal: true,
  });
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [themeEdits, setThemeEdits] = useState<Record<string, string>>({});
  const [dateEdits, setDateEdits] = useState<Record<string, string>>({});
  const [busyItemId, setBusyItemId] = useState('');
  const [bulkBusyAction, setBulkBusyAction] = useState('');
  const [selectedItemFilter, setSelectedItemFilter] = useState<ItemFilterKey>('all');
  const [selectedSignalFilter, setSelectedSignalFilter] = useState<SignalFilterKey>('all');
  const [selectedPlanTargetKey, setSelectedPlanTargetKey] = useState('all');
  const [selectedItemLocationKey, setSelectedItemLocationKey] = useState('all');
  const [selectedWeekKey, setSelectedWeekKey] = useState('all');

  const allowedHorizons = context?.subscription?.allowed_horizons || [30];
  const scopeOptions = context?.scope?.scope_options || [];
  const isNetworkContext = Boolean(context?.scope?.network?.is_network);
  const selectedScopeDescription = context?.scope?.selected_scope_description || '';
  const selectedScopeLabel = context?.scope?.selected_scope_label || '';
  const readiness = context?.readiness || null;
  const missingInputs = Array.isArray(readiness?.missing_inputs) ? readiness?.missing_inputs : [];

  const selectedScopeOption = useMemo(() => (
    scopeOptions.find((item) => `${item.scope_type}:${item.scope_target_id}` === selectedScopeKey) || null
  ), [scopeOptions, selectedScopeKey]);
  const filteredItems = useMemo(() => {
    const items = currentPlan?.items || [];
    return items.filter((item) => (
      _matchesItemFilter(item, selectedItemFilter)
      && _matchesSignalFilter(item, selectedSignalFilter)
      && _matchesItemLocationFilter(item, selectedItemLocationKey)
    ));
  }, [currentPlan?.items, selectedItemFilter, selectedSignalFilter, selectedItemLocationKey]);
  const availableWeeks = useMemo(() => {
    const seen = new Set<string>();
    const options: Array<{ key: string; label: string }> = [
      { key: 'all', label: isRu ? 'Все недели' : 'All weeks' },
    ];
    for (const item of filteredItems) {
      const key = _weekBucketKey(item.scheduled_for);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      options.push({
        key,
        label: _weekBucketLabel(key, isRu),
      });
    }
    return options;
  }, [filteredItems, isRu]);
  const weekSummary = useMemo(() => {
    const buckets = new Map<string, { key: string; label: string; total: number; needsDraft: number; readyToPublish: number }>();
    for (const item of filteredItems) {
      const key = _weekBucketKey(item.scheduled_for);
      if (!key) continue;
      const existing = buckets.get(key) || {
        key,
        label: _weekBucketLabel(key, isRu),
        total: 0,
        needsDraft: 0,
        readyToPublish: 0,
      };
      existing.total += 1;
      const hasDraft = Boolean(String(item.draft_text || '').trim());
      const hasNews = Boolean(String(item.usernews_id || '').trim());
      if (!hasDraft) {
        existing.needsDraft += 1;
      }
      if (hasDraft && !hasNews) {
        existing.readyToPublish += 1;
      }
      buckets.set(key, existing);
    }
    return Array.from(buckets.values()).sort((left, right) => left.key.localeCompare(right.key));
  }, [filteredItems, isRu]);
  const visibleItems = useMemo(() => (
    filteredItems.filter((item) => selectedWeekKey === 'all' || _weekBucketKey(item.scheduled_for) === selectedWeekKey)
  ), [filteredItems, selectedWeekKey]);
  const itemFilterCounts = useMemo(() => {
    const items = currentPlan?.items || [];
    return ITEM_FILTER_OPTIONS.reduce<Record<ItemFilterKey, number>>((acc, filterKey) => {
      acc[filterKey] = items.filter((item) => _matchesItemFilter(item, filterKey)).length;
      return acc;
    }, {
      all: 0,
      needs_draft: 0,
      has_draft: 0,
      news_created: 0,
    });
  }, [currentPlan?.items]);
  const signalFilterCounts = useMemo(() => {
    const items = currentPlan?.items || [];
    return SIGNAL_FILTER_OPTIONS.reduce<Record<SignalFilterKey, number>>((acc, filterKey) => {
      acc[filterKey] = items.filter((item) => _matchesSignalFilter(item, filterKey)).length;
      return acc;
    }, {
      all: 0,
      seo: 0,
      services: 0,
      sales: 0,
      audit: 0,
      seasonal: 0,
    });
  }, [currentPlan?.items]);
  const availableItemLocations = useMemo(() => {
    const seen = new Set<string>();
    const options: Array<{ key: string; label: string }> = [
      { key: 'all', label: isRu ? 'Все точки' : 'All locations' },
    ];
    for (const item of currentPlan?.items || []) {
      const key = String(item.location_scope || item.business_id || '').trim();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      options.push({
        key,
        label: _itemLocationLabel(item, isRu),
      });
    }
    return options;
  }, [currentPlan?.items, isRu]);
  const itemLocationSummary = useMemo(() => {
    const counts = new Map<string, { label: string; count: number }>();
    for (const item of currentPlan?.items || []) {
      const key = String(item.location_scope || item.business_id || '').trim();
      if (!key) continue;
      const existing = counts.get(key);
      if (existing) {
        existing.count += 1;
        continue;
      }
      counts.set(key, {
        label: _itemLocationLabel(item, isRu),
        count: 1,
      });
    }
    return Array.from(counts.values()).sort((left, right) => right.count - left.count);
  }, [currentPlan?.items, isRu]);
  const availablePlanTargets = useMemo(() => {
    const seen = new Set<string>();
    const options: Array<{ key: string; label: string }> = [
      { key: 'all', label: isRu ? 'Все планы' : 'All plans' },
    ];
    for (const plan of plans) {
      const key = `${plan.scope_type}:${plan.scope_target_id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      options.push({
        key,
        label: _planTargetLabel(plan, isRu),
      });
    }
    return options;
  }, [plans, isRu]);
  const visiblePlans = useMemo(() => {
    if (selectedPlanTargetKey === 'all') return plans;
    return plans.filter((plan) => `${plan.scope_type}:${plan.scope_target_id}` === selectedPlanTargetKey);
  }, [plans, selectedPlanTargetKey]);
  const bulkDraftCandidates = useMemo(() => (
    visibleItems.filter((item) => !String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim())
  ), [visibleItems]);
  const bulkNewsCandidates = useMemo(() => (
    visibleItems.filter((item) => String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim())
  ), [visibleItems]);

  const loadPlans = async () => {
    if (!businessId) return;
    const response = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(businessId)}`, {
      method: 'GET',
    });
    const nextPlans = Array.isArray(response.plans) ? response.plans : [];
    setPlans(nextPlans);
    if (nextPlans.length > 0) {
      const latestPlan = nextPlans[0];
      const fullPlanResponse = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(latestPlan.id)}`, {
        method: 'GET',
      });
      setCurrentPlan(fullPlanResponse.plan || null);
    } else {
      setCurrentPlan(null);
    }
  };

  const loadContext = async (scopeKey?: string) => {
    if (!businessId) return;
    setLoading(true);
    setError('');
    try {
      const scopeValue = scopeKey || selectedScopeKey;
      let scopeType = '';
      let scopeTargetId = '';
      if (scopeValue) {
        const separatorIndex = scopeValue.indexOf(':');
        if (separatorIndex >= 0) {
          scopeType = scopeValue.slice(0, separatorIndex);
          scopeTargetId = scopeValue.slice(separatorIndex + 1);
        }
      }
      const query = new URLSearchParams({ business_id: businessId });
      if (scopeType) query.set('scope_type', scopeType);
      if (scopeTargetId) query.set('scope_target_id', scopeTargetId);
      const response = await newAuth.makeRequest(`/content-plans/context?${query.toString()}`, { method: 'GET' });
      const nextContext = response.context || null;
      setContext(nextContext);
      const nextScopeOptions = nextContext?.scope?.scope_options || [];
      if (!scopeValue && nextScopeOptions.length > 0) {
        const preferred = nextScopeOptions.find((item: ScopeOption) => item.is_current) || nextScopeOptions[0];
        if (preferred) {
          setSelectedScopeKey(`${preferred.scope_type}:${preferred.scope_target_id}`);
        }
      }
      const nextAllowedHorizons = nextContext?.subscription?.allowed_horizons || [30];
      if (!nextAllowedHorizons.includes(Number(selectedPeriod))) {
        setSelectedPeriod(String(nextAllowedHorizons[0] || 30));
      }
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : (isRu ? 'Не удалось загрузить контекст' : 'Could not load context');
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadContext();
    void loadPlans();
  }, [businessId]);

  useEffect(() => {
    if (!businessId) return;
    if (!selectedScopeKey) return;
    void loadContext(selectedScopeKey);
  }, [selectedScopeKey, businessId]);

  useEffect(() => {
    if (availableWeeks.some((week) => week.key === selectedWeekKey)) return;
    setSelectedWeekKey('all');
  }, [availableWeeks, selectedWeekKey]);

  const toggleMix = (key: ContentMixKey) => {
    setContentMix((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const generatePlan = async () => {
    if (!businessId || !selectedScopeOption) return;
    setGenerating(true);
    setError('');
    try {
      const response = await newAuth.makeRequest('/content-plans/generate', {
        method: 'POST',
        body: JSON.stringify({
          business_id: businessId,
          scope_type: selectedScopeOption.scope_type,
          scope_target_id: selectedScopeOption.scope_target_id,
          period_days: Number(selectedPeriod),
          density: selectedDensity,
          content_mix: contentMix,
        }),
      });
      setCurrentPlan(response.plan || null);
      await loadPlans();
    } catch (generationError) {
      const message = generationError instanceof Error ? generationError.message : (isRu ? 'Не удалось собрать план' : 'Could not generate plan');
      setError(message);
    } finally {
      setGenerating(false);
    }
  };

  const saveItem = async (itemId: string) => {
    setBusyItemId(itemId);
    try {
      await persistItemEdits(itemId);
    } finally {
      setBusyItemId('');
    }
  };

  const generateDraft = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/generate-draft`, {
        method: 'POST',
      });
      setCurrentPlan(response.plan || null);
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать черновик' : 'Could not generate draft');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const createNews = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    try {
      await persistItemEdits(itemId);
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/create-news`, {
        method: 'POST',
      });
      setCurrentPlan(response.plan || null);
    } catch (publishError) {
      const message = publishError instanceof Error ? publishError.message : (isRu ? 'Не удалось создать новость' : 'Could not create news');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const persistItemEdits = async (itemId: string) => {
    setError('');
    const payload: Record<string, string> = {};
    if (themeEdits[itemId] !== undefined) payload.theme = themeEdits[itemId];
    if (dateEdits[itemId] !== undefined) payload.scheduled_for = dateEdits[itemId];
    if (draftEdits[itemId] !== undefined) payload.draft_text = draftEdits[itemId];
    if (Object.keys(payload).length === 0) {
      return currentPlan;
    }
    const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    const nextPlan = response.plan || null;
    setCurrentPlan(nextPlan);
    return nextPlan;
  };

  const runBulkGenerateDrafts = async () => {
    if (bulkDraftCandidates.length === 0) return;
    setBulkBusyAction('drafts');
    setError('');
    try {
      let nextPlan = currentPlan;
      for (const item of bulkDraftCandidates) {
        const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/generate-draft`, {
          method: 'POST',
        });
        nextPlan = response.plan || null;
        setCurrentPlan(nextPlan);
      }
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать черновики' : 'Could not generate drafts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runBulkCreateNews = async () => {
    if (bulkNewsCandidates.length === 0) return;
    setBulkBusyAction('news');
    setError('');
    try {
      let nextPlan = currentPlan;
      for (const item of bulkNewsCandidates) {
        await persistItemEdits(item.id);
        const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/create-news`, {
          method: 'POST',
        });
        nextPlan = response.plan || null;
        setCurrentPlan(nextPlan);
      }
    } catch (publishError) {
      const message = publishError instanceof Error ? publishError.message : (isRu ? 'Не удалось создать новости' : 'Could not create news items');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  if (!businessId) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-6 py-8 text-sm text-gray-600">
        {isRu ? 'Сначала выберите бизнес, чтобы собрать контент-план.' : 'Select a business first to build a content plan.'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              <CalendarDays className="h-4 w-4" />
              {isRu ? 'Контент-план' : 'Content plan'}
            </div>
            <h4 className="text-xl font-semibold text-slate-950">
              {isRu ? 'План публикаций для карт' : 'Maps content plan'}
            </h4>
            <p className="max-w-3xl text-sm leading-6 text-slate-600">
              {isRu
                ? 'Соберите план на 30/60/90 дней на основе услуг, SEO-ключей, продаж, отзывов и слабых зон карточки.'
                : 'Build a 30/60/90 day plan using services, SEO, sales, reviews, and listing weak spots.'}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <div className="font-semibold text-slate-900">
              {isRu ? 'Тариф' : 'Plan access'}
            </div>
            <div className="mt-1">
              {(context?.subscription?.tier || 'trial').toString()}
            </div>
          </div>
        </div>
      </div>

      {selectedScopeDescription ? (
        <div className="rounded-2xl border border-indigo-100 bg-indigo-50/70 px-5 py-4 text-sm text-indigo-950">
          <div className="font-semibold">
            {selectedScopeLabel || (isRu ? 'Выбранный сценарий' : 'Selected scope')}
          </div>
          <div className="mt-1 leading-6 text-indigo-900/90">
            {selectedScopeDescription}
          </div>
        </div>
      ) : null}

      {readiness && !readiness.is_grounded_for_search ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-950">
          <div className="font-semibold">
            {isRu ? 'План пока строится не на полном наборе данных' : 'The plan is not yet using the full data set'}
          </div>
          <div className="mt-1 leading-6 text-amber-900/90">
            {isRu
              ? 'Сейчас контент-план опирается в основном на аудит и сезонные поводы. Чтобы получить темы по реальному спросу, добавьте карту и услуги.'
              : 'Right now the plan relies mostly on audit signals and seasonal prompts. Add a map listing and services to ground it in real demand.'}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {missingInputs.includes('map_links') ? (
              <span className="rounded-full border border-amber-300 bg-white/80 px-3 py-1 text-xs font-medium text-amber-800">
                {isRu ? 'Нет ссылки на карту' : 'No map listing yet'}
              </span>
            ) : null}
            {missingInputs.includes('services') ? (
              <span className="rounded-full border border-amber-300 bg-white/80 px-3 py-1 text-xs font-medium text-amber-800">
                {isRu ? 'Нет услуг в карточке' : 'No services yet'}
              </span>
            ) : null}
            {missingInputs.includes('seo_keywords') ? (
              <span className="rounded-full border border-amber-300 bg-white/80 px-3 py-1 text-xs font-medium text-amber-800">
                {isRu ? 'Нет SEO-ключей по реальному спросу' : 'No grounded SEO keywords yet'}
              </span>
            ) : null}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {missingInputs.includes('map_links') ? (
              <Button
                type="button"
                variant="outline"
                className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100"
                onClick={() => navigate('/dashboard/profile')}
              >
                {isRu ? 'Добавить ссылку на карту' : 'Add map link'}
              </Button>
            ) : null}
            {missingInputs.includes('services') ? (
              <Button
                type="button"
                variant="outline"
                className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100"
                onClick={() => navigate('/dashboard/card?tab=services')}
              >
                {isRu ? 'Добавить услуги' : 'Add services'}
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-700">{isRu ? 'Куда строить план' : 'Scope'}</div>
              <Select value={selectedScopeKey} onValueChange={setSelectedScopeKey}>
                <SelectTrigger className="rounded-xl border-slate-200">
                  <SelectValue placeholder={isRu ? 'Выберите точку или сеть' : 'Select scope'} />
                </SelectTrigger>
                <SelectContent>
                  {scopeOptions.map((item) => {
                    const key = `${item.scope_type}:${item.scope_target_id}`;
                    const labelPrefix = item.is_parent
                      ? (isRu ? 'Материнская точка' : 'Parent network')
                      : item.scope_type === 'network_location'
                        ? (isRu ? 'Точка сети' : 'Network location')
                        : (isRu ? 'Текущий бизнес' : 'Current business');
                    return (
                      <SelectItem key={key} value={key}>
                        {labelPrefix}: {item.label}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-700">{isRu ? 'Горизонт планирования' : 'Planning horizon'}</div>
              <div className="grid grid-cols-3 gap-2">
                {PERIOD_OPTIONS.map((period) => {
                  const allowed = allowedHorizons.includes(period);
                  return (
                    <button
                      key={period}
                      type="button"
                      disabled={!allowed}
                      onClick={() => allowed && setSelectedPeriod(String(period))}
                      className={[
                        'rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
                        selectedPeriod === String(period) && allowed
                          ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                          : 'border-slate-200 bg-white text-slate-700',
                        !allowed ? 'cursor-not-allowed opacity-60' : 'hover:bg-slate-50',
                      ].join(' ')}
                    >
                      <div className="flex items-center justify-center gap-1">
                        {!allowed ? <Lock className="h-3.5 w-3.5" /> : null}
                        {period}
                      </div>
                    </button>
                  );
                })}
              </div>
              {!allowedHorizons.includes(60) || !allowedHorizons.includes(90) ? (
                <div className="text-xs text-amber-700">
                  {isRu
                    ? 'Планы на 60 и 90 дней доступны на тарифах 25k и Elite.'
                    : '60 and 90 day plans are available on 25k and Elite tiers.'}
                </div>
              ) : null}
            </div>

            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-700">{isRu ? 'Плотность' : 'Density'}</div>
              <Select value={selectedDensity} onValueChange={setSelectedDensity}>
                <SelectTrigger className="rounded-xl border-slate-200">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DENSITY_OPTIONS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {isRu ? item.labelRu : item.labelEn}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-700">{isRu ? 'Что использовать' : 'Use signals from'}</div>
              <div className="flex flex-wrap gap-2">
                {CONTENT_MIX_OPTIONS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => toggleMix(item.key)}
                    className={[
                      'rounded-full border px-3 py-1.5 text-sm transition-colors',
                      contentMix[item.key]
                        ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                        : 'border-slate-200 bg-white text-slate-600',
                    ].join(' ')}
                  >
                    {isRu ? item.labelRu : item.labelEn}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button onClick={generatePlan} disabled={generating || loading || !selectedScopeOption}>
              <Sparkles className="mr-2 h-4 w-4" />
              {generating
                ? (isRu ? 'Собираем план...' : 'Building plan...')
                : (isRu ? 'Собрать план' : 'Build plan')}
            </Button>
            <Button variant="outline" onClick={() => { void loadContext(); void loadPlans(); }} disabled={loading}>
              <Wand2 className="mr-2 h-4 w-4" />
              {isRu ? 'Обновить контекст' : 'Refresh context'}
            </Button>
          </div>

          {error ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
            {isRu ? 'Контекст' : 'Planning context'}
          </div>
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            {isNetworkContext ? (
              <div>
                <div className="font-semibold text-slate-900">{isRu ? 'Режим сети' : 'Network mode'}</div>
                <div>
                  {context?.scope?.network?.has_parent_scope
                    ? `${isRu ? 'Точек в сети' : 'Locations in network'}: ${context?.scope?.network?.locations_count || 0}`
                    : (isRu ? 'План строится по текущему бизнесу.' : 'Planning uses the current business.')}
                </div>
              </div>
            ) : null}
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Ссылки на карты' : 'Map listings'}</div>
              <div>{readiness?.map_links_count || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Услуги' : 'Services'}</div>
              <div>{context?.services?.length || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'SEO-ключи' : 'SEO keywords'}</div>
              <div>{context?.seo_keywords?.length || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Продажи' : 'Sales signals'}</div>
              <div>{context?.sales_signals?.length || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Сигналы аудита' : 'Audit signals'}</div>
              <div>{context?.audit_signals?.length || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Последние новости' : 'Recent news'}</div>
              <div>{context?.recent_news?.length || 0}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Последние планы' : 'Recent plans'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {currentPlan?.title || (isRu ? 'План ещё не собран' : 'No plan yet')}
            </div>
          </div>
          <div className="text-sm text-slate-600">
            {plans.length > 0 ? `${plans.length}` : '0'}
          </div>
        </div>

        {plans.length > 0 ? (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap gap-2">
              {availablePlanTargets.map((target) => (
                <button
                  key={target.key}
                  type="button"
                  onClick={() => setSelectedPlanTargetKey(target.key)}
                  className={[
                    'rounded-full border px-3 py-1.5 text-sm transition-colors',
                    selectedPlanTargetKey === target.key
                      ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {target.label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {visiblePlans.map((plan) => (
              <button
                key={plan.id}
                type="button"
                onClick={async () => {
                  const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(plan.id)}`, { method: 'GET' });
                  setCurrentPlan(response.plan || null);
                }}
                className={[
                  'rounded-full border px-3 py-1.5 text-sm transition-colors',
                  currentPlan?.id === plan.id
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                    : 'border-slate-200 bg-white text-slate-600',
                ].join(' ')}
              >
                {_scopeChipLabel(plan.scope_type, isRu)} · {_planTargetLabel(plan, isRu)} · {plan.period_days} {isRu ? 'дней' : 'days'}
              </button>
            ))}
            </div>
          </div>
        ) : null}

        {currentPlan?.items && currentPlan.items.length > 0 ? (
          <div className="mt-6 space-y-4">
            {itemLocationSummary.length > 1 ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {isRu ? 'Распределение по точкам' : 'Distribution by location'}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {itemLocationSummary.map((entry) => (
                    <div
                      key={entry.label}
                      className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                    >
                      {entry.label} · {entry.count}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {ITEM_FILTER_OPTIONS.map((filterKey) => (
                <button
                  key={filterKey}
                  type="button"
                  onClick={() => setSelectedItemFilter(filterKey)}
                  className={[
                    'rounded-full border px-3 py-1.5 text-sm transition-colors',
                    selectedItemFilter === filterKey
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {_itemFilterLabel(filterKey, isRu)} · {itemFilterCounts[filterKey]}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {SIGNAL_FILTER_OPTIONS.map((filterKey) => (
                <button
                  key={filterKey}
                  type="button"
                  onClick={() => setSelectedSignalFilter(filterKey)}
                  className={[
                    'rounded-full border px-3 py-1.5 text-sm transition-colors',
                    selectedSignalFilter === filterKey
                      ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {_signalFilterLabel(filterKey, isRu)} · {signalFilterCounts[filterKey]}
                </button>
              ))}
            </div>
            {availableItemLocations.length > 1 ? (
              <div className="flex flex-wrap gap-2">
                {availableItemLocations.map((location) => (
                  <button
                    key={location.key}
                    type="button"
                    onClick={() => setSelectedItemLocationKey(location.key)}
                    className={[
                      'rounded-full border px-3 py-1.5 text-sm transition-colors',
                      selectedItemLocationKey === location.key
                        ? 'border-sky-300 bg-sky-50 text-sky-800'
                        : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                    ].join(' ')}
                  >
                    {location.label}
                  </button>
                ))}
              </div>
            ) : null}
            {availableWeeks.length > 1 ? (
              <div className="flex flex-wrap gap-2">
                {availableWeeks.map((week) => (
                  <button
                    key={week.key}
                    type="button"
                    onClick={() => setSelectedWeekKey(week.key)}
                    className={[
                      'rounded-full border px-3 py-1.5 text-sm transition-colors',
                      selectedWeekKey === week.key
                        ? 'border-violet-300 bg-violet-50 text-violet-800'
                        : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                    ].join(' ')}
                  >
                    {week.label}
                  </button>
                ))}
              </div>
            ) : null}
            {weekSummary.length > 1 ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {weekSummary.map((week) => (
                  <button
                    key={week.key}
                    type="button"
                    onClick={() => setSelectedWeekKey(week.key)}
                    className={[
                      'rounded-2xl border px-4 py-4 text-left transition-colors',
                      selectedWeekKey === week.key
                        ? 'border-violet-300 bg-violet-50'
                        : 'border-slate-200 bg-white hover:bg-slate-50',
                    ].join(' ')}
                  >
                    <div className="text-sm font-semibold text-slate-900">
                      {week.label}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">
                        {isRu ? 'Всего' : 'Total'} · {week.total}
                      </span>
                      <span className="rounded-full bg-amber-100 px-2.5 py-1 text-amber-800">
                        {isRu ? 'Без текста' : 'No draft'} · {week.needsDraft}
                      </span>
                      <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-emerald-800">
                        {isRu ? 'Готово к публикации' : 'Ready to publish'} · {week.readyToPublish}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <Button
                variant="outline"
                onClick={() => { void runBulkGenerateDrafts(); }}
                disabled={Boolean(bulkBusyAction) || bulkDraftCandidates.length === 0}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {bulkBusyAction === 'drafts'
                  ? (isRu ? 'Генерируем черновики...' : 'Generating drafts...')
                  : `${isRu ? 'Сгенерировать по выборке' : 'Generate for filtered'} · ${bulkDraftCandidates.length}`}
              </Button>
              <Button
                onClick={() => { void runBulkCreateNews(); }}
                disabled={Boolean(bulkBusyAction) || bulkNewsCandidates.length === 0}
              >
                {bulkBusyAction === 'news'
                  ? (isRu ? 'Создаём новости...' : 'Creating news...')
                  : `${isRu ? 'Создать новости по выборке' : 'Create news for filtered'} · ${bulkNewsCandidates.length}`}
              </Button>
            </div>
            {visibleItems.map((item) => {
              const currentDraft = draftEdits[item.id] !== undefined ? draftEdits[item.id] : item.draft_text;
              const currentTheme = themeEdits[item.id] !== undefined ? themeEdits[item.id] : item.theme;
              const currentDate = dateEdits[item.id] !== undefined ? dateEdits[item.id] : item.scheduled_for;
              return (
                <div key={item.id} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="grid flex-1 gap-3 md:grid-cols-[180px_1fr]">
                      <div className="space-y-2">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          {isRu ? 'Дата' : 'Date'}
                        </div>
                        <Input
                          type="date"
                          value={currentDate}
                          onChange={(event) => setDateEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                        />
                      </div>
                      <div className="space-y-2">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          {isRu ? 'Тема' : 'Theme'}
                        </div>
                        <Input
                          value={currentTheme}
                          onChange={(event) => setThemeEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                        />
                      </div>
                    </div>
                    <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                      {_contentTypeLabel(item.content_type, isRu)}
                      {item.location_scope ? ` · ${_locationScopeLabel(currentPlan?.scope_type || '', isRu)}` : ''}
                      {item.location_label ? ` · ${_itemLocationLabel(item, isRu)}` : ''}
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
                      <div className="font-semibold text-slate-900">{isRu ? 'Почему эта тема' : 'Why this theme'}</div>
                      <div className="mt-2">{item.goal || '—'}</div>
                      <div className="mt-2 text-xs text-slate-500">
                        <MapPinned className="mr-1 inline h-3.5 w-3.5" />
                        {item.source_kind || 'signal'} {item.source_ref ? `· ${item.source_ref}` : ''}
                        {item.seo_keyword ? ` · SEO: ${item.seo_keyword}` : ''}
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        {isRu ? 'Черновик' : 'Draft'}
                      </div>
                      <Textarea
                        rows={4}
                        value={currentDraft}
                        onChange={(event) => setDraftEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                        placeholder={isRu ? 'Здесь появится текст публикации' : 'Draft text will appear here'}
                      />
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      onClick={() => generateDraft(item.id)}
                      disabled={busyItemId === item.id}
                    >
                      <Sparkles className="mr-2 h-4 w-4" />
                      {isRu ? 'Сгенерировать текст' : 'Generate draft'}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => saveItem(item.id)}
                      disabled={busyItemId === item.id}
                    >
                      {isRu ? 'Сохранить' : 'Save'}
                    </Button>
                    <Button
                      onClick={() => createNews(item.id)}
                      disabled={busyItemId === item.id || !currentDraft.trim()}
                    >
                      {item.usernews_id
                        ? (isRu ? 'Новость уже создана' : 'News already created')
                        : (isRu ? 'Создать новость' : 'Create news')}
                    </Button>
                  </div>
                </div>
              );
            })}
            {visibleItems.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-sm text-slate-600">
                {isRu
                  ? 'Для выбранного сочетания фильтров пока нет публикаций. Переключите статус или источник сигнала выше.'
                  : 'There are no items for this filter combination yet. Switch the status or signal filter above.'}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10 text-center text-sm text-slate-600">
            {loading
              ? (isRu ? 'Загружаем контекст и планы...' : 'Loading context and plans...')
              : (isRu ? 'Соберите первый контент-план, чтобы здесь появился календарь публикаций.' : 'Build your first content plan to see planned posts here.')}
          </div>
        )}
      </div>
    </div>
  );
}

function _contentTypeLabel(contentType: string, isRu: boolean): string {
  const normalized = String(contentType || '').trim().toLowerCase();
  if (normalized === 'seo') return isRu ? 'SEO' : 'SEO';
  if (normalized === 'service') return isRu ? 'Услуга' : 'Service';
  if (normalized === 'sales') return isRu ? 'Продажи' : 'Sales';
  if (normalized === 'audit') return isRu ? 'Аудит' : 'Audit';
  if (normalized === 'seasonal') return isRu ? 'Сезонность' : 'Seasonal';
  return isRu ? 'Контент' : 'Content';
}

function _scopeChipLabel(scopeType: string, isRu: boolean): string {
  const normalized = String(scopeType || '').trim().toLowerCase();
  if (normalized === 'network_parent') return isRu ? 'Сеть' : 'Network';
  if (normalized === 'network_location') return isRu ? 'Точка' : 'Location';
  return isRu ? 'Бизнес' : 'Business';
}

function _locationScopeLabel(scopeType: string, isRu: boolean): string {
  const normalized = String(scopeType || '').trim().toLowerCase();
  if (normalized === 'network_parent') return isRu ? 'материнский план' : 'parent plan';
  if (normalized === 'network_location') return isRu ? 'локальный план' : 'local plan';
  return isRu ? 'текущий бизнес' : 'current business';
}

function _planTargetLabel(plan: Pick<PlanPayload, 'scope_type' | 'scope_target_label' | 'scope_target_city' | 'scope_target_address'>, isRu: boolean): string {
  const label = String(plan.scope_target_label || '').trim();
  const city = String(plan.scope_target_city || '').trim();
  const address = String(plan.scope_target_address || '').trim();
  if (label && city) return `${label} · ${city}`;
  if (label && address) return `${label} · ${address}`;
  if (label) return label;
  return _scopeChipLabel(plan.scope_type, isRu);
}

function _itemLocationLabel(item: Pick<PlanItem, 'location_label' | 'location_city' | 'location_address'>, isRu: boolean): string {
  const label = String(item.location_label || '').trim();
  const city = String(item.location_city || '').trim();
  const address = String(item.location_address || '').trim();
  if (label && city) return `${label} · ${city}`;
  if (label && address) return `${label} · ${address}`;
  if (label) return label;
  return isRu ? 'Точка сети' : 'Network location';
}

function _itemFilterLabel(filterKey: ItemFilterKey, isRu: boolean): string {
  if (filterKey === 'needs_draft') return isRu ? 'Без текста' : 'No draft';
  if (filterKey === 'has_draft') return isRu ? 'Есть черновик' : 'Has draft';
  if (filterKey === 'news_created') return isRu ? 'Есть новость' : 'News created';
  return isRu ? 'Все' : 'All';
}

function _matchesItemFilter(item: PlanItem, filterKey: ItemFilterKey): boolean {
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  if (filterKey === 'needs_draft') return !hasDraft;
  if (filterKey === 'has_draft') return hasDraft && !hasNews;
  if (filterKey === 'news_created') return hasNews;
  return true;
}

function _signalFilterLabel(filterKey: SignalFilterKey, isRu: boolean): string {
  if (filterKey === 'seo') return 'SEO';
  if (filterKey === 'services') return isRu ? 'Услуги' : 'Services';
  if (filterKey === 'sales') return isRu ? 'Продажи' : 'Sales';
  if (filterKey === 'audit') return isRu ? 'Аудит' : 'Audit';
  if (filterKey === 'seasonal') return isRu ? 'Сезонность' : 'Seasonal';
  return isRu ? 'Все сигналы' : 'All signals';
}

function _matchesSignalFilter(item: PlanItem, filterKey: SignalFilterKey): boolean {
  if (filterKey === 'all') return true;
  const normalizedContentType = String(item.content_type || '').trim().toLowerCase();
  if (filterKey === 'services') return normalizedContentType === 'service';
  return normalizedContentType === filterKey;
}

function _matchesItemLocationFilter(item: PlanItem, filterKey: string): boolean {
  if (filterKey === 'all') return true;
  const itemKey = String(item.location_scope || item.business_id || '').trim();
  return itemKey === filterKey;
}

function _weekBucketKey(dateValue: string): string {
  const value = String(dateValue || '').trim();
  if (!value) return '';
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return '';
  const day = date.getUTCDay() || 7;
  const monday = new Date(date);
  monday.setUTCDate(date.getUTCDate() - day + 1);
  return monday.toISOString().slice(0, 10);
}

function _weekBucketLabel(weekKey: string, isRu: boolean): string {
  const value = String(weekKey || '').trim();
  if (!value) return isRu ? 'Неделя' : 'Week';
  const monday = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(monday.getTime())) return value;
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  const formatter = new Intl.DateTimeFormat(isRu ? 'ru-RU' : 'en-US', {
    day: 'numeric',
    month: 'short',
  });
  return `${formatter.format(monday)} - ${formatter.format(sunday)}`;
}
