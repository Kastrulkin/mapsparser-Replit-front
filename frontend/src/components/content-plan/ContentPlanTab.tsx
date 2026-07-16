import React, { useEffect, useMemo, useState } from 'react';
import { CalendarDays, CheckSquare, Globe, Lock, MapPinned, MoreHorizontal, Sparkles, Trash2, Wand2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLanguage } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import type {
  ScopeOption, ContextPayload, PlanItem, PlanPayload, SocialPost, SocialPublishEvidence,
  SocialPublishRehearsal, SocialPublishRehearsalBulk, SocialOpenClawCapabilityStatus, SocialOpenClawReadiness, SocialSupervisedSafetyContract, SocialPostMetadata,
  SocialPostsSummary, SocialRecommendationPayload, SocialLearningReadiness, SocialRecommendationTopicInsight, SocialRecommendationChannelInsight, SocialRecommendationTextSuggestion,
  SocialQueueGroup, SocialDispatchPreview, SocialDispatchExecutionReport, SocialFirstCycleVerification, SocialLaunchRunbook, SocialMetricsLearningPacket,
  SocialTelegramPublishTargetProbe, SocialLaunchPreflight, SocialRuntimeStatus, SocialChannelReadiness, SocialChannelTargetSetup, SocialFirstApiProofDossier,
  SocialApiChannelPreflight, SocialChannelConnectionCheck, SocialPlanNextAction, SocialPlanNextStep, SocialGoalStage, SocialGoalProgress,
  SocialLaunchStage, SocialAttributionEventType, LearningMetricsPayload, ActionSummary, BulkNewsReview, BulkActionReview,
  SocialPreparePreview, SocialApprovalPreview, SocialApprovalPreviewSummary, SocialQueuePreview, SocialQueuePreviewSummary, NetworkOperatingSlice,
  OperatorInsight, ContentPlanTabProps, ContentMixKey, ContentMixState, ItemFilterKey, SignalFilterKey,
  ViewPresetKey, QuickActionKey, ContentPlanZone, ContentPlanMode, ContentLanguageKey
} from './modules/types';
import {
  SocialLaunchChecklist, SocialOwnerLaunchPath, _isSupervisedPlatform, _isSocialPostTextLocked, _socialSupervisedPayload, _socialOpenClawReadinessDetails,
  _socialLaunchStageStatusLabel, _normalizeSocialGoalStage, _normalizeSocialGoalStageStatus, _socialLaunchStageTone, _socialOpenClawReadinessOperational, _socialOpenClawReadinessTitle,
  _socialOpenClawOwnerCheckSummary, _socialOpenClawCapabilityLine, _socialSupervisedHandoffStateLabel, _socialApiQueueWarnings, _socialApprovalPostText, _socialApprovalSummary,
  _socialQueueSummary, _socialSupervisedSafetySummary, _socialSupervisedSafetyActionLabel, _normalizeSocialChannelFilter, _socialChannelFilterLabel, _matchesChannelFilter,
  _socialPlatformLabel, _socialMetricsSourceText, _socialSettingsPathForPlatform, _socialChannelSetupSort, _socialChannelConnectionStateLabel, _socialWorkerEnvLines,
  _socialLaunchRunbookBlock, _socialLaunchRunbookClipboardLines, _socialFirstCycleVerificationBlock, _socialPublishModeLabel, _socialStatusLabel, _socialStatusClassName,
  _socialPublishEvidenceClassName, _socialProofQualityLabel, _socialLearningReadinessClassName, _socialLearningConfidenceLabel, _socialLearningChecklistStatusLabel, _socialNextActionLabel,
  _socialItemQueueSummary, _socialDispatchActionLabel, _socialDispatchReasonLabel, _socialInsightMetricLine, _socialAttributionFeedback, _socialQueueGroupLabel,
  _socialQueueGroupNextAction, _contentTypeLabel, _scopeChipLabel, _locationScopeLabel, _planTargetLabel, _itemLocationLabel,
  _locationLabelByKey, _bulkResultText, _bulkResultDetails, _learningCapabilityLabel, _networkQualityReasonLabel, _networkRiskLabel,
  _networkOperatingRecommendation, _itemFilterLabel, _planItemStatus, _humanizePlanTitle, _humanizePlanGoal, _cleanTechnicalPlanText,
  _matchesItemFilter, _matchesDateRange, _signalFilterLabel, _sourceKindLabel, _seoViewsLabel, _matchesSignalFilter,
  _matchesItemLocationFilter, _readStoredSortMode, _readStoredPreferences, _writeStoredPreferences, _isValidItemFilterKey, _isValidContentLanguageKey,
  _normalizeContentLanguage, _isValidSignalFilterKey, _isValidViewPresetKey, _inferViewPresetKey, _shiftIsoDate, _autoScheduledDate,
  _inputDateValue, _removeRecordKeys, _formatPlanItemDate, _itemPriorityRank, _weekBucketKey, _weekBucketLabel
} from './modules/helpers';
import { ContentOverviewView } from './modules/ContentOverviewView';
import { ContentPlanView } from './modules/ContentPlanView';
import { ContentQueueView } from './modules/ContentQueueView';
import { createCoreActions } from './modules/createCoreActions';
import { createSocialActions } from './modules/createSocialActions';
import { createPlanActions } from './modules/createPlanActions';
import {
  PERIOD_OPTIONS, DENSITY_OPTIONS, CONTENT_MIX_OPTIONS, CONTENT_LANGUAGE_OPTIONS, ITEM_FILTER_OPTIONS, SIGNAL_FILTER_OPTIONS,
  CONTENT_PLAN_PREFERENCES_KEY
} from './modules/constants';

interface KnowledgeFoundationItem {
  assertion_id: string;
  label: string;
  excerpt?: string;
  source_title?: string;
}

interface KnowledgeFoundationGroup {
  type: string;
  label: string;
  description: string;
  items: KnowledgeFoundationItem[];
}


























































































































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
  const [knowledgeFoundations, setKnowledgeFoundations] = useState<KnowledgeFoundationGroup[]>([]);
  const [selectedKnowledgeType, setSelectedKnowledgeType] = useState('');
  const [selectedKnowledgeAssertionId, setSelectedKnowledgeAssertionId] = useState('');
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
  const [selectedChannelFilter, setSelectedChannelFilter] = useState<'all' | 'social' | 'maps'>('all');
  const [dateFromFilter, setDateFromFilter] = useState('');
  const [dateToFilter, setDateToFilter] = useState('');
  const [sortMode, setSortMode] = useState<'priority' | 'date'>('date');
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
  const [socialPostsByItem, setSocialPostsByItem] = useState<Record<string, SocialPost[]>>({});
  const [socialSummary, setSocialSummary] = useState<SocialPostsSummary | null>(null);
  const [socialQueueGroups, setSocialQueueGroups] = useState<SocialQueueGroup[]>([]);
  const [socialChannelReadiness, setSocialChannelReadiness] = useState<SocialChannelReadiness[]>([]);
  const [socialApiPreflight, setSocialApiPreflight] = useState<SocialApiChannelPreflight[]>([]);
  const [socialOpenClawReadiness, setSocialOpenClawReadiness] = useState<SocialOpenClawReadiness | null>(null);
  const [socialRecommendation, setSocialRecommendation] = useState<SocialRecommendationPayload | null>(null);
  const [socialGoalProgress, setSocialGoalProgress] = useState<SocialGoalProgress | null>(null);
  const [socialFirstApiProofDossier, setSocialFirstApiProofDossier] = useState<SocialFirstApiProofDossier | null>(null);
  const [socialRecommendationApproved, setSocialRecommendationApproved] = useState(false);
  const [socialDispatchPreview, setSocialDispatchPreview] = useState<SocialDispatchPreview | null>(null);
  const [socialDispatchExecutionReport, setSocialDispatchExecutionReport] = useState<SocialDispatchExecutionReport | null>(null);
  const [socialMetricsLearningPacket, setSocialMetricsLearningPacket] = useState<SocialMetricsLearningPacket | null>(null);
  const [socialLaunchPreflight, setSocialLaunchPreflight] = useState<SocialLaunchPreflight | null>(null);
  const [socialTelegramPublishTargetProbe, setSocialTelegramPublishTargetProbe] = useState<SocialTelegramPublishTargetProbe | null>(null);
  const [socialRuntimeStatus, setSocialRuntimeStatus] = useState<SocialRuntimeStatus | null>(null);
  const [socialPostsLoading, setSocialPostsLoading] = useState(false);
  const [socialTextEdits, setSocialTextEdits] = useState<Record<string, string>>({});
  const [manualPublishRefs, setManualPublishRefs] = useState<Record<string, { url: string; id: string }>>({});
  const [socialPublishRehearsals, setSocialPublishRehearsals] = useState<Record<string, SocialPublishRehearsal>>({});
  const [socialBulkPublishRehearsal, setSocialBulkPublishRehearsal] = useState<SocialPublishRehearsalBulk | null>(null);
  const [socialPreparePreview, setSocialPreparePreview] = useState<SocialPreparePreview | null>(null);
  const [socialApprovalPreview, setSocialApprovalPreview] = useState<SocialApprovalPreview | null>(null);
  const [socialQueuePreview, setSocialQueuePreview] = useState<SocialQueuePreview | null>(null);
  const [socialBusyAction, setSocialBusyAction] = useState('');
  const [activeZone, setActiveZone] = useState<ContentPlanZone>('overview');
  const [contentMode, setContentMode] = useState<ContentPlanMode>('point');
  const [contentLanguage, setContentLanguage] = useState<ContentLanguageKey>(() => _normalizeContentLanguage(language));
  const [selectedQueueItemId, setSelectedQueueItemId] = useState('');
  const [editorItemId, setEditorItemId] = useState('');
  const [queueSearch, setQueueSearch] = useState('');
  const [showSelectedItemDetails, setShowSelectedItemDetails] = useState(false);
  const [selectedItemIds, setSelectedItemIds] = useState<Record<string, boolean>>({});
  const [showRecentPlans, setShowRecentPlans] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!businessId) {
      setKnowledgeFoundations([]);
      return () => {
        cancelled = true;
      };
    }
    const loadKnowledgeFoundations = async () => {
      try {
        const response = await newAuth.makeRequest(
          `/business/${encodeURIComponent(businessId)}/knowledge/content-foundations?limit=4`,
          { method: 'GET' },
        );
        if (!cancelled) {
          setKnowledgeFoundations(Array.isArray(response.foundations) ? response.foundations : []);
        }
      } catch {
        if (!cancelled) setKnowledgeFoundations([]);
      }
    };
    void loadKnowledgeFoundations();
    return () => {
      cancelled = true;
    };
  }, [businessId]);

  const allowedHorizons = useMemo(() => context?.subscription?.allowed_horizons || [30], [context?.subscription?.allowed_horizons]);
  const scopeOptions = useMemo(() => context?.scope?.scope_options || [], [context?.scope?.scope_options]);
  const isNetworkContext = Boolean(context?.scope?.network?.is_network);
  const selectedScopeDescription = context?.scope?.selected_scope_description || '';
  const selectedScopeLabel = context?.scope?.selected_scope_label || '';
  const readiness = context?.readiness || null;
  const missingInputs = useMemo(() => (
    Array.isArray(readiness?.missing_inputs) ? readiness.missing_inputs : []
  ), [readiness?.missing_inputs]);
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
      .filter((item) => _matchesChannelFilter(item, socialPostsByItem, selectedChannelFilter))
      .filter((item) => _matchesDateRange(item.scheduled_for, dateFromFilter, dateToFilter))
      .filter((item) => {
        const query = queueSearch.trim().toLowerCase();
        if (!query) return true;
        return [
          item.theme,
          item.goal,
          item.draft_text,
          item.source_ref,
          item.seo_keyword,
          item.location_label,
        ].some((value) => String(value || '').toLowerCase().includes(query));
      })
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
        const dateDiff = _inputDateValue(left.scheduled_for).localeCompare(_inputDateValue(right.scheduled_for));
        if (dateDiff !== 0) return dateDiff;
        return String(left.theme || '').localeCompare(String(right.theme || ''));
      })
  ), [dateFromFilter, dateToFilter, filteredItems, queueSearch, recentGeneratedItemId, selectedChannelFilter, selectedWeekKey, socialPostsByItem, sortMode]);
  const selectedQueueItem = useMemo(() => (
    visibleItems.find((item) => item.id === selectedQueueItemId) || visibleItems[0] || null
  ), [selectedQueueItemId, visibleItems]);
  const editorItem = useMemo(() => (
    visibleItems.find((item) => item.id === editorItemId)
    || currentPlan?.items?.find((item) => item.id === editorItemId)
    || null
  ), [currentPlan?.items, editorItemId, visibleItems]);
  const itemFilterCounts = useMemo(() => {
    const items = currentPlan?.items || [];
    return ITEM_FILTER_OPTIONS.reduce<Record<ItemFilterKey, number>>((acc, filterKey) => {
      acc[filterKey] = items.filter((item) => _matchesItemFilter(item, filterKey)).length;
      return acc;
    }, {
      all: 0,
      urgent: 0,
      has_draft: 0,
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
  const selectedSocialPosts = useMemo(() => (
    selectedItems.flatMap((item) => socialPostsByItem[item.id] || [])
  ), [selectedItems, socialPostsByItem]);
  const selectedSocialNeedsReview = useMemo(() => (
    selectedSocialPosts.filter((post) => post.status === 'draft' || post.status === 'needs_review')
  ), [selectedSocialPosts]);
  const selectedSocialDirtyReviewPosts = useMemo(() => (
    selectedSocialNeedsReview.filter((post) => (
      Object.prototype.hasOwnProperty.call(socialTextEdits, post.id)
      && String(socialTextEdits[post.id] ?? '').trim() !== String(post.platform_text || '').trim()
    ))
  ), [selectedSocialNeedsReview, socialTextEdits]);
  const selectedSocialCanQueue = useMemo(() => (
    selectedSocialPosts.filter((post) => post.status === 'approved')
  ), [selectedSocialPosts]);
  const selectedSocialCanMarkPublished = useMemo(() => (
    selectedSocialPosts.filter((post) => post.status === 'needs_supervised_publish' || post.status === 'needs_manual_publish')
  ), [selectedSocialPosts]);
  const selectedSocialCanRecordResults = useMemo(() => (
    selectedSocialPosts.filter((post) => post.status === 'published')
  ), [selectedSocialPosts]);
  const allSocialPosts = useMemo(() => (
    Object.values(socialPostsByItem).flat()
  ), [socialPostsByItem]);
  const allSocialNeedsReview = useMemo(() => (
    allSocialPosts.filter((post) => post.status === 'draft' || post.status === 'needs_review')
  ), [allSocialPosts]);
  const allSocialCanQueue = useMemo(() => (
    allSocialPosts.filter((post) => post.status === 'approved')
  ), [allSocialPosts]);
  const visibleSocialPosts = useMemo(() => (
    visibleItems.flatMap((item) => socialPostsByItem[item.id] || [])
  ), [socialPostsByItem, visibleItems]);
  const socialMetricsSourceSummary = useMemo(() => {
    const byPlatform = new Map<string, { platform: string; label: string; posts: number; published: number; sourceRu: string; sourceEn: string }>();
    for (const post of visibleSocialPosts) {
      const platform = String(post.platform || '').trim();
      if (!platform) continue;
      const existing = byPlatform.get(platform) || {
        platform,
        label: post.platform_label || _socialPlatformLabel(platform, isRu),
        posts: 0,
        published: 0,
        sourceRu: _socialMetricsSourceText(platform, true),
        sourceEn: _socialMetricsSourceText(platform, false),
      };
      existing.posts += 1;
      if (post.status === 'published') existing.published += 1;
      byPlatform.set(platform, existing);
    }
    return Array.from(byPlatform.values()).sort((left, right) => left.label.localeCompare(right.label));
  }, [isRu, visibleSocialPosts]);
  const visibleSocialNeedsReview = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'draft' || post.status === 'needs_review')
  ), [visibleSocialPosts]);
  const visibleSocialCanQueue = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'approved')
  ), [visibleSocialPosts]);
  const visibleSocialNeedsSupervised = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'needs_supervised_publish')
  ), [visibleSocialPosts]);
  const visibleSocialNeedsManual = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'needs_manual_publish')
  ), [visibleSocialPosts]);
  const visibleSocialPublishedPosts = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'published')
  ), [visibleSocialPosts]);
  const visibleSocialPublishedWithoutPrimaryResult = useMemo(() => (
    visibleSocialPublishedPosts.filter((post) => Number(post.leads || 0) + Number(post.inquiries || 0) === 0)
  ), [visibleSocialPublishedPosts]);
  const socialResultSummary = useMemo(() => (
    visibleSocialPosts.reduce((acc, post) => {
      acc.leads += Number(post.leads || 0);
      acc.inquiries += Number(post.inquiries || 0);
      acc.comments += Number(post.comments || 0);
      acc.shares += Number(post.shares || 0);
      acc.clicks += Number(post.clicks || 0);
      acc.likes += Number(post.likes || 0);
      acc.views += Number(post.views || post.reach || 0);
      return acc;
    }, {
      leads: 0,
      inquiries: 0,
      comments: 0,
      shares: 0,
      clicks: 0,
      likes: 0,
      views: 0,
    })
  ), [visibleSocialPosts]);
  const socialPrimaryResultCount = socialResultSummary.leads + socialResultSummary.inquiries;
  const socialEarlySignalCount = socialResultSummary.comments + socialResultSummary.shares + socialResultSummary.clicks + socialResultSummary.likes + socialResultSummary.views;
  const socialLearningLoopStatus = useMemo(() => {
    const published = Number(socialSummary?.published || 0);
    const pending = Number(socialSummary?.needs_supervised_publish || 0) + Number(socialSummary?.needs_manual_publish || 0);
    const failed = Number(socialSummary?.failed || 0);
    if (failed > 0 || pending > 0) {
      return {
        action: 'open_results',
        tone: 'warning',
        titleRu: 'Сначала закрыть публикации',
        titleEn: 'Finish publishing first',
        textRu: `Нужно закрыть ручное/контролируемое размещение или ошибки: ${pending + failed}. После этого LocalOS сможет честно сравнить результат.`,
        textEn: `Manual/supervised placement or failures still need action: ${pending + failed}. After that, LocalOS can compare results honestly.`,
        ctaRu: 'Открыть публикации',
        ctaEn: 'Open posts',
      };
    }
    if (socialPrimaryResultCount > 0) {
      return {
        action: 'recommend',
        tone: 'success',
        titleRu: 'Есть главный результат',
        titleEn: 'Primary results recorded',
        textRu: `Заявки и обращения: ${socialPrimaryResultCount}. Можно предлагать изменения следующего плана, но применять только после подтверждения.`,
        textEn: `Leads and inquiries: ${socialPrimaryResultCount}. You can suggest next-plan changes, but apply only after approval.`,
        ctaRu: 'Предложить изменения',
        ctaEn: 'Suggest changes',
      };
    }
    if (socialEarlySignalCount > 0) {
      return {
        action: 'recommend',
        tone: 'caution',
        titleRu: 'Есть ранние сигналы',
        titleEn: 'Early signals recorded',
        textRu: `Ранние сигналы: ${socialEarlySignalCount}. Перед применением изменений отметьте заявки/обращения, если они были.`,
        textEn: `Early signals: ${socialEarlySignalCount}. Before applying changes, record leads/inquiries if any happened.`,
        ctaRu: 'Предложить изменения',
        ctaEn: 'Suggest changes',
      };
    }
    if (published > 0) {
      return {
        action: 'collect',
        tone: 'caution',
        titleRu: 'Нужно собрать реакции',
        titleEn: 'Collect reactions next',
        textRu: `Опубликовано: ${published}. Соберите реакции или отметьте заявки вручную, затем предложите изменения следующего плана.`,
        textEn: `Published: ${published}. Collect reactions or record leads manually, then suggest next-plan changes.`,
        ctaRu: 'Собрать реакции',
        ctaEn: 'Collect reactions',
      };
    }
    return {
      action: 'open_results',
      tone: 'neutral',
      titleRu: 'Результаты появятся после публикаций',
      titleEn: 'Results appear after publishing',
      textRu: 'Сначала подготовьте, утвердите и поставьте посты в расписание. После публикаций здесь появятся реакции, заявки и следующий шаг.',
      textEn: 'Prepare, approve, and queue posts first. After publishing, reactions, leads, and the next action will appear here.',
      ctaRu: 'Открыть очередь',
      ctaEn: 'Open queue',
    };
  }, [
    socialEarlySignalCount,
    socialPrimaryResultCount,
    socialSummary?.failed,
    socialSummary?.needs_manual_publish,
    socialSummary?.needs_supervised_publish,
    socialSummary?.published,
  ]);
  const socialDispatchEnabled = Boolean(socialRuntimeStatus?.dispatch?.enabled);
  const socialDispatchBlockedWithoutScope = Boolean(socialRuntimeStatus?.dispatch?.blocked_without_scope);
  const socialDispatchScopeMismatch = Boolean(
    socialRuntimeStatus?.dispatch?.scoped
    && businessId
    && String(socialRuntimeStatus.dispatch.business_scope || '').trim()
    && String(socialRuntimeStatus.dispatch.business_scope || '').trim() !== String(businessId || '').trim(),
  );
  const socialQueueExecutionNotice = useMemo(() => {
    if (socialDispatchBlockedWithoutScope) {
      return {
        tone: 'warning',
        titleRu: 'Расписание включено, но остановлено защитой',
        titleEn: 'Dispatch is enabled but guarded',
        textRu: 'LocalOS не запустит публикации, пока не выбран конкретный бизнес для первого цикла. Укажите SOCIAL_POST_DISPATCH_BUSINESS_ID для тестового бизнеса или включите явное allow-all.',
        textEn: 'LocalOS will not publish until a business scope is set. Set SOCIAL_POST_DISPATCH_BUSINESS_ID for the test business or enable explicit allow-all.',
      };
    }
    if (socialDispatchScopeMismatch) {
      return {
        tone: 'warning',
        titleRu: 'Расписание включено для другого бизнеса',
        titleEn: 'Dispatch is scoped to another business',
        textRu: `Исполнитель расписания сейчас ограничен бизнесом ${String(socialRuntimeStatus?.dispatch?.business_scope || '')}. Посты этого бизнеса можно готовить и ставить в расписание, но они не уйдут, пока область запуска не совпадёт.`,
        textEn: `The worker is currently scoped to business ${String(socialRuntimeStatus?.dispatch?.business_scope || '')}. You can prepare and queue this business posts, but they will not publish until the scope matches.`,
      };
    }
    if (socialDispatchEnabled) {
      return {
        tone: 'ok',
        titleRu: 'Публикация по расписанию включена',
        titleEn: 'Publishing worker is enabled',
        textRu: 'Посты в расписании будут обработаны по дате: API-каналы уйдут через подключённые интеграции, карты перейдут в контролируемое или ручное размещение.',
        textEn: 'Scheduled posts will be processed by date: API channels use adapters, maps move to supervised placement or manual handoff.',
      };
    }
    return {
      tone: 'warning',
      titleRu: 'Публикация по расписанию сейчас выключена',
      titleEn: 'Publishing worker is currently disabled',
      textRu: 'Можно готовить, проверять и ставить посты в расписание, но исполнение не начнётся до включения фонового запуска. Для Яндекс/2ГИС останется контролируемое или ручное размещение.',
      textEn: 'You can prepare, review, and queue posts, but automatic execution will not start until dispatch is enabled. Yandex/2GIS remain supervised handoff.',
    };
  }, [socialDispatchBlockedWithoutScope, socialDispatchEnabled, socialDispatchScopeMismatch, socialRuntimeStatus?.dispatch?.business_scope]);
  const socialQueueResultSummary = (selectedOnly: boolean) => {
    const subjectRu = selectedOnly ? 'Выбранные публикации поставлены в расписание.' : 'Утверждённые публикации поставлены в расписание.';
    const subjectEn = selectedOnly ? 'Selected posts are queued.' : 'Approved posts are queued.';
    if (socialDispatchBlockedWithoutScope) {
      return {
        tone: 'success',
        text_ru: `${subjectRu} Расписание сохранено, но LocalOS не запустит внешнее исполнение без SOCIAL_POST_DISPATCH_BUSINESS_ID или явного allow-all.`,
        text_en: `${subjectEn} The queue is saved, but LocalOS will not start the external worker without SOCIAL_POST_DISPATCH_BUSINESS_ID or explicit allow-all.`,
      };
    }
    if (socialDispatchScopeMismatch) {
      return {
        tone: 'success',
        text_ru: `${subjectRu} Расписание сохранено, но текущий исполнитель смотрит другой business scope и не обработает эти посты.`,
        text_en: `${subjectEn} The queue is saved, but the current worker is scoped to another business and will not process these posts.`,
      };
    }
    if (socialDispatchEnabled) {
      return {
        tone: 'success',
        text_ru: `${subjectRu} Исполнитель обработает их по дате: API-каналы пойдут через интеграции, Яндекс/2ГИС - в контролируемое размещение.`,
        text_en: `${subjectEn} The worker will process them on schedule: API channels use adapters, Yandex/2GIS move to supervised placement.`,
      };
    }
    return {
      tone: 'success',
      text_ru: `${subjectRu} Фоновый запуск выключен: расписание сохранено, но внешнее исполнение начнётся только после включения исполнителя.`,
      text_en: `${subjectEn} Dispatch is disabled: the queue is saved, but external execution starts only after the worker is enabled.`,
    };
  };
  const socialPlanNextStep = useMemo<SocialPlanNextStep>(() => {
    if (!currentPlan?.items?.length) {
      return {
        action: 'none',
        titleRu: 'Сначала нужен контент-план',
        titleEn: 'Start with a content plan',
        descriptionRu: 'После создания плана здесь появится очередь постов для карт и соцсетей.',
        descriptionEn: 'After creating a plan, this area will show map and social posts.',
        ctaRu: 'Создать план',
        ctaEn: 'Create plan',
        count: 0,
        disabled: true,
      };
    }
    if (Number(socialSummary?.total || 0) === 0) {
      return {
        action: 'prepare',
        titleRu: 'Подготовьте посты для каналов',
        titleEn: 'Prepare channel posts',
        descriptionRu: 'LocalOS разложит темы на Яндекс Карты, 2ГИС, Google, Telegram, VK, Instagram и Facebook. Наружу ничего не отправится.',
        descriptionEn: 'LocalOS will split topics into Yandex Maps, 2GIS, Google, Telegram, VK, Instagram, and Facebook. Nothing is sent externally.',
        ctaRu: selectedItems.length > 0 ? 'Подготовить выбранные' : 'Подготовить ближайшие темы',
        ctaEn: selectedItems.length > 0 ? 'Prepare selected' : 'Prepare nearest topics',
        count: selectedItems.length || Math.min(visibleItems.length, 5),
        disabled: visibleItems.length === 0,
      };
    }
    if (visibleSocialNeedsReview.length > 0) {
      return {
        action: 'review',
        titleRu: 'Проверьте тексты перед подтверждением',
        titleEn: 'Review copy before approval',
        descriptionRu: 'Это безопасный предпросмотр: текст можно поправить, а внешняя публикация ещё не запускается.',
        descriptionEn: 'This is the safe preview step: copy can be edited and external publishing is not started yet.',
        ctaRu: 'Открыть на проверку',
        ctaEn: 'Open review',
        count: visibleSocialNeedsReview.length,
      };
    }
    if (visibleSocialCanQueue.length > 0) {
      return {
        action: 'queue',
        titleRu: socialDispatchBlockedWithoutScope
          ? 'Поставьте в расписание, затем выберите бизнес для запуска'
          : socialDispatchScopeMismatch
            ? 'Поставьте в расписание, затем исправьте область запуска'
            : socialDispatchEnabled ? 'Поставьте утверждённое в расписание' : 'Поставьте в расписание, затем включите фоновый запуск',
        titleEn: socialDispatchBlockedWithoutScope
          ? 'Queue posts, then set business scope'
          : socialDispatchScopeMismatch
            ? 'Queue posts, then fix dispatch scope'
            : socialDispatchEnabled ? 'Queue approved posts' : 'Queue posts, then enable dispatch',
        descriptionRu: socialDispatchBlockedWithoutScope
          ? 'Расписание зафиксирует подтверждение и даты, но исполнитель не начнёт внешние действия, пока фоновый запуск включён без SOCIAL_POST_DISPATCH_BUSINESS_ID.'
          : socialDispatchScopeMismatch
            ? 'Расписание зафиксирует подтверждение и даты, но исполнитель сейчас смотрит другой бизнес и не обработает эти посты.'
            : socialDispatchEnabled
              ? 'Исполнитель сможет по дате отправить API-каналы, а карты перевести в контролируемое размещение.'
              : 'Расписание зафиксирует подтверждение и даты, но внешнее исполнение не стартует, пока фоновый запуск выключен.',
        descriptionEn: socialDispatchBlockedWithoutScope
          ? 'Queueing records approval and dates, but the worker will not start external actions while dispatch is enabled without SOCIAL_POST_DISPATCH_BUSINESS_ID.'
          : socialDispatchScopeMismatch
            ? 'Queueing records approval and dates, but the worker is scoped to another business and will not process these posts.'
            : socialDispatchEnabled
              ? 'The worker can publish API channels on schedule and move maps to supervised placement.'
              : 'Queueing records approval and dates, but external execution will not start while worker dispatch is disabled.',
        ctaRu: 'Поставить в расписание',
        ctaEn: 'Queue on schedule',
        count: visibleSocialCanQueue.length,
      };
    }
    if (visibleSocialNeedsSupervised.length > 0) {
      return {
        action: 'supervised',
        titleRu: 'Завершите контролируемое размещение',
        titleEn: 'Finish supervised placement',
        descriptionRu: 'Яндекс/2ГИС не считаются стабильным API publish. Откройте задачу, проверьте текст и отметьте размещение.',
        descriptionEn: 'Yandex/2GIS are not treated as stable API publish. Open the task, verify copy, and mark placement.',
        ctaRu: 'Открыть задачу',
        ctaEn: 'Open task',
        count: visibleSocialNeedsSupervised.length,
      };
    }
    if (visibleSocialNeedsManual.length > 0) {
      return {
        action: 'manual',
        titleRu: 'Подключите канал или разместите вручную',
        titleEn: 'Connect the channel or publish manually',
        descriptionRu: 'Этот статус означает не OpenClaw-задачу, а отсутствие ключей/прав или ручной режим. Исправьте подключение либо отметьте размещение вручную.',
        descriptionEn: 'This status is not an OpenClaw task: keys/permissions are missing or manual fallback is needed. Fix the connection or mark manual placement.',
        ctaRu: 'Открыть публикацию',
        ctaEn: 'Open post',
        count: visibleSocialNeedsManual.length,
      };
    }
    if (Number(socialSummary?.published || 0) > 0) {
      if (!socialPrimaryResultCount && !socialEarlySignalCount && !socialRecommendation?.learning_readiness) {
        return {
          action: 'collect',
          titleRu: 'Соберите реакции после публикаций',
          titleEn: 'Collect reactions after publishing',
          descriptionRu: 'Опубликованные посты уже есть. Сначала обновите реакции и ручные заявки, затем LocalOS предложит изменения следующей недели.',
          descriptionEn: 'Published posts exist. First update reactions and manual leads, then LocalOS will suggest next-week changes.',
          ctaRu: 'Собрать реакции',
          ctaEn: 'Collect reactions',
          count: Number(socialSummary?.published || 0),
        };
      }
      return {
        action: 'recommend',
        titleRu: 'Соберите выводы для следующего плана',
        titleEn: 'Collect next-plan learnings',
        descriptionRu: 'LocalOS сравнит заявки, обращения и реакции, но изменения в будущий план применит только после подтверждения.',
        descriptionEn: 'LocalOS compares leads, inquiries, and reactions, but applies next-plan changes only after approval.',
        ctaRu: 'Предложить изменения',
        ctaEn: 'Suggest changes',
        count: Number(socialSummary?.published || 0),
      };
    }
    if (Number(socialSummary?.scheduled || 0) > 0) {
      return {
        action: 'wait',
        titleRu: 'Публикации ждут дату',
        titleEn: 'Posts are waiting for schedule',
        descriptionRu: 'Исполнитель возьмёт только подтверждённые посты, когда наступит дата. Если канал не готов, конкретный пост получит понятный статус.',
        descriptionEn: 'The worker picks only due approved posts. If a channel is not ready, that post gets a clear status.',
        ctaRu: 'Обновить очередь',
        ctaEn: 'Refresh queue',
        count: Number(socialSummary?.scheduled || 0),
      };
    }
    return {
      action: 'none',
      titleRu: 'Очередь под контролем',
      titleEn: 'Queue is under control',
      descriptionRu: 'Подготовьте новые темы или дождитесь результатов опубликованных постов.',
      descriptionEn: 'Prepare new topics or wait for results from published posts.',
      ctaRu: 'Обновить',
      ctaEn: 'Refresh',
      count: Number(socialSummary?.total || 0),
    };
  }, [
    currentPlan?.items?.length,
    selectedItems.length,
    socialDispatchBlockedWithoutScope,
    socialDispatchEnabled,
    socialDispatchScopeMismatch,
    socialSummary?.published,
    socialSummary?.scheduled,
    socialSummary?.total,
    visibleItems.length,
    visibleSocialCanQueue.length,
    visibleSocialNeedsManual.length,
    visibleSocialNeedsReview.length,
    visibleSocialNeedsSupervised.length,
  ]);
  const socialReadinessSummary = useMemo(() => {
    let apiReady = 0;
    let needsAttention = 0;
    let supervisedOrManual = 0;
    const blockedApiChannels: SocialChannelReadiness[] = [];
    for (const channel of socialChannelReadiness) {
      const mode = String(channel.publish_mode || '').trim();
      if (mode === 'openclaw_browser' || mode === 'local_supervised_browser' || mode === 'manual') {
        supervisedOrManual += 1;
      }
      if (mode === 'api' && channel.ready) {
        apiReady += 1;
      }
      if (!channel.ready) {
        needsAttention += 1;
        if (mode === 'api') blockedApiChannels.push(channel);
      }
    }
    return {
      apiReady,
      needsAttention,
      supervisedOrManual,
      blockedApiChannels,
    };
  }, [socialChannelReadiness]);
  const socialOverviewChannelHighlights = useMemo(() => {
    return [...socialChannelReadiness]
      .sort((a, b) => {
        const aMode = String(a.publish_mode || '').trim();
        const bMode = String(b.publish_mode || '').trim();
        const aControlled = aMode === 'openclaw_browser' || aMode === 'local_supervised_browser' || aMode === 'manual';
        const bControlled = bMode === 'openclaw_browser' || bMode === 'local_supervised_browser' || bMode === 'manual';
        const aRank = !a.ready && aMode === 'api' ? 0 : aControlled ? 1 : a.ready ? 2 : 3;
        const bRank = !b.ready && bMode === 'api' ? 0 : bControlled ? 1 : b.ready ? 2 : 3;
        return aRank - bRank;
      })
      .slice(0, 4);
  }, [socialChannelReadiness]);
  const socialReadinessSetupPath = useMemo(() => {
    const firstBlocked = socialReadinessSummary.blockedApiChannels[0];
    if (!firstBlocked) return '/dashboard/settings?focus=integrations';
    return firstBlocked.settings_path || _socialSettingsPathForPlatform(String(firstBlocked.platform || ''));
  }, [socialReadinessSummary.blockedApiChannels]);
  const socialChannelConnectionGuide = useMemo(() => {
    const apiChannels = socialChannelReadiness
      .filter((channel) => String(channel.publish_mode || '').trim() === 'api')
      .sort(_socialChannelSetupSort);
    const readyApiChannels = apiChannels.filter((channel) => Boolean(channel.ready));
    const blockedApiChannels = apiChannels.filter((channel) => !Boolean(channel.ready));
    const supervisedChannels = socialChannelReadiness
      .filter((channel) => String(channel.publish_mode || '').trim() !== 'api')
      .sort(_socialChannelSetupSort);
    const firstBlocked = blockedApiChannels[0] || null;
    const quickStartCandidate = readyApiChannels.find((channel) => (
      String(channel.platform || '').trim() === 'telegram'
      || String(channel.platform || '').trim() === 'vk'
    )) || readyApiChannels[0] || null;
    const recommendedSetup = blockedApiChannels.find((channel) => (
      String(channel.platform || '').trim() === 'telegram'
      || String(channel.platform || '').trim() === 'vk'
    )) || firstBlocked;
    return {
      apiChannels,
      readyApiChannels,
      blockedApiChannels,
      supervisedChannels,
      firstBlocked,
      quickStartCandidate,
      recommendedSetup,
      readyToStart: readyApiChannels.length > 0,
    };
  }, [socialChannelReadiness]);
  const socialChannelReadinessByPlatform = useMemo(() => {
    const byPlatform: Record<string, SocialChannelReadiness> = {};
    for (const item of socialChannelReadiness) {
      const platform = String(item.platform || '').trim();
      if (platform) byPlatform[platform] = item;
    }
    return byPlatform;
  }, [socialChannelReadiness]);
  const socialApiPreflightByPlatform = useMemo(() => {
    const byPlatform: Record<string, SocialApiChannelPreflight> = {};
    for (const item of socialApiPreflight) {
      const platform = String(item.platform || '').trim();
      if (platform) byPlatform[platform] = item;
    }
    return byPlatform;
  }, [socialApiPreflight]);
  const socialApiPreflightSummary = useMemo(() => {
    const ready = socialApiPreflight.filter((item) => Boolean(item.ready));
    const needsAttention = socialApiPreflight.filter((item) => !Boolean(item.ready));
    return {
      checked: socialApiPreflight.length,
      ready,
      needsAttention,
    };
  }, [socialApiPreflight]);
  const socialFirstApiPublishReadiness = useMemo(() => {
    const apiChannels = socialChannelReadiness.filter((channel) => String(channel.publish_mode || '').trim() === 'api');
    const readyChannels = apiChannels.filter((channel) => Boolean(channel.ready));
    const blockedChannels = apiChannels.filter((channel) => !Boolean(channel.ready));
    const liveReady = socialApiPreflight.filter((item) => Boolean(item.ready));
    const liveBlocked = socialApiPreflight.filter((item) => !Boolean(item.ready));
    const primaryReady = liveReady.length > 0 ? liveReady : readyChannels;
    const primaryBlocked = liveBlocked.length > 0 ? liveBlocked : blockedChannels;
    const firstReady = primaryReady[0];
    const firstBlocked = primaryBlocked[0];
    const readyLabels = primaryReady.map((item) => String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)));
    const blockedLabels = primaryBlocked.map((item) => String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)));
    const fastStartPlatforms = ['telegram', 'vk'];
    const fastStartReady = primaryReady.filter((item) => fastStartPlatforms.includes(String(item.platform || '').trim()));
    const fastStartBlocked = primaryBlocked.filter((item) => fastStartPlatforms.includes(String(item.platform || '').trim()));
    const fastStartReadyLabels = fastStartReady.map((item) => String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)));
    const fastStartBlockedLabels = fastStartBlocked.map((item) => String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)));
    const setupFocus = fastStartBlocked[0] || firstBlocked;
    const setupFocusStepsSource = isRu
      ? setupFocus?.setup_steps_ru
      : setupFocus?.setup_steps_en;
    const setupFocusSteps = Array.isArray(setupFocusStepsSource)
      ? setupFocusStepsSource.filter(Boolean).map(String).slice(0, 4)
      : [];
    const setupFocusChecks = Array.isArray(setupFocus?.connection_checks)
      ? setupFocus.connection_checks.filter((item) => !Boolean(item.ok)).slice(0, 4)
      : [];
    const setupFocusMissingFields = Array.isArray(setupFocus?.missing_fields)
      ? setupFocus.missing_fields.filter(Boolean).map(String).slice(0, 4)
      : [];
    return {
      apiChannels,
      readyChannels,
      blockedChannels,
      liveReady,
      liveBlocked,
      firstReady,
      firstBlocked,
      readyLabels,
      blockedLabels,
      fastStartReady,
      fastStartBlocked,
      fastStartReadyLabels,
      fastStartBlockedLabels,
      setupFocus,
      setupFocusSteps,
      setupFocusChecks,
      setupFocusMissingFields,
      hasLiveCheck: socialApiPreflight.length > 0,
      readyForFirstApiPublish: primaryReady.length > 0 && primaryBlocked.length === 0,
      hasAnyReadyApi: primaryReady.length > 0,
    };
  }, [isRu, socialApiPreflight, socialChannelReadiness]);
  const socialFirstApiBlockerCard = useMemo(() => {
    const totalPosts = Number(socialSummary?.total || 0);
    const needsReview = Math.max(visibleSocialNeedsReview.length, Number(socialSummary?.needs_review || 0));
    const approvedNotQueued = visibleSocialCanQueue.length;
    const queued = Number(socialSummary?.scheduled || 0);
    const firstBlocked = socialFirstApiPublishReadiness.firstBlocked;
    const firstBlockedPlatform = String(firstBlocked?.platform || '').trim();
    const firstBlockedLabel = firstBlocked
      ? String(firstBlocked.platform_label || _socialPlatformLabel(firstBlockedPlatform, isRu))
      : 'Telegram';
    const firstBlockedStatus = String(firstBlocked?.status || '').trim();
    const channelLineRu = socialFirstApiPublishReadiness.hasAnyReadyApi
      ? `Канал: готово ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`
      : `Канал: ${firstBlockedLabel} - нужны ключи или права.`;
    const channelLineEn = socialFirstApiPublishReadiness.hasAnyReadyApi
      ? `Channel: ready ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`
      : `Channel: ${firstBlockedLabel} needs keys or permissions.`;
    const textLineRu = socialPostsLoading
      ? 'Посты: обновляем очередь публикаций по этому плану.'
      : totalPosts > 0
      ? `Посты: ${needsReview} на проверке, ${approvedNotQueued} утверждено, ${queued} в расписании.`
      : 'Посты: сначала подготовьте публикации из тем контент-плана.';
    const textLineEn = socialPostsLoading
      ? 'Posts: refreshing the publishing queue for this plan.'
      : totalPosts > 0
      ? `Posts: ${needsReview} in review, ${approvedNotQueued} approved, ${queued} queued.`
      : 'Posts: first prepare publications from content-plan topics.';
    let status: 'connect' | 'prepare' | 'review' | 'queue' | 'wait' | 'ready' = 'ready';
    let titleRu = 'Первый рабочий запуск почти готов';
    let titleEn = 'First working launch is almost ready';
    let nextRu = 'Проверьте запуск по расписанию и после публикации соберите реакции/заявки.';
    let nextEn = 'Check scheduled launch and collect reactions/leads after publishing.';
    let ctaRu = 'Проверить запуск';
    let ctaEn = 'Check launch';

    if (socialPostsLoading) {
      status = 'prepare';
      titleRu = 'Обновляем очередь публикаций';
      titleEn = 'Refreshing the publishing queue';
      nextRu = 'Подождите пару секунд: LocalOS сверяет готовые тексты, подтверждения и расписание.';
      nextEn = 'Wait a moment: LocalOS is checking prepared copy, approvals, and schedule.';
      ctaRu = 'Обновляем';
      ctaEn = 'Refreshing';
    } else if (!socialFirstApiPublishReadiness.hasAnyReadyApi) {
      status = 'connect';
      titleRu = 'Первый запуск ждёт подключение канала';
      titleEn = 'First launch is waiting for channel setup';
      const permissionsIssue = firstBlockedStatus.includes('permission') || firstBlockedStatus.includes('forbidden');
      nextRu = permissionsIssue
        ? `Проверьте права ${firstBlockedLabel}, затем вернитесь к проверке текстов и расписанию.`
        : `Подключите ${firstBlockedLabel}, затем вернитесь к проверке текстов и расписанию.`;
      nextEn = permissionsIssue
        ? `Check ${firstBlockedLabel} permissions, then return to copy review and queueing.`
        : `Connect ${firstBlockedLabel}, then return to copy review and queueing.`;
      ctaRu = 'Открыть настройку канала';
      ctaEn = 'Open channel setup';
    } else if (totalPosts === 0) {
      status = 'prepare';
      titleRu = 'Первый запуск ждёт подготовку постов';
      titleEn = 'First launch is waiting for post preparation';
      nextRu = 'Подготовьте каналы из ближайших тем; наружу на этом шаге ничего не отправится.';
      nextEn = 'Prepare channel posts from the next topics; nothing is sent externally at this step.';
      ctaRu = 'Подготовить посты';
      ctaEn = 'Prepare posts';
    } else if (needsReview > 0) {
      status = 'review';
      titleRu = 'Первый запуск ждёт проверку текстов';
      titleEn = 'First launch is waiting for copy review';
      nextRu = 'Откройте предпросмотр, поправьте текст и подтвердите публикации отдельной кнопкой.';
      nextEn = 'Open the preview, edit copy, and approve publications with a separate button.';
      ctaRu = 'Открыть проверку';
      ctaEn = 'Open review';
    } else if (approvedNotQueued > 0) {
      status = 'queue';
      titleRu = 'Первый запуск ждёт расписание';
      titleEn = 'First launch is waiting for queueing';
      nextRu = 'Поставьте утверждённые посты в расписание; исполнитель возьмёт их только по дате.';
      nextEn = 'Queue approved posts; the worker will pick them only when due.';
      ctaRu = 'Поставить в расписание';
      ctaEn = 'Queue on schedule';
    } else if (queued > 0) {
      status = 'wait';
      titleRu = 'Первый запуск ждёт дату публикации';
      titleEn = 'First launch is waiting for the publish date';
      nextRu = 'Когда наступит дата, API-каналы пойдут через интеграции, а Яндекс/2ГИС останутся контролируемыми.';
      nextEn = 'When due, API channels use integrations while Yandex/2GIS stay supervised.';
      ctaRu = 'Проверить запуск';
      ctaEn = 'Check launch';
    }

    return {
      status,
      tone: status === 'connect' || status === 'review' ? 'warning' : status === 'ready' || status === 'wait' ? 'success' : 'neutral',
      firstBlockedPlatform,
      titleRu,
      titleEn,
      factsRu: [
        channelLineRu,
        textLineRu,
        'Карты: Яндекс/2ГИС только через контролируемое размещение или ручной режим.',
      ],
      factsEn: [
        channelLineEn,
        textLineEn,
        'Maps: Yandex/2GIS only use supervised placement or manual mode.',
      ],
      nextRu,
      nextEn,
      ctaRu,
      ctaEn,
    };
  }, [
    isRu,
    socialFirstApiPublishReadiness.firstBlocked,
    socialFirstApiPublishReadiness.hasAnyReadyApi,
    socialFirstApiPublishReadiness.readyLabels,
    socialPostsLoading,
    socialSummary?.needs_review,
    socialSummary?.scheduled,
    socialSummary?.total,
    visibleSocialCanQueue.length,
    visibleSocialNeedsReview.length,
  ]);
  const selectedSocialQueueApiWarnings = useMemo(() => (
    _socialApiQueueWarnings(selectedSocialCanQueue, socialApiPreflightByPlatform, socialChannelReadinessByPlatform, isRu)
  ), [isRu, selectedSocialCanQueue, socialApiPreflightByPlatform, socialChannelReadinessByPlatform]);
  const socialApprovalPreviewSummary = useMemo(() => {
    if (!socialApprovalPreview) return null;
    return _socialApprovalSummary(socialApprovalPreview.posts, socialApiPreflightByPlatform, socialChannelReadinessByPlatform, isRu);
  }, [isRu, socialApiPreflightByPlatform, socialApprovalPreview, socialChannelReadinessByPlatform]);
  const socialQueuePreviewSummary = useMemo(() => {
    if (!socialQueuePreview) return null;
    return _socialQueueSummary(socialQueuePreview.posts, socialApiPreflightByPlatform, socialChannelReadinessByPlatform, isRu);
  }, [isRu, socialApiPreflightByPlatform, socialQueuePreview, socialChannelReadinessByPlatform]);
  const localSocialLaunchStages = useMemo<SocialLaunchStage[]>(() => {
    const totalPosts = Number(socialSummary?.total || 0);
    const needsReview = visibleSocialNeedsReview.length;
    const canQueue = visibleSocialCanQueue.length;
    const scheduled = Number(socialSummary?.scheduled || 0);
    const supervised = visibleSocialNeedsSupervised.length;
    const manual = visibleSocialNeedsManual.length;
    const published = Number(socialSummary?.published || 0);
    const failed = Number(socialSummary?.failed || 0);
    const hasPlan = Boolean(currentPlan?.items?.length);
    const hasRecommendation = Number(socialRecommendation?.proposed_changes?.length || 0) > 0;
    const channelsPrepared = totalPosts > 0;

    return [
      {
        key: 'plan',
        labelRu: 'План есть',
        labelEn: 'Plan exists',
        status: hasPlan ? 'done' : 'current',
        detailRu: hasPlan
          ? `Тем в плане: ${Number(currentPlan?.items?.length || 0)}`
          : 'Создайте контент-план, потом LocalOS разложит темы по каналам.',
        detailEn: hasPlan
          ? `Plan items: ${Number(currentPlan?.items?.length || 0)}`
          : 'Create a content plan, then LocalOS will split topics by channel.',
        count: Number(currentPlan?.items?.length || 0),
      },
      {
        key: 'channels',
        labelRu: channelsPrepared ? 'Каналы подготовлены' : 'Подготовить каналы',
        labelEn: channelsPrepared ? 'Channels prepared' : 'Prepare channels',
        status: !hasPlan ? 'pending' : channelsPrepared ? 'done' : 'current',
        detailRu: channelsPrepared
          ? `Публикаций по каналам: ${totalPosts}`
          : 'Нажмите “Подготовить каналы”, внешних публикаций на этом шаге нет.',
        detailEn: channelsPrepared
          ? `Channel posts: ${totalPosts}`
          : 'Click “Prepare channels”; no external publishing happens at this step.',
        count: totalPosts,
      },
      {
        key: 'review',
        labelRu: 'Тексты проверены',
        labelEn: 'Copy reviewed',
        status: totalPosts === 0 ? 'pending' : needsReview > 0 ? 'current' : 'done',
        detailRu: needsReview > 0
          ? `Нужно проверить перед подтверждением: ${needsReview}`
          : 'Предпросмотр и подтверждение отделены от постановки в расписание.',
        detailEn: needsReview > 0
          ? `Needs review before approval: ${needsReview}`
          : 'Preview and approval are separate from queueing.',
        count: needsReview,
      },
      {
        key: 'schedule',
        labelRu: 'Поставлено в расписание',
        labelEn: 'Queued on schedule',
        status: canQueue > 0
          ? 'current'
          : scheduled > 0 || published > 0 || supervised > 0 || manual > 0
            ? 'done'
            : totalPosts > 0
              ? 'pending'
              : 'pending',
        detailRu: canQueue > 0
          ? `Утверждено, но ещё не в расписании: ${canQueue}`
          : scheduled > 0
            ? `Ждёт даты публикации: ${scheduled}`
            : 'После подтверждения нажмите “Поставить в расписание”.',
        detailEn: canQueue > 0
          ? `Approved but not queued: ${canQueue}`
          : scheduled > 0
            ? `Waiting for publish date: ${scheduled}`
            : 'After approval, click “Queue on schedule”.',
        count: canQueue || scheduled,
      },
      {
        key: 'execution',
        labelRu: 'Исполнение понятно',
        labelEn: 'Execution is clear',
        status: failed > 0
          ? 'attention'
          : supervised > 0 || manual > 0
            ? 'current'
            : published > 0
              ? 'done'
              : scheduled > 0
                ? 'current'
                : 'pending',
        detailRu: failed > 0
          ? `Есть ошибки: ${failed}. Откройте карточку и выберите повтор/ручной режим.`
          : supervised > 0
            ? `Яндекс/2ГИС ждут контролируемое размещение: ${supervised}`
            : manual > 0
              ? `Нужен ручной режим или подключение: ${manual}`
              : published > 0
                ? `Опубликовано: ${published}`
                : 'API уйдут по расписанию; карты останутся в контролируемом или ручном режиме.',
        detailEn: failed > 0
          ? `Failures: ${failed}. Open the post and retry or switch to manual mode.`
          : supervised > 0
            ? `Yandex/2GIS await supervised placement: ${supervised}`
            : manual > 0
              ? `Manual fallback or connection needed: ${manual}`
              : published > 0
                ? `Published: ${published}`
                : 'API channels run through the worker; maps stay supervised/manual.',
        count: failed || supervised || manual || published || scheduled,
      },
      {
        key: 'learning',
        labelRu: 'План улучшается',
        labelEn: 'Plan improves',
        status: hasRecommendation
          ? 'current'
          : published > 0
            ? 'current'
            : 'pending',
        detailRu: hasRecommendation
          ? 'Есть предложения к следующему плану. Применение только после подтверждения.'
          : published > 0
            ? 'Обновите реакции и заявки, затем предложите изменения следующей недели.'
            : 'После публикаций LocalOS ранжирует заявки и обращения выше охватов.',
        detailEn: hasRecommendation
          ? 'Next-plan changes are ready. Applying still requires confirmation.'
          : published > 0
            ? 'Update reactions and leads, then suggest next-week changes.'
            : 'After publishing, LocalOS ranks leads and inquiries above reach.',
        count: Number(socialRecommendation?.proposed_changes?.length || 0),
      },
    ];
  }, [
    currentPlan?.items?.length,
    socialRecommendation?.proposed_changes?.length,
    socialSummary?.failed,
    socialSummary?.published,
    socialSummary?.scheduled,
    socialSummary?.total,
    socialRecommendation?.learning_readiness,
    socialEarlySignalCount,
    socialPrimaryResultCount,
    visibleSocialCanQueue.length,
    visibleSocialNeedsManual.length,
    visibleSocialNeedsReview.length,
    visibleSocialNeedsSupervised.length,
  ]);
  const socialLaunchStages = useMemo<SocialLaunchStage[]>(() => {
    const apiStages = Array.isArray(socialGoalProgress?.stages) ? socialGoalProgress?.stages || [] : [];
    const normalizedStages = apiStages
      .map((stage) => _normalizeSocialGoalStage(stage))
      .filter((stage): stage is SocialLaunchStage => Boolean(stage));
    return normalizedStages.length > 0 ? normalizedStages : localSocialLaunchStages;
  }, [localSocialLaunchStages, socialGoalProgress?.stages]);
  const socialLaunchChecklistSummary = useMemo(() => {
    const done = socialLaunchStages.filter((stage) => stage.status === 'done').length;
    const attention = socialLaunchStages.filter((stage) => stage.status === 'attention').length;
    const current = socialLaunchStages.find((stage) => stage.status === 'attention')
      || socialLaunchStages.find((stage) => stage.status === 'current')
      || socialLaunchStages.find((stage) => stage.status === 'pending')
      || socialLaunchStages[socialLaunchStages.length - 1];
    return {
      done,
      total: socialLaunchStages.length,
      attention,
      current,
    };
  }, [socialLaunchStages]);
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
      key: 'ready',
      label: isRu ? 'Тексты готовы' : 'Drafts ready',
    },
    {
      key: 'urgent',
      label: isRu ? 'Срочное' : 'Urgent',
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
        title: isRu ? 'Открыть темы без текста' : 'Open empty topics',
        description: isRu
          ? 'Это не создаёт новый план. Откроется текущая очередь с темами, где ещё нет текста.'
          : 'This does not create a new plan. It opens the current queue items that still need text.',
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
    availableItemLocations.length,
    currentPlan,
    isRu,
    learningMetrics?.network_quality,
    locationWeekFocusSummary,
    planOperationalSummary.needsDraft,
    planOperationalSummary.readyToPublish,
    repeatTemplateCandidate,
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
        textRu: `${planOperationalSummary.readyToPublish} черновиков уже готовы как текст. Следующий шаг — разложить их по каналам и проверить предпросмотр.`,
        textEn: `${planOperationalSummary.readyToPublish} drafts are ready as copy. Next, turn them into channel posts and review the preview.`,
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

  const actionRefs: Record<string, (...args: any[]) => any> = {};
  const controllerScope = {
    businessId, navigate, language, isRu, context, setContext, plans, setPlans,
    currentPlan, setCurrentPlan, loading, setLoading, generating, setGenerating, metricsLoading, setMetricsLoading,
    error, setError, learningMetrics, setLearningMetrics, selectedScopeKey, setSelectedScopeKey, selectedPeriod, setSelectedPeriod,
    selectedDensity, setSelectedDensity, contentMix, setContentMix, knowledgeFoundations, selectedKnowledgeType, setSelectedKnowledgeType,
    selectedKnowledgeAssertionId, setSelectedKnowledgeAssertionId, draftEdits, setDraftEdits, themeEdits, setThemeEdits,
    dateEdits, setDateEdits, busyItemId, setBusyItemId, bulkBusyAction, setBulkBusyAction, actionSummary, setActionSummary,
    selectedItemFilter, setSelectedItemFilter, selectedSignalFilter, setSelectedSignalFilter, selectedPlanTargetKey, setSelectedPlanTargetKey, selectedItemLocationKey, setSelectedItemLocationKey,
    selectedWeekKey, setSelectedWeekKey, selectedChannelFilter, setSelectedChannelFilter, dateFromFilter, setDateFromFilter, dateToFilter, setDateToFilter,
    sortMode, setSortMode, selectedViewPreset, setSelectedViewPreset, lastFocusLocationKey, setLastFocusLocationKey, lastFocusWeekKey, setLastFocusWeekKey,
    showAdvancedControls, setShowAdvancedControls, showPlanSetupDetails, setShowPlanSetupDetails, showLearningDetails, setShowLearningDetails, showContextDetails, setShowContextDetails,
    bulkTargetDate, setBulkTargetDate, expandedDuplicateItemId, setExpandedDuplicateItemId, duplicateTargetSelections, setDuplicateTargetSelections, duplicateDateOverrides, setDuplicateDateOverrides,
    bulkNewsReview, setBulkNewsReview, bulkActionReview, setBulkActionReview, recentGeneratedItemId, setRecentGeneratedItemId, socialPostsByItem, setSocialPostsByItem,
    socialSummary, setSocialSummary, socialQueueGroups, setSocialQueueGroups, socialChannelReadiness, setSocialChannelReadiness, socialApiPreflight, setSocialApiPreflight,
    socialOpenClawReadiness, setSocialOpenClawReadiness, socialRecommendation, setSocialRecommendation, socialGoalProgress, setSocialGoalProgress, socialFirstApiProofDossier, setSocialFirstApiProofDossier,
    socialRecommendationApproved, setSocialRecommendationApproved, socialDispatchPreview, setSocialDispatchPreview, socialDispatchExecutionReport, setSocialDispatchExecutionReport, socialMetricsLearningPacket, setSocialMetricsLearningPacket,
    socialLaunchPreflight, setSocialLaunchPreflight, socialTelegramPublishTargetProbe, setSocialTelegramPublishTargetProbe, socialRuntimeStatus, setSocialRuntimeStatus, socialPostsLoading, setSocialPostsLoading,
    socialTextEdits, setSocialTextEdits, manualPublishRefs, setManualPublishRefs, socialPublishRehearsals, setSocialPublishRehearsals, socialBulkPublishRehearsal, setSocialBulkPublishRehearsal,
    socialPreparePreview, setSocialPreparePreview, socialApprovalPreview, setSocialApprovalPreview, socialQueuePreview, setSocialQueuePreview, socialBusyAction, setSocialBusyAction,
    activeZone, setActiveZone, contentMode, setContentMode, contentLanguage, setContentLanguage, selectedQueueItemId, setSelectedQueueItemId,
    editorItemId, setEditorItemId, queueSearch, setQueueSearch, showSelectedItemDetails, setShowSelectedItemDetails, selectedItemIds, setSelectedItemIds,
    showRecentPlans, setShowRecentPlans, allowedHorizons, scopeOptions, isNetworkContext, selectedScopeDescription, selectedScopeLabel, readiness,
    missingInputs, mapLinksCount, servicesCount, seoKeywordsCount, networkLocationsCount, hasSearchFoundation, hasOnlyServicesGap, networkHasSearchPlanFoundation,
    isNetworkMode, networkScopeOption, pointScopeOption, selectedScopeOption, filteredItems, availableWeeks, weekSummary, visibleItems,
    selectedQueueItem, editorItem, itemFilterCounts, signalFilterCounts, availableItemLocations, itemLocationSummary, locationOperationalSummary, availablePlanTargets,
    visiblePlans, bulkDraftCandidates, bulkNewsCandidates, selectedItems, selectedDraftCandidates, selectedNewsCandidates, selectedSocialPosts, selectedSocialNeedsReview,
    selectedSocialDirtyReviewPosts, selectedSocialCanQueue, selectedSocialCanMarkPublished, selectedSocialCanRecordResults, allSocialPosts, allSocialNeedsReview, allSocialCanQueue, visibleSocialPosts,
    socialMetricsSourceSummary, visibleSocialNeedsReview, visibleSocialCanQueue, visibleSocialNeedsSupervised, visibleSocialNeedsManual, visibleSocialPublishedPosts, visibleSocialPublishedWithoutPrimaryResult, socialResultSummary,
    socialPrimaryResultCount, socialEarlySignalCount, socialLearningLoopStatus, socialDispatchEnabled, socialDispatchBlockedWithoutScope, socialDispatchScopeMismatch, socialQueueExecutionNotice, socialQueueResultSummary,
    socialPlanNextStep, socialReadinessSummary, socialOverviewChannelHighlights, socialReadinessSetupPath, socialChannelConnectionGuide, socialChannelReadinessByPlatform, socialApiPreflightByPlatform, socialApiPreflightSummary,
    socialFirstApiPublishReadiness, socialFirstApiBlockerCard, selectedSocialQueueApiWarnings, socialApprovalPreviewSummary, socialQueuePreviewSummary, localSocialLaunchStages, socialLaunchStages, socialLaunchChecklistSummary,
    missingDateCandidates, planOperationalSummary, overviewRiskScore, repeatTemplateCandidate, viewPresets, activeLocationLabel, activeWeekLabel, locationWeekFocusSummary,
    networkOperatingSlices, quickActions, operatorQualityInsights, actionRefs
  };
  const coreActions = createCoreActions(controllerScope);
  const {
    loadPlans, openPlan, deletePlan, loadLearningMetrics, loadSocialRuntimeStatus, loadSocialPosts, loadContext, toggleMix,
    toggleSelectedItem, clearSelectedItems, generatePlan, saveItem, generateDraft, createNews, prepareSocialPosts, openSocialApprovalPreview,
    approveSocialPostItem, executeSocialApprovalPreview, saveSocialPostText, openSocialQueuePreview, queueSocialPostItem, executeSocialQueuePreview, markSocialPostPublished, rehearseSocialPostPublish,
    rehearseSelectedSocialPosts, markSupervisedPostBlocked, createSupervisedPostTask, checkOpenClawBrowserReadiness, checkApiChannelPreflight, checkTelegramPublishTargetProbe, copySocialPostText, copySocialWorkerEnv,
    recordSocialPostAttribution
  } = coreActions;
  const socialActions = createSocialActions({ ...controllerScope, ...coreActions });
  Object.assign(actionRefs, socialActions);
  const {
    openSocialPreparePreview, prepareSelectedSocialPosts, prepareSuggestedSocialPosts, executeSocialPreparePreview, approveSelectedSocialPosts, queueVisibleApprovedSocialPosts, queueSelectedSocialPosts, selectPublishedSocialPostsForResult,
    markSelectedSocialPostsPublished, recordSelectedSocialPostAttribution, fetchSocialPlanRecommendation, collectSocialPostMetricsForBusiness, previewSocialDispatch, checkSocialLaunchPreflight, runSocialDispatchOnce, recommendNextSocialPlan,
    applySocialPlanRecommendation, persistItemEdits
  } = socialActions;
  const planActions = createPlanActions({ ...controllerScope, ...coreActions, ...socialActions });
  const {
    deleteItem, runBulkGenerateDrafts, runSelectedGenerateDrafts, runSelectedCreateNews, runBulkCreateNews, runBulkAutofillDates, executeBulkNewsReview, executeBulkActionReview,
    resetViewState, applyViewPreset, applyLocationWeekFocus, getLocationWeekFocusItems, getDuplicateTargetLocationOptions, openDuplicateTargetPicker, toggleDuplicateTargetLocation, runLocationWeekFocusDrafts,
    runLocationWeekFocusNews, runLocationWeekSkip, runLocationWeekReschedule, runLocationWeekRescheduleToDate, runItemSkip, runItemReschedule, runItemDuplicate, runItemDuplicateToOtherLocations,
    runItemDuplicateToSelectedLocations, runQuickAction, runSocialPlanNextStep, openSocialPostsWaitingForReview, openSocialPostsWaitingForQueue, contentPlanZones
  } = planActions;
  const viewScope = {
    navigate, isRu, currentPlan, loading, bulkBusyAction, showLearningDetails, setShowLearningDetails, socialGoalProgress,
    socialFirstApiProofDossier, socialPostsLoading, socialBusyAction, activeZone, setActiveZone, readiness, socialLearningLoopStatus, socialPlanNextStep,
    socialReadinessSummary, socialOverviewChannelHighlights, socialReadinessSetupPath, socialFirstApiPublishReadiness, socialFirstApiBlockerCard, socialLaunchStages, socialLaunchChecklistSummary, planOperationalSummary,
    overviewRiskScore, operatorQualityInsights, checkOpenClawBrowserReadiness, collectSocialPostMetricsForBusiness, previewSocialDispatch, recommendNextSocialPlan, applyViewPreset, runSocialPlanNextStep,
    language, context, plans, generating, metricsLoading, error, learningMetrics, selectedScopeKey,
    setSelectedScopeKey, selectedPeriod, setSelectedPeriod, selectedDensity, setSelectedDensity, contentMix,
    knowledgeFoundations, selectedKnowledgeType, setSelectedKnowledgeType, selectedKnowledgeAssertionId, setSelectedKnowledgeAssertionId,
    selectedPlanTargetKey, setSelectedPlanTargetKey,
    showPlanSetupDetails, setShowPlanSetupDetails, showContextDetails, setShowContextDetails, contentLanguage, setContentLanguage, showRecentPlans, setShowRecentPlans,
    allowedHorizons, scopeOptions, isNetworkContext, selectedScopeDescription, selectedScopeLabel, missingInputs, mapLinksCount, servicesCount,
    seoKeywordsCount, networkLocationsCount, networkHasSearchPlanFoundation, selectedScopeOption, availablePlanTargets, visiblePlans, loadPlans, openPlan,
    deletePlan, loadContext, toggleMix, generatePlan, busyItemId, actionSummary, selectedViewPreset, bulkTargetDate,
    setBulkTargetDate, bulkNewsReview, setBulkNewsReview, bulkActionReview, setBulkActionReview, socialSummary, socialPreparePreview, setSocialPreparePreview,
    socialApprovalPreview, setSocialApprovalPreview, socialQueuePreview, setSocialQueuePreview, queueSearch, setQueueSearch, isNetworkMode, visibleItems,
    itemLocationSummary, selectedSocialCanRecordResults, visibleSocialNeedsReview, visibleSocialCanQueue, visibleSocialNeedsSupervised, visibleSocialNeedsManual, visibleSocialPublishedPosts, visibleSocialPublishedWithoutPrimaryResult,
    socialPrimaryResultCount, socialEarlySignalCount, socialDispatchEnabled, socialDispatchBlockedWithoutScope, socialDispatchScopeMismatch, socialApprovalPreviewSummary, socialQueuePreviewSummary, viewPresets,
    networkOperatingSlices, quickActions, executeSocialApprovalPreview, executeSocialQueuePreview, prepareSuggestedSocialPosts, executeSocialPreparePreview, selectPublishedSocialPostsForResult, executeBulkNewsReview,
    executeBulkActionReview, applyLocationWeekFocus, runLocationWeekFocusDrafts, runLocationWeekFocusNews, runLocationWeekSkip, runLocationWeekRescheduleToDate, runQuickAction, selectedItemFilter,
    setSelectedItemFilter, dateFromFilter, setDateFromFilter, dateToFilter, setDateToFilter, setSortMode, itemFilterCounts, resetViewState,
    businessId, socialDispatchPreview, socialDispatchExecutionReport, socialLaunchPreflight, socialTelegramPublishTargetProbe, socialRuntimeStatus, socialQueueExecutionNotice, checkTelegramPublishTargetProbe,
    copySocialWorkerEnv, checkSocialLaunchPreflight, runSocialDispatchOnce, openSocialPostsWaitingForReview, openSocialPostsWaitingForQueue, selectedChannelFilter, setSelectedChannelFilter, socialQueueGroups,
    socialChannelReadiness, socialApiPreflight, socialOpenClawReadiness, socialChannelConnectionGuide, socialApiPreflightByPlatform, socialApiPreflightSummary, checkApiChannelPreflight, socialRecommendation,
    socialRecommendationApproved, setSocialRecommendationApproved, socialMetricsLearningPacket, socialMetricsSourceSummary, applySocialPlanRecommendation, socialBulkPublishRehearsal, selectedItems, selectedDraftCandidates,
    selectedNewsCandidates, selectedSocialPosts, selectedSocialNeedsReview, selectedSocialDirtyReviewPosts, selectedSocialCanQueue, selectedSocialCanMarkPublished, selectedSocialQueueApiWarnings, clearSelectedItems,
    rehearseSelectedSocialPosts, prepareSelectedSocialPosts, approveSelectedSocialPosts, queueSelectedSocialPosts, markSelectedSocialPostsPublished, recordSelectedSocialPostAttribution, runSelectedGenerateDrafts, runSelectedCreateNews,
    draftEdits, setDraftEdits, themeEdits, setThemeEdits, dateEdits, setDateEdits, expandedDuplicateItemId, setExpandedDuplicateItemId,
    duplicateTargetSelections, duplicateDateOverrides, setDuplicateDateOverrides, recentGeneratedItemId, socialPostsByItem, socialTextEdits, setSocialTextEdits, manualPublishRefs,
    setManualPublishRefs, socialPublishRehearsals, setSelectedQueueItemId, setEditorItemId, showSelectedItemDetails, setShowSelectedItemDetails, selectedItemIds, selectedQueueItem,
    editorItem, availableItemLocations, toggleSelectedItem, saveItem, generateDraft, createNews, prepareSocialPosts, approveSocialPostItem,
    saveSocialPostText, queueSocialPostItem, markSocialPostPublished, rehearseSocialPostPublish, markSupervisedPostBlocked, createSupervisedPostTask, copySocialPostText, recordSocialPostAttribution,
    deleteItem, getDuplicateTargetLocationOptions, openDuplicateTargetPicker, toggleDuplicateTargetLocation, runItemSkip, runItemReschedule, runItemDuplicate, runItemDuplicateToOtherLocations,
    runItemDuplicateToSelectedLocations
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
              {isRu ? 'Новости, сторис и контент-план' : 'News, stories, and content plan'}
            </h4>
            <p className="max-w-3xl text-sm leading-6 text-slate-600">
              {isRu
                ? 'Один рабочий экран: понять состояние, собрать план, разобрать очередь и довести выбранную тему до публикации.'
                : 'One workspace: understand status, build the plan, work the queue, and turn one selected topic into a publication.'}
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
        <div className="grid gap-2 md:grid-cols-3">
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

      <ContentOverviewView scope={viewScope} />
      <ContentPlanView scope={viewScope} />
      <ContentQueueView scope={viewScope} />
    </div>
  );
}
