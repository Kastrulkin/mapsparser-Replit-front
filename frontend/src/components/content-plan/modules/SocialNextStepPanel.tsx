import React from 'react';
import { Button } from '@/components/ui/button';
import { CalendarDays, CheckSquare, Globe } from 'lucide-react';
import { SocialLaunchChecklist, SocialOwnerLaunchPath, _socialPlatformLabel, _socialSettingsPathForPlatform, _socialWorkerEnvLines, _socialLaunchRunbookBlock, _socialFirstCycleVerificationBlock, _socialLearningChecklistStatusLabel, _socialDispatchActionLabel, _socialDispatchReasonLabel } from './helpers';

export const SocialNextStepPanel = ({ scope }) => {
  const {
    businessId, navigate, isRu, bulkBusyAction, socialSummary, socialDispatchPreview, socialDispatchExecutionReport, socialLaunchPreflight,
    socialTelegramPublishTargetProbe, socialRuntimeStatus, socialBusyAction, readiness, visibleSocialCanQueue, visibleSocialPublishedPosts, socialQueueExecutionNotice, socialPlanNextStep,
    socialReadinessSummary, socialLaunchStages, socialLaunchChecklistSummary, checkTelegramPublishTargetProbe, copySocialWorkerEnv, selectPublishedSocialPostsForResult, collectSocialPostMetricsForBusiness, previewSocialDispatch,
    checkSocialLaunchPreflight, runSocialDispatchOnce, recommendNextSocialPlan, runSocialPlanNextStep, openSocialPostsWaitingForReview, openSocialPostsWaitingForQueue
  } = scope;
  return (
    <>
                <div
                  data-testid="social-publishing-next-step"
                  className="rounded-2xl border border-slate-200 bg-slate-950 px-4 py-4 text-white"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                        {isRu ? 'Следующий шаг публикаций' : 'Publishing next step'}
                      </div>
                      <div className="mt-2 text-lg font-semibold">
                        {isRu ? socialPlanNextStep.titleRu : socialPlanNextStep.titleEn}
                      </div>
                      <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                        {isRu ? socialPlanNextStep.descriptionRu : socialPlanNextStep.descriptionEn}
                      </div>
                      <div
                        data-testid="social-owner-simple-goal"
                        className="mt-3 grid gap-2 text-xs leading-5 md:grid-cols-3"
                      >
                        <div className="rounded-xl bg-white/10 px-3 py-2 text-slate-100">
                          <div className="font-semibold text-white">
                            {isRu ? '1. Что делать первым' : '1. First action'}
                          </div>
                          <div className="mt-1">
                            {isRu ? socialPlanNextStep.descriptionRu : socialPlanNextStep.descriptionEn}
                          </div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2 text-slate-100">
                          <div className="font-semibold text-white">
                            {isRu ? '2. Что не произойдёт само' : '2. What will not happen silently'}
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? 'Наружу ничего не уйдёт без предпросмотра, подтверждения и расписания. Финальный клик в Яндекс/2ГИС остаётся за человеком.'
                              : 'Nothing goes external without preview, approval, and queueing. The final Yandex/2GIS click stays human-controlled.'}
                          </div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2 text-slate-100">
                          <div className="font-semibold text-white">
                            {isRu ? '3. Как понять успех' : '3. Success signal'}
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? 'Посты опубликованы, ручные задачи закрыты, заявки/обращения отмечены. После этого LocalOS предлагает изменения следующего плана.'
                              : 'Posts are published, manual tasks are closed, and leads/inquiries are recorded. Then LocalOS suggests next-plan changes.'}
                          </div>
                        </div>
                      </div>
                      <SocialOwnerLaunchPath
                        isRu={isRu}
                        currentAction={socialPlanNextStep.action}
                      />
                    </div>
                    <div className="flex flex-col gap-2 sm:min-w-[260px]">
                      <Button
                        type="button"
                        onClick={runSocialPlanNextStep}
                        disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || Boolean(socialPlanNextStep.disabled)}
                        className="bg-white text-slate-950 hover:bg-slate-100"
                      >
                        {Boolean(bulkBusyAction) || Boolean(socialBusyAction)
                          ? (isRu ? 'Выполняем...' : 'Working...')
                          : `${isRu ? socialPlanNextStep.ctaRu : socialPlanNextStep.ctaEn} · ${socialPlanNextStep.count}`}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => document.getElementById('content-plan-topic-queue')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                        className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                      >
                        {isRu ? 'К списку тем' : 'Go to topic list'}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => { void previewSocialDispatch(); }}
                        disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction)}
                        className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                      >
                        {socialBusyAction === 'dispatch-preview'
                          ? (isRu ? 'Проверяем...' : 'Checking...')
                          : (isRu ? 'Проверить расписание' : 'Preview schedule')}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        data-testid="social-check-worker-launch"
                        onClick={() => { void checkSocialLaunchPreflight(); }}
                        disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || !businessId}
                        className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                      >
                        {socialBusyAction === 'launch-preflight'
                          ? (isRu ? 'Проверяем запуск...' : 'Checking launch...')
                          : (isRu ? 'Проверить запуск по расписанию' : 'Check worker launch')}
                      </Button>
                      <div className="text-[11px] leading-4 text-slate-400">
                        {isRu
                          ? 'Безопасная проверка: ничего не публикует, только показывает первый цикл и блокеры.'
                          : 'Safe check: publishes nothing, only shows the first cycle and blockers.'}
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center text-[11px] text-slate-300">
                        <div className="rounded-xl bg-white/10 px-2 py-2">
                          <div className="text-sm font-semibold text-white">{socialReadinessSummary.apiReady}</div>
                          <div>{isRu ? 'API готово' : 'API ready'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-2 py-2">
                          <div className="text-sm font-semibold text-white">{socialReadinessSummary.supervisedOrManual}</div>
                          <div>{isRu ? 'контроль' : 'supervised'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-2 py-2">
                          <div className="text-sm font-semibold text-white">{socialReadinessSummary.needsAttention}</div>
                          <div>{isRu ? 'ключи/права' : 'keys/rights'}</div>
                        </div>
                      </div>
                      <SocialLaunchChecklist
                        isRu={isRu}
                        stages={socialLaunchStages}
                        summary={socialLaunchChecklistSummary}
                        compact
                      />
                      {socialRuntimeStatus ? (
                        <div
                          className="rounded-xl bg-white/10 px-3 py-2 text-xs leading-5 text-slate-200"
                          data-testid="social-runtime-owner-status"
                          data-schema="localos_social_runtime_owner_status_v1"
                        >
                            <div className="font-semibold text-white">
                              {isRu ? 'Runtime расписания' : 'Schedule runtime'}
                          </div>
                          {socialRuntimeStatus.owner_status ? (
                            <div className="mt-2 rounded-lg border border-white/10 bg-white/10 px-2 py-2">
                              <div className="font-semibold text-white">
                                {isRu
                                  ? String(socialRuntimeStatus.owner_status.title_ru || '')
                                  : String(socialRuntimeStatus.owner_status.title_en || '')}
                              </div>
                              <div className="mt-1 text-slate-200">
                                {isRu
                                  ? String(socialRuntimeStatus.owner_status.summary_ru || '')
                                  : String(socialRuntimeStatus.owner_status.summary_en || '')}
                              </div>
                              <div className="mt-1 font-medium text-slate-100">
                                {isRu
                                  ? String(socialRuntimeStatus.owner_status.next_action_ru || '')
                                  : String(socialRuntimeStatus.owner_status.next_action_en || '')}
                              </div>
                              <div className="mt-1 text-[11px] text-slate-300">
                                {isRu
                                  ? String(socialRuntimeStatus.owner_status.metrics_summary_ru || '')
                                  : String(socialRuntimeStatus.owner_status.metrics_summary_en || '')}
                              </div>
                            </div>
                          ) : null}
                          <div className="mt-1 grid gap-1">
                            <div className="flex items-center justify-between gap-3">
                              <span>{isRu ? 'Публикация по расписанию' : 'Scheduled dispatch'}</span>
                              <span className={socialRuntimeStatus.dispatch?.enabled ? 'font-semibold text-emerald-200' : 'font-semibold text-amber-200'}>
                                {socialRuntimeStatus.dispatch?.enabled ? (isRu ? 'включена' : 'enabled') : (isRu ? 'выключена' : 'disabled')}
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-300">
                              {isRu
                                ? `интервал ${Number(socialRuntimeStatus.dispatch?.interval_sec || 0)}с · batch ${Number(socialRuntimeStatus.dispatch?.batch_size || 0)}`
                                : `interval ${Number(socialRuntimeStatus.dispatch?.interval_sec || 0)}s · batch ${Number(socialRuntimeStatus.dispatch?.batch_size || 0)}`}
                            </div>
                            <div className="text-[11px] text-slate-300">
                              {socialRuntimeStatus.dispatch?.blocked_without_scope
                                ? (isRu
                                  ? 'область: заблокировано без выбранного бизнеса'
                                  : 'scope: blocked until a business scope is set')
                                : socialRuntimeStatus.dispatch?.scoped
                                ? (isRu
                                  ? `область: только бизнес ${String(socialRuntimeStatus.dispatch?.business_scope || '')}`
                                  : `scope: business ${String(socialRuntimeStatus.dispatch?.business_scope || '')}`)
                                : socialRuntimeStatus.dispatch?.allow_unscoped
                                  ? (isRu ? 'область: все due-посты явно разрешены' : 'scope: all due posts explicitly allowed')
                                  : (isRu ? 'область: нужен business scope перед запуском' : 'scope: business scope required before dispatch')}
                            </div>
                            {socialRuntimeStatus.dispatch?.blocked_without_scope ? (
                              <div className="rounded-lg border border-amber-300/30 bg-amber-400/10 px-2 py-1 text-[11px] font-medium text-amber-100">
                                {isRu
                                  ? 'Dispatch включён, но LocalOS не запустит публикации без SOCIAL_POST_DISPATCH_BUSINESS_ID или явного allow-all.'
                                  : 'Dispatch is enabled, but LocalOS will not publish without SOCIAL_POST_DISPATCH_BUSINESS_ID or explicit allow-all.'}
                              </div>
                            ) : null}
                            <div className="flex items-center justify-between gap-3">
                              <span>{isRu ? 'Сбор реакций' : 'Metrics collection'}</span>
                              <span className={socialRuntimeStatus.metrics?.enabled ? 'font-semibold text-emerald-200' : 'font-semibold text-amber-200'}>
                                {socialRuntimeStatus.metrics?.enabled ? (isRu ? 'включён' : 'enabled') : (isRu ? 'выключен' : 'disabled')}
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-300">
                              {socialRuntimeStatus.metrics?.blocked_without_scope
                                ? (isRu
                                  ? 'реакции: заблокировано без выбранного бизнеса'
                                  : 'metrics: blocked until a business scope is set')
                                : socialRuntimeStatus.metrics?.scoped
                                ? (isRu
                                  ? `реакции: только бизнес ${String(socialRuntimeStatus.metrics?.business_scope || '')}`
                                  : `metrics: business ${String(socialRuntimeStatus.metrics?.business_scope || '')}`)
                                : socialRuntimeStatus.metrics?.allow_unscoped
                                  ? (isRu ? 'реакции: все опубликованные посты явно разрешены' : 'metrics: all published posts explicitly allowed')
                                  : (isRu ? 'реакции: нужен business scope перед сбором' : 'metrics: business scope required before collection')}
                            </div>
                            {socialRuntimeStatus.metrics?.blocked_without_scope ? (
                              <div className="rounded-lg border border-amber-300/30 bg-amber-400/10 px-2 py-1 text-[11px] font-medium text-amber-100">
                                {isRu
                                  ? 'Сбор реакций включён, но LocalOS не будет вызывать внешние API без SOCIAL_POST_METRICS_BUSINESS_ID или явного allow-all.'
                                  : 'Metrics collection is enabled, but LocalOS will not call external APIs without SOCIAL_POST_METRICS_BUSINESS_ID or explicit allow-all.'}
                              </div>
                            ) : null}
                            {socialRuntimeStatus.telegram_transport ? (
                              <div
                                data-testid="social-runtime-telegram-transport"
                                data-schema={String(socialRuntimeStatus.telegram_transport.schema || 'localos_telegram_transport_status_v1')}
                                className={[
                                  'rounded-lg border px-2 py-1.5 text-[11px] leading-4',
                                  socialRuntimeStatus.telegram_transport.ready
                                    ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-50'
                                    : 'border-amber-300/30 bg-amber-400/10 text-amber-50',
                                ].join(' ')}
                              >
                                <div className="flex items-center justify-between gap-3 font-semibold">
                                  <span>{isRu ? 'Telegram transport' : 'Telegram transport'}</span>
                                  <span>
                                    {socialRuntimeStatus.telegram_transport.ready
                                      ? (isRu ? 'готов' : 'ready')
                                      : (isRu ? 'требует проверки' : 'needs check')}
                                  </span>
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? String(socialRuntimeStatus.telegram_transport.summary_ru || '')
                                    : String(socialRuntimeStatus.telegram_transport.summary_en || '')}
                                </div>
                                <div className="mt-1 font-medium">
                                  {isRu
                                    ? String(socialRuntimeStatus.telegram_transport.next_action_ru || '')
                                    : String(socialRuntimeStatus.telegram_transport.next_action_en || '')}
                                </div>
                              </div>
                            ) : null}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-300">
                              {isRu
                                ? 'Внешние публикации всё равно требуют подтверждения; Яндекс/2ГИС не нажимают финальную кнопку без человека.'
                                : 'External posts still require approval; Yandex/2GIS do not click final publish without a human.'}
                          </div>
                        </div>
                      ) : null}
                      {socialRuntimeStatus && (visibleSocialCanQueue.length > 0 || Number(socialSummary?.scheduled || 0) > 0) ? (
                        <div
                          className={[
                            'rounded-xl border px-3 py-2 text-xs leading-5',
                            socialQueueExecutionNotice.tone === 'ok'
                              ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100'
                              : 'border-amber-300/30 bg-amber-400/10 text-amber-100',
                          ].join(' ')}
                        >
                          <div className="font-semibold">
                            {isRu ? socialQueueExecutionNotice.titleRu : socialQueueExecutionNotice.titleEn}
                          </div>
                          <div className="mt-1">
                            {isRu ? socialQueueExecutionNotice.textRu : socialQueueExecutionNotice.textEn}
                          </div>
                        </div>
                      ) : null}
                      {socialLaunchPreflight ? (
                        <div
                          className={[
                            'rounded-xl border px-3 py-2 text-xs leading-5',
                            socialLaunchPreflight.safe_to_enable_scoped_dispatch
                              ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100'
                              : 'border-amber-300/30 bg-amber-400/10 text-amber-100',
                          ].join(' ')}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold">
                              {isRu ? 'Проверка запуска по расписанию' : 'Worker launch preflight'}
                            </span>
                            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-white">
                              {socialLaunchPreflight.safe_to_enable_scoped_dispatch
                                ? (isRu ? 'можно scoped' : 'scoped ready')
                                : (isRu ? 'сначала подготовить' : 'prepare first')}
                            </span>
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? String(socialLaunchPreflight.message_ru || '')
                              : String(socialLaunchPreflight.message_en || '')}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-200">
                            {isRu
                              ? `Due ${Number(socialLaunchPreflight.summary?.due_posts || 0)} · API ${Number(socialLaunchPreflight.summary?.api_due_posts || 0)} · контролируемо ${Number(socialLaunchPreflight.summary?.controlled_due_posts || 0)} · вручную ${Number(socialLaunchPreflight.summary?.manual_due_posts || 0)}`
                              : `Due ${Number(socialLaunchPreflight.summary?.due_posts || 0)} · API ${Number(socialLaunchPreflight.summary?.api_due_posts || 0)} · supervised ${Number(socialLaunchPreflight.summary?.controlled_due_posts || 0)} · manual ${Number(socialLaunchPreflight.summary?.manual_due_posts || 0)}`}
                          </div>
                          {socialLaunchPreflight.worker_idle_reason ? (
                            <div
                              data-testid="social-worker-idle-reason"
                              className="mt-2 rounded-lg border border-amber-200/30 bg-amber-400/10 px-2 py-2 text-[11px] leading-5 text-amber-50"
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Почему worker ждёт' : 'Why the worker is waiting'}
                                    {' · '}
                                    {isRu
                                      ? String(socialLaunchPreflight.worker_idle_reason.title_ru || '')
                                      : String(socialLaunchPreflight.worker_idle_reason.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.worker_idle_reason.next_action_ru || '')
                                      : String(socialLaunchPreflight.worker_idle_reason.next_action_en || '')}
                                  </div>
                                  {String(socialLaunchPreflight.worker_idle_reason.status || '') === 'waiting_for_review' ? (
                                    <div className="mt-2">
                                      <Button
                                        size="sm"
                                        variant="secondary"
                                        onClick={openSocialPostsWaitingForReview}
                                        data-testid="social-open-waiting-review"
                                      >
                                        <CheckSquare className="mr-2 h-4 w-4" />
                                        {isRu ? 'Открыть посты на проверку' : 'Open posts for review'}
                                      </Button>
                                    </div>
                                  ) : null}
                                  {String(socialLaunchPreflight.worker_idle_reason.status || '') === 'waiting_for_queue' ? (
                                    <div className="mt-2">
                                      <Button
                                        size="sm"
                                        variant="secondary"
                                        onClick={openSocialPostsWaitingForQueue}
                                        data-testid="social-open-waiting-queue"
                                      >
                                        <CalendarDays className="mr-2 h-4 w-4" />
                                        {isRu ? 'Поставить утверждённые в расписание' : 'Queue approved posts'}
                                      </Button>
                                    </div>
                                  ) : null}
                                  {String(socialLaunchPreflight.worker_idle_reason.status || '') === 'has_due_queued_posts' ? (
                                    <div className="mt-2">
                                      <Button
                                        size="sm"
                                        variant="secondary"
                                        onClick={() => { void previewSocialDispatch(true); }}
                                        disabled={socialBusyAction === 'dispatch-preview'}
                                        data-testid="social-open-due-dispatch-preview"
                                      >
                                        <Globe className="mr-2 h-4 w-4" />
                                        {socialBusyAction === 'dispatch-preview'
                                          ? (isRu ? 'Проверяем due...' : 'Checking due...')
                                          : (isRu ? 'Проверить due-публикации' : 'Preview due dispatch')}
                                      </Button>
                                    </div>
                                  ) : null}
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {isRu
                                    ? `постов: ${Number(socialLaunchPreflight.worker_idle_reason.count || 0)}`
                                    : `posts: ${Number(socialLaunchPreflight.worker_idle_reason.count || 0)}`}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-4">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.workflow_stage_counts?.needs_review || socialLaunchPreflight.summary?.workflow_needs_review || 0)}</span>
                                  {' '}
                                  {isRu ? 'проверить' : 'review'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.workflow_stage_counts?.approved_not_queued || socialLaunchPreflight.summary?.workflow_approved_not_queued || 0)}</span>
                                  {' '}
                                  {isRu ? 'утверждено' : 'approved'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.workflow_stage_counts?.queued_future || socialLaunchPreflight.summary?.workflow_queued_future || 0)}</span>
                                  {' '}
                                  {isRu ? 'будущие' : 'future'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.workflow_stage_counts?.queued_due || socialLaunchPreflight.summary?.due_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'готовы сейчас' : 'due now'}
                                </div>
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.production_readiness ? (
                            <div
                              data-testid="social-production-readiness"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.production_readiness.ready_for_first_scoped_cycle
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : Number(socialLaunchPreflight.production_readiness.blockers?.length || 0) > 0
                                    ? 'border-amber-200/30 bg-amber-950/20 text-amber-50'
                                    : 'border-sky-200/30 bg-sky-400/10 text-sky-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Готовность к первому циклу' : 'First-cycle readiness'}
                                    {' · '}
                                    {isRu
                                      ? String(socialLaunchPreflight.production_readiness.title_ru || '')
                                      : String(socialLaunchPreflight.production_readiness.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.production_readiness.summary_ru || '')
                                      : String(socialLaunchPreflight.production_readiness.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {String(socialLaunchPreflight.production_readiness.status || 'prepare_first')}
                                </span>
                              </div>
                              {Number(socialLaunchPreflight.production_readiness.blockers?.length || 0) > 0 ? (
                                <div className="mt-2 rounded-lg bg-white/10 px-2 py-2">
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Блокеры перед запуском' : 'Launch blockers'}
                                  </div>
                                  <ul className="mt-1 space-y-1">
                                    {(socialLaunchPreflight.production_readiness.blockers || []).slice(0, 4).map((item) => (
                                      <li key={`production-blocker:${String(item.key || '')}`} className="text-amber-50">
                                        <span className="font-semibold text-white">
                                          {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                        </span>
                                        {': '}
                                        {isRu ? String(item.action_ru || '') : String(item.action_en || '')}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ) : null}
                              {Number(socialLaunchPreflight.production_readiness.warnings?.length || 0) > 0 ? (
                                <div className="mt-2 flex flex-wrap gap-1">
                                  {(socialLaunchPreflight.production_readiness.warnings || []).slice(0, 4).map((item) => (
                                    <span
                                      key={`production-warning:${String(item.key || '')}`}
                                      className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-slate-50"
                                    >
                                      {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Что сделать: ' : 'What to do: '}
                                {isRu
                                  ? String(socialLaunchPreflight.production_readiness.next_action_ru || '')
                                  : String(socialLaunchPreflight.production_readiness.next_action_en || '')}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.proof_requirements ? (
                            <div
                              data-testid="social-proof-requirements"
                              data-schema={String(socialLaunchPreflight.proof_requirements.schema || 'localos_social_proof_requirements_v1')}
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                String(socialLaunchPreflight.proof_requirements.status || '') === 'ready_for_live_proof'
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-sky-200/30 bg-sky-400/10 text-sky-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu
                                      ? String(socialLaunchPreflight.proof_requirements.title_ru || 'Что осталось для живого теста')
                                      : String(socialLaunchPreflight.proof_requirements.title_en || 'What remains for the live proof')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.proof_requirements.summary_ru || '')
                                      : String(socialLaunchPreflight.proof_requirements.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {Number(socialLaunchPreflight.proof_requirements.ready_groups || 0)}
                                  {'/'}
                                  {Number(socialLaunchPreflight.proof_requirements.total_groups || 0)}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-2 lg:grid-cols-3">
                                {(socialLaunchPreflight.proof_requirements.groups || []).slice(0, 3).map((group) => {
                                  const state = String(group.state || '');
                                  const ready = state === 'ready' || state === 'complete';
                                  const attention = state === 'needs_setup' || state === 'needs_channel' || state === 'needs_manual_fallback';
                                  const stateClass = ready
                                    ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                    : attention
                                      ? 'border-amber-200/30 bg-amber-400/10 text-amber-50'
                                      : 'border-white/10 bg-white/10 text-slate-100';
                                  const checklist = isRu ? group.checklist_ru : group.checklist_en;
                                  return (
                                    <div
                                      key={`proof-requirement:${String(group.key || '')}`}
                                      className={['rounded-lg border px-2 py-2', stateClass].join(' ')}
                                    >
                                      <div className="flex items-center justify-between gap-2">
                                        <span className="font-semibold text-white">
                                          {isRu
                                            ? String(group.title_ru || (
                                              String(group.key || '') === 'telegram_vk_api_proof'
                                                ? 'Telegram/VK API proof'
                                                : String(group.key || '') === 'maps_supervised_handoff'
                                                  ? 'Яндекс/2ГИС handoff'
                                                  : String(group.key || '') === 'metrics_and_recommendation'
                                                    ? 'Метрики и заявки'
                                                    : ''
                                            ))
                                            : String(group.title_en || '')}
                                        </span>
                                        <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white">
                                          {state || 'pending'}
                                        </span>
                                      </div>
                                      <div className="mt-1">
                                        {isRu ? String(group.summary_ru || '') : String(group.summary_en || '')}
                                      </div>
                                      {Array.isArray(checklist) && checklist.length > 0 ? (
                                        <ul className="mt-2 space-y-1">
                                          {checklist.slice(0, 3).map((step, index) => (
                                            <li key={`proof-step:${String(group.key || '')}:${index}:${step}`} className="flex gap-1.5">
                                              <span className="font-semibold text-white">{index + 1}.</span>
                                              <span>{step}</span>
                                            </li>
                                          ))}
                                        </ul>
                                      ) : null}
                                      <div className="mt-2 font-medium text-white">
                                        {isRu ? 'Дальше: ' : 'Next: '}
                                        {isRu ? String(group.next_action_ru || '') : String(group.next_action_en || '')}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                              <div className="mt-2 rounded-md bg-white/10 px-2 py-1 text-slate-100">
                                <span className="font-semibold text-white">
                                  {isRu ? 'Главный KPI: ' : 'Primary KPI: '}
                                </span>
                                {isRu
                                  ? String(socialLaunchPreflight.proof_requirements.primary_metric_ru || 'Заявки и обращения')
                                  : String(socialLaunchPreflight.proof_requirements.primary_metric_en || 'Leads and inquiries')}
                                {' · '}
                                {isRu
                                  ? 'внешняя публикация только после подтверждения, карты без финального автоклика.'
                                  : 'external publish only after approval, maps without final auto-click.'}
                              </div>
                              {(socialLaunchPreflight.proof_requirements.next_action_ru || socialLaunchPreflight.proof_requirements.next_action_en) ? (
                                <div className="mt-2 font-medium text-white">
                                  {isRu ? 'Ближайший шаг: ' : 'Closest next step: '}
                                  {isRu
                                    ? String(socialLaunchPreflight.proof_requirements.next_action_ru || '')
                                    : String(socialLaunchPreflight.proof_requirements.next_action_en || '')}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          {socialLaunchPreflight.first_api_publish_readiness ? (
                            <div
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.first_api_publish_readiness.ready
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-200/30 bg-amber-400/10 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-white">
                                  {isRu ? 'Первый API-пост' : 'First API post'}
                                </span>
                                <span className="rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialLaunchPreflight.first_api_publish_readiness.ready
                                    ? (isRu ? 'есть готовый канал' : 'ready channel')
                                    : (isRu ? 'нужны ключи' : 'needs keys')}
                                </span>
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? String(socialLaunchPreflight.first_api_publish_readiness.message_ru || '')
                                  : String(socialLaunchPreflight.first_api_publish_readiness.message_en || '')}
                              </div>
                              {(socialLaunchPreflight.first_api_publish_readiness.ready_platforms || []).length > 0 ? (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {(socialLaunchPreflight.first_api_publish_readiness.ready_platforms || []).slice(0, 4).map((item) => (
                                    <span
                                      key={`launch-api-ready:${String(item.platform || '')}`}
                                      className="rounded-full bg-emerald-400/20 px-2 py-0.5 font-medium text-emerald-50"
                                    >
                                      {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                              {(socialLaunchPreflight.first_api_publish_readiness.blocked_platforms || []).length > 0 ? (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {(socialLaunchPreflight.first_api_publish_readiness.blocked_platforms || []).slice(0, 4).map((item) => (
                                    <span
                                      key={`launch-api-blocked:${String(item.platform || '')}`}
                                      className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-amber-50"
                                    >
                                      {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                      {' · '}
                                      {String(item.status || 'not_ready')}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                              <div
                                data-testid="social-first-api-fast-start"
                                className="mt-2 rounded-lg bg-white/10 px-2 py-2"
                              >
                                <div className="font-semibold text-white">
                                  {isRu ? 'Быстрый старт API' : 'Fast API start'}
                                </div>
                                <div className="mt-1 text-slate-100">
                                  {isRu
                                    ? String(socialLaunchPreflight.first_api_publish_readiness.fast_start_message_ru || 'Telegram или VK быстрее всего дают первый проверенный API-пост.')
                                    : String(socialLaunchPreflight.first_api_publish_readiness.fast_start_message_en || 'Telegram or VK usually provide the fastest proven API post.')}
                                </div>
                                {(
                                  (socialLaunchPreflight.first_api_publish_readiness.fast_start_ready_platforms || []).length > 0
                                  || (socialLaunchPreflight.first_api_publish_readiness.fast_start_blocked_platforms || []).length > 0
                                ) ? (
                                  <div className="mt-2 flex flex-wrap gap-1">
                                    {(socialLaunchPreflight.first_api_publish_readiness.fast_start_ready_platforms || []).slice(0, 2).map((item) => (
                                      <span
                                        key={`fast-api-ready:${String(item.platform || '')}`}
                                        className="rounded-full bg-emerald-400/20 px-2 py-0.5 font-medium text-emerald-50"
                                      >
                                        {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                        {' · '}
                                        {isRu ? 'готов' : 'ready'}
                                      </span>
                                    ))}
                                    {(socialLaunchPreflight.first_api_publish_readiness.fast_start_blocked_platforms || []).slice(0, 2).map((item) => (
                                      <span
                                        key={`fast-api-blocked:${String(item.platform || '')}`}
                                        className="rounded-full bg-amber-950/20 px-2 py-0.5 font-medium text-amber-50"
                                      >
                                        {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                        {' · '}
                                        {String(item.status || 'not_ready')}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                                {(
                                  isRu
                                    ? socialLaunchPreflight.first_api_publish_readiness.safe_path_ru
                                    : socialLaunchPreflight.first_api_publish_readiness.safe_path_en
                                )?.length ? (
                                  <ol className="mt-2 grid gap-1 sm:grid-cols-2">
                                    {(
                                      isRu
                                        ? socialLaunchPreflight.first_api_publish_readiness.safe_path_ru
                                        : socialLaunchPreflight.first_api_publish_readiness.safe_path_en
                                    )?.slice(0, 5).map((step, index) => (
                                      <li key={`fast-api-safe-path:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                                        <span className="font-semibold text-white">{index + 1}.</span>
                                        <span>{step}</span>
                                      </li>
                                    ))}
                                  </ol>
                                ) : null}
                                {(socialLaunchPreflight.first_api_publish_readiness.pre_proof_checks || []).length > 0 ? (
                                  <div
                                    data-testid="social-first-api-pre-proof-checks"
                                    className="mt-2 rounded-lg border border-white/10 bg-white/10 px-2 py-2"
                                  >
                                    <div className="font-semibold text-white">
                                      {isRu ? 'Проверка перед первым API-proof' : 'Check before first API proof'}
                                    </div>
                                    <div className="mt-1 space-y-2">
                                      {(socialLaunchPreflight.first_api_publish_readiness.pre_proof_checks || []).slice(0, 3).map((check) => {
                                        const isTelegramTargetProbe = String(check.endpoint || '') === '/api/business/telegram-bot/publish-target-probe'
                                          || String(check.key || '').includes('telegram_publish_target');
                                        return (
                                          <div key={`first-api-pre-proof:${String(check.key || check.platform || '')}`} className="rounded-md bg-white/10 px-2 py-1.5 text-slate-100">
                                            <div className="font-semibold text-white">
                                              {isRu
                                                ? String(check.label_ru || 'Проверить API-канал без публикации')
                                                : String(check.label_en || 'Check API channel without publishing')}
                                            </div>
                                            <div className="mt-0.5">
                                              {isRu ? String(check.message_ru || '') : String(check.message_en || '')}
                                            </div>
                                            <div className="mt-0.5">
                                              <span className="font-semibold text-white">{isRu ? 'Что сделать: ' : 'Next: '}</span>
                                              {isRu ? String(check.action_ru || '') : String(check.action_en || '')}
                                            </div>
                                            {check.endpoint ? (
                                              <div className="mt-0.5 text-[10px] text-slate-200">
                                                {String(check.endpoint)}
                                                {' · '}
                                                {check.external_post_published === false
                                                  ? (isRu ? 'без публикации' : 'no publish')
                                                  : ''}
                                              </div>
                                            ) : null}
                                            {isTelegramTargetProbe ? (
                                              <div className="mt-2 rounded-md border border-sky-200/20 bg-sky-950/20 px-2 py-2">
                                                <div className="flex flex-wrap items-center justify-between gap-2">
                                                  <div>
                                                    <div className="font-semibold text-white">
                                                      {isRu ? 'Telegram-цель поста' : 'Telegram post target'}
                                                    </div>
                                                    <div className="mt-0.5 text-[11px] text-sky-50">
                                                      {isRu
                                                        ? 'Read-only проверка: бот, цель и право писать. Сообщение не отправляется.'
                                                        : 'Read-only check: bot, target, and write permission. No message is sent.'}
                                                    </div>
                                                  </div>
                                                  <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="secondary"
                                                    data-testid="social-run-telegram-publish-target-probe"
                                                    disabled={!businessId || socialBusyAction === 'telegram-publish-target-probe'}
                                                    onClick={checkTelegramPublishTargetProbe}
                                                    className="h-8 rounded-md bg-white text-slate-900 hover:bg-slate-100"
                                                  >
                                                    {socialBusyAction === 'telegram-publish-target-probe'
                                                      ? (isRu ? 'Проверяем...' : 'Checking...')
                                                      : (isRu ? 'Проверить цель Telegram' : 'Check Telegram target')}
                                                  </Button>
                                                </div>
                                                {socialTelegramPublishTargetProbe ? (
                                                  <div
                                                    data-testid="social-telegram-publish-target-probe-result"
                                                    className={[
                                                      'mt-2 rounded-md border px-2 py-2 text-[11px]',
                                                      socialTelegramPublishTargetProbe.ready
                                                        ? 'border-emerald-200/30 bg-emerald-950/25 text-emerald-50'
                                                        : 'border-amber-200/30 bg-amber-950/25 text-amber-50',
                                                    ].join(' ')}
                                                  >
                                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                                      <div className="font-semibold text-white">
                                                        {socialTelegramPublishTargetProbe.ready
                                                          ? (isRu ? 'Готово к API-proof' : 'Ready for API proof')
                                                          : (isRu ? 'Нужно действие перед API-proof' : 'Action needed before API proof')}
                                                      </div>
                                                      <span className="rounded-full bg-white/15 px-2 py-0.5 font-semibold text-white">
                                                        {String(socialTelegramPublishTargetProbe.status || 'checked')}
                                                      </span>
                                                    </div>
                                                    <div className="mt-1">
                                                      {isRu
                                                        ? String(socialTelegramPublishTargetProbe.message_ru || socialTelegramPublishTargetProbe.next_action_ru || '')
                                                        : String(socialTelegramPublishTargetProbe.message_en || socialTelegramPublishTargetProbe.next_action_en || '')}
                                                    </div>
                                                    {(socialTelegramPublishTargetProbe.target_summary_ru || socialTelegramPublishTargetProbe.target_summary_en) ? (
                                                      <div
                                                        data-testid="social-telegram-publish-target-evidence"
                                                        className="mt-1 rounded bg-white/15 px-2 py-1 font-medium text-white"
                                                      >
                                                        {isRu
                                                          ? String(socialTelegramPublishTargetProbe.target_summary_ru || '')
                                                          : String(socialTelegramPublishTargetProbe.target_summary_en || socialTelegramPublishTargetProbe.target_summary_ru || '')}
                                                      </div>
                                                    ) : null}
                                                    <div className="mt-1 grid gap-1 sm:grid-cols-3">
                                                      <div className="rounded bg-white/10 px-2 py-1">
                                                        <span className="font-semibold text-white">{isRu ? 'Бот: ' : 'Bot: '}</span>
                                                        {socialTelegramPublishTargetProbe.target_evidence?.bot?.username
                                                          ? `@${socialTelegramPublishTargetProbe.target_evidence.bot.username}`
                                                          : String(socialTelegramPublishTargetProbe.target_evidence?.bot?.display_name || (isRu ? 'не определён' : 'unknown'))}
                                                      </div>
                                                      <div className="rounded bg-white/10 px-2 py-1">
                                                        <span className="font-semibold text-white">{isRu ? 'Цель: ' : 'Target: '}</span>
                                                        {String(socialTelegramPublishTargetProbe.target_evidence?.target?.display_name || (isRu ? 'не определена' : 'unknown'))}
                                                      </div>
                                                      <div className="rounded bg-white/10 px-2 py-1">
                                                        <span className="font-semibold text-white">{isRu ? 'Отправка: ' : 'Send: '}</span>
                                                        {socialTelegramPublishTargetProbe.send_message_performed === false
                                                          ? (isRu ? 'не выполнялась' : 'not performed')
                                                          : (isRu ? 'не запускать без approval' : 'requires approval')}
                                                      </div>
                                                    </div>
                                                  </div>
                                                ) : null}
                                              </div>
                                            ) : null}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                ) : null}
                              </div>
                              <div className="mt-1 font-medium text-white">
                                {isRu
                                  ? String(socialLaunchPreflight.first_api_publish_readiness.next_action_ru || '')
                                  : String(socialLaunchPreflight.first_api_publish_readiness.next_action_en || '')}
                              </div>
                              {(
                                isRu
                                  ? socialLaunchPreflight.first_api_publish_readiness.first_post_checklist_ru
                                  : socialLaunchPreflight.first_api_publish_readiness.first_post_checklist_en
                              )?.length ? (
                                <div className="mt-2 rounded-lg bg-white/10 px-2 py-2">
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Чеклист первого API-поста' : 'First API post checklist'}
                                  </div>
                                  <ol className="mt-1 space-y-1">
                                    {(
                                      isRu
                                        ? socialLaunchPreflight.first_api_publish_readiness.first_post_checklist_ru
                                        : socialLaunchPreflight.first_api_publish_readiness.first_post_checklist_en
                                    )?.slice(0, 5).map((step, index) => (
                                      <li key={`first-api-checklist:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                                        <span className="font-semibold text-white">{index + 1}.</span>
                                        <span>{step}</span>
                                      </li>
                                    ))}
                                  </ol>
                                </div>
                              ) : null}
                              {(
                                isRu
                                  ? socialLaunchPreflight.first_api_publish_readiness.first_api_launch_plan_ru
                                  : socialLaunchPreflight.first_api_publish_readiness.first_api_launch_plan_en
                              )?.length ? (
                                <div
                                  data-testid="social-first-api-launch-plan"
                                  className="mt-2 rounded-lg bg-white/10 px-2 py-2"
                                >
                                  <div className="font-semibold text-white">
                                    {isRu ? 'План первого API-поста' : 'First API post launch plan'}
                                  </div>
                                  <ol className="mt-1 space-y-1">
                                    {(
                                      isRu
                                        ? socialLaunchPreflight.first_api_publish_readiness.first_api_launch_plan_ru
                                        : socialLaunchPreflight.first_api_publish_readiness.first_api_launch_plan_en
                                    )?.slice(0, 5).map((step, index) => (
                                      <li key={`first-api-launch-plan:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                                        <span className="font-semibold text-white">{index + 1}.</span>
                                        <span>{step}</span>
                                      </li>
                                    ))}
                                  </ol>
                                  <div className="mt-2 rounded-md bg-white/10 px-2 py-1 text-slate-100">
                                    <span className="font-semibold text-white">
                                      {isRu ? 'Почему этот канал: ' : 'Why this channel: '}
                                    </span>
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_publish_readiness.recommended_start_reason_ru || '')
                                      : String(socialLaunchPreflight.first_api_publish_readiness.recommended_start_reason_en || '')}
                                  </div>
                                  <div className="mt-1 rounded-md bg-white/10 px-2 py-1 text-slate-100">
                                    <span className="font-semibold text-white">
                                      {isRu ? 'Proof-check: ' : 'Proof check: '}
                                    </span>
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_publish_readiness.proof_check_ru || 'После первого запуска проверьте provider_post_id/provider_post_url; без этого цикл не доказан.')
                                      : String(socialLaunchPreflight.first_api_publish_readiness.proof_check_en || 'After the first run, check provider_post_id/provider_post_url; without that, the loop is not proven.')}
                                  </div>
                                  <div className="mt-1 rounded-md bg-white/10 px-2 py-1 text-slate-100">
                                    <span className="font-semibold text-white">
                                      {isRu ? 'После публикации: ' : 'After publishing: '}
                                    </span>
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_publish_readiness.metrics_followup_ru || 'После первого подтверждённого запуска соберите реакции/заявки; следующий план не меняется автоматически без подтверждения.')
                                      : String(socialLaunchPreflight.first_api_publish_readiness.metrics_followup_en || 'After proof, collect reactions/leads; the next plan is not changed automatically without approval.')}
                                  </div>
                                </div>
                              ) : null}
                              <div className="mt-1 text-slate-200">
                                {isRu
                                  ? String(socialLaunchPreflight.first_api_publish_readiness.publish_path_ru || 'Только после предпросмотра, подтверждения, расписания и наступления даты.')
                                  : String(socialLaunchPreflight.first_api_publish_readiness.publish_path_en || 'Only after preview, human approval, queueing, and the due date.')}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.launch_rehearsal ? (
                            <div
                              data-testid="social-launch-rehearsal"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                Number(socialLaunchPreflight.launch_rehearsal.summary?.manual_or_blocked || 0) > 0
                                  ? 'border-amber-200/30 bg-amber-400/10 text-amber-50'
                                  : Number(socialLaunchPreflight.launch_rehearsal.summary?.ready || 0) > 0
                                    ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                    : 'border-sky-200/30 bg-sky-400/10 text-sky-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Проверка постов на текущую дату' : 'Due-post launch check'}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.launch_rehearsal.summary?.message_ru || '')
                                      : String(socialLaunchPreflight.launch_rehearsal.summary?.message_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {String(socialLaunchPreflight.launch_rehearsal.summary?.status || 'empty')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-4">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_rehearsal.summary?.ready || 0)}</span>
                                  {' '}
                                  {isRu ? 'готово' : 'ready'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_rehearsal.summary?.api_ready || 0)}</span>
                                  {' '}
                                  API
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_rehearsal.summary?.supervised_ready || 0)}</span>
                                  {' '}
                                  {isRu ? 'контроль' : 'supervised'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_rehearsal.summary?.manual_or_blocked || 0)}</span>
                                  {' '}
                                  {isRu ? 'внимание' : 'attention'}
                                </div>
                              </div>
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                {isRu
                                  ? String(socialLaunchPreflight.launch_rehearsal.summary?.next_action_ru || '')
                                  : String(socialLaunchPreflight.launch_rehearsal.summary?.next_action_en || '')}
                              </div>
                              <div className="mt-1 text-slate-200">
                                {isRu
                                  ? 'Проверка запуска: наружу ничего не отправлено, provider write не выполнялся, финальный клик в Яндекс/2ГИС запрещён.'
                                  : 'Launch check: nothing was sent externally, provider write did not run, and the Yandex/2GIS final click is disabled.'}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.next_action_ru || socialLaunchPreflight.next_action_en ? (
                            <div className="mt-1 font-medium text-white">
                              {isRu ? 'Следующий шаг: ' : 'Next step: '}
                              {isRu
                                ? String(socialLaunchPreflight.next_action_ru || '')
                                : String(socialLaunchPreflight.next_action_en || '')}
                            </div>
                          ) : null}
                          {Number(socialLaunchPreflight.api_preflight_blocked_due_posts?.length || 0) > 0 ? (
                            <div className="mt-2 rounded-lg border border-amber-200/30 bg-amber-950/20 px-2 py-2 text-[11px] leading-5 text-amber-50">
                              <div className="font-semibold text-white">
                                {isRu ? 'Live API-preflight остановил запуск' : 'Live API preflight blocked launch'}
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? 'Исполнитель не будет запущен, пока API-посты с наступившей датой смотрят в канал без готовых ключей, прав, локации или адаптера.'
                                  : 'The worker will not run while due API posts target a channel without ready keys, permissions, location, or adapter.'}
                              </div>
                              <div className="mt-1 flex flex-wrap gap-1">
                                {(socialLaunchPreflight.api_preflight_blocked_due_posts || []).slice(0, 4).map((item) => (
                                  <div
                                    key={`launch-api-block:${String(item.id || '')}:${String(item.platform || '')}`}
                                    className="rounded-lg bg-white/10 px-2 py-1.5 text-amber-50"
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <span className="font-semibold text-white">
                                        {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                        {' · '}
                                        {String(item.status || 'not_ready')}
                                      </span>
                                      {item.settings_path ? (
                                        <button
                                          type="button"
                                          className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-white/20"
                                          onClick={() => navigate(String(item.settings_path || _socialSettingsPathForPlatform(String(item.platform || ''))))}
                                        >
                                          {isRu ? 'Открыть настройку' : 'Open setup'}
                                        </button>
                                      ) : null}
                                    </div>
                                    {(isRu ? item.message_ru : item.message_en) ? (
                                      <div className="mt-1 text-amber-100">
                                        {isRu ? String(item.message_ru || '') : String(item.message_en || '')}
                                      </div>
                                    ) : null}
                                    {(isRu ? item.next_action_ru : item.next_action_en) ? (
                                      <div className="mt-1 font-medium text-white">
                                        {isRu ? 'Что сделать: ' : 'What to do: '}
                                        {isRu ? String(item.next_action_ru || '') : String(item.next_action_en || '')}
                                      </div>
                                    ) : null}
                                    <div className="mt-1 text-[10px] leading-4 text-amber-100">
                                      {isRu
                                        ? String(item.safety_summary_ru || 'Исполнитель не будет публиковать этот пост, пока канал не пройдёт live API-проверку.')
                                        : String(item.safety_summary_en || 'The worker will not publish this due post until the channel passes live API preflight.')}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                          <div className="mt-2 rounded-lg bg-white/10 px-2 py-1.5 text-[11px] text-slate-200">
                            {isRu
                              ? `Рекомендованный бизнес для запуска: SOCIAL_POST_DISPATCH_BUSINESS_ID=${String(socialLaunchPreflight.recommended_env?.dispatch?.SOCIAL_POST_DISPATCH_BUSINESS_ID || businessId || '')}`
                              : `Recommended scope: SOCIAL_POST_DISPATCH_BUSINESS_ID=${String(socialLaunchPreflight.recommended_env?.dispatch?.SOCIAL_POST_DISPATCH_BUSINESS_ID || businessId || '')}`}
                          </div>
                          {socialLaunchPreflight.runtime_alignment ? (
                            <div className="mt-2 rounded-lg bg-white/10 px-2 py-1.5 text-[11px] leading-5 text-slate-200">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-white">
                                  {isRu ? 'Исполнитель этого бизнеса' : 'This business runtime'}
                                </span>
                                <span
                                  className={[
                                    'rounded-full px-2 py-0.5 font-semibold',
                                    socialLaunchPreflight.runtime_alignment.dispatch?.can_process_this_business
                                      ? 'bg-emerald-400/20 text-emerald-100'
                                      : 'bg-amber-400/20 text-amber-100',
                                  ].join(' ')}
                                >
                                  {socialLaunchPreflight.runtime_alignment.dispatch?.can_process_this_business
                                    ? (isRu ? 'совпадает' : 'matches')
                                    : (isRu ? 'нужно настроить' : 'needs setup')}
                                </span>
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? String(socialLaunchPreflight.runtime_alignment.dispatch?.message_ru || '')
                                  : String(socialLaunchPreflight.runtime_alignment.dispatch?.message_en || '')}
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? String(socialLaunchPreflight.runtime_alignment.metrics?.message_ru || '')
                                  : String(socialLaunchPreflight.runtime_alignment.metrics?.message_en || '')}
                              </div>
                              {(socialLaunchPreflight.runtime_alignment.next_action_ru || socialLaunchPreflight.runtime_alignment.next_action_en) ? (
                                <div className="mt-1 font-medium text-white">
                                  {isRu
                                    ? String(socialLaunchPreflight.runtime_alignment.next_action_ru || '')
                                    : String(socialLaunchPreflight.runtime_alignment.next_action_en || '')}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          {socialLaunchPreflight.launch_gate ? (
                            <div
                              data-testid="social-first-cycle-launch-gate"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.launch_gate.allowed
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-200/30 bg-amber-950/20 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Можно ли запускать сейчас' : 'Can run now'}
                                    {' · '}
                                    {isRu
                                      ? String(socialLaunchPreflight.launch_gate.title_ru || '')
                                      : String(socialLaunchPreflight.launch_gate.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.launch_gate.summary_ru || '')
                                      : String(socialLaunchPreflight.launch_gate.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialLaunchPreflight.launch_gate.allowed
                                    ? (isRu ? 'разрешено' : 'allowed')
                                    : (isRu ? 'стоп' : 'blocked')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-4">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_gate.api_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'API' : 'API'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_gate.supervised_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'контроль' : 'supervised'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_gate.manual_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'вручную' : 'manual'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_gate.blocked_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'блокеры' : 'blocked'}
                                </div>
                              </div>
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                {isRu
                                  ? String(socialLaunchPreflight.launch_gate.next_action_ru || '')
                                  : String(socialLaunchPreflight.launch_gate.next_action_en || '')}
                              </div>
                              <div className="mt-1 text-slate-200">
                                {isRu
                                  ? 'Нажатие запуска всё равно требует подтверждения; Яндекс/2ГИС без финального клика.'
                                  : 'Running still requires confirmation; Yandex/2GIS keep the final click disabled.'}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.first_api_proof_gate ? (
                            <div
                              data-testid="social-first-api-proof-gate"
                              data-schema="localos_social_first_api_proof_gate_v1"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.first_api_proof_gate.allowed
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-200/30 bg-amber-950/20 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Первый API-proof' : 'First API proof'}
                                    {' · '}
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_proof_gate.title_ru || '')
                                      : String(socialLaunchPreflight.first_api_proof_gate.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_proof_gate.summary_ru || '')
                                      : String(socialLaunchPreflight.first_api_proof_gate.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialLaunchPreflight.first_api_proof_gate.allowed
                                    ? (isRu ? 'можно проверить' : 'can verify')
                                    : (isRu ? 'не готово' : 'not ready')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-3">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialLaunchPreflight.first_api_proof_gate.ui_run_once_allowed ? (isRu ? 'да' : 'yes') : (isRu ? 'нет' : 'no')}
                                  </span>
                                  {' '}
                                  {isRu ? 'запуск из LocalOS' : 'LocalOS run'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialLaunchPreflight.first_api_proof_gate.background_worker_aligned ? (isRu ? 'да' : 'yes') : (isRu ? 'нет' : 'no')}
                                  </span>
                                  {' '}
                                  {isRu ? 'бизнес запуска' : 'worker scope'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {Number(socialLaunchPreflight.first_api_proof_gate.blocked_posts || 0)}
                                  </span>
                                  {' '}
                                  {isRu ? 'блокеры' : 'blockers'}
                                </div>
                              </div>
                              {socialLaunchPreflight.first_api_proof_gate.candidate?.ready ? (
                                <div className="mt-2 rounded-md bg-white/10 px-2 py-1.5 text-slate-100">
                                  <div className="font-semibold text-white">
                                    {socialLaunchPreflight.first_api_proof_gate.candidate.platform_label
                                      || _socialPlatformLabel(String(socialLaunchPreflight.first_api_proof_gate.candidate.platform || ''), isRu)}
                                  </div>
                                  <div>
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_proof_gate.candidate.proof_check_ru || 'После запуска должен появиться provider_post_id/provider_post_url.')
                                      : String(socialLaunchPreflight.first_api_proof_gate.candidate.proof_check_en || 'After launch, provider_post_id/provider_post_url must appear.')}
                                  </div>
                                </div>
                              ) : null}
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                {isRu
                                  ? String(socialLaunchPreflight.first_api_proof_gate.next_action_ru || '')
                                  : String(socialLaunchPreflight.first_api_proof_gate.next_action_en || '')}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.first_cycle_proof_packet ? (
                            <div
                              data-testid="social-first-cycle-proof-packet"
                              data-schema="localos_social_first_cycle_proof_packet_v1"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.first_cycle_proof_packet.ready_to_run_once
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-200/30 bg-amber-950/20 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Пакет первого запуска' : 'First-cycle proof packet'}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.first_cycle_proof_packet.run_once_action_ru || '')
                                      : String(socialLaunchPreflight.first_cycle_proof_packet.run_once_action_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialLaunchPreflight.first_cycle_proof_packet.ready_to_run_once
                                    ? (isRu ? 'можно один цикл' : 'one cycle ready')
                                    : (isRu ? 'не готово' : 'not ready')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-3">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {String(socialLaunchPreflight.first_cycle_proof_packet.dispatch_business_id || '-')}
                                  </span>
                                  {' '}
                                  {isRu ? 'бизнес запуска' : 'dispatch scope'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialLaunchPreflight.first_cycle_proof_packet.candidate_platform_label
                                      || _socialPlatformLabel(String(socialLaunchPreflight.first_cycle_proof_packet.candidate_platform || ''), isRu)
                                      || '-'}
                                  </span>
                                  {' '}
                                  API-proof
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {Number(socialLaunchPreflight.first_cycle_proof_packet.checklist_done || 0)}
                                    /
                                    {Number(socialLaunchPreflight.first_cycle_proof_packet.checklist_total || 0)}
                                  </span>
                                  {' '}
                                  {isRu ? 'чеклист' : 'checklist'}
                                </div>
                              </div>
                              {socialLaunchPreflight.first_cycle_proof_packet.external_publish_confirmation_phrase ? (
                                <div
                                  data-testid="social-first-cycle-confirmation-phrase"
                                  className="mt-2 rounded-md border border-white/10 bg-white/10 px-2 py-1.5 text-slate-100"
                                >
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Фраза подтверждения внешней публикации' : 'External publish confirmation phrase'}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.first_cycle_proof_packet.external_publish_confirmation_ru || '')
                                      : String(socialLaunchPreflight.first_cycle_proof_packet.external_publish_confirmation_en || '')}
                                  </div>
                                  <div className="mt-1 inline-flex rounded-md bg-white/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-white">
                                    {String(socialLaunchPreflight.first_cycle_proof_packet.external_publish_confirmation_phrase || '')}
                                  </div>
                                </div>
                              ) : null}
                              {socialLaunchPreflight.first_cycle_proof_packet.ready_to_run_once ? (
                                <div className="mt-2 rounded-md bg-white/10 px-2 py-1.5 text-slate-100">
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Что проверить после цикла' : 'What to verify after the cycle'}
                                  </div>
                                  <ol className="mt-1 space-y-1">
                                    {(
                                      isRu
                                        ? socialLaunchPreflight.first_cycle_proof_packet.after_run_checks_ru || []
                                        : socialLaunchPreflight.first_cycle_proof_packet.after_run_checks_en || []
                                    ).slice(0, 4).map((step, index) => (
                                      <li key={`first-cycle-proof-check:${index}:${step}`} className="flex gap-1.5">
                                        <span className="font-semibold text-white">{index + 1}.</span>
                                        <span>{step}</span>
                                      </li>
                                    ))}
                                  </ol>
                                </div>
                              ) : (
                                <div className="mt-2 rounded-md bg-white/10 px-2 py-1.5 text-amber-50">
                                  <span className="font-semibold text-white">
                                    {isRu ? 'Что мешает: ' : 'Blocked by: '}
                                  </span>
                                  {isRu
                                    ? String(socialLaunchPreflight.first_cycle_proof_packet.blocked_reason_ru || '')
                                    : String(socialLaunchPreflight.first_cycle_proof_packet.blocked_reason_en || '')}
                                </div>
                              )}
                            </div>
                          ) : null}
                          {Number(socialLaunchPreflight.live_validation_checklist?.length || 0) > 0 ? (
                            <div
                              data-testid="social-live-validation-checklist"
                              className="mt-2 rounded-lg border border-sky-200/30 bg-sky-400/10 px-2 py-2 text-[11px] leading-5 text-sky-50"
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Чеклист живой проверки' : 'Live validation checklist'}
                                  </div>
                                  <div className="mt-1 text-sky-100">
                                    {isRu
                                      ? 'Эти пункты показывают, доказан ли полный loop: публикация, контроль карт, сбор результата и корректировка плана.'
                                      : 'These items show whether the full loop is proven: publishing, map control, result collection, and plan correction.'}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {Number(socialLaunchPreflight.live_validation_checklist?.filter((item) => item.status === 'done').length || 0)}
                                  /
                                  {Number(socialLaunchPreflight.live_validation_checklist?.length || 0)}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-2 md:grid-cols-2">
                                {(socialLaunchPreflight.live_validation_checklist || []).map((item) => {
                                  const itemStatus = String(item.status || '').trim();
                                  const tone = itemStatus === 'done'
                                    ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                    : itemStatus === 'attention'
                                      ? 'border-amber-200/30 bg-amber-400/10 text-amber-50'
                                      : itemStatus === 'current'
                                        ? 'border-sky-200/40 bg-white/10 text-sky-50'
                                        : 'border-slate-200/20 bg-white/5 text-slate-100';
                                  return (
                                    <div
                                      key={`live-validation:${String(item.key || item.label_ru || item.label_en || '')}`}
                                      className={`rounded-lg border px-2 py-1.5 ${tone}`}
                                    >
                                      <div className="flex items-start justify-between gap-2">
                                        <span className="font-semibold text-white">
                                          {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                        </span>
                                        <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-medium text-white">
                                          {_socialLearningChecklistStatusLabel(itemStatus, isRu)}
                                        </span>
                                      </div>
                                      <div className="mt-1">
                                        {isRu ? String(item.detail_ru || '') : String(item.detail_en || '')}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ) : null}
                          <Button
                            type="button"
                            size="sm"
                            onClick={() => { void runSocialDispatchOnce(); }}
                            disabled={
                              Boolean(bulkBusyAction)
                              || Boolean(socialBusyAction)
                              || !(socialLaunchPreflight.launch_gate?.allowed ?? socialLaunchPreflight.safe_to_enable_scoped_dispatch)
                            }
                            className="mt-2 h-8 bg-white text-slate-950 hover:bg-slate-100"
                          >
                            {socialBusyAction === 'dispatch-run-once'
                              ? (isRu ? 'Запускаем цикл...' : 'Running cycle...')
                              : (isRu ? 'Запустить один ограниченный цикл' : 'Run one scoped cycle')}
                          </Button>
                          <div className="mt-1 text-[11px] text-slate-300">
                            {isRu
                              ? 'Запускает только посты текущего бизнеса, у которых наступила дата. API может опубликовать подтверждённые посты в расписании; Яндекс/2ГИС останутся в контролируемом или ручном размещении.'
                              : 'Runs only due posts for the current business. API may publish approved/queued posts; Yandex/2GIS stay supervised or manual.'}
                          </div>
                          <div className="mt-2 rounded-lg bg-slate-950/30 px-2 py-2 text-[11px] text-slate-100 ring-1 ring-white/10">
                            <div className="font-semibold text-white">
                              {isRu ? 'Команды для безопасного запуска' : 'Safe launch env'}
                            </div>
                            <div className="mt-1 space-y-0.5 font-mono text-[10px] leading-4 text-slate-200">
                              {_socialWorkerEnvLines(
                                socialLaunchPreflight.recommended_env?.dispatch || {},
                                socialLaunchPreflight.recommended_env?.metrics || {},
                              ).map((line) => (
                                <div key={line} className="break-all">{line}</div>
                              ))}
                            </div>
                              <Button
                                type="button"
                                size="sm"
                              variant="outline"
                              className="mt-2 h-7 border-white/20 bg-white/10 px-2 text-[11px] text-white hover:bg-white/20"
                              onClick={() => { void copySocialWorkerEnv(); }}
                            >
                              {isRu ? 'Скопировать настройки запуска' : 'Copy worker env'}
                            </Button>
                          </div>
                          {_socialFirstCycleVerificationBlock(socialLaunchPreflight.first_cycle_verification, isRu)}
                          {_socialLaunchRunbookBlock(socialLaunchPreflight.launch_runbook, isRu)}
                          <div className="mt-1 text-[11px] text-slate-300">
                            {isRu
                              ? 'Проверка ничего не публикует: подтверждение обязательно, карты остаются контролируемыми или ручными без финального клика.'
                              : 'Preflight publishes nothing: approval is required, and maps stay supervised without the final click.'}
                          </div>
                        </div>
                      ) : null}
                      {socialDispatchExecutionReport ? (
                        <div
                          data-testid="social-dispatch-execution-report"
                          className={[
                            'rounded-xl border px-3 py-2 text-xs leading-5',
                            Number(socialDispatchExecutionReport.failed || 0) > 0
                              ? 'border-red-300/30 bg-red-400/10 text-red-100'
                              : Number(socialDispatchExecutionReport.manual || 0) > 0
                                ? 'border-amber-300/30 bg-amber-400/10 text-amber-100'
                                : 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
                          ].join(' ')}
                        >
                          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <div className="font-semibold text-white">
                                {isRu ? 'Результат последнего запуска' : 'Last launch result'}
                                {' · '}
                                {isRu
                                  ? String(socialDispatchExecutionReport.title_ru || '')
                                  : String(socialDispatchExecutionReport.title_en || '')}
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? String(socialDispatchExecutionReport.summary_ru || '')
                                  : String(socialDispatchExecutionReport.summary_en || '')}
                              </div>
                            </div>
                            <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-white">
                              {String(socialDispatchExecutionReport.status || 'empty')}
                            </span>
                          </div>
                          <div className="mt-2 grid gap-1 sm:grid-cols-5">
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.published || 0)}</span>
                              {' '}
                              {isRu ? 'опубликовано' : 'published'}
                            </div>
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.supervised || 0)}</span>
                              {' '}
                              {isRu ? 'контроль' : 'supervised'}
                            </div>
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.manual || 0)}</span>
                              {' '}
                              {isRu ? 'вручную' : 'manual'}
                            </div>
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.failed || 0)}</span>
                              {' '}
                              {isRu ? 'ошибки' : 'failed'}
                            </div>
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.provider_write_summary?.published_with_provider_proof || 0)}</span>
                              {' '}
                              proof
                            </div>
                          </div>
                          <div className="mt-2 font-medium text-white">
                            {isRu ? 'Следующий шаг: ' : 'Next step: '}
                            {isRu
                              ? String(socialDispatchExecutionReport.next_action_ru || '')
                              : String(socialDispatchExecutionReport.next_action_en || '')}
                          </div>
                          {socialDispatchExecutionReport.after_run_proof_packet ? (
                            <div
                              data-testid="social-after-run-proof-packet"
                              data-schema="localos_social_after_run_proof_packet_v1"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialDispatchExecutionReport.after_run_proof_packet.can_collect_results
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50'
                                  : Number(socialDispatchExecutionReport.after_run_proof_packet.failed || 0) > 0
                                    ? 'border-red-300/20 bg-red-400/10 text-red-50'
                                    : 'border-amber-300/20 bg-amber-400/10 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Проверка после запуска' : 'After-run proof'}
                                    {' · '}
                                    {isRu
                                      ? String(socialDispatchExecutionReport.after_run_proof_packet.title_ru || '')
                                      : String(socialDispatchExecutionReport.after_run_proof_packet.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialDispatchExecutionReport.after_run_proof_packet.next_action_ru || '')
                                      : String(socialDispatchExecutionReport.after_run_proof_packet.next_action_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialDispatchExecutionReport.after_run_proof_packet.api_proof_ready
                                    ? 'API proof'
                                    : (isRu ? 'proof нужен' : 'proof needed')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-3">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialDispatchExecutionReport.after_run_proof_packet.can_collect_results ? (isRu ? 'да' : 'yes') : (isRu ? 'нет' : 'no')}
                                  </span>
                                  {' '}
                                  {isRu ? 'собирать результат' : 'collect results'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialDispatchExecutionReport.after_run_proof_packet.maps_handoff_created ? (isRu ? 'да' : 'yes') : (isRu ? 'нет' : 'no')}
                                  </span>
                                  {' '}
                                  {isRu ? 'карты handoff' : 'maps handoff'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialDispatchExecutionReport.after_run_proof_packet.browser_final_click_allowed === false
                                      ? (isRu ? 'человек' : 'human')
                                      : (isRu ? 'неясно' : 'unclear')}
                                  </span>
                                  {' '}
                                  {isRu ? 'финальный клик' : 'final click'}
                                </div>
                              </div>
                              <ol className="mt-2 space-y-1">
                                {(
                                  isRu
                                    ? socialDispatchExecutionReport.after_run_proof_packet.checks_ru || []
                                    : socialDispatchExecutionReport.after_run_proof_packet.checks_en || []
                                ).slice(0, 4).map((step, index) => (
                                  <li key={`after-run-proof:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                                    <span className="font-semibold text-white">{index + 1}.</span>
                                    <span>{step}</span>
                                  </li>
                                ))}
                              </ol>
                            </div>
                          ) : null}
                          {socialDispatchExecutionReport.first_api_proof_summary ? (
                            <div
                              data-testid="social-first-api-proof-summary"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialDispatchExecutionReport.first_api_proof_summary.ready
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-300/20 bg-amber-400/10 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="font-semibold text-white">
                                {isRu ? 'Proof первого API-loop' : 'First API-loop proof'}
                              </div>
                              <div>
                                {isRu
                                  ? String(socialDispatchExecutionReport.first_api_proof_summary.summary_ru || '')
                                  : String(socialDispatchExecutionReport.first_api_proof_summary.summary_en || '')}
                              </div>
                              <div className="mt-1 text-slate-100">
                                {isRu ? 'Проверено API-постов: ' : 'API posts checked: '}
                                {Number(socialDispatchExecutionReport.first_api_proof_summary.api_posts_checked || 0)}
                                {' · '}
                                {isRu ? 'с provider_post_id/provider_post_url: ' : 'with provider_post_id/provider_post_url: '}
                                {Number(socialDispatchExecutionReport.first_api_proof_summary.published_with_provider_proof || 0)}
                              </div>
                              {socialDispatchExecutionReport.first_api_proof_summary.provider_post_url || socialDispatchExecutionReport.first_api_proof_summary.provider_post_id ? (
                                <div className="mt-1 break-all text-slate-100">
                                  {String(
                                    socialDispatchExecutionReport.first_api_proof_summary.provider_post_url
                                    || socialDispatchExecutionReport.first_api_proof_summary.provider_post_id
                                    || ''
                                  )}
                                </div>
                              ) : null}
                              <div className="mt-1 font-medium text-white">
                                {isRu
                                  ? String(socialDispatchExecutionReport.first_api_proof_summary.next_action_ru || '')
                                  : String(socialDispatchExecutionReport.first_api_proof_summary.next_action_en || '')}
                              </div>
                            </div>
                          ) : null}
                          <div className="mt-1 text-[11px] text-slate-200">
                            {isRu
                              ? 'API-публикации возможны только после подтверждения и расписания; Яндекс/2ГИС остаются контролируемыми или ручными без финального клика.'
                              : 'API publishes only after approval/queue; Yandex/2GIS stay supervised/manual without the final click.'}
                          </div>
                          {socialDispatchExecutionReport.post_publish_learning_gate ? (
                            <div
                              data-testid="social-post-publish-learning-gate"
                              data-schema="localos_social_post_publish_learning_gate_v1"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialDispatchExecutionReport.post_publish_learning_gate.allowed
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-300/20 bg-amber-400/10 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Сбор реакций и заявок' : 'Reactions and leads'}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialDispatchExecutionReport.post_publish_learning_gate.summary_ru || '')
                                      : String(socialDispatchExecutionReport.post_publish_learning_gate.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialDispatchExecutionReport.post_publish_learning_gate.allowed
                                    ? (isRu ? 'можно собирать' : 'can collect')
                                    : (isRu ? 'сначала publish' : 'publish first')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-3">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {Number(socialDispatchExecutionReport.post_publish_learning_gate.published_posts || 0)}
                                  </span>
                                  {' '}
                                  {isRu ? 'published' : 'published'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {Number(socialDispatchExecutionReport.post_publish_learning_gate.published_with_api_proof || 0)}
                                  </span>
                                  {' '}
                                  API proof
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {isRu
                                      ? String(socialDispatchExecutionReport.post_publish_learning_gate.primary_metric_ru || 'Заявки и обращения')
                                      : String(socialDispatchExecutionReport.post_publish_learning_gate.primary_metric_en || 'Leads and inquiries')}
                                  </span>
                                </div>
                              </div>
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                {isRu
                                  ? String(socialDispatchExecutionReport.post_publish_learning_gate.next_action_ru || '')
                                  : String(socialDispatchExecutionReport.post_publish_learning_gate.next_action_en || '')}
                              </div>
                              {(socialDispatchExecutionReport.post_publish_learning_gate.learning_actions || []).length > 0 ? (
                                <div
                                  data-testid="social-post-publish-learning-actions"
                                  className="mt-2 rounded-md bg-white/10 px-2 py-1.5"
                                >
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Порядок после публикации' : 'After-publish sequence'}
                                  </div>
                                  <ol className="mt-1 space-y-1">
                                    {(socialDispatchExecutionReport.post_publish_learning_gate.learning_actions || [])
                                      .slice()
                                      .sort((left, right) => Number(left.order || 0) - Number(right.order || 0))
                                      .slice(0, 4)
                                      .map((action) => (
                                        <li key={`publish-learning-action:${String(action.key || action.label_ru || action.label_en || '')}`} className="flex gap-1.5 text-slate-100">
                                          <span className="font-semibold text-white">{Number(action.order || 0) || ''}</span>
                                          <span>
                                            <span className="font-semibold text-white">
                                              {isRu ? String(action.label_ru || '') : String(action.label_en || '')}
                                            </span>
                                            {action.primary_metric ? (
                                              <span className="ml-1 rounded-full bg-emerald-400/20 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-50">
                                                {isRu ? 'главный KPI' : 'main KPI'}
                                              </span>
                                            ) : null}
                                            <span className="block text-slate-200">
                                              {isRu ? String(action.summary_ru || '') : String(action.summary_en || '')}
                                            </span>
                                          </span>
                                        </li>
                                      ))}
                                  </ol>
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          <div
                            data-testid="social-post-publish-to-learning-next-step"
                            className="mt-2 rounded-lg bg-white/10 px-2 py-2"
                          >
                            <div className="text-[11px] font-semibold text-white">
                              {isRu ? 'После публикации' : 'After publishing'}
                            </div>
                            <div className="mt-1 text-[11px] leading-4 text-slate-200">
                              {isRu
                                ? 'Следующий шаг в loop: собрать реакции, отметить заявки/обращения и пересчитать следующий контент-план. Изменения плана не применяются автоматически.'
                                : 'Next loop step: collect reactions, mark leads/inquiries, and recalculate the next content plan. Plan changes are not applied automatically.'}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 border-white/20 bg-white/10 px-2 text-[11px] text-white hover:bg-white/20"
                                onClick={() => { void collectSocialPostMetricsForBusiness(); }}
                                disabled={
                                  socialBusyAction === 'collect-metrics'
                                  || Number(socialDispatchExecutionReport.published || 0) <= 0
                                }
                              >
                                {socialBusyAction === 'collect-metrics'
                                  ? (isRu ? 'Собираем...' : 'Collecting...')
                                  : (isRu ? 'Собрать реакции' : 'Collect reactions')}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 border-white/20 bg-white/10 px-2 text-[11px] text-white hover:bg-white/20"
                                onClick={selectPublishedSocialPostsForResult}
                                disabled={visibleSocialPublishedPosts.length === 0}
                              >
                                {isRu ? 'Отметить заявки/обращения' : 'Record leads/inquiries'}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 border-white/20 bg-white/10 px-2 text-[11px] text-white hover:bg-white/20"
                                onClick={() => { void recommendNextSocialPlan(); }}
                                disabled={socialBusyAction === 'recommend'}
                              >
                                {socialBusyAction === 'recommend'
                                  ? (isRu ? 'Считаем...' : 'Calculating...')
                                  : (isRu ? 'Предложить изменения' : 'Suggest changes')}
                              </Button>
                            </div>
                          </div>
                          {Number(socialDispatchExecutionReport.details?.length || 0) > 0 ? (
                            <div className="mt-2 space-y-1">
                              {(socialDispatchExecutionReport.details || []).slice(0, 4).map((item) => (
                                <div
                                  key={`dispatch-report:${String(item.id || '')}:${String(item.platform || '')}`}
                                  className="rounded-lg bg-white/10 px-2 py-1.5 text-[11px] leading-4 text-slate-100"
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="font-medium text-white">
                                      {_socialPlatformLabel(String(item.platform || ''), isRu)}
                                    </span>
                                    <span>{String(item.status || '')}</span>
                                  </div>
                                  {item.provider_post_url || item.provider_post_id || item.automation_task_id || item.last_error ? (
                                    <div className="mt-0.5 break-all text-slate-200">
                                      {item.provider_post_url
                                        ? String(item.provider_post_url)
                                        : item.provider_post_id
                                          ? `provider id: ${String(item.provider_post_id)}`
                                          : item.automation_task_id
                                            ? `task: ${String(item.automation_task_id)}`
                                            : String(item.last_error || '')}
                                    </div>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      {socialDispatchPreview ? (
                        <div
                          data-testid="social-dispatch-preview-panel"
                          className="rounded-xl bg-white/10 px-3 py-2 text-xs leading-5 text-slate-200"
                        >
                          <div className="font-semibold text-white">
                            {isRu ? 'Проверка исполнителя' : 'Worker dry-run'}
                          </div>
                          <div>
                            {isRu
                              ? `К дате: ${Number(socialDispatchPreview.picked || 0)} · API: ${Number(socialDispatchPreview.by_action?.publish_api || 0)} · контролируемо: ${Number(socialDispatchPreview.by_action?.create_supervised_task || 0)} · вручную: ${Number(socialDispatchPreview.by_action?.manual_handoff || 0)}`
                              : `Due: ${Number(socialDispatchPreview.picked || 0)} · API: ${Number(socialDispatchPreview.by_action?.publish_api || 0)} · supervised: ${Number(socialDispatchPreview.by_action?.create_supervised_task || 0)} · manual: ${Number(socialDispatchPreview.by_action?.manual_handoff || 0)}`}
                          </div>
                          <div className="text-[11px] text-slate-300">
                            {isRu ? 'Внешняя публикация не запускалась.' : 'No external publishing was started.'}
                          </div>
                          <div className="text-[11px] text-slate-300">
                            {socialDispatchPreview.business_scope
                              ? (isRu
                                ? `Проверка ограничена бизнесом: ${String(socialDispatchPreview.business_scope)}`
                                : `Dry-run scoped to business: ${String(socialDispatchPreview.business_scope)}`)
                              : (isRu ? 'Проверка без ограничения по бизнесу.' : 'Dry-run is not business-scoped.')}
                          </div>
                          {socialDispatchPreview.readiness?.message_ru || socialDispatchPreview.readiness?.message_en ? (
                            <div
                              className={[
                                'mt-2 rounded-lg border px-2 py-1.5 text-[11px] leading-5',
                                socialDispatchPreview.readiness?.has_external_publish
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-100'
                                  : socialDispatchPreview.readiness?.has_manual_fallback
                                    ? 'border-amber-300/20 bg-amber-400/10 text-amber-100'
                                    : 'border-slate-300/20 bg-white/10 text-slate-200',
                              ].join(' ')}
                            >
                              <div className="font-semibold">
                                {isRu ? 'Вывод перед запуском' : 'Dispatch readiness'}
                              </div>
                              <div>
                                {isRu
                                  ? String(socialDispatchPreview.readiness?.message_ru || '')
                                  : String(socialDispatchPreview.readiness?.message_en || '')}
                              </div>
                              {socialDispatchPreview.readiness?.next_action_ru || socialDispatchPreview.readiness?.next_action_en ? (
                                <div className="mt-1 font-medium text-white">
                                  {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                  {isRu
                                    ? String(socialDispatchPreview.readiness?.next_action_ru || '')
                                    : String(socialDispatchPreview.readiness?.next_action_en || '')}
                                </div>
                              ) : null}
                              <div className="mt-1 text-slate-300">
                                {isRu
                                  ? `API ${Number(socialDispatchPreview.readiness?.external_publish_count || 0)} · контролируемо ${Number(socialDispatchPreview.readiness?.controlled_count || 0)} · вручную ${Number(socialDispatchPreview.readiness?.manual_count || 0)}`
                                  : `external ${Number(socialDispatchPreview.readiness?.external_publish_count || 0)} · supervised ${Number(socialDispatchPreview.readiness?.controlled_count || 0)} · manual ${Number(socialDispatchPreview.readiness?.manual_count || 0)}`}
                              </div>
                            </div>
                          ) : null}
                          {socialDispatchPreview.readiness?.first_api_proof_candidate ? (
                            <div
                              data-testid="social-first-api-proof-candidate"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialDispatchPreview.readiness.first_api_proof_candidate.ready
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50'
                                  : 'border-slate-300/20 bg-white/10 text-slate-200',
                              ].join(' ')}
                            >
                              <div className="font-semibold text-white">
                                {isRu ? 'Кандидат на первый API-proof' : 'First API-proof candidate'}
                              </div>
                              <div>
                                {socialDispatchPreview.readiness.first_api_proof_candidate.ready
                                  ? (isRu
                                    ? `${String(socialDispatchPreview.readiness.first_api_proof_candidate.platform_label || '')}: после worker должен появиться provider_post_id/provider_post_url.`
                                    : `${String(socialDispatchPreview.readiness.first_api_proof_candidate.platform_label || '')}: after the worker runs, provider_post_id/provider_post_url must appear.`)
                                  : (isRu
                                    ? 'Нет due API-поста для доказательства loop.'
                                    : 'No due API post is available to prove the loop.')}
                              </div>
                              <div className="mt-1 text-slate-100">
                                {isRu
                                  ? String(socialDispatchPreview.readiness.first_api_proof_candidate.proof_check_ru || '')
                                  : String(socialDispatchPreview.readiness.first_api_proof_candidate.proof_check_en || '')}
                              </div>
                              <div className="mt-1 text-slate-100">
                                {isRu
                                  ? String(socialDispatchPreview.readiness.first_api_proof_candidate.metrics_followup_ru || '')
                                  : String(socialDispatchPreview.readiness.first_api_proof_candidate.metrics_followup_en || '')}
                              </div>
                            </div>
                          ) : null}
                          {_socialFirstCycleVerificationBlock(socialDispatchPreview.readiness?.first_cycle_verification, isRu)}
                          {Number(socialDispatchPreview.readiness?.first_cycle_steps?.length || 0) > 0 ? (
                            <div className="mt-2 rounded-lg border border-sky-300/20 bg-sky-400/10 px-2 py-2 text-[11px] leading-5 text-sky-50">
                              <div className="font-semibold text-white">
                                {isRu ? 'Что сделает первый цикл' : 'What the first cycle will do'}
                              </div>
                              <div className="mt-1 space-y-1.5">
                                {(socialDispatchPreview.readiness?.first_cycle_steps || []).map((step) => (
                                  <div key={String(step.key || step.label_ru || step.label_en)} className="rounded-md bg-white/10 px-2 py-1.5">
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="font-medium text-white">
                                        {isRu ? String(step.label_ru || '') : String(step.label_en || '')}
                                      </span>
                                      <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white">
                                        {Number(step.count || 0)}
                                      </span>
                                    </div>
                                    <div className="mt-0.5 text-sky-100">
                                      {isRu ? String(step.description_ru || '') : String(step.description_en || '')}
                                    </div>
                                    <div className="mt-0.5 text-sky-200">
                                      {isRu ? 'Ожидаемый статус: ' : 'Expected status: '}
                                      {isRu ? String(step.expected_status_ru || '') : String(step.expected_status_en || '')}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                          {Number((isRu ? socialDispatchPreview.readiness?.safety_notes_ru : socialDispatchPreview.readiness?.safety_notes_en)?.length || 0) > 0 ? (
                            <div className="mt-2 rounded-lg bg-white/10 px-2 py-1.5 text-[11px] leading-5 text-slate-200">
                              <div className="font-semibold text-white">
                                {isRu ? 'Границы безопасности' : 'Safety boundaries'}
                              </div>
                              {((isRu ? socialDispatchPreview.readiness?.safety_notes_ru : socialDispatchPreview.readiness?.safety_notes_en) || []).map((note) => (
                                <div key={String(note)}>{String(note)}</div>
                              ))}
                            </div>
                          ) : null}
                          {Number(socialDispatchPreview.items?.length || 0) > 0 ? (
                            <div className="mt-2 space-y-1">
                              {(socialDispatchPreview.items || []).slice(0, 5).map((item) => (
                                <div key={String(item.id || `${item.platform}-${item.dispatch_action}`)} className="rounded-lg bg-white/10 px-2 py-1.5">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="truncate font-medium text-white">
                                      {String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu))}
                                    </span>
                                    <span className="shrink-0 text-[11px] text-slate-200">
                                      {isRu
                                        ? String(item.action_label_ru || _socialDispatchActionLabel(String(item.dispatch_action || ''), isRu))
                                        : String(item.action_label_en || _socialDispatchActionLabel(String(item.dispatch_action || ''), false))}
                                    </span>
                                  </div>
                                  {item.would_status ? (
                                    <div className="mt-0.5 text-[11px] font-medium text-slate-200">
                                      {isRu ? 'Итог: ' : 'Result: '}
                                      {String(item.would_status || '')}
                                    </div>
                                  ) : null}
                                  {item.reason ? (
                                    <div className="mt-0.5 line-clamp-2 text-[11px] text-slate-300">
                                      {isRu
                                        ? String(item.reason_label_ru || _socialDispatchReasonLabel(String(item.reason || ''), isRu))
                                        : String(item.reason_label_en || _socialDispatchReasonLabel(String(item.reason || ''), false))}
                                    </div>
                                  ) : null}
                                  {item.safety_summary_ru || item.safety_summary_en ? (
                                    <div className="mt-1 rounded-md bg-black/10 px-2 py-1 text-[11px] leading-4 text-slate-200">
                                      {isRu ? String(item.safety_summary_ru || '') : String(item.safety_summary_en || '')}
                                    </div>
                                  ) : null}
                                </div>
                              ))}
                              {Number(socialDispatchPreview.items?.length || 0) > 5 ? (
                                <div className="text-[11px] text-slate-300">
                                  {isRu
                                    ? `Ещё ${Number(socialDispatchPreview.items?.length || 0) - 5} в этом dry-run.`
                                    : `${Number(socialDispatchPreview.items?.length || 0) - 5} more in this dry-run.`}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
    </>
  );
};
