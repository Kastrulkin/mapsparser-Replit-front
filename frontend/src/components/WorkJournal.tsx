import { JournalServiceSearch } from '@/components/operator/JournalServiceSearch';
import { teamWorkJson } from '@/lib/teamWorkRequest';
import { DayBriefing } from '@/components/operator/DayBriefing';
import { miniAppLaunchParams, miniAppChannel, miniAppPath } from "@/lib/miniAppPlatform";
import { workStatusLabel, workStatusDetail } from '@/lib/workStatus';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { OperatorVoiceInput } from '@/components/operator/OperatorVoice';
import { voiceHeaders, waitForOperatorResult } from '@/components/operator/OperatorVoice.logic';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

const defaultHeaders = voiceHeaders;
const journalChannelLabels: Record<string,string> = {web:'Кабинет',telegram:'Telegram',telegram_mini_app:'Telegram',max_bot:'MAX',max_mini_app:'MAX'};
type Entry = { author_name?: string; group_count?: number; review_status?: string; category?: string; decision?: string; assigned_to?: string; urgent?: boolean; id: string; version: number; user_id: string; can_edit?: boolean; channel: string; occurred_at: string; original_text: string; is_voided: boolean; booking_id?: string; facts_json: { knowledge_proposal?: {record_id:string;kind:string}; event_time_known?: boolean; quote?: string; outcome?: string; reason?: string } };
type LinkedAction = { material_href?: string | null; payload_json?: { search_task_id?: string; draft_id?: string; draft_href?: string }; id: string; version: number; title?: string; description?: string; status: string };
type Rule = { id: string; instruction: string; permanent?: boolean; starts_at?: string; ends_at?: string };
type PolicyHistory = { id: string; kind: string; created_at: string };
type Data = { business_city?: string; can_decide?: boolean; review_enabled?: boolean; can_review?: boolean; members?: { user_id: string; name: string }[]; enabled: boolean; role?: string; items: Entry[]; policy?: { version: number; rules_json: Rule[] }; policy_history?: PolicyHistory[] };
type Answer = { async_job_id?: string; chat_response?: string; conversation_id?: string; status?: string; approval?: { action_id?: string; status?: string }; operator_result?: Answer };

export function WorkJournal({ businessId, headers = defaultHeaders, embedded = false, initialView = 'journal' }: { initialView?: 'journal' | 'day_brief'; embedded?: boolean; businessId?: string | null; headers?: () => Record<string, string> }) {
  const { language } = useLanguage();
  const [data, setData] = useState<Data | null>(null); const [text, setText] = useState('');
  const [query, setQuery] = useState(''); const [day, setDay] = useState('');
  const [answer, setAnswer] = useState<Answer | null>(null); const [conversation, setConversation] = useState<string>();
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [editing, setEditing] = useState<Entry | null>(null); const [correction, setCorrection] = useState('');
  const [history, setHistory] = useState<Record<string, { created_at: string; after_json: Entry }[]>>({});
  const [selectedObservation,setSelectedObservation]=useState<Entry | null>(null); const [selectedTask,setSelectedTask]=useState<LinkedAction | null>(null);
  const [linked,setLinked]=useState<Record<string,LinkedAction[]>>({});
  const [searchEntryId,setSearchEntryId]=useState(''); const [taskEntry,setTaskEntry]=useState<Entry | null>(null); const [taskTitle,setTaskTitle]=useState(''); const [taskText,setTaskText]=useState(''); const [taskAssignee,setTaskAssignee]=useState(''); const taskRequest=useRef(crypto.randomUUID());
  const [digestTime,setDigestTime]=useState('18:00'); const [digestEnabled,setDigestEnabled]=useState(false); const [reviewerId,setReviewerId]=useState('');
  const [briefingOpen, setBriefingOpen] = useState(() => initialView === 'day_brief' || miniAppLaunchParams().get('item_type') === 'day_brief');
  const [briefingVisited, setBriefingVisited] = useState(briefingOpen);
  const [tab,setTab]=useState('journal'); const [inbox,setInbox]=useState<Entry[]>([]);
  const [reviewStatus,setReviewStatus]=useState('new'); const [reviewCategory,setReviewCategory]=useState('');
  const [reviewing,setReviewing]=useState<Entry | null>(null); const [resolution,setResolution]=useState('in_progress');
  const [reviewNotice,setReviewNotice]=useState(''); const [reason,setReason]=useState(''); const [assignee,setAssignee]=useState('');
  const openedEntry = useRef(''); const journalRequest=useRef(crypto.randomUUID());
  const scope = useRef(businessId); scope.current = businessId;
  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const requestedBusiness=scope.current;
    const { response, body } = await teamWorkJson(`/api${path}`, { ...init, headers: { ...headers(), 'Content-Type': 'application/json' } });
    if (!response.ok) {
      if ([401,403].includes(response.status) && scope.current===requestedBusiness) {setData(null);setAnswer(null);setHistory({});setEditing(null);setConversation(undefined);setInbox([]);setReviewing(null);setLinked({});setSelectedObservation(null);setSelectedTask(null);setTaskEntry(null);setSearchEntryId('');setTaskTitle('');setTaskText('');setTaskAssignee('');}
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
  useEffect(() => { setData(null); setText(''); setAnswer(null); setConversation(undefined); setEditing(null); setHistory({}); setError(''); setQuery(''); setDay(''); setBusy(false); setTab('journal'); setInbox([]); setReviewing(null); setReviewNotice(''); setReason(''); setAssignee(''); setReviewerId(''); setDigestTime('18:00'); setDigestEnabled(false); setLinked({}); setSelectedObservation(null); setSelectedTask(null); setTaskEntry(null); setSearchEntryId(''); setTaskTitle(''); setTaskText(''); setTaskAssignee(''); taskRequest.current=crypto.randomUUID(); journalRequest.current=crypto.randomUUID(); }, [businessId]);
  useEffect(()=>{if(data?.can_review===false){setInbox([]);setReviewing(null);setLinked({});setHistory({});setReason('');setSelectedObservation(null);setSelectedTask(null);setTaskEntry(null);setSearchEntryId('');setTaskTitle('');setTaskText('');setTaskAssignee('');}},[data?.can_review]);
  useEffect(() => {
    if (data?.role !== 'owner' || !data.review_enabled) return;
    const business=businessId; const controller=new AbortController();
    void request(`/work-journal/digest-settings?${new URLSearchParams({business_id:business || ''})}`,{signal:controller.signal})
      .then(value=>{if(scope.current===business && !controller.signal.aborted){setDigestTime(value.local_time);setDigestEnabled(value.enabled===true);}})
      .catch(failure=>{if(scope.current===business && !controller.signal.aborted)setError(failure.message);});
    return ()=>controller.abort();
  },[businessId,data?.role,data?.review_enabled,request]);
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
    const raw: Answer = await request('/operator/chat', { method: 'POST', body: JSON.stringify({ business_id: business, input_context: 'work_journal', work_entry_id:selectedObservation?.id, work_action_id:selectedTask?.id, channel: headers === defaultHeaders ? 'web' : miniAppChannel(), conversation_id: conversation, message, request_id: journalRequest.current, ...source }) });
    if (scope.current !== business) return;
    const final=await waitForOperatorResult(raw.operator_result || raw,business || '',headers,()=>scope.current===business);
    if(scope.current!==business)return;
    setAnswer(final); setConversation(raw.conversation_id); setText(previous=>previous===message?'':previous); journalRequest.current=crypto.randomUUID(); setSelectedObservation(null);setSelectedTask(null); await load();
  };
  const change = async (entry: Entry, voided: boolean) => {
    const business = businessId;
    await request(`/work-journal/${entry.id}`, { method: 'PATCH', body: JSON.stringify({ business_id: business, version: entry.version, void: voided, text: voided ? '' : correction, channel:headers === defaultHeaders ? 'web' : miniAppChannel(), request_id: crypto.randomUUID() }) });
    if (scope.current === business) { setEditing(null); setAnswer({ status: 'completed', chat_response: voided ? 'Запись отменена. Она останется в истории.' : 'Исправление сохранено.' }); await load(); }
  };
  const decision = async (approve: boolean) => {
    const business = businessId; const id = answer?.approval?.action_id; if (!id) return;
    const response: Answer = await request(`/operator/actions/${id}/${approve ? 'confirm' : 'reject'}`, { method: 'POST', body: JSON.stringify({ business_id: business }) });
    if (scope.current === business) { setAnswer(response.operator_result || response); await load(); }
  };
  const loadInbox=async (status=reviewStatus) => {
    const business=businessId; const params=new URLSearchParams({business_id:business || '',status,category:reviewCategory});
    const value=await request(`/work-journal/review?${params}`); if(scope.current===business)setInbox(value.items);
  };
  const saveReview=async () => {
    if(!reviewing)return; const business=businessId;
    await request(`/work-journal/${reviewing.id}/decision`,{method:'POST',body:JSON.stringify({business_id:business,version:reviewing.version,status:resolution,decision:reason,assigned_to:assignee || null,request_id:crypto.randomUUID()})});
    if(scope.current===business){setReviewing(null);setReviewStatus(resolution);setReviewNotice(resolution==='in_progress'?'Запись принята в работу. Теперь можно назначить задачу.':'Решение сохранено.');await loadInbox(resolution);await load();}
  };
  if (!businessId) return <p>Выберите бизнес, чтобы открыть планёрку и журнал.</p>;
  return <div className="space-y-5">
    {!embedded && <h1 className="text-2xl font-semibold">Планёрка и журнал</h1>}
    <p className="text-sm text-muted-foreground">Планёрка — что делаем сегодня. Журнал — что произошло в работе.</p>
    <Tabs value={briefingOpen ? 'briefing' : 'journal'} onValueChange={value => { setBriefingOpen(value === 'briefing'); if (value === 'briefing') setBriefingVisited(true); }}>
      <TabsList className="grid h-auto min-h-11 w-full grid-cols-2" aria-label="Планёрка и журнал">
        <TabsTrigger className="min-h-11" value="briefing">Планёрка</TabsTrigger>
        <TabsTrigger className="min-h-11" value="journal">Журнал</TabsTrigger>
      </TabsList>
      <TabsContent forceMount value="briefing" hidden={!briefingOpen} className="space-y-4 data-[state=inactive]:hidden">
        {briefingVisited && <DayBriefing key={businessId} businessId={businessId} headers={headers} channel={headers === defaultHeaders ? 'web' : miniAppChannel()} />}
      </TabsContent>
      <TabsContent forceMount value="journal" hidden={briefingOpen} className="space-y-4 data-[state=inactive]:hidden">
    <div><h2 className="text-xl font-semibold">Что произошло на работе?</h2><p className="text-sm text-muted-foreground">Запишите наблюдение: что заметили, что сказал клиент или что нужно исправить. Руководитель сможет разобрать запись и выбрать следующий шаг.</p></div>
    {error && <p role="alert">{error}</p>}
    {data && !data.enabled && <p role="status">Новый ввод пока отключён. Сохранённая история доступна.</p>}
    {data?.role==='viewer' && <p role="status">У вас доступ для просмотра. Для записи наблюдений попросите владельца предоставить право сотрудника.</p>}
    {data?.enabled && data.role!=='viewer' && <section className="space-y-3 rounded-xl border bg-card p-4 text-card-foreground">
      {selectedObservation && <p className="text-sm">По записи: {selectedObservation.facts_json.quote}<Button variant="ghost" onClick={()=>{setSelectedObservation(null);setSelectedTask(null);setTaskEntry(null);setSearchEntryId('');setTaskTitle('');setTaskText('');setTaskAssignee('');}}>Убрать привязку</Button></p>}
      <label className="block">Что вы заметили?<Textarea value={text} onChange={(e) => {setText(e.target.value);journalRequest.current=crypto.randomUUID();}} placeholder="Например: клиент отказался от ухода — сказал, что дорого." /></label>
      <details className="text-sm text-muted-foreground"><summary className="cursor-pointer py-2">Примеры наблюдений</summary><ul className="list-disc space-y-1 pl-5"><li>У витрины грязное стекло, нужно протереть.</li><li>Клиент отказался от ухода: сказал, что дорого.</li><li>Закончился шампунь, нужно пополнить запас.</li></ul></details>
      <p className="text-sm text-muted-foreground">Вопросы и поручения — в «Чат с LocalOS». Здесь сообщайте о том, что произошло; если деталей не хватает, LocalOS уточнит их.</p>
      <Button disabled={busy || !text.trim()} onClick={() => void run(() => submit(text))}>Отправить наблюдение</Button>
      <OperatorVoiceInput contextKey="work_journal" directSubmit={false} submitLabel="Сохранить наблюдение" draftLabel="Проверьте запись для журнала" disabled={busy} businessId={businessId} conversationId={conversation} channel={headers === defaultHeaders ? 'web' : miniAppChannel()} headers={headers} onSubmit={submit} />
      {answer?.chat_response && <p className="whitespace-pre-wrap" role="status">{answer.chat_response}</p>}
      {answer?.approval?.action_id && answer.approval.status === 'pending' && <div className="flex gap-2"><Button disabled={busy} onClick={() => void run(() => decision(true))}>Подтвердить изменение</Button><Button variant="outline" disabled={busy} onClick={() => void run(() => decision(false))}>Отклонить</Button></div>}
    </section>}
    {data?.can_review && <div className="flex gap-2" aria-label="Раздел журнала"><Button variant={tab==='journal'?'default':'outline'} onClick={()=>setTab('journal')}>Все доступные записи</Button><Button variant={tab==='review'?'default':'outline'} onClick={()=>void run(async()=>{setTab('review');await loadInbox();})}>На разбор</Button></div>}
    {tab==='review' && data?.can_review && <section className="space-y-3">
      <h2 className="text-lg font-semibold">На разбор</h2>{reviewNotice && <p role="status">{reviewNotice}</p>}<p>Здесь сведения со слов сотрудников. Выберите запись, примите решение и назначьте следующий шаг.</p>
      <div className="flex flex-wrap gap-3"><label>Статус<select className="block rounded-md border bg-background p-2" value={reviewStatus} onChange={e=>setReviewStatus(e.target.value)}><option value="new">Новые</option><option value="clarification">Нужно уточнить</option><option value="observing">Наблюдаем</option><option value="in_progress">В работе</option><option value="rejected">Отклонены</option><option value="completed">Завершены</option><option value="">Все</option></select></label><label>Категория<select className="block rounded-md border bg-background p-2" value={reviewCategory} onChange={e=>setReviewCategory(e.target.value)}><option value="">Все</option><option value="complaint">Жалобы</option><option value="wish">Пожелания</option><option value="idea">Идеи</option><option value="operations">Организационные проблемы</option><option value="other">Другое</option></select></label><Button variant="outline" disabled={busy} onClick={()=>void run(loadInbox)}>Показать</Button></div>
      {!inbox.length && <p>Нет записей с выбранными условиями.</p>}
      {inbox.map(entry=><article key={entry.id} className="space-y-2 rounded-xl border bg-card p-4">{Boolean(entry.group_count && entry.group_count>1) && <p className="font-medium">Похожие сообщения: {entry.group_count}. Каждое разбирается отдельно.</p>}<p>{entry.urgent?'Срочно · ':''}{entry.facts_json.quote || entry.original_text}</p><p className="text-sm text-muted-foreground">Со слов: {entry.author_name || 'сотрудника'} · {entry.facts_json.event_time_known?'Событие':'Получено'}: {new Date(entry.occurred_at).toLocaleString()}</p>{entry.decision && <p>Решение: {entry.decision}</p>}
        <Button disabled={busy || data.can_decide===false} onClick={()=>{setReviewing(entry);setReason('');setAssignee(entry.assigned_to || '');setResolution('in_progress');}}>Разобрать</Button>
        {entry.review_status==='in_progress' && <Button variant="outline" disabled={busy || data.can_decide===false} onClick={()=>{setTaskEntry(entry);setTaskTitle('');setTaskText('');setTaskAssignee(entry.assigned_to || '');taskRequest.current=crypto.randomUUID();}}>Назначить задачу</Button>}
        {taskEntry?.id===entry.id && <section className="space-y-3 rounded-md border p-3" aria-label="Задача по наблюдению">
          <h3 className="font-semibold">Что нужно сделать?</h3><p className="text-sm text-muted-foreground">По записи сотрудника: {taskEntry.facts_json.quote || taskEntry.original_text}</p>
          <label className="block">Задача<Input autoFocus maxLength={250} value={taskTitle} onChange={event=>{setTaskTitle(event.target.value);taskRequest.current=crypto.randomUUID();}} placeholder="Например: найти мойщика окон рядом с салоном" /></label>
          <label className="block">Подробности<Textarea maxLength={6000} value={taskText} onChange={event=>{setTaskText(event.target.value);taskRequest.current=crypto.randomUUID();}} placeholder="Что проверить и какой результат получить" /></label>
          <label className="block">Ответственный<select className="block min-h-11 w-full rounded-md border bg-background p-2" value={taskAssignee} onChange={event=>{setTaskAssignee(event.target.value);taskRequest.current=crypto.randomUUID();}}><option value="">Мне</option>{data.members?.map(member=><option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></label>
          <p className="text-sm text-muted-foreground">Это поручение по записи журнала. Поиск компаний, отправка писем и договорённости требуют отдельных действий и подтверждения.</p>
          <div className="flex flex-wrap gap-2"><Button disabled={busy || !taskTitle.trim()} onClick={()=>void run(async()=>{const business=businessId; const value=await request(`/work-journal/${taskEntry.id}/actions`,{method:'POST',body:JSON.stringify({business_id:business,version:taskEntry.version,request_id:taskRequest.current,kind:'task',title:taskTitle,text:taskText,assigned_to:taskAssignee || undefined})});if(scope.current===business){setLinked(previous=>({...previous,[entry.id]:[...(previous[entry.id] || []).filter(item=>item.id!==value.action.id),value.action]}));setTaskEntry(null);}})}>Создать задачу</Button><Button variant="outline" disabled={busy} onClick={()=>setTaskEntry(null)}>Отмена</Button></div>
        </section>}
        {entry.review_status==='in_progress' && <Button variant="outline" disabled={busy || data.can_decide===false} onClick={()=>{setTaskEntry(null);setSearchEntryId(entry.id);}}>Найти исполнителя</Button>}
        {searchEntryId===entry.id && <JournalServiceSearch key={businessId+':'+entry.id+':'+entry.version} businessId={businessId || ''} entryId={entry.id} version={entry.version} quote={entry.facts_json.quote || entry.original_text} city={data.business_city} channel={headers===defaultHeaders?'web':miniAppChannel()} request={request} onCancel={()=>setSearchEntryId('')} onStarted={async()=>{const business=businessId;const value=await request(`/work-journal/${entry.id}/actions?business_id=${business}`);if(scope.current===business){setLinked(previous=>({...previous,[entry.id]:value.items}));setSearchEntryId('');setReviewNotice('Поиск запущен. Найденные компании и черновики будут в «Партнёрствах». Обращения не отправляются.');}}}/>}
        <Button variant="ghost" disabled={busy} onClick={()=>void run(async()=>{const business=businessId;const value=await request(`/work-journal/${entry.id}/actions?business_id=${business}`);if(scope.current===business)setLinked(previous=>({...previous,[entry.id]:value.items}));})}>Задачи и результаты</Button>
        {linked[entry.id]?.map(action=><div key={action.id} className="rounded-md border p-3"><p>{action.title} · {workStatusLabel(action.status, language)}</p><p className="whitespace-pre-wrap">{action.description}</p>{action.payload_json?.search_task_id ? <Link className="underline" to={embedded?`${miniAppPath()}?screen=partnerships&scope_type=business&scope_id=${encodeURIComponent(businessId || '')}&filter_search_task_id=${encodeURIComponent(action.payload_json.search_task_id)}&filter_section=leads`:`/dashboard/partnerships?business_id=${encodeURIComponent(businessId || '')}&search_task_id=${encodeURIComponent(action.payload_json.search_task_id)}&section=companies`}>Открыть поиск исполнителя</Link> : action.material_href ? <a className="underline" href={action.material_href}>Открыть сохранённый черновик</a> : action.payload_json?.draft_id ? <p className="text-sm">Ссылка на материал недоступна. Откройте связанную задачу для проверки.</p> : null}{action.status!=='completed' && <Button variant="outline" onClick={()=>{setSelectedObservation(entry);setSelectedTask(action);setText('Выбранная задача выполнена. Результат: ');document.querySelector<HTMLTextAreaElement>('textarea')?.focus();}}>Сообщить результат</Button>}</div>)}
      </article>)}
      {reviewing && <section className="space-y-3 rounded-xl border bg-card p-4" aria-label="Решение по наблюдению"><p>{reviewing.facts_json.quote}</p><label className="block">Решение<select autoFocus className="block rounded-md border bg-background p-2" value={resolution} onChange={e=>setResolution(e.target.value)}><option value="in_progress">Принять в работу</option><option value="clarification">Уточнить</option><option value="observing">Наблюдать</option><option value="rejected">Отклонить</option><option value="completed">Закрыть с результатом</option></select></label><label className="block">Ответственный<select className="block rounded-md border bg-background p-2" value={assignee} onChange={e=>setAssignee(e.target.value)}><option value="">Не назначен</option>{data.members?.map(member=><option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></label><label className="block">Комментарий руководства<Textarea value={reason} onChange={e=>setReason(e.target.value)} placeholder="Причина решения или подтверждённый результат" /></label><Button disabled={busy || (['rejected','completed'].includes(resolution) && !reason.trim())} onClick={()=>void run(saveReview)}>Сохранить решение</Button><Button variant="ghost" onClick={()=>setReviewing(null)}>Отмена</Button></section>}
    </section>}
    {tab==='journal' && <><div className="flex flex-wrap gap-3"><label>Поиск<Input value={query} onChange={(e) => setQuery(e.target.value)} /></label><label>Местная дата<Input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label><Button variant="outline" disabled={busy} onClick={() => void run(() => load())}>Обновить</Button></div>
    {data?.items.length === 0 && (query || day ? <div className="space-y-2"><p>По этим условиям записей нет. Измените поиск или дату.</p><Button variant="outline" onClick={() => { setQuery(''); setDay(''); }}>Сбросить фильтры</Button></div> : <p>Записей пока нет. Например: «Сегодня клиенты спрашивали про новую услугу».</p>)}
    {data?.items.map((entry) => <article id={`journal-${entry.id}`} key={entry.id} className="space-y-2 rounded-xl border bg-card p-4 text-card-foreground">
      {!entry.is_voided&&<Link className="inline-block text-sm underline" to={embedded?`${miniAppPath()}?screen=business_knowledge&tab=more&module=business_knowledge&scope_type=business&scope_id=${encodeURIComponent(businessId||'')}&source_entry=${encodeURIComponent(entry.id)}${entry.facts_json.knowledge_proposal?`&${entry.facts_json.knowledge_proposal.kind==='field'?'field':'rule'}=${encodeURIComponent(entry.facts_json.knowledge_proposal.record_id)}`:''}`:`/dashboard/profile?section=knowledge&business_id=${encodeURIComponent(businessId||'')}&scope_type=business&source_entry=${encodeURIComponent(entry.id)}${entry.facts_json.knowledge_proposal?`&${entry.facts_json.knowledge_proposal.kind==='field'?'field':'rule'}=${encodeURIComponent(entry.facts_json.knowledge_proposal.record_id)}`:''}`}>Предложить изменение сведений</Link>}
      <p>{entry.facts_json.quote || entry.original_text}</p><p className="text-sm text-muted-foreground">Автор: {entry.author_name || 'не указан'} · {new Date(entry.occurred_at).toLocaleString()} · {journalChannelLabels[entry.channel] || 'LocalOS'} · {entry.is_voided ? 'Отменено' : entry.booking_id ? 'Связано с визитом' : 'Без привязки к визиту'} · версия {entry.version}</p>
      <details><summary>Исходное сообщение</summary><p>{entry.original_text}</p></details>
      {editing?.id === entry.id ? <div className="space-y-2"><label>Исправленный текст<Textarea autoFocus value={correction} onChange={(e) => setCorrection(e.target.value)} /></label><Button disabled={busy || !correction.trim()} onClick={() => void run(() => change(entry, false))}>Сохранить исправление</Button><Button variant="ghost" onClick={() => setEditing(null)}>Закрыть</Button></div> : data.enabled && entry.can_edit && !entry.is_voided && <div className="flex gap-2"><Button variant="outline" disabled={busy} onClick={() => { setEditing(entry); setCorrection(entry.facts_json.quote || entry.original_text); }}>Исправить</Button><Button variant="outline" disabled={busy} onClick={() => void run(() => change(entry, true))}>Отменить запись</Button></div>}
      <Button variant="ghost" onClick={() => void run(async () => { const business = businessId; const value = await request(`/work-journal/${entry.id}/history?business_id=${business}`); if (scope.current === business) setHistory((previous) => ({ ...previous, [entry.id]: value.items })); })}>История</Button>
      {history[entry.id]?.map((item) => <p key={`${item.created_at}:${item.after_json.version}`} className="text-sm">{new Date(item.created_at).toLocaleString(language)} · {item.after_json.is_voided ? 'Отменено' : item.after_json.facts_json?.quote || item.after_json.decision || 'Решение обновлено'}</p>)}
    </article>)}
    </>}
    {data?.role==='owner' && data.review_enabled && data.can_decide!==false && <details className="rounded-xl border bg-card p-4"><summary>Настройки разбора и уведомлений</summary><div className="space-y-3 pt-3"><p>Управляющий получает доступ только к выбранному бизнесу. Изменение права требует подтверждения.</p><label className="block">Управляющий<select className="block rounded-md border bg-background p-2" value={reviewerId} onChange={e=>setReviewerId(e.target.value)}><option value="">Выберите участника</option>{data.members?.map(member=><option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></label>{[true,false].map(grant=><Button key={String(grant)} variant="outline" disabled={busy || !reviewerId} onClick={()=>void run(async()=>{const business=businessId;const preview:Answer=await request('/work-journal/policy/preview',{method:'POST',body:JSON.stringify({business_id:business,kind:'reviewer',user_id:reviewerId,enabled:grant,request_id:crypto.randomUUID()})});if(scope.current===business)setAnswer(preview);})}>{grant?'Предоставить право':'Отозвать право'}</Button>)}<label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={digestEnabled} onChange={event=>setDigestEnabled(event.target.checked)} />Получать уведомления журнала</label><p className="text-sm text-muted-foreground">Срочные записи и дневная сводка. Включаются только по вашему выбору; сами записи всегда доступны в журнале.</p><label className="block">Время дневной сводки в часовом поясе бизнеса<Input type="time" value={digestTime} onChange={e=>setDigestTime(e.target.value)} /></label><Button variant="outline" disabled={busy} onClick={()=>void run(async()=>{const business=businessId;await request('/work-journal/digest-settings',{method:'POST',body:JSON.stringify({business_id:business,local_time:digestTime,enabled:digestEnabled})});if(scope.current===business)setAnswer({chat_response:digestEnabled?'Уведомления журнала включены.':'Уведомления журнала выключены.'});})}>Сохранить уведомления</Button></div></details>}
    {data?.role === 'owner' && <details className="rounded-xl border bg-card p-4 text-card-foreground"><summary className="cursor-pointer font-semibold">Правила допродаж</summary><div className="space-y-3 pt-3"><p>Изменения применяются только после вашего подтверждения. Точка — выбранный бизнес.</p>
      {!data.policy?.rules_json.length && <p>Дополнительных правил пока нет.</p>}
      {data.policy?.rules_json.map((rule) => <p key={rule.id}>{rule.instruction} · {rule.permanent ? 'постоянно' : `${rule.starts_at || 'сразу'} — ${rule.ends_at}`}</p>)}
      <Button variant="outline" onClick={() => setText('Измени правила рекомендаций: ')}>Подготовить изменение правил</Button>
      {data.policy_history?.filter((item) => item.kind === 'rules').map((item) => <div key={item.id}><span>{new Date(item.created_at).toLocaleString(language)}</span><Button variant="ghost" disabled={busy || !data.enabled} onClick={() => void run(async () => { const business = businessId; const preview: Answer = await request('/work-journal/policy/preview', { method: 'POST', body: JSON.stringify({ business_id: business, restore_history_id: item.id, request_id: crypto.randomUUID() }) }); if (scope.current === business) setAnswer(preview); })}>Подготовить откат</Button></div>)}
    </div></details>}
      </TabsContent>
    </Tabs>
  </div>;
}
