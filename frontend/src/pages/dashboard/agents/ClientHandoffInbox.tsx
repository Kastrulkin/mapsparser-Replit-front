import { ClientDialogueGraph } from './ClientDialogueGraph';
import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';

type Conversation = { id: string; client_name?: string; client_phone: string; current_state: string };
type Message = { id: string; content: string; sender: string; message_type: string };
const labels: Record<string,string> = { waiting_for_staff:'Ожидает сотрудника', human_active:'Сотрудник подключился', closing:'Завершён' };
const events: Record<string,string> = { handoff_requested:'Обращение добавлено в очередь сотрудников.',handoff_accept:'Сотрудник принял диалог.',handoff_close:'Сотрудник завершил диалог.',handoff_reply:'Сотрудник подготовил ответ.' };

function notificationLabel(content:string) {
 try { const receipt=JSON.parse(content); return receipt.status==='sent'?'Тестовое уведомление отправлено в Telegram. Прочтение не подтверждено.':receipt.status==='failed'?'Тестовое уведомление не отправлено. Можно повторить проверку.':'Статус тестового уведомления проверяется. Повторная отправка заблокирована во избежание дубля.'; } catch { return 'Не удалось прочитать статус тестового уведомления.'; }
}

const defaultHeaders=():Record<string,string>=>{const token=newAuth.getToken();return token?{Authorization:'Bearer '+token}:{};};

export function ClientHandoffInbox({businessId,initialConversationId=null,headers=defaultHeaders}:{businessId:string;initialConversationId?:string|null;headers?:()=>Record<string,string>}) {
  const [items,setItems]=useState<Conversation[]>([]);
  const [selected,setSelected]=useState<string|null>(null);
  const [messages,setMessages]=useState<Message[]>([]);
  const [reply,setReply]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [showGraph,setShowGraph]=useState(false);
  const [messagesLoading,setMessagesLoading]=useState(false);
  const heading=useRef<HTMLHeadingElement>(null);
  const followedLink=useRef(false);
  const lifetime=useRef({active:true});
  const listRevision=useRef(0);
  const messageRevision=useRef(0);
  const selection=useRef(selected);selection.current=selected;
  const current=items.find(item=>item.id===selected);
  const request=async(path:string,body?:object) => {
    const response=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{...headers(),'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
    const result=await response.json();
    if(!response.ok) throw new Error(result.error || 'Не удалось выполнить действие.');
    return result;
  };
  const load=async() => {
    const scope=lifetime.current;
    const revision=++listRevision.current;
    try {
      const result=await request('business/'+businessId+'/conversations?agent_id=all');
      if(scope.active&&revision===listRevision.current) {
      const rows=(result.conversations || []).filter((item:Conversation)=>labels[item.current_state]);
      setItems(rows);
      if(initialConversationId&&!selection.current&&!followedLink.current) {
        if(rows.some((item:Conversation)=>item.id===initialConversationId)){followedLink.current=true;selection.current=initialConversationId;setSelected(initialConversationId);}
        else setError('Обращение из ссылки недоступно в выбранном бизнесе.');
      }
     }
    } catch(reason) {if(scope.active)setError(reason instanceof Error?reason.message:'Не удалось загрузить очередь.');}
  };
  const loadMessages=async(id:string) => {
    const scope=lifetime.current;
    const revision=++messageRevision.current;
    try {
      const result=await request('conversations/'+id+'/messages');
      if(scope.active&&revision===messageRevision.current&&selection.current===id)setMessages(result.messages || []);
    } finally {if(scope.active&&revision===messageRevision.current&&selection.current===id)setMessagesLoading(false);}
  };
  useEffect(()=>{
    const scope={active:true};lifetime.current=scope;
    setItems([]);setMessages([]);setSelected(null);selection.current=null;followedLink.current=false;setShowGraph(false);setError('');
    void load();const timer=setInterval(()=>{void load();if(selection.current)void loadMessages(selection.current).catch(()=>{if(scope.active)setError('Не удалось обновить сообщения. Обновите очередь.');});},15000);
    return ()=>{scope.active=false;clearInterval(timer);};
    // Each business owns a separate mounted inbox.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[businessId,initialConversationId,headers]);
  useEffect(()=>{setMessages([]);setReply('');setShowGraph(false);setMessagesLoading(Boolean(selected));heading.current?.focus();if(selected)void loadMessages(selected).catch(reason=>{if(lifetime.current.active&&selection.current===selected)setError(String(reason.message || reason));});},[selected]);
  const action=async(kind:string) => {
    const scope=lifetime.current;
    setBusy(true);setError('');
    try {
      if(kind==='test') {
        const result=await request('business/'+businessId+'/client-handoff-test',{});
        if(scope.active){selection.current=result.conversation_id;setSelected(result.conversation_id);}
      } else if(kind==='notify'&&selected) {
        await request('business/'+businessId+'/client-handoffs/'+selected+'/notify-self-test',{});
        if(scope.active)await loadMessages(selected);
      } else if(selected) {
        await request('business/'+businessId+'/client-handoffs/'+selected,{action:kind,...(kind==='reply'?{message:reply}:{})});
        if(scope.active){setReply('');await loadMessages(selected);}
      }
      if(scope.active)await load();
    } catch(reason) {if(scope.active)setError(reason instanceof Error?reason.message:'Не удалось выполнить действие.');}
    finally{if(scope.active)setBusy(false);}
  };
  const visibleMessages=messages.filter(message=>message.message_type==='text');
  const auditMessages=messages.filter(message=>Boolean(events[message.message_type])||message.message_type==='handoff_notification');
  const refresh=()=>{setError('');void load();if(selected)void loadMessages(selected).catch(()=>setError('Не удалось обновить переписку. Попробуйте ещё раз.'));};
  return <section aria-label="Передача сотруднику" className="space-y-4">
    <div className="flex items-center justify-between gap-3">
      {current?<Button variant="ghost" disabled={busy} onClick={()=>{selection.current=null;setSelected(null);setMessages([]);setError('');}}>Все обращения</Button>:<h2 ref={heading} tabIndex={-1} className="text-xl font-semibold outline-none">Обращения сотрудникам</h2>}
      <Button variant="ghost" disabled={busy} onClick={refresh}>Обновить</Button>
    </div>
    {error&&<p role="alert" className="text-destructive">{error}</p>}
    {current?<article className="space-y-4" aria-label="Выбранный диалог">
      <header className="space-y-1">
        <h3 ref={heading} tabIndex={-1} className="break-words text-lg font-semibold outline-none">{current.client_name || current.client_phone}</h3>
        <p role="status" className="text-sm text-muted-foreground">{labels[current.current_state]} · Автоответы на паузе</p>
      </header>
      {current.current_state==='waiting_for_staff'&&<Button className="w-full sm:w-auto" disabled={busy} onClick={()=>void action('accept')}>Взять диалог</Button>}
      <div className="space-y-3" aria-label="Переписка">
        {messagesLoading?<p className="text-sm text-muted-foreground">Загружаем переписку…</p>:visibleMessages.length===0?<p className="text-sm text-muted-foreground">Сообщений пока нет.</p>:visibleMessages.map(message=><div key={message.id} className={'max-w-full rounded-lg p-3 '+(message.sender==='client'?'bg-muted':'border bg-background')}>
          <p className="mb-1 text-xs text-muted-foreground">{message.sender==='client'?'Клиент':message.sender==='operator'?'Сотрудник':'Помощник'}</p>
          <p className="whitespace-pre-wrap break-words text-sm">{message.content}</p>
        </div>)}
      </div>
      {current.current_state==='human_active'&&<div className="space-y-3 border-t pt-4">
        {(current.client_phone.startsWith('test-handoff:')||current.client_phone.startsWith('tg-ras-pilot:'))?<>
          <label className="text-sm font-medium" htmlFor="staff-test-reply">{current.client_phone.startsWith('tg-ras-pilot:')?'Ответ клиенту в Telegram':'Ответ в тестовый диалог'}</label>
          <Textarea id="staff-test-reply" value={reply} onChange={event=>setReply(event.target.value)} maxLength={4000}/>
          <Button className="w-full sm:w-auto" disabled={busy||!reply.trim()} onClick={()=>void action('reply')}>{current.client_phone.startsWith('tg-ras-pilot:')?'Отправить клиенту в Telegram':'Добавить тестовый ответ'}</Button>
        </>:<p className="text-sm text-muted-foreground">Отправка клиенту станет доступна после подключения и проверки клиентского канала.</p>}
        <Button className="w-full sm:w-auto" variant="outline" disabled={busy} onClick={()=>void action('close')}>Завершить диалог без включения агента</Button>
      </div>}
      <div className="divide-y rounded-lg border px-3">
        <details className="py-3" key={'audit:'+current.id}><summary className="cursor-pointer text-sm font-medium">История действий</summary><div className="mt-3 space-y-2 text-sm text-muted-foreground">{auditMessages.length?auditMessages.map(message=><p key={message.id}>{message.message_type==='handoff_notification'?notificationLabel(message.content):events[message.message_type]}</p>):<p>Действий пока нет.</p>}</div></details>
        <details className="py-3" key={'graph:'+current.id} onToggle={event=>setShowGraph(event.currentTarget.open)}><summary className="cursor-pointer text-sm font-medium">Этапы диалога и граф</summary>{showGraph&&<div className="mt-3"><ClientDialogueGraph key={businessId+current.id+current.current_state} businessId={businessId} conversationId={current.id} headers={headers}/></div>}</details>
      </div>
    </article>:<div className="space-y-2" aria-label="Список обращений">{items.length===0?<p className="text-sm text-muted-foreground">Обращений пока нет. Когда клиент попросит помощи, его диалог появится здесь.</p>:items.map(item=><Button key={item.id} className="h-auto min-h-12 w-full justify-start whitespace-normal text-left" variant="outline" onClick={()=>{selection.current=item.id;setSelected(item.id);setError('');}}><span className="min-w-0 break-words">{item.client_name || item.client_phone}<span className="mt-1 block text-xs text-muted-foreground">{labels[item.current_state]}</span></span></Button>)}</div>}
    <details className="border-t pt-3"><summary className="cursor-pointer text-xs text-muted-foreground">Проверка без клиента</summary><div className="mt-3 space-y-3">
      <p className="text-xs text-muted-foreground">Внутренний тест. Сообщения клиентам и сотрудникам не отправляются. Уведомление себе запускается отдельно.</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={()=>void action('test')}>Проверить передачу без клиента</Button>{current?.current_state==='waiting_for_staff'&&current.client_phone.startsWith('test-handoff:')&&<Button variant="outline" disabled={busy} onClick={()=>void action('notify')}>Уведомить меня в Telegram (тест)</Button>}</div>
    </div></details>
  </section>;
}
