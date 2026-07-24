import { useEffect } from 'react';
import { newAuth } from '@/lib/auth_new';
import { _socialOpenClawReadinessDetails, _socialApprovalSummary, _socialWorkerEnvLines, _socialLaunchRunbookClipboardLines, _socialAttributionFeedback, _readStoredPreferences, _writeStoredPreferences, _isValidItemFilterKey, _isValidContentLanguageKey, _isValidViewPresetKey, _inferViewPresetKey, _removeRecordKeys, copyTextToClipboard } from './helpers';
import type { ScopeOption, SocialPost, SocialPublishRehearsalBulk, SocialRecommendationPayload, SocialAttributionEventType, ContentMixKey } from './types';

export const createCoreActions = (scope) => {
  const {
    businessId, language, isRu, context, setContext, plans, setPlans, currentPlan,
    setCurrentPlan, setLoading, setGenerating, setMetricsLoading, setError, setLearningMetrics, selectedScopeKey, setSelectedScopeKey,
    selectedPeriod, setSelectedPeriod, selectedDensity, contentMix, setContentMix, selectedKnowledgeType,
    selectedKnowledgeAssertionId, setDraftEdits, setThemeEdits, setDateEdits,
    setBusyItemId, setBulkBusyAction, setActionSummary, selectedItemFilter, setSelectedItemFilter, selectedSignalFilter, selectedPlanTargetKey, selectedItemLocationKey,
    selectedWeekKey, setSelectedWeekKey, dateFromFilter, setDateFromFilter, dateToFilter, setDateToFilter, sortMode, setSortMode,
    selectedViewPreset, setSelectedViewPreset, lastFocusLocationKey, setLastFocusLocationKey, lastFocusWeekKey, setLastFocusWeekKey, setRecentGeneratedItemId, setDraftGeneratingItemId, setSocialPostsByItem,
    setSocialSummary, setSocialQueueGroups, setSocialChannelReadiness, setSocialApiPreflight, setSocialOpenClawReadiness, setSocialRecommendation, setSocialGoalProgress, setSocialFirstApiProofDossier,
    setSocialRecommendationApproved, setSocialDispatchPreview, setSocialDispatchExecutionReport, socialLaunchPreflight, setSocialLaunchPreflight, setSocialTelegramPublishTargetProbe, setSocialRuntimeStatus, setSocialPostsLoading,
    socialTextEdits, manualPublishRefs, setManualPublishRefs, setSocialPublishRehearsals, setSocialBulkPublishRehearsal, setSocialPreparePreview, socialApprovalPreview, setSocialApprovalPreview,
    socialQueuePreview, setSocialQueuePreview, setSocialBusyAction, setActiveZone, contentMode, contentLanguage, setContentLanguage, selectedQueueItemId,
    setSelectedQueueItemId, editorItemId, setEditorItemId, setSelectedItemIds, setShowRecentPlans, scopeOptions, readiness, networkScopeOption,
    pointScopeOption, selectedScopeOption, availableWeeks, visibleItems, selectedSocialPosts, socialQueueResultSummary, socialChannelReadinessByPlatform, socialApiPreflightByPlatform, actionRefs
  } = scope;
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

  const openPlan = async (planId: string) => {
    if (!planId) return;
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}`, { method: 'GET' });
      setCurrentPlan(response.plan || null);
      setActiveZone('queue');
      setShowRecentPlans(true);
      setEditorItemId('');
      setSelectedQueueItemId('');
      clearSelectedItems();
      setDraftEdits({});
      setThemeEdits({});
      setDateEdits({});
    } catch (planError) {
      const message = planError instanceof Error ? planError.message : (isRu ? 'Не удалось открыть план' : 'Could not open plan');
      setError(message);
    }
  };

  const deletePlan = async (planId: string) => {
    if (!planId) return;
    const confirmed = typeof window === 'undefined' ? true : window.confirm(isRu
      ? 'Удалить выбранный контент-план целиком? Темы внутри плана тоже будут удалены.'
      : 'Delete this content plan entirely? All topics inside it will also be deleted.');
    if (!confirmed) return;
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}`, { method: 'DELETE' });
      const response = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(businessId || '')}`, {
        method: 'GET',
      });
      const nextPlans = Array.isArray(response.plans) ? response.plans : [];
      setPlans(nextPlans);
      if (currentPlan?.id === planId) {
        if (nextPlans.length > 0) {
          const fullPlanResponse = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(nextPlans[0].id)}`, {
            method: 'GET',
          });
          setCurrentPlan(fullPlanResponse.plan || null);
        } else {
          setCurrentPlan(null);
        }
      }
      setEditorItemId('');
      clearSelectedItems();
      setActionSummary({
        tone: 'success',
        text_ru: 'План удалён.',
        text_en: 'Plan deleted.',
      });
    } catch (deleteError) {
      const message = deleteError instanceof Error ? deleteError.message : (isRu ? 'Не удалось удалить план' : 'Could not delete plan');
      setError(message);
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

  const loadSocialRuntimeStatus = async () => {
    try {
      const response = await newAuth.makeRequest('/social-posts/runtime-status', {
        method: 'GET',
      });
      setSocialRuntimeStatus({
        dispatch: response.dispatch || {},
        metrics: response.metrics || {},
        approval_required: Boolean(response.approval_required),
        browser_final_click_allowed: Boolean(response.browser_final_click_allowed),
      });
    } catch {
      setSocialRuntimeStatus(null);
    }
  };

  const loadSocialPosts = async (planId: string) => {
    if (!planId) return;
    setSocialPostsLoading(true);
    try {
      const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}/social-posts`, {
        method: 'GET',
      });
      const posts = Array.isArray(response.posts) ? response.posts : [];
      const grouped: Record<string, SocialPost[]> = {};
      for (const post of posts) {
        const itemId = String(post.content_plan_item_id || '').trim();
        if (!itemId) continue;
        grouped[itemId] = [...(grouped[itemId] || []), post];
      }
      setSocialPostsByItem(grouped);
      setSocialSummary(response.summary || null);
      setSocialQueueGroups(Array.isArray(response.queue_groups) ? response.queue_groups : []);
      setSocialChannelReadiness(Array.isArray(response.channel_readiness) ? response.channel_readiness : []);
      setSocialGoalProgress(response.goal_progress && typeof response.goal_progress === 'object'
        ? response.goal_progress
        : null);
      setSocialFirstApiProofDossier(response.first_api_proof_dossier && typeof response.first_api_proof_dossier === 'object'
        ? response.first_api_proof_dossier
        : null);
      setSocialOpenClawReadiness(response.openclaw_browser_readiness && typeof response.openclaw_browser_readiness === 'object'
        ? response.openclaw_browser_readiness
        : null);
      setSocialRecommendation(response.recommendation || response.learning_readiness ? {
        recommendation: response.recommendation || {},
        learning_readiness: response.learning_readiness || undefined,
      } : null);
      setSocialRecommendationApproved(false);
    } catch {
      setSocialPostsByItem({});
      setSocialSummary(null);
      setSocialQueueGroups([]);
      setSocialChannelReadiness([]);
      setSocialGoalProgress(null);
      setSocialFirstApiProofDossier(null);
      setSocialOpenClawReadiness(null);
      setSocialRecommendation(null);
      setSocialRecommendationApproved(false);
      setSocialDispatchPreview(null);
      setSocialDispatchExecutionReport(null);
      setSocialLaunchPreflight(null);
    } finally {
      setSocialPostsLoading(false);
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
    void loadSocialRuntimeStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessId]);

  useEffect(() => {
    if (!currentPlan?.id) {
      setSocialPostsByItem({});
      setSocialSummary(null);
      setSocialQueueGroups([]);
      setSocialPostsLoading(false);
      return;
    }
    void loadSocialPosts(currentPlan.id);
  }, [currentPlan?.id]);

  useEffect(() => {
    if (!businessId) return;
    if (!selectedScopeKey) return;
    void loadContext(selectedScopeKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      if (editorItemId) setEditorItemId('');
      return;
    }
    if (selectedQueueItemId && visibleItems.some((item) => item.id === selectedQueueItemId)) return;
    setSelectedQueueItemId(visibleItems[0].id);
  }, [editorItemId, selectedQueueItemId, visibleItems]);

  useEffect(() => {
    if (!editorItemId) return;
    if (visibleItems.some((item) => item.id === editorItemId)) return;
    setEditorItemId('');
  }, [editorItemId, visibleItems]);

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
    if (typeof stored.dateFromFilter === 'string' && stored.dateFromFilter.trim()) {
      setDateFromFilter(stored.dateFromFilter.slice(0, 10));
    }
    if (typeof stored.dateToFilter === 'string' && stored.dateToFilter.trim()) {
      setDateToFilter(stored.dateToFilter.slice(0, 10));
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
    if (_isValidContentLanguageKey(stored.contentLanguage)) {
      setContentLanguage(stored.contentLanguage);
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
      dateFromFilter,
      dateToFilter,
      sortMode,
    }));
  }, [
    selectedItemFilter,
    selectedSignalFilter,
    selectedPlanTargetKey,
    selectedItemLocationKey,
    selectedWeekKey,
    dateFromFilter,
    dateToFilter,
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
      dateFromFilter,
      dateToFilter,
      sortMode,
      contentLanguage,
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
    dateFromFilter,
    dateToFilter,
    sortMode,
    contentLanguage,
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
    if (currentPlan?.items?.length && typeof window !== 'undefined') {
      const confirmed = window.confirm(isRu
        ? 'У вас уже есть контент-план. Создать новый план? Старый не удалится, но в списке появится ещё один план.'
        : 'You already have a content plan. Create a new one? The old plan will stay, but another plan will appear in the list.');
      if (!confirmed) {
        setActiveZone('queue');
        return;
      }
    }
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
          content_mix: {
            ...contentMix,
            knowledge_foundation: selectedKnowledgeAssertionId ? {
              type: selectedKnowledgeType || 'market_signal',
              assertion_ids: [selectedKnowledgeAssertionId],
            } : undefined,
          },
        }),
      });
      setCurrentPlan(response.plan || null);
      setActiveZone('queue');
      if (businessId) {
        const plansResponse = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(businessId)}`, {
          method: 'GET',
        });
        setPlans(Array.isArray(plansResponse.plans) ? plansResponse.plans : []);
      }
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
      await actionRefs.persistItemEdits(itemId);
    } finally {
      setBusyItemId('');
    }
  };

  const generateDraft = async (itemId: string) => {
    const startedAt = Date.now();
    setBusyItemId(itemId);
    setDraftGeneratingItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/generate-draft`, {
        method: 'POST',
        body: JSON.stringify({ language: contentLanguage }),
      });
      const remaining = Math.max(0, 3800 - (Date.now() - startedAt));
      if (remaining) await new Promise((resolve) => window.setTimeout(resolve, remaining));
      setCurrentPlan(response.plan || null);
      setDraftEdits((prev) => _removeRecordKeys(prev, [itemId]));
      setRecentGeneratedItemId(itemId);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Черновик сгенерирован для выбранной публикации.',
        text_en: 'Draft generated for the selected item.',
      });
      await new Promise((resolve) => window.setTimeout(resolve, 700));
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать черновик' : 'Could not generate draft');
      setError(message);
    } finally {
      setDraftGeneratingItemId('');
      setBusyItemId('');
    }
  };

  const createNews = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      await actionRefs.persistItemEdits(itemId);
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/create-news`, {
        method: 'POST',
        body: JSON.stringify({ language: contentLanguage }),
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

  const prepareSocialPosts = async (itemId: string) => {
    setSocialBusyAction(`prepare:${itemId}`);
    setError('');
    setActionSummary(null);
    try {
      await actionRefs.persistItemEdits(itemId);
      const item = visibleItems.find((planItem) => planItem.id === itemId)
        || currentPlan?.items?.find((planItem) => planItem.id === itemId);
      if (!item) {
        throw new Error(isRu ? 'Тема плана не найдена' : 'Plan item not found');
      }
      await actionRefs.openSocialPreparePreview([item], 'selected', `single-social-prepare:${itemId}`);
    } catch (socialError) {
      const message = socialError instanceof Error ? socialError.message : (isRu ? 'Не удалось подготовить каналы' : 'Could not prepare channels');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const openSocialApprovalPreview = (posts: SocialPost[], source: 'selected' | 'single', busyAction: string) => {
    const postIds = posts
      .map((post) => String(post.id || '').trim())
      .filter(Boolean);
    if (postIds.length === 0) return;
    setSocialPreparePreview(null);
    setSocialQueuePreview(null);
    setSocialApprovalPreview({
      key: `${source}:${postIds.join(':')}`,
      posts,
      postIds,
      busyAction,
      source,
    });
    setActionSummary({
      tone: 'neutral',
      text_ru: 'Предпросмотр подтверждения готов. Проверьте, что именно подтверждаете: это только проверка текста, без внешней публикации.',
      text_en: 'Approval preview is ready. Review exactly what you approve: this only confirms copy, without external publishing.',
    });
  };

  const approveSocialPostItem = (post: SocialPost) => {
    openSocialApprovalPreview([post], 'single', `approve:${post.id}`);
  };

  const executeSocialApprovalPreview = async () => {
    const preview = socialApprovalPreview;
    if (!preview || preview.postIds.length === 0) return;
    const summary = _socialApprovalSummary(preview.posts, socialApiPreflightByPlatform, socialChannelReadinessByPlatform, isRu);
    if (summary.emptyText > 0) {
      setActionSummary({
        tone: 'warning',
        text_ru: `Перед подтверждением заполните текст: ${summary.emptyText}. Пустой пост нельзя подтверждать к исполнению.`,
        text_en: `Add copy before approval: ${summary.emptyText}. Empty posts cannot be approved for execution.`,
      });
      return;
    }
    setBulkBusyAction(preview.busyAction);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/social-posts/bulk-approve', {
        method: 'POST',
        body: JSON.stringify({ post_ids: preview.postIds }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setSocialApprovalPreview(null);
      setActionSummary({
        tone: 'success',
        text_ru: preview.source === 'single'
          ? 'Пост подтверждён человеком. Внешняя публикация ещё не запускалась.'
          : 'Выбранные публикации подтверждены. Внешняя публикация ещё не запускалась.',
        text_en: preview.source === 'single'
          ? 'Post approved by a human. External publishing has not started yet.'
          : 'Selected posts approved. External publishing has not started yet.',
        details_ru: [
          'Следующий шаг - “Поставить в расписание”.',
          'API-каналы пойдут в исполнение только после постановки в расписание и даты публикации.',
          'Яндекс/2ГИС после постановки в расписание останутся контролируемым или ручным размещением.',
        ],
        details_en: [
          'Next step: “Queue on schedule”.',
          'API channels go to the worker only after queueing and the scheduled date.',
          'Yandex/2GIS stay supervised or manual after queueing.',
        ],
      });
    } catch (approveError) {
      const message = approveError instanceof Error ? approveError.message : (isRu ? 'Не удалось подтвердить публикацию' : 'Could not approve post');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const saveSocialPostText = async (post: SocialPost, fallbackText: string) => {
    const nextText = String(socialTextEdits[post.id] ?? post.platform_text ?? fallbackText ?? '').trim();
    setSocialBusyAction(`save-text:${post.id}`);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}`, {
        method: 'PATCH',
        body: JSON.stringify({
          platform_text: nextText,
          base_text: fallbackText,
        }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setActionSummary({
        tone: 'success',
        text_ru: 'Текст канала сохранён. Перед публикацией снова проверьте и подтвердите его.',
        text_en: 'Channel copy saved. Review and approve it again before publishing.',
      });
    } catch (saveError) {
      const message = saveError instanceof Error ? saveError.message : (isRu ? 'Не удалось сохранить текст канала' : 'Could not save channel copy');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const openSocialQueuePreview = (posts: SocialPost[], source: 'selected' | 'visible' | 'single', busyAction: string) => {
    const postIds = posts
      .map((post) => String(post.id || '').trim())
      .filter(Boolean);
    if (postIds.length === 0) return;
    setSocialPreparePreview(null);
    setSocialApprovalPreview(null);
    setSocialQueuePreview({
      key: `${source}:${postIds.join(':')}`,
      posts,
      postIds,
      busyAction,
      source,
    });
    setActionSummary({
      tone: 'neutral',
      text_ru: 'Предпросмотр расписания готов. Проверьте, что именно разрешаете выполнить по дате.',
      text_en: 'Queue preview is ready. Review exactly what you allow the worker to execute on schedule.',
    });
  };

  const queueSocialPostItem = (post: SocialPost) => {
    openSocialQueuePreview([post], 'single', `queue:${post.id}`);
  };

  const executeSocialQueuePreview = async () => {
    const preview = socialQueuePreview;
    if (!preview || preview.postIds.length === 0) return;
    setBulkBusyAction(preview.busyAction);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/social-posts/bulk-queue', {
        method: 'POST',
        body: JSON.stringify({ post_ids: preview.postIds }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setSocialQueuePreview(null);
      setActionSummary(socialQueueResultSummary(preview.source === 'selected' || preview.source === 'single'));
    } catch (queueError) {
      const message = queueError instanceof Error ? queueError.message : (isRu ? 'Не удалось поставить публикацию в расписание' : 'Could not queue post');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const markSocialPostPublished = async (post: SocialPost) => {
    setSocialBusyAction(`manual:${post.id}`);
    setError('');
    setActionSummary(null);
    const refs = manualPublishRefs[post.id] || { url: '', id: '' };
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/mark-manual-published`, {
        method: 'POST',
        body: JSON.stringify({
          provider_post_url: String(refs.url || '').trim(),
          provider_post_id: String(refs.id || '').trim(),
        }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setManualPublishRefs((prev) => {
        const next = { ...prev };
        delete next[post.id];
        return next;
      });
      setActionSummary({
        tone: 'success',
        text_ru: refs.url || refs.id
          ? 'Публикация отмечена как размещённая, ссылка/ID сохранены.'
          : 'Публикация отмечена как размещённая.',
        text_en: refs.url || refs.id
          ? 'Post marked as published and URL/ID saved.'
          : 'Post marked as published.',
      });
    } catch (manualError) {
      const message = manualError instanceof Error ? manualError.message : (isRu ? 'Не удалось отметить публикацию' : 'Could not mark post as published');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const rehearseSocialPostPublish = async (post: SocialPost) => {
    setSocialBusyAction(`rehearsal:${post.id}`);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/publish-rehearsal`, {
        method: 'POST',
      });
      const rehearsal = response.rehearsal && typeof response.rehearsal === 'object'
        ? response.rehearsal
        : {};
      setSocialPublishRehearsals((prev) => ({
        ...prev,
        [post.id]: rehearsal,
      }));
      const ready = Boolean(rehearsal.ready_for_execution);
      setActionSummary({
        tone: ready ? 'success' : 'warning',
        text_ru: String(rehearsal.summary_ru || (ready ? 'Проверка запуска пройдена.' : 'Проверка нашла блокер перед запуском.')),
        text_en: String(rehearsal.summary_en || (ready ? 'Launch check passed.' : 'The launch check found a blocker.')),
      });
    } catch (rehearsalError) {
      const message = rehearsalError instanceof Error ? rehearsalError.message : (isRu ? 'Не удалось проверить запуск публикации' : 'Could not check publish readiness');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const rehearseSelectedSocialPosts = async () => {
    const postIds = selectedSocialPosts
      .map((post) => String(post.id || '').trim())
      .filter(Boolean);
    if (postIds.length === 0) return;
    setBulkBusyAction('selected-social-rehearsal');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/social-posts/bulk-publish-rehearsal', {
        method: 'POST',
        body: JSON.stringify({ post_ids: postIds }),
      });
      const rehearsals = Array.isArray(response.rehearsals) ? response.rehearsals : [];
      const summary = response.summary && typeof response.summary === 'object' ? response.summary : {};
      const failed = Array.isArray(response.failed) ? response.failed : [];
      const bulkPayload: SocialPublishRehearsalBulk = {
        schema: String(response.schema || 'localos_social_publish_rehearsal_bulk_v1'),
        dry_run: Boolean(response.dry_run),
        external_publish_performed: Boolean(response.external_publish_performed),
        provider_write_performed: Boolean(response.provider_write_performed),
        rehearsals,
        failed,
        summary,
      };
      setSocialBulkPublishRehearsal(bulkPayload);
      setSocialPublishRehearsals((prev) => {
        const next = { ...prev };
        for (const rehearsal of rehearsals) {
          const postId = String(rehearsal.post_id || '').trim();
          if (postId) next[postId] = rehearsal;
        }
        return next;
      });
      const ready = Number(summary.ready || 0);
      const blocked = Number(summary.manual_or_blocked || 0);
      setActionSummary({
        tone: blocked > 0 ? 'warning' : 'success',
        text_ru: String(summary.message_ru || `Проверка выбранных завершена: готово ${ready}, требуют внимания ${blocked}.`),
        text_en: String(summary.message_en || `Selected launch check finished: ready ${ready}, need attention ${blocked}.`),
      });
    } catch (rehearsalError) {
      const message = rehearsalError instanceof Error ? rehearsalError.message : (isRu ? 'Не удалось проверить выбранные посты' : 'Could not check selected posts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const markSupervisedPostBlocked = async (post: SocialPost) => {
    setSocialBusyAction(`blocked:${post.id}`);
    setError('');
    setActionSummary(null);
    const reason = isRu
      ? 'Контролируемое размещение заблокировано: нужен ручной режим (логин, капча или изменённый интерфейс площадки).'
      : 'Supervised placement is blocked: manual fallback is needed (login, captcha, or changed platform UI).';
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/mark-supervised-blocked`, {
        method: 'POST',
        body: JSON.stringify({
          reason,
          blocked_source: 'localos_ui',
        }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setActionSummary({
        tone: 'warning',
        text_ru: 'Пост переведён в ручной режим. Текст и ссылка на площадку остались доступны, план не сорван.',
        text_en: 'Post moved to manual fallback. Copy and platform link remain available, and the plan is not blocked.',
      });
    } catch (blockedError) {
      const message = blockedError instanceof Error ? blockedError.message : (isRu ? 'Не удалось перевести пост в ручной режим' : 'Could not move post to manual fallback');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const createSupervisedPostTask = async (post: SocialPost) => {
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(
        isRu
          ? 'Подготовить контролируемое размещение для Яндекс/2ГИС? LocalOS соберёт текст, ссылку на площадку и инструкцию. Финальную кнопку публикации он не нажимает.'
          : 'Prepare supervised placement for Yandex/2GIS? LocalOS will prepare copy, the platform link, and instructions. It will not click the final publish button.'
      );
      if (!confirmed) return;
    }
    setSocialBusyAction(`supervised-task:${post.id}`);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/supervised-task`, {
        method: 'POST',
        body: JSON.stringify({ approved: true }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      const updatedPost = response.post && typeof response.post === 'object' ? response.post : {};
      const status = String(updatedPost.status || '').trim();
      setActionSummary({
        tone: status === 'needs_manual_publish' ? 'warning' : 'success',
        text_ru: status === 'needs_manual_publish'
          ? 'Контролируемое размещение подготовлено как ручной режим: браузерное размещение OpenClaw сейчас недоступно или не подтверждено.'
          : 'Контролируемое размещение подготовлено. Проверьте инструкцию, откройте площадку и завершите размещение только после проверки предпросмотра.',
        text_en: status === 'needs_manual_publish'
          ? 'Supervised placement was prepared as manual fallback: OpenClaw browser-use is unavailable or not confirmed.'
          : 'Supervised placement prepared. Review the instructions, open the platform, and finish placement only after preview review.',
      });
    } catch (taskError) {
      const message = taskError instanceof Error ? taskError.message : (isRu ? 'Не удалось подготовить контролируемое размещение' : 'Could not prepare supervised placement');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const checkOpenClawBrowserReadiness = async () => {
    if (!businessId) return;
    setSocialBusyAction('openclaw-check');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/social-posts/openclaw-browser-check`, {
        method: 'GET',
      });
      const readiness = response.openclaw_browser_readiness && typeof response.openclaw_browser_readiness === 'object'
        ? response.openclaw_browser_readiness
        : null;
      setSocialOpenClawReadiness(readiness);
      setActionSummary({
        tone: readiness?.ready ? 'success' : 'warning',
        text_ru: readiness?.ready
          ? 'Браузерное размещение OpenClaw подтверждено. Яндекс/2ГИС можно вести через контролируемое размещение без финального клика.'
          : 'Браузерное размещение OpenClaw не подтверждено. Яндекс/2ГИС останутся в ручном режиме, план не будет сорван.',
        text_en: readiness?.ready
          ? 'OpenClaw browser-use is confirmed. Yandex/2GIS can use supervised placement without the final click.'
          : 'OpenClaw browser-use is not confirmed. Yandex/2GIS will stay in manual fallback, and the plan will not be blocked.',
        details_ru: _socialOpenClawReadinessDetails(readiness, true),
        details_en: _socialOpenClawReadinessDetails(readiness, false),
      });
    } catch (checkError) {
      const message = checkError instanceof Error ? checkError.message : (isRu ? 'Не удалось проверить браузерное размещение OpenClaw' : 'Could not check OpenClaw browser-use');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const checkApiChannelPreflight = async () => {
    if (!businessId) return;
    setSocialBusyAction('api-channel-preflight');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/social-posts/api-channel-preflight`, {
        method: 'GET',
      });
      const preflight = Array.isArray(response.api_preflight) ? response.api_preflight : [];
      setSocialApiPreflight(preflight);
      const readyCount = Number(response.summary?.ready || 0);
      const attentionCount = Number(response.summary?.needs_attention || 0);
      setActionSummary({
        tone: attentionCount > 0 ? 'warning' : 'success',
        text_ru: attentionCount > 0
          ? `API-каналы проверены без публикации: готовы ${readyCount}, требуют внимания ${attentionCount}. Исправьте ключи/права до расписания.`
          : `API-каналы проверены без публикации: готовы ${readyCount}. Публикация всё равно начнётся только после подтверждения и расписания.`,
        text_en: attentionCount > 0
          ? `API channels checked without publishing: ready ${readyCount}, need attention ${attentionCount}. Fix keys/permissions before scheduling.`
          : `API channels checked without publishing: ready ${readyCount}. Publishing still starts only after approval and queueing.`,
      });
    } catch (preflightError) {
      const message = preflightError instanceof Error ? preflightError.message : (isRu ? 'Не удалось проверить API-каналы' : 'Could not check API channels');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const checkTelegramPublishTargetProbe = async () => {
    if (!businessId) return;
    setSocialBusyAction('telegram-publish-target-probe');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/business/telegram-bot/publish-target-probe', {
        method: 'POST',
        body: JSON.stringify({ business_id: businessId }),
      });
      const probe = response.probe && typeof response.probe === 'object'
        ? response.probe
        : {
          ready: Boolean(response.ready),
          status: response.status,
          message_ru: response.message_ru,
          message_en: response.message_en,
          next_action_ru: response.next_action_ru,
          next_action_en: response.next_action_en,
          target_summary_ru: response.target_summary_ru,
          target_summary_en: response.target_summary_en,
          external_post_published: response.external_post_published,
          send_message_performed: response.send_message_performed,
          target_evidence: response.target_evidence,
          checks: response.checks,
        };
      setSocialTelegramPublishTargetProbe(probe);
      setActionSummary({
        tone: probe.ready ? 'success' : 'warning',
        text_ru: probe.ready
          ? 'Telegram-цель проверена без отправки сообщений: можно готовить первый API-proof после preview, approval и расписания.'
          : 'Telegram-цель проверена без отправки сообщений: перед первым API-proof нужно исправить цель публикации.',
        text_en: probe.ready
          ? 'Telegram target checked without sending messages: the first API proof can proceed after preview, approval, and queueing.'
          : 'Telegram target checked without sending messages: fix the publish target before the first API proof.',
        details_ru: probe.target_summary_ru || probe.message_ru || probe.next_action_ru || '',
        details_en: probe.target_summary_en || probe.message_en || probe.next_action_en || '',
      });
    } catch (probeError) {
      const message = probeError instanceof Error ? probeError.message : (isRu ? 'Не удалось проверить цель Telegram' : 'Could not check Telegram target');
      setError(message);
      setSocialTelegramPublishTargetProbe({
        ready: false,
        status: 'request_failed',
        message_ru: message,
        message_en: message,
        next_action_ru: 'Проверьте настройки Telegram и повторите безопасную проверку.',
        next_action_en: 'Check Telegram settings and run the safe check again.',
        external_post_published: false,
        send_message_performed: false,
      });
    } finally {
      setSocialBusyAction('');
    }
  };

  const copySocialPostText = async (post: SocialPost, text: string) => {
    const value = String(text || post.platform_text || post.base_text || '').trim();
    if (!value) return;
    setError('');
    try {
      await copyTextToClipboard(value);
      setActionSummary({
        tone: 'success',
        text_ru: 'Текст скопирован. Теперь откройте площадку и вставьте его в форму публикации.',
        text_en: 'Post text copied. Open the platform and paste it into the publication form.',
      });
    } catch {
      setError(isRu ? 'Не удалось скопировать текст' : 'Could not copy text');
    }
  };

  const copySocialWorkerEnv = async () => {
    const dispatchEnv = socialLaunchPreflight?.recommended_env?.dispatch || {};
    const metricsEnv = socialLaunchPreflight?.recommended_env?.metrics || {};
    const lines = _socialWorkerEnvLines(dispatchEnv, metricsEnv);
    if (!lines.length) return;
    const runbookLines = _socialLaunchRunbookClipboardLines(socialLaunchPreflight?.launch_runbook, isRu);
    setError('');
    try {
      await copyTextToClipboard([...lines, ...runbookLines].join('\n'));
      setActionSummary({
        tone: 'success',
        text_ru: 'Настройки и чеклист первого цикла скопированы. Включайте запуск только для выбранного бизнеса и проверьте логи после одного цикла.',
        text_en: 'Scoped dispatch env and first-cycle runbook copied. Enable the worker only for the selected business and check logs after one cycle.',
      });
    } catch {
      setError(isRu ? 'Не удалось скопировать настройки запуска' : 'Could not copy worker env');
    }
  };

  const recordSocialPostAttribution = async (post: SocialPost, eventType: SocialAttributionEventType) => {
    setSocialBusyAction(`attribute:${eventType}:${post.id}`);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/attribution-events`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: eventType,
          value: 1,
          event_source: 'manual_content_plan',
          metadata: {
            platform: post.platform,
            content_plan_item_id: post.content_plan_item_id,
          },
        }),
      });
      const nextPost = response?.post && typeof response.post === 'object' ? response.post : null;
      if (nextPost) {
        const itemId = String(nextPost.content_plan_item_id || post.content_plan_item_id || '').trim();
        setSocialPostsByItem((prev) => {
          const currentPosts = prev[itemId] || [];
          const nextPosts = currentPosts.map((existing) => (
            existing.id === post.id ? { ...existing, ...nextPost } : existing
          ));
          return {
            ...prev,
            [itemId]: nextPosts.length ? nextPosts : [{ ...post, ...nextPost }],
          };
        });
      } else if (currentPlan?.id) {
        await loadSocialPosts(currentPlan.id);
      }
      let recommendationPayload: SocialRecommendationPayload | null = null;
      let recommendationError = '';
      if (currentPlan?.id) {
        try {
          recommendationPayload = await actionRefs.fetchSocialPlanRecommendation(currentPlan.id);
        } catch (recommendErrorCaught) {
          recommendationError = recommendErrorCaught instanceof Error
            ? recommendErrorCaught.message
            : (isRu ? 'Не удалось пересчитать рекомендации' : 'Could not recalculate recommendations');
          setSocialRecommendation(null);
          setSocialRecommendationApproved(false);
        }
      } else {
        setSocialRecommendation(null);
        setSocialRecommendationApproved(false);
      }
      const feedback = _socialAttributionFeedback(eventType);
      const metrics = response?.metrics && typeof response.metrics === 'object' ? response.metrics : {};
      const leads = Number(metrics.leads || nextPost?.leads || post.leads || 0);
      const inquiries = Number(metrics.inquiries || nextPost?.inquiries || post.inquiries || 0);
      const comments = Number(metrics.comments || nextPost?.comments || post.comments || 0);
      const reach = Number(metrics.reach || metrics.views || nextPost?.reach || nextPost?.views || post.reach || post.views || 0);
      const proposedCount = Number(recommendationPayload?.proposed_changes?.length || 0);
      const readiness = recommendationPayload?.learning_readiness;
      const readinessSummaryRu = String(readiness?.summary_ru || '').trim();
      const readinessSummaryEn = String(readiness?.summary_en || '').trim();
      setActionSummary({
        tone: recommendationError ? 'warning' : 'success',
        text_ru: feedback.ru,
        text_en: feedback.en,
        details_ru: [
          `Итого по посту: заявки ${leads}, обращения ${inquiries}, комментарии ${comments}, охват ${reach}.`,
          recommendationError
            ? `Рекомендации сброшены: результат сохранён, но новый предпросмотр не пересчитался: ${recommendationError}`
            : proposedCount > 0
              ? `LocalOS сразу подготовил предложения к следующему плану: ${proposedCount}. Они не применены автоматически.`
              : 'LocalOS пересчитал рекомендации, но пока не нашёл изменений для применения.',
          readinessSummaryRu || 'Главная метрика - заявки и обращения; изменения требуют отдельного подтверждения.',
        ],
        details_en: [
          `Post totals: leads ${leads}, inquiries ${inquiries}, comments ${comments}, reach ${reach}.`,
          recommendationError
            ? `The result was saved, but recommendations were not recalculated: ${recommendationError}`
            : proposedCount > 0
              ? `LocalOS immediately prepared next-plan proposals: ${proposedCount}. They were not applied automatically.`
              : 'LocalOS recalculated recommendations, but found no changes to apply yet.',
          readinessSummaryEn || 'The main metric is leads and inquiries; changes require separate approval.',
        ],
      });
    } catch (attributeError) {
      const message = attributeError instanceof Error ? attributeError.message : (isRu ? 'Не удалось отметить результат публикации' : 'Could not record post result');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };
  return {
    loadPlans, openPlan, deletePlan, loadLearningMetrics, loadSocialRuntimeStatus, loadSocialPosts, loadContext, toggleMix,
    toggleSelectedItem, clearSelectedItems, generatePlan, saveItem, generateDraft, createNews, prepareSocialPosts, openSocialApprovalPreview,
    approveSocialPostItem, executeSocialApprovalPreview, saveSocialPostText, openSocialQueuePreview, queueSocialPostItem, executeSocialQueuePreview, markSocialPostPublished, rehearseSocialPostPublish,
    rehearseSelectedSocialPosts, markSupervisedPostBlocked, createSupervisedPostTask, checkOpenClawBrowserReadiness, checkApiChannelPreflight, checkTelegramPublishTargetProbe, copySocialPostText, copySocialWorkerEnv,
    recordSocialPostAttribution
  };
};
