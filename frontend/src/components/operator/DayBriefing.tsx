import { teamWorkJson } from '@/lib/teamWorkRequest';
import { miniAppLaunchParams } from '@/lib/miniAppPlatform';
import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { OperatorVoiceInput, type VoiceSubmission } from './OperatorVoice';
import { WorkDiscussion } from '@/components/telegram/WorkDiscussion';

type Task = { id?: string; text: string; done?: boolean };
type Target = { user_id: string; platforms: string[]; tasks: Task[] };
type Draft = { id: string; focus: string; date: string; version: number; status: string; recipients: Target[] };
type Assignment = { id: string; user_id: string; status: string; version: number; payload_json: { date: string; focus: string; tasks: Task[]; tips: { main_service: string; service: string; wording: string }[]; note: string } };
type Overview = { date: string; user_id: string; can_manage: boolean; can_complete: boolean; delivery_enabled: boolean; draft?: Draft | null;
  deliveries?: { action_id: string; platform: string; state: string }[];
  members: { id: string; name: string; platforms: string[] }[]; assignments: Assignment[] };
type Preview = { approval: { action_id: string }; day_brief_preview: { delivery_enabled: boolean; messages: { user_id: string; name: string; platforms: string[]; text: string }[] } };

const deliveryLabels: Record<string,string> = {sent:'Отправлено',queued:'В очереди',failed:'Не отправлено',stopped:'Доставка остановлена',unknown:'Результат доставки неизвестен; повторная отправка остановлена'};

export function DayBriefing({ businessId, headers, channel }: { businessId: string; headers: () => Record<string, string>; channel: string }) {
  const launch = miniAppLaunchParams();
  const itemId = launch.get('item_type') === 'day_brief' ? launch.get('item_id') || '' : '';
  const [data, setData] = useState<Overview | null>(null);
  const [focus, setFocus] = useState('');
  const [targets, setTargets] = useState<Target[]>([]);
  const [saved, setSaved] = useState<Draft | null>(null);
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingCompletion, setPendingCompletion] = useState<{ action: string; task?: string; done: boolean } | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [voice, setVoice] = useState<(VoiceSubmission & { text: string }) | null>(null);
  const previewFocus = useRef<HTMLDivElement>(null);
  useEffect(() => { if (preview) previewFocus.current?.focus(); }, [preview]);
  const requestId = useRef(crypto.randomUUID());
  const lifetime = useRef(new AbortController());
  const scope = useRef(businessId + ':' + channel + ':' + itemId); scope.current = businessId + ':' + channel + ':' + itemId;
  const currentHeaders = useRef(headers); currentHeaders.current = headers;

  async function request<T>(path: string, body?: unknown): Promise<T> {
    const signal = lifetime.current.signal;
    const expectedScope = businessId + ':' + channel + ':' + itemId;
    if (scope.current !== expectedScope) throw new DOMException('Context changed', 'AbortError');
    const { response, body: value } = await teamWorkJson('/api/operator/' + path, { signal, method: body === undefined ? 'GET' : 'POST',
      headers: { ...currentHeaders.current(), 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    signal.throwIfAborted();
    if (scope.current !== expectedScope) throw new DOMException('Context changed', 'AbortError');
    if (!response.ok) {
      if ([401, 403].includes(response.status)) { setData(null); setSaved(null); setTargets([]); setFocus(''); setVoice(null); setPreview(null); }
      throw new Error(response.status >= 500 ? (value.message || 'Не удалось выполнить действие. Проверьте соединение и повторите попытку.') : (value.error || value.message || 'Не удалось открыть планёрку. Повторите.'));
    }
    return value;
  }
  async function reload(replaceDraft = false) {
    const value = await request<Overview>('day-brief?business_id=' + encodeURIComponent(businessId) + (itemId ? '&item_id=' + encodeURIComponent(itemId) : ''));
    setData(value);
    if (replaceDraft) { setSaved(value.draft || null); setFocus(value.draft?.focus || ''); setTargets(value.draft?.recipients || []); setDirty(false); }
  }
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    setData(null); setSaved(null); setFocus(''); setTargets([]); setDirty(false); setPreview(null); setVoice(null); setError(''); setNotice(''); setBusy(false); setPendingCompletion(null);
    requestId.current = crypto.randomUUID();
    void reload(true).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить планёрку.'); });
    return () => controller.abort();
    // Form edits must not reload the business or replace unsaved dictation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessId, channel, itemId]);
  function edited() { setDirty(true); setPreview(null); setNotice(''); requestId.current = crypto.randomUUID(); }
  async function perform(action: () => Promise<void>) {
    const signal = lifetime.current.signal; setBusy(true); setError('');
    try { await action(); } catch (reason) { if (!signal.aborted) setError(reason instanceof Error ? reason.message : 'Не удалось выполнить действие.'); }
    finally { if (!signal.aborted) setBusy(false); }
  }
  async function save() {
    if (saved && !dirty) return saved;
    const result = await request<{ draft: Draft }>('day-brief', { business_id: businessId, date: saved?.date || data?.date,
      version: saved?.version || 0, focus, recipients: targets, request_id: requestId.current, channel,
      ...(voice?.text === focus ? { transcription_id: voice.transcription_id, conversation_id: voice.conversation_id } : {}) });
    setSaved(result.draft); setTargets(result.draft.recipients); setDirty(false); setVoice(null);
    return result.draft;
  }
  const recipientsReady = targets.length > 0 && targets.every(target => target.platforms.length > 0 && target.tasks.some(task => task.text.trim()));
  function updateTarget(id: string, transform: (target: Target) => Target) { edited(); setTargets(values => values.map(row => row.user_id === id ? transform(row) : row)); }

  return <section className="space-y-4" aria-label="Планёрка дня">
    <div><h2 className="text-xl font-semibold">{!data ? 'Планёрка дня' : data.can_manage === false ? 'Мои задачи дня' : 'Фокус и задачи на день'}</h2><p className="text-sm text-muted-foreground">{!data ? 'Загружаем ваши задачи.' : data.can_manage === false ? 'Прочитайте свои поручения и подсказки. Отмечайте задачи по мере выполнения.' : 'Напишите или надиктуйте фокус. Затем выберите сотрудников и проверьте поручения.'}</p></div>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {error && data?.can_manage && <details className="text-sm"><summary className="cursor-pointer py-2">Если планёрка изменена в другом окне</summary><p className="text-muted-foreground">Можно загрузить сохранённую версию. Это заменит фокус и задачи в форме; сначала скопируйте несохранённые правки, если они нужны.</p><Button variant="outline" disabled={busy} onClick={() => void perform(async () => { await reload(true); setPreview(null); setVoice(null); requestId.current = crypto.randomUUID(); setNotice('Загружена сохранённая версия планёрки.'); })}>Загрузить сохранённую версию</Button></details>}
    {!data && <Button variant="outline" disabled={busy || !error} onClick={() => void perform(() => reload(true))}>{error ? 'Повторить загрузку' : 'Загрузка планёрки…'}</Button>}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {data && <>
      <p className="text-sm text-muted-foreground">{data.date} · {saved?.status === 'assigned' && !dirty ? 'Задачи переданы в кабинеты' : data.can_manage ? 'Черновик до подтверждения' : 'Мои задачи'}</p>
      {data.can_manage && <>
        <details className="text-sm text-muted-foreground"><summary className="cursor-pointer py-2">Пример фокуса дня</summary><p>«Сегодня внимательно встречаем новых клиентов. Анна проверяет витрину, администратор предлагает подходящий уход после окрашивания». Пишите обычными словами — специальные команды не нужны.</p></details>
        <label className="block space-y-2"><span className="font-medium">1. Фокус дня</span>
          <Textarea aria-label="Фокус дня" disabled={busy} maxLength={1500} value={focus} onChange={event => { edited(); setFocus(event.target.value); }} placeholder="Например: внимательно встречаем новых клиентов и предлагаем подходящий уход после окрашивания." /></label>
        <OperatorVoiceInput contextKey="day_brief" businessId={businessId} channel={channel} headers={headers} disabled={busy} directSubmit={false} submitLabel="Вставить в фокус дня" draftLabel="Распознанный фокус"
          onSubmit={async (value, source) => { edited(); setFocus(value); setVoice({ ...source, text: value }); }} />
        <p className="text-sm text-muted-foreground">Распознанный текст можно поправить. Запись и сохранение черновика ничего не отправляют.</p>
        <fieldset disabled={busy} className="space-y-3"><legend className="mb-2 font-medium">2. Кому и какие задачи передать?</legend>
          {!data.members.length && <p className="text-sm text-muted-foreground">Сначала добавьте сотрудников в разделе «Бизнес и команда» и подключите их мессенджеры.</p>}
          {data.members.map(member => {
            const target = targets.find(row => row.user_id === member.id);
            return <div key={member.id} className="space-y-2 border-b pb-3">
              <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={Boolean(target)} disabled={!member.platforms.length}
                onChange={event => { edited(); setTargets(rows => event.target.checked ? [...rows, { user_id: member.id, platforms: [member.platforms[0]], tasks: [{ text: focus }] }] : rows.filter(row => row.user_id !== member.id)); }} />{member.name}</label>
              {!member.platforms.length && <p className="text-sm text-muted-foreground">Мессенджер ещё не подключён.</p>}
              {target && <>
                <div className="flex flex-wrap gap-3">{member.platforms.map(platform => <label key={platform} className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={target.platforms.includes(platform)} onChange={event => updateTarget(member.id, row => ({ ...row, platforms: event.target.checked ? [...row.platforms, platform] : row.platforms.filter(p => p !== platform) }))} />{platform === 'max' ? 'MAX' : 'Telegram'}</label>)}</div>
                <label className="block text-sm">Задачи для {member.name}, каждая с новой строки<Textarea value={target.tasks.map(task => task.text).join('\n')} onChange={event => updateTarget(member.id, row => ({ ...row, tasks: event.target.value.split('\n').map(value => ({ text: value })) }))} /></label>
              </>}
            </div>;
          })}
        </fieldset>
        {targets.length > 0 && !recipientsReady && <p role="status" className="text-sm text-muted-foreground">Для каждого выбранного сотрудника выберите канал и добавьте хотя бы одну задачу.</p>}
        {!data.delivery_enabled && <p className="text-sm text-muted-foreground">Уведомления в мессенджеры пока выключены. После подтверждения задачи появятся в кабинетах сотрудников.</p>}
        <div className="flex flex-wrap gap-2">{!preview && <Button disabled={busy || !focus.trim() || !recipientsReady} onClick={() => void perform(async () => {
          const value = await save(); setPreview(await request<Preview>('day-brief/preview', { business_id: businessId, record_id: value.id, version: value.version }));
        })}>Проверить перед передачей</Button>}<Button variant="outline" disabled={busy || !focus.trim()} onClick={() => void perform(async () => { await save(); setNotice('Черновик сохранён. Сотрудникам ничего не передано.'); })}>Сохранить черновик</Button></div>
        {saved && <WorkDiscussion businessId={businessId} itemId={saved.id} updatedAt={String(saved.version)} itemType="day_brief" disabled={dirty || busy} />}
        {preview && <div className="space-y-4 border-t pt-4" aria-label="Проверка планёрки" role="region" ref={previewFocus} tabIndex={-1}>
          <h3 className="font-semibold">3. Проверьте точный текст и получателей</h3>
          {preview.day_brief_preview.messages.map(message => <div key={message.user_id}><p className="font-medium">{message.name} · {message.platforms.map(p => p === 'max' ? 'MAX' : 'Telegram').join(', ')}</p><p className="whitespace-pre-wrap break-words text-sm">{message.text}</p></div>)}
          <p className="text-sm">{preview.day_brief_preview.delivery_enabled ? 'Уведомления будут поставлены в очередь. Статус очереди не подтверждает доставку.' : 'Задачи появятся в кабинетах. Уведомления выключены.'}</p>
          <div className="flex flex-wrap gap-2"><Button disabled={busy || dirty} onClick={() => void perform(async () => {
            const result = await request<{ operator_result?: { chat_response?: string; status?: string }; chat_response?: string }>('actions/' + preview.approval.action_id + '/confirm', { business_id: businessId });
            if (result.operator_result?.status && result.operator_result.status !== 'completed') throw new Error(result.operator_result.chat_response || 'Передача не подтверждена. Обновите планёрку.');
            setNotice(result.operator_result?.chat_response || result.chat_response || 'Проверьте результат передачи.'); setPreview(null); await reload(true);
          })}>Подтвердить передачу задач</Button><Button variant="outline" disabled={busy} onClick={() => void perform(async () => { await request('actions/' + preview.approval.action_id + '/reject', { business_id: businessId }); setPreview(null); setNotice('Передача отменена. Черновик сохранён.'); })}>Отмена</Button></div>
        </div>}
      </>}
      <div className="space-y-4 border-t pt-4"><h3 className="font-semibold">{data.can_manage ? 'Переданные задачи команды' : 'Мои задачи и подсказки'}</h3>
        {!data.assignments.length && <p className="text-sm text-muted-foreground">Подтверждённых задач пока нет. Они появятся после проверки владельцем.</p>}
        {data.assignments.map(action => <div key={action.id} className="space-y-2 border-b pb-3"><p className="font-medium">{data.members.find(member => member.id === action.user_id)?.name || 'Мои задачи'} · {action.payload_json.date}</p><p className="text-sm">Фокус: {action.payload_json.focus}</p>
          {action.payload_json.tasks.map(task => <label key={task.id} className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={pendingCompletion?.action === action.id && pendingCompletion.task === task.id ? pendingCompletion.done : Boolean(task.done)} disabled={busy || !data.can_complete || action.user_id !== data.user_id} onChange={event => { const done = event.target.checked; const expected = scope.current; setPendingCompletion({ action: action.id, task: task.id, done }); void perform(async () => { try { await request('day-brief/task', { business_id: businessId, action_id: action.id, task_id: task.id, version: action.version, done }); await reload(); } finally { if (scope.current === expected) setPendingCompletion(null); } }); }} /><span className="min-w-0 break-words">{task.text}</span></label>)}
          {data.deliveries?.filter(delivery=>delivery.action_id===action.id).map(delivery=><p key={delivery.platform} className="text-sm">{delivery.platform==='max'?'MAX':'Telegram'}: {(deliveryLabels[delivery.state] || 'Проверьте доставку')}</p>)}
          {action.payload_json.tips.map((tip, index) => <p key={index} className="text-sm">{tip.main_service} → {tip.service}: {tip.wording}</p>)}<p className="text-sm text-muted-foreground">{action.payload_json.note}</p>
        </div>)}
        <Button variant="outline" disabled={busy} onClick={() => void perform(() => reload())}>Обновить задачи</Button>
      </div>
    </>}
  </section>;
}
