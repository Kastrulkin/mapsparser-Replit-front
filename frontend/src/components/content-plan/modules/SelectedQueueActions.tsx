import React from 'react';
import { Button } from '@/components/ui/button';
import { CheckSquare, Globe, Sparkles } from 'lucide-react';

export const SelectedQueueActions = ({ scope }) => {
  const {
    isRu, bulkBusyAction, socialBulkPublishRehearsal, selectedItems, selectedDraftCandidates, selectedNewsCandidates, selectedSocialPosts, selectedSocialNeedsReview,
    selectedSocialDirtyReviewPosts, selectedSocialCanQueue, selectedSocialCanMarkPublished, selectedSocialCanRecordResults, selectedSocialQueueApiWarnings, clearSelectedItems, rehearseSelectedSocialPosts, prepareSelectedSocialPosts,
    approveSelectedSocialPosts, queueSelectedSocialPosts, markSelectedSocialPostsPublished, recordSelectedSocialPostAttribution, runSelectedGenerateDrafts, runSelectedCreateNews
  } = scope;
  return (
    <>
              {selectedItems.length > 0 ? (
                <div className="flex w-full flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-3">
                  <div className="mr-auto flex items-center gap-2 text-sm font-medium text-slate-900">
                    <CheckSquare className="h-4 w-4" />
                    {isRu ? `Выбрано: ${selectedItems.length}` : `Selected: ${selectedItems.length}`}
                  </div>
                  <div className="w-full rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-900">
                    <div className="font-semibold text-blue-950">
                      {isRu ? 'Маршрут выбранных постов' : 'Selected post path'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? `Проверить предпросмотр: ${selectedSocialNeedsReview.length} · поставить в расписание: ${selectedSocialCanQueue.length} · ручное/контролируемое размещение: ${selectedSocialCanMarkPublished.length} · отметить результат: ${selectedSocialCanRecordResults.length}.`
                        : `Review preview: ${selectedSocialNeedsReview.length} · queue on schedule: ${selectedSocialCanQueue.length} · manual/supervised placement: ${selectedSocialCanMarkPublished.length} · record result: ${selectedSocialCanRecordResults.length}.`}
                    </div>
                    <div className="mt-1 text-blue-800">
                      {selectedSocialNeedsReview.length > 0
                        ? (isRu
                          ? 'Сначала откройте карточку темы ниже, проверьте “Предпросмотр перед подтверждением”, затем нажмите “Подтвердить посты”.'
                          : 'First open a topic card below, review “Preview before approval”, then click “Approve posts”.')
                        : selectedSocialCanQueue.length > 0
                          ? (isRu
                            ? 'Посты подтверждены: следующий безопасный шаг - “Поставить в расписание”.'
                            : 'Posts are approved: the next safe step is “Queue on schedule”.')
                          : selectedSocialCanMarkPublished.length > 0
                            ? (isRu
                              ? 'Для этих каналов нужен ручной или контролируемый финал: проверьте задачу и отметьте размещение.'
                              : 'These channels need a manual or supervised finish: review the task and mark placement.')
                            : selectedSocialCanRecordResults.length > 0
                              ? (isRu
                                ? 'Посты опубликованы: отметьте заявки, обращения и ранние реакции, чтобы LocalOS корректировал следующий план по реальному результату.'
                                : 'Posts are published: record leads, inquiries, and early reactions so LocalOS can adjust the next plan by real outcomes.')
                              : (isRu
                                ? 'Если кнопки ниже показывают 0, сначала подготовьте каналы для выбранных тем.'
                                : 'If the buttons below show 0, prepare channels for the selected topics first.')}
                    </div>
                  </div>
                  {selectedSocialQueueApiWarnings.length > 0 ? (
                    <div className="w-full rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                      <div className="font-semibold text-amber-950">
                        {isRu ? 'Перед расписанием эти API-каналы не готовы' : 'These API channels are not ready before queueing'}
                      </div>
                      <div className="mt-1">
                        {isRu
                          ? 'Расписание можно сохранить, но исполнитель не будет публиковать эти каналы, пока не появятся ключи, права, локация или адаптер.'
                          : 'Queue can still be saved, but the worker will not publish these channels until keys, permissions, location, or adapter are ready.'}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedSocialQueueApiWarnings.slice(0, 6).map((warning) => (
                          <span
                            key={`selected-api-warning:${warning.postId}:${warning.platform}`}
                            className="rounded-full bg-white px-2.5 py-1 font-medium text-amber-800"
                          >
                            {warning.label} · {warning.status}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {socialBulkPublishRehearsal ? (
                    <div
                      data-testid="social-bulk-publish-rehearsal"
                      className={[
                        'w-full rounded-xl border px-3 py-3 text-xs leading-5',
                        Number(socialBulkPublishRehearsal.summary?.manual_or_blocked || 0) > 0
                          ? 'border-amber-200 bg-amber-50 text-amber-900'
                          : 'border-emerald-200 bg-emerald-50 text-emerald-900',
                      ].join(' ')}
                    >
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className={Number(socialBulkPublishRehearsal.summary?.manual_or_blocked || 0) > 0 ? 'font-semibold text-amber-950' : 'font-semibold text-emerald-950'}>
                            {isRu ? 'Проверка запуска выбранных' : 'Selected launch check'}
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? String(socialBulkPublishRehearsal.summary?.message_ru || '')
                              : String(socialBulkPublishRehearsal.summary?.message_en || '')}
                          </div>
                          <div className="mt-1 font-medium">
                            {isRu
                              ? String(socialBulkPublishRehearsal.summary?.next_action_ru || '')
                              : String(socialBulkPublishRehearsal.summary?.next_action_en || '')}
                          </div>
                        </div>
                        <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold">
                          {isRu ? 'наружу ничего не отправлено' : 'nothing sent externally'}
                        </span>
                      </div>
                      <div className="mt-2 grid gap-2 sm:grid-cols-4">
                        <div className="rounded-lg bg-white/70 px-2.5 py-2">
                          <div className="font-semibold">{Number(socialBulkPublishRehearsal.summary?.ready || 0)}</div>
                          <div>{isRu ? 'готово' : 'ready'}</div>
                        </div>
                        <div className="rounded-lg bg-white/70 px-2.5 py-2">
                          <div className="font-semibold">{Number(socialBulkPublishRehearsal.summary?.api_ready || 0)}</div>
                          <div>{isRu ? 'API' : 'API'}</div>
                        </div>
                        <div className="rounded-lg bg-white/70 px-2.5 py-2">
                          <div className="font-semibold">{Number(socialBulkPublishRehearsal.summary?.supervised_ready || 0)}</div>
                          <div>{isRu ? 'контроль' : 'supervised'}</div>
                        </div>
                        <div className="rounded-lg bg-white/70 px-2.5 py-2">
                          <div className="font-semibold">{Number(socialBulkPublishRehearsal.summary?.manual_or_blocked || 0)}</div>
                          <div>{isRu ? 'внимание' : 'attention'}</div>
                        </div>
                      </div>
                      {Number(socialBulkPublishRehearsal.failed?.length || 0) > 0 ? (
                        <div className="mt-2 rounded-lg bg-white/70 px-2.5 py-2 text-[11px]">
                          {isRu
                            ? `Не удалось проверить: ${Number(socialBulkPublishRehearsal.failed?.length || 0)}.`
                            : `Could not check: ${Number(socialBulkPublishRehearsal.failed?.length || 0)}.`}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <Button
                    variant="outline"
                    onClick={() => { void runSelectedGenerateDrafts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedDraftCandidates.length === 0}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {bulkBusyAction === 'selected-drafts'
                      ? (isRu ? 'Генерируем тексты...' : 'Generating texts...')
                      : `${isRu ? 'Сгенерировать тексты' : 'Generate texts'} · ${selectedDraftCandidates.length}`}
                  </Button>
                  <Button
                    onClick={runSelectedCreateNews}
                    disabled={Boolean(bulkBusyAction) || selectedNewsCandidates.length === 0}
                  >
                    {bulkBusyAction === 'selected-news'
                      ? (isRu ? 'Создаём публикации...' : 'Creating publications...')
                      : `${isRu ? 'Создать выбранные публикации' : 'Create selected publications'} · ${selectedNewsCandidates.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void prepareSelectedSocialPosts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedItems.length === 0}
                  >
                    <Globe className="mr-2 h-4 w-4" />
                    {bulkBusyAction === 'selected-social-prepare'
                      ? (isRu ? 'Готовим каналы...' : 'Preparing channels...')
                      : `${isRu ? 'Подготовить каналы' : 'Prepare channels'} · ${selectedItems.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void rehearseSelectedSocialPosts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialPosts.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-rehearsal'
                      ? (isRu ? 'Проверяем запуск...' : 'Checking launch...')
                      : `${isRu ? 'Проверить запуск выбранных' : 'Check selected launch'} · ${selectedSocialPosts.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void approveSelectedSocialPosts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialNeedsReview.length === 0 || selectedSocialDirtyReviewPosts.length > 0}
                  >
                    {bulkBusyAction === 'selected-social-approve'
                      ? (isRu ? 'Подтверждаем...' : 'Approving...')
                      : `${isRu ? 'Подтвердить посты' : 'Approve posts'} · ${selectedSocialNeedsReview.length}`}
                  </Button>
                  {selectedSocialDirtyReviewPosts.length > 0 ? (
                    <div className="w-full rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
                      {isRu
                        ? `Сначала сохраните правки текста: ${selectedSocialDirtyReviewPosts.length}. После этого можно подтверждать выбранные посты.`
                        : `Save copy edits first: ${selectedSocialDirtyReviewPosts.length}. Then selected posts can be approved.`}
                    </div>
                  ) : null}
                  <Button
                    variant="outline"
                    onClick={() => { void queueSelectedSocialPosts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanQueue.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-queue'
                      ? (isRu ? 'Ставим в расписание...' : 'Queueing...')
                      : `${isRu ? 'Поставить в расписание' : 'Queue on schedule'} · ${selectedSocialCanQueue.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void markSelectedSocialPostsPublished(); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanMarkPublished.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-manual'
                      ? (isRu ? 'Отмечаем...' : 'Marking...')
                      : `${isRu ? 'Отметить размещёнными' : 'Mark published'} · ${selectedSocialCanMarkPublished.length}`}
                  </Button>
                  {selectedSocialCanRecordResults.length > 0 ? (
                    <div
                      data-testid="social-bulk-attribution-actions"
                      className="w-full rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-900"
                    >
                      <div className="font-semibold text-emerald-950">
                        {isRu ? 'Отметить результат по выбранным публикациям' : 'Record result for selected posts'}
                      </div>
                      <div className="mt-1">
                        {isRu
                          ? 'Сначала отмечайте заявки и обращения. Комментарии, репосты, клики, лайки и просмотры помогают понять формат, но стоят ниже бизнес-результата.'
                          : 'Record leads and inquiries first. Comments, shares, clicks, likes, and views help evaluate the format, but rank below business outcomes.'}
                      </div>
                    </div>
                  ) : null}
                  <span className="w-full text-xs font-semibold uppercase tracking-wide text-emerald-700">
                    {isRu ? 'Главный результат' : 'Primary result'}
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('lead'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-lead'
                      ? (isRu ? 'Отмечаем заявки...' : 'Recording leads...')
                      : `${isRu ? 'Была заявка' : 'Record lead'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('inquiry'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-inquiry'
                      ? (isRu ? 'Отмечаем обращения...' : 'Recording inquiries...')
                      : `${isRu ? 'Было обращение' : 'Record inquiry'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <span className="w-full text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {isRu ? 'Ранние сигналы' : 'Early signals'}
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('comment'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-comment'
                      ? (isRu ? 'Отмечаем комментарии...' : 'Recording comments...')
                      : `${isRu ? 'Был комментарий' : 'Record comment'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('share'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-share'
                      ? (isRu ? 'Отмечаем репосты...' : 'Recording shares...')
                      : `${isRu ? 'Был репост' : 'Record share'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('click'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-click'
                      ? (isRu ? 'Отмечаем клики...' : 'Recording clicks...')
                      : `${isRu ? 'Был клик' : 'Record click'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('like'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-like'
                      ? (isRu ? 'Отмечаем лайки...' : 'Recording likes...')
                      : `${isRu ? 'Был лайк' : 'Record like'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('view'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-view'
                      ? (isRu ? 'Отмечаем просмотры...' : 'Recording views...')
                      : `${isRu ? 'Был просмотр' : 'Record view'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button type="button" variant="ghost" onClick={clearSelectedItems}>
                    {isRu ? 'Снять выбор' : 'Clear'}
                  </Button>
                </div>
              ) : null}
    </>
  );
};
