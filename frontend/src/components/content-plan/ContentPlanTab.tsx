import React, { useEffect, useMemo, useState } from 'react';
import { CalendarDays, CheckSquare, Lock, MapPinned, MoreHorizontal, Sparkles, Wand2 } from 'lucide-react';
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
  seo_views?: number;
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

type LearningMetricsPayload = {
  window_days: number;
  items: Array<{
    capability: string;
    generated_total: number;
    accepted_total: number;
    accepted_edited_total: number;
    skipped_total: number;
    rescheduled_total: number;
    minor_edit_total: number;
    major_rewrite_total: number;
    edited_before_accept_pct: number;
  }>;
  summary: {
    generated_total?: number;
    accepted_total?: number;
    accepted_edited_total?: number;
    skipped_total?: number;
    rescheduled_total?: number;
    minor_edit_total?: number;
    major_rewrite_total?: number;
    edited_before_accept_pct?: number;
  };
  source_kind_breakdown?: Array<{
    key: string;
    accepted_total: number;
    accepted_edited_total: number;
    edited_before_accept_pct: number;
  }>;
  content_type_breakdown?: Array<{
    key: string;
    accepted_total: number;
    accepted_edited_total: number;
    edited_before_accept_pct: number;
  }>;
  location_breakdown?: Array<{
    key: string;
    label?: string;
    accepted_total: number;
    accepted_edited_total: number;
    edited_before_accept_pct: number;
  }>;
  network_quality?: Array<{
    key: string;
    label?: string;
    accepted_total: number;
    accepted_edited_total: number;
    skipped_total: number;
    rescheduled_total: number;
    major_rewrite_total: number;
    draft_generated_total: number;
    edited_before_accept_pct: number;
    planned_activity_total: number;
    risk_score: number;
    reasons?: string[];
  }>;
  quality_insights?: Array<{
    kind: string;
    text_ru: string;
    text_en: string;
  }>;
};

type ActionSummary = {
  tone: 'neutral' | 'success' | 'warning';
  text_ru: string;
  text_en: string;
  details_ru?: string[];
  details_en?: string[];
  focusLocationKey?: string;
  focusWeekKey?: string;
};

type BulkNewsReview = {
  key: string;
  titleRu: string;
  titleEn: string;
  descriptionRu: string;
  descriptionEn: string;
  items: PlanItem[];
  busyAction: string;
  summaryPrefixRu?: string;
  summaryPrefixEn?: string;
  focusLocationKey?: string;
  focusWeekKey?: string;
};

type BulkActionReview = {
  key: string;
  kind: 'skip' | 'reschedule';
  titleRu: string;
  titleEn: string;
  descriptionRu: string;
  descriptionEn: string;
  confirmLabelRu: string;
  confirmLabelEn: string;
  items: PlanItem[];
  busyAction: string;
  targetDate?: string;
  summaryPrefixRu?: string;
  summaryPrefixEn?: string;
  focusLocationKey?: string;
  focusWeekKey?: string;
};

type NetworkOperatingSlice = {
  key: string;
  label: string;
  riskScore: number;
  reasons: string[];
  total: number;
  needsDraft: number;
  readyToPublish: number;
  published: number;
  skipped: number;
  focusWeekKey: string;
  focusWeekLabel: string;
  focusWeekNeedsDraft: number;
  focusWeekReadyToPublish: number;
  recommendation: string;
};

type OperatorInsight = {
  key: string;
  textRu: string;
  textEn: string;
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
type ItemFilterKey = 'all' | 'urgent' | 'needs_draft' | 'has_draft' | 'news_created';
type SignalFilterKey = 'all' | ContentMixKey;
type ViewPresetKey = 'overview' | 'urgent' | 'ready' | 'published' | 'focus' | 'custom';
type QuickActionKey = 'create_month_plan' | 'open_week' | 'weak_locations' | 'fix_gaps' | 'repeat_template';
type ContentPlanZone = 'overview' | 'plan' | 'queue' | 'editor';
type ContentPlanMode = 'point' | 'network';

const CONTENT_MIX_OPTIONS: Array<{ key: ContentMixKey; labelRu: string; labelEn: string }> = [
  { key: 'services', labelRu: 'Услуги', labelEn: 'Services' },
  { key: 'seo', labelRu: 'SEO', labelEn: 'SEO' },
  { key: 'sales', labelRu: 'Продажи', labelEn: 'Sales' },
  { key: 'audit', labelRu: 'Аудит', labelEn: 'Audit' },
  { key: 'seasonal', labelRu: 'Сезонность', labelEn: 'Seasonal' },
];
const ITEM_FILTER_OPTIONS: ItemFilterKey[] = ['all', 'urgent', 'needs_draft', 'has_draft', 'news_created'];
const SIGNAL_FILTER_OPTIONS: SignalFilterKey[] = ['all', 'seo', 'services', 'sales', 'audit', 'seasonal'];
const CONTENT_PLAN_PREFERENCES_KEY = 'content_plan_preferences_v1';

export default function ContentPlanTab({ businessId }: ContentPlanTabProps) {
  const navigate = useNavigate();
  const { language } = useLanguage();
  const isRu = language === 'ru';
  const [context, setContext] = useState<ContextPayload | null>(null);
  const [plans, setPlans] = useState<PlanPayload[]>([]);
  const [currentPlan, setCurrentPlan] = useState<PlanPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [error, setError] = useState('');
  const [learningMetrics, setLearningMetrics] = useState<LearningMetricsPayload | null>(null);
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
  const [actionSummary, setActionSummary] = useState<ActionSummary | null>(null);
  const [selectedItemFilter, setSelectedItemFilter] = useState<ItemFilterKey>('all');
  const [selectedSignalFilter, setSelectedSignalFilter] = useState<SignalFilterKey>('all');
  const [selectedPlanTargetKey, setSelectedPlanTargetKey] = useState('all');
  const [selectedItemLocationKey, setSelectedItemLocationKey] = useState('all');
  const [selectedWeekKey, setSelectedWeekKey] = useState('all');
  const [sortMode, setSortMode] = useState<'priority' | 'date'>(() => _readStoredSortMode());
  const [selectedViewPreset, setSelectedViewPreset] = useState<ViewPresetKey>('overview');
  const [lastFocusLocationKey, setLastFocusLocationKey] = useState('all');
  const [lastFocusWeekKey, setLastFocusWeekKey] = useState('all');
  const [showAdvancedControls, setShowAdvancedControls] = useState(false);
  const [showPlanSetupDetails, setShowPlanSetupDetails] = useState(false);
  const [showLearningDetails, setShowLearningDetails] = useState(false);
  const [showContextDetails, setShowContextDetails] = useState(false);
  const [bulkTargetDate, setBulkTargetDate] = useState(() => _shiftIsoDate('', 7));
  const [expandedDuplicateItemId, setExpandedDuplicateItemId] = useState('');
  const [duplicateTargetSelections, setDuplicateTargetSelections] = useState<Record<string, string[]>>({});
  const [duplicateDateOverrides, setDuplicateDateOverrides] = useState<Record<string, string>>({});
  const [bulkNewsReview, setBulkNewsReview] = useState<BulkNewsReview | null>(null);
  const [bulkActionReview, setBulkActionReview] = useState<BulkActionReview | null>(null);
  const [recentGeneratedItemId, setRecentGeneratedItemId] = useState('');
  const [activeZone, setActiveZone] = useState<ContentPlanZone>('overview');
  const [contentMode, setContentMode] = useState<ContentPlanMode>('point');
  const [selectedQueueItemId, setSelectedQueueItemId] = useState('');
  const [showSelectedItemDetails, setShowSelectedItemDetails] = useState(false);
  const [selectedItemIds, setSelectedItemIds] = useState<Record<string, boolean>>({});
  const [showRecentPlans, setShowRecentPlans] = useState(false);

  const allowedHorizons = context?.subscription?.allowed_horizons || [30];
  const scopeOptions = context?.scope?.scope_options || [];
  const isNetworkContext = Boolean(context?.scope?.network?.is_network);
  const selectedScopeDescription = context?.scope?.selected_scope_description || '';
  const selectedScopeLabel = context?.scope?.selected_scope_label || '';
  const readiness = context?.readiness || null;
  const missingInputs = Array.isArray(readiness?.missing_inputs) ? readiness?.missing_inputs : [];
  const mapLinksCount = Number(readiness?.map_links_count || 0);
  const servicesCount = context?.services?.length || 0;
  const seoKeywordsCount = context?.seo_keywords?.length || 0;
  const networkLocationsCount = context?.scope?.network?.locations_count || 0;
  const hasSearchFoundation = mapLinksCount > 0 && seoKeywordsCount > 0;
  const hasOnlyServicesGap = missingInputs.length === 1 && missingInputs.includes('services');
  const networkHasSearchPlanFoundation = isNetworkContext && hasSearchFoundation && hasOnlyServicesGap;
  const isNetworkMode = contentMode === 'network' && isNetworkContext;
  const networkScopeOption = useMemo(() => (
    scopeOptions.find((item) => item.scope_type === 'network_parent') || null
  ), [scopeOptions]);
  const pointScopeOption = useMemo(() => (
    scopeOptions.find((item) => item.is_current)
    || scopeOptions.find((item) => item.scope_type !== 'network_parent')
    || scopeOptions[0]
    || null
  ), [scopeOptions]);

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
      if (String(item.status || '').trim() === 'skipped') continue;
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
    filteredItems
      .filter((item) => selectedWeekKey === 'all' || _weekBucketKey(item.scheduled_for) === selectedWeekKey)
      .slice()
      .sort((left, right) => {
        if (recentGeneratedItemId) {
          if (left.id === recentGeneratedItemId && right.id !== recentGeneratedItemId) return -1;
          if (right.id === recentGeneratedItemId && left.id !== recentGeneratedItemId) return 1;
        }
        if (sortMode === 'priority') {
          const priorityDiff = _itemPriorityRank(left) - _itemPriorityRank(right);
          if (priorityDiff !== 0) return priorityDiff;
        }
        const dateDiff = String(left.scheduled_for || '').localeCompare(String(right.scheduled_for || ''));
        if (dateDiff !== 0) return dateDiff;
        return String(left.theme || '').localeCompare(String(right.theme || ''));
      })
  ), [filteredItems, recentGeneratedItemId, selectedWeekKey, sortMode]);
  const selectedQueueItem = useMemo(() => (
    visibleItems.find((item) => item.id === selectedQueueItemId) || visibleItems[0] || null
  ), [selectedQueueItemId, visibleItems]);
  const itemFilterCounts = useMemo(() => {
    const items = currentPlan?.items || [];
    return ITEM_FILTER_OPTIONS.reduce<Record<ItemFilterKey, number>>((acc, filterKey) => {
      acc[filterKey] = items.filter((item) => _matchesItemFilter(item, filterKey)).length;
      return acc;
    }, {
      all: 0,
      urgent: 0,
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
  const locationOperationalSummary = useMemo(() => {
    const buckets = new Map<string, { key: string; label: string; total: number; needsDraft: number; readyToPublish: number }>();
    for (const item of filteredItems) {
      if (String(item.status || '').trim() === 'skipped') continue;
      const key = String(item.location_scope || item.business_id || '').trim();
      if (!key) continue;
      const existing = buckets.get(key) || {
        key,
        label: _itemLocationLabel(item, isRu),
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
    return Array.from(buckets.values()).sort((left, right) => right.total - left.total);
  }, [filteredItems, isRu]);
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
  const selectedItems = useMemo(() => (
    visibleItems.filter((item) => Boolean(selectedItemIds[item.id]))
  ), [selectedItemIds, visibleItems]);
  const selectedDraftCandidates = useMemo(() => (
    selectedItems.filter((item) => !String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim())
  ), [selectedItems]);
  const selectedNewsCandidates = useMemo(() => (
    selectedItems.filter((item) => String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim())
  ), [selectedItems]);
  const missingDateCandidates = useMemo(() => (
    visibleItems.filter((item) => !_inputDateValue(item.scheduled_for) && !String(item.usernews_id || '').trim())
  ), [visibleItems]);
  const planOperationalSummary = useMemo(() => {
    const items = currentPlan?.items || [];
    return items.reduce(
      (acc, item) => {
        const status = String(item.status || '').trim();
        const hasDraft = Boolean(String(item.draft_text || '').trim());
        const hasNews = Boolean(String(item.usernews_id || '').trim());
        acc.total += 1;
        if (status === 'skipped') {
          acc.skipped += 1;
          return acc;
        }
        if (!hasDraft) acc.needsDraft += 1;
        if (hasDraft && !hasNews) acc.readyToPublish += 1;
        if (hasNews) acc.published += 1;
        return acc;
      },
      {
        total: 0,
        needsDraft: 0,
        readyToPublish: 0,
        published: 0,
        skipped: 0,
      },
    );
  }, [currentPlan?.items]);
  const overviewRiskScore = useMemo(() => {
    const networkRisk = Math.max(...(learningMetrics?.network_quality || []).map((item) => Number(item.risk_score || 0)), 0);
    const skippedRisk = planOperationalSummary.skipped > 0 ? Math.min(100, planOperationalSummary.skipped * 12) : 0;
    const emptyRisk = planOperationalSummary.total > 0 && planOperationalSummary.needsDraft === planOperationalSummary.total ? 35 : 0;
    return Math.max(networkRisk, skippedRisk, emptyRisk);
  }, [learningMetrics?.network_quality, planOperationalSummary.needsDraft, planOperationalSummary.skipped, planOperationalSummary.total]);
  const repeatTemplateCandidate = useMemo(() => (
    (currentPlan?.items || []).find((item) => (
      Boolean(String(item.draft_text || item.usernews_id || '').trim())
      && availableItemLocations.length > 2
    )) || null
  ), [currentPlan?.items, availableItemLocations.length]);
  const viewPresets = useMemo<Array<{ key: ViewPresetKey; label: string }>>(() => ([
    {
      key: 'overview',
      label: isRu ? 'Обзор' : 'Overview',
    },
    {
      key: 'urgent',
      label: isRu ? 'Срочное' : 'Urgent',
    },
    {
      key: 'ready',
      label: isRu ? 'Готово к публикации' : 'Ready to publish',
    },
    {
      key: 'published',
      label: isRu ? 'Опубликовано' : 'Published',
    },
    {
      key: 'focus',
      label: isRu ? 'Фокус' : 'Focus',
    },
  ]), [
    isRu,
  ]);
  const activeLocationLabel = useMemo(() => {
    const activeLocation = availableItemLocations.find((item) => item.key === selectedItemLocationKey);
    return activeLocation?.label || (isRu ? 'Все точки' : 'All locations');
  }, [availableItemLocations, selectedItemLocationKey, isRu]);
  const activeWeekLabel = useMemo(() => {
    const activeWeek = availableWeeks.find((item) => item.key === selectedWeekKey);
    return activeWeek?.label || (isRu ? 'Все недели' : 'All weeks');
  }, [availableWeeks, selectedWeekKey, isRu]);
  const locationWeekFocusSummary = useMemo(() => {
    const buckets = new Map<string, {
      key: string;
      locationKey: string;
      weekKey: string;
      locationLabel: string;
      weekLabel: string;
      total: number;
      needsDraft: number;
      readyToPublish: number;
    }>();
    for (const item of currentPlan?.items || []) {
      if (String(item.status || '').trim() === 'skipped') continue;
      const locationKey = String(item.location_scope || item.business_id || '').trim();
      const weekKey = _weekBucketKey(item.scheduled_for);
      if (!locationKey || !weekKey) continue;
      const bucketKey = `${locationKey}::${weekKey}`;
      const existing = buckets.get(bucketKey) || {
        key: bucketKey,
        locationKey,
        weekKey,
        locationLabel: _itemLocationLabel(item, isRu),
        weekLabel: _weekBucketLabel(weekKey, isRu),
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
      buckets.set(bucketKey, existing);
    }
    return Array.from(buckets.values())
      .filter((item) => item.needsDraft > 0 || item.readyToPublish > 0)
      .sort((left, right) => {
        const needsDraftDiff = right.needsDraft - left.needsDraft;
        if (needsDraftDiff !== 0) return needsDraftDiff;
        const readyDiff = right.readyToPublish - left.readyToPublish;
        if (readyDiff !== 0) return readyDiff;
        return right.total - left.total;
      })
      .slice(0, 6);
  }, [currentPlan?.items, isRu]);
  const networkOperatingSlices = useMemo<NetworkOperatingSlice[]>(() => {
    if (!isNetworkMode || !currentPlan?.items?.length) return [];
    const qualityByLocation = new Map<string, NonNullable<LearningMetricsPayload['network_quality']>[number]>();
    for (const item of learningMetrics?.network_quality || []) {
      const key = String(item.key || '').trim();
      if (key) qualityByLocation.set(key, item);
    }
    const locationKeys = new Set<string>();
    for (const item of currentPlan.items) {
      const key = String(item.location_scope || item.business_id || '').trim();
      if (key) locationKeys.add(key);
    }
    const slices: NetworkOperatingSlice[] = [];
    for (const locationKey of Array.from(locationKeys)) {
      const locationItems = currentPlan.items.filter((item) => String(item.location_scope || item.business_id || '').trim() === locationKey);
      if (locationItems.length === 0) continue;
      const quality = qualityByLocation.get(locationKey);
      const firstItem = locationItems[0];
      let needsDraft = 0;
      let readyToPublish = 0;
      let published = 0;
      let skipped = 0;
      const weekBuckets = new Map<string, { key: string; needsDraft: number; readyToPublish: number; total: number }>();
      for (const item of locationItems) {
        const status = String(item.status || '').trim();
        const hasDraft = Boolean(String(item.draft_text || '').trim());
        const hasNews = Boolean(String(item.usernews_id || '').trim());
        if (status === 'skipped') {
          skipped += 1;
          continue;
        }
        if (!hasDraft) needsDraft += 1;
        if (hasDraft && !hasNews) readyToPublish += 1;
        if (hasNews) published += 1;
        const weekKey = _weekBucketKey(item.scheduled_for);
        if (!weekKey) continue;
        const existing = weekBuckets.get(weekKey) || { key: weekKey, needsDraft: 0, readyToPublish: 0, total: 0 };
        existing.total += 1;
        if (!hasDraft) existing.needsDraft += 1;
        if (hasDraft && !hasNews) existing.readyToPublish += 1;
        weekBuckets.set(weekKey, existing);
      }
      const focusWeek = Array.from(weekBuckets.values())
        .filter((item) => item.needsDraft > 0 || item.readyToPublish > 0)
        .sort((left, right) => {
          const urgentDiff = (right.needsDraft + right.readyToPublish) - (left.needsDraft + left.readyToPublish);
          if (urgentDiff !== 0) return urgentDiff;
          return left.key.localeCompare(right.key);
        })[0] || Array.from(weekBuckets.values()).sort((left, right) => left.key.localeCompare(right.key))[0];
      const reasons = quality?.reasons && Array.isArray(quality.reasons) ? quality.reasons : [];
      slices.push({
        key: locationKey,
        label: String(quality?.label || _itemLocationLabel(firstItem, isRu) || locationKey),
        riskScore: Number(quality?.risk_score || 0),
        reasons,
        total: locationItems.length,
        needsDraft,
        readyToPublish,
        published,
        skipped,
        focusWeekKey: focusWeek?.key || 'all',
        focusWeekLabel: focusWeek?.key ? _weekBucketLabel(focusWeek.key, isRu) : (isRu ? 'Все недели' : 'All weeks'),
        focusWeekNeedsDraft: focusWeek?.needsDraft || 0,
        focusWeekReadyToPublish: focusWeek?.readyToPublish || 0,
        recommendation: _networkOperatingRecommendation(reasons, isRu),
      });
    }
    return slices
      .sort((left, right) => {
        const riskDiff = right.riskScore - left.riskScore;
        if (riskDiff !== 0) return riskDiff;
        const urgentDiff = (right.needsDraft + right.readyToPublish + right.skipped) - (left.needsDraft + left.readyToPublish + left.skipped);
        if (urgentDiff !== 0) return urgentDiff;
        return right.total - left.total;
      })
      .slice(0, 5);
  }, [currentPlan?.items, isNetworkMode, isRu, learningMetrics?.network_quality]);
  const quickActions = useMemo(() => {
    const weakLocation = (learningMetrics?.network_quality || [])[0];
    const focusSlice = locationWeekFocusSummary[0];
    const actions: Array<{
      key: QuickActionKey;
      title: string;
      description: string;
      metric: string;
      disabled: boolean;
    }> = [
      {
        key: 'create_month_plan',
        title: isRu ? 'Составить план на месяц' : 'Build a monthly plan',
        description: isRu
          ? 'Пересобрать план на 30 дней по текущим услугам, SEO и слабым зонам.'
          : 'Rebuild a 30 day plan from services, SEO, and weak zones.',
        metric: currentPlan ? `${currentPlan.period_days} ${isRu ? 'дней' : 'days'}` : (isRu ? 'первый план' : 'first plan'),
        disabled: generating || loading || !selectedScopeOption || !allowedHorizons.includes(30),
      },
      {
        key: 'open_week',
        title: isRu ? 'Открыть эту неделю' : 'Open this week',
        description: focusSlice
          ? `${focusSlice.locationLabel} · ${focusSlice.weekLabel}`
          : (isRu ? 'Показать ближайший рабочий срез.' : 'Show the nearest operating slice.'),
        metric: focusSlice ? `${focusSlice.needsDraft + focusSlice.readyToPublish}` : `${visibleItems.length}`,
        disabled: !currentPlan || (!focusSlice && visibleItems.length === 0),
      },
      {
        key: 'weak_locations',
        title: isRu ? 'Показать слабые точки' : 'Show weak locations',
        description: weakLocation
          ? `${String(weakLocation.label || weakLocation.key)} · ${isRu ? 'риск' : 'risk'} ${Number(weakLocation.risk_score || 0).toFixed(0)}`
          : (isRu ? 'Когда накопятся правки, здесь появятся проблемные точки.' : 'Risky locations appear here after edits accumulate.'),
        metric: `${learningMetrics?.network_quality?.length || 0}`,
        disabled: !weakLocation,
      },
      {
        key: 'fix_gaps',
        title: isRu ? 'Дописать пустые темы' : 'Fill empty topics',
        description: isRu
          ? 'Открыть темы без текста и готовые черновики, которые ещё не стали новостями.'
          : 'Open items without drafts and drafts that are not yet news.',
        metric: `${planOperationalSummary.needsDraft + planOperationalSummary.readyToPublish}`,
        disabled: !currentPlan || planOperationalSummary.needsDraft + planOperationalSummary.readyToPublish === 0,
      },
      {
        key: 'repeat_template',
        title: isRu ? 'Повторить удачную тему' : 'Repeat a winning template',
        description: repeatTemplateCandidate
          ? String(repeatTemplateCandidate.theme || '').trim()
          : (isRu ? 'Нужен хотя бы один готовый черновик и несколько точек.' : 'Needs one ready draft and multiple locations.'),
        metric: `${Math.max(availableItemLocations.length - 2, 0)}`,
        disabled: !repeatTemplateCandidate,
      },
    ];
    return actions;
  }, [
    allowedHorizons,
    availableItemLocations.length,
    currentPlan,
    generating,
    isRu,
    learningMetrics?.network_quality,
    loading,
    locationWeekFocusSummary,
    planOperationalSummary.needsDraft,
    planOperationalSummary.readyToPublish,
    repeatTemplateCandidate,
    selectedScopeOption,
    visibleItems.length,
  ]);
  const operatorQualityInsights = useMemo(() => {
    const insights: OperatorInsight[] = [];
    for (const item of learningMetrics?.quality_insights || []) {
      const textRu = String(item.text_ru || '').trim();
      const textEn = String(item.text_en || '').trim();
      if (!textRu && !textEn) continue;
      insights.push({
        key: `metric:${item.kind}:${textRu}:${textEn}`,
        textRu,
        textEn,
      });
    }
    const weakSlice = networkOperatingSlices.find((item) => Number(item.riskScore || 0) >= 35);
    if (weakSlice) {
      insights.push({
        key: `network:${weakSlice.key}`,
        textRu: `${weakSlice.label}: точка требует внимания. ${weakSlice.recommendation}`,
        textEn: `${weakSlice.label}: this location needs attention. ${weakSlice.recommendation}`,
      });
    }
    if (planOperationalSummary.needsDraft > 0) {
      insights.push({
        key: 'plan:no-draft',
        textRu: `В плане ${planOperationalSummary.needsDraft} тем без текста. Начните с них, иначе план останется календарём идей, а не публикациями.`,
        textEn: `${planOperationalSummary.needsDraft} plan items have no draft. Start there or the plan stays a calendar of ideas, not publications.`,
      });
    }
    if (planOperationalSummary.readyToPublish > 0) {
      insights.push({
        key: 'plan:ready',
        textRu: `${planOperationalSummary.readyToPublish} черновиков уже готовы к новости. Это самый быстрый путь к видимой активности в карточках.`,
        textEn: `${planOperationalSummary.readyToPublish} drafts are ready to become news. This is the fastest path to visible listing activity.`,
      });
    }
    if (Number(learningMetrics?.summary?.edited_before_accept_pct || 0) >= 35) {
      insights.push({
        key: 'quality:edited-before-accept',
        textRu: 'Черновики часто правят перед публикацией. Значит генератору нужны более конкретные услуги, SEO-сценарии или примеры удачных тем.',
        textEn: 'Drafts are often edited before publishing. The generator needs more concrete services, SEO scenarios, or examples of good topics.',
      });
    }
    if (missingInputs.includes('seo_keywords')) {
      insights.push({
        key: 'input:seo',
        textRu: 'Плану не хватает SEO-ключей по реальному спросу. Без них темы слабее закрывают поисковые сценарии на картах.',
        textEn: 'The plan lacks real-demand SEO keywords. Without them, topics cover map search scenarios less precisely.',
      });
    }
    if (missingInputs.includes('services')) {
      insights.push({
        key: 'input:services',
        textRu: networkHasSearchPlanFoundation
          ? 'Для сети уже есть карты и SEO-спрос. Следующее усиление — добавить меню, товары или ключевые услуги, чтобы публикации были не только поисковыми, но и коммерческими.'
          : 'Плану не хватает списка услуг. Добавьте услуги, чтобы новости были не общими, а привязанными к конкретному выбору клиента.',
        textEn: networkHasSearchPlanFoundation
          ? 'The network already has map listings and SEO demand. The next upgrade is adding menu items, products, or key services so posts become commercial, not only search-driven.'
          : 'The plan lacks a service list. Add services so news posts are tied to concrete customer choices.',
      });
    }
    if (!context?.sales_signals?.length) {
      insights.push({
        key: 'input:sales',
        textRu: 'В плане пока нет продажных сигналов. Когда появятся продажи/популярные услуги, темы можно будет ранжировать по реальному спросу.',
        textEn: 'There are no sales signals yet. Once sales or popular services appear, topics can be ranked by real demand.',
      });
    }
    if (Number(learningMetrics?.summary?.skipped_total || 0) > 0) {
      insights.push({
        key: 'quality:skipped',
        textRu: `Пропущено тем: ${learningMetrics?.summary?.skipped_total || 0}. Это сигнал, что часть тем слишком абстрактная или неудобная для быстрой публикации.`,
        textEn: `${learningMetrics?.summary?.skipped_total || 0} topics were skipped. That usually means some topics are too abstract or hard to publish quickly.`,
      });
    }
    return insights.slice(0, 4);
  }, [
    context?.sales_signals?.length,
    learningMetrics?.quality_insights,
    learningMetrics?.summary?.skipped_total,
    learningMetrics?.summary?.edited_before_accept_pct,
    missingInputs,
    networkHasSearchPlanFoundation,
    networkOperatingSlices,
    planOperationalSummary.needsDraft,
    planOperationalSummary.readyToPublish,
  ]);

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

  const loadLearningMetrics = async () => {
    if (!businessId) return;
    setMetricsLoading(true);
    try {
      const response = await newAuth.makeRequest(`/content-plans/learning-metrics?business_id=${encodeURIComponent(businessId)}`, {
        method: 'GET',
      });
      setLearningMetrics(response || null);
    } catch {
      setLearningMetrics(null);
    } finally {
      setMetricsLoading(false);
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
    void loadLearningMetrics();
  }, [businessId]);

  useEffect(() => {
    if (!businessId) return;
    if (!selectedScopeKey) return;
    void loadContext(selectedScopeKey);
  }, [selectedScopeKey, businessId]);

  useEffect(() => {
    if (!scopeOptions.length) return;
    if (contentMode === 'network' && networkScopeOption) {
      const nextKey = `${networkScopeOption.scope_type}:${networkScopeOption.scope_target_id}`;
      if (selectedScopeKey !== nextKey) setSelectedScopeKey(nextKey);
      return;
    }
    if (contentMode === 'point' && pointScopeOption) {
      const nextKey = `${pointScopeOption.scope_type}:${pointScopeOption.scope_target_id}`;
      if (selectedScopeKey !== nextKey) setSelectedScopeKey(nextKey);
    }
  }, [contentMode, networkScopeOption, pointScopeOption, scopeOptions.length, selectedScopeKey]);

  useEffect(() => {
    if (availableWeeks.some((week) => week.key === selectedWeekKey)) return;
    setSelectedWeekKey('all');
  }, [availableWeeks, selectedWeekKey]);

  useEffect(() => {
    if (visibleItems.length === 0) {
      if (selectedQueueItemId) setSelectedQueueItemId('');
      return;
    }
    if (selectedQueueItemId && visibleItems.some((item) => item.id === selectedQueueItemId)) return;
    setSelectedQueueItemId(visibleItems[0].id);
  }, [selectedQueueItemId, visibleItems]);

  useEffect(() => {
    setSelectedItemIds((prev) => {
      const visibleIds = new Set(visibleItems.map((item) => item.id));
      const next: Record<string, boolean> = {};
      for (const [itemId, isSelected] of Object.entries(prev)) {
        if (isSelected && visibleIds.has(itemId)) next[itemId] = true;
      }
      return next;
    });
  }, [visibleItems]);

  useEffect(() => {
    if (!businessId) return;
    const stored = _readStoredPreferences(businessId);
    if (!stored) return;
    if (_isValidItemFilterKey(stored.selectedItemFilter)) {
      setSelectedItemFilter(stored.selectedItemFilter);
    }
    if (_isValidSignalFilterKey(stored.selectedSignalFilter)) {
      setSelectedSignalFilter(stored.selectedSignalFilter);
    }
    if (typeof stored.selectedPlanTargetKey === 'string' && stored.selectedPlanTargetKey.trim()) {
      setSelectedPlanTargetKey(stored.selectedPlanTargetKey);
    }
    if (typeof stored.selectedItemLocationKey === 'string' && stored.selectedItemLocationKey.trim()) {
      setSelectedItemLocationKey(stored.selectedItemLocationKey);
    }
    if (typeof stored.selectedWeekKey === 'string' && stored.selectedWeekKey.trim()) {
      setSelectedWeekKey(stored.selectedWeekKey);
    }
    if (typeof stored.lastFocusLocationKey === 'string' && stored.lastFocusLocationKey.trim()) {
      setLastFocusLocationKey(stored.lastFocusLocationKey);
    }
    if (typeof stored.lastFocusWeekKey === 'string' && stored.lastFocusWeekKey.trim()) {
      setLastFocusWeekKey(stored.lastFocusWeekKey);
    }
    if (stored.sortMode === 'priority' || stored.sortMode === 'date') {
      setSortMode(stored.sortMode);
    }
    if (_isValidViewPresetKey(stored.selectedViewPreset)) {
      setSelectedViewPreset(stored.selectedViewPreset);
    }
  }, [businessId]);

  useEffect(() => {
    if (selectedViewPreset !== 'focus') return;
    if (selectedItemLocationKey !== 'all') {
      setLastFocusLocationKey(selectedItemLocationKey);
    }
    if (selectedWeekKey !== 'all') {
      setLastFocusWeekKey(selectedWeekKey);
    }
  }, [selectedViewPreset, selectedItemLocationKey, selectedWeekKey]);

  useEffect(() => {
    setSelectedViewPreset(_inferViewPresetKey({
      selectedItemFilter,
      selectedSignalFilter,
      selectedPlanTargetKey,
      selectedItemLocationKey,
      selectedWeekKey,
      sortMode,
    }));
  }, [
    selectedItemFilter,
    selectedSignalFilter,
    selectedPlanTargetKey,
    selectedItemLocationKey,
    selectedWeekKey,
    sortMode,
  ]);

  useEffect(() => {
    if (!businessId) return;
    _writeStoredPreferences(businessId, {
      selectedViewPreset,
      lastFocusLocationKey,
      lastFocusWeekKey,
      selectedItemFilter,
      selectedSignalFilter,
      selectedPlanTargetKey,
      selectedItemLocationKey,
      selectedWeekKey,
      sortMode,
    });
  }, [
    businessId,
    selectedViewPreset,
    lastFocusLocationKey,
    lastFocusWeekKey,
    selectedItemFilter,
    selectedSignalFilter,
    selectedPlanTargetKey,
    selectedItemLocationKey,
    selectedWeekKey,
    sortMode,
  ]);

  const toggleMix = (key: ContentMixKey) => {
    setContentMix((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleSelectedItem = (itemId: string) => {
    setSelectedItemIds((prev) => {
      const next = { ...prev };
      if (next[itemId]) {
        delete next[itemId];
      } else {
        next[itemId] = true;
      }
      return next;
    });
  };

  const clearSelectedItems = () => {
    setSelectedItemIds({});
  };

  const generatePlan = async (periodOverride?: string) => {
    if (!businessId || !selectedScopeOption) return;
    setGenerating(true);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/content-plans/generate', {
        method: 'POST',
        body: JSON.stringify({
          business_id: businessId,
          scope_type: selectedScopeOption.scope_type,
          scope_target_id: selectedScopeOption.scope_target_id,
          period_days: Number(periodOverride || selectedPeriod),
          density: selectedDensity,
          content_mix: contentMix,
        }),
      });
      setCurrentPlan(response.plan || null);
      setActiveZone('queue');
      await loadPlans();
      await loadLearningMetrics();
    } catch (generationError) {
      const message = generationError instanceof Error ? generationError.message : (isRu ? 'Не удалось собрать план' : 'Could not generate plan');
      setError(message);
    } finally {
      setGenerating(false);
    }
  };

  const saveItem = async (itemId: string) => {
    setBusyItemId(itemId);
    setActionSummary(null);
    try {
      await persistItemEdits(itemId);
    } finally {
      setBusyItemId('');
    }
  };

  const generateDraft = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/generate-draft`, {
        method: 'POST',
      });
      setCurrentPlan(response.plan || null);
      setDraftEdits((prev) => _removeRecordKeys(prev, [itemId]));
      setRecentGeneratedItemId(itemId);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Черновик сгенерирован для выбранной публикации.',
        text_en: 'Draft generated for the selected item.',
      });
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
    setActionSummary(null);
    try {
      await persistItemEdits(itemId);
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/create-news`, {
        method: 'POST',
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Новость создана из выбранного элемента плана.',
        text_en: 'News item created from the selected plan item.',
      });
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
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let generatedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      const generatedIds: string[] = [];
      for (const item of bulkDraftCandidates) {
        try {
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/generate-draft`, {
            method: 'POST',
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          generatedCount += 1;
          generatedIds.push(item.id);
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      if (generatedIds.length > 0) {
        setDraftEdits((prev) => _removeRecordKeys(prev, generatedIds));
      }
      await loadLearningMetrics();
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: _bulkResultText('drafts', generatedCount, failedCount, true),
        text_en: _bulkResultText('drafts', generatedCount, failedCount, false),
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
      });
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать черновики' : 'Could not generate drafts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runSelectedGenerateDrafts = async () => {
    if (selectedDraftCandidates.length === 0) return;
    setBulkBusyAction('selected-drafts');
    setError('');
    setActionSummary(null);
    try {
      let generatedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      const generatedIds: string[] = [];
      for (const item of selectedDraftCandidates) {
        try {
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/generate-draft`, {
            method: 'POST',
          });
          setCurrentPlan(response.plan || null);
          generatedCount += 1;
          generatedIds.push(item.id);
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      if (generatedIds.length > 0) {
        setDraftEdits((prev) => _removeRecordKeys(prev, generatedIds));
      }
      await loadLearningMetrics();
      clearSelectedItems();
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: _bulkResultText('drafts', generatedCount, failedCount, true),
        text_en: _bulkResultText('drafts', generatedCount, failedCount, false),
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
      });
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать тексты' : 'Could not generate texts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runSelectedCreateNews = () => {
    if (selectedNewsCandidates.length === 0) return;
    setBulkNewsReview({
      key: 'selected',
      titleRu: 'Создать выбранные новости',
      titleEn: 'Create selected news',
      descriptionRu: 'Будут созданы новости только из отмеченных тем. Проверьте выборку перед запуском.',
      descriptionEn: 'News will be created only from selected topics. Review the selection before continuing.',
      items: selectedNewsCandidates,
      busyAction: 'selected-news',
    });
  };

  const runBulkCreateNews = async () => {
    if (bulkNewsCandidates.length === 0) return;
    setBulkNewsReview({
      key: 'filtered',
      titleRu: 'Проверить новости перед созданием',
      titleEn: 'Review news before creating',
      descriptionRu: 'Будут созданы новости только из текущей выборки: с учётом точки, недели и фильтров сверху.',
      descriptionEn: 'News will be created only from the current view: respecting location, week, and filters above.',
      items: bulkNewsCandidates,
      busyAction: 'news',
    });
  };

  const runBulkAutofillDates = async () => {
    if (missingDateCandidates.length === 0) return;
    setBulkBusyAction('autofill-dates');
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let updatedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      for (let index = 0; index < missingDateCandidates.length; index += 1) {
        const item = missingDateCandidates[index];
        try {
          const nextDate = _autoScheduledDate(index);
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}`, {
            method: 'PUT',
            body: JSON.stringify({ scheduled_for: nextDate, status: 'planned' }),
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          setDateEdits((prev) => ({ ...prev, [item.id]: nextDate }));
          updatedCount += 1;
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: `Даты расставлены автоматически: ${updatedCount}${failedCount > 0 ? `, не получилось ${failedCount}` : ''}`,
        text_en: `Dates assigned automatically: ${updatedCount}${failedCount > 0 ? `, failed ${failedCount}` : ''}`,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
      });
    } catch (dateError) {
      const message = dateError instanceof Error ? dateError.message : (isRu ? 'Не удалось расставить даты' : 'Could not assign dates');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const executeBulkNewsReview = async () => {
    const review = bulkNewsReview;
    if (!review || review.items.length === 0) return;
    if (review.focusLocationKey && review.focusWeekKey) {
      applyLocationWeekFocus(review.focusLocationKey, review.focusWeekKey);
    }
    setBulkBusyAction(review.busyAction);
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let createdCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      for (const item of review.items) {
        try {
          await persistItemEdits(item.id);
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/create-news`, {
            method: 'POST',
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          createdCount += 1;
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      await loadLearningMetrics();
      const textRu = _bulkResultText('news', createdCount, failedCount, true);
      const textEn = _bulkResultText('news', createdCount, failedCount, false);
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: review.summaryPrefixRu ? `${review.summaryPrefixRu}: ${textRu}` : textRu,
        text_en: review.summaryPrefixEn ? `${review.summaryPrefixEn}: ${textEn}` : textEn,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
        focusLocationKey: review.focusLocationKey,
        focusWeekKey: review.focusWeekKey,
      });
      setBulkNewsReview(null);
    } catch (publishError) {
      const message = publishError instanceof Error ? publishError.message : (isRu ? 'Не удалось создать новости' : 'Could not create news items');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const executeBulkActionReview = async () => {
    const review = bulkActionReview;
    if (!review || review.items.length === 0) return;
    if (review.focusLocationKey && review.focusWeekKey) {
      applyLocationWeekFocus(review.focusLocationKey, review.focusWeekKey);
    }
    setBulkBusyAction(review.busyAction);
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let processedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      for (const item of review.items) {
        try {
          const payload: Record<string, string> = {};
          if (review.kind === 'skip') {
            payload.status = 'skipped';
          } else {
            payload.scheduled_for = String(review.targetDate || '').slice(0, 10);
            payload.status = 'planned';
          }
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          if (review.kind === 'reschedule') {
            setDateEdits((prev) => ({ ...prev, [item.id]: String(review.targetDate || '').slice(0, 10) }));
          }
          processedCount += 1;
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      await loadLearningMetrics();
      const actionTextRu = review.kind === 'skip'
        ? `пропущено тем ${processedCount}${failedCount > 0 ? `, не получилось ${failedCount}` : ''}`
        : `перенесено на ${String(review.targetDate || '').slice(0, 10)} тем ${processedCount}${failedCount > 0 ? `, не получилось ${failedCount}` : ''}`;
      const actionTextEn = review.kind === 'skip'
        ? `skipped ${processedCount}${failedCount > 0 ? `, failed ${failedCount}` : ''}`
        : `moved to ${String(review.targetDate || '').slice(0, 10)}: ${processedCount}${failedCount > 0 ? `, failed ${failedCount}` : ''}`;
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: review.summaryPrefixRu ? `${review.summaryPrefixRu}: ${actionTextRu}` : actionTextRu,
        text_en: review.summaryPrefixEn ? `${review.summaryPrefixEn}: ${actionTextEn}` : actionTextEn,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
        focusLocationKey: review.focusLocationKey,
        focusWeekKey: review.kind === 'reschedule' && review.targetDate ? _weekBucketKey(review.targetDate) : review.focusWeekKey,
      });
      setBulkActionReview(null);
    } catch (bulkError) {
      const message = bulkError instanceof Error ? bulkError.message : (isRu ? 'Не удалось выполнить массовое действие' : 'Could not run bulk action');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const resetViewState = () => {
    setSelectedViewPreset('overview');
    setSelectedItemFilter('all');
    setSelectedSignalFilter('all');
    setSelectedPlanTargetKey('all');
    setSelectedItemLocationKey('all');
    setSelectedWeekKey('all');
    setSortMode('priority');
  };

  const applyViewPreset = (preset: ViewPresetKey) => {
    if (preset === 'overview') {
      resetViewState();
      return;
    }
    setSelectedViewPreset(preset);
    setSelectedSignalFilter('all');
    setSelectedItemLocationKey('all');
    setSelectedWeekKey('all');
    if (preset === 'urgent') {
      setSelectedItemFilter('urgent');
      setSortMode('priority');
      return;
    }
    if (preset === 'ready') {
      setSelectedItemFilter('has_draft');
      setSortMode('priority');
      return;
    }
    if (preset === 'focus') {
      setSelectedItemFilter('urgent');
      setSortMode('priority');
      if (lastFocusLocationKey !== 'all') {
        setSelectedItemLocationKey(lastFocusLocationKey);
      }
      if (lastFocusWeekKey !== 'all') {
        setSelectedWeekKey(lastFocusWeekKey);
      }
      return;
    }
    setSelectedItemFilter('news_created');
    setSortMode('date');
  };

  const applyLocationWeekFocus = (locationKey: string, weekKey: string) => {
    setSelectedViewPreset('focus');
    setLastFocusLocationKey(locationKey);
    setLastFocusWeekKey(weekKey);
    setSelectedItemFilter('urgent');
    setSelectedSignalFilter('all');
    setSelectedItemLocationKey(locationKey);
    setSelectedWeekKey(weekKey);
    setSortMode('priority');
  };

  const getLocationWeekFocusItems = (locationKey: string, weekKey: string) => (
    (currentPlan?.items || []).filter((item) => {
      const itemLocationKey = String(item.location_scope || item.business_id || '').trim();
      return itemLocationKey === locationKey && _weekBucketKey(item.scheduled_for) === weekKey;
    })
  );

  const getDuplicateTargetLocationOptions = (item: PlanItem) => {
    const sourceLocationKey = String(item.location_scope || item.business_id || '').trim();
    return availableItemLocations.filter((location) => location.key !== 'all' && location.key !== sourceLocationKey);
  };

  const openDuplicateTargetPicker = (item: PlanItem) => {
    const targetOptions = getDuplicateTargetLocationOptions(item);
    setExpandedDuplicateItemId((prev) => (prev === item.id ? '' : item.id));
    setDuplicateDateOverrides((prev) => ({
      ...prev,
      [item.id]: prev[item.id] || String(item.scheduled_for || '').slice(0, 10) || _shiftIsoDate('', 7),
    }));
    setDuplicateTargetSelections((prev) => ({
      ...prev,
      [item.id]: prev[item.id]?.length ? prev[item.id] : targetOptions.map((location) => location.key),
    }));
  };

  const toggleDuplicateTargetLocation = (itemId: string, locationKey: string) => {
    setDuplicateTargetSelections((prev) => {
      const current = Array.isArray(prev[itemId]) ? prev[itemId] : [];
      const exists = current.includes(locationKey);
      return {
        ...prev,
        [itemId]: exists
          ? current.filter((key) => key !== locationKey)
          : [...current, locationKey],
      };
    });
  };

  const runLocationWeekFocusDrafts = async (locationKey: string, weekKey: string) => {
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => !String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    setBulkBusyAction(`focus-drafts:${locationKey}:${weekKey}`);
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let generatedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      const generatedIds: string[] = [];
      for (const item of focusCandidates) {
        try {
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/generate-draft`, {
            method: 'POST',
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          generatedCount += 1;
          generatedIds.push(item.id);
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      if (generatedIds.length > 0) {
        setDraftEdits((prev) => _removeRecordKeys(prev, generatedIds));
      }
      await loadLearningMetrics();
      const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
      const weekLabel = _weekBucketLabel(weekKey, isRu);
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: `${locationLabel} · ${weekLabel}: ${_bulkResultText('drafts', generatedCount, failedCount, true)}`,
        text_en: `${locationLabel} · ${weekLabel}: ${_bulkResultText('drafts', generatedCount, failedCount, false)}`,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
        focusLocationKey: locationKey,
        focusWeekKey: weekKey,
      });
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать черновики' : 'Could not generate drafts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runLocationWeekFocusNews = async (locationKey: string, weekKey: string) => {
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
    const weekLabel = _weekBucketLabel(weekKey, isRu);
    setBulkNewsReview({
      key: `focus:${locationKey}:${weekKey}`,
      titleRu: 'Проверить новости по срезу',
      titleEn: 'Review slice news',
      descriptionRu: `${locationLabel} · ${weekLabel}. Будут созданы новости только из готовых черновиков этого среза.`,
      descriptionEn: `${locationLabel} · ${weekLabel}. News will be created only from ready drafts in this slice.`,
      items: focusCandidates,
      busyAction: `focus-news:${locationKey}:${weekKey}`,
      summaryPrefixRu: `${locationLabel} · ${weekLabel}`,
      summaryPrefixEn: `${locationLabel} · ${weekLabel}`,
      focusLocationKey: locationKey,
      focusWeekKey: weekKey,
    });
  };

  const runLocationWeekSkip = async (locationKey: string, weekKey: string) => {
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => String(item.status || '').trim() !== 'skipped' && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    setError('');
    setActionSummary(null);
    const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
    const weekLabel = _weekBucketLabel(weekKey, isRu);
    setBulkActionReview({
      key: `skip:${locationKey}:${weekKey}`,
      kind: 'skip',
      titleRu: 'Проверить пропуск пачки',
      titleEn: 'Review batch skip',
      descriptionRu: `${locationLabel} · ${weekLabel}. Эти темы будут помечены как пропущенные и уйдут из рабочего среза.`,
      descriptionEn: `${locationLabel} · ${weekLabel}. These items will be marked as skipped and removed from the active slice.`,
      confirmLabelRu: 'Подтвердить пропуск',
      confirmLabelEn: 'Confirm skip',
      items: focusCandidates,
      busyAction: `focus-skip:${locationKey}:${weekKey}`,
      summaryPrefixRu: `${locationLabel} · ${weekLabel}`,
      summaryPrefixEn: `${locationLabel} · ${weekLabel}`,
      focusLocationKey: locationKey,
      focusWeekKey: weekKey,
    });
  };

  const runLocationWeekReschedule = async (locationKey: string, weekKey: string, daysDelta: number) => {
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => String(item.status || '').trim() !== 'skipped' && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    setBulkBusyAction(`focus-reschedule:${locationKey}:${weekKey}`);
    setError('');
    setActionSummary(null);
    try {
      let movedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      for (const item of focusCandidates) {
        try {
          const nextDate = _shiftIsoDate(item.scheduled_for, daysDelta);
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}`, {
            method: 'PUT',
            body: JSON.stringify({ scheduled_for: nextDate, status: 'planned' }),
          });
          setCurrentPlan(response.plan || null);
          movedCount += 1;
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      await loadLearningMetrics();
      const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
      const weekLabel = _weekBucketLabel(weekKey, isRu);
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: `${locationLabel} · ${weekLabel}: перенесено тем ${movedCount}${failedCount > 0 ? `, не получилось ${failedCount}` : ''}`,
        text_en: `${locationLabel} · ${weekLabel}: rescheduled ${movedCount}${failedCount > 0 ? `, failed ${failedCount}` : ''}`,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
        focusLocationKey: locationKey,
        focusWeekKey: _weekBucketKey(_shiftIsoDate(weekKey, daysDelta)),
      });
    } catch (rescheduleError) {
      const message = rescheduleError instanceof Error ? rescheduleError.message : (isRu ? 'Не удалось перенести срез' : 'Could not reschedule slice');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runLocationWeekRescheduleToDate = async (locationKey: string, weekKey: string, targetDate: string) => {
    const normalizedTargetDate = String(targetDate || '').slice(0, 10);
    if (!normalizedTargetDate) {
      setError(isRu ? 'Выберите дату переноса' : 'Select a target date');
      return;
    }
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => String(item.status || '').trim() !== 'skipped' && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    setError('');
    setActionSummary(null);
    const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
    const weekLabel = _weekBucketLabel(weekKey, isRu);
    setBulkActionReview({
      key: `reschedule:${locationKey}:${weekKey}:${normalizedTargetDate}`,
      kind: 'reschedule',
      titleRu: 'Проверить перенос пачки',
      titleEn: 'Review batch move',
      descriptionRu: `${locationLabel} · ${weekLabel}. Все элементы среза будут перенесены на ${normalizedTargetDate}.`,
      descriptionEn: `${locationLabel} · ${weekLabel}. All slice items will be moved to ${normalizedTargetDate}.`,
      confirmLabelRu: 'Подтвердить перенос',
      confirmLabelEn: 'Confirm move',
      items: focusCandidates,
      busyAction: `focus-reschedule-date:${locationKey}:${weekKey}`,
      targetDate: normalizedTargetDate,
      summaryPrefixRu: `${locationLabel} · ${weekLabel}`,
      summaryPrefixEn: `${locationLabel} · ${weekLabel}`,
      focusLocationKey: locationKey,
      focusWeekKey: weekKey,
    });
  };

  const runItemSkip = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}`, {
        method: 'PUT',
        body: JSON.stringify({ status: 'skipped' }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Элемент помечен как пропущенный.',
        text_en: 'The item was marked as skipped.',
      });
    } catch (skipError) {
      const message = skipError instanceof Error ? skipError.message : (isRu ? 'Не удалось пропустить элемент' : 'Could not skip item');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runItemReschedule = async (itemId: string, scheduledFor: string, daysDelta: number) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const nextDate = _shiftIsoDate(scheduledFor, daysDelta);
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}`, {
        method: 'PUT',
        body: JSON.stringify({ scheduled_for: nextDate, status: 'planned' }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setDateEdits((prev) => ({ ...prev, [itemId]: nextDate }));
      setActionSummary({
        tone: 'success',
        text_ru: `Элемент перенесён на ${nextDate}.`,
        text_en: `The item was rescheduled to ${nextDate}.`,
      });
    } catch (rescheduleError) {
      const message = rescheduleError instanceof Error ? rescheduleError.message : (isRu ? 'Не удалось перенести элемент' : 'Could not reschedule item');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runItemDuplicate = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/duplicate`, {
        method: 'POST',
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Элемент продублирован и добавлен в план.',
        text_en: 'The item was duplicated and added to the plan.',
      });
    } catch (duplicateError) {
      const message = duplicateError instanceof Error ? duplicateError.message : (isRu ? 'Не удалось дублировать элемент' : 'Could not duplicate item');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runItemDuplicateToOtherLocations = async (item: PlanItem) => {
    const sourceLocationKey = String(item.location_scope || item.business_id || '').trim();
    const targetLocationScopes = availableItemLocations
      .map((location) => location.key)
      .filter((key) => key !== 'all' && key !== sourceLocationKey);
    if (targetLocationScopes.length === 0) return;
    setBusyItemId(item.id);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/duplicate-to-locations`, {
        method: 'POST',
        body: JSON.stringify({
          target_location_scopes: targetLocationScopes,
          scheduled_for: item.scheduled_for,
        }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: `Шаблон размножен на другие точки: ${targetLocationScopes.length}.`,
        text_en: `Template duplicated to other locations: ${targetLocationScopes.length}.`,
      });
    } catch (duplicateError) {
      const message = duplicateError instanceof Error ? duplicateError.message : (isRu ? 'Не удалось размножить шаблон' : 'Could not duplicate template');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runItemDuplicateToSelectedLocations = async (item: PlanItem) => {
    const targetLocationScopes = (duplicateTargetSelections[item.id] || [])
      .map((key) => String(key || '').trim())
      .filter(Boolean);
    if (targetLocationScopes.length === 0) {
      setError(isRu ? 'Выберите хотя бы одну точку для дублирования' : 'Select at least one target location');
      return;
    }
    setBusyItemId(item.id);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/duplicate-to-locations`, {
        method: 'POST',
        body: JSON.stringify({
          target_location_scopes: targetLocationScopes,
          scheduled_for: duplicateDateOverrides[item.id] || item.scheduled_for,
        }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setExpandedDuplicateItemId('');
      setActionSummary({
        tone: 'success',
        text_ru: `Шаблон размножен на выбранные точки: ${targetLocationScopes.length}.`,
        text_en: `Template duplicated to selected locations: ${targetLocationScopes.length}.`,
      });
    } catch (duplicateError) {
      const message = duplicateError instanceof Error ? duplicateError.message : (isRu ? 'Не удалось размножить шаблон' : 'Could not duplicate template');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runQuickAction = (actionKey: QuickActionKey) => {
    if (actionKey === 'create_month_plan') {
      setSelectedPeriod('30');
      void generatePlan('30');
      return;
    }
    if (actionKey === 'open_week') {
      const focusSlice = locationWeekFocusSummary[0];
      if (focusSlice) {
        applyLocationWeekFocus(focusSlice.locationKey, focusSlice.weekKey);
        return;
      }
      if (availableWeeks[1]) {
        setSelectedWeekKey(availableWeeks[1].key);
      }
      return;
    }
    if (actionKey === 'weak_locations') {
      const weakLocation = (learningMetrics?.network_quality || [])[0];
      const weakLocationKey = String(weakLocation?.key || '').trim();
      if (weakLocationKey) {
        setSelectedViewPreset('focus');
        setSelectedItemFilter('urgent');
        setSelectedItemLocationKey(weakLocationKey);
        setSelectedWeekKey('all');
        setSortMode('priority');
      }
      return;
    }
    if (actionKey === 'fix_gaps') {
      applyViewPreset('urgent');
      return;
    }
    if (repeatTemplateCandidate) {
      void runItemDuplicateToOtherLocations(repeatTemplateCandidate);
    }
  };

  const contentPlanZones: Array<{ key: ContentPlanZone; titleRu: string; titleEn: string; hintRu: string; hintEn: string }> = [
    { key: 'overview', titleRu: 'Обзор', titleEn: 'Overview', hintRu: 'Состояние и следующий шаг', hintEn: 'Status and next step' },
    { key: 'plan', titleRu: 'План', titleEn: 'Plan', hintRu: 'Точка, сеть и источники', hintEn: 'Location, network, inputs' },
    { key: 'queue', titleRu: 'Очередь', titleEn: 'Queue', hintRu: 'Темы без лишних деталей', hintEn: 'Topics without noise' },
    { key: 'editor', titleRu: 'Редактор', titleEn: 'Editor', hintRu: 'Одна тема до новости', hintEn: 'One topic to news' },
  ];

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
              {isRu ? 'Новости, сторис и контент-план' : 'News, stories, and content plan'}
            </h4>
            <p className="max-w-3xl text-sm leading-6 text-slate-600">
              {isRu
                ? 'Один рабочий экран: понять состояние, собрать план, разобрать очередь и довести выбранную тему до новости.'
                : 'One workspace: understand status, build the plan, work the queue, and turn one selected topic into news.'}
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

      <div className="rounded-[28px] border border-slate-200 bg-white p-2 shadow-sm">
        <div className="grid gap-2 md:grid-cols-4">
          {contentPlanZones.map((zone) => (
            <button
              key={zone.key}
              type="button"
              onClick={() => setActiveZone(zone.key)}
              className={[
                'rounded-3xl px-4 py-4 text-left transition-colors',
                activeZone === zone.key
                  ? 'bg-slate-950 text-white shadow-sm'
                  : 'bg-transparent text-slate-600 hover:bg-slate-50',
              ].join(' ')}
            >
              <div className="text-lg font-semibold">{isRu ? zone.titleRu : zone.titleEn}</div>
              <div className={['mt-1 text-sm leading-5', activeZone === zone.key ? 'text-slate-300' : 'text-slate-500'].join(' ')}>
                {isRu ? zone.hintRu : zone.hintEn}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-950">
            {isRu ? 'Режим работы' : 'Mode'}
          </div>
          <div className="text-sm text-slate-500">
            {isRu
              ? 'В точке показываем только локальную работу. В сети — операционный обзор по точкам.'
              : 'Location mode shows local work. Network mode shows the operating view across locations.'}
          </div>
        </div>
        <div className="grid w-full grid-cols-2 rounded-2xl bg-slate-100 p-1 sm:w-[260px]">
          <button
            type="button"
            onClick={() => setContentMode('point')}
            className={[
              'rounded-xl px-4 py-2 text-sm font-medium transition-colors',
              contentMode === 'point' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950',
            ].join(' ')}
          >
            {isRu ? 'Точка' : 'Location'}
          </button>
          <button
            type="button"
            onClick={() => setContentMode('network')}
            disabled={!isNetworkContext}
            className={[
              'rounded-xl px-4 py-2 text-sm font-medium transition-colors',
              contentMode === 'network' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950',
              !isNetworkContext ? 'cursor-not-allowed opacity-50' : '',
            ].join(' ')}
          >
            {isRu ? 'Сеть' : 'Network'}
          </button>
        </div>
      </div>

      <div className={activeZone === 'overview' ? 'space-y-6' : 'hidden'}>
        <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                {isRu ? 'Обзор' : 'Overview'}
              </div>
              <div className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
                {currentPlan?.items?.length
                  ? (planOperationalSummary.needsDraft > 0
                    ? (isRu ? 'Сначала допишите пустые темы' : 'Start by filling empty topics')
                    : planOperationalSummary.readyToPublish > 0
                      ? (isRu ? 'Готовые тексты можно превратить в новости' : 'Ready texts can become news')
                      : (isRu ? 'План выглядит спокойно' : 'The plan looks calm'))
                  : (isRu ? 'Соберите первый план публикаций' : 'Build the first content plan')}
              </div>
              <div className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                {isRu
                  ? 'Здесь только главное: состояние плана, слабое место и одно действие, которое двигает работу дальше.'
                  : 'Only the essentials: plan status, weak spot, and one action that moves the work forward.'}
              </div>
            </div>
            {!currentPlan?.items?.length ? (
              <Button onClick={() => setActiveZone('plan')} disabled={loading}>
                <Sparkles className="mr-2 h-4 w-4" />
                {isRu ? 'Перейти к плану' : 'Go to plan'}
              </Button>
            ) : planOperationalSummary.needsDraft > 0 ? (
              <Button onClick={() => { applyViewPreset('urgent'); setActiveZone('queue'); }}>
                {isRu ? 'Дописать пустые темы' : 'Fill empty topics'}
              </Button>
            ) : planOperationalSummary.readyToPublish > 0 ? (
              <Button onClick={() => { applyViewPreset('ready'); setActiveZone('queue'); }}>
                {isRu ? 'Открыть готовые к публикации' : 'Open ready to publish'}
              </Button>
            ) : (
              <Button onClick={() => setActiveZone('plan')}>
                {isRu ? 'Собрать новый план' : 'Build a new plan'}
              </Button>
            )}
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-5">
            <div className="rounded-2xl bg-emerald-50 px-4 py-4">
              <div className="text-2xl font-semibold text-emerald-950">{planOperationalSummary.readyToPublish}</div>
              <div className="mt-1 text-sm text-emerald-800">{isRu ? 'Готово к публикации' : 'Ready to publish'}</div>
            </div>
            <div className="rounded-2xl bg-amber-50 px-4 py-4">
              <div className="text-2xl font-semibold text-amber-950">{planOperationalSummary.needsDraft}</div>
              <div className="mt-1 text-sm text-amber-800">{isRu ? 'Без текста' : 'No text'}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-4">
              <div className="text-2xl font-semibold text-slate-950">{planOperationalSummary.published}</div>
              <div className="mt-1 text-sm text-slate-600">{isRu ? 'Создано' : 'Created'}</div>
            </div>
            <div className="rounded-2xl bg-rose-50 px-4 py-4">
              <div className="text-2xl font-semibold text-rose-950">{Number(overviewRiskScore || 0).toFixed(0)}</div>
              <div className="mt-1 text-sm text-rose-800">{isRu ? 'Риск / слабые точки' : 'Risk / weak spots'}</div>
            </div>
            <div className="rounded-2xl bg-blue-50 px-4 py-4">
              <div className="text-2xl font-semibold text-blue-950">{planOperationalSummary.total}</div>
              <div className="mt-1 text-sm text-blue-800">{isRu ? 'Тем в плане' : 'Plan topics'}</div>
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <button
              type="button"
              onClick={() => setShowLearningDetails((prev) => !prev)}
              className="flex w-full items-center justify-between gap-3 text-left text-sm font-semibold text-slate-900"
            >
              <span>{isRu ? 'Что система уже поняла' : 'What the system already learned'}</span>
              <span className="text-xs text-slate-500">{showLearningDetails ? (isRu ? 'Скрыть' : 'Hide') : (isRu ? 'Показать' : 'Show')}</span>
            </button>
            {showLearningDetails ? (
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                {(operatorQualityInsights.length > 0 ? operatorQualityInsights : [{
                  key: 'empty-learning',
                  textRu: 'Пока мало истории. После публикаций здесь появятся подсказки по темам и источникам.',
                  textEn: 'There is not enough history yet. Topic and source hints will appear after publications.',
                }]).map((item) => (
                  <div key={item.key} className="rounded-xl bg-white px-3 py-2 text-sm leading-6 text-slate-700">
                    {isRu ? item.textRu : item.textEn}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className={activeZone === 'plan' ? 'space-y-6' : 'hidden'}>
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
        <div
          className={[
            'rounded-2xl border px-5 py-4 text-sm',
            networkHasSearchPlanFoundation
              ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
              : 'border-amber-200 bg-amber-50 text-amber-950',
          ].join(' ')}
        >
          <div className="font-semibold">
            {networkHasSearchPlanFoundation
              ? (isRu ? 'Сеть готова для поискового контент-плана' : 'The network is ready for a search-driven content plan')
              : (isRu ? 'План пока строится не на полном наборе данных' : 'The plan is not yet using the full data set')}
          </div>
          <div
            className={[
              'mt-1 leading-6',
              networkHasSearchPlanFoundation ? 'text-emerald-900/90' : 'text-amber-900/90',
            ].join(' ')}
          >
            {networkHasSearchPlanFoundation
              ? (isRu
                ? `Есть ${mapLinksCount} ссылок на карты и ${seoKeywordsCount} SEO-ключей. Можно строить план по спросу; меню, товары или услуги добавят темам коммерческую конкретику.`
                : `There are ${mapLinksCount} map listings and ${seoKeywordsCount} SEO keywords. You can build demand-driven posts now; menu items, products, or services will make topics more commercial.`)
              : (isRu
                ? 'Сейчас контент-план опирается в основном на аудит и сезонные поводы. Чтобы получить темы по реальному спросу, добавьте карту и услуги.'
                : 'Right now the plan relies mostly on audit signals and seasonal prompts. Add a map listing and services to ground it in real demand.')}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {missingInputs.includes('map_links') ? (
              <span className="rounded-full border border-amber-300 bg-white/80 px-3 py-1 text-xs font-medium text-amber-800">
                {isRu ? 'Нет ссылки на карту' : 'No map listing yet'}
              </span>
            ) : null}
            {missingInputs.includes('services') ? (
              <span
                className={[
                  'rounded-full border bg-white/80 px-3 py-1 text-xs font-medium',
                  networkHasSearchPlanFoundation
                    ? 'border-emerald-300 text-emerald-800'
                    : 'border-amber-300 text-amber-800',
                ].join(' ')}
              >
                {isNetworkContext
                  ? (isRu ? 'Нет меню, товаров или услуг' : 'No menu, products, or services yet')
                  : (isRu ? 'Нет услуг в карточке' : 'No services yet')}
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
                className={[
                  'bg-white',
                  networkHasSearchPlanFoundation
                    ? 'border-emerald-300 text-emerald-900 hover:bg-emerald-100'
                    : 'border-amber-300 text-amber-900 hover:bg-amber-100',
                ].join(' ')}
                onClick={() => navigate('/dashboard/card?tab=services')}
              >
                {isNetworkContext
                  ? (isRu ? 'Добавить меню/услуги' : 'Add menu/services')
                  : (isRu ? 'Добавить услуги' : 'Add services')}
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4">
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Что сделать сейчас' : 'What to do now'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {currentPlan?.items?.length
                ? (isRu ? 'Откройте неделю или точку, а не весь план сразу' : 'Open a week or location instead of the whole plan')
                : (isRu ? 'Соберите первый план публикаций' : 'Build the first publication plan')}
            </div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              {isRu
                ? 'Основное действие сверху. Источники, плотность и тонкие настройки спрятаны, чтобы экран не начинался с перегруза.'
                : 'The primary action stays on top. Sources, density, and detailed controls are tucked away to reduce first-screen noise.'}
            </div>
          </div>
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

            {showPlanSetupDetails ? (
              <>
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
              </>
            ) : null}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button onClick={() => { void generatePlan(); }} disabled={generating || loading || !selectedScopeOption}>
              <Sparkles className="mr-2 h-4 w-4" />
              {generating
                ? (isRu ? 'Собираем план...' : 'Building plan...')
                : (isRu ? 'Собрать план' : 'Build plan')}
            </Button>
            <Button variant="outline" onClick={() => { void loadContext(); void loadPlans(); }} disabled={loading}>
              <Wand2 className="mr-2 h-4 w-4" />
              {isRu ? 'Обновить контекст' : 'Refresh context'}
            </Button>
            <button
              type="button"
              onClick={() => setShowPlanSetupDetails((prev) => !prev)}
              className="rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {showPlanSetupDetails
                ? (isRu ? 'Скрыть настройки' : 'Hide settings')
                : (isRu ? 'Настроить источники' : 'Tune sources')}
            </button>
          </div>

          {error ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                {isRu ? 'Качество данных' : 'Data quality'}
              </div>
              <div className="mt-1 text-lg font-semibold text-slate-950">
                {readiness?.is_grounded_for_search || networkHasSearchPlanFoundation
                  ? (isRu ? 'Данных достаточно для плана' : 'Enough data for planning')
                  : (isRu ? 'Плану не хватает источников' : 'The plan needs more inputs')}
              </div>
              {networkHasSearchPlanFoundation ? (
                <div className="mt-1 text-sm leading-6 text-slate-600">
                  {isRu
                    ? 'Для сети уже есть поисковый фундамент. Услуги и товары нужны как следующий слой конкретики.'
                    : 'The network already has a search foundation. Services and products are the next layer of specificity.'}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => setShowContextDetails((prev) => !prev)}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {showContextDetails ? (isRu ? 'Скрыть' : 'Hide') : (isRu ? 'Подробнее' : 'Details')}
            </button>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-sm text-slate-700">
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{mapLinksCount}</div>
              <div className="text-xs text-slate-500">{isNetworkContext ? (isRu ? 'ссылок на карты' : 'map links') : (isRu ? 'карты' : 'maps')}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{servicesCount}</div>
              <div className="text-xs text-slate-500">{isNetworkContext ? (isRu ? 'меню/услуг' : 'menu/services') : (isRu ? 'услуг' : 'services')}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{seoKeywordsCount}</div>
              <div className="text-xs text-slate-500">{isRu ? 'SEO' : 'SEO'}</div>
            </div>
          </div>
          {showContextDetails ? (
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            {isNetworkContext ? (
              <div>
                <div className="font-semibold text-slate-900">{isRu ? 'Режим сети' : 'Network mode'}</div>
                <div>
                  {context?.scope?.network?.has_parent_scope
                    ? `${isRu ? 'Точек в сети' : 'Locations in network'}: ${networkLocationsCount}`
                    : (isRu ? 'План строится по текущему бизнесу.' : 'Planning uses the current business.')}
                </div>
              </div>
            ) : null}
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Ссылки на карты' : 'Map listings'}</div>
              <div>{mapLinksCount}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isNetworkContext ? (isRu ? 'Меню, товары или услуги' : 'Menu, products, or services') : (isRu ? 'Услуги' : 'Services')}</div>
              <div>{servicesCount}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'SEO-ключи' : 'SEO keywords'}</div>
              <div>{seoKeywordsCount}</div>
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
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Качество плана' : 'Plan quality'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {isRu ? 'Что система уже поняла по работе с темами' : 'What the system learned from topic work'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowLearningDetails((prev) => !prev)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            {metricsLoading
              ? (isRu ? 'Обновляем...' : 'Refreshing...')
              : showLearningDetails
                ? (isRu ? 'Скрыть метрики' : 'Hide metrics')
                : `${isRu ? 'Показать метрики' : 'Show metrics'} · ${learningMetrics?.window_days || 30} ${isRu ? 'дней' : 'days'}`}
          </button>
        </div>
        {operatorQualityInsights.length > 0 ? (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {operatorQualityInsights.map((item) => (
              <div
                key={item.key}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"
              >
                {isRu ? item.textRu : item.textEn}
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
            {isRu
              ? 'Пока мало истории, чтобы делать выводы. После публикаций и правок здесь появятся подсказки по качеству тем.'
              : 'There is not enough history yet. After edits and publications, quality guidance will appear here.'}
          </div>
        )}
        {showLearningDetails ? (
          <>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Сгенерировано' : 'Generated'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.generated_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Принято' : 'Accepted'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.accepted_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Правили перед публикацией' : 'Edited before accept'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.accepted_edited_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Пропущено' : 'Skipped'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.skipped_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Правки до принятия' : 'Edited before accept'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{Number(learningMetrics?.summary?.edited_before_accept_pct || 0).toFixed(0)}%</div>
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Небольшие правки' : 'Minor edits'}</div>
            <div className="mt-2 text-xl font-semibold text-slate-950">{learningMetrics?.summary?.minor_edit_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Смысловые переписывания' : 'Major rewrites'}</div>
            <div className="mt-2 text-xl font-semibold text-slate-950">{learningMetrics?.summary?.major_rewrite_total || 0}</div>
          </div>
        </div>
        {learningMetrics?.quality_insights && learningMetrics.quality_insights.length > 0 ? (
          <div className="mt-4 space-y-2">
            {learningMetrics.quality_insights.map((item) => (
              <div
                key={`${item.kind}:${item.text_ru || item.text_en}`}
                className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
              >
                {isRu ? item.text_ru : item.text_en}
              </div>
            ))}
          </div>
        ) : null}
        {learningMetrics?.items && learningMetrics.items.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {learningMetrics.items.map((item) => (
              <div
                key={item.capability}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
              >
                {_learningCapabilityLabel(item.capability, isRu)} · {isRu ? 'принято' : 'accepted'} {item.accepted_total} · {isRu ? 'сгенерировано' : 'generated'} {item.generated_total}
              </div>
            ))}
          </div>
        ) : null}
        {(learningMetrics?.source_kind_breakdown && learningMetrics.source_kind_breakdown.length > 0)
          || (learningMetrics?.content_type_breakdown && learningMetrics.content_type_breakdown.length > 0)
          || (learningMetrics?.location_breakdown && learningMetrics.location_breakdown.length > 0) ? (
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по сигналу' : 'Most edited by signal'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.source_kind_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {_sourceKindLabel(item.key, isRu)} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по типу темы' : 'Most edited by content type'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.content_type_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {_contentTypeLabel(item.key, isRu)} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по точке' : 'Most edited by location'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.location_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {String(item.label || item.key || (isRu ? 'Точка' : 'Location'))} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}
        {learningMetrics?.network_quality && learningMetrics.network_quality.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {isRu ? 'Качество по точкам' : 'Quality by location'}
                </div>
                <div className="mt-1 text-sm text-slate-600">
                  {isRu
                    ? 'Показывает, где контент-план чаще требует вмешательства: правки, пропуски, черновики без публикации.'
                    : 'Shows where the content plan needs more operator attention: edits, skips, drafts without publishing.'}
                </div>
              </div>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {learningMetrics.network_quality.slice(0, 3).map((item) => (
                <div key={item.key} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">
                        {String(item.label || item.key || (isRu ? 'Точка' : 'Location'))}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {isRu ? 'Индекс риска' : 'Risk score'} · {Number(item.risk_score || 0).toFixed(0)}
                      </div>
                    </div>
                    <span className={[
                      'rounded-full px-2.5 py-1 text-xs font-medium',
                      Number(item.risk_score || 0) >= 60
                        ? 'bg-red-100 text-red-700'
                        : Number(item.risk_score || 0) >= 30
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-emerald-100 text-emerald-800',
                    ].join(' ')}
                    >
                      {Number(item.risk_score || 0) >= 60
                        ? (isRu ? 'Высокий' : 'High')
                        : Number(item.risk_score || 0) >= 30
                          ? (isRu ? 'Средний' : 'Medium')
                          : (isRu ? 'Норма' : 'Stable')}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Опубликовано' : 'Published'} · {item.accepted_total}
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Правки' : 'Edits'} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Пропуски' : 'Skipped'} · {item.skipped_total}
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Переписывания' : 'Rewrites'} · {item.major_rewrite_total}
                    </span>
                  </div>
                  {item.reasons && item.reasons.length > 0 ? (
                    <div className="mt-3 text-xs leading-5 text-slate-500">
                      {item.reasons.slice(0, 2).map((reason) => _networkQualityReasonLabel(reason, isRu)).join(' · ')}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
          </>
        ) : null}
      </div>

      </div>

      <div className={activeZone === 'queue' || activeZone === 'editor' ? 'rounded-2xl border border-slate-200 bg-white p-5 shadow-sm' : 'hidden'}>
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
          <button
            type="button"
            onClick={() => setShowRecentPlans((prev) => !prev)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            {showRecentPlans ? (isRu ? 'Скрыть' : 'Hide') : (isRu ? 'Показать' : 'Show')}
          </button>
        </div>

        {showRecentPlans && plans.length > 0 ? (
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
            <div className="rounded-[28px] border border-slate-200 bg-slate-950 p-5 text-white shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    {isRu ? 'Что сделать дальше' : 'Next best action'}
                  </div>
                  <div className="mt-2 text-xl font-semibold">
                    {planOperationalSummary.needsDraft > 0
                      ? (isRu ? 'Сначала закройте темы без текста' : 'Start with items without drafts')
                      : planOperationalSummary.readyToPublish > 0
                        ? (isRu ? 'Теперь можно создать новости' : 'Now create news items')
                        : (isRu ? 'План под контролем' : 'Plan is under control')}
                  </div>
                  <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                    {isRu
                      ? 'Это операторский слой: не фильтры ради фильтров, а быстрые сценарии для недели, точки и сети.'
                      : 'This is the operator layer: not filters for their own sake, but fast workflows for week, location, and network.'}
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs text-slate-300 sm:min-w-[320px]">
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.needsDraft}</div>
                    <div>{isRu ? 'без текста' : 'no draft'}</div>
                  </div>
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.readyToPublish}</div>
                    <div>{isRu ? 'к новости' : 'ready'}</div>
                  </div>
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.published}</div>
                    <div>{isRu ? 'создано' : 'created'}</div>
                  </div>
                </div>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                {quickActions.map((action) => (
                  <button
                    key={action.key}
                    type="button"
                    disabled={action.disabled || Boolean(bulkBusyAction) || Boolean(busyItemId)}
                    onClick={() => runQuickAction(action.key)}
                    className={[
                      'rounded-2xl border px-4 py-4 text-left transition-colors',
                      action.disabled
                        ? 'cursor-not-allowed border-white/5 bg-white/[0.03] text-slate-500 opacity-70'
                        : 'border-white/10 bg-white/10 text-white hover:bg-white/15',
                    ].join(' ')}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="text-sm font-semibold">{action.title}</div>
                      <div
                        className={[
                          'rounded-full px-2 py-0.5 text-xs',
                          action.disabled ? 'bg-white/5 text-slate-500' : 'bg-white/10 text-slate-200',
                        ].join(' ')}
                      >
                        {action.disabled ? (isRu ? 'Недоступно' : 'Locked') : action.metric}
                      </div>
                    </div>
                    <div className={['mt-2 line-clamp-2 text-xs leading-5', action.disabled ? 'text-slate-500' : 'text-slate-300'].join(' ')}>
                      {action.description}
                    </div>
                  </button>
                ))}
              </div>
            </div>
            {isNetworkMode && itemLocationSummary.length > 1 ? (
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
            {networkOperatingSlices.length > 0 ? (
              <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Режим управления сетью' : 'Network operating mode'}
                    </div>
                    <div className="mt-1 text-lg font-semibold text-slate-950">
                      {isRu ? 'Точки, где есть работа прямо сейчас' : 'Locations that need work now'}
                    </div>
                    <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
                      {isRu
                        ? 'Откройте конкретную точку и неделю, чтобы не тонуть во всём плане сети сразу.'
                        : 'Open a specific location and week instead of working through the whole network plan at once.'}
                    </div>
                  </div>
                  <div className="rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white">
                    {networkOperatingSlices.length} {isRu ? 'точек в фокусе' : 'locations in focus'}
                  </div>
                </div>
                <div className="mt-5 grid gap-3 xl:grid-cols-2">
                  {networkOperatingSlices.map((slice) => (
                    <div key={slice.key} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="text-base font-semibold text-slate-950">{slice.label}</div>
                          <div className="mt-1 text-sm text-slate-600">
                            {slice.focusWeekLabel} · {isRu ? 'рабочий срез' : 'operating slice'}
                          </div>
                        </div>
                        <span className={[
                          'w-fit rounded-full px-2.5 py-1 text-xs font-medium',
                          slice.riskScore >= 60
                            ? 'bg-red-100 text-red-700'
                            : slice.riskScore >= 30
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-emerald-100 text-emerald-800',
                        ].join(' ')}
                        >
                          {_networkRiskLabel(slice.riskScore, isRu)}
                        </span>
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.needsDraft}</div>
                          <div className="text-slate-500">{isRu ? 'без текста' : 'no draft'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.readyToPublish}</div>
                          <div className="text-slate-500">{isRu ? 'к новости' : 'ready'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.published}</div>
                          <div className="text-slate-500">{isRu ? 'создано' : 'created'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.skipped}</div>
                          <div className="text-slate-500">{isRu ? 'пропуски' : 'skipped'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{Number(slice.riskScore || 0).toFixed(0)}</div>
                          <div className="text-slate-500">{isRu ? 'риск' : 'risk'}</div>
                        </div>
                      </div>
                      <div className="mt-3 rounded-xl bg-white px-3 py-2 text-sm leading-6 text-slate-700">
                        {slice.recommendation}
                      </div>
                      {slice.reasons.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2 text-xs">
                          {slice.reasons.slice(0, 3).map((reason) => (
                            <span key={reason} className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                              {_networkQualityReasonLabel(reason, isRu)}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <div className="mt-4 flex flex-wrap items-center gap-2">
                        <Input
                          type="date"
                          value={bulkTargetDate}
                          onChange={(event) => setBulkTargetDate(event.target.value)}
                          className="h-9 w-[158px] bg-white"
                          aria-label={isRu ? 'Дата переноса среза' : 'Slice target date'}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applyLocationWeekFocus(slice.key, slice.focusWeekKey)}
                        >
                          {isRu ? 'Открыть точку' : 'Open location'}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => { void runLocationWeekFocusDrafts(slice.key, slice.focusWeekKey); }}
                          disabled={Boolean(bulkBusyAction) || slice.focusWeekKey === 'all' || slice.focusWeekNeedsDraft === 0}
                        >
                          {bulkBusyAction === `focus-drafts:${slice.key}:${slice.focusWeekKey}`
                            ? (isRu ? 'Генерируем...' : 'Generating...')
                            : `${isRu ? 'Сгенерировать неделю' : 'Generate week'} · ${slice.focusWeekNeedsDraft}`}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => { void runLocationWeekFocusNews(slice.key, slice.focusWeekKey); }}
                          disabled={Boolean(bulkBusyAction) || slice.focusWeekKey === 'all' || slice.focusWeekReadyToPublish === 0}
                        >
                          {bulkBusyAction === `focus-news:${slice.key}:${slice.focusWeekKey}`
                            ? (isRu ? 'Создаём...' : 'Creating...')
                            : `${isRu ? 'Создать новости' : 'Create news'} · ${slice.focusWeekReadyToPublish}`}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => { void runLocationWeekRescheduleToDate(slice.key, slice.focusWeekKey, bulkTargetDate); }}
                          disabled={Boolean(bulkBusyAction) || slice.focusWeekKey === 'all' || slice.total === 0}
                        >
                          {bulkBusyAction === `focus-reschedule-date:${slice.key}:${slice.focusWeekKey}`
                            ? (isRu ? 'Переносим...' : 'Rescheduling...')
                            : (isRu ? 'Перенести на дату' : 'Move to date')}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => { void runLocationWeekSkip(slice.key, slice.focusWeekKey); }}
                          disabled={Boolean(bulkBusyAction) || slice.focusWeekKey === 'all' || slice.total === 0}
                        >
                          {bulkBusyAction === `focus-skip:${slice.key}:${slice.focusWeekKey}`
                            ? (isRu ? 'Пропускаем...' : 'Skipping...')
                            : (isRu ? 'Пропустить срез' : 'Skip slice')}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {viewPresets.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  onClick={() => applyViewPreset(preset.key)}
                  className={[
                    'rounded-full border px-3 py-1.5 text-sm transition-colors',
                    selectedViewPreset === preset.key
                      ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            {locationWeekFocusSummary.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {locationWeekFocusSummary.map((focus) => (
                  <div
                    key={focus.key}
                    className={[
                      'rounded-2xl border px-4 py-4 text-left transition-colors',
                      selectedViewPreset === 'focus' && selectedItemLocationKey === focus.locationKey && selectedWeekKey === focus.weekKey
                        ? 'border-indigo-300 bg-indigo-50'
                        : 'border-slate-200 bg-white hover:bg-slate-50',
                    ].join(' ')}
                  >
                    <button
                      type="button"
                      onClick={() => applyLocationWeekFocus(focus.locationKey, focus.weekKey)}
                      className="w-full text-left"
                    >
                      <div className="text-sm font-semibold text-slate-900">
                        {focus.locationLabel}
                      </div>
                      <div className="mt-1 text-xs font-medium text-slate-500">
                        {focus.weekLabel}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs">
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">
                          {isRu ? 'Всего' : 'Total'} · {focus.total}
                        </span>
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-amber-800">
                          {isRu ? 'Без текста' : 'No draft'} · {focus.needsDraft}
                        </span>
                        <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-emerald-800">
                          {isRu ? 'Готово к публикации' : 'Ready'} · {focus.readyToPublish}
                        </span>
                      </div>
                    </button>
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <Input
                        type="date"
                        value={bulkTargetDate}
                        onChange={(event) => setBulkTargetDate(event.target.value)}
                        className="h-9 w-[158px] bg-white"
                        aria-label={isRu ? 'Дата переноса среза' : 'Slice target date'}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => applyLocationWeekFocus(focus.locationKey, focus.weekKey)}
                      >
                        {isRu ? 'Открыть этот срез' : 'Open this slice'}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => { void runLocationWeekFocusDrafts(focus.locationKey, focus.weekKey); }}
                        disabled={Boolean(bulkBusyAction) || focus.needsDraft === 0}
                      >
                        {bulkBusyAction === `focus-drafts:${focus.locationKey}:${focus.weekKey}`
                          ? (isRu ? 'Генерируем...' : 'Generating...')
                          : `${isRu ? 'Сгенерировать' : 'Generate'} · ${focus.needsDraft}`}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => { void runLocationWeekFocusNews(focus.locationKey, focus.weekKey); }}
                        disabled={Boolean(bulkBusyAction) || focus.readyToPublish === 0}
                      >
                        {bulkBusyAction === `focus-news:${focus.locationKey}:${focus.weekKey}`
                          ? (isRu ? 'Публикуем...' : 'Publishing...')
                          : `${isRu ? 'Создать новости' : 'Create news'} · ${focus.readyToPublish}`}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => { void runLocationWeekRescheduleToDate(focus.locationKey, focus.weekKey, bulkTargetDate); }}
                        disabled={Boolean(bulkBusyAction) || focus.total === 0}
                      >
                        {bulkBusyAction === `focus-reschedule-date:${focus.locationKey}:${focus.weekKey}`
                          ? (isRu ? 'Переносим...' : 'Rescheduling...')
                          : (isRu ? 'Перенести на дату' : 'Move to date')}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => { void runLocationWeekSkip(focus.locationKey, focus.weekKey); }}
                        disabled={Boolean(bulkBusyAction) || focus.total === 0}
                      >
                        {bulkBusyAction === `focus-skip:${focus.locationKey}:${focus.weekKey}`
                          ? (isRu ? 'Пропускаем...' : 'Skipping...')
                          : (isRu ? 'Пропустить пачку' : 'Skip batch')}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
            {bulkNewsReview ? (
              <div className="rounded-[28px] border border-slate-900 bg-white p-5 shadow-lg">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Подтверждение публикаций' : 'Publication review'}
                    </div>
                    <div className="mt-2 text-lg font-semibold text-slate-950">
                      {isRu ? bulkNewsReview.titleRu : bulkNewsReview.titleEn}
                    </div>
                    <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                      {isRu ? bulkNewsReview.descriptionRu : bulkNewsReview.descriptionEn}
                    </div>
                  </div>
                  <div className="rounded-2xl bg-slate-950 px-4 py-3 text-center text-white">
                    <div className="text-2xl font-semibold">{bulkNewsReview.items.length}</div>
                    <div className="text-xs text-slate-300">{isRu ? 'новостей' : 'news items'}</div>
                  </div>
                </div>
                {bulkNewsReview.items.filter((item) => !_inputDateValue(item.scheduled_for)).length > 0 ? (
                  <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                    {isRu
                      ? `${bulkNewsReview.items.filter((item) => !_inputDateValue(item.scheduled_for)).length} публикации без даты. Они будут созданы как черновики без календаря.`
                      : `${bulkNewsReview.items.filter((item) => !_inputDateValue(item.scheduled_for)).length} publications have no date. They will be created as drafts without a calendar date.`}
                  </div>
                ) : null}
                <div className="mt-4 grid gap-2">
                  {bulkNewsReview.items.slice(0, 5).map((item) => (
                    <div key={`${bulkNewsReview.key}:${item.id}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-sm font-semibold text-slate-950">
                          {String(item.theme || item.goal || (isRu ? 'Без темы' : 'Untitled')).trim()}
                        </div>
                        <div className="text-xs text-slate-500">{_formatPlanItemDate(item.scheduled_for, isRu)}</div>
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {_itemLocationLabel(item, isRu)} · {_sourceKindLabel(item.source_kind, isRu)}
                      </div>
                    </div>
                  ))}
                  {bulkNewsReview.items.length > 5 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                      {isRu
                        ? `И ещё ${bulkNewsReview.items.length - 5} элементов в этом массовом действии.`
                        : `And ${bulkNewsReview.items.length - 5} more items in this bulk action.`}
                    </div>
                  ) : null}
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    onClick={() => { void executeBulkNewsReview(); }}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {bulkBusyAction === bulkNewsReview.busyAction
                      ? (isRu ? 'Создаём новости...' : 'Creating news...')
                      : (isRu ? 'Подтвердить и создать' : 'Confirm and create')}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setBulkNewsReview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  {bulkNewsReview.focusLocationKey && bulkNewsReview.focusWeekKey ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="bg-slate-50"
                      onClick={() => {
                        applyLocationWeekFocus(bulkNewsReview.focusLocationKey || 'all', bulkNewsReview.focusWeekKey || 'all');
                      }}
                      disabled={Boolean(bulkBusyAction)}
                    >
                      {isRu ? 'Открыть срез перед созданием' : 'Open slice before creating'}
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}
            {bulkActionReview ? (
              <div className="rounded-[28px] border border-slate-900 bg-white p-5 shadow-lg">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Подтверждение массового действия' : 'Bulk action review'}
                    </div>
                    <div className="mt-2 text-lg font-semibold text-slate-950">
                      {isRu ? bulkActionReview.titleRu : bulkActionReview.titleEn}
                    </div>
                    <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                      {isRu ? bulkActionReview.descriptionRu : bulkActionReview.descriptionEn}
                    </div>
                  </div>
                  <div className="rounded-2xl bg-slate-950 px-4 py-3 text-center text-white">
                    <div className="text-2xl font-semibold">{bulkActionReview.items.length}</div>
                    <div className="text-xs text-slate-300">{isRu ? 'элементов' : 'items'}</div>
                  </div>
                </div>
                <div className="mt-4 grid gap-2">
                  {bulkActionReview.items.slice(0, 5).map((item) => (
                    <div key={`${bulkActionReview.key}:${item.id}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-sm font-semibold text-slate-950">
                          {String(item.theme || item.goal || (isRu ? 'Без темы' : 'Untitled')).trim()}
                        </div>
                        <div className="text-xs text-slate-500">
                          {bulkActionReview.kind === 'reschedule' && bulkActionReview.targetDate
                            ? `${_formatPlanItemDate(item.scheduled_for, isRu)} → ${_formatPlanItemDate(bulkActionReview.targetDate, isRu)}`
                            : _formatPlanItemDate(item.scheduled_for, isRu)}
                        </div>
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {_itemLocationLabel(item, isRu)} · {_sourceKindLabel(item.source_kind, isRu)}
                      </div>
                    </div>
                  ))}
                  {bulkActionReview.items.length > 5 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                      {isRu
                        ? `И ещё ${bulkActionReview.items.length - 5} элементов в этом массовом действии.`
                        : `And ${bulkActionReview.items.length - 5} more items in this bulk action.`}
                    </div>
                  ) : null}
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    onClick={() => { void executeBulkActionReview(); }}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {bulkBusyAction === bulkActionReview.busyAction
                      ? (isRu ? 'Выполняем...' : 'Processing...')
                      : (isRu ? bulkActionReview.confirmLabelRu : bulkActionReview.confirmLabelEn)}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setBulkActionReview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  {bulkActionReview.focusLocationKey && bulkActionReview.focusWeekKey ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="bg-slate-50"
                      onClick={() => {
                        applyLocationWeekFocus(bulkActionReview.focusLocationKey || 'all', bulkActionReview.focusWeekKey || 'all');
                      }}
                      disabled={Boolean(bulkBusyAction)}
                    >
                      {isRu ? 'Открыть срез' : 'Open slice'}
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}
            {actionSummary ? (
              <div
                className={[
                  'rounded-2xl border px-4 py-3 text-sm',
                  actionSummary.tone === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : actionSummary.tone === 'warning'
                      ? 'border-amber-200 bg-amber-50 text-amber-900'
                      : 'border-slate-200 bg-slate-50 text-slate-700',
                ].join(' ')}
              >
                <div>{isRu ? actionSummary.text_ru : actionSummary.text_en}</div>
                {(isRu ? actionSummary.details_ru : actionSummary.details_en)?.length ? (
                  <div className="mt-2 space-y-1 text-xs opacity-90">
                    {(isRu ? actionSummary.details_ru : actionSummary.details_en)?.map((detail) => (
                      <div key={detail}>{detail}</div>
                    ))}
                  </div>
                ) : null}
                {actionSummary.focusLocationKey && actionSummary.focusWeekKey ? (
                  <div className="mt-3">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="bg-white/70"
                      onClick={() => applyLocationWeekFocus(String(actionSummary.focusLocationKey || ''), String(actionSummary.focusWeekKey || ''))}
                    >
                      {isRu ? 'Открыть этот срез' : 'Open this slice'}
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 md:flex-row md:items-center md:justify-between">
              <div>
                <span className="font-medium text-slate-900">
                  {isRu ? 'Сейчас показано:' : 'Current view:'}
                </span>{' '}
                {_itemFilterLabel(selectedItemFilter, isRu)} · {_signalFilterLabel(selectedSignalFilter, isRu)} · {activeLocationLabel} · {activeWeekLabel} · {sortMode === 'priority' ? (isRu ? 'По приоритету' : 'By priority') : (isRu ? 'По дате' : 'By date')}
              </div>
              <button
                type="button"
                onClick={() => setShowAdvancedControls((prev) => !prev)}
                className="self-start rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-100 md:self-auto"
              >
                {showAdvancedControls
                  ? (isRu ? 'Скрыть тонкие фильтры' : 'Hide advanced filters')
                  : (isRu ? 'Тонкие фильтры' : 'Advanced filters')}
              </button>
            </div>
            {showAdvancedControls ? (
              <>
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
            {isNetworkMode && availableItemLocations.length > 1 ? (
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
            {isNetworkMode && locationOperationalSummary.length > 1 ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {locationOperationalSummary.map((location) => (
                  <button
                    key={location.key}
                    type="button"
                    onClick={() => setSelectedItemLocationKey(location.key)}
                    className={[
                      'rounded-2xl border px-4 py-4 text-left transition-colors',
                      selectedItemLocationKey === location.key
                        ? 'border-sky-300 bg-sky-50'
                        : 'border-slate-200 bg-white hover:bg-slate-50',
                    ].join(' ')}
                  >
                    <div className="text-sm font-semibold text-slate-900">
                      {location.label}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">
                        {isRu ? 'Всего' : 'Total'} · {location.total}
                      </span>
                      <span className="rounded-full bg-amber-100 px-2.5 py-1 text-amber-800">
                        {isRu ? 'Без текста' : 'No draft'} · {location.needsDraft}
                      </span>
                      <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-emerald-800">
                        {isRu ? 'Готово к публикации' : 'Ready to publish'} · {location.readyToPublish}
                      </span>
                    </div>
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
              </>
            ) : null}
            <div className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <div className="w-full text-xs font-medium text-slate-500">
                {sortMode === 'priority'
                  ? (isRu
                    ? 'Порядок внутри списка: сначала без текста, затем готовые к публикации, затем остальные.'
                    : 'Items are ordered by next best action: no draft first, then ready to publish, then the rest.')
                  : (isRu
                    ? 'Порядок внутри списка: по календарной дате, затем по теме.'
                    : 'Items are ordered by calendar date, then by theme.')}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setSortMode('priority')}
                  className={[
                    'rounded-full border px-3 py-1.5 text-sm transition-colors',
                    sortMode === 'priority'
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {isRu ? 'По приоритету' : 'By priority'}
                </button>
                <button
                  type="button"
                  onClick={() => setSortMode('date')}
                  className={[
                    'rounded-full border px-3 py-1.5 text-sm transition-colors',
                    sortMode === 'date'
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {isRu ? 'По дате' : 'By date'}
                </button>
                <button
                  type="button"
                  onClick={resetViewState}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition-colors hover:bg-slate-50"
                >
                  {isRu ? 'Сбросить вид' : 'Reset view'}
                </button>
              </div>
              {selectedItems.length > 0 ? (
                <div className="flex w-full flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-3">
                  <div className="mr-auto flex items-center gap-2 text-sm font-medium text-slate-900">
                    <CheckSquare className="h-4 w-4" />
                    {isRu ? `Выбрано: ${selectedItems.length}` : `Selected: ${selectedItems.length}`}
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => { void runSelectedGenerateDrafts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedDraftCandidates.length === 0}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {bulkBusyAction === 'selected-drafts'
                      ? (isRu ? 'Генерируем тексты...' : 'Generating texts...')
                      : `${isRu ? 'Сгенерировать тексты' : 'Generate texts'} · ${selectedDraftCandidates.length}`}
                  </Button>
                  <Button
                    onClick={runSelectedCreateNews}
                    disabled={Boolean(bulkBusyAction) || selectedNewsCandidates.length === 0}
                  >
                    {bulkBusyAction === 'selected-news'
                      ? (isRu ? 'Создаём новости...' : 'Creating news...')
                      : `${isRu ? 'Создать выбранные новости' : 'Create selected news'} · ${selectedNewsCandidates.length}`}
                  </Button>
                  <Button type="button" variant="ghost" onClick={clearSelectedItems}>
                    {isRu ? 'Снять выбор' : 'Clear'}
                  </Button>
                </div>
              ) : null}
            </div>
            {visibleItems.length > 0 ? (
              <div className={activeZone === 'editor' ? 'grid gap-4' : 'grid gap-4 xl:grid-cols-[minmax(280px,0.75fr)_minmax(0,1.35fr)]'}>
                <div className={activeZone === 'editor' ? 'hidden' : 'rounded-[28px] border border-slate-200 bg-slate-50 p-3'}>
                  <div className="px-2 pb-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Очередь тем' : 'Topic queue'}
                    </div>
                    <div className="mt-1 text-sm text-slate-600">
                      {isRu ? 'Выберите одну тему для работы справа.' : 'Select one item to work on at the right.'}
                    </div>
                  </div>
                  <div className="max-h-[680px] space-y-2 overflow-y-auto pr-1">
                    {visibleItems.map((item) => {
                      const status = _planItemStatus(item, isRu);
                      const isSelected = selectedQueueItem?.id === item.id;
                      return (
                        <button
                          key={item.id}
                          type="button"
	                          onClick={() => {
	                            setSelectedQueueItemId(item.id);
	                            setShowSelectedItemDetails(false);
                            setActiveZone('editor');
	                          }}
                          className={[
                            'w-full rounded-2xl border px-4 py-3 text-left transition-colors',
                            isSelected
                              ? 'border-slate-950 bg-white shadow-sm'
                              : 'border-transparent bg-white/70 hover:border-slate-200 hover:bg-white',
                          ].join(' ')}
                        >
	                          <div className="flex items-start justify-between gap-3">
                            <span className="flex items-center gap-2">
                              <span
                                role="checkbox"
                                aria-checked={Boolean(selectedItemIds[item.id])}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  toggleSelectedItem(item.id);
                                }}
                                className={[
                                  'flex h-5 w-5 items-center justify-center rounded-md border transition-colors',
                                  selectedItemIds[item.id]
                                    ? 'border-slate-900 bg-slate-900 text-white'
                                    : 'border-slate-300 bg-white text-transparent',
                                ].join(' ')}
                              >
                                <CheckSquare className="h-3.5 w-3.5" />
                              </span>
	                            <span className={status.className}>{status.label}</span>
                            </span>
                            <span className="shrink-0 text-xs font-medium text-slate-400">
                              {_formatPlanItemDate(item.scheduled_for, isRu)}
                            </span>
                          </div>
                          <div className="mt-2 line-clamp-2 text-sm font-semibold leading-5 text-slate-950">
                            {_humanizePlanTitle(item, isRu)}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-slate-500">
                            <span>{_contentTypeLabel(item.content_type, isRu)}</span>
                            <span>·</span>
                            <span>{_sourceKindLabel(item.source_kind, isRu)}</span>
                            {_seoViewsLabel(item, isRu) ? (
                              <>
                                <span>·</span>
                                <span>{_seoViewsLabel(item, isRu)}</span>
                              </>
                            ) : null}
                            {isNetworkMode && item.location_label ? (
                              <>
                                <span>·</span>
                                <span className="line-clamp-1">{_itemLocationLabel(item, isRu)}</span>
                              </>
                            ) : null}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {activeZone === 'editor' && selectedQueueItem ? (() => {
                  const item = selectedQueueItem;
                  const currentDraft = draftEdits[item.id] !== undefined ? draftEdits[item.id] : item.draft_text;
                  const currentTheme = themeEdits[item.id] !== undefined ? themeEdits[item.id] : item.theme;
                  const currentDate = dateEdits[item.id] !== undefined ? dateEdits[item.id] : item.scheduled_for;
                  const currentInputDate = _inputDateValue(currentDate);
                  const duplicateTargetOptions = getDuplicateTargetLocationOptions(item);
                  const selectedDuplicateTargets = duplicateTargetSelections[item.id] || [];
                  const duplicateTargetDate = duplicateDateOverrides[item.id] || currentInputDate;
                  const status = _planItemStatus(item, isRu);
                  const hasDraft = Boolean(String(currentDraft || '').trim());
                  const hasNews = Boolean(String(item.usernews_id || '').trim());
                  return (
                    <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={status.className}>{status.label}</span>
                            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                              {_contentTypeLabel(item.content_type, isRu)}
                            </span>
                            {isNetworkMode && item.location_label ? (
                              <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-800">
                                {_itemLocationLabel(item, isRu)}
                              </span>
                            ) : null}
                          </div>
                          <h5 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">
                            {_humanizePlanTitle(item, isRu)}
                          </h5>
                          {recentGeneratedItemId === item.id ? (
                            <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
                              {isRu
                                ? 'Черновик сгенерирован именно для этой темы.'
                                : 'The draft was generated for this selected item.'}
                            </div>
                          ) : null}
                        </div>
                        <div className="grid min-w-[180px] grid-cols-2 gap-2 text-center text-xs text-slate-500">
                          <div className="rounded-2xl bg-slate-50 px-3 py-3">
                            <div className="text-sm font-semibold text-slate-950">{_formatPlanItemDate(currentDate, isRu)}</div>
                            <div>{isRu ? 'дата' : 'date'}</div>
                          </div>
                          <div className="rounded-2xl bg-slate-50 px-3 py-3">
                            <div className="text-sm font-semibold text-slate-950">{_sourceKindLabel(item.source_kind, isRu)}</div>
                            <div>{isRu ? 'сигнал' : 'signal'}</div>
                          </div>
                          {_seoViewsLabel(item, isRu) ? (
                            <div className="col-span-2 rounded-2xl bg-blue-50 px-3 py-3">
                              <div className="text-sm font-semibold text-blue-950">{_seoViewsLabel(item, isRu)}</div>
                              <div>{isRu ? 'частотность запроса' : 'query demand'}</div>
                            </div>
                          ) : null}
                        </div>
                      </div>

                      <div className="mt-6 grid gap-4 lg:grid-cols-[180px_1fr]">
                        <div className="space-y-2">
                          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                            {isRu ? 'Дата' : 'Date'}
                          </div>
                          <Input
                            type="date"
                            value={currentInputDate}
                            onChange={(event) => setDateEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                          />
                          {!currentInputDate ? (
                            <div className="text-xs leading-5 text-amber-700">
                              {isRu ? 'Назначьте дату публикации' : 'Set a publication date'}
                            </div>
                          ) : null}
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

                      <div className="mt-5 space-y-2">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          {isRu ? 'Черновик' : 'Draft'}
                        </div>
                        <Textarea
                          rows={8}
                          value={currentDraft}
                          onChange={(event) => setDraftEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                          placeholder={isRu ? 'Здесь появится текст публикации' : 'Draft text will appear here'}
                        />
                      </div>

                      <div className="sticky bottom-3 z-10 mt-5 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white/95 px-3 py-3 shadow-lg backdrop-blur">
                          <Button
                            onClick={() => createNews(item.id)}
                            disabled={busyItemId === item.id || !String(currentDraft || '').trim() || hasNews}
                          >
                            {hasNews
                              ? (isRu ? 'Новость создана' : 'News created')
                              : (isRu ? 'Создать новость' : 'Create news')}
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => saveItem(item.id)}
                            disabled={busyItemId === item.id}
                          >
                            {isRu ? 'Сохранить' : 'Save'}
                          </Button>
                          {!hasDraft ? (
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => generateDraft(item.id)}
                              disabled={busyItemId === item.id}
                            >
                              <Sparkles className="mr-2 h-4 w-4" />
                              {isRu ? 'Сгенерировать текст' : 'Generate text'}
                            </Button>
                          ) : null}
                          <details className="relative">
                            <summary className="flex cursor-pointer list-none items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                              <MoreHorizontal className="h-4 w-4" />
                              {isRu ? 'Ещё' : 'More'}
                            </summary>
                            <div className="absolute bottom-11 right-0 z-20 w-56 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                              <button
                                type="button"
                                onClick={() => generateDraft(item.id)}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                              >
                                {hasDraft ? (isRu ? 'Перегенерировать' : 'Regenerate') : (isRu ? 'Сгенерировать текст' : 'Generate text')}
                              </button>
                              <button
                                type="button"
                                onClick={() => runItemReschedule(item.id, currentDate, 7)}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                              >
                                {isRu ? 'Перенести на 7 дней' : 'Move by 7 days'}
                              </button>
                              <button
                                type="button"
                                onClick={() => runItemDuplicate(item.id)}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                              >
                                {isRu ? 'Дублировать' : 'Duplicate'}
                              </button>
                              {isNetworkMode && availableItemLocations.length > 2 ? (
                                <button
                                  type="button"
                                  onClick={() => openDuplicateTargetPicker(item)}
                                  disabled={busyItemId === item.id || !String(currentDraft || item.usernews_id || '').trim()}
                                  className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                                >
                                  {isRu ? 'Выбрать точки' : 'Choose locations'}
                                </button>
                              ) : null}
                              <button
                                type="button"
                                onClick={() => runItemSkip(item.id)}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-500 hover:bg-slate-50 disabled:opacity-50"
                              >
                                {isRu ? 'Пропустить' : 'Skip'}
                              </button>
                            </div>
                          </details>
                      </div>

                      <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                        <button
                          type="button"
                          onClick={() => setShowSelectedItemDetails((prev) => !prev)}
                          className="flex w-full items-center justify-between gap-3 text-left text-sm font-semibold text-slate-900"
                        >
                          <span>{isRu ? 'Почему эта тема и откуда сигнал' : 'Why this topic and signal source'}</span>
                          <span className="text-xs font-medium text-slate-500">
                            {showSelectedItemDetails ? (isRu ? 'Скрыть' : 'Hide') : (isRu ? 'Показать' : 'Show')}
                          </span>
                        </button>
                        {showSelectedItemDetails ? (
                          <div className="mt-3 text-sm leading-6 text-slate-700">
                            <div>{_humanizePlanGoal(item, isRu)}</div>
                            <div className="mt-2 text-xs text-slate-500">
                              <MapPinned className="mr-1 inline h-3.5 w-3.5" />
                              {_sourceKindLabel(item.source_kind, isRu)} {item.source_ref ? `· ${item.source_ref}` : ''}
                              {item.seo_keyword ? ` · SEO: ${item.seo_keyword}` : ''}
                              {_seoViewsLabel(item, isRu) ? ` · ${_seoViewsLabel(item, isRu)}` : ''}
                            </div>
                          </div>
                        ) : null}
                      </div>

                      {expandedDuplicateItemId === item.id ? (
                        <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                              <div className="text-sm font-semibold text-slate-950">
                                {isRu ? 'Дублировать удачную тему на выбранные точки' : 'Duplicate this winning topic to selected locations'}
                              </div>
                              <div className="mt-1 text-sm leading-6 text-slate-600">
                                {isRu
                                  ? 'Выберите только те точки, где эта тема действительно уместна. Черновик и дата будут скопированы.'
                                  : 'Pick only locations where this topic fits. The draft and date will be copied.'}
                              </div>
                            </div>
                            <Input
                              type="date"
                              value={duplicateTargetDate}
                              onChange={(event) => setDuplicateDateOverrides((prev) => ({ ...prev, [item.id]: event.target.value }))}
                              className="h-9 max-w-[180px]"
                              aria-label={isRu ? 'Дата дублирования темы' : 'Duplicate target date'}
                            />
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {duplicateTargetOptions.map((location) => (
                              <button
                                key={location.key}
                                type="button"
                                onClick={() => toggleDuplicateTargetLocation(item.id, location.key)}
                                className={[
                                  'rounded-full border px-3 py-1.5 text-sm transition-colors',
                                  selectedDuplicateTargets.includes(location.key)
                                    ? 'border-sky-300 bg-sky-50 text-sky-800'
                                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                                ].join(' ')}
                              >
                                {location.label}
                              </button>
                            ))}
                          </div>
                          <div className="mt-4 flex flex-wrap gap-2">
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => { void runItemDuplicateToSelectedLocations(item); }}
                              disabled={busyItemId === item.id || selectedDuplicateTargets.length === 0}
                            >
                              {isRu ? `Дублировать · ${selectedDuplicateTargets.length}` : `Duplicate · ${selectedDuplicateTargets.length}`}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => setExpandedDuplicateItemId('')}
                            >
                              {isRu ? 'Отмена' : 'Cancel'}
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => { void runItemDuplicateToOtherLocations(item); }}
                              disabled={busyItemId === item.id || duplicateTargetOptions.length === 0}
                            >
                              {isRu ? 'На все остальные' : 'All other locations'}
                            </Button>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  );
                })() : null}
              </div>
            ) : null}
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

function _locationLabelByKey(items: PlanItem[], locationKey: string, isRu: boolean): string {
  for (const item of items) {
    const currentKey = String(item.location_scope || item.business_id || '').trim();
    if (currentKey === locationKey) {
      return _itemLocationLabel(item, isRu);
    }
  }
  return isRu ? 'Точка сети' : 'Network location';
}

function _bulkResultText(kind: 'drafts' | 'news', successCount: number, failedCount: number, isRu: boolean): string {
  if (kind === 'drafts') {
    if (failedCount > 0) {
      return isRu
        ? `сгенерировано черновиков ${successCount}, не получилось ${failedCount}`
        : `generated drafts ${successCount}, failed ${failedCount}`;
    }
    return isRu
      ? `сгенерировано черновиков ${successCount}`
      : `generated drafts ${successCount}`;
  }
  if (failedCount > 0) {
    return isRu
      ? `создано новостей ${successCount}, не получилось ${failedCount}`
      : `created news items ${successCount}, failed ${failedCount}`;
  }
  return isRu
    ? `создано новостей ${successCount}`
    : `created news items ${successCount}`;
}

function _bulkResultDetails(failedThemes: string[], isRu: boolean): string[] {
  const cleanThemes = failedThemes
    .map((theme) => String(theme || '').trim())
    .filter(Boolean)
    .slice(0, 3);
  if (cleanThemes.length === 0) return [];
  const prefix = isRu ? 'Не обработано' : 'Not processed';
  return cleanThemes.map((theme) => `${prefix}: ${theme}`);
}

function _learningCapabilityLabel(capability: string, isRu: boolean): string {
  const normalized = String(capability || '').trim().toLowerCase();
  if (normalized === 'content_plan.generate') return isRu ? 'Генерация плана' : 'Plan generation';
  if (normalized === 'content_plan.draft') return isRu ? 'Генерация черновика' : 'Draft generation';
  if (normalized === 'content_plan.item') return isRu ? 'Действия с элементами' : 'Item actions';
  if (normalized === 'content_plan.publish') return isRu ? 'Создание новостей' : 'News creation';
  return isRu ? 'Контент-план' : 'Content plan';
}

function _networkQualityReasonLabel(reason: string, isRu: boolean): string {
  const normalized = String(reason || '').trim();
  if (normalized === 'many_edits') return isRu ? 'часто правят перед публикацией' : 'often edited before publishing';
  if (normalized === 'skipped_items') return isRu ? 'есть пропущенные темы' : 'has skipped topics';
  if (normalized === 'major_rewrites') return isRu ? 'есть смысловые переписывания' : 'has major rewrites';
  if (normalized === 'drafts_not_published') return isRu ? 'черновики не доходят до новостей' : 'drafts do not reach publishing';
  if (normalized === 'stable') return isRu ? 'работает стабильно' : 'stable';
  return isRu ? 'нужна проверка' : 'needs review';
}

function _networkRiskLabel(riskScore: number, isRu: boolean): string {
  if (Number(riskScore || 0) >= 60) return isRu ? 'Высокий риск' : 'High risk';
  if (Number(riskScore || 0) >= 30) return isRu ? 'Средний риск' : 'Medium risk';
  return isRu ? 'Норма' : 'Stable';
}

function _networkOperatingRecommendation(reasons: string[], isRu: boolean): string {
  const normalized = Array.isArray(reasons) ? reasons.map((item) => String(item || '').trim()) : [];
  if (normalized.includes('drafts_not_published')) {
    return isRu
      ? 'Сначала доведите готовые черновики до новостей: здесь уже есть заготовки, но они не превращаются в публикации.'
      : 'Start by turning ready drafts into news: this location has drafts that do not reach publishing.';
  }
  if (normalized.includes('skipped_items')) {
    return isRu
      ? 'Проверьте темы этой точки: часть идей пропускается, значит нужно упростить поводы и оставить только то, что реально выпустить.'
      : 'Review this location themes: skipped items mean the topics should be simpler and easier to publish.';
  }
  if (normalized.includes('major_rewrites')) {
    return isRu
      ? 'Генерируйте черновики точнее: конкретная услуга, понятная выгода, доказательство и одно действие для клиента.'
      : 'Generate tighter drafts: concrete service, clear benefit, proof point, and one customer action.';
  }
  if (normalized.includes('many_edits')) {
    return isRu
      ? 'Перед публикацией проверьте формулировки: по этой точке часто нужны ручные правки.'
      : 'Review wording before publishing: this location often needs manual edits.';
  }
  return isRu
    ? 'Работайте ближайшей неделей: закройте темы без текста, затем создайте новости из готовых черновиков.'
    : 'Work through the nearest week: fill missing drafts, then create news from ready drafts.';
}

function _itemFilterLabel(filterKey: ItemFilterKey, isRu: boolean): string {
  if (filterKey === 'urgent') return isRu ? 'Только срочное' : 'Urgent only';
  if (filterKey === 'needs_draft') return isRu ? 'Без текста' : 'No draft';
  if (filterKey === 'has_draft') return isRu ? 'Есть черновик' : 'Has draft';
  if (filterKey === 'news_created') return isRu ? 'Есть новость' : 'News created';
  return isRu ? 'Все' : 'All';
}

function _planItemStatus(item: Pick<PlanItem, 'draft_text' | 'usernews_id' | 'status'>, isRu: boolean): { label: string; className: string } {
  const normalizedStatus = String(item.status || '').trim();
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const baseClassName = 'rounded-full px-2.5 py-1 text-xs font-semibold';
  if (normalizedStatus === 'skipped') {
    return {
      label: isRu ? 'Пропущено' : 'Skipped',
      className: `${baseClassName} bg-slate-100 text-slate-500`,
    };
  }
  if (hasNews) {
    return {
      label: isRu ? 'Опубликовано' : 'Published',
      className: `${baseClassName} bg-emerald-100 text-emerald-800`,
    };
  }
  if (hasDraft) {
    return {
      label: isRu ? 'Готово к публикации' : 'Ready',
      className: `${baseClassName} bg-sky-100 text-sky-800`,
    };
  }
  return {
    label: isRu ? 'Без текста' : 'No draft',
    className: `${baseClassName} bg-amber-100 text-amber-800`,
  };
}

function _humanizePlanTitle(item: Pick<PlanItem, 'theme' | 'goal' | 'seo_keyword' | 'content_type'>, isRu: boolean): string {
  const rawTitle = String(item.theme || item.goal || item.seo_keyword || '').trim();
  const fallback = isRu ? 'Тема для публикации' : 'Publication topic';
  if (!rawTitle) return fallback;
  const noisyPrefixes = [
    'Закрыть слабую зону карточки:',
    'Недопокрытый поисковый сценарий:',
    'Ответить на спрос:',
    'Закрыть слабое место карточки:',
    'Аудит ·',
    'SEO ·',
    'Услуга ·',
    'Продажи ·',
  ];
  let title = rawTitle;
  for (const prefix of noisyPrefixes) {
    if (title.toLowerCase().startsWith(prefix.toLowerCase())) {
      title = title.slice(prefix.length).trim();
    }
  }
  title = title
    .replace(/\s+/g, ' ')
    .replace(/^["'«]+|["'»]+$/g, '')
    .trim();
  if (!title) return fallback;
  if (title.length <= 96) return title;
  return `${title.slice(0, 93).trim()}...`;
}

function _humanizePlanGoal(item: Pick<PlanItem, 'goal' | 'theme' | 'source_kind' | 'source_ref' | 'seo_keyword'>, isRu: boolean): string {
  const rawGoal = String(item.goal || '').trim();
  const rawTheme = String(item.theme || '').trim();
  const sourceRef = String(item.source_ref || item.seo_keyword || '').trim();
  const combined = `${rawGoal} ${rawTheme} ${sourceRef}`.toLowerCase();
  if (!rawGoal && !rawTheme && !sourceRef) {
    return isRu ? 'Причина не указана.' : 'No reason provided.';
  }
  if (
    combined.includes('недопокрытый поисковый сценарий')
    || combined.includes('закрыть слабую зону карточки')
    || combined.includes('закрыть слабое место карточки')
  ) {
    const readableSource = _cleanTechnicalPlanText(sourceRef || rawTheme);
    if (readableSource && /цен|стоимост|прайс|пример|работ|фото/i.test(readableSource)) {
      return isRu
        ? 'Клиенту проще записаться, если в карточке видно цену, результат и понятный следующий шаг.'
        : 'Customers are more likely to book when the listing shows price, result, and the next step.';
    }
    if (readableSource) {
      return isRu
        ? `Карточке нужен понятный ответ на запрос клиента: ${readableSource}.`
        : `The listing needs a clear answer for this customer search: ${readableSource}.`;
    }
    return isRu
      ? 'Карточке нужен более понятный ответ на поисковый сценарий клиента.'
      : 'The listing needs a clearer answer for this customer search scenario.';
  }
  return rawGoal || rawTheme || (isRu ? 'Причина не указана.' : 'No reason provided.');
}

function _cleanTechnicalPlanText(value: string): string {
  const prefixes = [
    'Закрыть слабую зону карточки:',
    'Закрыть слабое место карточки вокруг темы',
    'Закрыть слабое место карточки:',
    'Недопокрытый поисковый сценарий:',
    'Ответить на спрос:',
  ];
  let text = String(value || '').trim();
  let changed = true;
  while (changed) {
    changed = false;
    for (const prefix of prefixes) {
      if (text.toLowerCase().startsWith(prefix.toLowerCase())) {
        text = text.slice(prefix.length).trim();
        changed = true;
      }
    }
  }
  return text
    .replace(/^["'«]+|["'»]+$/g, '')
    .replace(/\s+и снизить сомнения перед звонком, визитом или записью\.?$/i, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function _matchesItemFilter(item: PlanItem, filterKey: ItemFilterKey): boolean {
  const status = String(item.status || '').trim();
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  if (status === 'skipped') return filterKey === 'all';
  if (filterKey === 'urgent') return !hasNews;
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

function _sourceKindLabel(sourceKind: string, isRu: boolean): string {
  const normalized = String(sourceKind || '').trim().toLowerCase();
  if (normalized === 'seo_keyword') return isRu ? 'SEO-сигнал' : 'SEO signal';
  if (normalized === 'service') return isRu ? 'Основание: услуга' : 'Reason: service';
  if (normalized === 'transaction') return isRu ? 'Основание: продажи' : 'Reason: sales';
  if (normalized === 'audit_signal') return isRu ? 'Основание: аудит' : 'Reason: audit';
  if (normalized === 'seasonal') return isRu ? 'Основание: сезон' : 'Reason: season';
  if (normalized === 'fallback') return isRu ? 'Базовый сигнал' : 'Baseline signal';
  return isRu ? 'Сигнал' : 'Signal';
}

function _seoViewsLabel(item: Pick<PlanItem, 'source_kind' | 'seo_views'>, isRu: boolean): string {
  if (String(item.source_kind || '').trim().toLowerCase() !== 'seo_keyword') return '';
  const views = Number(item.seo_views || 0);
  if (!Number.isFinite(views) || views <= 0) return '';
  const formatted = new Intl.NumberFormat(isRu ? 'ru-RU' : 'en-US').format(Math.round(views));
  return isRu ? `${formatted} показов` : `${formatted} searches`;
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

function _readStoredSortMode(): 'priority' | 'date' {
  if (typeof window === 'undefined') return 'priority';
  try {
    const raw = window.localStorage.getItem(CONTENT_PLAN_PREFERENCES_KEY);
    if (!raw) return 'priority';
    const parsed = JSON.parse(raw);
    const sortMode = parsed && typeof parsed.sortMode === 'string' ? parsed.sortMode : '';
    return sortMode === 'date' ? 'date' : 'priority';
  } catch {
    return 'priority';
  }
}

function _readStoredPreferences(businessId: string): Record<string, string> | null {
  if (!businessId || typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(`${CONTENT_PLAN_PREFERENCES_KEY}:${businessId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function _writeStoredPreferences(businessId: string, value: Record<string, string>): void {
  if (!businessId || typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(`${CONTENT_PLAN_PREFERENCES_KEY}:${businessId}`, JSON.stringify(value));
    window.localStorage.setItem(CONTENT_PLAN_PREFERENCES_KEY, JSON.stringify({ sortMode: value.sortMode || 'priority' }));
  } catch {
    // Ignore storage write failures to keep the UI operational.
  }
}

function _isValidItemFilterKey(value: string): value is ItemFilterKey {
  return value === 'all'
    || value === 'urgent'
    || value === 'needs_draft'
    || value === 'has_draft'
    || value === 'news_created';
}

function _isValidSignalFilterKey(value: string): value is SignalFilterKey {
  return value === 'all'
    || value === 'seo'
    || value === 'services'
    || value === 'sales'
    || value === 'audit'
    || value === 'seasonal';
}

function _isValidViewPresetKey(value: string): value is ViewPresetKey {
  return value === 'overview'
    || value === 'urgent'
    || value === 'ready'
    || value === 'published'
    || value === 'focus'
    || value === 'custom';
}

function _inferViewPresetKey(value: {
  selectedItemFilter: ItemFilterKey;
  selectedSignalFilter: SignalFilterKey;
  selectedPlanTargetKey: string;
  selectedItemLocationKey: string;
  selectedWeekKey: string;
  sortMode: 'priority' | 'date';
}): ViewPresetKey {
  if (value.selectedItemLocationKey !== 'all' || value.selectedWeekKey !== 'all') {
    return 'focus';
  }
  if (value.selectedSignalFilter !== 'all' || value.selectedPlanTargetKey !== 'all') {
    return 'custom';
  }
  if (value.selectedItemFilter === 'all' && value.sortMode === 'priority') {
    return 'overview';
  }
  if (value.selectedItemFilter === 'urgent') {
    return 'urgent';
  }
  if (value.selectedItemFilter === 'has_draft') {
    return 'ready';
  }
  if (value.selectedItemFilter === 'news_created' && value.sortMode === 'date') {
    return 'published';
  }
  return 'custom';
}

function _shiftIsoDate(input: string, daysDelta: number): string {
  const normalized = String(input || '').slice(0, 10);
  if (!normalized) {
    return new Date(Date.now() + daysDelta * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  }
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return normalized;
  }
  parsed.setUTCDate(parsed.getUTCDate() + daysDelta);
  return parsed.toISOString().slice(0, 10);
}

function _autoScheduledDate(index: number): string {
  return _shiftIsoDate('', Math.max(Number(index || 0), 0) * 3);
}

function _inputDateValue(input: unknown): string {
  const normalized = String(input || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(normalized)) return '';
  return normalized;
}

function _removeRecordKeys(source: Record<string, string>, keys: string[]): Record<string, string> {
  const blocked = new Set(keys.map((item) => String(item || '').trim()).filter(Boolean));
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(source)) {
    if (!blocked.has(key)) {
      next[key] = value;
    }
  }
  return next;
}

function _formatPlanItemDate(input: unknown, isRu: boolean): string {
  const normalized = _inputDateValue(input);
  if (!normalized) return isRu ? 'Дата не назначена' : 'No date set';
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return normalized;
  return new Intl.DateTimeFormat(isRu ? 'ru-RU' : 'en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(parsed);
}

function _itemPriorityRank(item: Pick<PlanItem, 'draft_text' | 'usernews_id'>): number {
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  if (!hasDraft) return 0;
  if (hasDraft && !hasNews) return 1;
  return 2;
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
