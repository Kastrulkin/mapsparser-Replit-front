import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

type Option = {
  value: string;
  label: string;
};

type PartnershipDraftItem = {
  id: string;
  lead_id: string;
  lead_name?: string;
  channel?: string;
  status?: string;
  generated_text?: string;
  edited_text?: string;
  approved_text?: string;
};

type PartnershipQueueItem = {
  id: string;
  lead_name?: string;
  delivery_status?: string;
  error_text?: string;
  channel?: string;
  latest_outcome?: string | null;
  latest_human_outcome?: string | null;
};

type PartnershipBatchItem = {
  id: string;
  status: string;
  items?: PartnershipQueueItem[];
};

type PartnershipReactionItem = {
  id: string;
  lead_id: string;
  lead_name?: string;
  batch_id?: string;
  channel?: string;
  delivery_status?: string;
  raw_reply?: string | null;
  classified_outcome?: string | null;
  human_confirmed_outcome?: string | null;
};

type DraftsSectionProps = {
  drafts: PartnershipDraftItem[];
  selectedDraftIds: string[];
  draftView: string;
  draftViewOptions: readonly Option[];
  loading: boolean;
  onDraftViewChange: (value: string) => void;
  onRefresh: () => void;
  onBulkApprove: () => void;
  onBulkDelete: () => void;
  onToggleAll: (checked: boolean) => void;
  onToggleDraft: (id: string, checked: boolean) => void;
  onDraftTextChange: (id: string, value: string) => void;
  onApproveDraft: (id: string, text: string) => void;
};

type QueueSectionProps = {
  batches: PartnershipBatchItem[];
  selectedQueueIds: string[];
  queueView: string;
  queueViewOptions: readonly Option[];
  bulkQueueStatus: string;
  queueReadyDraftsCount: number;
  loading: boolean;
  sendQueueBusy: Record<string, unknown>;
  outcomeOptions: readonly string[];
  onQueueViewChange: (value: string) => void;
  onRefresh: () => void;
  onCreateBatch: () => void;
  onBulkQueueStatusChange: (value: string) => void;
  onBulkUpdateDelivery: () => void;
  onBulkDeleteQueueItems: () => void;
  onToggleAll: (checked: boolean) => void;
  onToggleQueueItem: (id: string, checked: boolean) => void;
  onApproveBatch: (id: string) => void;
  onRecordReaction: (queueId: string, outcome?: string) => void;
};

type SentSectionProps = {
  reactions: PartnershipReactionItem[];
  reactionView: string;
  reactionViewOptions: readonly Option[];
  loading: boolean;
  reactionBusy: Record<string, unknown>;
  outcomeOptions: readonly string[];
  onReactionViewChange: (value: string) => void;
  onRefresh: () => void;
  onConfirmReaction: (reactionId: string, outcome: string) => void;
};

function getQueueItemIds(batches: PartnershipBatchItem[]) {
  return batches.flatMap((batch) => (batch.items || []).map((item) => item.id));
}

const outcomeLabel = (value?: string | null) => {
  if (value === 'positive') return 'Интерес';
  if (value === 'question') return 'Вопрос';
  if (value === 'no_response') return 'Нет ответа';
  if (value === 'hard_no') return 'Отказ';
  return value || '—';
};

export function PartnershipDraftsSection({
  drafts,
  selectedDraftIds,
  draftView,
  draftViewOptions,
  loading,
  onDraftViewChange,
  onRefresh,
  onBulkApprove,
  onBulkDelete,
  onToggleAll,
  onToggleDraft,
  onDraftTextChange,
  onApproveDraft,
}: DraftsSectionProps) {
  return (
    <div className="space-y-4 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">Черновики сообщений ({drafts.length})</h2>
          <p className="mt-1 text-sm text-slate-500">Проверьте текст перед отправкой. Здесь оператор принимает финальное решение.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={draftView} onValueChange={onDraftViewChange}>
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="Фильтр черновиков" />
            </SelectTrigger>
            <SelectContent>
              {draftViewOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={onRefresh} disabled={loading}>
            Обновить
          </Button>
        </div>
      </div>

      {drafts.length > 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="text-xs text-muted-foreground">Выбрано черновиков: {selectedDraftIds.length}</div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={onBulkApprove} disabled={loading || selectedDraftIds.length === 0}>
                Утвердить выбранные
              </Button>
              <Button variant="outline" onClick={onBulkDelete} disabled={loading || selectedDraftIds.length === 0}>
                Удалить выбранные
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {drafts.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-muted-foreground">
          Черновиков пока нет. Перейдите в воронку, выберите партнёров и подготовьте первое сообщение.
        </div>
      ) : (
        <>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={drafts.length > 0 && drafts.every((draft) => selectedDraftIds.includes(draft.id))}
              onChange={(event) => onToggleAll(event.target.checked)}
            />
            Выбрать все черновики в текущем фильтре
          </label>
          {drafts.map((draft) => {
            const draftText = draft.approved_text || draft.edited_text || draft.generated_text || '';
            return (
              <div key={draft.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start gap-3">
                  <input
                    className="mt-1"
                    type="checkbox"
                    checked={selectedDraftIds.includes(draft.id)}
                    onChange={(event) => onToggleDraft(draft.id, event.target.checked)}
                  />
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-foreground">{draft.lead_name || draft.lead_id}</div>
                    <div className="mb-2 text-xs text-muted-foreground">
                      Статус: {draft.status || '—'} · канал: {draft.channel || '—'}
                    </div>
                    <Textarea
                      rows={5}
                      value={draftText}
                      onChange={(event) => onDraftTextChange(draft.id, event.target.value)}
                    />
                    <div className="mt-2 flex justify-end">
                      <Button size="sm" onClick={() => onApproveDraft(draft.id, draftText)} disabled={loading}>
                        Утвердить для отправки
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

export function PartnershipQueueSection({
  batches,
  selectedQueueIds,
  queueView,
  queueViewOptions,
  bulkQueueStatus,
  queueReadyDraftsCount,
  loading,
  sendQueueBusy,
  outcomeOptions,
  onQueueViewChange,
  onRefresh,
  onCreateBatch,
  onBulkQueueStatusChange,
  onBulkUpdateDelivery,
  onBulkDeleteQueueItems,
  onToggleAll,
  onToggleQueueItem,
  onApproveBatch,
  onRecordReaction,
}: QueueSectionProps) {
  const queueItemIds = getQueueItemIds(batches);

  return (
    <div className="space-y-4 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">Очередь отправки ({batches.length})</h2>
          <p className="mt-1 text-sm text-slate-500">Отправка остаётся ручной и контролируемой: сначала проверка, затем фиксация результата.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={queueView} onValueChange={onQueueViewChange}>
            <SelectTrigger className="w-[230px]">
              <SelectValue placeholder="Фильтр очереди" />
            </SelectTrigger>
            <SelectContent>
              {queueViewOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={onRefresh} disabled={loading}>
            Обновить
          </Button>
          <Button onClick={onCreateBatch} disabled={loading || queueReadyDraftsCount === 0}>
            Создать очередь ({queueReadyDraftsCount})
          </Button>
        </div>
      </div>

      {batches.length > 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="text-xs text-muted-foreground">Выбрано сообщений: {selectedQueueIds.length}</div>
            <div className="flex flex-wrap gap-2">
              <Select value={bulkQueueStatus} onValueChange={onBulkQueueStatusChange}>
                <SelectTrigger className="w-[220px] bg-white">
                  <SelectValue placeholder="Delivery-статус" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sent">sent</SelectItem>
                  <SelectItem value="delivered">delivered</SelectItem>
                  <SelectItem value="failed">failed</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" onClick={onBulkUpdateDelivery} disabled={loading || selectedQueueIds.length === 0}>
                Обновить статус
              </Button>
              <Button variant="outline" onClick={onBulkDeleteQueueItems} disabled={loading || selectedQueueIds.length === 0}>
                Удалить выбранные
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {batches.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-muted-foreground">
          Очереди пока нет. Когда черновики будут утверждены, создайте очередь и проверьте её перед отправкой.
        </div>
      ) : (
        <>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={queueItemIds.length > 0 && queueItemIds.every((id) => selectedQueueIds.includes(id))}
              onChange={(event) => onToggleAll(event.target.checked)}
            />
            Выбрать все сообщения в текущем фильтре
          </label>
          {batches.map((batch) => (
            <div key={batch.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-semibold text-foreground">Группа отправки</div>
                  <div className="text-xs text-muted-foreground">
                    ID: {batch.id} · статус: {batch.status} · сообщений: {(batch.items || []).length}
                  </div>
                </div>
                {batch.status === 'draft' ? (
                  <Button size="sm" onClick={() => onApproveBatch(batch.id)} disabled={loading}>
                    Утвердить очередь
                  </Button>
                ) : null}
              </div>
              {(batch.items || []).length > 0 ? (
                <div className="mt-2 space-y-2">
                  {(batch.items || []).slice(0, 8).map((item) => (
                    <div key={item.id} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-xs text-muted-foreground">
                      <div className="flex items-start gap-2">
                        <input
                          className="mt-0.5"
                          type="checkbox"
                          checked={selectedQueueIds.includes(item.id)}
                          onChange={(event) => onToggleQueueItem(item.id, event.target.checked)}
                        />
                        <div>
                          <div>
                            {item.lead_name || item.id} · {item.channel || '—'} · {item.delivery_status || '—'}
                            {item.error_text ? ` · ${item.error_text}` : ''}
                          </div>
                          {item.latest_human_outcome || item.latest_outcome ? (
                            <div className="mt-1 text-emerald-700">
                              Результат: {outcomeLabel(item.latest_human_outcome || item.latest_outcome)}
                            </div>
                          ) : null}
                          {item.delivery_status === 'sent' && !(item.latest_human_outcome || item.latest_outcome) ? (
                            <div className="mt-2 flex flex-wrap gap-1">
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 px-2"
                                onClick={() => onRecordReaction(item.id)}
                                disabled={Boolean(sendQueueBusy[item.id])}
                              >
                                Определить результат
                              </Button>
                              {outcomeOptions.map((outcome) => (
                                <Button
                                  key={`${item.id}-${outcome}`}
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2"
                                  onClick={() => onRecordReaction(item.id, outcome)}
                                  disabled={Boolean(sendQueueBusy[item.id])}
                                >
                                  {outcomeLabel(outcome)}
                                </Button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </>
      )}
    </div>
  );
}

export function PartnershipSentSection({
  reactions,
  reactionView,
  reactionViewOptions,
  loading,
  reactionBusy,
  outcomeOptions,
  onReactionViewChange,
  onRefresh,
  onConfirmReaction,
}: SentSectionProps) {
  return (
    <div className="space-y-4 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">Отправлено и ответы ({reactions.length})</h2>
          <p className="mt-1 text-sm text-slate-500">Фиксируйте результат касания: интерес, вопрос, нет ответа или отказ.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={reactionView} onValueChange={onReactionViewChange}>
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="Фильтр результата" />
            </SelectTrigger>
            <SelectContent>
              {reactionViewOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={onRefresh} disabled={loading}>
            Обновить
          </Button>
        </div>
      </div>

      {reactions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-muted-foreground">
          Ответов пока нет. Они появятся после отправки сообщений и фиксации результата.
        </div>
      ) : (
        reactions.slice(0, 20).map((reaction) => (
          <div key={reaction.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-sm font-semibold">{reaction.lead_name || reaction.lead_id}</div>
            <div className="text-xs text-muted-foreground">
              Очередь: {reaction.batch_id || '—'} · канал: {reaction.channel || '—'} · доставка: {reaction.delivery_status || '—'}
            </div>
            {reaction.raw_reply ? (
              <div className="mt-2 whitespace-pre-wrap text-sm text-foreground">{reaction.raw_reply}</div>
            ) : null}
            <div className="mt-2 text-xs text-muted-foreground">
              Предварительно: {outcomeLabel(reaction.classified_outcome)} · Подтверждено: {outcomeLabel(reaction.human_confirmed_outcome || reaction.classified_outcome)}
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {outcomeOptions.map((outcome) => (
                <Button
                  key={`${reaction.id}-${outcome}`}
                  size="sm"
                  variant={(reaction.human_confirmed_outcome || reaction.classified_outcome) === outcome ? 'default' : 'outline'}
                  className="h-7 px-2"
                  onClick={() => onConfirmReaction(reaction.id, outcome)}
                  disabled={Boolean(reactionBusy[reaction.id])}
                >
                  {outcomeLabel(outcome)}
                </Button>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
