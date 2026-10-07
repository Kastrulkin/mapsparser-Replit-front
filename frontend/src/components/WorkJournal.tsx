import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { OperatorVoiceInput, voiceHeaders } from '@/components/operator/OperatorVoice';

const defaultHeaders = voiceHeaders;
type Entry = { id: string; version: number; user_id: string; can_edit?: boolean; channel: string; occurred_at: string; original_text: string; is_voided: boolean; booking_id?: string; facts_json: { quote?: string; outcome?: string; reason?: string } };
type Rule = { id: string; instruction: string; permanent?: boolean; starts_at?: string; ends_at?: string };
type PolicyHistory = { id: string; kind: string; created_at: string };
type Data = { enabled: boolean; role?: string; items: Entry[]; policy?: { version: number; rules_json: Rule[] }; policy_history?: PolicyHistory[] };
type Answer = { chat_response?: string; conversation_id?: string; status?: string; approval?: { action_id?: string; status?: string }; operator_result?: Answer };

export function WorkJournal({ businessId, headers = defaultHeaders, embedded = false }: { embedded?: boolean; businessId?: string | null; headers?: () => Record<string, string> }) {
  const [data, setData] = useState<Data | null>(null); const [text, setText] = useState('');
  const [query, setQuery] = useState(''); const [day, setDay] = useState('');
  const [answer, setAnswer] = useState<Answer | null>(null); const [conversation, setConversation] = useState<string>();
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [editing, setEditing] = useState<Entry | null>(null); const [correction, setCorrection] = useState('');
  const [history, setHistory] = useState<Record<string, { created_at: string; after_json: Entry }[]>>({});
  const openedEntry = useRef('');
  const scope = useRef(businessId); scope.current = businessId;
  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const requestedBusiness=scope.current;
    const response = await fetch(`/api${path}`, { ...init, headers: { ...headers(), 'Content-Type': 'application/json' } });
    const body = await response.json();
    if (!response.ok) {
      if ([401,403].includes(response.status) && scope.current===requestedBusiness) {setData(null);setAnswer(null);setHistory({});setEditing(null);setConversation(undefined);}
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
  useEffect(() => { setData(null); setText(''); setAnswer(null); setConversation(undefined); setEditing(null); setHistory({}); setError(''); setQuery(''); setDay(''); setBusy(false); }, [businessId]);
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
    const raw: Answer = await request('/operator/chat', { method: 'POST', body: JSON.stringify({ business_id: business, input_context: 'work_journal', channel: headers === defaultHeaders ? 'web' : 'telegram_mini_app', conversation_id: conversation, message, request_id: crypto.randomUUID(), ...source }) });
    if (scope.current !== business) return;
    setAnswer(raw.operator_result || raw); setConversation(raw.conversation_id); setText(''); await load();
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
  if (!businessId) return <p>Выберите бизнес, чтобы открыть рабочий журнал.</p>;
  return <div className="space-y-5">
    <div>{!embedded && <h1 className="text-2xl font-semibold">Рабочий журнал</h1>}<p className="text-sm text-muted-foreground">Сообщайте о работе и спрашивайте, что предложить клиентам. Заметки сохраняются с возможностью отмены.</p></div>
    {error && <p role="alert">{error}</p>}
    {data && !data.enabled && <p role="status">Новый ввод пока отключён. Сохранённая история доступна.</p>}
    {data?.enabled && <section className="space-y-3 rounded-xl border bg-card p-4 text-card-foreground">
      <label className="block">Сообщение Оператору<Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Клиент отказался от ухода: дорого. Или: что предложить клиентам сегодня?" /></label>
      <Button disabled={busy || !text.trim()} onClick={() => void run(() => submit(text))}>Отправить</Button>
      <OperatorVoiceInput directSubmit disabled={busy} businessId={businessId} conversationId={conversation} channel={headers === defaultHeaders ? 'web' : 'telegram_mini_app'} headers={headers} onSubmit={submit} />
      {answer?.chat_response && <p className="whitespace-pre-wrap" role="status">{answer.chat_response}</p>}
      {answer?.approval?.action_id && answer.approval.status === 'pending' && <div className="flex gap-2"><Button disabled={busy} onClick={() => void run(() => decision(true))}>Подтвердить изменение</Button><Button variant="outline" disabled={busy} onClick={() => void run(() => decision(false))}>Отклонить</Button></div>}
    </section>}
    <div className="flex flex-wrap gap-3"><label>Поиск<Input value={query} onChange={(e) => setQuery(e.target.value)} /></label><label>Местная дата<Input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label><Button variant="outline" disabled={busy} onClick={() => void run(() => load())}>Обновить</Button></div>
    {data?.items.length === 0 && <p>Записей пока нет. Например: «Запомни: сегодня клиенты спрашивали про новую услугу».</p>}
    {data?.items.map((entry) => <article id={`journal-${entry.id}`} key={entry.id} className="space-y-2 rounded-xl border bg-card p-4 text-card-foreground">
      <p>{entry.facts_json.quote || entry.original_text}</p><p className="text-sm text-muted-foreground">{new Date(entry.occurred_at).toLocaleString()} · {entry.channel} · {entry.is_voided ? 'Отменено' : entry.booking_id ? 'Связано с визитом' : 'Без привязки к визиту'} · версия {entry.version}</p>
      <details><summary>Исходное сообщение</summary><p>{entry.original_text}</p></details>
      {editing?.id === entry.id ? <div className="space-y-2"><label>Исправленный текст<Textarea autoFocus value={correction} onChange={(e) => setCorrection(e.target.value)} /></label><Button disabled={busy || !correction.trim()} onClick={() => void run(() => change(entry, false))}>Сохранить исправление</Button><Button variant="ghost" onClick={() => setEditing(null)}>Закрыть</Button></div> : data.enabled && entry.can_edit && !entry.is_voided && <div className="flex gap-2"><Button variant="outline" disabled={busy} onClick={() => { setEditing(entry); setCorrection(entry.facts_json.quote || entry.original_text); }}>Исправить</Button><Button variant="outline" disabled={busy} onClick={() => void run(() => change(entry, true))}>Отменить запись</Button></div>}
      <Button variant="ghost" onClick={() => void run(async () => { const business = businessId; const value = await request(`/work-journal/${entry.id}/history?business_id=${business}`); if (scope.current === business) setHistory((previous) => ({ ...previous, [entry.id]: value.items })); })}>История</Button>
      {history[entry.id]?.map((item) => <p key={`${item.created_at}:${item.after_json.version}`} className="text-sm">{item.created_at} · {item.after_json.is_voided ? 'Отменено' : item.after_json.facts_json.quote}</p>)}
    </article>)}
    {data?.role === 'owner' && <section className="space-y-3 rounded-xl border bg-card p-4 text-card-foreground"><h2 className="text-lg font-semibold">Правила рекомендаций</h2><p>Изменения применяются только после вашего подтверждения. Точка — выбранный бизнес.</p>
      {!data.policy?.rules_json.length && <p>Дополнительных правил пока нет.</p>}
      {data.policy?.rules_json.map((rule) => <p key={rule.id}>{rule.instruction} · {rule.permanent ? 'постоянно' : `${rule.starts_at || 'сразу'} — ${rule.ends_at}`}</p>)}
      <Button variant="outline" onClick={() => setText('Измени правила рекомендаций: ')}>Изменить правила через Оператора</Button>
      {data.policy_history?.filter((item) => item.kind === 'rules').map((item) => <div key={item.id}><span>{item.created_at}</span><Button variant="ghost" disabled={busy || !data.enabled} onClick={() => void run(async () => { const business = businessId; const preview: Answer = await request('/work-journal/policy/preview', { method: 'POST', body: JSON.stringify({ business_id: business, restore_history_id: item.id, request_id: crypto.randomUUID() }) }); if (scope.current === business) setAnswer(preview); })}>Подготовить откат</Button></div>)}
    </section>}
  </div>;
}
