import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';

type Conversation = { id: string; client_name?: string; client_phone: string; current_state: string };
type Message = { id: string; content: string; sender: string; message_type: string };
const labels: Record<string,string> = { waiting_for_staff:'Ожидает сотрудника', human_active:'Сотрудник подключился', closing:'Завершён' };
const events: Record<string,string> = { handoff_requested:'Обращение добавлено в очередь сотрудников.',handoff_accept:'Сотрудник принял диалог.',handoff_close:'Сотрудник завершил диалог.',handoff_reply:'Сотрудник подготовил ответ.' };

export function ClientHandoffInbox({businessId}:{businessId:string}) {
  const [items,setItems]=useState<Conversation[]>([]);
  const [selected,setSelected]=useState<string|null>(null);
  const [messages,setMessages]=useState<Message[]>([]);
  const [reply,setReply]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const lifetime=useRef({active:true});
  const listRevision=useRef(0);
  const messageRevision=useRef(0);
  const selection=useRef(selected);selection.current=selected;
  const current=items.find(item=>item.id===selected);
  const request=async(path:string,body?:object) => {
    const token=newAuth.getToken();
    const response=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{...(token?{Authorization:'Bearer '+token}:{}),'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
    const result=await response.json();
    if(!response.ok) throw new Error(result.error || 'Не удалось выполнить действие.');
    return result;
  };
  const load=async() => {
    const scope=lifetime.current;
    const revision=++listRevision.current;
    try {
      const result=await request('business/'+businessId+'/conversations?agent_id=all');
      if(scope.active&&revision===listRevision.current)setItems((result.conversations || []).filter((item:Conversation)=>labels[item.current_state]));
    } catch(reason) {if(scope.active)setError(reason instanceof Error?reason.message:'Не удалось загрузить очередь.');}
  };
  const loadMessages=async(id:string) => {
    const scope=lifetime.current;
    const revision=++messageRevision.current;
    const result=await request('conversations/'+id+'/messages');
    if(scope.active&&revision===messageRevision.current&&selection.current===id)setMessages(result.messages || []);
  };
  useEffect(()=>{
    const scope={active:true};lifetime.current=scope;
    setItems([]);setMessages([]);setSelected(null);selection.current=null;setError('');
    void load();const timer=setInterval(()=>{void load();if(selection.current)void loadMessages(selection.current).catch(()=>{if(scope.active)setError('Не удалось обновить сообщения. Обновите очередь.');});},15000);
    return ()=>{scope.active=false;clearInterval(timer);};
    // Each business owns a separate mounted inbox.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[businessId]);
  useEffect(()=>{setMessages([]);setReply('');if(selected)void loadMessages(selected).catch(reason=>{if(lifetime.current.active)setError(String(reason.message || reason));});},[selected]);
  const action=async(kind:string) => {
    const scope=lifetime.current;
    setBusy(true);setError('');
    try {
      if(kind==='test') {
        const result=await request('business/'+businessId+'/client-handoff-test',{});
        if(scope.active){selection.current=result.conversation_id;setSelected(result.conversation_id);}
      } else if(selected) {
        await request('business/'+businessId+'/client-handoffs/'+selected,{action:kind,...(kind==='reply'?{message:reply}:{})});
        if(scope.active){setReply('');await loadMessages(selected);}
      }
      if(scope.active)await load();
    } catch(reason) {if(scope.active)setError(reason instanceof Error?reason.message:'Не удалось выполнить действие.');}
    finally{if(scope.active)setBusy(false);}
  };
  return <section aria-label="Передача сотруднику" className="space-y-4">
    <header><h2 className="text-xl font-semibold">Обращения сотрудникам</h2><p className="text-muted-foreground">При передаче агент останавливает ответы. Сотрудник принимает обращение здесь; запись в очередь не означает, что он уже прочитал сообщение.</p></header>
    <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={()=>void load()}>Обновить очередь</Button><Button variant="outline" disabled={busy} onClick={()=>void action('test')}>Проверить передачу без клиента</Button></div>
    <p className="text-sm text-muted-foreground">Проверка создаст внутренний тестовый диалог. Сообщения клиентам и сотрудникам в мессенджеры не отправляются.</p>
    {error&&<p role="alert" className="text-destructive">{error}</p>}
    <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
      <div className="space-y-2">{items.length===0?<p>Обращений пока нет. Новый запрос на помощь появится здесь.</p>:items.map(item=><Button key={item.id} className="h-auto w-full justify-start whitespace-normal text-left" variant={selected===item.id?'default':'outline'} onClick={()=>{selection.current=item.id;setSelected(item.id);setError('');}}><span>{item.client_name || item.client_phone}<br/>{labels[item.current_state]}</span></Button>)}</div>
      <div className="space-y-3 rounded-lg border p-4">{current?<>
        <h3 className="font-semibold">{current.client_name || current.client_phone}</h3><p role="status">{labels[current.current_state]}. Автоответы приостановлены.</p>
        {current.current_state==='waiting_for_staff'&&<Button disabled={busy} onClick={()=>void action('accept')}>Взять диалог</Button>}
        <div className="space-y-2">{messages.map(message=><div key={message.id} className="rounded-md bg-muted p-3"><span className="text-xs text-muted-foreground">{events[message.message_type]?'Событие':message.sender==='client'?'Клиент':message.sender==='operator'?'Сотрудник':'Агент'}</span><p className="whitespace-pre-wrap">{events[message.message_type] || message.content}</p></div>)}</div>
        {current.current_state==='human_active'&&<>
          {current.client_phone.startsWith('test-handoff:')?<><label htmlFor="staff-test-reply">Ответ в тестовый диалог</label><Textarea id="staff-test-reply" value={reply} onChange={event=>setReply(event.target.value)} maxLength={4000}/><Button disabled={busy||!reply.trim()} onClick={()=>void action('reply')}>Добавить тестовый ответ</Button></>:<p>Для отправки ответа клиенту нужен подключённый и проверенный клиентский канал. Пока сообщение можно обработать вручную.</p>}
          <Button variant="outline" disabled={busy} onClick={()=>void action('close')}>Завершить диалог без включения агента</Button>
        </>}
      </>:<p>Выберите обращение, чтобы прочитать историю и принять диалог.</p>}</div>
    </div>
  </section>;
}
