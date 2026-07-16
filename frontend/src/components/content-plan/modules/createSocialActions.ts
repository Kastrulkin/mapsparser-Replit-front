import { newAuth } from '@/lib/auth_new';
import { _socialAttributionFeedback } from './helpers';
import type { PlanItem, SocialRecommendationPayload, SocialDispatchPreview, SocialDispatchExecutionReport, SocialLaunchPreflight, SocialAttributionEventType } from './types';

export const createSocialActions = (scope) => {
  const {
    businessId, isRu, plans, currentPlan, setCurrentPlan, error, setError, draftEdits,
    themeEdits, dateEdits, setBulkBusyAction, setActionSummary, setSocialRecommendation, setSocialRecommendationApproved, socialDispatchPreview, setSocialDispatchPreview,
    setSocialDispatchExecutionReport, setSocialMetricsLearningPacket, socialLaunchPreflight, setSocialLaunchPreflight, socialPreparePreview, setSocialPreparePreview, setSocialApprovalPreview, setSocialQueuePreview,
    setSocialBusyAction, setActiveZone, setSelectedQueueItemId, setEditorItemId, setSelectedItemIds, readiness, visibleItems, selectedItems,
    selectedSocialNeedsReview, selectedSocialDirtyReviewPosts, selectedSocialCanQueue, selectedSocialCanMarkPublished, selectedSocialCanRecordResults, visibleSocialCanQueue, visibleSocialPublishedPosts, loadPlans,
    loadSocialRuntimeStatus, loadSocialPosts, openSocialApprovalPreview, openSocialQueuePreview
  } = scope;
  const openSocialPreparePreview = async (
    itemsToPrepare: PlanItem[],
    source: 'selected' | 'suggested',
    busyAction: string,
  ) => {
    const firstItem = itemsToPrepare[0];
    if (!firstItem) return false;
    setBulkBusyAction(busyAction);
    setError('');
    setActionSummary(null);
    setSocialApprovalPreview(null);
    setSocialQueuePreview(null);
    try {
    const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(firstItem.id)}/social-posts/prepare-preview`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    const item = response.item && typeof response.item === 'object' ? response.item : {};
    const fallbackTitle = isRu ? 'выбранная тема' : 'selected topic';
    const title = String(item.theme || firstItem.theme || firstItem.goal || fallbackTitle).trim();
      setSocialPreparePreview({
        key: `${source}:${firstItem.id}:${Date.now()}`,
        items: itemsToPrepare,
        itemIds: itemsToPrepare.map((prepareItem) => prepareItem.id),
        busyAction,
        source,
        previewItemTitle: title,
        preview: {
          read_only: Boolean(response.read_only),
          database_write_performed: Boolean(response.database_write_performed),
          external_publish_performed: Boolean(response.external_publish_performed),
          summary: response.summary && typeof response.summary === 'object' ? response.summary : {},
          posts: Array.isArray(response.posts) ? response.posts : [],
          next_action_ru: String(response.next_action_ru || ''),
          next_action_en: String(response.next_action_en || ''),
        },
      });
      setActionSummary({
        tone: 'neutral',
        text_ru: 'Предпросмотр подготовки каналов готов. Проверьте сводку и подтвердите создание черновиков отдельной кнопкой.',
        text_en: 'Channel preparation preview is ready. Review the summary and confirm draft creation with a separate button.',
      });
      return false;
    } catch (previewError) {
      const message = previewError instanceof Error ? previewError.message : (isRu ? 'Не удалось открыть предпросмотр подготовки каналов' : 'Could not open channel preparation preview');
      setError(message);
      return false;
    } finally {
      setBulkBusyAction('');
    }
  };

  const prepareSelectedSocialPosts = async () => {
    if (!selectedItems.length) return;
    await openSocialPreparePreview(selectedItems, 'selected', 'selected-social-prepare');
  };

  const prepareSuggestedSocialPosts = async () => {
    const itemsToPrepare = selectedItems.length > 0 ? selectedItems : visibleItems.slice(0, 5);
    if (itemsToPrepare.length === 0) return;
    await openSocialPreparePreview(itemsToPrepare, selectedItems.length > 0 ? 'selected' : 'suggested', 'suggested-social-prepare');
  };

  const executeSocialPreparePreview = async () => {
    const preview = socialPreparePreview;
    if (!preview || preview.itemIds.length === 0) return;
    setBulkBusyAction(preview.busyAction);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/content-plans/social-posts/bulk-prepare', {
        method: 'POST',
        body: JSON.stringify({ item_ids: preview.itemIds }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setSelectedItemIds(preview.items.reduce((acc: Record<string, boolean>, item) => {
        acc[item.id] = true;
        return acc;
      }, {}));
      setSocialPreparePreview(null);
      setActionSummary({
        tone: 'success',
        text_ru: preview.source === 'selected'
          ? 'Каналы подготовлены для выбранных тем. Следующий шаг - проверить тексты.'
          : 'Каналы подготовлены. Следующий безопасный шаг - открыть предпросмотр и проверить тексты.',
        text_en: preview.source === 'selected'
          ? 'Channels prepared for selected items. Next step: review copy.'
          : 'Channels prepared. Next safe step: open preview and review copy.',
        details_ru: [
          preview.source === 'selected'
            ? 'Выбранные темы остались отмечены. В панели ниже откройте предпросмотр, сохраните правки и нажмите “Подтвердить посты”.'
            : 'LocalOS отметил подготовленные темы, чтобы массовое подтверждение было видно сразу.',
          'Наружу ничего не отправлено: подтверждение и постановка в расписание идут отдельными шагами.',
        ],
        details_en: [
          preview.source === 'selected'
            ? 'Selected topics stayed checked. In the panel below, open preview, save edits, and click “Approve posts”.'
            : 'LocalOS selected the prepared topics so bulk approval is visible immediately.',
          'Nothing was sent externally: approval and queueing stay separate steps.',
        ],
      });
    } catch (bulkError) {
      const message = bulkError instanceof Error ? bulkError.message : (isRu ? 'Не удалось подготовить каналы' : 'Could not prepare channels');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const approveSelectedSocialPosts = async () => {
    if (!selectedSocialNeedsReview.length) return;
    if (selectedSocialDirtyReviewPosts.length > 0) {
      setActionSummary({
        tone: 'warning',
        text_ru: `Сначала сохраните правки текста: ${selectedSocialDirtyReviewPosts.length}. Массовое подтверждение не подтвердит несохранённый предпросмотр.`,
        text_en: `Save copy edits first: ${selectedSocialDirtyReviewPosts.length}. Bulk approval will not approve unsaved preview text.`,
      });
      return;
    }
    openSocialApprovalPreview(selectedSocialNeedsReview, 'selected', 'selected-social-approve');
  };

  const queueVisibleApprovedSocialPosts = async () => {
    if (!visibleSocialCanQueue.length) return;
    openSocialQueuePreview(visibleSocialCanQueue, 'visible', 'visible-social-queue');
  };

  const queueSelectedSocialPosts = async () => {
    if (!selectedSocialCanQueue.length) return;
    openSocialQueuePreview(selectedSocialCanQueue, 'selected', 'selected-social-queue');
  };

  const selectPublishedSocialPostsForResult = () => {
    const itemIds: string[] = visibleSocialPublishedPosts
      .map((post) => String(post.content_plan_item_id || '').trim())
      .filter(Boolean);
    const uniqueItemIds = Array.from(new Set(itemIds));
    if (!uniqueItemIds.length) return;
    setSelectedItemIds(uniqueItemIds.reduce((acc: Record<string, boolean>, itemId) => {
      acc[itemId] = true;
      return acc;
    }, {}));
    setSelectedQueueItemId(uniqueItemIds[0]);
    setEditorItemId(uniqueItemIds[0]);
    setActiveZone('queue');
    setActionSummary({
      tone: 'neutral',
      text_ru: `Выбраны опубликованные темы: ${uniqueItemIds.length}. Теперь можно отметить заявки, обращения или ранние реакции.`,
      text_en: `Published topics selected: ${uniqueItemIds.length}. You can now record leads, inquiries, or early reactions.`,
      details_ru: [
        'Это не публикует ничего наружу и не меняет план автоматически.',
        'После отметки результата LocalOS пересчитает предложения следующего плана.',
      ],
      details_en: [
        'This does not publish externally and does not change the plan automatically.',
        'After result marking, LocalOS recalculates next-plan proposals.',
      ],
    });
  };

  const markSelectedSocialPostsPublished = async () => {
    if (!selectedSocialCanMarkPublished.length) return;
    setBulkBusyAction('selected-social-manual');
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/social-posts/bulk-mark-manual-published', {
        method: 'POST',
        body: JSON.stringify({ post_ids: selectedSocialCanMarkPublished.map((post) => post.id) }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setActionSummary({
        tone: 'success',
        text_ru: 'Выбранные ручные/контролируемые публикации отмечены как размещённые.',
        text_en: 'Selected manual/supervised posts marked as published.',
      });
    } catch (bulkError) {
      const message = bulkError instanceof Error ? bulkError.message : (isRu ? 'Не удалось отметить выбранные публикации' : 'Could not mark selected posts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const recordSelectedSocialPostAttribution = async (eventType: SocialAttributionEventType) => {
    if (!selectedSocialCanRecordResults.length) return;
    setBulkBusyAction(`selected-social-attribute-${eventType}`);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/social-posts/bulk-attribution-events', {
        method: 'POST',
        body: JSON.stringify({
          post_ids: selectedSocialCanRecordResults.map((post) => post.id),
          event_type: eventType,
          value: 1,
          event_source: 'manual_content_plan_bulk',
          metadata: {
            selected_bulk: true,
          },
        }),
      });
      if (currentPlan?.id) {
        await loadSocialPosts(currentPlan.id);
        try {
          await fetchSocialPlanRecommendation(currentPlan.id);
        } catch (recommendError) {
          setActionSummary({
            tone: 'warning',
            text_ru: 'Результаты сохранены, но рекомендации следующего плана не пересчитались.',
            text_en: 'Results were saved, but next-plan recommendations were not recalculated.',
            details_ru: [recommendError instanceof Error ? recommendError.message : 'Повторите пересчёт рекомендаций позже.'],
            details_en: [recommendError instanceof Error ? recommendError.message : 'Run recommendation refresh again later.'],
          });
          return;
        }
      }
      const feedback = _socialAttributionFeedback(eventType);
      const isPrimaryResult = eventType === 'lead' || eventType === 'inquiry';
      setActionSummary({
        tone: 'success',
        text_ru: isPrimaryResult
          ? `${feedback.ru} Массово отмечено: ${selectedSocialCanRecordResults.length}. LocalOS пересчитал рекомендации, но не применил изменения автоматически.`
          : `${feedback.ru} Массово отмечено: ${selectedSocialCanRecordResults.length}. LocalOS пересчитал рекомендации, но заявки и обращения остаются главным KPI.`,
        text_en: isPrimaryResult
          ? `${feedback.en} Bulk recorded: ${selectedSocialCanRecordResults.length}. LocalOS recalculated recommendations but did not apply changes automatically.`
          : `${feedback.en} Bulk recorded: ${selectedSocialCanRecordResults.length}. LocalOS recalculated recommendations, while leads and inquiries remain the main KPI.`,
        details_ru: ['Главная метрика - заявки и обращения; комментарии, репосты, клики, охваты и лайки остаются ранними сигналами.'],
        details_en: ['The main metric is leads and inquiries; comments, shares, clicks, reach, and likes remain early signals.'],
      });
    } catch (bulkError) {
      const message = bulkError instanceof Error ? bulkError.message : (isRu ? 'Не удалось отметить результат выбранных публикаций' : 'Could not record selected post results');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const fetchSocialPlanRecommendation = async (planId: string) => {
    const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}/social-posts/recommend-next-plan`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    const payload: SocialRecommendationPayload = {
      recommendation: response.recommendation || {},
      learning_readiness: response.learning_readiness || undefined,
      application_preview: response.application_preview && typeof response.application_preview === 'object'
        ? response.application_preview
        : undefined,
      proposed_changes: Array.isArray(response.proposed_changes) ? response.proposed_changes : [],
    };
    setSocialRecommendation(payload);
    setSocialRecommendationApproved(false);
    return payload;
  };

  const collectSocialPostMetricsForBusiness = async () => {
    if (!businessId || !currentPlan?.id) return;
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(
        isRu
          ? 'Собрать реакции один раз для опубликованных постов текущего бизнеса? Это не публикует новые посты и только обновляет метрики/заявки для рекомендаций.'
          : 'Collect reactions once for published posts in the current business? This will not publish new posts and only updates metrics/leads for recommendations.'
      );
      if (!confirmed) return;
    }
    setSocialBusyAction('collect-metrics');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/social-posts/metrics/run-once', {
        method: 'POST',
        body: JSON.stringify({ business_id: businessId, batch_size: 25, approved: true }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      const result = response.metrics_result && typeof response.metrics_result === 'object'
        ? response.metrics_result
        : {};
      setSocialMetricsLearningPacket(
        response.metrics_learning_packet && typeof response.metrics_learning_packet === 'object'
          ? response.metrics_learning_packet
          : null
      );
      const collected = Number(result.collected || 0);
      const picked = Number(result.picked || 0);
      const failed = Number(result.failed || 0);
      const resultSummariesRu = Array.isArray(result.result_summaries_ru)
        ? result.result_summaries_ru.map(String).filter(Boolean)
        : [];
      const resultSummariesEn = Array.isArray(result.result_summaries_en)
        ? result.result_summaries_en.map(String).filter(Boolean)
        : [];
      let recommendationPayload: SocialRecommendationPayload | null = null;
      let recommendationError = '';
      try {
        recommendationPayload = await fetchSocialPlanRecommendation(currentPlan.id);
      } catch (recommendErrorCaught) {
        recommendationError = recommendErrorCaught instanceof Error
          ? recommendErrorCaught.message
          : (isRu ? 'Не удалось пересчитать рекомендации' : 'Could not recalculate recommendations');
        setSocialRecommendation(null);
        setSocialRecommendationApproved(false);
      }
      const proposedCount = Number(recommendationPayload?.proposed_changes?.length || 0);
      const readiness = recommendationPayload?.learning_readiness;
      const readinessSummaryRu = String(readiness?.summary_ru || '').trim();
      const readinessSummaryEn = String(readiness?.summary_en || '').trim();
      setActionSummary({
        tone: failed > 0 || recommendationError ? 'warning' : 'success',
        text_ru: String(response.message_ru || `Сбор реакций выполнен: проверено ${picked}, обновлено ${collected}, ошибок ${failed}.`),
        text_en: String(response.message_en || `Metrics collection finished: checked ${picked}, updated ${collected}, failed ${failed}.`),
        details_ru: [
          ...resultSummariesRu,
          recommendationError
            ? `Рекомендации сброшены: реакции сохранены, но новый предпросмотр не пересчитался: ${recommendationError}`
            : proposedCount > 0
              ? `LocalOS сразу подготовил предложения к следующему плану: ${proposedCount}. Они не применены автоматически.`
              : 'LocalOS пересчитал рекомендации, но пока не нашёл изменений для применения.',
          readinessSummaryRu || 'Главная метрика - заявки и обращения; изменения требуют отдельного подтверждения.',
        ].slice(0, 7),
        details_en: [
          ...resultSummariesEn,
          recommendationError
            ? `Recommendations were reset: reactions were saved, but the new preview was not recalculated: ${recommendationError}`
            : proposedCount > 0
              ? `LocalOS immediately prepared next-plan proposals: ${proposedCount}. They were not applied automatically.`
              : 'LocalOS recalculated recommendations, but found no changes to apply yet.',
          readinessSummaryEn || 'The main metric is leads and inquiries; changes require separate approval.',
        ].slice(0, 7),
      });
    } catch (collectError) {
      const message = collectError instanceof Error ? collectError.message : (isRu ? 'Не удалось обновить реакции' : 'Could not update reactions');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const previewSocialDispatch = async (scrollToPreview = false) => {
    setSocialBusyAction('dispatch-preview');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/social-posts/dispatch/preview', {
        method: 'POST',
        body: JSON.stringify({ batch_size: 10, business_id: businessId }),
      });
      const preview: SocialDispatchPreview = {
        dry_run: Boolean(response.dry_run),
        picked: Number(response.picked || 0),
        skipped_no_access: Number(response.skipped_no_access || 0),
        batch_size: Number(response.batch_size || 10),
        business_scope: String(response.business_scope || ''),
        by_action: response.by_action && typeof response.by_action === 'object' ? response.by_action : {},
        readiness: response.readiness && typeof response.readiness === 'object' ? response.readiness : {},
        items: Array.isArray(response.items) ? response.items : [],
      };
      setSocialDispatchPreview(preview);
      const apiCount = Number(preview.readiness?.external_publish_count ?? preview.by_action?.publish_api ?? 0);
      const supervisedCount = Number(preview.readiness?.controlled_count ?? preview.by_action?.create_supervised_task ?? 0);
      const manualCount = Number(preview.readiness?.manual_count ?? preview.by_action?.manual_handoff ?? 0);
      const dryRunMessageRu = String(preview.readiness?.message_ru || '');
      const dryRunMessageEn = String(preview.readiness?.message_en || '');
      setActionSummary({
        tone: manualCount > 0 || Number(preview.skipped_no_access || 0) > 0 ? 'warning' : 'success',
        text_ru: `Проверка расписания по текущему бизнесу: пора публиковать ${preview.picked || 0}, API ${apiCount}, контролируемое размещение ${supervisedCount}, вручную ${manualCount}. Наружу ничего не отправлено.`,
        text_en: `Schedule dry-run for the current business: due posts ${preview.picked || 0}, API ${apiCount}, supervised ${supervisedCount}, manual ${manualCount}. Nothing was sent externally.`,
        details_ru: dryRunMessageRu ? [dryRunMessageRu] : [],
        details_en: dryRunMessageEn ? [dryRunMessageEn] : [],
      });
      if (scrollToPreview && typeof window !== 'undefined') {
        window.setTimeout(() => {
          document
            .querySelector('[data-testid="social-dispatch-preview-panel"]')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
      }
    } catch (previewError) {
      const message = previewError instanceof Error ? previewError.message : (isRu ? 'Не удалось проверить расписание' : 'Could not preview schedule');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const checkSocialLaunchPreflight = async () => {
    if (!businessId) return;
    setSocialBusyAction('launch-preflight');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/social-posts/launch-preflight`, {
        method: 'GET',
      });
      const dispatchPreview = response.dispatch_preview && typeof response.dispatch_preview === 'object'
        ? {
          dry_run: Boolean(response.dispatch_preview.dry_run),
          picked: Number(response.dispatch_preview.picked || 0),
          skipped_no_access: Number(response.dispatch_preview.skipped_no_access || 0),
          batch_size: Number(response.dispatch_preview.batch_size || 10),
          business_scope: String(response.dispatch_preview.business_scope || ''),
          by_action: response.dispatch_preview.by_action && typeof response.dispatch_preview.by_action === 'object' ? response.dispatch_preview.by_action : {},
          readiness: response.dispatch_preview.readiness && typeof response.dispatch_preview.readiness === 'object' ? response.dispatch_preview.readiness : {},
          items: Array.isArray(response.dispatch_preview.items) ? response.dispatch_preview.items : [],
        }
        : null;
      const preflight: SocialLaunchPreflight = {
        business_id: String(response.business_id || businessId),
        status: String(response.status || ''),
        safe_to_enable_scoped_dispatch: Boolean(response.safe_to_enable_scoped_dispatch),
        production_readiness: response.production_readiness && typeof response.production_readiness === 'object'
          ? response.production_readiness
          : undefined,
        launch_gate: response.launch_gate && typeof response.launch_gate === 'object'
          ? response.launch_gate
          : undefined,
        first_api_proof_gate: response.first_api_proof_gate && typeof response.first_api_proof_gate === 'object'
          ? response.first_api_proof_gate
          : undefined,
        first_cycle_proof_packet: response.first_cycle_proof_packet && typeof response.first_cycle_proof_packet === 'object'
          ? response.first_cycle_proof_packet
          : undefined,
        proof_requirements: response.proof_requirements && typeof response.proof_requirements === 'object'
          ? response.proof_requirements
          : undefined,
        workflow_stage_counts: response.workflow_stage_counts && typeof response.workflow_stage_counts === 'object'
          ? response.workflow_stage_counts
          : undefined,
        worker_idle_reason: response.worker_idle_reason && typeof response.worker_idle_reason === 'object'
          ? response.worker_idle_reason
          : undefined,
        live_validation_checklist: Array.isArray(response.live_validation_checklist)
          ? response.live_validation_checklist
          : [],
        channel_summary: response.channel_summary && typeof response.channel_summary === 'object' ? response.channel_summary : {},
        dispatch_preview: dispatchPreview || undefined,
        dispatch_readiness: response.dispatch_readiness && typeof response.dispatch_readiness === 'object' ? response.dispatch_readiness : {},
        api_preflight: Array.isArray(response.api_preflight) ? response.api_preflight : [],
        api_preflight_summary: response.api_preflight_summary && typeof response.api_preflight_summary === 'object' ? response.api_preflight_summary : {},
        launch_rehearsal: response.launch_rehearsal && typeof response.launch_rehearsal === 'object'
          ? {
            schema: String(response.launch_rehearsal.schema || 'localos_social_publish_rehearsal_bulk_v1'),
            dry_run: Boolean(response.launch_rehearsal.dry_run),
            external_publish_performed: Boolean(response.launch_rehearsal.external_publish_performed),
            provider_write_performed: Boolean(response.launch_rehearsal.provider_write_performed),
            rehearsals: Array.isArray(response.launch_rehearsal.rehearsals) ? response.launch_rehearsal.rehearsals : [],
            failed: Array.isArray(response.launch_rehearsal.failed) ? response.launch_rehearsal.failed : [],
            summary: response.launch_rehearsal.summary && typeof response.launch_rehearsal.summary === 'object' ? response.launch_rehearsal.summary : {},
          }
          : undefined,
        api_preflight_blocked_due_posts: Array.isArray(response.api_preflight_blocked_due_posts) ? response.api_preflight_blocked_due_posts : [],
        first_api_publish_readiness: response.first_api_publish_readiness && typeof response.first_api_publish_readiness === 'object'
          ? response.first_api_publish_readiness
          : undefined,
        recommended_env: response.recommended_env && typeof response.recommended_env === 'object' ? response.recommended_env : {},
        safety: response.safety && typeof response.safety === 'object' ? response.safety : {},
        summary: response.summary && typeof response.summary === 'object' ? response.summary : {},
        message_ru: String(response.message_ru || ''),
        message_en: String(response.message_en || ''),
        next_action_ru: String(response.next_action_ru || ''),
        next_action_en: String(response.next_action_en || ''),
        launch_runbook: response.launch_runbook && typeof response.launch_runbook === 'object' ? response.launch_runbook : undefined,
        runtime_alignment: response.runtime_alignment && typeof response.runtime_alignment === 'object' ? response.runtime_alignment : undefined,
      };
      setSocialLaunchPreflight(preflight);
      if (dispatchPreview) {
        setSocialDispatchPreview(dispatchPreview);
      }
      setActionSummary({
        tone: preflight.production_readiness?.ready_for_first_scoped_cycle || preflight.safe_to_enable_scoped_dispatch ? 'success' : 'warning',
        text_ru: preflight.production_readiness?.summary_ru || preflight.message_ru || 'Проверка запуска по расписанию готова.',
        text_en: preflight.production_readiness?.summary_en || preflight.message_en || 'Worker launch preflight is ready.',
        details_ru: [
          `Пора публиковать: ${Number(preflight.summary?.due_posts || 0)} · API: ${Number(preflight.summary?.api_due_posts || 0)} · контролируемо: ${Number(preflight.summary?.controlled_due_posts || 0)} · вручную: ${Number(preflight.summary?.manual_due_posts || 0)}.`,
          preflight.worker_idle_reason?.next_action_ru || '',
          preflight.production_readiness?.next_action_ru || '',
          preflight.next_action_ru || 'Следующий шаг появится в блоке запуска.',
        ].filter(Boolean),
        details_en: [
          `Due: ${Number(preflight.summary?.due_posts || 0)} · API: ${Number(preflight.summary?.api_due_posts || 0)} · supervised: ${Number(preflight.summary?.controlled_due_posts || 0)} · manual: ${Number(preflight.summary?.manual_due_posts || 0)}.`,
          preflight.worker_idle_reason?.next_action_en || '',
          preflight.production_readiness?.next_action_en || '',
          preflight.next_action_en || 'The next step is shown in the launch block.',
        ].filter(Boolean),
      });
    } catch (preflightError) {
      const message = preflightError instanceof Error ? preflightError.message : (isRu ? 'Не удалось проверить запуск по расписанию' : 'Could not check worker launch');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const runSocialDispatchOnce = async () => {
    if (!businessId) return;
    const apiDuePosts = Number(
      socialLaunchPreflight?.summary?.api_due_posts
      ?? socialLaunchPreflight?.launch_gate?.api_posts
      ?? socialDispatchPreview?.readiness?.external_publish_count
      ?? 0
    );
    const externalPublishPhrase = String(
      socialLaunchPreflight?.launch_gate?.external_publish_confirmation_phrase
      || 'ПУБЛИКУЮ'
    );
    let approvalText = '';
    if (typeof window !== 'undefined') {
      if (apiDuePosts > 0) {
        const typed = window.prompt(
          isRu
            ? `Этот запуск может опубликовать API-посты: ${apiDuePosts}. Чтобы подтвердить внешний publish, введите: ${externalPublishPhrase}`
            : `This run may publish API posts: ${apiDuePosts}. To confirm external publishing, type: ${externalPublishPhrase}`,
          ''
        );
        if (typed === null) return;
        approvalText = typed;
      } else {
        const confirmed = window.confirm(
          isRu
            ? 'Запустить один scoped цикл для текущего бизнеса? Яндекс/2ГИС перейдут в контролируемое или ручное размещение без финального клика.'
            : 'Run one scoped cycle for the current business? Yandex/2GIS will move to supervised placement without the final click.'
        );
        if (!confirmed) return;
      }
    }
    setSocialBusyAction('dispatch-run-once');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/social-posts/dispatch/run-once', {
        method: 'POST',
        body: JSON.stringify({
          business_id: businessId,
          batch_size: 10,
          approved: true,
          approval_text: approvalText,
        }),
      });
      const result = response.dispatch_result && typeof response.dispatch_result === 'object'
        ? response.dispatch_result
        : {};
      const executionReport: SocialDispatchExecutionReport | null = response.execution_report && typeof response.execution_report === 'object'
        ? response.execution_report
        : null;
      const followupRu = Array.isArray(result.followup_actions_ru)
        ? result.followup_actions_ru.map(String).filter(Boolean)
        : [];
      const followupEn = Array.isArray(result.followup_actions_en)
        ? result.followup_actions_en.map(String).filter(Boolean)
        : [];
      const resultSummariesRu = Array.isArray(result.result_summaries_ru)
        ? result.result_summaries_ru.map(String).filter(Boolean)
        : [];
      const resultSummariesEn = Array.isArray(result.result_summaries_en)
        ? result.result_summaries_en.map(String).filter(Boolean)
        : [];
      setActionSummary({
        tone: Number(result.failed || 0) > 0 || Number(result.manual || 0) > 0 ? 'warning' : 'success',
        text_ru: String(response.message_ru || `Первый scoped цикл выполнен: взято ${Number(result.picked || 0)}, опубликовано ${Number(result.published || 0)}, контролируемое размещение ${Number(result.supervised || 0)}, вручную ${Number(result.manual || 0)}, ошибок ${Number(result.failed || 0)}.`),
        text_en: String(response.message_en || `First scoped cycle finished: picked ${Number(result.picked || 0)}, published ${Number(result.published || 0)}, supervised ${Number(result.supervised || 0)}, manual ${Number(result.manual || 0)}, failed ${Number(result.failed || 0)}.`),
        details_ru: [
          ...resultSummariesRu,
          ...(followupRu.length ? followupRu : [
            'Проверьте карточки постов: API должны показать ссылку/ID или понятную ошибку, карты - контролируемое или ручное размещение.',
          ]),
        ].slice(0, 7),
        details_en: [
          ...resultSummariesEn,
          ...(followupEn.length ? followupEn : [
            'Check post cards: API posts should show a URL/ID or a clear error, maps should show supervised placement or manual handoff.',
          ]),
        ].slice(0, 7),
      });
      if (currentPlan?.id) {
        await loadSocialPosts(currentPlan.id);
      }
      await loadSocialRuntimeStatus();
      setSocialDispatchExecutionReport(executionReport);
      setSocialDispatchPreview(null);
      setSocialLaunchPreflight(null);
    } catch (dispatchError) {
      const message = dispatchError instanceof Error ? dispatchError.message : (isRu ? 'Не удалось запустить scoped цикл' : 'Could not run scoped cycle');
      setError(message);
      try {
        await checkSocialLaunchPreflight();
      } catch {
        // The visible recovery summary below is enough if refresh also fails.
      }
      setActionSummary({
        tone: 'warning',
        text_ru: 'Первый цикл не запущен: LocalOS остановил внешнее исполнение.',
        text_en: 'The first cycle did not run: LocalOS stopped external execution.',
        details_ru: [
          message,
          apiDuePosts > 0
            ? `Если это API-публикация, повторите запуск только после dry-run и введите фразу подтверждения: ${externalPublishPhrase}.`
            : 'Повторите безопасную проверку запуска: она ничего не публикует и покажет текущий блокер.',
          'Яндекс/2ГИС всё равно остаются контролируемым или ручным размещением без финального автоклика.',
        ],
        details_en: [
          message,
          apiDuePosts > 0
            ? `If this is API publishing, rerun only after the dry-run and type the confirmation phrase: ${externalPublishPhrase}.`
            : 'Run the safe launch check again: it publishes nothing and shows the current blocker.',
          'Yandex/2GIS still stay supervised or manual without the final auto-click.',
        ],
      });
    } finally {
      setSocialBusyAction('');
    }
  };

  const recommendNextSocialPlan = async () => {
    if (!currentPlan?.id) return;
    setSocialBusyAction('recommend');
    setError('');
    setActionSummary(null);
    try {
      const recommendationPayload = await fetchSocialPlanRecommendation(currentPlan.id);
      const proposedCount = Number(recommendationPayload.proposed_changes?.length || 0);
      setActionSummary({
        tone: 'success',
        text_ru: proposedCount > 0
          ? `LocalOS подготовил предложения для корректировки плана: ${proposedCount}. Они не применены автоматически.`
          : 'LocalOS пересчитал рекомендации, но пока не нашёл изменений для применения.',
        text_en: proposedCount > 0
          ? `LocalOS prepared plan adjustment proposals: ${proposedCount}. They were not applied automatically.`
          : 'LocalOS recalculated recommendations, but found no changes to apply yet.',
      });
    } catch (recommendError) {
      const message = recommendError instanceof Error ? recommendError.message : (isRu ? 'Не удалось подготовить рекомендации' : 'Could not prepare recommendations');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const applySocialPlanRecommendation = async () => {
    if (!currentPlan?.id) return;
    setSocialBusyAction('apply-recommendation');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(currentPlan.id)}/social-posts/apply-recommendation`, {
        method: 'POST',
        body: JSON.stringify({ approved: true }),
      });
      await loadPlans();
      if (currentPlan?.id) {
        const planResponse = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(currentPlan.id)}`, {
          method: 'GET',
        });
        setCurrentPlan(planResponse.plan || currentPlan);
        await loadSocialPosts(currentPlan.id);
      }
      const approvalRecord = response.approval_record && typeof response.approval_record === 'object'
        ? response.approval_record
        : {};
      const approvedAt = String(approvalRecord.approved_at || '').trim();
      setActionSummary({
        tone: 'success',
        text_ru: `Корректировка применена после подтверждения: ${Number(response.applied_count || 0)} пунктов плана. Изменялись только будущие неопубликованные пункты${approvedAt ? ` · ${approvedAt}` : ''}.`,
        text_en: `Recommendation applied after approval: ${Number(response.applied_count || 0)} plan items. Only future unpublished items were changed${approvedAt ? ` · ${approvedAt}` : ''}.`,
      });
      setSocialRecommendationApproved(false);
    } catch (applyError) {
      const message = applyError instanceof Error ? applyError.message : (isRu ? 'Не удалось применить рекомендации' : 'Could not apply recommendations');
      setError(message);
    } finally {
      setSocialBusyAction('');
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
  return {
    openSocialPreparePreview, prepareSelectedSocialPosts, prepareSuggestedSocialPosts, executeSocialPreparePreview, approveSelectedSocialPosts, queueVisibleApprovedSocialPosts, queueSelectedSocialPosts, selectPublishedSocialPostsForResult,
    markSelectedSocialPostsPublished, recordSelectedSocialPostAttribution, fetchSocialPlanRecommendation, collectSocialPostMetricsForBusiness, previewSocialDispatch, checkSocialLaunchPreflight, runSocialDispatchOnce, recommendNextSocialPlan,
    applySocialPlanRecommendation, persistItemEdits
  };
};
