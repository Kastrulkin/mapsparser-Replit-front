import React from 'react';
import { Button } from '@/components/ui/button';
import { _socialPlatformLabel, _socialLearningReadinessClassName, _socialLearningConfidenceLabel, _socialLearningChecklistStatusLabel, _socialInsightMetricLine } from './helpers';

export const SocialRecommendationPanel = ({ scope }) => {
  const {
    isRu, socialSummary, socialRecommendation, socialRecommendationApproved, setSocialRecommendationApproved, socialMetricsLearningPacket, socialBusyAction, readiness,
    socialMetricsSourceSummary, socialPrimaryResultCount, socialEarlySignalCount, socialLearningLoopStatus, selectPublishedSocialPostsForResult, collectSocialPostMetricsForBusiness, recommendNextSocialPlan, applySocialPlanRecommendation
  } = scope;
  return (
    <>
                <div
                  data-testid="social-next-plan-recommendation"
                  className="mt-3 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-3"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-emerald-950">
                        {isRu ? 'Что менять в следующем плане' : 'What to change next'}
                      </div>
                        <div className="mt-1 text-xs leading-5 text-emerald-800">
                          {isRu
                            ? String(socialRecommendation?.recommendation?.text_ru || 'После публикаций LocalOS будет ранжировать темы по заявкам и обращениям, затем по комментариям и охвату.')
                            : String(socialRecommendation?.recommendation?.text_en || 'After publishing, LocalOS will rank topics by leads and inquiries first, then comments and reach.')}
                        </div>
                        <div
                          data-testid="social-learning-loop-status"
                          className={[
                            'mt-3 rounded-lg border px-3 py-2 text-xs leading-5',
                            socialLearningLoopStatus.tone === 'success'
                              ? 'border-emerald-200 bg-white text-emerald-900'
                              : socialLearningLoopStatus.tone === 'warning'
                                ? 'border-amber-200 bg-amber-50 text-amber-900'
                                : socialLearningLoopStatus.tone === 'caution'
                                  ? 'border-sky-200 bg-sky-50 text-sky-900'
                                  : 'border-slate-200 bg-white text-slate-700',
                          ].join(' ')}
                        >
                          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <div className="font-semibold">
                                {isRu ? 'Статус learning loop' : 'Learning loop status'} · {isRu ? socialLearningLoopStatus.titleRu : socialLearningLoopStatus.titleEn}
                              </div>
                              <div className="mt-1">
                                {isRu ? socialLearningLoopStatus.textRu : socialLearningLoopStatus.textEn}
                              </div>
                            </div>
                            <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium">
                              {socialPrimaryResultCount > 0
                                ? (isRu ? 'заявки главнее' : 'leads first')
                                : socialEarlySignalCount > 0
                              ? (isRu ? 'ранний сигнал' : 'early signal')
                              : Number(socialSummary?.published || 0) > 0
                                ? (isRu ? 'ждём реакции' : 'needs reactions')
                                : (isRu ? 'после publish' : 'after publish')}
                            </span>
                          </div>
                        </div>
                        {socialMetricsLearningPacket ? (
                          <div
                            data-testid="social-metrics-learning-packet"
                            data-schema="localos_social_metrics_learning_packet_v1"
                            className={[
                              'mt-3 rounded-lg border px-3 py-2 text-xs leading-5',
                              Number(socialMetricsLearningPacket.primary_result_total || 0) > 0
                                ? 'border-emerald-200 bg-white text-emerald-900'
                                : Number(socialMetricsLearningPacket.early_signal_total || 0) > 0
                                  ? 'border-sky-200 bg-sky-50 text-sky-900'
                                  : Number(socialMetricsLearningPacket.failed_posts || 0) > 0
                                    ? 'border-amber-200 bg-amber-50 text-amber-900'
                                    : 'border-slate-200 bg-white text-slate-700',
                            ].join(' ')}
                          >
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div>
                                <div className="font-semibold">
                                  {isRu ? 'Результат после сбора реакций' : 'Result after collecting reactions'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? String(socialMetricsLearningPacket.summary_ru || '')
                                    : String(socialMetricsLearningPacket.summary_en || '')}
                                </div>
                              </div>
                              <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium">
                                {isRu
                                  ? `обновлено: ${Number(socialMetricsLearningPacket.collected_posts || 0)}`
                                  : `updated: ${Number(socialMetricsLearningPacket.collected_posts || 0)}`}
                              </span>
                            </div>
                            <div className="mt-2 grid gap-2 text-[11px] sm:grid-cols-3">
                              <div className="rounded-lg bg-white px-2.5 py-2">
                                <div className="font-semibold">
                                  {isRu ? 'Главная метрика' : 'Main metric'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? String(socialMetricsLearningPacket.primary_metric_ru || 'Заявки и обращения')
                                    : String(socialMetricsLearningPacket.primary_metric_en || 'Leads and inquiries')}
                                </div>
                                <div className="mt-1 text-base font-semibold">
                                  {Number(socialMetricsLearningPacket.primary_result_total || 0)}
                                </div>
                              </div>
                              <div className="rounded-lg bg-white px-2.5 py-2">
                                <div className="font-semibold">
                                  {isRu ? 'Ранние сигналы' : 'Early signals'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? `комм. ${Number(socialMetricsLearningPacket.comments || 0)}, репосты ${Number(socialMetricsLearningPacket.shares || 0)}, клики ${Number(socialMetricsLearningPacket.clicks || 0)}`
                                    : `comments ${Number(socialMetricsLearningPacket.comments || 0)}, shares ${Number(socialMetricsLearningPacket.shares || 0)}, clicks ${Number(socialMetricsLearningPacket.clicks || 0)}`}
                                </div>
                                <div className="mt-1 text-base font-semibold">
                                  {Number(socialMetricsLearningPacket.early_signal_total || 0)}
                                </div>
                              </div>
                              <div className="rounded-lg bg-white px-2.5 py-2">
                                <div className="font-semibold">
                                  {isRu ? 'Для проверки' : 'Need attention'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? `ошибок: ${Number(socialMetricsLearningPacket.failed_posts || 0)}`
                                    : `failed: ${Number(socialMetricsLearningPacket.failed_posts || 0)}`}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? `заявки ${Number(socialMetricsLearningPacket.leads || 0)}, обращения ${Number(socialMetricsLearningPacket.inquiries || 0)}`
                                    : `leads ${Number(socialMetricsLearningPacket.leads || 0)}, inquiries ${Number(socialMetricsLearningPacket.inquiries || 0)}`}
                                </div>
                              </div>
                            </div>
                            <div className="mt-2 rounded-lg bg-white px-2.5 py-2 text-[11px] font-medium">
                              {isRu ? 'Следующий шаг: ' : 'Next step: '}
                              {isRu
                                ? String(socialMetricsLearningPacket.next_action_ru || '')
                                : String(socialMetricsLearningPacket.next_action_en || '')}
                            </div>
                          </div>
                        ) : null}
                        {socialRecommendation?.learning_readiness ? (
                          <div className={_socialLearningReadinessClassName(socialRecommendation.learning_readiness.confidence || '')}>
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div>
                                <div className="text-xs font-semibold">
                                  {isRu ? 'Готовность к корректировке плана' : 'Plan correction readiness'}
                                </div>
                                <div className="mt-1 text-xs leading-5">
                                  {isRu
                                    ? String(socialRecommendation.learning_readiness.summary_ru || '')
                                    : String(socialRecommendation.learning_readiness.summary_en || '')}
                                </div>
                              </div>
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium">
                                {_socialLearningConfidenceLabel(socialRecommendation.learning_readiness.confidence || '', isRu)}
                              </span>
                            </div>
                            <div className="mt-2 grid gap-2 text-[11px] sm:grid-cols-3">
                              <div>
                                <span className="font-semibold">{isRu ? 'Опубликовано: ' : 'Published: '}</span>
                                {Number(socialRecommendation.learning_readiness.published_posts || 0)}
                              </div>
                              <div>
                                <span className="font-semibold">{isRu ? 'Заявки/обращения: ' : 'Leads/inquiries: '}</span>
                                {Number(socialRecommendation.learning_readiness.posts_with_primary_result || 0)}
                              </div>
                              <div>
                                <span className="font-semibold">{isRu ? 'Нужно закрыть: ' : 'Need action: '}</span>
                                {Number(socialRecommendation.learning_readiness.pending_manual_or_supervised_posts || 0) + Number(socialRecommendation.learning_readiness.failed_posts || 0)}
                              </div>
                            </div>
                            <div className="mt-2 rounded-lg bg-white px-2.5 py-2 text-[11px] leading-5">
                              <div className="font-semibold">
                                {isRu ? 'Факты для следующего плана' : 'Facts for the next plan'}
                              </div>
                              <div className="mt-1 grid gap-1 sm:grid-cols-3">
                                <div>
                                  {isRu
                                    ? `заявки ${Number(socialRecommendation.learning_readiness.leads || 0)}, обращения ${Number(socialRecommendation.learning_readiness.inquiries || 0)}`
                                    : `leads ${Number(socialRecommendation.learning_readiness.leads || 0)}, inquiries ${Number(socialRecommendation.learning_readiness.inquiries || 0)}`}
                                </div>
                                <div>
                                  {isRu
                                    ? `комментарии ${Number(socialRecommendation.learning_readiness.comments || 0)}, репосты ${Number(socialRecommendation.learning_readiness.shares || 0)}, клики ${Number(socialRecommendation.learning_readiness.clicks || 0)}`
                                    : `comments ${Number(socialRecommendation.learning_readiness.comments || 0)}, shares ${Number(socialRecommendation.learning_readiness.shares || 0)}, clicks ${Number(socialRecommendation.learning_readiness.clicks || 0)}`}
                                </div>
                                <div>
                                  {isRu
                                    ? `лайки ${Number(socialRecommendation.learning_readiness.likes || 0)}, охват/просмотры ${Number(socialRecommendation.learning_readiness.reach || 0)}`
                                    : `likes ${Number(socialRecommendation.learning_readiness.likes || 0)}, reach/views ${Number(socialRecommendation.learning_readiness.reach || 0)}`}
                                </div>
                              </div>
                            </div>
                            {Number(socialRecommendation.learning_readiness.checklist?.length || 0) > 0 ? (
                              <div
                                data-testid="social-learning-readiness-checklist"
                                className="mt-2 rounded-lg bg-white px-2.5 py-2 text-[11px] leading-5"
                              >
                                <div className="font-semibold">
                                  {isRu ? 'Чеклист перед корректировкой' : 'Checklist before changing the plan'}
                                </div>
                                <div className="mt-2 grid gap-2 md:grid-cols-2">
                                  {(socialRecommendation.learning_readiness.checklist || []).map((item) => {
                                    const itemStatus = String(item.status || '').trim();
                                    const tone = itemStatus === 'done'
                                      ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
                                      : itemStatus === 'attention'
                                        ? 'border-amber-100 bg-amber-50 text-amber-900'
                                        : itemStatus === 'current'
                                          ? 'border-sky-100 bg-sky-50 text-sky-900'
                                          : 'border-slate-200 bg-slate-50 text-slate-700';
                                    return (
                                      <div
                                        key={String(item.key || item.label_ru || item.label_en || '')}
                                        className={`rounded-lg border px-2.5 py-2 ${tone}`}
                                      >
                                        <div className="flex items-center justify-between gap-2">
                                          <span className="font-semibold">
                                            {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                          </span>
                                          <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium">
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
                            <div className="mt-2 text-[11px] leading-5">
                              {isRu
                                ? String(socialRecommendation.learning_readiness.next_action_ru || '')
                                : String(socialRecommendation.learning_readiness.next_action_en || '')}
                            </div>
                          </div>
                        ) : null}
                        {socialPrimaryResultCount > 0 || socialEarlySignalCount > 0 ? (
                          <div className="mt-3 rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-emerald-900">
                          <div className="font-semibold text-emerald-950">
                            {socialPrimaryResultCount > 0
                              ? (isRu
                                ? `Есть заявки/обращения: ${socialPrimaryResultCount}`
                                : `Leads/inquiries recorded: ${socialPrimaryResultCount}`)
                              : (isRu
                                ? `Есть ранние сигналы: ${socialEarlySignalCount}`
                                : `Early signals recorded: ${socialEarlySignalCount}`)}
                          </div>
                          <div className="mt-1 text-emerald-800">
                            {isRu
                              ? 'Нажмите «Предложить изменения», чтобы пересчитать следующую неделю по этим фактам. LocalOS не применит изменения без подтверждения.'
                              : 'Click “Suggest changes” to recalculate next week from these facts. LocalOS will not apply changes without confirmation.'}
                          </div>
                        </div>
                      ) : null}
                      {Number(socialRecommendation?.recommendation?.signal_priority?.length || 0) > 0 ? (
                        <div className="mt-3 grid gap-2 sm:grid-cols-4">
                          {(socialRecommendation?.recommendation?.signal_priority || []).slice(0, 4).map((signal) => (
                            <div key={String(signal.key || signal.rank || '')} className="rounded-lg border border-emerald-100 bg-white px-2.5 py-2">
                              <div className="text-[11px] font-medium text-emerald-700">
                                #{Number(signal.rank || 0)} · {isRu ? String(signal.role_ru || '') : String(signal.role_en || '')}
                              </div>
                              <div className="mt-1 flex items-baseline justify-between gap-2">
                                <span className="text-xs font-semibold text-emerald-950">
                                  {isRu ? String(signal.label_ru || signal.key || '') : String(signal.label_en || signal.key || '')}
                                </span>
                                <span className="text-sm font-semibold text-emerald-900">
                                  {Number(signal.value || 0)}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {socialMetricsSourceSummary.length > 0 ? (
                        <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-700">
                          <div className="font-semibold text-slate-950">
                            {isRu ? 'Как считаем результат' : 'How results are counted'}
                          </div>
                          <div className="mt-1 text-slate-500">
                            {isRu
                              ? 'Заявки и обращения всегда главнее охватов. Где API-метрик нет, LocalOS честно ждёт ручную отметку результата.'
                              : 'Leads and inquiries always rank above reach. Where API metrics are unavailable, LocalOS clearly uses manual result marking.'}
                          </div>
                          <div className="mt-2 grid gap-2 md:grid-cols-2">
                            {socialMetricsSourceSummary.map((item) => (
                              <div key={item.platform} className="rounded-lg bg-slate-50 px-2.5 py-2">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-semibold text-slate-900">{item.label}</span>
                                  <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">
                                    {isRu
                                      ? `опубликовано ${item.published}/${item.posts}`
                                      : `published ${item.published}/${item.posts}`}
                                  </span>
                                </div>
                                <div className="mt-1 text-[11px] leading-4 text-slate-600">
                                  {isRu ? item.sourceRu : item.sourceEn}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => { void collectSocialPostMetricsForBusiness(); }}
                        disabled={socialBusyAction === 'collect-metrics' || !Number(socialSummary?.published || 0)}
                      >
                        {socialBusyAction === 'collect-metrics'
                          ? (isRu ? 'Собираем...' : 'Collecting...')
                          : `${isRu ? 'Собрать реакции один раз' : 'Collect reactions once'} · ${Number(socialSummary?.published || 0)}`}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={selectPublishedSocialPostsForResult}
                        disabled={!Number(socialSummary?.published || 0)}
                      >
                        {`${isRu ? 'Отметить заявки/обращения' : 'Record leads/inquiries'} · ${Number(socialSummary?.published || 0)}`}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => { void recommendNextSocialPlan(); }}
                        disabled={socialBusyAction === 'recommend'}
                      >
                        {socialBusyAction === 'recommend'
                          ? (isRu ? 'Считаем...' : 'Calculating...')
                          : (isRu ? 'Предложить изменения' : 'Suggest changes')}
                      </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => { void applySocialPlanRecommendation(); }}
                          disabled={
                            socialBusyAction === 'apply-recommendation'
                            || !Number(socialRecommendation?.proposed_changes?.length || 0)
                            || !socialRecommendationApproved
                            || socialRecommendation?.learning_readiness?.safe_to_apply_recommendation === false
                          }
                        >
                        {socialBusyAction === 'apply-recommendation'
                          ? (isRu ? 'Применяем...' : 'Applying...')
                          : (isRu ? 'Применить после подтверждения' : 'Apply with approval')}
                      </Button>
                    </div>
                  </div>
                  {Number(socialRecommendation?.recommendation?.winning_topics?.length || 0)
                    || Number(socialRecommendation?.recommendation?.weak_channels?.length || 0)
                    || Number(socialRecommendation?.recommendation?.no_result_topics?.length || 0)
                    || Number(socialRecommendation?.recommendation?.owner_next_steps?.length || 0)
                    || Number(socialRecommendation?.recommendation?.cta_suggestions?.length || 0)
                    || Number(socialRecommendation?.recommendation?.frequency_suggestions?.length || 0) ? (
                    <div className="mt-3 grid gap-2 lg:grid-cols-3">
                      {Number(socialRecommendation?.recommendation?.owner_next_steps?.length || 0) > 0 ? (
                        <div className="rounded-lg border border-emerald-200 bg-white px-3 py-2 lg:col-span-3">
                          <div className="text-xs font-semibold text-emerald-950">
                            {isRu ? 'Что сделать первым' : 'What to do first'}
                          </div>
                          <div className="mt-2 grid gap-2 md:grid-cols-2">
                            {(socialRecommendation?.recommendation?.owner_next_steps || []).slice(0, 4).map((step, index) => (
                              <div key={String(step.key || index)} className="flex gap-2 rounded-md bg-emerald-50 px-2.5 py-2 text-xs leading-5 text-emerald-900">
                                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-semibold text-emerald-800">
                                  {Number(step.priority || index + 1)}
                                </span>
                                <span>{isRu ? String(step.ru || '') : String(step.en || '')}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {Number(socialRecommendation?.recommendation?.winning_topics?.length || 0) > 0 ? (
                        <div className="rounded-lg border border-emerald-100 bg-white px-3 py-2">
                          <div className="text-xs font-semibold text-emerald-950">
                            {isRu ? 'Что сработало' : 'What worked'}
                          </div>
                          <div className="mt-2 space-y-2">
                            {(socialRecommendation?.recommendation?.winning_topics || []).slice(0, 3).map((topic) => (
                              <div key={String(topic.item_id || topic.theme || '')} className="text-xs leading-5 text-emerald-800">
                                <span className="font-medium">{String(topic.theme || (isRu ? 'Тема плана' : 'Plan topic'))}</span>
                                <span className="block text-[11px] text-emerald-700">
                                  {_socialInsightMetricLine(topic.metrics, isRu)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {Number(socialRecommendation?.recommendation?.weak_channels?.length || 0) > 0 ? (
                        <div className="rounded-lg border border-amber-100 bg-white px-3 py-2">
                          <div className="text-xs font-semibold text-amber-950">
                            {isRu ? 'Слабые каналы' : 'Weak channels'}
                          </div>
                          <div className="mt-2 space-y-2">
                            {(socialRecommendation?.recommendation?.weak_channels || []).slice(0, 3).map((channel) => (
                              <div key={String(channel.platform || channel.platform_label || '')} className="text-xs leading-5 text-amber-800">
                                <span className="font-medium">{String(channel.platform_label || _socialPlatformLabel(String(channel.platform || ''), isRu))}</span>
                                <span className="block">{isRu ? String(channel.reason_ru || '') : String(channel.reason_en || '')}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {Number(socialRecommendation?.recommendation?.no_result_topics?.length || 0) > 0 ? (
                        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                          <div className="text-xs font-semibold text-slate-950">
                            {isRu ? 'Темы без результата' : 'No-result topics'}
                          </div>
                          <div className="mt-2 space-y-2">
                            {(socialRecommendation?.recommendation?.no_result_topics || []).slice(0, 3).map((topic) => (
                              <div key={String(topic.item_id || topic.theme || '')} className="text-xs leading-5 text-slate-700">
                                {String(topic.theme || (isRu ? 'Тема плана' : 'Plan topic'))}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      <div className="rounded-lg border border-emerald-100 bg-white px-3 py-2 lg:col-span-3">
                        <div className="grid gap-3 md:grid-cols-2">
                          <div>
                            <div className="text-xs font-semibold text-emerald-950">
                              {isRu ? 'CTA' : 'CTA'}
                            </div>
                            <div className="mt-1 space-y-1 text-xs leading-5 text-emerald-800">
                              {(socialRecommendation?.recommendation?.cta_suggestions || []).slice(0, 2).map((suggestion, index) => (
                                <div key={`cta-${index}`}>{isRu ? String(suggestion.ru || '') : String(suggestion.en || '')}</div>
                              ))}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs font-semibold text-emerald-950">
                              {isRu ? 'Частота' : 'Frequency'}
                            </div>
                            <div className="mt-1 space-y-1 text-xs leading-5 text-emerald-800">
                              {(socialRecommendation?.recommendation?.frequency_suggestions || []).slice(0, 2).map((suggestion, index) => (
                                <div key={`frequency-${index}`}>{isRu ? String(suggestion.ru || '') : String(suggestion.en || '')}</div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {Number(socialRecommendation?.proposed_changes?.length || 0) > 0 ? (
                    <>
                      <div className="mt-3 rounded-lg border border-emerald-100 bg-white px-3 py-3">
                        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                          <div>
                            <div className="text-xs font-semibold text-emerald-950">
                              {isRu ? 'Предпросмотр изменений плана' : 'Plan changes preview'}
                            </div>
                            <div className="mt-1 text-xs leading-5 text-emerald-800">
                              {isRu
                                ? 'LocalOS покажет, какие будущие цели изменятся. Уже опубликованные и прошлые пункты не перезаписываются.'
                                : 'LocalOS shows which future goals will change. Published and past items are not overwritten.'}
                            </div>
                          </div>
                          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-800">
                            {isRu
                              ? `изменений: ${Number(socialRecommendation?.proposed_changes?.length || 0)}`
                              : `changes: ${Number(socialRecommendation?.proposed_changes?.length || 0)}`}
                          </span>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2">
                          {(socialRecommendation?.proposed_changes || []).slice(0, 4).map((change) => (
                            <div key={String(change.item_id || change.theme || '')} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                              <div className="line-clamp-1 text-xs font-semibold text-slate-950">
                                {String(change.theme || (isRu ? 'Тема плана' : 'Plan topic'))}
                              </div>
                              <div className="mt-2 grid gap-2 text-[11px] leading-4 text-slate-700">
                                <div>
                                  <span className="font-semibold text-slate-500">{isRu ? 'Сейчас: ' : 'Now: '}</span>
                                  {String(change.current_goal || (isRu ? 'цель не задана' : 'no goal set'))}
                                </div>
                                <div>
                                  <span className="font-semibold text-emerald-700">{isRu ? 'Станет: ' : 'Will become: '}</span>
                                  {String(change.proposed_goal || '')}
                                </div>
                              </div>
                              <div className="mt-2 text-xs leading-5 text-emerald-800">
                                {isRu ? String(change.reason_ru || '') : String(change.reason_en || '')}
                              </div>
                              <div className="mt-1 text-[11px] text-slate-500">
                                {isRu
                                  ? `сигналы: заявки ${Number(change.metrics?.leads || 0)}, обращения ${Number(change.metrics?.inquiries || 0)}, комментарии ${Number(change.metrics?.comments || 0)}, охват ${Number(change.metrics?.reach || 0)}`
                                  : `signals: leads ${Number(change.metrics?.leads || 0)}, inquiries ${Number(change.metrics?.inquiries || 0)}, comments ${Number(change.metrics?.comments || 0)}, reach ${Number(change.metrics?.reach || 0)}`}
                              </div>
                              {change.channel_breakdown?.summary_ru || change.channel_breakdown?.summary_en ? (
                                <div className="mt-2 rounded-md border border-emerald-100 bg-white px-2 py-1.5 text-[11px] leading-5 text-emerald-900">
                                  <div className="font-semibold text-emerald-950">
                                    {isRu ? 'По каналам' : 'By channel'}
                                  </div>
                                  <div>
                                    {isRu
                                      ? String(change.channel_breakdown?.summary_ru || '')
                                      : String(change.channel_breakdown?.summary_en || '')}
                                  </div>
                                  {Number(change.channel_breakdown?.best_channels?.length || 0) > 0 ? (
                                    <div className="mt-1 text-emerald-800">
                                      {(change.channel_breakdown?.best_channels || []).slice(0, 2).map((channel) => (
                                        <div key={`best:${String(change.item_id || '')}:${String(channel.platform || channel.platform_label || '')}`}>
                                          + {String(channel.platform_label || _socialPlatformLabel(String(channel.platform || ''), isRu))}: {_socialInsightMetricLine(channel.metrics, isRu)}
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
                                  {Number(change.channel_breakdown?.weak_channels?.length || 0) > 0 ? (
                                    <div className="mt-1 text-amber-800">
                                      {(change.channel_breakdown?.weak_channels || []).slice(0, 2).map((channel) => (
                                        <div key={`weak:${String(change.item_id || '')}:${String(channel.platform || channel.platform_label || '')}`}>
                                          - {String(channel.platform_label || _socialPlatformLabel(String(channel.platform || ''), isRu))}: {isRu ? String(channel.reason_ru || '') : String(channel.reason_en || '')}
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                        {socialRecommendation?.application_preview ? (
                          <div
                            data-testid="social-recommendation-application-preview"
                            className="mt-3 rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-900"
                          >
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div>
                                <div className="font-semibold text-sky-950">
                                  {isRu ? 'Что реально изменится' : 'What will actually change'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? String(socialRecommendation.application_preview.summary_ru || '')
                                    : String(socialRecommendation.application_preview.summary_en || '')}
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                <span className="rounded-full bg-white px-2 py-0.5 font-medium text-sky-800">
                                  {isRu
                                    ? `изменится: ${Number(socialRecommendation.application_preview.applicable_count || 0)}`
                                    : `changes: ${Number(socialRecommendation.application_preview.applicable_count || 0)}`}
                                </span>
                                <span className="rounded-full bg-white px-2 py-0.5 font-medium text-sky-800">
                                  {isRu
                                    ? `пропустится: ${Number(socialRecommendation.application_preview.skipped_count || 0)}`
                                    : `skipped: ${Number(socialRecommendation.application_preview.skipped_count || 0)}`}
                                </span>
                              </div>
                            </div>
                            {Number(socialRecommendation.application_preview.items?.length || 0) > 0 ? (
                              <div className="mt-2 grid gap-1.5 md:grid-cols-2">
                                {(socialRecommendation.application_preview.items || []).slice(0, 4).map((item) => (
                                  <div
                                    key={`application-preview:${String(item.item_id || item.theme || '')}`}
                                    className={[
                                      'rounded-md border px-2 py-1.5',
                                      item.applicable
                                        ? 'border-emerald-100 bg-white text-emerald-900'
                                        : 'border-amber-100 bg-white text-amber-900',
                                    ].join(' ')}
                                  >
                                    <div className="flex items-start justify-between gap-2">
                                      <span className="line-clamp-1 font-semibold">
                                        {String(item.theme || item.item_id || (isRu ? 'Пункт плана' : 'Plan item'))}
                                      </span>
                                      <span className="shrink-0 rounded-full bg-slate-50 px-2 py-0.5 text-[10px] font-medium">
                                        {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                      </span>
                                    </div>
                                    <div className="mt-1 text-[11px]">
                                      {isRu
                                        ? `дата: ${String(item.scheduled_for || 'не задана')}${item.status ? ` · статус: ${String(item.status)}` : ''}`
                                        : `date: ${String(item.scheduled_for || 'not set')}${item.status ? ` · status: ${String(item.status)}` : ''}`}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                        {Number(socialRecommendation?.proposed_changes?.length || 0) > 4 ? (
                          <div className="mt-2 text-[11px] text-emerald-700">
                            {isRu
                              ? `Ещё ${Number(socialRecommendation?.proposed_changes?.length || 0) - 4} изменений будут применены по тому же правилу.`
                              : `${Number(socialRecommendation?.proposed_changes?.length || 0) - 4} more changes will be applied by the same rule.`}
                          </div>
                        ) : null}
                      </div>
                      <label className="mt-3 flex items-start gap-2 rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-emerald-900">
                        <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 rounded border-emerald-300 text-emerald-700 focus:ring-emerald-500"
                            checked={socialRecommendationApproved}
                            disabled={socialRecommendation?.learning_readiness?.safe_to_apply_recommendation === false}
                            onChange={(event) => setSocialRecommendationApproved(event.target.checked)}
                          />
                        <span>
                          {isRu
                            ? 'Я проверил предпросмотр выше и подтверждаю применение только к будущим пунктам плана.'
                            : 'I reviewed the preview above and approve applying it only to future plan items.'}
                        </span>
                      </label>
                      {socialRecommendation?.learning_readiness?.safe_to_apply_recommendation === false ? (
                        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                          <div className="font-semibold text-amber-950">
                            {isRu ? 'Почему нельзя применить сейчас' : 'Why apply is blocked'}
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? String(socialRecommendation.learning_readiness.apply_blocked_reason_ru || socialRecommendation.learning_readiness.next_action_ru || '')
                              : String(socialRecommendation.learning_readiness.apply_blocked_reason_en || socialRecommendation.learning_readiness.next_action_en || '')}
                          </div>
                        </div>
                      ) : null}
                    </>
                  ) : null}
                </div>
    </>
  );
};
