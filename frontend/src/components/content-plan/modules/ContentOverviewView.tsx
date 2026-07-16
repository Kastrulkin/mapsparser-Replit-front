import React from 'react';
import { Button } from '@/components/ui/button';
import { Sparkles } from 'lucide-react';
import { SocialLaunchChecklist, SocialOwnerLaunchPath, _socialPlatformLabel, _socialSettingsPathForPlatform, _socialPublishModeLabel } from './helpers';

export const ContentOverviewView = ({ scope }) => {
  const {
    navigate, isRu, currentPlan, loading, bulkBusyAction, showLearningDetails, setShowLearningDetails, socialGoalProgress,
    socialFirstApiProofDossier, socialPostsLoading, socialBusyAction, activeZone, setActiveZone, readiness, socialLearningLoopStatus, socialPlanNextStep,
    socialReadinessSummary, socialOverviewChannelHighlights, socialReadinessSetupPath, socialFirstApiPublishReadiness, socialFirstApiBlockerCard, socialLaunchStages, socialLaunchChecklistSummary, planOperationalSummary,
    overviewRiskScore, operatorQualityInsights, checkOpenClawBrowserReadiness, collectSocialPostMetricsForBusiness, previewSocialDispatch, recommendNextSocialPlan, applyViewPreset, runSocialPlanNextStep
  } = scope;
  return (
    <>
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
                      ? (isRu ? 'Готовые тексты можно разложить по каналам' : 'Ready drafts can become channel posts')
                      : (isRu ? 'План выглядит спокойно' : 'The plan looks calm'))
                  : (isRu ? 'Соберите первый план публикаций' : 'Build the first content plan')}
              </div>
            <div className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              {isRu
                ? 'Здесь короткая сводка: сколько тем уже есть, сколько текстов готово, сколько ещё надо дописать и что делать следующим шагом.'
                : 'A short summary: how many topics exist, how many drafts are ready, how many still need text, and the next step.'}
            </div>
            </div>
            {!currentPlan?.items?.length ? (
              <Button onClick={() => setActiveZone('plan')} disabled={loading}>
                <Sparkles className="mr-2 h-4 w-4" />
                {isRu ? 'Перейти к плану' : 'Go to plan'}
              </Button>
            ) : planOperationalSummary.needsDraft > 0 ? (
              <Button onClick={() => { applyViewPreset('urgent'); setActiveZone('queue'); }}>
                {isRu ? 'Открыть темы без текста' : 'Open empty topics'}
              </Button>
            ) : planOperationalSummary.readyToPublish > 0 ? (
              <Button onClick={() => { applyViewPreset('ready'); setActiveZone('queue'); }}>
                {isRu ? 'Открыть готовые тексты' : 'Open ready drafts'}
              </Button>
            ) : (
              <Button onClick={() => setActiveZone('plan')}>
                {isRu ? 'Собрать новый план' : 'Build a new plan'}
              </Button>
            )}
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-5">
            <div className="rounded-2xl bg-blue-50 px-4 py-4">
              <div className="text-2xl font-semibold text-blue-950">{planOperationalSummary.total}</div>
              <div className="mt-1 text-sm text-blue-800">{isRu ? 'Всего тем' : 'Plan topics'}</div>
            </div>
            <div className="rounded-2xl bg-emerald-50 px-4 py-4">
              <div className="text-2xl font-semibold text-emerald-950">{planOperationalSummary.readyToPublish}</div>
              <div className="mt-1 text-sm text-emerald-800">{isRu ? 'Текст готов' : 'Draft ready'}</div>
            </div>
            <div className="rounded-2xl bg-amber-50 px-4 py-4">
              <div className="text-2xl font-semibold text-amber-950">{planOperationalSummary.needsDraft}</div>
              <div className="mt-1 text-sm text-amber-800">{isRu ? 'Без текста' : 'No text'}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-4">
              <div className="text-2xl font-semibold text-slate-950">{planOperationalSummary.published}</div>
              <div className="mt-1 text-sm text-slate-600">{isRu ? 'Новости созданы' : 'News created'}</div>
            </div>
            <div className="rounded-2xl bg-rose-50 px-4 py-4">
              <div className="text-2xl font-semibold text-rose-950">{Number(overviewRiskScore || 0).toFixed(0)}</div>
              <div className="mt-1 text-sm text-rose-800">{isRu ? 'Риск / слабые точки' : 'Risk / weak spots'}</div>
            </div>
          </div>

          <div
            data-testid="social-owner-simple-goal"
            className="mt-5 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-4"
          >
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-blue-700">
                  {isRu ? 'Цель сейчас' : 'Current goal'}
                </div>
                <div className="mt-1 text-lg font-semibold text-blue-950">
                  {isRu
                    ? 'Довести тему до публикации и результата'
                    : 'Move a topic to publishing and results'}
                </div>
                <div className="mt-1 max-w-3xl text-sm leading-6 text-blue-900">
                  {isRu
                    ? 'Простой путь: подготовить посты из контент-плана, проверить тексты, подтвердить, поставить в расписание, закрыть Яндекс/2ГИС контролируемо и отметить заявки.'
                    : 'Simple path: prepare posts from the content plan, review copy, approve, queue, finish Yandex/2GIS supervised placement, and record leads.'}
                </div>
              </div>
              <Button
                type="button"
                onClick={runSocialPlanNextStep}
                disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || Boolean(socialPlanNextStep.disabled)}
                className="shrink-0 bg-blue-700 text-white hover:bg-blue-800"
              >
                {Boolean(bulkBusyAction) || Boolean(socialBusyAction)
                  ? (isRu ? 'Выполняем...' : 'Working...')
                  : (isRu ? socialPlanNextStep.ctaRu : socialPlanNextStep.ctaEn)}
              </Button>
            </div>
            <div className="mt-3 grid gap-2 text-sm leading-6 md:grid-cols-3">
              <div className="rounded-xl bg-white px-3 py-3 text-blue-900">
                <div className="font-semibold text-blue-950">
                  {isRu ? '1. Что делать первым' : '1. First action'}
                </div>
                <div className="mt-1">
                  {isRu ? socialPlanNextStep.descriptionRu : socialPlanNextStep.descriptionEn}
                </div>
              </div>
              <div className="rounded-xl bg-white px-3 py-3 text-blue-900">
                <div className="font-semibold text-blue-950">
                  {isRu ? '2. Что не произойдёт само' : '2. What will not happen silently'}
                </div>
                <div className="mt-1">
                  {isRu
                    ? 'Наружу ничего не уйдёт без предпросмотра, подтверждения и расписания. Финальный клик в Яндекс/2ГИС остаётся за человеком.'
                    : 'Nothing goes external without preview, approval, and queueing. The final Yandex/2GIS click stays human-controlled.'}
                </div>
              </div>
              <div className="rounded-xl bg-white px-3 py-3 text-blue-900">
                <div className="font-semibold text-blue-950">
                  {isRu ? '3. Как понять успех' : '3. Success signal'}
                </div>
                <div className="mt-1">
                  {isRu
                    ? 'Есть опубликованные посты, закрытые ручные задачи и отмеченные заявки/обращения. После этого LocalOS предлагает изменения следующего плана.'
                    : 'Posts are published, manual tasks are closed, and leads/inquiries are recorded. Then LocalOS suggests next-plan changes.'}
                </div>
              </div>
            </div>
            {socialLaunchStages.length > 0 ? (
              <div
                data-testid="social-owner-goal-progress"
                className="mt-3 rounded-xl border border-blue-100 bg-white px-3 py-3 text-sm leading-6 text-blue-900"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="font-semibold text-blue-950">
                      {isRu ? 'Где мы сейчас' : 'Where we are now'}
                    </div>
                    <div className="mt-1">
                      {String(
                        (isRu ? socialGoalProgress?.summary?.current_label_ru : socialGoalProgress?.summary?.current_label_en)
                        || (socialLaunchChecklistSummary.current
                          ? (isRu ? socialLaunchChecklistSummary.current.labelRu : socialLaunchChecklistSummary.current.labelEn)
                          : (isRu ? 'Следующий шаг' : 'Next step'))
                      )}
                      {' · '}
                      {String(
                        (isRu ? socialGoalProgress?.next_action_ru : socialGoalProgress?.next_action_en)
                        || (socialLaunchChecklistSummary.current
                          ? (isRu
                            ? socialLaunchChecklistSummary.current.detailRu
                            : socialLaunchChecklistSummary.current.detailEn)
                          : (isRu
                            ? 'Откройте очередь публикаций и подготовьте первый канал.'
                            : 'Open the publishing queue and prepare the first channel.'))
                      )}
                    </div>
                  </div>
                  <div className="grid gap-2 text-xs sm:grid-cols-3 lg:min-w-[420px]">
                    <div className="rounded-lg bg-blue-50 px-2 py-1.5">
                      <div className="font-semibold text-blue-950">
                        {Number(socialLaunchChecklistSummary.done || 0)}
                        /
                        {Number(socialLaunchChecklistSummary.total || socialLaunchStages.length || 0)}
                      </div>
                      <div>{isRu ? 'этапов готово' : 'steps done'}</div>
                    </div>
                    <div className="rounded-lg bg-amber-50 px-2 py-1.5 text-amber-800">
                      <div className="font-semibold text-amber-950">
                        {Math.max(0, Number(socialLaunchChecklistSummary.attention || 0))}
                      </div>
                      <div>{isRu ? 'требует внимания' : 'need attention'}</div>
                    </div>
                    <div className="rounded-lg bg-emerald-50 px-2 py-1.5 text-emerald-800">
                      <div className="font-semibold text-emerald-950">
                        {Math.max(
                          0,
                          Number(socialLaunchChecklistSummary.total || socialLaunchStages.length || 0)
                            - Number(socialLaunchChecklistSummary.done || 0),
                        )}
                      </div>
                      <div>{isRu ? 'осталось до loop' : 'left to loop'}</div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div
            data-testid="social-quick-launch"
            className="mt-5 rounded-2xl border border-slate-900 bg-slate-950 px-4 py-4 text-white"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  {isRu ? 'Быстрый запуск публикаций' : 'Quick publishing launch'}
                </div>
                <div className="mt-2 text-lg font-semibold">
                  {isRu ? socialPlanNextStep.titleRu : socialPlanNextStep.titleEn}
                </div>
                <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                  {isRu ? socialPlanNextStep.descriptionRu : socialPlanNextStep.descriptionEn}
                </div>
                <SocialOwnerLaunchPath
                  isRu={isRu}
                  currentAction={socialPlanNextStep.action}
                />
                <div className="mt-3 grid gap-2 text-xs text-slate-300 sm:grid-cols-3">
                  <div className="rounded-xl bg-white/10 px-3 py-2">
                    <div className="text-base font-semibold text-white">{socialReadinessSummary.apiReady}</div>
                    <div>{isRu ? 'API-каналы готовы' : 'API channels ready'}</div>
                  </div>
                  <div className="rounded-xl bg-white/10 px-3 py-2">
                    <div className="text-base font-semibold text-white">{socialReadinessSummary.supervisedOrManual}</div>
                    <div>{isRu ? 'Яндекс/2ГИС под контролем' : 'Yandex/2GIS supervised'}</div>
                  </div>
                  <div className="rounded-xl bg-white/10 px-3 py-2">
                    <div className="text-base font-semibold text-white">{socialReadinessSummary.needsAttention}</div>
                    <div>{isRu ? 'нужны ключи или права' : 'need keys or rights'}</div>
                  </div>
                </div>
                <div
                  data-testid="social-overview-first-api-readiness"
                  className={[
                    'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                    socialFirstApiPublishReadiness.hasAnyReadyApi
                      ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-50'
                      : 'border-amber-300/30 bg-amber-400/10 text-amber-50',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="font-semibold text-white">
                        {isRu ? 'Первый API-пост' : 'First API post'}
                        {' · '}
                        {socialFirstApiPublishReadiness.hasAnyReadyApi
                          ? (isRu ? 'есть готовый канал' : 'ready channel exists')
                          : (isRu ? 'нужны ключи' : 'needs keys')}
                      </div>
                      <div className="mt-1 text-slate-200">
                        {socialFirstApiPublishReadiness.hasAnyReadyApi
                          ? (isRu
                            ? `Можно начинать с API-каналов: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`
                            : `You can start with API channels: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`)
                          : (isRu
                            ? 'Пока нет готового API-канала: подключите Telegram или VK, чтобы первый пост вышел по расписанию.'
                            : 'No API channel is ready yet: connect Telegram or VK so the first post can publish on schedule.')}
                      </div>
                      <div className="mt-1 text-slate-300">
                        {isRu
                          ? 'Наружу только после предпросмотра, подтверждения, расписания и даты публикации.'
                          : 'External publishing happens only after preview, human approval, queueing, and the due date.'}
                      </div>
                      <div
                        data-testid="social-overview-fast-api-start"
                        className="mt-2 rounded-lg bg-white/10 px-2.5 py-2 text-slate-100"
                      >
                        <div className="font-semibold text-white">
                          {isRu ? 'Быстрый API старт: Telegram/VK' : 'Fast API start: Telegram/VK'}
                        </div>
                        <div className="mt-1">
                          {socialFirstApiPublishReadiness.fastStartReadyLabels.length > 0
                            ? (isRu
                              ? `Начните proof с ${socialFirstApiPublishReadiness.fastStartReadyLabels.join(', ')}; это самый короткий путь до первого опубликованного API-поста.`
                              : `Start the proof with ${socialFirstApiPublishReadiness.fastStartReadyLabels.join(', ')}; this is the shortest path to the first published API post.`)
                            : socialFirstApiPublishReadiness.fastStartBlockedLabels.length > 0
                              ? (isRu
                                ? `Сначала подключите ${socialFirstApiPublishReadiness.fastStartBlockedLabels.join(', ')}: это быстрее, чем ждать Meta/Google permissions.`
                                : `Connect ${socialFirstApiPublishReadiness.fastStartBlockedLabels.join(', ')} first: this is faster than waiting for Meta/Google permissions.`)
                              : (isRu
                                ? 'Если Telegram/VK не выбраны в плане, первый API-proof можно начать с готового канала, но Telegram/VK остаются самым быстрым MVP-путём.'
                                : 'If Telegram/VK are not selected for the plan, start the first API proof with any ready channel, while Telegram/VK remain the fastest MVP path.')}
                        </div>
                        <div className="mt-1 text-slate-300">
                          {isRu
                            ? 'Безопасный порядок: проверить API-канал без публикации → открыть preview → утвердить человеком → поставить в расписание.'
                            : 'Safe order: check the API channel without publishing → open preview → human approval → queue it.'}
                        </div>
                      </div>
                      {socialFirstApiPublishReadiness.setupFocus?.target_setup?.schema ? (
                        <div
                          data-testid={`social-overview-channel-target-setup-${String(socialFirstApiPublishReadiness.setupFocus.platform || '')}`}
                          data-schema={String(socialFirstApiPublishReadiness.setupFocus.target_setup.schema || 'localos_social_channel_target_setup_v1')}
                          className="mt-2 rounded-lg border border-white/10 bg-white/10 px-2.5 py-2 text-slate-100"
                        >
                          <div className="font-semibold text-white">
                            {isRu
                              ? String(socialFirstApiPublishReadiness.setupFocus.target_setup.target_label_ru || 'Цель публикации')
                              : String(socialFirstApiPublishReadiness.setupFocus.target_setup.target_label_en || 'Publish target')}
                          </div>
                          {socialFirstApiPublishReadiness.setupFocus.target_setup.owner_telegram_present ? (
                            <div
                              data-testid="social-overview-owner-telegram-linked"
                              className="mt-1 inline-flex rounded-full bg-sky-400/20 px-2 py-0.5 text-[11px] font-semibold text-sky-50"
                            >
                              {isRu ? 'Владелец подключён в Telegram' : 'Owner Telegram is linked'}
                            </div>
                          ) : null}
                          {socialFirstApiPublishReadiness.setupFocus.target_setup.telegram_app_present ? (
                            <div
                              data-testid="social-overview-telegram-app-linked"
                              className="ml-1 mt-1 inline-flex rounded-full bg-violet-400/20 px-2 py-0.5 text-[11px] font-semibold text-violet-50"
                            >
                              {isRu ? 'Telegram app подключён' : 'Telegram app linked'}
                            </div>
                          ) : null}
                          <div className="mt-1">
                            {isRu
                              ? String(socialFirstApiPublishReadiness.setupFocus.target_setup.summary_ru || '')
                              : String(socialFirstApiPublishReadiness.setupFocus.target_setup.summary_en || '')}
                          </div>
                          <div className="mt-1 text-slate-300">
                            {isRu
                              ? String(socialFirstApiPublishReadiness.setupFocus.target_setup.not_a_target_ru || '')
                              : String(socialFirstApiPublishReadiness.setupFocus.target_setup.not_a_target_en || '')}
                          </div>
                          <div className="mt-1 font-medium text-white">
                            {isRu
                              ? String(socialFirstApiPublishReadiness.setupFocus.target_setup.proof_ru || '')
                              : String(socialFirstApiPublishReadiness.setupFocus.target_setup.proof_en || '')}
                          </div>
                        </div>
                      ) : null}
                      {socialFirstApiPublishReadiness.blockedLabels.length > 0 ? (
                        <div className="mt-1 text-amber-100">
                          <span className="font-semibold">{isRu ? 'Сначала исправить: ' : 'Fix first: '}</span>
                          {socialFirstApiPublishReadiness.blockedLabels.slice(0, 3).join(', ')}
                        </div>
                      ) : null}
                    </div>
                    {socialFirstApiPublishReadiness.firstBlocked ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(_socialSettingsPathForPlatform(String(socialFirstApiPublishReadiness.firstBlocked?.platform || '')))}
                        className="h-8 shrink-0 border-white/20 bg-white/10 px-3 text-xs text-white hover:bg-white/20 hover:text-white"
                      >
                        {isRu ? 'Открыть настройку' : 'Open setup'}
                      </Button>
                    ) : null}
                  </div>
                </div>
                <div
                  data-testid="social-first-api-blocker-card"
                  className={[
                    'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                    socialFirstApiBlockerCard.tone === 'success'
                      ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-50'
                      : socialFirstApiBlockerCard.tone === 'warning'
                        ? 'border-amber-300/30 bg-amber-400/10 text-amber-50'
                        : 'border-sky-300/30 bg-sky-400/10 text-sky-50',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="font-semibold text-white">
                        {isRu ? socialFirstApiBlockerCard.titleRu : socialFirstApiBlockerCard.titleEn}
                      </div>
                      <ul className="mt-2 space-y-1 text-slate-100">
                        {(isRu ? socialFirstApiBlockerCard.factsRu : socialFirstApiBlockerCard.factsEn).map((line) => (
                          <li key={`first-api-blocker-fact:${line}`} className="flex gap-1.5">
                            <span className="font-semibold text-white">•</span>
                            <span>{line}</span>
                          </li>
                        ))}
                      </ul>
                      <div className="mt-2 font-medium text-white">
                        {isRu ? 'Следующий безопасный шаг: ' : 'Next safe step: '}
                        {isRu ? socialFirstApiBlockerCard.nextRu : socialFirstApiBlockerCard.nextEn}
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={socialFirstApiBlockerCard.status === 'prepare' && socialPostsLoading}
                      onClick={() => {
                        if (socialFirstApiBlockerCard.status === 'connect') {
                          navigate(_socialSettingsPathForPlatform(socialFirstApiBlockerCard.firstBlockedPlatform || 'telegram'));
                          return;
                        }
                        runSocialPlanNextStep();
                      }}
                      className="h-8 shrink-0 border-white/20 bg-white/10 px-3 text-xs text-white hover:bg-white/20 hover:text-white"
                    >
                      {isRu ? socialFirstApiBlockerCard.ctaRu : socialFirstApiBlockerCard.ctaEn}
                    </Button>
                  </div>
                </div>
                <div
                  data-testid="social-owner-publishing-path"
                  className="mt-3 rounded-xl border border-white/10 bg-white/10 px-3 py-3"
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                        {isRu ? 'Маршрут поста' : 'Post path'}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-white">
                        {isRu
                          ? 'Подготовить, проверить, подтвердить и только потом исполнить'
                          : 'Prepare, review, approve, then execute'}
                      </div>
                    </div>
                    <div className="rounded-lg bg-white/10 px-2 py-1.5 text-xs font-semibold text-emerald-100">
                      {isRu ? 'Финальный клик на картах — за человеком' : 'Map final click stays human'}
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {[
                      {
                        labelRu: '1. Подготовить каналы',
                        labelEn: '1. Prepare channels',
                        detailRu: 'Из темы создаются тексты для карт и соцсетей.',
                        detailEn: 'A plan topic becomes map and social drafts.',
                      },
                      {
                        labelRu: '2. Проверить тексты',
                        labelEn: '2. Review drafts',
                        detailRu: 'Предпросмотр показывает канал, текст, дату и ограничения.',
                        detailEn: 'Preview shows channel, copy, date, and limits.',
                      },
                      {
                        labelRu: '3. Подтвердить',
                        labelEn: '3. Approve',
                        detailRu: 'Подтверждение фиксирует согласие, но ещё ничего не публикует.',
                        detailEn: 'Approval records consent and still publishes nothing.',
                      },
                      {
                        labelRu: '4. Поставить в расписание',
                        labelEn: '4. Queue on schedule',
                        detailRu: 'Исполнитель возьмёт только подтверждённые API-посты, когда наступит дата.',
                        detailEn: 'The worker can execute only approved due API posts.',
                      },
                      {
                        labelRu: '5. Контролируемое размещение',
                        labelEn: '5. Supervised placement',
                        detailRu: 'Яндекс/2ГИС получают задачу с предпросмотром, без тихого автоклика.',
                        detailEn: 'Yandex/2GIS get a preview task, without hidden auto-clicks.',
                      },
                      {
                        labelRu: '6. Сбор реакций и заявок',
                        labelEn: '6. Collect results',
                        detailRu: 'Главный сигнал для следующего плана — заявки и обращения.',
                        detailEn: 'Leads and inquiries are the main signal for the next plan.',
                      },
                    ].map((step) => (
                      <div
                        key={isRu ? step.labelRu : step.labelEn}
                        className="rounded-lg bg-slate-950/50 px-3 py-2 text-xs leading-5 text-slate-300"
                      >
                        <div className="font-semibold text-white">{isRu ? step.labelRu : step.labelEn}</div>
                        <div className="mt-1">{isRu ? step.detailRu : step.detailEn}</div>
                      </div>
                    ))}
                  </div>
                </div>
                {socialFirstApiProofDossier ? (
                  <div
                    data-testid="social-first-api-proof-dossier"
                    data-schema="localos_social_first_api_proof_dossier_v1"
                    className={[
                      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                      socialFirstApiProofDossier.ready
                        ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-50'
                        : 'border-sky-300/30 bg-sky-400/10 text-sky-50',
                    ].join(' ')}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="font-semibold text-white">
                          {isRu ? socialFirstApiProofDossier.title_ru : socialFirstApiProofDossier.title_en}
                        </div>
                        <div className="mt-1 text-slate-200">
                          {isRu ? socialFirstApiProofDossier.summary_ru : socialFirstApiProofDossier.summary_en}
                        </div>
                      </div>
                      <div className="rounded-lg bg-white/10 px-2 py-1.5 text-[11px] font-semibold text-white">
                        {isRu ? socialFirstApiProofDossier.primary_metric_ru : socialFirstApiProofDossier.primary_metric_en}
                      </div>
                    </div>
                    <div className="mt-2 rounded-lg bg-white/10 px-2 py-2">
                      <div className="font-semibold text-white">
                        {isRu ? 'Следующий шаг: ' : 'Next step: '}
                        {isRu ? socialFirstApiProofDossier.next_action_ru : socialFirstApiProofDossier.next_action_en}
                      </div>
                      {(
                        isRu
                          ? socialFirstApiProofDossier.steps_ru
                          : socialFirstApiProofDossier.steps_en
                      )?.length ? (
                        <ol className="mt-2 space-y-1">
                          {(
                            isRu
                              ? socialFirstApiProofDossier.steps_ru
                              : socialFirstApiProofDossier.steps_en
                          )?.slice(0, 3).map((step, index) => (
                            <li key={`first-api-proof-dossier-step:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                              <span className="font-semibold text-white">{index + 1}.</span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ol>
                      ) : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-slate-100">
                        {isRu ? 'подтверждение обязательно' : 'approval required'}
                      </span>
                      <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-slate-100">
                        {isRu ? 'публикация только по расписанию' : 'publish only through queue/due'}
                      </span>
                      <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-slate-100">
                        {isRu ? 'карты без финального автоклика' : 'maps without final auto-click'}
                      </span>
                    </div>
                  </div>
                ) : null}
                <SocialLaunchChecklist
                  isRu={isRu}
                  stages={socialLaunchStages}
                  summary={socialLaunchChecklistSummary}
                />
                <div
                  data-testid="social-overview-learning-loop-status"
                  className={[
                    'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                    socialLearningLoopStatus.tone === 'success'
                      ? 'border-emerald-300/40 bg-emerald-400/10 text-emerald-50'
                      : socialLearningLoopStatus.tone === 'warning'
                        ? 'border-amber-300/40 bg-amber-400/10 text-amber-50'
                        : socialLearningLoopStatus.tone === 'caution'
                          ? 'border-sky-300/40 bg-sky-400/10 text-sky-50'
                          : 'border-white/10 bg-white/10 text-slate-200',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="font-semibold text-white">
                        {isRu ? 'Learning loop' : 'Learning loop'} · {isRu ? socialLearningLoopStatus.titleRu : socialLearningLoopStatus.titleEn}
                      </div>
                      <div className="mt-1 text-slate-200">
                        {isRu ? socialLearningLoopStatus.textRu : socialLearningLoopStatus.textEn}
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (socialLearningLoopStatus.action === 'collect') {
                          void collectSocialPostMetricsForBusiness();
                          return;
                        }
                        if (socialLearningLoopStatus.action === 'recommend') {
                          void recommendNextSocialPlan();
                          return;
                        }
                        setActiveZone('queue');
                      }}
                      disabled={
                        (socialLearningLoopStatus.action === 'collect' && socialBusyAction === 'collect-metrics')
                        || (socialLearningLoopStatus.action === 'recommend' && socialBusyAction === 'recommend')
                      }
                      data-testid="social-overview-learning-loop-action"
                      className="h-8 shrink-0 border-white/20 bg-white/10 px-3 text-xs text-white hover:bg-white/20 hover:text-white"
                    >
                      {socialLearningLoopStatus.action === 'collect' && socialBusyAction === 'collect-metrics'
                        ? (isRu ? 'Собираем...' : 'Collecting...')
                        : socialLearningLoopStatus.action === 'recommend' && socialBusyAction === 'recommend'
                          ? (isRu ? 'Считаем...' : 'Calculating...')
                          : (isRu ? socialLearningLoopStatus.ctaRu : socialLearningLoopStatus.ctaEn)}
                    </Button>
                  </div>
                </div>
                {socialOverviewChannelHighlights.length > 0 ? (
                  <div className="mt-3 rounded-xl bg-white/10 px-3 py-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                      {isRu ? 'Каналы: что сделать' : 'Channels: next actions'}
                    </div>
                    <div className="mt-2 grid gap-2 md:grid-cols-2">
                      {socialOverviewChannelHighlights.map((channel) => {
                        const mode = String(channel.publish_mode || '').trim();
                        const isControlled = mode === 'openclaw_browser' || mode === 'local_supervised_browser' || mode === 'manual';
                        const badge = channel.ready
                          ? (isRu ? 'готов' : 'ready')
                          : isControlled
                            ? (isRu ? 'контроль' : 'supervised')
                            : (isRu ? 'нужно внимание' : 'needs attention');
                        const line = String(
                          (isRu
                            ? channel.setup_summary_ru || channel.next_action_ru || channel.message_ru
                            : channel.setup_summary_en || channel.next_action_en || channel.message_en) || ''
                        ).trim();
                        return (
                          <div key={`overview-channel-${channel.platform}`} className="rounded-lg bg-white/10 px-3 py-2 text-xs leading-5 text-slate-200">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-semibold text-white">
                                {channel.platform_label || _socialPlatformLabel(channel.platform, isRu)}
                              </span>
                              <span className={channel.ready || isControlled ? 'text-sky-200' : 'text-amber-200'}>
                                {badge}
                              </span>
                            </div>
                            <div className="mt-1 line-clamp-2 text-slate-300">
                              {line || _socialPublishModeLabel(channel.publish_mode || '', isRu)}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {socialReadinessSummary.blockedApiChannels.length > 0 ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(socialReadinessSetupPath)}
                        className="mt-3 h-8 border-white/20 bg-white/10 px-3 text-xs text-white hover:bg-white/20 hover:text-white"
                      >
                        {isRu ? 'Открыть настройку канала' : 'Open channel setup'}
                      </Button>
                    ) : null}
                  </div>
                ) : null}
                <div className="mt-3 rounded-xl bg-white/10 px-3 py-2 text-xs leading-5 text-slate-200">
                  <div>
                    {isRu
                      ? 'Внешние публикации идут только после предпросмотра и подтверждения. Для Яндекс/2ГИС LocalOS готовит контролируемое размещение, а не скрытую автопубликацию.'
                      : 'External publishing runs only after preview and approval. For Yandex/2GIS, LocalOS prepares supervised placement, not hidden autopublish.'}
                  </div>
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="text-slate-300">
                      {isRu
                        ? 'Готовность OpenClaw для Яндекс/2ГИС проверяется отдельно: если внешний исполнитель недоступен, будет ручной режим без срыва плана.'
                        : 'OpenClaw readiness for Yandex/2GIS is checked separately: if the receiver is unreachable, LocalOS keeps manual fallback without blocking the plan.'}
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => { void checkOpenClawBrowserReadiness(); }}
                      disabled={socialBusyAction === 'openclaw-check'}
                      className="h-7 shrink-0 border-white/20 bg-white/10 px-2.5 text-[11px] text-white hover:bg-white/20 hover:text-white"
                    >
                      {socialBusyAction === 'openclaw-check'
                        ? (isRu ? 'Проверяем...' : 'Checking...')
                        : (isRu ? 'Проверить OpenClaw' : 'Check OpenClaw')}
                    </Button>
                  </div>
                </div>
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
                  onClick={() => setActiveZone('queue')}
                  className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                >
                  {isRu ? 'Открыть очередь и предпросмотр' : 'Open queue and preview'}
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
              </div>
            </div>
          </div>

          {socialLaunchStages.length > 0 ? (
            <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-950">
                    {isRu ? 'Цель публикаций' : 'Publishing goal'}
                  </div>
                  <div className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
                    {String(
                      (isRu ? socialGoalProgress?.goal_ru : socialGoalProgress?.goal_en)
                      || (isRu
                        ? 'Дойти от темы в контент-плане до публикации, результата и корректировки следующей недели. Карты идут через контролируемое или ручное размещение, API-каналы — только после подтверждения.'
                        : 'Move from a content-plan topic to publishing, results, and next-week correction. Maps stay supervised; API channels run only after approval.')
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-medium">
                    <span className="rounded-full bg-white px-2 py-0.5 text-slate-700">
                      {isRu ? 'Главный KPI: ' : 'Main KPI: '}
                      {String((isRu ? socialGoalProgress?.primary_metric_ru : socialGoalProgress?.primary_metric_en) || (isRu ? 'заявки и обращения' : 'leads and inquiries'))}
                    </span>
                    <span className="rounded-full bg-white px-2 py-0.5 text-slate-700">
                      {socialGoalProgress?.approval_required === false
                        ? (isRu ? 'подтверждение не требуется' : 'approval not required')
                        : (isRu ? 'подтверждение обязательно' : 'approval required')}
                    </span>
                    <span className="rounded-full bg-white px-2 py-0.5 text-slate-700">
                      {socialGoalProgress?.maps_are_supervised_or_manual === false
                        ? (isRu ? 'карты требуют проверки режима' : 'map mode needs review')
                        : (isRu ? 'Яндекс/2ГИС: контроль/вручную' : 'Yandex/2GIS: supervised/manual')}
                    </span>
                  </div>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start lg:max-w-[520px]">
                  <div
                    data-testid="social-goal-current-step"
                    className={[
                      'rounded-xl border bg-white px-3 py-2 text-xs leading-5',
                      socialLaunchChecklistSummary.attention > 0
                        ? 'border-red-100 text-red-800'
                        : socialLaunchChecklistSummary.current?.status === 'current'
                          ? 'border-sky-100 text-sky-800'
                          : 'border-slate-200 text-slate-600',
                    ].join(' ')}
                  >
                    <div className="font-semibold text-slate-950">
                      {isRu
                        ? `Этап ${Math.max(1, socialLaunchChecklistSummary.done + 1)} из ${socialLaunchChecklistSummary.total || socialLaunchStages.length}`
                        : `Step ${Math.max(1, socialLaunchChecklistSummary.done + 1)} of ${socialLaunchChecklistSummary.total || socialLaunchStages.length}`}
                    </div>
                    <div className="mt-0.5 font-medium">
                      {String(
                        (isRu ? socialGoalProgress?.summary?.current_label_ru : socialGoalProgress?.summary?.current_label_en)
                        || (socialLaunchChecklistSummary.current
                          ? (isRu ? socialLaunchChecklistSummary.current.labelRu : socialLaunchChecklistSummary.current.labelEn)
                          : (isRu ? 'Следующий шаг' : 'Next step'))
                      )}
                    </div>
                    <div className="mt-0.5">
                      {String(
                        (isRu ? socialGoalProgress?.next_action_ru : socialGoalProgress?.next_action_en)
                        || (socialLaunchChecklistSummary.current
                          ? (isRu
                            ? socialLaunchChecklistSummary.current.detailRu
                            : socialLaunchChecklistSummary.current.detailEn)
                          : (isRu
                            ? 'Откройте очередь публикаций и подготовьте первый канал.'
                            : 'Open the publishing queue and prepare the first channel.'))
                      )}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="bg-white"
                    onClick={() => setActiveZone('queue')}
                  >
                    {isRu ? 'Открыть очередь' : 'Open queue'}
                  </Button>
                </div>
              </div>
              <div
                data-testid="social-goal-remaining-work"
                className="mt-3 grid gap-2 text-xs leading-5 sm:grid-cols-3"
              >
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-600">
                  <div className="font-semibold text-slate-950">
                    {isRu ? '1. Подготовить и утвердить' : '1. Prepare and approve'}
                  </div>
                  <div className="mt-1">
                    {isRu
                      ? 'Посты появляются из контент-плана LocalOS, проходят предпросмотр и подтверждение.'
                      : 'Posts come from the LocalOS content plan, then pass preview and approval.'}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-600">
                  <div className="font-semibold text-slate-950">
                    {isRu ? '2. Исполнить безопасно' : '2. Execute safely'}
                  </div>
                  <div className="mt-1">
                    {isRu
                      ? 'API-каналы идут по расписанию; Яндекс/2ГИС остаются контролируемыми или ручными.'
                      : 'API channels run on schedule; Yandex/2GIS stay supervised or manual.'}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-600">
                  <div className="font-semibold text-slate-950">
                    {isRu ? '3. Улучшить следующий план' : '3. Improve the next plan'}
                  </div>
                  <div className="mt-1">
                    {isRu
                      ? 'Система ранжирует заявки и обращения выше охватов и ждёт подтверждения перед применением.'
                      : 'The system ranks leads and inquiries above reach and waits for confirmation before applying changes.'}
                  </div>
                </div>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {socialLaunchStages.map((stage) => (
                  <div
                    key={`overview-${stage.key}`}
                    className={[
                      'rounded-xl border bg-white px-3 py-3',
                      stage.status === 'done'
                        ? 'border-emerald-100'
                        : stage.status === 'current'
                          ? 'border-sky-200'
                          : stage.status === 'attention'
                            ? 'border-red-200'
                            : 'border-slate-200',
                    ].join(' ')}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div
                        className={[
                          'text-xs font-semibold',
                          stage.status === 'done'
                            ? 'text-emerald-800'
                            : stage.status === 'current'
                              ? 'text-sky-800'
                              : stage.status === 'attention'
                                ? 'text-red-800'
                                : 'text-slate-600',
                        ].join(' ')}
                      >
                        {isRu ? stage.labelRu : stage.labelEn}
                      </div>
                      <span
                        className={[
                          'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold',
                          stage.status === 'done'
                            ? 'bg-emerald-50 text-emerald-700'
                            : stage.status === 'current'
                              ? 'bg-sky-50 text-sky-700'
                              : stage.status === 'attention'
                                ? 'bg-red-50 text-red-700'
                                : 'bg-slate-100 text-slate-500',
                        ].join(' ')}
                      >
                        {stage.status === 'done'
                          ? (isRu ? 'готово' : 'done')
                          : stage.status === 'current'
                            ? (isRu ? 'сейчас' : 'now')
                            : stage.status === 'attention'
                              ? (isRu ? 'внимание' : 'attention')
                              : (isRu ? 'позже' : 'later')}
                      </span>
                    </div>
                    <div className="mt-1 text-xs leading-5 text-slate-500">
                      {isRu ? stage.detailRu : stage.detailEn}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

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
    </>
  );
};
