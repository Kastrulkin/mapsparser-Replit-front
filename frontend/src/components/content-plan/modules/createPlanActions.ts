import { newAuth } from '@/lib/auth_new';
import { _locationLabelByKey, _bulkResultText, _bulkResultDetails, _shiftIsoDate, _autoScheduledDate, _inputDateValue, _removeRecordKeys, _weekBucketKey, _weekBucketLabel } from './helpers';
import type { PlanItem, ViewPresetKey, QuickActionKey, ContentPlanZone } from './types';

export const createPlanActions = (scope) => {
  const {
    language, isRu, plans, currentPlan, setCurrentPlan, setError, learningMetrics, setDraftEdits,
    setThemeEdits, setDateEdits, setBusyItemId, setBulkBusyAction, setActionSummary, setSelectedItemFilter, setSelectedSignalFilter, setSelectedPlanTargetKey,
    setSelectedItemLocationKey, setSelectedWeekKey, setDateFromFilter, setDateToFilter, setSortMode, setSelectedViewPreset, lastFocusLocationKey, setLastFocusLocationKey,
    lastFocusWeekKey, setLastFocusWeekKey, setExpandedDuplicateItemId, duplicateTargetSelections, setDuplicateTargetSelections, duplicateDateOverrides, setDuplicateDateOverrides, bulkNewsReview,
    setBulkNewsReview, bulkActionReview, setBulkActionReview, setActiveZone, contentLanguage, setSelectedQueueItemId, setEditorItemId, setSelectedItemIds,
    availableWeeks, availableItemLocations, bulkDraftCandidates, bulkNewsCandidates, selectedDraftCandidates, selectedNewsCandidates, allSocialNeedsReview, allSocialCanQueue,
    visibleSocialNeedsReview, visibleSocialCanQueue, visibleSocialNeedsSupervised, visibleSocialNeedsManual, socialPlanNextStep, missingDateCandidates, repeatTemplateCandidate, locationWeekFocusSummary,
    loadPlans, loadLearningMetrics, loadSocialPosts, clearSelectedItems, openSocialApprovalPreview, openSocialQueuePreview, prepareSuggestedSocialPosts, queueVisibleApprovedSocialPosts,
    collectSocialPostMetricsForBusiness, recommendNextSocialPlan, persistItemEdits
  } = scope;
  const deleteItem = async (itemId: string) => {
    if (!itemId) return;
    const confirmed = typeof window === 'undefined' ? true : window.confirm(isRu
      ? 'Удалить эту тему из выбранного плана?'
      : 'Delete this topic from the selected plan?');
    if (!confirmed) return;
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}`, {
        method: 'DELETE',
      });
      setCurrentPlan(response.plan || null);
      setEditorItemId('');
      setSelectedQueueItemId('');
      setDraftEdits((prev) => _removeRecordKeys(prev, [itemId]));
      setThemeEdits((prev) => _removeRecordKeys(prev, [itemId]));
      setDateEdits((prev) => _removeRecordKeys(prev, [itemId]));
      clearSelectedItems();
      await loadPlans();
      setActionSummary({
        tone: 'success',
        text_ru: 'Тема удалена из плана.',
        text_en: 'Topic deleted from the plan.',
      });
    } catch (deleteError) {
      const message = deleteError instanceof Error ? deleteError.message : (isRu ? 'Не удалось удалить тему' : 'Could not delete topic');
      setError(message);
    } finally {
      setBusyItemId('');
    }
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
            body: JSON.stringify({ language: contentLanguage }),
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
            body: JSON.stringify({ language: contentLanguage }),
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
            body: JSON.stringify({ language: contentLanguage }),
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
    setDateFromFilter('');
    setDateToFilter('');
    setSortMode('date');
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
    setDateFromFilter('');
    setDateToFilter('');
    if (preset === 'urgent') {
      setSelectedItemFilter('urgent');
      setSortMode('date');
      return;
    }
    if (preset === 'ready') {
      setSelectedItemFilter('has_draft');
      setSortMode('date');
      return;
    }
    if (preset === 'focus') {
      setSelectedItemFilter('urgent');
      setSortMode('date');
      if (lastFocusLocationKey !== 'all') {
        setSelectedItemLocationKey(lastFocusLocationKey);
      }
      if (lastFocusWeekKey !== 'all') {
        setSelectedWeekKey(lastFocusWeekKey);
      }
      return;
    }
    setSelectedItemFilter('all');
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
    setSortMode('date');
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
      [item.id]: prev[item.id] || _inputDateValue(item.scheduled_for) || _shiftIsoDate('', 7),
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
            body: JSON.stringify({ language: contentLanguage }),
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

  const runSocialPlanNextStep = () => {
    setActiveZone('queue');
    if (socialPlanNextStep.action === 'prepare') {
      void prepareSuggestedSocialPosts();
      return;
    }
    if (socialPlanNextStep.action === 'review') {
      const itemIds: string[] = visibleSocialNeedsReview
        .map((post) => String(post.content_plan_item_id || '').trim())
        .filter(Boolean);
      const uniqueItemIds = Array.from(new Set(itemIds));
      if (uniqueItemIds.length > 0) {
        setSelectedItemIds(uniqueItemIds.reduce<Record<string, boolean>>((acc, itemId) => {
          acc[itemId] = true;
          return acc;
        }, {}));
        setSelectedQueueItemId(uniqueItemIds[0]);
        setEditorItemId(uniqueItemIds[0]);
      }
      if (visibleSocialNeedsReview.length > 0) {
        openSocialApprovalPreview(visibleSocialNeedsReview, 'selected', 'selected-social-approve');
        setActionSummary({
          tone: 'neutral',
          text_ru: `Выделили темы с постами на проверку: ${uniqueItemIds.length}. Проверьте предпросмотр и подтвердите тексты отдельной кнопкой.`,
          text_en: `Selected topics with posts to review: ${uniqueItemIds.length}. Review the preview and approve copy with a separate button.`,
          details_ru: [
            'Наружу ничего не публикуется на этом шаге.',
            'После подтверждения следующим шагом будет “Поставить в расписание”.',
          ],
          details_en: [
            'Nothing is published externally at this step.',
            'After approval, the next step is “Queue on schedule”.',
          ],
        });
        if (typeof window !== 'undefined') {
          window.setTimeout(() => {
            document
              .querySelector('[data-testid="social-approval-preview-panel"]')
              ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 50);
        }
      }
      return;
    }
    if (socialPlanNextStep.action === 'queue') {
      void queueVisibleApprovedSocialPosts();
      return;
    }
    if (socialPlanNextStep.action === 'supervised') {
      const post = visibleSocialNeedsSupervised[0];
      const itemId = String(post?.content_plan_item_id || '').trim();
      if (itemId) {
        setSelectedQueueItemId(itemId);
        setEditorItemId(itemId);
      }
      return;
    }
    if (socialPlanNextStep.action === 'manual') {
      const post = visibleSocialNeedsManual[0];
      const itemId = String(post?.content_plan_item_id || '').trim();
      if (itemId) {
        setSelectedQueueItemId(itemId);
        setEditorItemId(itemId);
      }
      return;
    }
    if (socialPlanNextStep.action === 'collect') {
      void collectSocialPostMetricsForBusiness();
      return;
    }
    if (socialPlanNextStep.action === 'recommend') {
      void recommendNextSocialPlan();
      return;
    }
    if (currentPlan?.id) {
      void loadSocialPosts(currentPlan.id);
    }
  };

  const openSocialPostsWaitingForReview = () => {
    setActiveZone('queue');
    applyViewPreset('overview');
    const reviewPosts = allSocialNeedsReview.length > 0 ? allSocialNeedsReview : visibleSocialNeedsReview;
    const itemIds: string[] = reviewPosts
      .map((post) => String(post.content_plan_item_id || '').trim())
      .filter(Boolean);
    const uniqueItemIds = Array.from(new Set(itemIds));
    if (uniqueItemIds.length > 0) {
      setSelectedItemIds(uniqueItemIds.reduce<Record<string, boolean>>((acc, itemId) => {
        acc[itemId] = true;
        return acc;
      }, {}));
      setSelectedQueueItemId(uniqueItemIds[0]);
      setEditorItemId(uniqueItemIds[0]);
    }
    if (reviewPosts.length > 0) {
      openSocialApprovalPreview(reviewPosts, 'selected', 'selected-social-approve');
      setActionSummary({
        tone: 'neutral',
        text_ru: `Открыли посты на проверку: ${reviewPosts.length}. Проверьте предпросмотр, затем подтвердите тексты отдельной кнопкой.`,
        text_en: `Opened posts for review: ${reviewPosts.length}. Review the preview, then approve copy with a separate button.`,
        details_ru: [
          'Наружу ничего не публикуется на этом шаге.',
          'После подтверждения worker сможет поставить посты в расписание и исполнить API-каналы.',
        ],
        details_en: [
          'Nothing is published externally at this step.',
          'After approval, the worker can queue posts and execute API channels.',
        ],
      });
      if (typeof window !== 'undefined') {
        window.setTimeout(() => {
          document
            .querySelector('[data-testid="social-approval-preview-panel"]')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
      }
    }
  };

  const openSocialPostsWaitingForQueue = () => {
    setActiveZone('queue');
    applyViewPreset('overview');
    const queuePosts = allSocialCanQueue.length > 0 ? allSocialCanQueue : visibleSocialCanQueue;
    const itemIds: string[] = queuePosts
      .map((post) => String(post.content_plan_item_id || '').trim())
      .filter(Boolean);
    const uniqueItemIds = Array.from(new Set(itemIds));
    if (uniqueItemIds.length > 0) {
      setSelectedItemIds(uniqueItemIds.reduce<Record<string, boolean>>((acc, itemId) => {
        acc[itemId] = true;
        return acc;
      }, {}));
      setSelectedQueueItemId(uniqueItemIds[0]);
      setEditorItemId(uniqueItemIds[0]);
    }
    if (queuePosts.length > 0) {
      openSocialQueuePreview(queuePosts, 'selected', 'selected-social-queue');
      setActionSummary({
        tone: 'neutral',
        text_ru: `Открыли утверждённые посты: ${queuePosts.length}. Проверьте расписание и подтвердите постановку отдельной кнопкой.`,
        text_en: `Opened approved posts: ${queuePosts.length}. Review the schedule and confirm queueing with a separate button.`,
        details_ru: [
          'Это ещё не мгновенная публикация всех каналов.',
          'После постановки в расписание API-каналы пойдут по дате, а Яндекс/2ГИС останутся контролируемыми или ручными.',
        ],
        details_en: [
          'This is not instant publishing for every channel.',
          'After queueing, API channels run by date while Yandex/2GIS stay supervised or manual.',
        ],
      });
      if (typeof window !== 'undefined') {
        window.setTimeout(() => {
          document
            .querySelector('[data-testid="social-queue-preview-panel"]')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
      }
    }
  };

  const contentPlanZones: Array<{ key: ContentPlanZone; titleRu: string; titleEn: string; hintRu: string; hintEn: string }> = [
    { key: 'overview', titleRu: 'Обзор', titleEn: 'Overview', hintRu: 'Состояние и следующий шаг', hintEn: 'Status and next step' },
    { key: 'plan', titleRu: 'План', titleEn: 'Plan', hintRu: 'Создание и источники', hintEn: 'Creation and inputs' },
    { key: 'queue', titleRu: 'Готовая очередь по плану', titleEn: 'Plan queue', hintRu: 'Темы, тексты и публикации', hintEn: 'Topics, drafts, and publishing' },
  ];
  return {
    deleteItem, runBulkGenerateDrafts, runSelectedGenerateDrafts, runSelectedCreateNews, runBulkCreateNews, runBulkAutofillDates, executeBulkNewsReview, executeBulkActionReview,
    resetViewState, applyViewPreset, applyLocationWeekFocus, getLocationWeekFocusItems, getDuplicateTargetLocationOptions, openDuplicateTargetPicker, toggleDuplicateTargetLocation, runLocationWeekFocusDrafts,
    runLocationWeekFocusNews, runLocationWeekSkip, runLocationWeekReschedule, runLocationWeekRescheduleToDate, runItemSkip, runItemReschedule, runItemDuplicate, runItemDuplicateToOtherLocations,
    runItemDuplicateToSelectedLocations, runQuickAction, runSocialPlanNextStep, openSocialPostsWaitingForReview, openSocialPostsWaitingForQueue, contentPlanZones
  };
};
