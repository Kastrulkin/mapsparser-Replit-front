import { PartnershipGroupLaunch } from './PartnershipGroupLaunch';
import { mobileJsonHeaders, readMobileJson } from '@/lib/mobileDataClient';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

type Touch = { id: string; sequence_index: number; channel: string; subject?: string; generated_text: string; recipient: string; contact_source?: string; sender_name?: string; sender_identity?: string; scheduled_at?: string; status: string };
type Prepared = { id: string; lead_id: string; name: string; address?: string; status: string; needs_review: boolean; hold_reason?: string; review_digest: string; touches: Touch[]; policy_json: { prepared_group?: string } };
const statusLabels: Record<string,string> = {approved:'утверждено',active:'в работе',paused:'на паузе',completed:'завершено',cancelled:'отменено'};
const channelName: Record<string,string> = { telegram: 'Telegram', email: 'Электронная почта' };

export function PreparedPartnershipMessages({ businessId,searchTaskId,showMessages=true,onCountChange,mobile=false }: { businessId: string; mobile?: boolean; searchTaskId?: string; showMessages?: boolean; onCountChange?: (count: number)=>void }) {
  const [items,setItems]=useState<Prepared[]>([]),[error,setError]=useState(''),[notice,setNotice]=useState(''),[loading,setLoading]=useState(false),[busy,setBusy]=useState(''),[selected,setSelected]=useState<Prepared|null>(null),[checked,setChecked]=useState(false),[group,setGroup]=useState(''),[fileItems,setFileItems]=useState<unknown[]>([]),[fileName,setFileName]=useState('');
  const [pendingJobs,setPendingJobs]=useState(0);
  const inFlightEpoch=useRef<number|null>(null);
  const mounted=useRef(true),scope=useRef(businessId),epoch=useRef(0);if(scope.current!==businessId){scope.current=businessId;epoch.current++;}
  const request = (path: string, options?: RequestInit) => mobile ? fetch(`/api${path}`, { ...options, headers: mobileJsonHeaders() }).then(readMobileJson<{ items?: Prepared[]; jobs?: unknown[]; job?: { id?: string }; error?: string }>) : options ? newAuth.makeRequest(path, options) : newAuth.makeRequest(path);
  const load=async (keepError=false) => {
    if(!mounted.current || inFlightEpoch.current===epoch.current)return;const current=businessId,version=epoch.current;inFlightEpoch.current=version;setLoading(true);
    try { const result=await request(`/partnership/prepared-messages?business_id=${encodeURIComponent(current)}${searchTaskId ? `&search_task_id=${encodeURIComponent(searchTaskId)}` : ''}`);if(!mounted.current || scope.current!==current || epoch.current!==version)return;setItems(result.items || []);onCountChange?.((result.items || []).reduce((total:number,item:Prepared)=>total+(item.hold_reason ? 0 : item.touches.length),0));setPendingJobs((result.jobs || []).length);if(!keepError)setError(''); }
    catch(issue) {if(scope.current===current && epoch.current===version)setError(issue instanceof Error?issue.message:'Не удалось загрузить касания. Повторите проверку.');}
    finally {if(inFlightEpoch.current===version)inFlightEpoch.current=null;if(scope.current===current && epoch.current===version)setLoading(false);}
  };
  useEffect(()=>{mounted.current=true;setItems([]);setPendingJobs(0);setSelected(null);setChecked(false);setError('');setNotice('');setGroup('');setFileItems([]);setFileName('');void load();return()=>{mounted.current=false;epoch.current++;};},[businessId,searchTaskId,mobile]);
  useEffect(()=>{if(!pendingJobs)return;const timer=setInterval(()=>void load(true),5000);return()=>clearInterval(timer);},[businessId,searchTaskId,pendingJobs]);
  useEffect(()=>{if(!showMessages){setSelected(null);setChecked(false);}},[showMessages]);
  const groups=Array.from(new Set(items.map(item=>item.policy_json.prepared_group || 'Подготовленные письма')));
  const activeGroup=group || groups[0];
  const visible=searchTaskId ? items.filter(item=>!item.hold_reason) : items.filter(item=>(item.policy_json.prepared_group || 'Подготовленные письма')===activeGroup);
  const confirm=async () => {
    if(!selected || !checked)return;const current=businessId;setBusy(selected.id);setError('');
    try {await request('/partnership/prepared-messages',{method:'POST',body:JSON.stringify({business_id:current,action:'review',campaign_id:selected.id,review_digest:selected.review_digest,save:true})});if(!mounted.current || scope.current!==current)return;setSelected(null);setChecked(false);setNotice('Тексты подтверждены. Отправка ещё не разрешена: выберите время и подтвердите её отдельно.');await load();}
    catch(issue) {if(scope.current===current)setError(issue instanceof Error?issue.message:'Не удалось подтвердить тексты.');}
    finally {if(scope.current===current)setBusy('');}
  };
  const importCopy=async () => {
    const current=businessId;setBusy('import');setError('');setNotice('Проверяем прежнюю переписку подключённого отправителя. Сохраняем только черновики, без отправки.');
    try {
      const jobs=[];
      for(const item of fileItems){
        if(!mounted.current || scope.current!==current)return;
        const response=await request('/partnership/prepared-messages',{method:'POST',body:JSON.stringify({business_id:current,item,save:true})});
        if(!response.job)throw new Error('Сохранение не подтверждено. Обновите список перед повтором.');
        jobs.push(response.job);
      }
      let states=jobs;
      while(true){
        if(!mounted.current || scope.current!==current)return;
        const saved=states.filter(job=>job.status==='completed').length;
        const pending=states.filter(job=>!job.terminal);
        setNotice(`Сохранено компаний: ${saved} из ${jobs.length}. Проверяем: ${pending.length}. Отправлено: 0.`);
        await load(true);
        if(!pending.length)break;
        await new Promise(resolve=>setTimeout(resolve,2000));
        states=await Promise.all(states.map(async job=>job.terminal?job:(await request(`/partnership/prepared-messages?business_id=${encodeURIComponent(current)}&job_id=${encodeURIComponent(job.id)}`)).job));
      }
      const failures=states.filter(job=>job.status!=='completed');
      if(failures.length)throw new Error(failures.map(job=>job.error || 'Проверка остановлена. Ничего не отправлено.').join(' '));
      if(scope.current===current)setFileItems([]);
    }
    catch(issue) {if(scope.current===current){setError(issue instanceof Error?issue.message:'Сохранение остановлено. Проверьте уже сохранённые касания.');await load(true);}}
    finally {if(scope.current===current)setBusy('');}
  };
  if(!showMessages)return null;
  return <section aria-label="Готовые касания партнёрам" className="space-y-4 rounded-2xl border border-border bg-card p-4 text-card-foreground">
    {searchTaskId && <PartnershipGroupLaunch businessId={businessId} collectionId={searchTaskId} mobile={mobile} />}
    <header><h2 className="text-xl font-semibold">Первые обращения новым партнёрам</h2><p className="mt-2 text-sm text-muted-foreground">Проверьте получателя и готовые сообщения. Подтверждение текста ничего не отправляет. Любой ответ остановит дальнейшие касания.</p></header>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status" className="text-sm">{notice}</p>}
    {!searchTaskId && groups.length>1 && <label className="block text-sm">Подборка<select aria-label="Подборка готовых касаний" value={activeGroup} onChange={event=>{setGroup(event.target.value);setSelected(null);setChecked(false);}} className="mt-2 min-h-11 w-full rounded-md border bg-background p-2">{groups.map(name=><option key={name}>{name}</option>)}</select></label>}
    {activeGroup && <p className="font-medium">{searchTaskId ? 'Выбранная подборка' : activeGroup} · компаний: {visible.length}</p>}
    {pendingJobs>0 && <p role="status" className="text-sm">Проверяем переписку и сохраняем касания. Можно закрыть страницу: результат останется здесь. Заданий: {pendingJobs}.</p>}
    {loading && items.length===0 && <p role="status">Загружаем сохранённые сообщения…</p>}
    {visible.map(item=><article key={item.id} className="space-y-3 rounded-xl border border-border p-4"><h3 className="font-semibold">{item.name}</h3><p className="text-sm text-muted-foreground">{item.address}</p><p className="text-sm">{channelName[item.touches[0]?.channel] || 'Канал нужно проверить'} · {item.touches[0]?.recipient || 'Получатель не выбран'}</p><p className="text-sm text-muted-foreground">Отправитель: {[item.touches[0]?.sender_name,item.touches[0]?.sender_identity].filter(Boolean).join(' · ') || 'Не выбран'}</p>{item.touches[0]?.contact_source && <a className="block break-words text-sm underline" href={item.touches[0].contact_source} target="_blank" rel="noopener noreferrer">Источник сведений</a>}<p className="text-sm">{item.hold_reason || (item.status!=='draft'?'Состояние: '+(statusLabels[item.status] || 'проверьте историю'):item.needs_review?'Готово к вашему просмотру':'Тексты проверены. Отправка ожидает отдельного подтверждения.')}</p><p className="whitespace-pre-wrap break-words text-sm leading-6">{item.touches[0]?.generated_text}</p><Button type="button" variant="outline" onClick={()=>{setSelected(item);setChecked(false);setError('');}}>Посмотреть все касания ({item.touches.length})</Button>{!item.needs_review && !item.hold_reason && <Button asChild><Link to={`/dashboard/partnerships?business_id=${encodeURIComponent(businessId)}&section=letters&campaign_id=${encodeURIComponent(item.id)}&lead=${encodeURIComponent(item.lead_id)}&item_id=${encodeURIComponent(item.lead_id)}`}>Перейти к отправке</Link></Button>}</article>)}
    {!loading && !error && items.length===0 && <p className="text-sm text-muted-foreground">Готовых обращений пока нет. Откройте компанию ниже и подготовьте письмо в чате или добавьте уже подготовленные тексты.</p>}
    <Dialog open={selected!==null} onOpenChange={open=>{if(!open && busy===''){setSelected(null);setChecked(false);}}}><DialogContent className="max-h-[85dvh] overflow-y-auto">{selected && <div className="space-y-4"><DialogHeader><DialogTitle>Проверьте сообщения для {selected.name}</DialogTitle><DialogDescription>Подтверждаете только тексты. Дату и отправку нужно будет подтвердить отдельно.</DialogDescription></DialogHeader><p className="text-sm">Кому: {selected.touches[0]?.recipient}</p>{selected.touches.map((touch,index)=><div key={touch.id} className="space-y-2 border-t pt-3"><h4 className="font-medium">{index===0?'Первое обращение':`Повторное касание ${index}`}</h4>{touch.scheduled_at && <p className="text-xs text-muted-foreground">Предлагаемая дата: {new Date(touch.scheduled_at).toLocaleString('ru-RU')}. Можно изменить перед запуском.</p>}{touch.subject && <p className="text-sm">Тема: {touch.subject}</p>}<p className="whitespace-pre-wrap break-words text-sm leading-6">{touch.generated_text}</p></div>)}{selected.hold_reason?<p role="alert" className="text-sm text-destructive">{selected.hold_reason}</p>:selected.needs_review && selected.status==='draft' && <><label className="flex min-h-11 gap-3 text-sm"><input type="checkbox" checked={checked} onChange={event=>setChecked(event.target.checked)} />Я проверил все тексты, получателя и условия предложения.</label><Button type="button" disabled={!checked || busy!==''} onClick={()=>void confirm()}>Подтвердить только тексты</Button><p className="text-xs text-muted-foreground">Сообщения сохранятся без запуска. Время и отправку нужно подтвердить отдельно.</p></>}<Button variant="outline" disabled={busy!==''} onClick={()=>{setSelected(null);setChecked(false);}}>Закрыть просмотр</Button></div>}</DialogContent></Dialog>
    <details><summary className="min-h-11 cursor-pointer py-3 text-sm">Добавить уже подготовленные тексты</summary><div className="space-y-3"><p className="text-sm text-muted-foreground">Загрузите файл подготовленной подборки. Компания, контакт и прежняя история проверяются перед сохранением. Существующие группы сохранятся.</p><input aria-label="Файл подготовленных касаний" type="file" accept=".json,application/json" disabled={busy!==''} onChange={async event=>{const file=event.target.files?.[0];if(!file)return;setFileItems([]);setError('');try{if(file.size>2000000)throw new Error('Файл слишком большой.');const value=JSON.parse(await file.text());if(!Array.isArray(value) || value.length<1 || value.length>50)throw new Error('Нужна подборка от 1 до 50 компаний.');if(scope.current===businessId){setFileItems(value);setFileName(file.name);}}catch(issue){setError(issue instanceof Error?issue.message:'Не удалось прочитать файл.');}}}/>{fileItems.length>0 && <><p className="text-sm">{fileName} · компаний: {fileItems.length}</p><Button disabled={busy!==''} onClick={()=>void importCopy()}>Сохранить касания без отправки</Button></>}</div></details>
    <Button type="button" variant="ghost" disabled={loading || busy!==''} onClick={()=>void load()}>Обновить касания</Button>
  </section>;
}
