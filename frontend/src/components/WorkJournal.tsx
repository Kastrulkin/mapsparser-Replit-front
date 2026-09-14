import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { OperatorVoiceInput, voiceHeaders, waitForOperatorResult } from '@/components/operator/OperatorVoice';

const defaultHeaders = voiceHeaders;
type Entry = { author_name?: string; group_count?: number; review_status?: string; category?: string; decision?: string; assigned_to?: string; urgent?: boolean; id: string; version: number; user_id: string; can_edit?: boolean; channel: string; occurred_at: string; original_text: string; is_voided: boolean; booking_id?: string; facts_json: { event_time_known?: boolean; quote?: string; outcome?: string; reason?: string } };
type LinkedAction = { payload_json?: { draft_id?: string; draft_href?: string }; id: string; version: number; title?: string; description?: string; status: string };
type Rule = { id: string; instruction: string; permanent?: boolean; starts_at?: string; ends_at?: string };
type PolicyHistory = { id: string; kind: string; created_at: string };
type Data = { review_enabled?: boolean; can_review?: boolean; members?: { user_id: string; name: string }[]; enabled: boolean; role?: string; items: Entry[]; policy?: { version: number; rules_json: Rule[] }; policy_history?: PolicyHistory[] };
type Answer = { async_job_id?: string; chat_response?: string; conversation_id?: string; status?: string; approval?: { action_id?: string; status?: string }; operator_result?: Answer };

export function WorkJournal({ businessId, headers = defaultHeaders, embedded = false }: { embedded?: boolean; businessId?: string | null; headers?: () => Record<string, string> }) {
  const [data, setData] = useState<Data | null>(null); const [text, setText] = useState('');
  const [query, setQuery] = useState(''); const [day, setDay] = useState('');
  const [answer, setAnswer] = useState<Answer | null>(null); const [conversation, setConversation] = useState<string>();
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [editing, setEditing] = useState<Entry | null>(null); const [correction, setCorrection] = useState('');
  const [history, setHistory] = useState<Record<string, { created_at: string; after_json: Entry }[]>>({});
  const [selectedObservation,setSelectedObservation]=useState<Entry | null>(null); const [selectedTask,setSelectedTask]=useState<LinkedAction | null>(null);
  const [linked,setLinked]=useState<Record<string,LinkedAction[]>>({});
  const [digestTime,setDigestTime]=useState('18:00'); const [reviewerId,setReviewerId]=useState('');
  const [tab,setTab]=useState('journal'); const [inbox,setInbox]=useState<Entry[]>([]);
  const [reviewStatus,setReviewStatus]=useState('new'); const [reviewCategory,setReviewCategory]=useState('');
  const [reviewing,setReviewing]=useState<Entry | null>(null); const [resolution,setResolution]=useState('in_progress');
  const [reason,setReason]=useState(''); const [assignee,setAssignee]=useState('');
  const openedEntry = useRef('');
  const scope = useRef(businessId); scope.current = businessId;
  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const requestedBusiness=scope.current;
    const response = await fetch(`/api${path}`, { ...init, headers: { ...headers(), 'Content-Type': 'application/json' } });
    const body = await response.json();
    if (!response.ok) {
      if ([401,403].includes(response.status) && scope.current===requestedBusiness) {setData(null);setAnswer(null);setHistory({});setEditing(null);setConversation(undefined);setInbox([]);setReviewing(null);setLinked({});setSelectedObservation(null);setSelectedTask(null);}
      throw new Error(body.error || 'Не удалось выполнить запрос.');
    }
    return body;
  }, [headers]);
  const load = useCallback(async (signal?: AbortSignal) => {
    const business = businessId; if (!business) return;
    const params = new URLSearchParams({ business_id: business });
    if (query) params.set('query', query); if (day) params.set('date', day);
    const result: Data = await request(`/work-journal?${params}`, { signal });
    if (scope.current === business && !signal?.aborted) setData(result);
  }, [businessId, query, day, request]);
  useEffect(() => { setData(null); setText(''); setAnswer(null); setConversation(undefined); setEditing(null); setHistory({}); setError(''); setQuery(''); setDay(''); setBusy(false); setTab('journal'); setInbox([]); setReviewing(null); setReason(''); setAssignee(''); setReviewerId(''); setDigestTime('18:00'); setLinked({}); setSelectedObservation(null); setSelectedTask(null); }, [businessId]);
  useEffect(()=>{if(data?.can_review===false){setInbox([]);setReviewing(null);setLinked({});setHistory({});setReason('');setSelectedObservation(null);setSelectedTask(null);}},[data?.can_review]);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); }); return () => controller.abort(); }, [load]);
  useEffect(() => {
    const params=new URLSearchParams(window.location.search); const id=params.get('entry');
    if (!id || openedEntry.current===`${businessId}:${id}`) return;
    const entry=data?.items.find(item=>item.id===id); if (!entry) return;
    openedEntry.current=`${businessId}:${id}`;
    document.getElementById(`journal-${id}`)?.scrollIntoView({block:'center'});
    if (params.get('mode')==='edit' && entry.can_edit) {setEditing(entry);setCorrection(entry.facts_json.quote || entry.original_text);}
  },[data,businessId]);
  const run = async (action: () => Promise<void>) => {
    const business = businessId; setBusy(true); setError('');
    try { await action(); } catch (failure) { if (scope.current === business) setError(failure instanceof Error ? failure.message : 'Повторите запрос.'); }
    finally { if (scope.current === business) setBusy(false); }
  };
  const submit = async (message: string, source?: { transcription_id: string; conversation_id: string; request_id: string }) => {
    const business = businessId;
    const raw: Answer = await request('/operator/chat', { method: 'POST', body: JSON.stringify({ business_id: business, input_context: 'work_journal', work_entry_id:selectedObservation?.id, work_action_id:selectedTask?.id, channel: headers === defaultHeaders ? 'web' : 'telegram_mini_app', conversation_id: conversation, message, request_id: crypto.randomUUID(), ...source }) });
    if (scope.current !== business) return;
    const final=await waitForOperatorResult(raw.operator_result || raw,business || '',headers,()=>scope.current===business);
    if(scope.current!==business)return;
    setAnswer(final); setConversation(raw.conversation_id); setText(''); setSelectedObservation(null);setSelectedTask(null); await load();
  };
  const change = async (entry: Entry, voided: boolean) => {
    const business = businessId;
    if (!voided) { await submit(`Исправь рабочую заметку ${entry.id}, версия ${entry.version}. Новый текст: ${correction}`); if (scope.current === business) setEditing(null); return; }
    await request(`/work-journal/${entry.id}`, { method: 'PATCH', body: JSON.stringify({ business_id: business, version: entry.version, void: voided, text: voided ? '' : correction, request_id: crypto.randomUUID() }) });
    if (scope.current === business) { setEditing(null); await load(); }
  };
  const decision = async (approve: boolean) => {
    const business = businessId; const id = answer?.approval?.action_id; if (!id) return;
    const response: Answer = await request(`/operator/actions/${id}/${approve ? 'confirm' : 'reject'}`, { method: 'POST', body: JSON.stringify({ business_id: business }) });
    if (scope.current === business) { setAnswer(response.operator_result || response); await load(); }
  };
  const loadInbox=async () => {
    const business=businessId; const params=new URLSearchParams({business_id:business || '',status:reviewStatus,category:reviewCategory});
    const value=await request(`/work-journal/review?${params}`); if(scope.current===business)setInbox(value.items);
  };
  const saveReview=async () => {
    if(!reviewing)return; const business=businessId;
    await request(`/work-journal/${reviewing.id}/decision`,{method:'POST',body:JSON.stringify({business_id:business,version:reviewing.version,status:resolution,decision:reason,assigned_to:assignee || null,request_id:crypto.randomUUID()})});
    if(scope.current===business){setReviewing(null);await loadInbox();await load();}
  };
  if (!businessId) return <p>Выберите бизнес, чтобы открыть рабочий журнал.</p>;
  return <div className="space-y-5">
    <div>{!embedded && <h1 className="text-2xl font-semibold">Рабочий журнал</h1>}<p className="text-sm text-muted-foreground">Сообщайте о работе и спрашивайте, что предложить клиентам. Заметки сохраняются с возможностью отмены.</p></div>
    {error && <p role="alert">{error}</p>}
    {data && !data.enabled && <p role="status">Новый ввод пока отключён. Сохранённая история доступна.</p>}
    {data?.enabled && <section className="space-y-3 rounded-xl border bg-card p-4 text-card-foreground">
      {selectedObservation && <p className="text-sm">По записи: {selectedObservation.facts_json.quote}<Button variant="ghost" onClick={()=>{setSelectedObservation(null);setSelectedTask(null);}}>Убрать привязку</Button></p>}
      <label className="block">Сообщение Оператору<Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Клиент отказался от ухода: дорого. Или: что предложить клиентам сегодня?" /></label>
      <Button disabled={busy || !text.trim()} onClick={() => void run(() => submit(text))}>Отправить</Button>
      <OperatorVoiceInput directSubmit disabled={busy} businessId={businessId} conversationId={conversation} channel={headers === defaultHeaders ? 'web' : 'telegram_mini_app'} headers={headers} onSubmit={submit} />
      {answer?.chat_response && <p className="whitespace-pre-wrap" role="status">{answer.chat_response}</p>}
      {answer?.approval?.action_id && answer.approval.status === 'pending' && <div className="flex gap-2"><Button disabled={busy} onClick={() => void run(() => decision(true))}>Подтвердить изменение</Button><Button variant="outline" disabled={busy} onClick={() => void run(() => decision(false))}>Отклонить</Button></div>}
    </section>}
    {data?.can_review && <div className="flex gap-2" aria-label="Раздел журнала"><Button variant={tab==='journal'?'default':'outline'} onClick={()=>setTab('journal')}>Все доступные записи</Button><Button variant={tab==='review'?'default':'outline'} onClick={()=>void run(async()=>{setTab('review');await loadInbox();})}>На разбор</Button></div>}
    {tab==='review' && data?.can_review && <section className="space-y-3">
      <h2 className="text-lg font-semibold">На разбор</h2><p>Здесь сведения со слов сотрудников. Выберите запись, примите решение и назначьте следующий шаг.</p>
      <div className="flex flex-wrap gap-3"><label>Статус<select className="block rounded-md border bg-background p-2" value={reviewStatus} onChange={e=>setReviewStatus(e.target.value)}><option value="new">Новые</option><option value="clarification">Нужно уточнить</option><option value="observing">Наблюдаем</option><option value="in_progress">В работе</option><option value="rejected">Отклонены</option><option value="completed">Завершены</option><option value="">Все</option></select></label><label>Категория<select className="block rounded-md border bg-background p-2" value={reviewCategory} onChange={e=>setReviewCategory(e.target.value)}><option value="">Все</option><option value="complaint">Жалобы</option><option value="wish">Пожелания</option><option value="idea">Идеи</option><option value="operations">Организационные проблемы</option><option value="other">Другое</option></select></label><Button variant="outline" disabled={busy} onClick={()=>void run(loadInbox)}>Показать</Button></div>
      {!inbox.length && <p>Нет записей с выбранными условиями.</p>}
      {inbox.map(entry=><article key={entry.id} className="space-y-2 rounded-xl border bg-card p-4">{Boolean(entry.group_count && entry.group_count>1) && <p className="font-medium">Похожие сообщения: {entry.group_count}. Каждое разбирается отдельно.</p>}<p>{entry.urgent?'Срочно · ':''}{entry.facts_json.quote || entry.original_text}</p><p className="text-sm text-muted-foreground">Со слов: {entry.author_name || 'сотрудника'} · {entry.facts_json.event_time_known?'Событие':'Получено'}: {new Date(entry.occurred_at).toLocaleString()}</p>{entry.decision && <p>Решение: {entry.decision}</p>}
        <Button disabled={busy} onClick={()=>{setReviewing(entry);setReason('');setAssignee(entry.assigned_to || '');setResolution('in_progress');}}>Разобрать</Button>
        {entry.review_status==='in_progress' && <Button variant="outline" onClick={()=>{setSelectedObservation(entry);setSelectedTask(null);setText('По выбранному наблюдению создай задачу: ');document.querySelector<HTMLTextAreaElement>('textarea')?.focus();}}>Подготовить действие</Button>}
        <Button variant="ghost" disabled={busy} onClick={()=>void run(async()=>{const business=businessId;const value=await request(`/work-journal/${entry.id}/actions?business_id=${business}`);if(scope.current===business)setLinked(previous=>({...previous,[entry.id]:value.items}));})}>Задачи и результаты</Button>
        {linked[entry.id]?.map(action=><div key={action.id} className="rounded-md border p-3"><p>{action.title} · {action.status==='completed'?'Выполнено':'В работе'}</p><p className="whitespace-pre-wrap">{action.description}</p>{action.payload_json?.draft_id && <a className="underline" href="/dashboard/content-plan">Открыть сохранённый черновик</a>}{action.status!=='completed' && <Button variant="outline" onClick={()=>{setSelectedObservation(entry);setSelectedTask(action);setText('Выбранная задача выполнена. Результат: ');document.querySelector<HTMLTextAreaElement>('textarea')?.focus();}}>Сообщить результат</Button>}</div>)}
      </article>)}
      {reviewing && <section className="space-y-3 rounded-xl border bg-card p-4" aria-label="Решение по наблюдению"><p>{reviewing.facts_json.quote}</p><label className="block">Решение<select autoFocus className="block rounded-md border bg-background p-2" value={resolution} onChange={e=>setResolution(e.target.value)}><option value="in_progress">Принять в работу</option><option value="clarification">Уточнить</option><option value="observing">Наблюдать</option><option value="rejected">Отклонить</option><option value="completed">Закрыть с результатом</option></select></label><label className="block">Ответственный<select className="block rounded-md border bg-background p-2" value={assignee} onChange={e=>setAssignee(e.target.value)}><option value="">Не назначен</option>{data.members?.map(member=><option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></label><label className="block">Комментарий руководства<Textarea value={reason} onChange={e=>setReason(e.target.value)} placeholder="Причина решения или подтверждённый результат" /></label><Button disabled={busy || (['rejected','completed'].includes(resolution) && !reason.trim())} onClick={()=>void run(saveReview)}>Сохранить решение</Button><Button variant="ghost" onClick={()=>setReviewing(null)}>Отмена</Button></section>}
    </section>}
    {tab==='journal' && <><div className="flex flex-wrap gap-3"><label>Поиск<Input value={query} onChange={(e) => setQuery(e.target.value)} /></label><label>Местная дата<Input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label><Button variant="outline" disabled={busy} onClick={() => void run(() => load())}>Обновить</Button></div>
    {data?.items.length === 0 && <p>Записей пока нет. Например: «Запомни: сегодня клиенты спрашивали про новую услугу».</p>}
    {data?.items.map((entry) => <article id={`journal-${entry.id}`} key={entry.id} className="space-y-2 rounded-xl border bg-card p-4 text-card-foreground">
      <p>{entry.facts_json.quote || entry.original_text}</p><p className="text-sm text-muted-foreground">{new Date(entry.occurred_at).toLocaleString()} · {entry.channel} · {entry.is_voided ? 'Отменено' : entry.booking_id ? 'Связано с визитом' : 'Без привязки к визиту'} · версия {entry.version}</p>
      <details><summary>Исходное сообщение</summary><p>{entry.original_text}</p></details>
      {editing?.id === entry.id ? <div className="space-y-2"><label>Исправленный текст<Textarea autoFocus value={correction} onChange={(e) => setCorrection(e.target.value)} /></label><Button disabled={busy || !correction.trim()} onClick={() => void run(() => change(entry, false))}>Сохранить исправление</Button><Button variant="ghost" onClick={() => setEditing(null)}>Закрыть</Button></div> : data.enabled && entry.can_edit && !entry.is_voided && <div className="flex gap-2"><Button variant="outline" disabled={busy} onClick={() => { setEditing(entry); setCorrection(entry.facts_json.quote || entry.original_text); }}>Исправить</Button><Button variant="outline" disabled={busy} onClick={() => void run(() => change(entry, true))}>Отменить запись</Button></div>}
      <Button variant="ghost" onClick={() => void run(async () => { const business = businessId; const value = await request(`/work-journal/${entry.id}/history?business_id=${business}`); if (scope.current === business) setHistory((previous) => ({ ...previous, [entry.id]: value.items })); })}>История</Button>
      {history[entry.id]?.map((item) => <p key={`${item.created_at}:${item.after_json.version}`} className="text-sm">{item.created_at} · {item.after_json.is_voided ? 'Отменено' : item.after_json.facts_json?.quote || item.after_json.decision || 'Решение обновлено'}</p>)}
    </article>)}
    </>}
    {data?.role==='owner' && data.review_enabled && <details className="rounded-xl border bg-card p-4"><summary>Настройки разбора и уведомлений</summary><div className="space-y-3 pt-3"><p>Управляющий получает доступ только к выбранному бизнесу. Изменение права требует подтверждения.</p><label className="block">Управляющий<select className="block rounded-md border bg-background p-2" value={reviewerId} onChange={e=>setReviewerId(e.target.value)}><option value="">Выберите участника</option>{data.members?.map(member=><option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></label>{[true,false].map(grant=><Button key={String(grant)} variant="outline" disabled={busy || !reviewerId} onClick={()=>void run(async()=>{const business=businessId;const preview:Answer=await request('/work-journal/policy/preview',{method:'POST',body:JSON.stringify({business_id:business,kind:'reviewer',user_id:reviewerId,enabled:grant,request_id:crypto.randomUUID()})});if(scope.current===business)setAnswer(preview);})}>{grant?'Предоставить право':'Отозвать право'}</Button>)}<label className="block">Время дневной сводки в часовом поясе бизнеса<Input type="time" value={digestTime} onChange={e=>setDigestTime(e.target.value)} /></label><Button variant="outline" disabled={busy} onClick={()=>void run(async()=>{const business=businessId;await request('/work-journal/digest-settings',{method:'POST',body:JSON.stringify({business_id:business,local_time:digestTime,enabled:true})});if(scope.current===business)setAnswer({chat_response:'Время сводки сохранено.'});})}>Сохранить время сводки</Button></div></details>}
    {data?.role === 'owner' && <section className="space-y-3 rounded-xl border bg-card p-4 text-card-foreground"><h2 className="text-lg font-semibold">Правила рекомендаций</h2><p>Изменения применяются только после вашего подтверждения. Точка — выбранный бизнес.</p>
      {!data.policy?.rules_json.length && <p>Дополнительных правил пока нет.</p>}
      {data.policy?.rules_json.map((rule) => <p key={rule.id}>{rule.instruction} · {rule.permanent ? 'постоянно' : `${rule.starts_at || 'сразу'} — ${rule.ends_at}`}</p>)}
      <Button variant="outline" onClick={() => setText('Измени правила рекомендаций: ')}>Изменить правила через Оператора</Button>
      {data.policy_history?.filter((item) => item.kind === 'rules').map((item) => <div key={item.id}><span>{item.created_at}</span><Button variant="ghost" disabled={busy || !data.enabled} onClick={() => void run(async () => { const business = businessId; const preview: Answer = await request('/work-journal/policy/preview', { method: 'POST', body: JSON.stringify({ business_id: business, restore_history_id: item.id, request_id: crypto.randomUUID() }) }); if (scope.current === business) setAnswer(preview); })}>Подготовить откат</Button></div>)}
    </section>}
  </div>;
}
