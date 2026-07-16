import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { _itemLocationLabel, _networkQualityReasonLabel, _networkRiskLabel, _sourceKindLabel, _inputDateValue, _formatPlanItemDate } from './helpers';

export const QueueSummary = ({ scope }) => {
  const {
    isRu, busyItemId, bulkBusyAction, actionSummary, selectedViewPreset, bulkTargetDate, setBulkTargetDate, bulkNewsReview,
    setBulkNewsReview, bulkActionReview, setBulkActionReview, socialSummary, socialPreparePreview, setSocialPreparePreview, socialApprovalPreview, setSocialApprovalPreview,
    socialQueuePreview, setSocialQueuePreview, socialBusyAction, queueSearch, setQueueSearch, readiness, isNetworkMode, visibleItems,
    itemLocationSummary, selectedSocialCanRecordResults, visibleSocialNeedsReview, visibleSocialCanQueue, visibleSocialNeedsSupervised, visibleSocialNeedsManual, visibleSocialPublishedPosts, visibleSocialPublishedWithoutPrimaryResult,
    socialPrimaryResultCount, socialEarlySignalCount, socialDispatchEnabled, socialDispatchBlockedWithoutScope, socialDispatchScopeMismatch, socialPlanNextStep, socialApprovalPreviewSummary, socialQueuePreviewSummary,
    planOperationalSummary, viewPresets, networkOperatingSlices, quickActions, executeSocialApprovalPreview, executeSocialQueuePreview, prepareSuggestedSocialPosts, executeSocialPreparePreview,
    selectPublishedSocialPostsForResult, executeBulkNewsReview, executeBulkActionReview, applyViewPreset, applyLocationWeekFocus, runLocationWeekFocusDrafts, runLocationWeekFocusNews, runLocationWeekSkip,
    runLocationWeekRescheduleToDate, runQuickAction, runSocialPlanNextStep
  } = scope;
  return (
    <>
            <div className="rounded-[28px] border border-slate-200 bg-slate-950 p-5 text-white shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    {isRu ? 'Что сделать дальше' : 'Next best action'}
                  </div>
                  <div className="mt-2 text-xl font-semibold">
                    {visibleSocialNeedsReview.length > 0
                      ? (isRu ? 'Проверьте готовые публикации' : 'Review prepared publications')
                      : visibleSocialCanQueue.length > 0
                        ? (isRu ? 'Поставьте утверждённые посты в расписание' : 'Queue approved posts on schedule')
                        : visibleSocialNeedsSupervised.length > 0
                          ? (isRu ? 'Откройте контролируемое размещение' : 'Open supervised placement')
                          : visibleSocialNeedsManual.length > 0
                            ? (isRu ? 'Закройте ручные публикации' : 'Finish manual publications')
                            : Number(socialSummary?.scheduled || 0) > 0
                              ? (isRu ? 'Расписание ждёт исполнения' : 'Schedule is waiting for execution')
                              : Number(socialSummary?.published || 0) > 0
                                ? (isRu ? 'Соберите результат и улучшите план' : 'Collect results and improve the plan')
                                : planOperationalSummary.needsDraft > 0
                                  ? (isRu ? 'В плане есть темы без текста' : 'Some plan topics need text')
                                  : planOperationalSummary.readyToPublish > 0
                                    ? (isRu ? 'Теперь можно создать публикации' : 'Now create publications')
                                    : (isRu ? 'План под контролем' : 'Plan is under control')}
                  </div>
                  <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                    {visibleSocialNeedsReview.length > 0
                      ? (isRu
                        ? 'Главный шаг сейчас — предпросмотр и подтверждение. Текст можно поправить, а наружу ничего не отправится до отдельной постановки в расписание.'
                        : 'The main step now is preview and approval. You can edit copy; nothing external is sent until a separate queue step.')
                      : visibleSocialCanQueue.length > 0
                        ? (isRu
                          ? 'Подтверждение уже есть. Следующий безопасный шаг — поставить посты в расписание, после чего исполнитель обработает их только по дате и готовности каналов.'
                          : 'Approval is done. The next safe step is queueing posts, then the worker processes them only by date and channel readiness.')
                        : visibleSocialNeedsSupervised.length > 0
                          ? (isRu
                            ? 'Яндекс/2ГИС ждут контролируемое размещение: LocalOS подготовит текст и задачу, финальный клик остаётся за человеком.'
                            : 'Yandex/2GIS await supervised placement: LocalOS prepares copy and a task, while the final click stays human-controlled.')
                          : visibleSocialNeedsManual.length > 0
                            ? (isRu
                              ? 'Есть каналы без API или browser-use. Скопируйте готовый текст, разместите вручную и отметьте результат в LocalOS.'
                              : 'Some channels have no API or browser-use. Copy the prepared text, publish manually, and mark the result in LocalOS.')
                            : Number(socialSummary?.published || 0) > 0
                              ? (isRu
                                ? 'Публикации уже вышли. Теперь отметьте заявки/обращения и пересчитайте рекомендации следующего плана.'
                                : 'Posts are already published. Record leads/inquiries and refresh next-plan recommendations.')
                              : (isRu
                                ? 'Это не создаёт новый план. Здесь вы работаете с уже выбранным планом: дописываете тексты, находите нужную тему и создаёте публикации.'
                                : 'This does not create a new plan. Here you work with the selected plan: fill text, find topics, and create publications.')}
                  </div>
                  {Number(socialSummary?.total || 0) > 0 ? (
                    <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
                      <Button
                        type="button"
                        size="sm"
                        onClick={runSocialPlanNextStep}
                        disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || Boolean(socialPlanNextStep.disabled)}
                        className="shrink-0 bg-white text-slate-950 hover:bg-slate-100"
                      >
                        {bulkBusyAction || socialBusyAction
                          ? (isRu ? 'Выполняем...' : 'Working...')
                          : `${isRu ? socialPlanNextStep.ctaRu : socialPlanNextStep.ctaEn} · ${socialPlanNextStep.count}`}
                      </Button>
                      <div className="text-xs leading-5 text-slate-300">
                        {isRu
                          ? 'Кнопка ведёт к безопасному шагу: предпросмотр, подтверждение, расписание, контролируемое размещение или сбор результата.'
                          : 'This button opens the safe next step: preview, approval, queueing, supervised placement, or result collection.'}
                      </div>
                    </div>
                  ) : null}
                  {Number(socialSummary?.total || 0) === 0 ? (
                    <div className="mt-4 rounded-2xl border border-white/10 bg-white/10 px-4 py-4">
                      <div className="text-sm font-semibold text-white">
                        {isRu ? 'Первый запуск publishing loop' : 'First publishing-loop launch'}
                      </div>
                      <div className="mt-2 grid gap-2 text-xs leading-5 text-slate-300 md:grid-cols-4">
                        <div className="rounded-xl bg-white/10 px-3 py-2">
                          <div className="font-semibold text-white">{isRu ? '1. Подготовить каналы' : '1. Prepare channels'}</div>
                          <div>{isRu ? 'Создать черновики для карт и соцсетей из тем плана.' : 'Create channel drafts from plan topics.'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2">
                          <div className="font-semibold text-white">{isRu ? '2. Проверить тексты' : '2. Review copy'}</div>
                          <div>{isRu ? 'Открыть предпросмотр, поправить общий текст и версии под каналы.' : 'Open preview and edit base plus platform-specific copy.'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2">
                          <div className="font-semibold text-white">{isRu ? '3. Утвердить и поставить' : '3. Approve and queue'}</div>
                          <div>{isRu ? 'Подтверждение и расписание идут отдельными безопасными шагами.' : 'Approval and scheduling stay separate safe steps.'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2">
                          <div className="font-semibold text-white">{isRu ? '4. Исполнить по режиму' : '4. Execute by mode'}</div>
                          <div>{isRu ? 'API-каналы пойдут через worker, Яндекс/2ГИС - через контролируемое размещение.' : 'API channels run via worker; Yandex/2GIS use supervised placement.'}</div>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-xs leading-5 text-slate-300">
                          {isRu
                            ? 'Наружу ничего не отправится на первом шаге. Яндекс/2ГИС не нажимают финальную кнопку без человека.'
                            : 'Nothing is sent externally on the first step. Yandex/2GIS never click the final publish button without a person.'}
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => { void prepareSuggestedSocialPosts(); }}
                          disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || visibleItems.length === 0}
                          className="shrink-0 bg-white text-slate-950 hover:bg-slate-100"
                        >
                          {bulkBusyAction === 'suggested-social-prepare'
                            ? (isRu ? 'Готовим...' : 'Preparing...')
                            : (isRu ? 'Подготовить первые публикации' : 'Prepare first posts')}
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs text-slate-300 sm:min-w-[320px]">
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.needsDraft}</div>
                    <div>{isRu ? 'без текста' : 'no draft'}</div>
                  </div>
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.readyToPublish}</div>
                    <div>{isRu ? 'текст готов' : 'draft ready'}</div>
                  </div>
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.published}</div>
                    <div>{isRu ? 'новости' : 'news'}</div>
                  </div>
                </div>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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
            {visibleSocialPublishedPosts.length > 0 ? (
              <div
                data-testid="social-result-collection-guide"
                className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm leading-6 text-emerald-900"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700">
                      {isRu ? 'Сбор результата' : 'Result collection'}
                    </div>
                    <div className="mt-1 text-base font-semibold text-emerald-950">
                      {socialPrimaryResultCount > 0
                        ? (isRu ? 'Есть заявки или обращения' : 'Leads or inquiries recorded')
                        : (isRu ? 'Отметьте заявки и обращения после публикаций' : 'Record leads and inquiries after publishing')}
                    </div>
                    <div className="mt-1 max-w-3xl text-sm leading-6 text-emerald-800">
                      {isRu
                        ? 'LocalOS корректирует следующий план по фактам: сначала заявки и обращения, затем комментарии, репосты, клики и охваты. Изменения плана не применяются без подтверждения.'
                        : 'LocalOS adjusts the next plan from facts: leads and inquiries first, then comments, shares, clicks, and reach. Plan changes are never applied without approval.'}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={selectPublishedSocialPostsForResult}
                    disabled={visibleSocialPublishedPosts.length === 0}
                    className="shrink-0 border-emerald-300 bg-white text-emerald-900 hover:bg-emerald-100"
                  >
                    {isRu ? 'Выбрать опубликованные' : 'Select published'}
                  </Button>
                </div>
                <div className="mt-3 grid gap-2 text-xs sm:grid-cols-4">
                  <div className="rounded-xl bg-white px-3 py-2">
                    <div className="text-base font-semibold text-emerald-950">{visibleSocialPublishedPosts.length}</div>
                    <div>{isRu ? 'опубликовано' : 'published'}</div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2">
                    <div className="text-base font-semibold text-emerald-950">{visibleSocialPublishedWithoutPrimaryResult.length}</div>
                    <div>{isRu ? 'без заявки/обращения' : 'without lead/inquiry'}</div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2">
                    <div className="text-base font-semibold text-emerald-950">{socialPrimaryResultCount}</div>
                    <div>{isRu ? 'заявки и обращения' : 'leads and inquiries'}</div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2">
                    <div className="text-base font-semibold text-emerald-950">{socialEarlySignalCount}</div>
                    <div>{isRu ? 'ранние сигналы' : 'early signals'}</div>
                  </div>
                </div>
                <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-emerald-800">
                  {selectedSocialCanRecordResults.length > 0
                    ? (isRu
                      ? `Выбрано опубликованных постов: ${selectedSocialCanRecordResults.length}. Ниже доступны кнопки “Была заявка” и “Было обращение”.`
                      : `Published posts selected: ${selectedSocialCanRecordResults.length}. The “Record lead” and “Record inquiry” buttons are available below.`)
                    : (isRu
                      ? 'Нажмите “Выбрать опубликованные”, затем отметьте результат по выбранным публикациям.'
                      : 'Click “Select published”, then record results for the selected publications.')}
                </div>
              </div>
            ) : null}
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
            {isNetworkMode && networkOperatingSlices.length > 0 ? (
              <details className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                <summary className="cursor-pointer list-none text-sm font-semibold text-slate-900">
                  {isRu ? 'Сетевые срезы по точкам' : 'Network slices by location'}
                </summary>
                <div className="mt-4">
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
                          <div className="text-slate-500">{isRu ? 'текст готов' : 'draft ready'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.published}</div>
                          <div className="text-slate-500">{isRu ? 'новости' : 'news'}</div>
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
                            : `${isRu ? 'Создать публикации' : 'Create publications'} · ${slice.focusWeekReadyToPublish}`}
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
              </details>
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
            {socialPreparePreview ? (
              <div
                data-testid="social-prepare-preview-panel"
                className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-4 text-sm text-blue-950"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
                      {isRu ? 'Предпросмотр подготовки каналов' : 'Channel preparation preview'}
                    </div>
                    <div className="mt-1 text-base font-semibold text-blue-950">
                      {socialPreparePreview.previewItemTitle}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-blue-800">
                      {isRu
                        ? 'Это отдельный безопасный шаг: LocalOS показал, что будет создано, но черновики ещё не записаны и наружу ничего не опубликовано.'
                        : 'This is a separate safe step: LocalOS shows what will be created, but drafts are not written yet and nothing is published externally.'}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-4">
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-blue-100">
                      <div className="text-lg font-semibold text-blue-950">{Number(socialPreparePreview.preview.summary?.total || 0)}</div>
                      <div>{isRu ? 'каналов' : 'channels'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-blue-100">
                      <div className="text-lg font-semibold text-blue-950">{Number(socialPreparePreview.preview.summary?.would_create || 0)}</div>
                      <div>{isRu ? 'создать' : 'create'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-blue-100">
                      <div className="text-lg font-semibold text-blue-950">{Number(socialPreparePreview.preview.summary?.would_update || 0)}</div>
                      <div>{isRu ? 'обновить' : 'update'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-blue-100">
                      <div className="text-lg font-semibold text-blue-950">{Number(socialPreparePreview.preview.summary?.would_preserve || 0)}</div>
                      <div>{isRu ? 'сохранить' : 'preserve'}</div>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {(socialPreparePreview.preview.posts || []).slice(0, 8).map((post) => (
                    <span
                      key={`${String(post.platform || '')}:${String(post.prepare_action || '')}`}
                      className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-blue-800 ring-1 ring-blue-100"
                    >
                      {String(post.platform_label || post.platform || '')}
                      {' · '}
                      {String(post.prepare_action || 'preview')}
                    </span>
                  ))}
                </div>
                <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-blue-800 ring-1 ring-blue-100">
                  {isRu
                    ? `Выбрано тем: ${socialPreparePreview.itemIds.length}. Подробный предпросмотр показан по первой теме; при продолжении черновики будут созданы для всех выбранных тем.`
                    : `Selected items: ${socialPreparePreview.itemIds.length}. The detailed preview is shown for the first item; continuing creates drafts for all selected items.`}
                </div>
                <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    className="bg-white"
                    onClick={() => setSocialPreparePreview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => { void executeSocialPreparePreview(); }}
                    disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction)}
                  >
                    {bulkBusyAction === socialPreparePreview.busyAction
                      ? (isRu ? 'Создаём черновики...' : 'Creating drafts...')
                      : (isRu ? 'Создать черновики для проверки' : 'Create drafts for review')}
                  </Button>
                </div>
              </div>
            ) : null}
            {socialApprovalPreview && socialApprovalPreviewSummary ? (
              <div
                data-testid="social-approval-preview-panel"
                className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm text-sky-950"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-600">
                      {isRu ? 'Предпросмотр перед подтверждением' : 'Preview before approval'}
                    </div>
                    <div className="mt-1 text-base font-semibold text-sky-950">
                      {isRu
                        ? `Подтвердить тексты: ${socialApprovalPreviewSummary.total}`
                        : `Approve copy: ${socialApprovalPreviewSummary.total}`}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-sky-800">
                      {isRu
                        ? 'Подтверждение только фиксирует проверку текста. Наружу ничего не публикуется: после этого отдельный шаг - “Поставить в расписание”.'
                        : 'Approval only records copy review. Nothing is published externally: the separate next step is “Queue on schedule”.'}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-4">
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-sky-100">
                      <div className="text-lg font-semibold text-sky-950">{socialApprovalPreviewSummary.total}</div>
                      <div>{isRu ? 'всего' : 'total'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-sky-100">
                      <div className="text-lg font-semibold text-sky-950">{socialApprovalPreviewSummary.api}</div>
                      <div>{isRu ? 'API' : 'API'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-sky-100">
                      <div className="text-lg font-semibold text-sky-950">{socialApprovalPreviewSummary.supervised}</div>
                      <div>{isRu ? 'карты' : 'maps'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-sky-100">
                      <div className="text-lg font-semibold text-sky-950">{socialApprovalPreviewSummary.emptyText}</div>
                      <div>{isRu ? 'без текста' : 'empty'}</div>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {socialApprovalPreviewSummary.platformLabels.slice(0, 10).map((label) => (
                    <span
                      key={`approval-preview-platform:${label}`}
                      className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-100"
                    >
                      {label}
                    </span>
                  ))}
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
                    <div className="font-semibold text-sky-950">
                      {isRu ? 'Что произойдёт сейчас' : 'What happens now'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'LocalOS сохранит подтверждение человека. API-публикация не начнётся, пока вы отдельно не поставите посты в расписание.'
                        : 'LocalOS will save human approval. API publishing will not start until you separately queue posts on schedule.'}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
                    <div className="font-semibold text-sky-950">
                      {isRu ? 'Яндекс/2ГИС' : 'Yandex/2GIS'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'Для карт подтверждение не означает автопубликацию: после постановки в расписание LocalOS создаст контролируемую или ручную задачу, финальный клик остаётся за человеком.'
                        : 'For map platforms, approval does not mean autopublish: after queueing, LocalOS creates a supervised or manual task, and the final click stays human-controlled.'}
                    </div>
                  </div>
                </div>
                {socialApprovalPreviewSummary.blockedApiWarnings.length > 0 ? (
                  <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                    <div className="font-semibold text-amber-950">
                      {isRu ? 'API-каналы можно подтвердить, но они ещё не готовы к публикации' : 'API channels can be approved, but are not ready to publish yet'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'Подтверждение текста разрешено, но исполнитель не опубликует эти каналы без ключей, прав или привязки аккаунта.'
                        : 'Copy approval is allowed, but the worker will not publish these channels without keys, permissions, or account binding.'}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {socialApprovalPreviewSummary.blockedApiWarnings.slice(0, 6).map((warning) => (
                        <span
                          key={`approval-api-warning:${warning.postId}:${warning.platform}`}
                          className="rounded-full bg-white px-2.5 py-1 font-medium text-amber-800"
                        >
                          {warning.label} · {warning.status}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                {socialApprovalPreviewSummary.emptyText > 0 ? (
                  <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-800">
                    {isRu
                      ? `Перед подтверждением заполните и сохраните текст: ${socialApprovalPreviewSummary.emptyText}.`
                      : `Add and save copy before approval: ${socialApprovalPreviewSummary.emptyText}.`}
                  </div>
                ) : null}
                <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    className="bg-white"
                    onClick={() => setSocialApprovalPreview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => { void executeSocialApprovalPreview(); }}
                    disabled={Boolean(bulkBusyAction) || socialApprovalPreviewSummary.emptyText > 0}
                  >
                    {bulkBusyAction === socialApprovalPreview.busyAction
                      ? (isRu ? 'Подтверждаем тексты...' : 'Approving copy...')
                      : (isRu ? 'Подтвердить тексты' : 'Approve copy')}
                  </Button>
                </div>
              </div>
            ) : null}
            {socialQueuePreview && socialQueuePreviewSummary ? (
              <div
                data-testid="social-queue-preview-panel"
                className="rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-4 text-sm text-indigo-950"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">
                      {isRu ? 'Предпросмотр постановки в расписание' : 'Queue preview'}
                    </div>
                    <div className="mt-1 text-base font-semibold text-indigo-950">
                      {isRu
                        ? `Разрешить исполнение по дате: ${socialQueuePreviewSummary.total}`
                        : `Allow scheduled execution: ${socialQueuePreviewSummary.total}`}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-indigo-800">
                      {isRu
                        ? 'Этот шаг переводит утверждённые посты в расписание. После второго клика исполнитель сможет обработать API-каналы по дате; это уже шаг исполнения, но не мгновенная публикация всех каналов.'
                        : 'Queue moves approved posts onto the schedule. After the second click, the worker can process due API channels by date; this is an execution step, but not instant publishing for every channel.'}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-4">
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-indigo-100">
                      <div className="text-lg font-semibold text-indigo-950">{socialQueuePreviewSummary.total}</div>
                      <div>{isRu ? 'в расписание' : 'to queue'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-indigo-100">
                      <div className="text-lg font-semibold text-indigo-950">{socialQueuePreviewSummary.api}</div>
                      <div>{isRu ? 'API' : 'API'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-indigo-100">
                      <div className="text-lg font-semibold text-indigo-950">{socialQueuePreviewSummary.supervised}</div>
                      <div>{isRu ? 'карты' : 'maps'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-indigo-100">
                      <div className="text-lg font-semibold text-indigo-950">{socialQueuePreviewSummary.dueNow}</div>
                      <div>{isRu ? 'уже due' : 'due now'}</div>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {socialQueuePreviewSummary.platformLabels.slice(0, 10).map((label) => (
                    <span
                      key={`queue-preview-platform:${label}`}
                      className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-indigo-800 ring-1 ring-indigo-100"
                    >
                      {label}
                    </span>
                  ))}
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-3">
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-indigo-800 ring-1 ring-indigo-100">
                    <div className="font-semibold text-indigo-950">
                      {isRu ? 'Когда' : 'When'}
                    </div>
                    <div className="mt-1">
                      {socialQueuePreviewSummary.firstScheduledFor
                        ? _formatPlanItemDate(socialQueuePreviewSummary.firstScheduledFor, isRu)
                        : (isRu ? 'Дата не указана' : 'No date set')}
                    </div>
                    <div className="mt-1 text-indigo-700">
                      {socialQueuePreviewSummary.dueNow > 0
                        ? (isRu
                          ? 'Часть постов уже пора публиковать: исполнитель сможет взять их в ближайший цикл.'
                          : 'Some posts are already due: the worker can pick them up in the next cycle.')
                        : (isRu
                          ? 'Исполнитель будет ждать дату публикации.'
                          : 'The worker will wait for the scheduled date.')}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-indigo-800 ring-1 ring-indigo-100">
                    <div className="font-semibold text-indigo-950">
                      {isRu ? 'API-каналы' : 'API channels'}
                    </div>
                    <div className="mt-1">
                      {socialDispatchEnabled && !socialDispatchBlockedWithoutScope && !socialDispatchScopeMismatch
                        ? (isRu
                          ? 'Фоновый запуск включён для этого бизнеса и обработает готовые API-каналы.'
                          : 'The worker is enabled for this business and will process ready API channels.')
                        : (isRu
                          ? 'Расписание сохранится, но фоновый запуск сейчас не отправит эти API-посты.'
                          : 'Queue will be saved, but the external worker will not run these API posts right now.')}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-indigo-800 ring-1 ring-indigo-100">
                    <div className="font-semibold text-indigo-950">
                      {isRu ? 'Яндекс/2ГИС' : 'Yandex/2GIS'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'Карты после постановки в расписание не публикуются тихо: LocalOS создаст контролируемую или ручную задачу, финальный клик остаётся за человеком.'
                        : 'Maps do not publish silently after queueing: LocalOS creates a supervised or manual task, and the final click stays human-controlled.'}
                    </div>
                  </div>
                </div>
                {socialQueuePreviewSummary.blockedApiWarnings.length > 0 ? (
                  <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                    <div className="font-semibold text-amber-950">
                      {isRu ? 'Эти API-каналы попадут в расписание, но пока не готовы к публикации' : 'These API channels will be queued, but are not ready to publish yet'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'Исполнитель пропустит их или переведёт в понятный статус, пока не появятся ключи, права или привязка аккаунта.'
                        : 'The worker will skip them or move them into a clear status until keys, permissions, or account binding are present.'}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {socialQueuePreviewSummary.blockedApiWarnings.slice(0, 6).map((warning) => (
                        <span
                          key={`queue-api-warning:${warning.postId}:${warning.platform}`}
                          className="rounded-full bg-white px-2.5 py-1 font-medium text-amber-800"
                        >
                          {warning.label} · {warning.status}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    className="bg-white"
                    onClick={() => setSocialQueuePreview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => { void executeSocialQueuePreview(); }}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {bulkBusyAction === socialQueuePreview.busyAction
                      ? (isRu ? 'Ставим в расписание...' : 'Queueing...')
                      : (isRu ? 'Поставить в расписание после проверки' : 'Queue after review')}
                  </Button>
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
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-950">
                    {isRu ? 'Найти тему в очереди' : 'Find a topic in the queue'}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-slate-500">
                    {isRu
                      ? 'Поиск ищет по теме, тексту черновика, ключу и точке. Например: отпуск, ХИТ, стрижка.'
                      : 'Search by topic, draft text, keyword, and location. For example: vacation, haircut, promo.'}
                  </div>
                </div>
                <div className="flex w-full gap-2 lg:w-[420px]">
                  <Input
                    value={queueSearch}
                    onChange={(event) => setQueueSearch(event.target.value)}
                    placeholder={isRu ? 'Поиск: отпуск, ХИТ, стрижка...' : 'Search: vacation, haircut...'}
                    className="bg-white"
                  />
                  {queueSearch.trim() ? (
                    <Button type="button" variant="outline" onClick={() => setQueueSearch('')}>
                      {isRu ? 'Сбросить' : 'Clear'}
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
    </>
  );
};
