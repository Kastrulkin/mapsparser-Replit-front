import React from 'react';
import { Button } from '@/components/ui/button';
import { _socialOpenClawReadinessDetails, _socialOpenClawReadinessOperational, _socialOpenClawReadinessTitle, _socialOpenClawOwnerCheckSummary, _normalizeSocialChannelFilter, _socialChannelFilterLabel, _socialPlatformLabel, _socialSettingsPathForPlatform, _socialChannelConnectionStateLabel, _socialPublishModeLabel, _socialQueueGroupLabel, _socialQueueGroupNextAction } from './helpers';

export const SocialStatusPanels = ({ scope }) => {
  const {
    navigate, isRu, selectedChannelFilter, setSelectedChannelFilter, socialSummary, socialQueueGroups, socialChannelReadiness, socialApiPreflight,
    socialOpenClawReadiness, socialBusyAction, readiness, socialReadinessSummary, socialReadinessSetupPath, socialChannelConnectionGuide, socialApiPreflightByPlatform, socialApiPreflightSummary,
    socialFirstApiPublishReadiness, socialLaunchStages, checkOpenClawBrowserReadiness, checkApiChannelPreflight
  } = scope;
  return (
    <>
                <div
                  data-testid="social-launch-readiness"
                  className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4"
                >
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">
                        {isRu ? 'Готовность к рабочему запуску' : 'Launch readiness'}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-slate-500">
                        {isRu
                          ? 'Короткий путь до полного цикла: подготовить каналы, проверить тексты, поставить в расписание, выполнить публикации и собрать результат.'
                          : 'The short path to a full loop: prepare channels, review copy, queue, publish, and collect results.'}
                      </div>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600 lg:max-w-[360px]">
                      <span className="font-semibold text-slate-900">
                        {isRu ? 'Главный ориентир: ' : 'Main signal: '}
                      </span>
                      {isRu
                        ? 'заявки и обращения важнее охватов; изменения плана применяются только после подтверждения.'
                        : 'leads and inquiries matter more than reach; plan changes apply only after confirmation.'}
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                    {socialLaunchStages.map((stage) => (
                      <div
                        key={stage.key}
                        className={[
                          'rounded-xl border px-3 py-3',
                          stage.status === 'done'
                            ? 'border-emerald-100 bg-emerald-50'
                            : stage.status === 'current'
                              ? 'border-sky-100 bg-sky-50'
                              : stage.status === 'attention'
                                ? 'border-red-100 bg-red-50'
                                : 'border-slate-200 bg-slate-50',
                        ].join(' ')}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div
                              className={[
                                'text-xs font-semibold',
                                stage.status === 'done'
                                  ? 'text-emerald-950'
                                  : stage.status === 'current'
                                    ? 'text-sky-950'
                                    : stage.status === 'attention'
                                      ? 'text-red-950'
                                      : 'text-slate-700',
                              ].join(' ')}
                            >
                              {isRu ? stage.labelRu : stage.labelEn}
                            </div>
                            <div
                              className={[
                                'mt-1 text-xs leading-5',
                                stage.status === 'done'
                                  ? 'text-emerald-800'
                                  : stage.status === 'current'
                                    ? 'text-sky-800'
                                    : stage.status === 'attention'
                                      ? 'text-red-800'
                                      : 'text-slate-500',
                              ].join(' ')}
                            >
                              {isRu ? stage.detailRu : stage.detailEn}
                            </div>
                          </div>
                          <span
                            className={[
                              'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold',
                              stage.status === 'done'
                                ? 'bg-white text-emerald-700'
                                : stage.status === 'current'
                                  ? 'bg-white text-sky-700'
                                  : stage.status === 'attention'
                                    ? 'bg-white text-red-700'
                                    : 'bg-white text-slate-500',
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
                      </div>
                    ))}
                  </div>
                </div>
                <div
                  data-testid="social-channel-queue"
                  className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div>
                    <div className="text-sm font-semibold text-slate-950">
                      {isRu ? 'Очередь публикаций по каналам' : 'Channel publishing queue'}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-slate-500">
                      {isRu
                        ? 'Здесь видно, что нужно проверить, что готово к API и где требуется контролируемое размещение.'
                        : 'See what needs review, what is API-ready, and where supervised placement is required.'}
                    </div>
                  </div>
                  {Number(socialSummary?.total || 0) > 0 ? (
                    <div className="text-xs font-medium text-slate-500">
                      {isRu ? `Всего публикаций: ${socialSummary?.total || 0}` : `Posts: ${socialSummary?.total || 0}`}
                    </div>
                  ) : null}
                </div>
                {socialQueueGroups.length > 0 ? (
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
                    {socialQueueGroups.map((group) => (
                      <div key={group.key} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-xs font-semibold text-slate-700">
                            {_socialQueueGroupLabel(group, isRu)}
                          </div>
                          <div className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-slate-900">
                            {group.count || 0}
                          </div>
                        </div>
                        <div className="mt-2 min-h-[40px] text-xs leading-5 text-slate-500">
                          {_socialQueueGroupNextAction(group, isRu)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600">
                    {isRu
                      ? 'Подготовьте каналы для тем плана, чтобы увидеть рабочую очередь публикаций.'
                      : 'Prepare channels for plan items to see the publishing workload.'}
                  </div>
                )}
                {socialChannelReadiness.length > 0 ? (
                  <>
                    <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="text-sm font-semibold text-slate-950">
                            {isRu ? 'Готовность каналов' : 'Channel readiness'}
                          </div>
                          <div className="mt-1 text-xs leading-5 text-slate-600">
                            {socialReadinessSummary.blockedApiChannels.length > 0
                              ? (isRu
                                ? 'Перед постановкой API-каналов в расписание подключите ключи или права. Карты останутся контролируемыми или ручными и не будут выглядеть как автопубликация.'
                                : 'Connect keys or permissions before queueing API channels. Maps stay supervised/manual and are not shown as autopublish.')
                              : (isRu
                                ? 'API-каналы готовы к публикации после подтверждения. Карты идут через контролируемое или ручное размещение.'
                                : 'API channels are ready to publish after approval. Maps use supervised placement.')}
                          </div>
                          {socialOpenClawReadiness ? (
                            (() => {
                              const openClawOperational = _socialOpenClawReadinessOperational(socialOpenClawReadiness);
                              return (
                                <div className={[
                                  'mt-3 rounded-lg border px-3 py-2 text-xs leading-5',
                                  openClawOperational
                                    ? 'border-sky-100 bg-sky-50 text-sky-800'
                                    : 'border-amber-100 bg-amber-50 text-amber-800',
                                ].join(' ')}
                                >
                                  <div className={openClawOperational ? 'font-semibold text-sky-950' : 'font-semibold text-amber-950'}>
                                    {_socialOpenClawReadinessTitle(socialOpenClawReadiness, isRu)}
                                  </div>
                                  <div className="mt-1">
                                    {isRu ? socialOpenClawReadiness.message_ru : socialOpenClawReadiness.message_en}
                                  </div>
                                  <div className="mt-1 font-medium">
                                    {isRu ? socialOpenClawReadiness.next_action_ru : socialOpenClawReadiness.next_action_en}
                                  </div>
                                  {_socialOpenClawReadinessDetails(socialOpenClawReadiness, isRu).length > 0 ? (
                                    <ul className="mt-2 space-y-1">
                                      {_socialOpenClawReadinessDetails(socialOpenClawReadiness, isRu).slice(0, 4).map((detail) => (
                                        <li key={`openclaw-readiness:${detail}`} className="flex gap-2">
                                          <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-70" />
                                          <span>{detail}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  ) : null}
                                  <div className="mt-2 rounded-md bg-white/70 px-2 py-1.5 text-[11px] leading-4">
                                    {_socialOpenClawOwnerCheckSummary(socialOpenClawReadiness, isRu)}
                                  </div>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    className="mt-2 h-7 rounded-lg bg-white/80 px-2 text-[11px]"
                                    onClick={() => { void checkOpenClawBrowserReadiness(); }}
                                    disabled={socialBusyAction === 'openclaw-check'}
                                  >
                                    {socialBusyAction === 'openclaw-check'
                                      ? (isRu ? 'Проверяем...' : 'Checking...')
                                      : (isRu ? 'Проверить OpenClaw сейчас' : 'Check OpenClaw now')}
                                  </Button>
                                </div>
                              );
                            })()
                          ) : null}
                          {socialReadinessSummary.blockedApiChannels.length > 0 ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => navigate(socialReadinessSetupPath)}
                              >
                                {isRu ? 'Настроить нужный канал' : 'Open required setup'}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="bg-white"
                                onClick={() => { void checkApiChannelPreflight(); }}
                                disabled={socialBusyAction === 'api-channel-preflight'}
                              >
                                {socialBusyAction === 'api-channel-preflight'
                                  ? (isRu ? 'Проверяем API...' : 'Checking API...')
                                  : (isRu ? 'Проверить API-каналы' : 'Check API channels')}
                              </Button>
                            </div>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="mt-3 bg-white"
                              onClick={() => { void checkApiChannelPreflight(); }}
                              disabled={socialBusyAction === 'api-channel-preflight'}
                            >
                              {socialBusyAction === 'api-channel-preflight'
                                ? (isRu ? 'Проверяем API...' : 'Checking API...')
                                : (isRu ? 'Проверить API-каналы' : 'Check API channels')}
                            </Button>
                          )}
                        </div>
                        <div className="grid gap-2 text-xs sm:grid-cols-3 lg:min-w-[360px]">
                          <div className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">
                            <div className="font-semibold text-emerald-950">{socialReadinessSummary.apiReady}</div>
                            <div>{isRu ? 'API готовы' : 'API ready'}</div>
                          </div>
                          <div className="rounded-lg bg-amber-50 px-3 py-2 text-amber-800">
                            <div className="font-semibold text-amber-950">{socialReadinessSummary.needsAttention}</div>
                            <div>{isRu ? 'нужно внимание' : 'need attention'}</div>
                          </div>
                          <div className="rounded-lg bg-sky-50 px-3 py-2 text-sky-800">
                            <div className="font-semibold text-sky-950">{socialReadinessSummary.supervisedOrManual}</div>
                            <div>{isRu ? 'контроль/вручную' : 'supervised/manual'}</div>
                          </div>
                        </div>
                      </div>
                      <div
                        data-testid="social-first-api-publish-readiness"
                        className={[
                          'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                          socialFirstApiPublishReadiness.readyForFirstApiPublish
                            ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
                            : socialFirstApiPublishReadiness.hasAnyReadyApi
                              ? 'border-sky-100 bg-sky-50 text-sky-900'
                              : 'border-amber-100 bg-amber-50 text-amber-900',
                        ].join(' ')}
                      >
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <div className={[
                              'text-sm font-semibold',
                              socialFirstApiPublishReadiness.readyForFirstApiPublish
                                ? 'text-emerald-950'
                                : socialFirstApiPublishReadiness.hasAnyReadyApi
                                  ? 'text-sky-950'
                                  : 'text-amber-950',
                            ].join(' ')}
                            >
                              {isRu ? 'Первый API-пост' : 'First API post'}
                            </div>
                            <div className="mt-1">
                              {socialFirstApiPublishReadiness.readyForFirstApiPublish
                                ? (isRu
                                  ? `Каналы готовы к первому реальному API-посту после предпросмотра, подтверждения и расписания: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`
                                  : `Channels are ready for the first real API post after preview, approval, and queueing: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`)
                                : socialFirstApiPublishReadiness.hasAnyReadyApi
                                  ? (isRu
                                    ? `Можно начинать с готовых каналов: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}. Заблокированные каналы исполнитель пропустит до настройки.`
                                    : `You can start with ready channels: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}. Blocked channels will be skipped until setup is fixed.`)
                                  : (isRu
                                    ? 'Пока нет готового API-канала для первого реального поста. Сначала подключите ключи и права, затем запустите live API-проверку.'
                                    : 'No API channel is ready for the first real post yet. Connect keys and permissions first, then run the live API check.')}
                            </div>
                            <div className="mt-1 font-medium">
                              {socialFirstApiPublishReadiness.hasLiveCheck
                                ? (isRu ? 'Live API-проверка уже выполнена без публикации.' : 'Live API check has already run without publishing.')
                                : (isRu ? 'Для уверенного запуска нажмите “Проверить API-каналы” перед расписанием.' : 'For a confident launch, click “Check API channels” before queueing.')}
                            </div>
                            {socialFirstApiPublishReadiness.blockedLabels.length > 0 ? (
                              <div className="mt-2">
                                <span className="font-semibold">{isRu ? 'Сначала исправить: ' : 'Fix first: '}</span>
                                {socialFirstApiPublishReadiness.blockedLabels.slice(0, 4).join(', ')}
                              </div>
                            ) : null}
                            {socialFirstApiPublishReadiness.setupFocus ? (
                              <div
                                data-testid="social-first-api-setup-checklist"
                                className="mt-3 rounded-lg border border-white bg-white/70 px-3 py-2 text-xs leading-5"
                              >
                                <div className="font-semibold">
                                  {isRu ? 'Мини-чеклист подключения' : 'Connection mini-checklist'}
                                  {' · '}
                                  {socialFirstApiPublishReadiness.setupFocus.platform_label
                                    || _socialPlatformLabel(String(socialFirstApiPublishReadiness.setupFocus.platform || ''), isRu)}
                                </div>
                                {socialFirstApiPublishReadiness.setupFocusSteps.length > 0 ? (
                                  <ol className="mt-1 list-decimal space-y-1 pl-4">
                                    {socialFirstApiPublishReadiness.setupFocusSteps.map((step) => (
                                      <li key={`first-api-setup-step:${step}`}>{step}</li>
                                    ))}
                                  </ol>
                                ) : null}
                                {socialFirstApiPublishReadiness.setupFocusChecks.length > 0 ? (
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {socialFirstApiPublishReadiness.setupFocusChecks.map((check) => (
                                      <span
                                        key={`first-api-setup-check:${String(check.key || '')}`}
                                        className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-900"
                                      >
                                        {isRu ? String(check.label_ru || check.key || '') : String(check.label_en || check.key || '')}
                                        {': '}
                                        {isRu ? String(check.detail_ru || '') : String(check.detail_en || '')}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                                {socialFirstApiPublishReadiness.setupFocusMissingFields.length > 0 ? (
                                  <div className="mt-2 font-mono text-[11px]">
                                    {isRu ? 'Поля: ' : 'Fields: '}
                                    {socialFirstApiPublishReadiness.setupFocusMissingFields.join(', ')}
                                  </div>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-2">
                            {socialFirstApiPublishReadiness.firstBlocked ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg bg-white px-2.5 text-[11px]"
                                onClick={() => navigate(socialFirstApiPublishReadiness.firstBlocked?.settings_path || _socialSettingsPathForPlatform(String(socialFirstApiPublishReadiness.firstBlocked?.platform || '')))}
                              >
                                {isRu ? 'Открыть настройку' : 'Open setup'}
                              </Button>
                            ) : null}
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-8 rounded-lg bg-white px-2.5 text-[11px]"
                              onClick={() => { void checkApiChannelPreflight(); }}
                              disabled={socialBusyAction === 'api-channel-preflight'}
                            >
                              {socialBusyAction === 'api-channel-preflight'
                                ? (isRu ? 'Проверяем...' : 'Checking...')
                                : (isRu ? 'Проверить API' : 'Check API')}
                            </Button>
                          </div>
                        </div>
                      </div>
                      <div
                        data-testid="social-channel-connection-guide"
                        className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3"
                      >
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <div className="text-sm font-semibold text-slate-950">
                              {isRu ? 'Подключение каналов' : 'Channel setup guide'}
                            </div>
                            <div className="mt-1 text-xs leading-5 text-slate-600">
                              {socialChannelConnectionGuide.readyToStart
                                ? (isRu
                                  ? `Можно начинать с готового API-канала: ${socialChannelConnectionGuide.quickStartCandidate?.platform_label || _socialPlatformLabel(String(socialChannelConnectionGuide.quickStartCandidate?.platform || ''), isRu)}. Остальные каналы LocalOS покажет как “нужно подключить” или “контролируемое размещение”.`
                                  : `You can start with a ready API channel: ${socialChannelConnectionGuide.quickStartCandidate?.platform_label || _socialPlatformLabel(String(socialChannelConnectionGuide.quickStartCandidate?.platform || ''), isRu)}. Other channels stay marked as setup needed or supervised placement.`)
                                : (isRu
                                  ? 'Для первого реального API-поста быстрее всего подключить Telegram или VK. Яндекс/2ГИС останутся контролируемым размещением, а не скрытой автопубликацией.'
                                  : 'For the first real API post, connect Telegram or VK first. Yandex/2GIS stay supervised placement, not hidden autopublish.')}
                            </div>
                            <div className="mt-2 text-xs font-medium text-slate-700">
                              {socialChannelConnectionGuide.recommendedSetup
                                ? (isRu
                                  ? `Первое действие: открыть настройку ${socialChannelConnectionGuide.recommendedSetup.platform_label || _socialPlatformLabel(String(socialChannelConnectionGuide.recommendedSetup.platform || ''), isRu)} и добавить ключи/права.`
                                  : `First action: open ${socialChannelConnectionGuide.recommendedSetup.platform_label || _socialPlatformLabel(String(socialChannelConnectionGuide.recommendedSetup.platform || ''), isRu)} setup and add keys/permissions.`)
                                : (isRu
                                  ? 'Первое действие: подготовить посты, проверить предпросмотр и поставить готовые API-каналы в расписание.'
                                  : 'First action: prepare posts, review the preview, and queue ready API channels.')}
                            </div>
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-2">
                            {socialChannelConnectionGuide.recommendedSetup ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg bg-white px-2.5 text-[11px]"
                                onClick={() => navigate(socialChannelConnectionGuide.recommendedSetup?.settings_path || _socialSettingsPathForPlatform(String(socialChannelConnectionGuide.recommendedSetup?.platform || '')))}
                              >
                                {isRu ? 'Открыть подключение' : 'Open setup'}
                              </Button>
                            ) : null}
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-8 rounded-lg bg-white px-2.5 text-[11px]"
                              onClick={() => { void checkApiChannelPreflight(); }}
                              disabled={socialBusyAction === 'api-channel-preflight'}
                            >
                              {socialBusyAction === 'api-channel-preflight'
                                ? (isRu ? 'Проверяем...' : 'Checking...')
                                : (isRu ? 'Проверить готовность' : 'Check readiness')}
                            </Button>
                          </div>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                          {socialChannelConnectionGuide.apiChannels.map((channel) => (
                            <div
                              key={`connection-guide-api:${channel.platform}`}
                              className={channel.ready
                                ? 'rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-emerald-800'
                                : 'rounded-lg border border-amber-100 bg-white px-3 py-2 text-xs leading-5 text-amber-800'}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className={channel.ready ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                                  {channel.platform_label || _socialPlatformLabel(channel.platform, isRu)}
                                </span>
                                <span className={channel.ready ? 'rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700' : 'rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700'}>
                                  {_socialChannelConnectionStateLabel(channel, isRu)}
                                </span>
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? channel.setup_summary_ru || channel.next_action_ru || channel.message_ru
                                  : channel.setup_summary_en || channel.next_action_en || channel.message_en}
                              </div>
                              {channel.target_setup?.schema ? (
                                <div
                                  data-testid={`social-channel-guide-target-setup-${String(channel.platform || '')}`}
                                  className={channel.ready
                                    ? 'mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-[11px] leading-4 text-emerald-900'
                                    : 'mt-2 rounded-lg bg-amber-50 px-2 py-1.5 text-[11px] leading-4 text-amber-900'}
                                >
                                  <div className={channel.ready ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                                    {isRu
                                      ? String(channel.target_setup.target_label_ru || 'Цель публикации')
                                      : String(channel.target_setup.target_label_en || 'Publish target')}
                                  </div>
                                  {channel.target_setup.owner_telegram_present ? (
                                    <div
                                      data-testid={`social-channel-guide-owner-telegram-linked-${String(channel.platform || '')}`}
                                      className="mt-1 inline-flex rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-800"
                                    >
                                      {isRu ? 'Владелец подключён' : 'Owner linked'}
                                    </div>
                                  ) : null}
                                  {channel.target_setup.telegram_app_present ? (
                                    <div
                                      data-testid={`social-channel-guide-telegram-app-linked-${String(channel.platform || '')}`}
                                      className="ml-1 mt-1 inline-flex rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-800"
                                    >
                                      {isRu ? 'Telegram app подключён' : 'Telegram app linked'}
                                    </div>
                                  ) : null}
                                  <div className="mt-1">
                                    {isRu
                                      ? String(channel.target_setup.summary_ru || '')
                                      : String(channel.target_setup.summary_en || '')}
                                  </div>
                                  <div className="mt-1 text-slate-600">
                                    {isRu
                                      ? String(channel.target_setup.not_a_target_ru || '')
                                      : String(channel.target_setup.not_a_target_en || '')}
                                  </div>
                                  <div className="mt-1 font-medium">
                                    {isRu
                                      ? String(channel.target_setup.proof_ru || '')
                                      : String(channel.target_setup.proof_en || '')}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ))}
                          {socialChannelConnectionGuide.supervisedChannels.length > 0 ? (
                            <div className="rounded-lg border border-sky-100 bg-white px-3 py-2 text-xs leading-5 text-sky-800">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-sky-950">
                                  {isRu ? 'Яндекс/2ГИС' : 'Yandex/2GIS'}
                                </span>
                                <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-700">
                                  {isRu ? 'контролируемо' : 'supervised'}
                                </span>
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? 'LocalOS подготовит текст и задачу. Финальный клик остаётся за человеком.'
                                  : 'LocalOS prepares the text and task. The final click stays with a human.'}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>
                      {socialReadinessSummary.blockedApiChannels.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {socialReadinessSummary.blockedApiChannels.slice(0, 4).map((channel) => (
                            <span key={channel.platform} className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
                              {channel.platform_label || _socialPlatformLabel(channel.platform, isRu)} · {isRu ? channel.setup_summary_ru || channel.next_action_ru || channel.message_ru : channel.setup_summary_en || channel.next_action_en || channel.message_en}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {socialApiPreflightSummary.checked > 0 ? (
                        <div className="mt-3 rounded-xl border border-sky-100 bg-sky-50 px-3 py-3 text-xs leading-5 text-sky-900">
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <div className="font-semibold text-sky-950">
                                {isRu ? 'Live API-проверка каналов' : 'Live API channel check'}
                              </div>
                              <div className="mt-1 text-sky-800">
                                {isRu
                                  ? `Проверено без публикации: ${socialApiPreflightSummary.checked}. Готово: ${socialApiPreflightSummary.ready.length}. Нужно внимание: ${socialApiPreflightSummary.needsAttention.length}.`
                                  : `Checked without publishing: ${socialApiPreflightSummary.checked}. Ready: ${socialApiPreflightSummary.ready.length}. Needs attention: ${socialApiPreflightSummary.needsAttention.length}.`}
                              </div>
                            </div>
                            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-sky-800">
                              {isRu ? 'публикация только после подтверждения' : 'publish only after approval'}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {socialApiPreflight.map((item) => {
                              const missingFields = (item.missing_fields || []).slice(0, 3);
                              const setupPath = item.settings_path || _socialSettingsPathForPlatform(String(item.platform || ''));
                              return (
                                <span
                                  key={`api-preflight-summary:${String(item.platform || '')}`}
                                  className={
                                    item.ready
                                      ? 'inline-flex flex-wrap items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-medium text-emerald-800'
                                      : 'inline-flex flex-wrap items-center gap-1 rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-amber-800'
                                  }
                                >
                                  <span>
                                    {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                    {' · '}
                                    {item.ready ? (isRu ? 'готов' : 'ready') : String(item.status || (isRu ? 'нужно внимание' : 'needs attention'))}
                                  </span>
                                  {!item.ready && missingFields.length > 0 ? (
                                    <span className="text-[10px] font-semibold text-amber-700">
                                      {missingFields.join(', ')}
                                    </span>
                                  ) : null}
                                  {!item.ready ? (
                                    <button
                                      type="button"
                                      className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800 underline-offset-2 hover:underline"
                                      onClick={() => navigate(setupPath)}
                                    >
                                      {isRu ? 'настроить' : 'setup'}
                                    </button>
                                  ) : null}
                                </span>
                              );
                            })}
                          </div>
                          {socialApiPreflightSummary.needsAttention.length > 0 ? (
                            <div className="mt-2 text-sky-800">
                              {isRu
                                ? 'Перед расписанием исправьте ключи, права или используйте ручной режим для заблокированных каналов.'
                                : 'Before queueing, fix keys, permissions, or use manual fallback for blocked channels.'}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                      {socialChannelReadiness.map((channel) => (
                        <div
                          key={channel.platform}
                          className={[
                            'rounded-xl border px-3 py-2',
                            channel.ready
                              ? 'border-emerald-100 bg-emerald-50'
                              : 'border-amber-100 bg-amber-50',
                          ].join(' ')}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className={channel.ready ? 'text-xs font-semibold text-emerald-950' : 'text-xs font-semibold text-amber-950'}>
                              {channel.platform_label || _socialPlatformLabel(channel.platform, isRu)}
                            </div>
                            <span className={channel.ready ? 'text-[11px] font-medium text-emerald-700' : 'text-[11px] font-medium text-amber-700'}>
                              {channel.ready ? (isRu ? 'готов' : 'ready') : (isRu ? 'нужно внимание' : 'needs attention')}
                            </span>
                          </div>
                          <div className={channel.ready ? 'mt-1 text-xs leading-5 text-emerald-800' : 'mt-1 text-xs leading-5 text-amber-800'}>
                            {isRu ? channel.message_ru : channel.message_en}
                          </div>
                          <div className={channel.ready ? 'mt-2 text-[11px] font-medium text-emerald-700' : 'mt-2 text-[11px] font-medium text-amber-700'}>
                            {_socialPublishModeLabel(channel.publish_mode || '', isRu)}
                          </div>
                          {channel.setup_summary_ru || channel.setup_summary_en ? (
                            <div className={channel.ready ? 'mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-emerald-900' : 'mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-amber-900'}>
                              <span className="font-semibold">
                                {isRu ? 'Сейчас: ' : 'Now: '}
                              </span>
                              {isRu ? channel.setup_summary_ru : channel.setup_summary_en}
                            </div>
                          ) : null}
                          {channel.next_action_ru || channel.next_action_en ? (
                            <div className={channel.ready ? 'mt-2 rounded-lg bg-white/70 px-2 py-1.5 text-[11px] leading-4 text-emerald-900' : 'mt-2 rounded-lg bg-white/70 px-2 py-1.5 text-[11px] leading-4 text-amber-900'}>
                              <span className="font-semibold">
                                {isRu ? 'Что сделать: ' : 'Next: '}
                              </span>
                              {isRu ? channel.next_action_ru : channel.next_action_en}
                            </div>
                          ) : null}
                          {channel.target_setup?.schema ? (
                            <div
                              data-testid={`social-channel-target-setup-${String(channel.platform || '')}`}
                              data-schema={String(channel.target_setup.schema || 'localos_social_channel_target_setup_v1')}
                              className={channel.ready ? 'mt-2 rounded-lg border border-emerald-100 bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-emerald-900' : 'mt-2 rounded-lg border border-amber-100 bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-amber-900'}
                            >
                              <div className={channel.ready ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                                {isRu
                                  ? String(channel.target_setup.target_label_ru || 'Цель публикации')
                                  : String(channel.target_setup.target_label_en || 'Publish target')}
                              </div>
                              {channel.target_setup.owner_telegram_present ? (
                                <div
                                  data-testid={`social-channel-owner-telegram-linked-${String(channel.platform || '')}`}
                                  className="mt-1 inline-flex rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-800"
                                >
                                  {isRu ? 'Владелец подключён в Telegram' : 'Owner Telegram is linked'}
                                </div>
                              ) : null}
                              {channel.target_setup.telegram_app_present ? (
                                <div
                                  data-testid={`social-channel-telegram-app-linked-${String(channel.platform || '')}`}
                                  className="ml-1 mt-1 inline-flex rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-800"
                                >
                                  {isRu ? 'Telegram app подключён' : 'Telegram app linked'}
                                </div>
                              ) : null}
                              <div className="mt-1">
                                {isRu
                                  ? String(channel.target_setup.summary_ru || '')
                                  : String(channel.target_setup.summary_en || '')}
                              </div>
                              {(isRu ? channel.target_setup.not_a_target_ru : channel.target_setup.not_a_target_en) ? (
                                <div className="mt-1 text-slate-600">
                                  {isRu
                                    ? String(channel.target_setup.not_a_target_ru || '')
                                    : String(channel.target_setup.not_a_target_en || '')}
                                </div>
                              ) : null}
                              {((isRu ? channel.target_setup.steps_ru : channel.target_setup.steps_en) || []).length > 0 ? (
                                <ol className="mt-1 space-y-1">
                                  {((isRu ? channel.target_setup.steps_ru : channel.target_setup.steps_en) || []).slice(0, 4).map((step, index) => (
                                    <li key={`${channel.platform}-target-setup-${index}`} className="flex gap-1.5">
                                      <span className="mt-[1px] shrink-0 font-semibold">{index + 1}.</span>
                                      <span>{step}</span>
                                    </li>
                                  ))}
                                </ol>
                              ) : null}
                              <div className="mt-1 font-medium">
                                {isRu
                                  ? String(channel.target_setup.proof_ru || '')
                                  : String(channel.target_setup.proof_en || '')}
                              </div>
                            </div>
                          ) : null}
                          {(channel.connection_checks || []).length > 0 ? (
                            <div className={channel.ready ? 'mt-2 rounded-lg border border-emerald-100 bg-white/70 px-2 py-1.5' : 'mt-2 rounded-lg border border-amber-100 bg-white/70 px-2 py-1.5'}>
                              <div className={channel.ready ? 'text-[11px] font-semibold text-emerald-950' : 'text-[11px] font-semibold text-amber-950'}>
                                {isRu ? 'Что проверить' : 'What to check'}
                              </div>
                              <div className="mt-1 space-y-1">
                                {(channel.connection_checks || []).slice(0, 4).map((check) => {
                                  const checkOk = Boolean(check.ok);
                                  const state = String(check.state || '').trim();
                                  const neutral = state === 'deferred' || state === 'manual' || state === 'recommended' || state === 'human_approval';
                                  const checkStateLabel = checkOk
                                    ? (isRu ? 'Готово' : 'Ready')
                                    : neutral
                                      ? (isRu ? 'Инфо' : 'Info')
                                      : (isRu ? 'Нужно' : 'Needed');
                                  return (
                                    <div
                                      key={`${channel.platform}-check-${String(check.key || check.label_en || check.label_ru || '')}`}
                                      className="flex gap-2 text-[11px] leading-4"
                                    >
                                      <span className={[
                                        'mt-[1px] shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
                                        checkOk ? 'bg-emerald-50 text-emerald-700' : neutral ? 'bg-sky-50 text-sky-700' : 'bg-amber-50 text-amber-700',
                                      ].join(' ')}
                                      >
                                        {checkStateLabel}
                                      </span>
                                      <span className={checkOk ? 'text-emerald-800' : neutral ? 'text-sky-800' : 'text-amber-800'}>
                                        <span className="font-medium">
                                          {isRu ? String(check.label_ru || '') : String(check.label_en || '')}
                                        </span>
                                        {(isRu ? check.detail_ru : check.detail_en) ? ` · ${isRu ? String(check.detail_ru || '') : String(check.detail_en || '')}` : ''}
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ) : null}
                          {socialApiPreflightByPlatform[String(channel.platform || '')] ? (
                            <div
                              className={
                                socialApiPreflightByPlatform[String(channel.platform || '')].ready
                                  ? 'mt-2 rounded-lg border border-emerald-200 bg-white px-2 py-1.5'
                                  : 'mt-2 rounded-lg border border-amber-200 bg-white px-2 py-1.5'
                              }
                            >
                              <div
                                className={
                                  socialApiPreflightByPlatform[String(channel.platform || '')].ready
                                    ? 'text-[11px] font-semibold text-emerald-950'
                                    : 'text-[11px] font-semibold text-amber-950'
                                }
                              >
                                {isRu ? 'Live API-проверка' : 'Live API preflight'}
                              </div>
                              <div
                                className={
                                  socialApiPreflightByPlatform[String(channel.platform || '')].ready
                                    ? 'mt-1 text-[11px] leading-4 text-emerald-800'
                                    : 'mt-1 text-[11px] leading-4 text-amber-800'
                                }
                              >
                                {isRu
                                  ? socialApiPreflightByPlatform[String(channel.platform || '')].message_ru
                                  : socialApiPreflightByPlatform[String(channel.platform || '')].message_en}
                              </div>
                              <div className="mt-1 space-y-1">
                                {(socialApiPreflightByPlatform[String(channel.platform || '')].connection_checks || []).slice(-2).map((check) => (
                                  <div key={`${channel.platform}-live-${String(check.key || check.label_en || check.label_ru || '')}`} className="flex gap-1.5 text-[11px] leading-4">
                                    <span className={check.ok ? 'text-emerald-700' : 'text-amber-700'}>
                                      {check.ok ? '✓' : '!'}
                                    </span>
                                    <span className={check.ok ? 'text-emerald-800' : 'text-amber-800'}>
                                      <span className="font-medium">{isRu ? String(check.label_ru || '') : String(check.label_en || '')}</span>
                                      {(isRu ? check.detail_ru : check.detail_en) ? ` · ${isRu ? String(check.detail_ru || '') : String(check.detail_en || '')}` : ''}
                                    </span>
                                  </div>
                                ))}
                              </div>
                              <div className="mt-1 text-[10px] font-medium text-slate-500">
                                {isRu ? 'Посты не отправлялись. Публикация только после подтверждения.' : 'No posts were sent. Publish only after approval.'}
                              </div>
                            </div>
                          ) : null}
                          {((isRu ? channel.setup_steps_ru : channel.setup_steps_en) || []).length > 0 ? (
                            <div className={channel.ready ? 'mt-2 rounded-lg border border-emerald-100 bg-white/70 px-2 py-1.5' : 'mt-2 rounded-lg border border-amber-100 bg-white/70 px-2 py-1.5'}>
                              <div className={channel.ready ? 'text-[11px] font-semibold text-emerald-950' : 'text-[11px] font-semibold text-amber-950'}>
                                {isRu ? 'Чеклист' : 'Checklist'}
                              </div>
                              <ul className={channel.ready ? 'mt-1 space-y-1 text-[11px] leading-4 text-emerald-800' : 'mt-1 space-y-1 text-[11px] leading-4 text-amber-800'}>
                                {((isRu ? channel.setup_steps_ru : channel.setup_steps_en) || []).slice(0, 3).map((step, index) => (
                                  <li key={`${channel.platform}-setup-${index}`} className="flex gap-1.5">
                                    <span className="mt-[1px] shrink-0 font-semibold">{index + 1}.</span>
                                    <span>{step}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {!channel.ready && (channel.missing_fields || []).length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {(channel.missing_fields || []).slice(0, 3).map((field) => (
                                <span key={`${channel.platform}-missing-${field}`} className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium text-amber-800">
                                  {field}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          {!channel.ready && channel.publish_mode === 'api' ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="mt-2 h-7 rounded-lg px-2 text-[11px]"
                              onClick={() => navigate(channel.settings_path || _socialSettingsPathForPlatform(String(channel.platform || '')))}
                            >
                              {isRu ? 'Открыть настройку канала' : 'Open channel setup'}
                            </Button>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-2">
                  {['all', 'social', 'maps'].map((filterKey) => (
                    <button
                      key={filterKey}
                      type="button"
                      onClick={() => setSelectedChannelFilter(_normalizeSocialChannelFilter(filterKey))}
                      className={[
                        'rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
                        selectedChannelFilter === filterKey
                          ? 'border-slate-900 bg-slate-900 text-white'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                      ].join(' ')}
                    >
                      {_socialChannelFilterLabel(filterKey, isRu)}
                    </button>
                  ))}
                </div>
    </>
  );
};
