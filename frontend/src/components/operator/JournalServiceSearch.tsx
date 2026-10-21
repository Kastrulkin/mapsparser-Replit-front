import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

type Answer = { status?: string; chat_response?: string; approval?: { action_id?: string; status?: string }; operator_result?: Answer };
export function JournalServiceSearch({ businessId, entryId, version, quote, city, channel, request, onStarted, onCancel }: {
  businessId: string; entryId: string; version: number; quote: string; city?: string; channel: string;
  request: (path: string, init?: RequestInit) => Promise<Answer>; onStarted: () => Promise<void>; onCancel: () => void;
}) {
  const [audience,setAudience]=useState(''); const [geography,setGeography]=useState(city || '');
  const [requirements,setRequirements]=useState(''); const [count,setCount]=useState(3);
  const [mode,setMode]=useState('find_only'); const [offer,setOffer]=useState(''); const [language,setLanguage]=useState('ru');
  const [preview,setPreview]=useState<Answer | null>(null); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const requestId=useRef(crypto.randomUUID()); const pendingId=useRef(''); const lifetime=useRef(new AbortController());
  useEffect(()=>{const controller=new AbortController();lifetime.current=controller;setAudience('');setGeography(city || '');setRequirements('');setCount(3);setMode('find_only');setOffer('');setLanguage('ru');setPreview(null);setError('');setBusy(false);pendingId.current='';requestId.current=crypto.randomUUID();return()=>controller.abort();
    // A city refresh must not replace an edited request; reset only with its scope.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[businessId,entryId,version]);
  const edited=()=>{setPreview(null);setError('');requestId.current=crypto.randomUUID();};
  async function perform(action:()=>Promise<void>) {
    const signal=lifetime.current.signal;setBusy(true);setError('');
    try{await action();}catch(reason){if(!signal.aborted)setError(reason instanceof Error?reason.message:'Не удалось подготовить поиск.');}
    finally{if(!signal.aborted)setBusy(false);}
  }
  return <section className="space-y-3 rounded-md border p-3" aria-label="Поиск исполнителя по записи">
    <h3 className="font-semibold">Найти исполнителя</h3><p className="text-sm text-muted-foreground">По записи сотрудника: {quote}</p>
    <fieldset disabled={busy} className="space-y-3">
      <label className="block">Кого найти?<Input autoFocus maxLength={500} value={audience} onChange={event=>{edited();setAudience(event.target.value);}} placeholder="Например: компании по мойке окон с выездом в салон"/></label>
      <label className="block">Город, район или адрес<Input maxLength={120} value={geography} onChange={event=>{edited();setGeography(event.target.value);}}/></label>
      <label className="block">Что проверить, каждое условие с новой строки<Textarea value={requirements} onChange={event=>{edited();setRequirements(event.target.value);}} placeholder="Выезжают по нашему адресу&#10;Могут прислать стоимость и свободное время"/></label>
      <div className="flex flex-wrap gap-3"><label>Сколько исполнителей<Input type="number" min={1} max={10} value={count} onChange={event=>{edited();setCount(Number(event.target.value));}}/></label><label>Результат<select className="block min-h-11 rounded-md border bg-background p-2" value={mode} onChange={event=>{edited();setMode(event.target.value);}}><option value="find_only">Список с проверенными контактами</option><option value="prepare_only">Список и черновики обращений</option></select></label></div>
      {mode==='prepare_only' && <><label className="block">О чём написать исполнителю<Textarea maxLength={2000} value={offer} onChange={event=>{edited();setOffer(event.target.value);}} placeholder="Что требуется, какие условия и сроки нужно уточнить"/></label><label>Язык обращения<select className="block min-h-11 rounded-md border bg-background p-2" value={language} onChange={event=>{edited();setLanguage(event.target.value);}}><option value="ru">Русский</option><option value="en">Английский</option></select></label></>}
    </fieldset>
    <p className="text-sm text-muted-foreground">Ищем в интернете. Условия выезда и близость проверяем по адресу; точное расстояние может быть неизвестно. До подтверждения поиск не запускается. Отправка обращений и договорённости требуют отдельного решения.</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {!preview && <Button disabled={busy || !audience.trim() || !geography.trim() || !Number.isInteger(count) || count<1 || count>10 || (mode==='prepare_only'&&!offer.trim())} onClick={()=>void perform(async()=>{
      const value=await request(`/work-journal/${entryId}/service-search/preview`,{method:'POST',signal:lifetime.current.signal,body:JSON.stringify({business_id:businessId,version,audience,geography,requirements:requirements.split('\n').map(value=>value.trim()).filter(Boolean),target_count:count,mode,offer,language,channel,request_id:requestId.current})});
      if(lifetime.current.signal.aborted)return;
      if(value.status!=='approval_required' || !value.approval?.action_id)throw new Error(value.chat_response || 'Поиск недоступен. Ничего не запущено.');
      pendingId.current=value.approval.status==='pending'?value.approval.action_id:'';setPreview(value);
    })}>Проверить условия и расходы</Button>}
    {preview && <div className="space-y-3 border-t pt-3"><h4 className="font-semibold">Проверьте перед запуском</h4><p className="whitespace-pre-wrap text-sm">{preview.chat_response}</p><Button disabled={busy || preview.approval?.status!=='pending'} onClick={()=>void perform(async()=>{
      const value=await request(`/operator/actions/${preview.approval?.action_id}/confirm`,{method:'POST',signal:lifetime.current.signal,body:JSON.stringify({business_id:businessId})});
      if(lifetime.current.signal.aborted)return;
      const result=value.operator_result || value;
      if(result.status!=='completed')throw new Error(result.chat_response || 'Поиск не запущен. Проверьте условия заново.');
      pendingId.current='';await onStarted();
    })}>Подтвердить запуск поиска</Button></div>}
    <Button variant="outline" disabled={busy} onClick={()=>void perform(async()=>{if(pendingId.current)await request(`/operator/actions/${pendingId.current}/reject`,{method:'POST',signal:lifetime.current.signal,body:JSON.stringify({business_id:businessId})});if(!lifetime.current.signal.aborted)onCancel();})}>Закрыть без запуска</Button>
  </section>;
}
