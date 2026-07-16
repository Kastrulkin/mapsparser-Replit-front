import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { CheckSquare, Globe, MapPinned, MoreHorizontal, Sparkles } from 'lucide-react';
import { _isSupervisedPlatform, _isSocialPostTextLocked, _socialSupervisedPayload, _socialOpenClawCapabilityLine, _socialSupervisedHandoffStateLabel, _socialSupervisedSafetySummary, _socialPlatformLabel, _socialPublishModeLabel, _socialStatusLabel, _socialStatusClassName, _socialPublishEvidenceClassName, _socialProofQualityLabel, _socialNextActionLabel, _socialItemQueueSummary, _contentTypeLabel, _itemLocationLabel, _planItemStatus, _humanizePlanTitle, _humanizePlanGoal, _sourceKindLabel, _seoViewsLabel, _inputDateValue, _formatPlanItemDate } from './helpers';

export const QueueItems = ({ scope }) => {
  const {
    isRu, draftEdits, setDraftEdits, themeEdits, setThemeEdits, dateEdits, setDateEdits, busyItemId,
    expandedDuplicateItemId, setExpandedDuplicateItemId, duplicateTargetSelections, duplicateDateOverrides, setDuplicateDateOverrides, recentGeneratedItemId, socialPostsByItem, socialTextEdits,
    setSocialTextEdits, manualPublishRefs, setManualPublishRefs, socialPublishRehearsals, socialBusyAction, setSelectedQueueItemId, setEditorItemId, showSelectedItemDetails,
    setShowSelectedItemDetails, selectedItemIds, readiness, isNetworkMode, visibleItems, selectedQueueItem, editorItem, availableItemLocations,
    toggleSelectedItem, saveItem, generateDraft, createNews, prepareSocialPosts, approveSocialPostItem, saveSocialPostText, queueSocialPostItem,
    markSocialPostPublished, rehearseSocialPostPublish, markSupervisedPostBlocked, createSupervisedPostTask, copySocialPostText, recordSocialPostAttribution, deleteItem, getDuplicateTargetLocationOptions,
    openDuplicateTargetPicker, toggleDuplicateTargetLocation, runItemSkip, runItemReschedule, runItemDuplicate, runItemDuplicateToOtherLocations, runItemDuplicateToSelectedLocations
  } = scope;
  return (
    <>
            {visibleItems.length > 0 ? (
              <div className="grid gap-4">
                <div id="content-plan-topic-queue" className="scroll-mt-6 rounded-[28px] border border-slate-200 bg-slate-50 p-3">
                  <div className="px-2 pb-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Очередь тем' : 'Topic queue'}
                    </div>
                    <div className="mt-1 text-sm text-slate-600">
                      {isRu ? 'Выберите тему, чтобы открыть редактор в окне.' : 'Select one item to open the editor in a modal.'}
                    </div>
                  </div>
                  <div className="max-h-[680px] space-y-2 overflow-y-auto pr-1">
                    {visibleItems.map((item) => {
                      const status = _planItemStatus(item, isRu);
                      const isSelected = selectedQueueItem?.id === item.id;
                      const itemSocialPosts = socialPostsByItem[item.id] || [];
                      const itemSocialSummary = _socialItemQueueSummary(itemSocialPosts, isRu);
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => {
                            setSelectedQueueItemId(item.id);
                            setEditorItemId(item.id);
                            setShowSelectedItemDetails(false);
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
                          {itemSocialPosts.length > 0 ? (
                            <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className={itemSocialSummary.className}>
                                  {itemSocialSummary.label}
                                </span>
                                <span className="text-[11px] font-medium text-slate-500">
                                  {itemSocialSummary.totalLabel}
                                </span>
                              </div>
                              <div className="mt-1 text-xs leading-5 text-slate-600">
                                {itemSocialSummary.detail}
                              </div>
                            </div>
                          ) : (
                            <div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
                              {isRu
                                ? 'Каналы ещё не подготовлены: откройте тему и нажмите “Подготовить каналы”.'
                                : 'Channels are not prepared yet: open the topic and click “Prepare channels”.'}
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {editorItem ? (() => {
                  const item = editorItem;
                  const currentDraft = draftEdits[item.id] !== undefined ? draftEdits[item.id] : item.draft_text;
                  const currentTheme = themeEdits[item.id] !== undefined ? themeEdits[item.id] : item.theme;
                  const currentDate = dateEdits[item.id] !== undefined ? dateEdits[item.id] : item.scheduled_for;
                  const currentInputDate = _inputDateValue(currentDate);
                  const duplicateTargetOptions = getDuplicateTargetLocationOptions(item);
                  const selectedDuplicateTargets = duplicateTargetSelections[item.id] || [];
                  const duplicateTargetDate = duplicateDateOverrides[item.id] || currentInputDate;
                  const status = _planItemStatus(item, isRu);
                  const itemSocialPosts = socialPostsByItem[item.id] || [];
                  const hasDraft = Boolean(String(currentDraft || '').trim());
                  const hasNews = Boolean(String(item.usernews_id || '').trim());
                  return (
                    <div
                      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm"
                      onClick={() => setEditorItemId('')}
                    >
                      <div
                        className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-[28px] border border-slate-200 bg-white p-5 shadow-2xl"
                        onClick={(event) => event.stopPropagation()}
                      >
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
                          <button
                            type="button"
                            onClick={() => setEditorItemId('')}
                            className="col-span-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                          >
                            {isRu ? 'Закрыть редактор' : 'Close editor'}
                          </button>
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

                      <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <div className="text-sm font-semibold text-slate-950">
                              {isRu ? 'Каналы публикации' : 'Publishing channels'}
                            </div>
                            <div className="mt-1 text-sm leading-6 text-slate-600">
                              {isRu
                                ? 'Один пункт плана раскладывается на карты и соцсети. Внешняя публикация идёт только после проверки.'
                                : 'One plan item becomes map and social posts. External publishing starts only after review.'}
                            </div>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant={itemSocialPosts.length ? 'outline' : 'default'}
                            onClick={() => { void prepareSocialPosts(item.id); }}
                            disabled={socialBusyAction === `prepare:${item.id}` || !String(currentDraft || currentTheme || '').trim()}
                          >
                            <Globe className="mr-2 h-4 w-4" />
                            {itemSocialPosts.length
                              ? (isRu ? 'Обновить каналы' : 'Refresh channels')
                              : (isRu ? 'Подготовить каналы' : 'Prepare channels')}
                          </Button>
                        </div>

                        {itemSocialPosts.length > 0 ? (
                          <div className="mt-4 grid gap-3 xl:grid-cols-2">
                            {itemSocialPosts.map((post) => {
                              const postBusy = socialBusyAction.endsWith(`:${post.id}`);
                              const needsReview = post.status === 'draft' || post.status === 'needs_review';
                              const canQueue = post.status === 'approved';
                              const canMarkPublished = post.status === 'needs_supervised_publish' || post.status === 'needs_manual_publish';
                              const canRecordResult = post.status === 'published';
                              const isSupervisedPost = _isSupervisedPlatform(post.platform);
                              const canCreateSupervisedTask = isSupervisedPost
                                && (post.status === 'approved' || post.status === 'queued' || post.status === 'needs_manual_publish');
                              const publishEvidence = post.publish_evidence || null;
                              const resultPacket = publishEvidence?.result_packet || null;
                              const publishRehearsal = socialPublishRehearsals[post.id] || null;
                              const supervisedPayload = _socialSupervisedPayload(post);
                              const placementPacket = publishEvidence?.placement_packet || null;
                              const supervisedHandoffState = supervisedPayload?.handoff_state || null;
                              const manualRefs = manualPublishRefs[post.id] || {
                                url: String(post.provider_post_url || ''),
                                id: String(post.provider_post_id || ''),
                              };
                              const postTextFallback = String(currentDraft || '').trim();
                              const postTextValue = String(socialTextEdits[post.id] ?? post.platform_text ?? postTextFallback);
                              const postTextLocked = _isSocialPostTextLocked(post.status);
                              const postTextDirty = postTextValue.trim() !== String(post.platform_text || '').trim();
                              const supervisedLedgerId = String(post.metadata_json?.agent_action_ledger_id || '').trim();
                              const supervisedCapabilityLine = _socialOpenClawCapabilityLine(supervisedPayload?.openclaw_capability_status, isRu);
                              const supervisedTaskStatus = String(supervisedPayload?.task_status || '').trim();
                              const supervisedActionRef = String(supervisedPayload?.openclaw_action_ref || '').trim();
                              const supervisedManualHandoff = supervisedPayload?.manual_handoff || null;
                              const supervisedManualInstruction = String(
                                isRu
                                  ? supervisedPayload?.manual_instruction_ru || supervisedManualHandoff?.instruction_ru || ''
                                  : supervisedPayload?.manual_instruction_en || supervisedManualHandoff?.instruction_en || ''
                              ).trim();
                              const supervisedManualChecklistSource = isRu
                                ? supervisedPayload?.manual_checklist_ru || supervisedManualHandoff?.checklist_ru || publishEvidence?.manual_checklist_ru || []
                                : supervisedPayload?.manual_checklist_en || supervisedManualHandoff?.checklist_en || publishEvidence?.manual_checklist_en || [];
                              const supervisedManualChecklist = Array.isArray(supervisedManualChecklistSource)
                                ? supervisedManualChecklistSource.filter(Boolean).map(String)
                                : [];
                              const supervisedCopyReadyText = String(
                                placementPacket?.copy_ready_text || supervisedPayload?.copy_ready_text || supervisedManualHandoff?.copy_ready_text || publishEvidence?.copy_ready_text || ''
                              ).trim();
                              const supervisedProfileHint = String(
                                placementPacket?.profile_hint || supervisedPayload?.profile_hint || supervisedManualHandoff?.profile_hint || publishEvidence?.profile_hint || ''
                              ).trim();
                              const supervisedTargetUrl = String(
                                placementPacket?.target_url || supervisedPayload?.target_url || supervisedManualHandoff?.target_url || publishEvidence?.target_url || ''
                              ).trim();
                              const placementChecklistSource = isRu
                                ? placementPacket?.checklist_ru || []
                                : placementPacket?.checklist_en || [];
                              const placementChecklist = Array.isArray(placementChecklistSource)
                                ? placementChecklistSource.filter(Boolean).map(String)
                                : [];
                              const placementHandoffChecklistSource = isRu
                                ? placementPacket?.handoff_checklist_ru || supervisedPayload?.handoff_checklist_ru || []
                                : placementPacket?.handoff_checklist_en || supervisedPayload?.handoff_checklist_en || [];
                              const placementHandoffChecklist = Array.isArray(placementHandoffChecklistSource)
                                ? placementHandoffChecklistSource.filter(Boolean).map(String).slice(0, 5)
                                : [];
                              const placementNextAction = String(
                                isRu
                                  ? placementPacket?.owner_next_action_ru || ''
                                  : placementPacket?.owner_next_action_en || ''
                              ).trim();
                              const placementTaskId = String(placementPacket?.automation_task_id || post.automation_task_id || '').trim();
                              const placementOutboxId = String(placementPacket?.openclaw_outbox_id || '').trim();
                              const placementLedgerId = String(placementPacket?.agent_action_ledger_id || supervisedLedgerId || '').trim();
                              const placementOperatorNextAction = String(
                                isRu
                                  ? placementPacket?.operator_next_action_ru || supervisedPayload?.operator_next_action_ru || ''
                                  : placementPacket?.operator_next_action_en || supervisedPayload?.operator_next_action_en || ''
                              ).trim();
                              const placementCompletionFields = Array.isArray(placementPacket?.completion_required_fields)
                                ? placementPacket.completion_required_fields.filter(Boolean).map(String).slice(0, 5)
                                : [];
                              const placementDoneCriteriaFallback = isRu
                                ? [
                                  'Предпросмотр на площадке показан человеку.',
                                  'Финальную публикацию нажал человек, не браузер-автоматизация.',
                                  'В LocalOS внесена ссылка или ID опубликованного поста, если площадка их даёт.',
                                  'Пост отмечен размещённым, чтобы реакции и заявки попали в следующий план.',
                                ]
                                : [
                                  'The platform preview was shown to a human.',
                                  'The final publish click was made by a human, not browser automation.',
                                  'LocalOS has the published post URL or ID if the platform provides one.',
                                  'The post is marked as published so reactions and leads can inform the next plan.',
                                ];
                              const placementDoneCriteriaSource = isRu
                                ? placementPacket?.done_criteria_ru || placementDoneCriteriaFallback
                                : placementPacket?.done_criteria_en || placementDoneCriteriaFallback;
                              const placementDoneCriteria = Array.isArray(placementDoneCriteriaSource)
                                ? placementDoneCriteriaSource.filter(Boolean).map(String).slice(0, 5)
                                : [];
                              const placementReadyChips = [
                                placementPacket?.target_ready
                                  ? (isRu ? 'цель готова' : 'target ready')
                                  : (isRu ? 'нужна ссылка на профиль' : 'profile link needed'),
                                placementPacket?.copy_ready
                                  ? (isRu ? 'текст готов' : 'copy ready')
                                  : (isRu ? 'нужен текст' : 'copy needed'),
                                placementPacket?.openclaw_task_requested
                                  ? (isRu ? 'задача отправлена' : 'task sent')
                                  : (isRu ? 'ожидает запуска' : 'waiting to start'),
                                placementPacket?.browser_final_click_allowed === false
                                  ? (isRu ? 'финальный клик человеком' : 'human final click')
                                  : '',
                              ].filter(Boolean);
                              const supervisedFallbackReasons = Array.isArray(supervisedPayload?.fallback_reasons)
                                ? supervisedPayload.fallback_reasons.filter(Boolean).map(String)
                                : [];
                              const supervisedSafety = _socialSupervisedSafetySummary(supervisedPayload?.safety_contract, isRu);
                              const supervisedHandoffStatus = String(
                                isRu
                                  ? supervisedHandoffState?.owner_status_ru || ''
                                  : supervisedHandoffState?.owner_status_en || ''
                              ).trim();
                              const supervisedHandoffNextAction = String(
                                isRu
                                  ? supervisedHandoffState?.owner_next_action_ru || ''
                                  : supervisedHandoffState?.owner_next_action_en || ''
                              ).trim();
                              const supervisedHandoffStateLabel = _socialSupervisedHandoffStateLabel(
                                String(supervisedHandoffState?.state || ''),
                                isRu,
                              );
                              const preflightStatus = String(post.metadata_json?.queue_preflight_status || post.metadata_json?.provider_status || '').trim();
                              const preflightMessage = String(
                                isRu
                                  ? post.metadata_json?.queue_preflight_message_ru || post.metadata_json?.provider_note || ''
                                  : post.metadata_json?.queue_preflight_message_en || post.metadata_json?.provider_note || ''
                              ).trim();
                              const nextActionLabel = _socialNextActionLabel(post.next_action || '', isRu);
                              const hasNextAction = Boolean(String(post.next_action || '').trim());
                              const evidenceTitle = String(isRu ? publishEvidence?.title_ru || '' : publishEvidence?.title_en || '').trim();
                              const evidenceSummary = String(isRu ? publishEvidence?.summary_ru || '' : publishEvidence?.summary_en || '').trim();
                              const evidenceNextAction = String(isRu ? publishEvidence?.next_action_ru || '' : publishEvidence?.next_action_en || '').trim();
                              const evidenceProofUrl = String(publishEvidence?.proof_url || post.provider_post_url || '').trim();
                              const evidenceProofId = String(publishEvidence?.proof_id || post.provider_post_id || '').trim();
                              const evidenceProviderStatus = String(publishEvidence?.provider_status || '').trim();
                              const scheduleAttention = post.schedule_attention || {};
                              const scheduleNeedsAttention = Boolean(scheduleAttention.requires_attention);
                              const scheduleAttentionMessage = String(
                                isRu
                                  ? scheduleAttention.message_ru || ''
                                  : scheduleAttention.message_en || ''
                              ).trim();
                              const scheduleAttentionNextAction = String(
                                isRu
                                  ? scheduleAttention.next_action_ru || ''
                                  : scheduleAttention.next_action_en || ''
                              ).trim();
                              const evidenceProofSource = String(publishEvidence?.proof_source || '').trim();
                              const evidenceProofQuality = String(publishEvidence?.proof_quality || '').trim();
                              const rehearsalSummary = String(isRu ? publishRehearsal?.summary_ru || '' : publishRehearsal?.summary_en || '').trim();
                              const rehearsalNextAction = String(isRu ? publishRehearsal?.next_action_ru || '' : publishRehearsal?.next_action_en || '').trim();
                              const rehearsalAction = String(isRu ? publishRehearsal?.dispatch_decision?.action_label_ru || '' : publishRehearsal?.dispatch_decision?.action_label_en || '').trim();
                              const rehearsalReason = String(isRu ? publishRehearsal?.dispatch_decision?.reason_label_ru || '' : publishRehearsal?.dispatch_decision?.reason_label_en || '').trim();
                              const rehearsalReady = Boolean(publishRehearsal?.ready_for_execution);
                              const rehearsalBlockers = Array.isArray(publishRehearsal?.blockers) ? publishRehearsal.blockers : [];
                              const actionHint = needsReview
                                  ? {
                                    tone: 'safe',
                                    textRu: 'Подтверждение только фиксирует, что текст проверен. Наружу ничего не отправится.',
                                    textEn: 'Approval only records that the copy was reviewed. Nothing is sent externally.',
                                  }
                                  : canQueue
                                    ? {
                                      tone: 'queue',
                                      textRu: isSupervisedPost
                                        ? 'Расписание зафиксирует дату. Для Яндекс/2ГИС LocalOS создаст контролируемое или ручное размещение, не автопубликацию.'
                                        : 'Расписание передаст пост worker-у: API-публикация начнётся только по дате и только при готовом канале.',
                                      textEn: isSupervisedPost
                                        ? 'Queueing records the date. For Yandex/2GIS, LocalOS creates supervised placement, not autopublish.'
                                        : 'Queueing hands the post to the worker: API publishing starts only on schedule and only when the channel is ready.',
                                    }
                                    : post.status === 'queued'
                                      ? {
                                        tone: 'queue',
                                        textRu: isSupervisedPost
                                          ? 'Пост ждёт дату. Когда наступит время, он перейдёт в контролируемое или ручное размещение.'
                                          : 'Пост ждёт дату. Worker обработает только due-публикации с подтверждённым текстом.',
                                        textEn: isSupervisedPost
                                          ? 'The post is waiting for its date. When due, it moves to supervised placement.'
                                          : 'The post is waiting for its date. The worker processes only due posts with approved copy.',
                                      }
                                      : canCreateSupervisedTask
                                        ? {
                                          tone: 'controlled',
                                          textRu: 'Контролируемое размещение подготовит текст, ссылку и инструкцию. Финальную кнопку публикации нажимает человек.',
                                          textEn: 'Supervised placement prepares copy, link, and instructions. A human clicks the final publish button.',
                                        }
                                        : canMarkPublished
                                          ? {
                                            tone: 'manual',
                                            textRu: 'Используйте это, когда пост уже размещён вручную или через контролируемое размещение, чтобы LocalOS смог собрать результат.',
                                            textEn: 'Use this after manual or supervised placement so LocalOS can collect results.',
                                          }
                                          : null;
                                return (
                                <div key={post.id} className="rounded-2xl border border-slate-200 bg-white p-3">
                                  <div className="flex flex-wrap items-start justify-between gap-2">
                                    <div>
                                      <div className="font-semibold text-slate-950">
                                        {_socialPlatformLabel(post.platform, isRu)}
                                      </div>
                                      <div className="mt-1 text-xs text-slate-500">
                                        {_socialPublishModeLabel(post.publish_mode, isRu)}
                                      </div>
                                    </div>
                                    <span className={_socialStatusClassName(post.status)}>
                                      {_socialStatusLabel(post.status, isRu)}
                                    </span>
                                  </div>
                                  {hasNextAction ? (
                                    <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-800">
                                      <div className="font-semibold text-blue-950">
                                        {isRu ? 'Следующий шаг' : 'Next action'}
                                      </div>
                                      <div>{nextActionLabel}</div>
                                    </div>
                                  ) : null}
                                  {scheduleNeedsAttention ? (
                                    <div
                                      data-testid={`social-post-schedule-attention-${post.id}`}
                                      className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"
                                    >
                                      <div className="font-semibold text-amber-950">
                                        {isRu ? 'Проверьте дату публикации' : 'Check publish date'}
                                      </div>
                                      {scheduleAttentionMessage ? <div>{scheduleAttentionMessage}</div> : null}
                                      {scheduleAttentionNextAction ? (
                                        <div className="mt-1">
                                          <span className="font-semibold">{isRu ? 'Что сделать: ' : 'Next: '}</span>
                                          {scheduleAttentionNextAction}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                  <div className="mt-3 space-y-2">
                                    <div className="flex items-center justify-between gap-2">
                                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                                        {isRu ? 'Текст для канала' : 'Channel copy'}
                                      </div>
                                      {postTextLocked ? (
                                        <span className="text-[11px] font-medium text-slate-400">
                                          {isRu ? 'заблокировано после расписания' : 'locked after queue'}
                                        </span>
                                      ) : null}
                                    </div>
                                    <Textarea
                                      rows={5}
                                      value={postTextValue}
                                      onChange={(event) => setSocialTextEdits((prev) => ({ ...prev, [post.id]: event.target.value }))}
                                      disabled={postTextLocked || postBusy}
                                      placeholder={isRu ? 'Текст ещё не подготовлен' : 'Text is not prepared yet'}
                                    />
                                    {!postTextLocked && postTextDirty ? (
                                      <div className="flex flex-wrap items-center gap-2">
                                        <Button
                                          type="button"
                                          size="sm"
                                          variant="outline"
                                          onClick={() => { void saveSocialPostText(post, postTextFallback); }}
                                          disabled={postBusy}
                                        >
                                          {socialBusyAction === `save-text:${post.id}`
                                            ? (isRu ? 'Сохраняем...' : 'Saving...')
                                            : (isRu ? 'Сохранить текст' : 'Save copy')}
                                        </Button>
                                        <span className="text-xs leading-5 text-amber-700">
                                          {isRu
                                            ? 'После сохранения текст снова нужно подтвердить перед публикацией.'
                                            : 'After saving, copy must be approved again before publishing.'}
                                        </span>
                                      </div>
                                    ) : null}
                                  </div>
                                  {isSupervisedPost ? (
                                    <div
                                      data-testid="social-supervised-handoff"
                                      className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800"
                                    >
                                      <div className="font-semibold text-amber-950">
                                        {isRu ? 'Контролируемое размещение' : 'Supervised placement'}
                                      </div>
                                      <div className="mt-1">
                                        {isRu
                                          ? 'Для этого канала LocalOS готовит задачу для OpenClaw/manual handoff, а не делает вид стабильной API-автопубликации.'
                                          : 'For this channel LocalOS prepares an OpenClaw/manual handoff task instead of pretending stable API autopublishing exists.'}
                                      </div>
                                      {placementPacket ? (
                                        <div
                                          data-testid="social-supervised-placement-packet"
                                          className="mt-3 rounded-lg border border-amber-200 bg-white px-3 py-2 text-amber-950"
                                        >
                                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                            <div>
                                              <div className="font-semibold">
                                                {isRu ? 'Пакет для размещения' : 'Placement packet'}
                                              </div>
                                              <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                                {placementNextAction || (isRu
                                                  ? 'Откройте площадку, проверьте предпросмотр и завершите размещение вручную.'
                                                  : 'Open the platform, review the preview, and finish placement manually.')}
                                              </div>
                                            </div>
                                            <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-800">
                                              {placementPacket.manual_fallback_required
                                                ? (isRu ? 'ручной режим' : 'manual mode')
                                                : (isRu ? 'контролируемо' : 'supervised')}
                                            </span>
                                          </div>
                                          <div className="mt-2 grid gap-2 sm:grid-cols-2">
                                            <div className="rounded-md bg-amber-50 px-2 py-1.5">
                                              <div className="font-semibold">
                                                {isRu ? 'Куда размещать' : 'Where to post'}
                                              </div>
                                              <div className="mt-1 break-all text-[11px] leading-5 text-amber-900">
                                                {supervisedTargetUrl || supervisedProfileHint || (isRu ? 'Ссылка на профиль не найдена' : 'Profile link is missing')}
                                              </div>
                                            </div>
                                            <div className="rounded-md bg-amber-50 px-2 py-1.5">
                                              <div className="font-semibold">
                                                {isRu ? 'Что готово' : 'Ready assets'}
                                              </div>
                                              <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                                {isRu
                                                  ? `текст: ${placementPacket.copy_ready ? 'готов' : 'нужен'} · шагов: ${Number(placementPacket.checklist_count || placementChecklist.length || 0)}`
                                                  : `copy: ${placementPacket.copy_ready ? 'ready' : 'needed'} · steps: ${Number(placementPacket.checklist_count || placementChecklist.length || 0)}`}
                                              </div>
                                            </div>
                                          </div>
                                          {placementReadyChips.length > 0 ? (
                                            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                                              {placementReadyChips.map((chip) => (
                                                <span key={`${post.id}:placement-chip:${chip}`} className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                                                  {chip}
                                                </span>
                                              ))}
                                            </div>
                                          ) : null}
                                          {placementTaskId || placementOutboxId || placementLedgerId ? (
                                            <div className="mt-2 grid gap-1 text-[11px] text-amber-900 sm:grid-cols-3">
                                              {placementTaskId ? (
                                                <div>
                                                  <span className="font-semibold">task:</span>{' '}
                                                  <span className="font-mono">{placementTaskId}</span>
                                                </div>
                                              ) : null}
                                              {placementOutboxId ? (
                                                <div>
                                                  <span className="font-semibold">outbox:</span>{' '}
                                                  <span className="font-mono">{placementOutboxId}</span>
                                                </div>
                                              ) : null}
                                              {placementLedgerId ? (
                                                <div>
                                                  <span className="font-semibold">ledger:</span>{' '}
                                                  <span className="font-mono">{placementLedgerId}</span>
                                                </div>
                                              ) : null}
                                            </div>
                                          ) : null}
                                          {placementOperatorNextAction || placementCompletionFields.length > 0 || placementPacket.preview_required ? (
                                            <div className="mt-2 rounded-md bg-amber-50 px-2 py-1.5 text-[11px] leading-5 text-amber-900">
                                              {placementOperatorNextAction ? (
                                                <div>
                                                  <span className="font-semibold">
                                                    {isRu ? 'Как выполнить: ' : 'How to execute: '}
                                                  </span>
                                                  {placementOperatorNextAction}
                                                </div>
                                              ) : null}
                                              {placementPacket.preview_required ? (
                                                <div>
                                                  <span className="font-semibold">
                                                    {isRu ? 'Предпросмотр: ' : 'Preview: '}
                                                  </span>
                                                  {isRu ? 'обязателен перед финальным кликом' : 'required before the final click'}
                                                </div>
                                              ) : null}
                                              {placementCompletionFields.length > 0 ? (
                                                <div>
                                                  <span className="font-semibold">
                                                    {isRu ? 'Вернуть результат: ' : 'Return result: '}
                                                  </span>
                                                  {placementCompletionFields.join(', ')}
                                                </div>
                                              ) : null}
                                            </div>
                                          ) : null}
                                          {placementHandoffChecklist.length > 0 ? (
                                            <div
                                              data-testid="social-supervised-handoff-checklist"
                                              className="mt-2 rounded-md border border-amber-100 bg-amber-50 px-2 py-1.5 text-[11px] leading-5 text-amber-900"
                                            >
                                              <div className="font-semibold text-amber-950">
                                                {isRu ? 'Маршрут handoff' : 'Handoff route'}
                                              </div>
                                              <ol className="mt-1 list-decimal space-y-1 pl-4">
                                                {placementHandoffChecklist.map((step, index) => (
                                                  <li key={`${post.id}:handoff-checklist:${index}`}>{step}</li>
                                                ))}
                                              </ol>
                                            </div>
                                          ) : null}
                                          {placementDoneCriteria.length > 0 ? (
                                            <div
                                              data-testid="social-supervised-done-criteria"
                                              className="mt-2 rounded-md border border-amber-100 bg-amber-50 px-2 py-1.5 text-[11px] leading-5 text-amber-900"
                                            >
                                              <div className="font-semibold text-amber-950">
                                                {isRu ? 'Готово, когда' : 'Done when'}
                                              </div>
                                              <ul className="mt-1 list-disc space-y-1 pl-4">
                                                {placementDoneCriteria.map((criterion, index) => (
                                                  <li key={`${post.id}:done-criterion:${index}`}>{criterion}</li>
                                                ))}
                                              </ul>
                                            </div>
                                          ) : null}
                                        </div>
                                      ) : null}
                                      {supervisedHandoffState ? (
                                        <div className="mt-3 rounded-lg border border-amber-200 bg-white px-3 py-2 text-amber-950">
                                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                            <div>
                                              <div className="font-semibold">
                                                {isRu ? 'Состояние handoff' : 'Handoff state'}
                                              </div>
                                              <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                                {supervisedHandoffStatus || supervisedHandoffStateLabel}
                                              </div>
                                              {supervisedHandoffNextAction ? (
                                                <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                                  <span className="font-semibold">
                                                    {isRu ? 'Что сделать: ' : 'Next: '}
                                                  </span>
                                                  {supervisedHandoffNextAction}
                                                </div>
                                              ) : null}
                                            </div>
                                            {supervisedHandoffStateLabel ? (
                                              <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-800">
                                                {supervisedHandoffStateLabel}
                                              </span>
                                            ) : null}
                                          </div>
                                          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                                            {supervisedHandoffState.task_payload_ready ? (
                                              <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-800">
                                                {isRu ? 'payload готов' : 'payload ready'}
                                              </span>
                                            ) : null}
                                            {supervisedHandoffState.openclaw_ready ? (
                                              <span className="rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-800">
                                                {isRu ? 'OpenClaw готов' : 'OpenClaw ready'}
                                              </span>
                                            ) : (
                                              <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                                                {isRu ? 'ручной режим' : 'manual fallback'}
                                              </span>
                                            )}
                                            {supervisedHandoffState.openclaw_task_requested ? (
                                              <span className="rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-800">
                                                {isRu ? 'task отправлен' : 'task requested'}
                                              </span>
                                            ) : (
                                              <span className="rounded-full bg-white px-2 py-0.5 font-medium text-amber-800">
                                                {isRu ? 'task не отправлен во внешний runtime' : 'task not sent to external runtime'}
                                              </span>
                                            )}
                                            {supervisedHandoffState.ledger_recorded ? (
                                              <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                                                {isRu ? 'журнал записан' : 'ledger recorded'}
                                              </span>
                                            ) : null}
                                            {supervisedHandoffState.browser_final_click_allowed === false ? (
                                              <span className="rounded-full bg-red-50 px-2 py-0.5 font-medium text-red-700">
                                                {isRu ? 'финальный клик запрещён' : 'final click forbidden'}
                                              </span>
                                            ) : null}
                                          </div>
                                          {supervisedHandoffState.openclaw_outbox_id ? (
                                            <div className="mt-2 font-mono text-[11px] text-amber-900">
                                              outbox: {supervisedHandoffState.openclaw_outbox_id}
                                            </div>
                                          ) : null}
                                        </div>
                                      ) : null}
                                      {supervisedPayload?.instruction_ru || supervisedPayload?.instruction_en ? (
                                        <div className="mt-2 text-amber-900">
                                          {isRu
                                            ? String(supervisedPayload.instruction_ru || '')
                                            : String(supervisedPayload.instruction_en || '')}
                                        </div>
                                      ) : null}
                                      <div className="mt-3 grid gap-2 rounded-lg bg-white px-3 py-2 text-[11px] leading-5 text-amber-950 sm:grid-cols-2">
                                        <div>
                                          <div className="font-semibold">
                                            {isRu ? 'Ассистент сделает' : 'Assistant will'}
                                          </div>
                                          <div className="mt-1 text-amber-900">
                                            {supervisedSafety.allowed.join(', ')}
                                          </div>
                                        </div>
                                        <div>
                                          <div className="font-semibold">
                                            {isRu ? 'Ассистент не сделает' : 'Assistant will not'}
                                          </div>
                                          <div className="mt-1 text-amber-900">
                                            {supervisedSafety.forbidden.join(', ')}
                                          </div>
                                        </div>
                                        {supervisedSafety.fallback.length > 0 ? (
                                          <div className="sm:col-span-2 text-amber-900">
                                            <span className="font-semibold">
                                              {isRu ? 'Если мешает логин/капча/интерфейс: ' : 'If login/captcha/UI blocks it: '}
                                            </span>
                                            {supervisedSafety.fallback.join(', ')}
                                          </div>
                                        ) : null}
                                      </div>
                                      {supervisedManualInstruction || supervisedManualChecklist.length > 0 || supervisedCopyReadyText ? (
                                        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-amber-950">
                                          <div className="font-semibold">
                                            {isRu ? 'Ручной режим без догадок' : 'Manual fallback without guessing'}
                                          </div>
                                          {supervisedManualInstruction ? (
                                            <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                              {supervisedManualInstruction}
                                            </div>
                                          ) : null}
                                          {supervisedProfileHint ? (
                                            <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                              {isRu ? 'Профиль: ' : 'Profile: '}
                                              {supervisedProfileHint}
                                            </div>
                                          ) : null}
                                          {supervisedCopyReadyText ? (
                                            <div className="mt-2 rounded-md border border-amber-100 bg-amber-50 px-2 py-1.5 text-[11px] leading-5 text-slate-700">
                                              {supervisedCopyReadyText}
                                            </div>
                                          ) : null}
                                          {supervisedManualChecklist.length > 0 ? (
                                            <ol className="mt-2 list-decimal space-y-1 pl-4 text-[11px] leading-5 text-amber-900">
                                              {supervisedManualChecklist.map((step, index) => (
                                                <li key={`${post.id}:manual-step:${index}`}>{step}</li>
                                              ))}
                                            </ol>
                                          ) : null}
                                        </div>
                                      ) : null}
                                      {post.automation_task_id || supervisedTaskStatus || supervisedActionRef || supervisedTargetUrl ? (
                                        <div className="mt-3 grid gap-2 rounded-lg bg-white px-3 py-2 text-[11px] text-amber-950 sm:grid-cols-2">
                                          {post.automation_task_id ? (
                                            <div>
                                              <span className="font-semibold">task:</span>{' '}
                                              <span className="font-mono">{post.automation_task_id}</span>
                                            </div>
                                          ) : null}
                                          {supervisedTaskStatus ? (
                                            <div>
                                              <span className="font-semibold">status:</span>{' '}
                                              <span className="font-mono">{supervisedTaskStatus}</span>
                                            </div>
                                          ) : null}
                                          {supervisedActionRef ? (
                                            <div>
                                              <span className="font-semibold">action:</span>{' '}
                                              <span className="font-mono">{supervisedActionRef}</span>
                                            </div>
                                          ) : null}
                                          {supervisedTargetUrl ? (
                                            <div>
                                              <span className="font-semibold">{isRu ? 'цель:' : 'target:'}</span>{' '}
                                              <span className="break-all">{supervisedTargetUrl}</span>
                                            </div>
                                          ) : null}
                                        </div>
                                      ) : null}
                                      {supervisedLedgerId ? (
                                        <div className="mt-1 font-mono text-[11px] text-amber-900">
                                          ledger: {supervisedLedgerId}
                                        </div>
                                      ) : null}
                                      {supervisedCapabilityLine ? (
                                        <div className="mt-1 text-[11px] text-amber-900">
                                          {supervisedCapabilityLine}
                                        </div>
                                      ) : null}
                                      {supervisedFallbackReasons.length > 0 ? (
                                        <div className="mt-1 text-[11px] text-amber-900">
                                          {isRu ? 'ручной режим: ' : 'fallback: '}
                                          {supervisedFallbackReasons.join(', ')}
                                        </div>
                                      ) : null}
                                      {post.automation_task_id || supervisedLedgerId ? (
                                        <div className="mt-2 text-[11px] font-medium text-amber-900">
                                          {isRu
                                            ? 'Журнал действия создан; финальная публикация остаётся за человеком.'
                                            : 'Action ledger is recorded; final publishing stays human-controlled.'}
                                        </div>
                                        ) : null}
                                      </div>
                                    ) : null}
                                    {publishEvidence && (evidenceTitle || evidenceSummary || evidenceNextAction || evidenceProofUrl || evidenceProofId) ? (
                                      <div className={_socialPublishEvidenceClassName(publishEvidence.tone || '')}>
                                        {evidenceTitle ? (
                                          <div className="font-semibold">
                                            {evidenceTitle}
                                          </div>
                                        ) : null}
                                        {evidenceSummary ? (
                                          <div className="mt-1">
                                            {evidenceSummary}
                                          </div>
                                        ) : null}
                                        {evidenceNextAction ? (
                                          <div className="mt-1 font-medium">
                                            {evidenceNextAction}
                                          </div>
                                        ) : null}
                                        {evidenceProofQuality || evidenceProofSource || publishEvidence.ready_for_metrics || publishEvidence.external_publish_proven ? (
                                          <div
                                            data-testid="social-provider-proof-quality"
                                            className="mt-2 flex flex-wrap gap-1.5 text-[11px]"
                                          >
                                            {evidenceProofQuality ? (
                                              <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                                {isRu ? 'proof: ' : 'proof: '}
                                                {_socialProofQualityLabel(evidenceProofQuality, isRu)}
                                              </span>
                                            ) : null}
                                            {evidenceProofSource ? (
                                              <span className="rounded-full bg-white/70 px-2 py-0.5 font-mono">
                                                {evidenceProofSource}
                                              </span>
                                            ) : null}
                                            {publishEvidence.external_publish_proven ? (
                                              <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">
                                                {isRu ? 'внешняя публикация подтверждена' : 'external publish proven'}
                                              </span>
                                            ) : null}
                                            {publishEvidence.ready_for_metrics ? (
                                              <span className="rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-700">
                                                {isRu ? 'готово к метрикам' : 'ready for metrics'}
                                              </span>
                                            ) : null}
                                            {publishEvidence.manual_confirmation ? (
                                              <span className="rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
                                                {isRu ? 'ручная отметка' : 'manual confirmation'}
                                              </span>
                                            ) : null}
                                          </div>
                                        ) : null}
                                        {evidenceProofUrl || evidenceProofId || evidenceProviderStatus ? (
                                          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                                            {evidenceProofUrl ? (
                                              <a
                                                href={evidenceProofUrl}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="font-medium underline underline-offset-2"
                                              >
                                                {isRu ? 'Открыть опубликованный пост' : 'Open published post'}
                                              </a>
                                            ) : null}
                                            {evidenceProofId ? (
                                              <span className="font-mono">
                                                id: {evidenceProofId}
                                              </span>
                                            ) : null}
                                            {evidenceProviderStatus ? (
                                              <span className="font-mono">
                                                status: {evidenceProviderStatus}
                                              </span>
                                            ) : null}
                                          </div>
                                        ) : null}
                                      </div>
                                    ) : null}
                                    {post.last_error && !publishEvidence ? (
                                      <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-700">
                                        {post.last_error}
                                      </div>
                                    ) : null}
                                  {!isSupervisedPost && (preflightMessage || preflightStatus) ? (
                                    <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
                                      <div className="font-semibold text-amber-950">
                                        {isRu ? 'Готовность канала' : 'Channel readiness'}
                                      </div>
                                      {preflightMessage ? (
                                        <div className="mt-1 text-amber-900">{preflightMessage}</div>
                                      ) : null}
                                      {preflightStatus ? (
                                        <div className="mt-1 font-mono text-[11px] text-amber-900">
                                          status: {preflightStatus}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                  {publishRehearsal ? (
                                    <div
                                      data-testid="social-publish-rehearsal"
                                      className={[
                                        'mt-3 rounded-xl border px-3 py-2 text-xs leading-5',
                                        rehearsalReady
                                          ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                                          : 'border-amber-200 bg-amber-50 text-amber-800',
                                      ].join(' ')}
                                    >
                                      <div className={rehearsalReady ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                                        {isRu ? 'Проверка запуска' : 'Launch check'}
                                      </div>
                                      {rehearsalSummary ? (
                                        <div className="mt-1">{rehearsalSummary}</div>
                                      ) : null}
                                      {rehearsalNextAction ? (
                                        <div className="mt-1 font-medium">
                                          {rehearsalNextAction}
                                        </div>
                                      ) : null}
                                      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                                        <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                          {isRu ? 'наружу ничего не отправлено' : 'nothing sent externally'}
                                        </span>
                                        <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                          {publishRehearsal.would_external_publish
                                            ? (isRu ? 'API готов к публикации' : 'API publish ready')
                                            : (isRu ? 'без API-публикации сейчас' : 'no API publish now')}
                                        </span>
                                        {publishRehearsal.would_create_supervised_task ? (
                                          <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                            {isRu ? 'создаст supervised task' : 'will create supervised task'}
                                          </span>
                                        ) : null}
                                        {publishRehearsal.browser_final_click_allowed === false ? (
                                          <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                            {isRu ? 'финальный клик запрещён' : 'final click forbidden'}
                                          </span>
                                        ) : null}
                                      </div>
                                      {rehearsalAction || rehearsalReason || rehearsalBlockers.length > 0 ? (
                                        <div className="mt-2 grid gap-1 rounded-lg bg-white/70 px-3 py-2 text-[11px]">
                                          {rehearsalAction ? (
                                            <div>
                                              <span className="font-semibold">{isRu ? 'Что будет: ' : 'Action: '}</span>
                                              {rehearsalAction}
                                            </div>
                                          ) : null}
                                          {rehearsalReason ? (
                                            <div>
                                              <span className="font-semibold">{isRu ? 'Причина: ' : 'Reason: '}</span>
                                              {rehearsalReason}
                                            </div>
                                          ) : null}
                                          {rehearsalBlockers.length > 0 ? (
                                            <div>
                                              <span className="font-semibold">{isRu ? 'Блокер: ' : 'Blocker: '}</span>
                                              {String(
                                                isRu
                                                  ? rehearsalBlockers[0]?.message_ru || rehearsalBlockers[0]?.code || ''
                                                  : rehearsalBlockers[0]?.message_en || rehearsalBlockers[0]?.code || ''
                                              )}
                                            </div>
                                          ) : null}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                  {!canRecordResult ? (
                                    <div
                                      data-testid="social-preview-before-approval"
                                      className="mt-3 rounded-xl border border-sky-100 bg-sky-50 px-3 py-3 text-xs leading-5 text-sky-900"
                                    >
                                      <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div className="font-semibold text-sky-950">
                                          {isRu ? 'Предпросмотр перед подтверждением' : 'Preview before approval'}
                                        </div>
                                        <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-sky-800">
                                          {_formatPlanItemDate(post.scheduled_for, isRu)}
                                        </span>
                                      </div>
                                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                                        <div>
                                          <div className="text-[11px] uppercase tracking-[0.12em] text-sky-700">
                                            {isRu ? 'Канал' : 'Channel'}
                                          </div>
                                          <div className="font-medium">
                                            {_socialPlatformLabel(post.platform, isRu)}
                                          </div>
                                        </div>
                                        <div>
                                          <div className="text-[11px] uppercase tracking-[0.12em] text-sky-700">
                                            {isRu ? 'Исполнение' : 'Execution'}
                                          </div>
                                          <div className="font-medium">
                                            {_socialPublishModeLabel(post.publish_mode, isRu)}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="mt-2 rounded-lg bg-white px-3 py-2 text-slate-700">
                                        {postTextValue.trim()
                                          ? postTextValue.trim()
                                          : (isRu ? 'Текст ещё пустой: перед подтверждением нужно сохранить текст.' : 'Copy is still empty: save copy before approval.')}
                                      </div>
                                      <div className="mt-2 text-[11px] text-sky-800">
                                        {isSupervisedPost
                                          ? (isRu
                                            ? 'После подтверждения LocalOS подготовит контролируемое или ручное размещение; финальная публикация остаётся за человеком.'
                                            : 'After approval, LocalOS prepares supervised or manual placement; final publishing stays human-controlled.')
                                          : (isRu
                                            ? 'После подтверждения можно поставить в расписание; API-публикация запустится только исполнителем и только по дате.'
                                            : 'After approval, you can queue it; API publishing starts only through the worker and only on schedule.')}
                                      </div>
                                    </div>
                                  ) : null}
                                  {canMarkPublished ? (
                                    <div className="mt-3 grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 md:grid-cols-2">
                                      <div className="md:col-span-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                                        {isRu ? 'Факт размещения' : 'Placement proof'}
                                      </div>
                                      <Input
                                        value={manualRefs.url}
                                        onChange={(event) => setManualPublishRefs((prev) => ({
                                          ...prev,
                                          [post.id]: {
                                            url: event.target.value,
                                            id: prev[post.id]?.id ?? String(post.provider_post_id || ''),
                                          },
                                        }))}
                                        placeholder={isRu ? 'Ссылка на пост, если есть' : 'Post URL, if available'}
                                        disabled={postBusy}
                                      />
                                      <Input
                                        value={manualRefs.id}
                                        onChange={(event) => setManualPublishRefs((prev) => ({
                                          ...prev,
                                          [post.id]: {
                                            url: prev[post.id]?.url ?? String(post.provider_post_url || ''),
                                            id: event.target.value,
                                          },
                                        }))}
                                        placeholder={isRu ? 'ID поста, если есть' : 'Post ID, if available'}
                                        disabled={postBusy}
                                      />
                                      <div className="md:col-span-2 text-xs leading-5 text-slate-500">
                                        {isRu
                                          ? 'Можно оставить пустым, но ссылка помогает потом связать реакции и заявки с конкретной публикацией.'
                                          : 'Optional, but a URL helps connect reactions and leads to the exact publication later.'}
                                      </div>
                                    </div>
                                  ) : null}
                                    {(post.provider_post_url || post.provider_post_id) && !publishEvidence ? (
                                      <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-800">
                                      {post.provider_post_url ? (
                                        <a
                                          href={post.provider_post_url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="font-medium underline underline-offset-2"
                                        >
                                          {isRu ? 'Открыть опубликованный пост' : 'Open published post'}
                                        </a>
                                      ) : null}
                                      {post.provider_post_id ? (
                                        <div className="font-mono text-[11px] text-emerald-900">
                                          id: {post.provider_post_id}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    {post.status !== 'published' ? (
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        onClick={() => { void rehearseSocialPostPublish(post); }}
                                        disabled={postBusy || postTextDirty}
                                      >
                                        {socialBusyAction === `rehearsal:${post.id}`
                                          ? (isRu ? 'Проверяем...' : 'Checking...')
                                          : (isRu ? 'Проверить запуск' : 'Check launch')}
                                      </Button>
                                    ) : null}
                                    {needsReview ? (
                                      <Button
                                        type="button"
                                        size="sm"
                                        onClick={() => { void approveSocialPostItem(post); }}
                                        disabled={postBusy || postTextDirty}
                                      >
                                        {isRu ? 'Подтвердить' : 'Approve'}
                                      </Button>
                                    ) : null}
                                    {canQueue ? (
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        onClick={() => { void queueSocialPostItem(post); }}
                                        disabled={postBusy || postTextDirty}
                                      >
                                        {isRu ? 'Поставить в расписание' : 'Queue on schedule'}
                                      </Button>
                                    ) : null}
                                    {post.status === 'queued' ? (
                                      <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-800">
                                        {isRu ? 'В расписании' : 'Scheduled'}
                                      </span>
                                    ) : null}
                                    {canCreateSupervisedTask ? (
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        onClick={() => { void createSupervisedPostTask(post); }}
                                        disabled={postBusy || postTextDirty}
                                      >
                                        {isRu ? 'Подготовить контролируемое размещение' : 'Prepare supervised placement'}
                                      </Button>
                                    ) : null}
                                    {canMarkPublished ? (
                                      <>
                                        {postTextValue.trim() ? (
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            onClick={() => { void copySocialPostText(post, postTextValue); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Скопировать текст' : 'Copy text'}
                                          </Button>
                                        ) : null}
                                        {supervisedTargetUrl ? (
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            onClick={() => window.open(supervisedTargetUrl, '_blank', 'noopener,noreferrer')}
                                          >
                                            {isRu ? 'Открыть площадку' : 'Open platform'}
                                          </Button>
                                        ) : null}
                                        {post.status === 'needs_supervised_publish' ? (
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            onClick={() => { void markSupervisedPostBlocked(post); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Нужен ручной режим' : 'Manual fallback needed'}
                                          </Button>
                                        ) : null}
                                        <Button
                                          type="button"
                                          size="sm"
                                          variant="outline"
                                          onClick={() => { void markSocialPostPublished(post); }}
                                          disabled={postBusy}
                                        >
                                          {isRu ? 'Отметить размещённым' : 'Mark published'}
                                        </Button>
                                      </>
                                    ) : null}
                                    {actionHint ? (
                                      <div
                                        className={[
                                          'w-full rounded-xl border px-3 py-2 text-xs leading-5',
                                          actionHint.tone === 'safe'
                                            ? 'border-sky-100 bg-sky-50 text-sky-800'
                                            : actionHint.tone === 'queue'
                                              ? 'border-blue-100 bg-blue-50 text-blue-800'
                                              : actionHint.tone === 'controlled'
                                                ? 'border-amber-100 bg-amber-50 text-amber-800'
                                                : 'border-slate-200 bg-slate-50 text-slate-700',
                                        ].join(' ')}
                                      >
                                        {isRu ? actionHint.textRu : actionHint.textEn}
                                      </div>
                                    ) : null}
                                    {canRecordResult ? (
                                      <div className="mt-1 flex w-full flex-col gap-2 rounded-xl border border-emerald-100 bg-emerald-50/60 px-3 py-2">
                                        {resultPacket ? (
                                          <div
                                            data-testid="social-result-collection-packet"
                                            className="rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-emerald-900"
                                          >
                                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                              <div>
                                                <div className="font-semibold text-emerald-950">
                                                  {isRu ? 'Результат публикации' : 'Post result'}
                                                </div>
                                                <div className="mt-1">
                                                  {isRu
                                                    ? String(resultPacket.owner_next_action_ru || 'Отметьте заявки, обращения или ранние сигналы.')
                                                    : String(resultPacket.owner_next_action_en || 'Record leads, inquiries, or early signals.')}
                                                </div>
                                              </div>
                                              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-800">
                                                {resultPacket.ready_for_recommendation
                                                  ? (isRu ? 'есть данные для плана' : 'plan data ready')
                                                  : (isRu ? 'нужен результат' : 'result needed')}
                                              </span>
                                            </div>
                                            <div className="mt-2 grid gap-2 sm:grid-cols-2">
                                              <div className="rounded-md bg-emerald-50 px-2 py-1.5">
                                                <div className="font-semibold">
                                                  {isRu ? 'Главная метрика' : 'Primary metric'}
                                                </div>
                                                <div className="mt-1 text-[11px] text-emerald-900">
                                                  {isRu
                                                    ? `заявки ${Number(resultPacket.leads || 0)} · обращения ${Number(resultPacket.inquiries || 0)}`
                                                    : `leads ${Number(resultPacket.leads || 0)} · inquiries ${Number(resultPacket.inquiries || 0)}`}
                                                </div>
                                              </div>
                                              <div className="rounded-md bg-emerald-50 px-2 py-1.5">
                                                <div className="font-semibold">
                                                  {isRu ? 'Ранние сигналы' : 'Early signals'}
                                                </div>
                                                <div className="mt-1 text-[11px] text-emerald-900">
                                                  {isRu
                                                    ? `комм. ${Number(resultPacket.comments || 0)} · репосты ${Number(resultPacket.shares || 0)} · клики ${Number(resultPacket.clicks || 0)} · лайки ${Number(resultPacket.likes || 0)} · просмотры ${Number(resultPacket.views || 0)}`
                                                    : `comments ${Number(resultPacket.comments || 0)} · shares ${Number(resultPacket.shares || 0)} · clicks ${Number(resultPacket.clicks || 0)} · likes ${Number(resultPacket.likes || 0)} · views ${Number(resultPacket.views || 0)}`}
                                                </div>
                                              </div>
                                            </div>
                                          </div>
                                        ) : null}
                                        <div className="text-xs leading-5 text-emerald-900">
                                          {isRu
                                            ? 'Отмечайте заявки и обращения в первую очередь: LocalOS считает их главным результатом и по ним предлагает изменения следующего плана. Лайки и просмотры - только ранний сигнал.'
                                            : 'Record leads and inquiries first: LocalOS treats them as the main result and uses them to suggest next-plan changes. Likes and views are only early signals.'}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                          <span className="text-xs font-semibold uppercase text-emerald-800">
                                            {isRu ? 'Главный результат' : 'Primary result'}
                                          </span>
                                          <Button
                                            type="button"
                                            size="sm"
                                            className="h-7 bg-emerald-700 px-2 text-xs text-white hover:bg-emerald-800"
                                            onClick={() => { void recordSocialPostAttribution(post, 'lead'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Была заявка' : 'Record lead'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            className="h-7 bg-emerald-700 px-2 text-xs text-white hover:bg-emerald-800"
                                            onClick={() => { void recordSocialPostAttribution(post, 'inquiry'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Было обращение' : 'Record inquiry'}
                                          </Button>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                          <span className="text-xs font-semibold uppercase text-slate-500">
                                            {isRu ? 'Ранние сигналы' : 'Early signals'}
                                          </span>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'comment'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Комментарий' : 'Comment'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'share'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Репост' : 'Share'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'click'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Клик' : 'Click'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'like'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Лайк' : 'Like'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'view'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Просмотр' : 'View'}
                                          </Button>
                                        </div>
                                      </div>
                                    ) : null}
                                  </div>
                                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                                    {Number(post.leads || 0) || Number(post.inquiries || 0) ? (
                                      <span className="font-medium text-emerald-700">
                                        {isRu ? `заявки/обращения: ${Number(post.leads || 0) + Number(post.inquiries || 0)}` : `leads/inquiries: ${Number(post.leads || 0) + Number(post.inquiries || 0)}`}
                                      </span>
                                    ) : null}
                                    {Number(post.comments || 0) || Number(post.shares || 0) || Number(post.clicks || 0) || Number(post.likes || 0) || Number(post.views || 0) || Number(post.reach || 0) ? (
                                      <span>
                                        {isRu
                                          ? `ранние сигналы: комментарии ${Number(post.comments || 0)}, репосты ${Number(post.shares || 0)}, клики ${Number(post.clicks || 0)}, лайки ${Number(post.likes || 0)}, просмотры ${Number(post.views || post.reach || 0)}`
                                          : `early signals: comments ${Number(post.comments || 0)}, shares ${Number(post.shares || 0)}, clicks ${Number(post.clicks || 0)}, likes ${Number(post.likes || 0)}, views ${Number(post.views || post.reach || 0)}`}
                                      </span>
                                    ) : null}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="mt-4 rounded-xl border border-dashed border-slate-200 bg-white px-3 py-3">
                            <div className="text-sm font-semibold text-slate-950">
                              {isRu ? 'Сначала подготовьте варианты по каналам' : 'First prepare channel variants'}
                            </div>
                            <div className="mt-1 text-sm leading-6 text-slate-600">
                              {isRu
                                ? 'LocalOS создаст отдельные черновики для карт и соцсетей. Это безопасный шаг: посты не подтверждаются, не ставятся в расписание и не публикуются.'
                                : 'LocalOS creates separate drafts for maps and social channels. This is a safe step: posts are not approved, queued, or published.'}
                            </div>
                            <div className="mt-3 grid gap-2 text-xs leading-5 text-slate-600 md:grid-cols-3">
                              <div className="rounded-lg bg-slate-50 px-3 py-2">
                                <div className="font-semibold text-slate-950">
                                  1. {isRu ? 'Подготовка' : 'Prepare'}
                                </div>
                                <div>
                                  {isRu
                                    ? 'Создаём тексты под Яндекс, 2ГИС, Google, Telegram, VK и Meta.'
                                    : 'Create copy for Yandex, 2GIS, Google, Telegram, VK, and Meta.'}
                                </div>
                              </div>
                              <div className="rounded-lg bg-slate-50 px-3 py-2">
                                <div className="font-semibold text-slate-950">
                                  2. {isRu ? 'Предпросмотр и подтверждение' : 'Preview and approval'}
                                </div>
                                <div>
                                  {isRu
                                    ? 'Вы проверяете каждый текст и отдельно нажимаете «Подтвердить».'
                                    : 'You review each copy and explicitly click “Approve”.'}
                                </div>
                              </div>
                              <div className="rounded-lg bg-slate-50 px-3 py-2">
                                <div className="font-semibold text-slate-950">
                                  3. {isRu ? 'Расписание' : 'Queue'}
                                </div>
                                <div>
                                  {isRu
                                    ? 'Только после подтверждения можно поставить API-каналы в расписание; карты останутся контролируемыми или ручными.'
                                    : 'Only after approval can API channels be queued; maps remain supervised/manual.'}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="sticky bottom-3 z-10 mt-5 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white/95 px-3 py-3 shadow-lg backdrop-blur">
                          <Button
                            onClick={() => createNews(item.id)}
                            disabled={busyItemId === item.id || !String(currentDraft || '').trim() || hasNews}
                          >
                            {hasNews
                              ? (isRu ? 'Публикация создана' : 'Publication created')
                              : (isRu ? 'Создать публикацию' : 'Create publication')}
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
                              <button
                                type="button"
                                onClick={() => { void deleteItem(item.id); }}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
                              >
                                {isRu ? 'Удалить из плана' : 'Delete from plan'}
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
                    </div>
                  );
                })() : null}
              </div>
            ) : null}
    </>
  );
};
