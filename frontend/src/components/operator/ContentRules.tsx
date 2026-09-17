import { useEffect, useId, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { voiceHeaders } from './OperatorVoice';

type Rule = { id: string; text: string; status: string; version: number; starts_at?: string; ends_at?: string; source: string; author_name?: string; updated_at: string };
type Payload = { timezone?: string; rules?: Rule[]; can_manage?: boolean; error?: string; history?: { snapshot: Rule }[] };
export function ContentRules({ businessId, headers = voiceHeaders }: { businessId: string; headers?: () => Record<string,string> }) {
  const label = useId();
  const [data, setData] = useState<Payload>({});
  const [text, setText] = useState('');
  const [startsDate,setStartsDate]=useState('');
  const [endsDate,setEndsDate]=useState('');
  const [periodChanged,setPeriodChanged]=useState(false);
  const [editing, setEditing] = useState<Rule | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [history, setHistory] = useState<Rule[]>([]);
  const generation = useRef(0);
  useEffect(() => {
    const controller = new AbortController(); generation.current++;
    setData({}); setText(''); setStartsDate('');setEndsDate('');setPeriodChanged(false);setEditing(null); setHistory([]); setError(''); setBusy(false);
    fetch(`/api/content-voice/rules?business_id=${encodeURIComponent(businessId)}`, {headers:headers(),signal:controller.signal})
      .then(async response => { const next: Payload = await response.json(); if (!response.ok) throw new Error(next.error || 'Правила недоступны'); if (!controller.signal.aborted) setData(next); })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить правила'); });
    return () => { controller.abort(); generation.current++; };
  },[businessId,headers,reload]);
  async function save(rule: Rule | null, cancel = false) {
    const version = generation.current; setBusy(true); setError('');
    try {
      const response = await fetch('/api/content-voice/rules', {method:rule ? 'PATCH':'POST',headers:{...headers(),'Content-Type':'application/json'},body:JSON.stringify({business_id:businessId,request_id:crypto.randomUUID(),text:cancel ? rule?.text:text,rule_id:rule?.id,expected_version:rule?.version,status:cancel?'cancelled':'active',starts_at:rule?.starts_at,ends_at:rule?.ends_at,...(periodChanged && !cancel ? {starts_date:startsDate || null,ends_date:endsDate || null}:{})})});
      const result: Payload = await response.json();
      if (version !== generation.current) return;
      if (!response.ok) throw new Error(result.error || 'Правило не сохранено');
      setReload(value => value+1);
    } catch(reason) { if (version === generation.current) setError(reason instanceof Error ? reason.message : 'Не удалось сохранить правило'); }
    finally { if (version === generation.current) setBusy(false); }
  }
  async function showHistory(rule: Rule) {
    const version=generation.current;setHistory([]);setError('');
    try {
      const response=await fetch(`/api/content-voice/rules/${encodeURIComponent(rule.id)}/history?business_id=${encodeURIComponent(businessId)}`,{headers:headers()});
      const result: Payload=await response.json();
      if(version!==generation.current)return;
      if(!response.ok)throw new Error(result.error || 'История недоступна');
      setHistory((result.history || []).map(entry=>entry.snapshot));
    } catch(reason) { if(version===generation.current)setError(reason instanceof Error ? reason.message:'История недоступна'); }
  }
  return <section className="rounded-xl border border-border p-4 space-y-3" aria-labelledby={label}>
    <h2 id={label} className="font-semibold">Правила для контента</h2>
    <p className="text-sm text-muted-foreground">Укажите, чего нельзя обещать в публикациях. Правила учитываются в новых текстах и при переписывании. Старые посты автоматически не меняются.</p>
    {error && <p role="alert">{error}</p>}
    {!data.rules && !error && <p role="status">Загружаем правила…</p>}
    {data.rules?.length===0 && <p>Пока нет правил. Например: «Не обещаем стрижку без слёз каждому ребёнку».</p>}
    {data.rules?.map(rule=><article key={rule.id} className="border-b border-border pb-3 space-y-2">
      <p className="whitespace-pre-wrap break-words">{rule.text}</p>
      <p className="text-sm text-muted-foreground">{rule.status!=='active'?'Отменено':rule.ends_at && new Date(rule.ends_at).getTime()<=Date.now()?'Срок завершён':rule.starts_at && new Date(rule.starts_at).getTime()>Date.now()?'Начнёт действовать':'Действует'}{rule.ends_at ? ` · до ${new Date(rule.ends_at).toLocaleString()}`:''}</p>
      <p className="text-sm text-muted-foreground">Этот бизнес · {rule.author_name || 'Пользователь'} · {new Date(rule.updated_at).toLocaleString()}</p>
      <div className="flex flex-wrap gap-2">
        {data.can_manage && rule.status==='active' && <><Button variant="outline" disabled={busy} onClick={()=>{setEditing(rule);setText(rule.text);setPeriodChanged(false);setStartsDate(rule.starts_at && data.timezone ? new Date(rule.starts_at).toLocaleDateString('sv-SE',{timeZone:data.timezone}):'');setEndsDate(rule.ends_at && data.timezone ? new Date(new Date(rule.ends_at).getTime()-1).toLocaleDateString('sv-SE',{timeZone:data.timezone}):'');}}>Изменить</Button><Button variant="ghost" disabled={busy} onClick={()=>save(rule,true)}>Отменить правило</Button></>}
        <Button variant="ghost" onClick={()=>showHistory(rule)}>История</Button>
      </div>
    </article>)}
    {history.length>0 && <div aria-live="polite"><h3 className="font-medium">История изменений</h3>{history.map(rule=><p key={rule.version}>{new Date(rule.updated_at).toLocaleString()} · {rule.status==='active'?'Сохранено':'Отменено'}: {rule.text}</p>)}</div>}
    {data.can_manage && <form className="space-y-2" onSubmit={event=>{event.preventDefault();void save(editing);}}>
      <label htmlFor={`${label}-text`}>{editing?'Исправьте правило':'Добавьте ограничение'}</label>
      <Textarea id={`${label}-text`} value={text} maxLength={6000} onChange={event=>setText(event.target.value)} disabled={busy}/>
      <details><summary className="cursor-pointer text-sm">Срок действия</summary>
        <p className="text-sm text-muted-foreground">{data.timezone ? `По времени бизнеса: ${data.timezone}. Без дат правило бессрочное.`:'Для временного правила сначала укажите часовой пояс в настройках бизнеса.'}</p>
        <label htmlFor={`${label}-start`}>Начало</label><Input id={`${label}-start`} type="date" value={startsDate} disabled={busy || !data.timezone} onChange={event=>{setStartsDate(event.target.value);setPeriodChanged(true);}}/>
        <label htmlFor={`${label}-end`}>Последний день действия</label><Input id={`${label}-end`} type="date" value={endsDate} disabled={busy || !data.timezone} onChange={event=>{setEndsDate(event.target.value);setPeriodChanged(true);}}/>
      </details>
      <Button type="submit" disabled={busy || !text.trim()}>{busy?'Сохраняем…':'Сохранить правило'}</Button>
      {editing && <Button variant="ghost" type="button" onClick={()=>{setEditing(null);setText('');setStartsDate('');setEndsDate('');setPeriodChanged(false);}}>Отменить редактирование</Button>}
    </form>}
    {data.can_manage===false && <p>Предложите изменение через Оператора: «Передай руководителю пожелание для текстов: …».</p>}
  </section>;
}
