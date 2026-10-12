import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { BookOpen, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { browserBearerToken } from '@/lib/browserSessionFetch';
import { safeWorkReturn } from '@/lib/workNavigation';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { AudienceField, FieldForm, FormField, TextForm, ValueForm } from './KnowledgeForms';
import type { Audience, KnowledgeChange, KnowledgeData, KnowledgeHistory, KnowledgePayload, KnowledgeRecord, KnowledgeScope, KnowledgeTemplate } from './types';

const defaultHeaders = () => ({Authorization:`Bearer ${browserBearerToken()}`});
const blank:KnowledgeData={enabled:true,name:'',can_edit:false,can_configure:false,fields:[],rules:[],documents:[],members:[],editors:[],existing_sources:[]};
type Editor = {kind:'field'|'value'|'rule'|'document'|'upload'|'template'|'archive'|'proposal'; record?:KnowledgeRecord};
type ApiResult = {record?:KnowledgeRecord;duplicate?:boolean;error?:string;status?:string;approval?:{action_id:string;business_id:string};preview?:{before?:KnowledgeRecord;after?:KnowledgePayload}};
class RequestFailure extends Error { constructor(message:string,public status:number){super(message);} }
export function formatKnowledgeValue(record?:KnowledgeRecord|null,definition?:KnowledgeRecord):string {
  return formatPayload(record?.payload_json,definition?.payload_json);
}
function formatPayload(p?:KnowledgePayload,definition?:KnowledgePayload):string {
  if(!p||p.state==='unknown')return 'Не указано';
  if(p.state==='not_applicable')return 'Не применяется';
  if(typeof p.value==='boolean')return p.value?'Да':'Нет';
  if(p.value===null||p.value===undefined)return 'Не указано';
  const options=definition?.options;
  const label=(id:string)=>options?.find(o=>o.id===id)?.label||id;
  return Array.isArray(p.value)?p.value.map(label).join(', '):typeof p.value==='string'?label(p.value):String(p.value);
}
export function BusinessKnowledge({scope,headers=defaultHeaders,onBusinessChange,embedded=false,focusRecordId}: {scope:KnowledgeScope|null;headers?:()=>HeadersInit;onBusinessChange?:(id:string,requestedKind?:'business'|'network')=>void;embedded?:boolean;focusRecordId?:string}) {
  const location=useLocation();const navigate=useNavigate();const {language}=useLanguage();
  const identity=scope?scope.type+':'+scope.id:'';
  const generation=useRef(0);const panel=useRef<HTMLDivElement>(null);
  const pendingRequest=useRef<{signature:string;id:string}|null>(null);
  const requestKey=(payload:unknown)=>{const signature=JSON.stringify({identity,payload});if(pendingRequest.current?.signature!==signature)pendingRequest.current={signature,id:crypto.randomUUID()};return pendingRequest.current.id;};
  const headersRef=useRef(headers);headersRef.current=headers;
  const [snapshot,setSnapshot]=useState<{identity:string;data:KnowledgeData}|null>(null);
  const data=snapshot?.identity===identity?snapshot.data:null;
  const [loading,setLoading]=useState(false);const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [tab,setTab]=useState('fields');const [editor,setEditor]=useState<Editor|null>(null);
  const [templates,setTemplates]=useState<KnowledgeTemplate[]>([]);const [template,setTemplate]=useState('');const [selected,setSelected]=useState<string[]>([]);
  const [proposalText,setProposalText]=useState('');
  const [audience,setAudience]=useState<Audience>('team');const [file,setFile]=useState<File|null>(null);
  const [history,setHistory]=useState<{record:KnowledgeRecord;items:KnowledgeHistory[]}|null>(null);
  const [approval,setApproval]=useState<ApiResult|null>(null);
  const query=scope?new URLSearchParams({scope_type:scope.type,scope_id:scope.id}).toString():'';
  const queryRef=useRef(query);queryRef.current=query;
  const [proposalSource,setProposalSource]=useState<string|null>(null);
  const sourceEntry=proposalSource||new URLSearchParams(location.search).get('source_entry');
  const returnTo=safeWorkReturn(new URLSearchParams(location.search).get('return_to'));
  const api=useCallback(async <T,>(path:string,init:RequestInit={}):Promise<T>=>{
    const requestHeaders=new Headers(headersRef.current());
    if(init.body && !(init.body instanceof FormData))requestHeaders.set('Content-Type','application/json');
    else requestHeaders.delete('Content-Type');
    const response=await fetch(`/api/business-knowledge${path}${path.includes('?')?'&':'?'}${queryRef.current}`,{...init,headers:requestHeaders,cache:'no-store'});
    const result=await response.json();
    if(!response.ok)throw new RequestFailure(result.error||'Не удалось получить сведения.',response.status);
    return result;
  },[]);
  const fail=useCallback((caught:unknown)=>{
    if(caught instanceof RequestFailure&&[401,403,404].includes(caught.status)){setSnapshot(null);setEditor(null);setHistory(null);setApproval(null);}
    setError(caught instanceof Error?caught.message:'Не удалось получить сведения.');
  },[]);
  const reload=useCallback(async(signal?:AbortSignal)=>{
    if(!queryRef.current)return;
    const version=generation.current;setLoading(true);
    try{const result=await api<KnowledgeData>('',{signal});if(version===generation.current){setSnapshot({identity,data:result});setError('');}}
    catch(caught){if(version===generation.current && !(caught instanceof DOMException&&caught.name==='AbortError'))fail(caught);}
    finally{if(version===generation.current)setLoading(false);}
  },[api,fail,identity]);
  useEffect(()=>{
    generation.current+=1;pendingRequest.current=null;setSnapshot(null);setEditor(null);setHistory(null);setApproval(null);setTemplates([]);setTemplate('');setSelected([]);setFile(null);setError('');setNotice('');setProposalSource(null);setBusy(false);setTab('fields');
    const controller=new AbortController();void reload(controller.signal);
    return ()=>{generation.current+=1;controller.abort();};
  },[identity,reload]);
  useEffect(()=>{if(editor){panel.current?.focus();panel.current?.scrollIntoView({block:'nearest'});}},[editor,approval]);
  const deepId=new URLSearchParams(location.search).get('field')||new URLSearchParams(location.search).get('rule')||new URLSearchParams(location.search).get('document')||focusRecordId;
  useEffect(()=>{
    if(!data||!deepId)return;
    const record=data.fields.find(r=>r.id===deepId||r.value_record?.id===deepId)||data.rules.find(r=>r.id===deepId)||data.documents.find(r=>r.id===deepId);
    if(!record){setNotice('Запись недоступна в выбранном контексте.');return;}
    setTab(record.kind==='field'?'fields':record.kind==='rule'?'rules':'documents');
    requestAnimationFrame(()=>document.getElementById(`knowledge-${record.id}`)?.focus());
  },[data,deepId]);
  const act=async(change:KnowledgeChange)=>{
    const version=generation.current;setBusy(true);setError('');
    try{
      const proposed=!!sourceEntry&&['value','rule','document'].includes(change.operation);
      const result=await api<ApiResult>(proposed?'/preview':'',{method:'POST',body:JSON.stringify({...change,request_id:requestKey({...change,source_entry_id:proposed?sourceEntry:undefined}),source_entry_id:proposed?sourceEntry:undefined})});
      if(version!==generation.current)return;
      if(proposed)setApproval(result);
      else {pendingRequest.current=null;setEditor(null);setHistory(null);setNotice(change.operation==='rule'?'Правило сохранено. Проверьте работу, на которую оно влияет.':'Сведения сохранены.');await reload();}
    }catch(caught){if(version===generation.current){fail(caught);if(caught instanceof RequestFailure&&caught.status===409){await reload();setError(caught.message);setEditor(null);}}}
    finally{if(version===generation.current)setBusy(false);}
  };
  const showHistory=async(record:KnowledgeRecord)=>{
    const version=generation.current;
    try{const result=await api<{items:KnowledgeHistory[]}>(`/${encodeURIComponent(record.value_record?.id||record.id)}/history`);if(version===generation.current){setHistory({record,items:result.items});setEditor(null);}}
    catch(caught){if(version===generation.current)fail(caught);}
  };
  const openTemplates=async()=>{
    const version=generation.current;
    try{const result=await api<{items:KnowledgeTemplate[]}>('/templates');if(version===generation.current){setTemplates(result.items);const first=result.items.find(t=>t.type_key===data?.business_type)||result.items.find(t=>t.type_key==='other')||result.items[0];setTemplate(first?.type_key||'');setSelected(first?.fields.flatMap(f=>f.template_key?[f.template_key]:[])||[]);setEditor({kind:'template'});}}
    catch(caught){if(version===generation.current)fail(caught);}
  };
  const upload=async()=>{
    if(!file)return;const version=generation.current;setBusy(true);
    const form=new FormData();form.append('file',file);form.append('request_id',requestKey({operation:'upload',filename:file.name,size:file.size,modified:file.lastModified,id:editor?.record?.id,version:editor?.record?.version,audience:editor?.record?.audience||audience}));form.append('audience',editor?.record?.audience||audience);
    if(editor?.record){form.append('id',editor.record.id);form.append('version',String(editor.record.version));}
    try{const result=await api<ApiResult>('/documents',{method:'POST',body:form});if(version!==generation.current)return;
      setNotice(result.duplicate?'Такой файл уже загружен. Открыт существующий документ.':'Файл сохранён. Проверьте текст и подтвердите использование.');setFile(null);pendingRequest.current=null;await reload();if(version!==generation.current)return;if(result.record)setEditor({kind:'document',record:result.record});setTab('documents');
    }catch(caught){if(version===generation.current)fail(caught);}finally{if(version===generation.current)setBusy(false);}
  };
  const download=async(record:KnowledgeRecord,revision?:number)=>{
    const version=generation.current;
    try{const response=await fetch(`/api/business-knowledge/${record.id}/download?${query}${revision?`&version=${revision}`:''}`,{headers:headersRef.current(),cache:'no-store'});
      if(!response.ok){const result=await response.json();throw new RequestFailure(result.error||'Файл недоступен.',response.status);}
      const blob=await response.blob();if(version!==generation.current)return;
      const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=record.payload_json.filename||'document';link.click();URL.revokeObjectURL(url);
    }catch(caught){if(version===generation.current)fail(caught);}
  };
  const confirm=async()=>{
    const chosen=approval?.approval;if(!chosen)return;const version=generation.current;setBusy(true);
    try{const response=await fetch(`/api/operator/actions/${chosen.action_id}/confirm`,{method:'POST',headers:{...Object.fromEntries(new Headers(headersRef.current())),'Content-Type':'application/json'},body:JSON.stringify({business_id:chosen.business_id})});
      const result=await response.json();if(!response.ok||result.success===false||result.operator_result?.status==='blocked')throw new RequestFailure(result.error||result.chat_response||result.operator_result?.chat_response||'Не удалось подтвердить изменение.',response.status);
      if(version===generation.current){pendingRequest.current=null;setApproval(null);setEditor(null);setProposalSource(null);setNotice('Изменение из журнала подтверждено и сохранено.');await reload();}
    }catch(caught){if(version===generation.current)fail(caught);}finally{if(version===generation.current)setBusy(false);}
  };
  const date=(value:string)=>{const parsed=new Date(value);return Number.isNaN(parsed.getTime())?'Дата не указана':new Intl.DateTimeFormat(language,{dateStyle:'medium',timeStyle:'short'}).format(parsed);};
  const details=(record:KnowledgeRecord)=><details className="mt-2 text-sm"><summary className="cursor-pointer rounded-sm text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Источник и история</summary><div className="mt-3 grid gap-2"><p>{record.scope_type!==scope?.type||record.scope_id!==scope?.id?'Общие сведения сети. ':''}Источник: {record.payload_json.source||'Указано пользователем'}</p><p>Изменено {date(record.updated_at)} · автор {record.updated_by} · версия {record.version}. Время устройства.</p><p>{record.audience==='management'?'Только руководству':'Участникам бизнеса'}{record.payload_json.valid_until?` · актуально до ${new Intl.DateTimeFormat(language,{dateStyle:'medium',timeZone:'UTC'}).format(new Date(record.payload_json.valid_until))}`:''}</p><Button variant="outline" size="sm" onClick={()=>void showHistory(record)}>Посмотреть историю</Button></div></details>;
  const expired=(record:KnowledgeRecord)=>!!record.payload_json.valid_until&&record.payload_json.valid_until<new Date().toISOString().slice(0,10);
  const owned=(record:KnowledgeRecord)=>record.scope_type===scope?.type&&record.scope_id===scope?.id;
  const rowActions=(record:KnowledgeRecord)=><div className="flex flex-wrap gap-2">{!data?.can_edit&&scope?.type==='business'&&record.kind!=='document'&&<Button variant="outline" size="sm" onClick={()=>{setProposalText('');setEditor({kind:'proposal',record});}}>Предложить изменение</Button>}{data?.can_edit&&<Button variant="outline" size="sm" onClick={()=>setEditor({kind:record.kind==='field'?'value':record.kind==='document'?'document':'rule',record})} disabled={scope?.type==='network'&&record.kind==='field'&&record.payload_json.location_only!==false||record.kind==='document'&&!owned(record)}>{!owned(record)&&record.kind==='rule'?'Добавить исключение':'Изменить'}</Button>}{(data?.can_configure&&record.kind==='field'||data?.can_edit&&record.kind!=='field')&&owned(record)&&<Button variant="ghost" size="sm" onClick={()=>setEditor({kind:'archive',record})}>В архив</Button>}</div>;
  const active=data||blank;
  const empty=!active.fields.length&&!active.rules.length&&!active.documents.length;
  return <div className="mx-auto min-w-0 max-w-5xl space-y-6 pb-8">
    {!embedded&&<DashboardPageHeader icon={BookOpen} title="Знания о бизнесе" description="Постоянные сведения, правила и документы для работы с вашим бизнесом" actions={<Button variant="outline" disabled={loading} onClick={()=>void reload()}><RefreshCw className="mr-2 h-4 w-4" />Обновить</Button>} />}
    {!scope?<p>Выберите бизнес или сеть в общем переключателе.</p>:<>
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{active.name} · {scope.type==='network'?'Общие правила и структура сети. Вместимость заполняется в точках.':'Характеристики выбранного бизнеса.'}</p>{returnTo&&<Button variant="outline" onClick={()=>navigate(returnTo)}>Вернуться к работе</Button>}</div>
      {error&&<div role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm"><p>{data?'Не удалось обновить сведения. Показаны ранее полученные данные. ':''}{error}</p><Button className="mt-2" variant="outline" onClick={()=>void reload()}>Повторить</Button></div>}
      {notice&&<p role="status" className="text-sm">{notice}</p>}
      {loading&&!data?<p role="status">Загрузка сведений…</p>:!data?null:!active.enabled?<p>Раздел ещё не установлен. Сохранённые данные бизнеса остаются в профиле.</p>:<>
      {sourceEntry&&<p className="rounded-lg border p-4 text-sm">Открыто наблюдение рабочего журнала. Выберите характеристику или правило и предложите изменение; перед сохранением будет сравнение и подтверждение.</p>}
      {empty&&!editor&&<section className="rounded-xl border bg-card p-6"><h2 className="font-semibold">Сведения, которые не нужно вводить заново</h2><p className="mt-2 text-sm text-muted-foreground">Добавьте характеристики помещения, особенности обслуживания и постоянные правила. Например: шесть кресел, размер учебной группы или ограничение по высоте автомобиля. Временные события записывайте в рабочий журнал.</p>{active.can_configure?<Button className="mt-4" onClick={()=>void openTemplates()}>Добавить сведения</Button>:<p className="mt-4 text-sm">Владелец добавляет поля и назначает редакторов.</p>}</section>}
      <Tabs value={tab} onValueChange={value=>{setTab(value);setEditor(null);setHistory(null);setApproval(null);}}>
        <TabsList className="grid h-auto w-full grid-cols-3"><TabsTrigger className="whitespace-normal break-words px-1 py-3 text-xs sm:text-sm" value="fields">Характеристики</TabsTrigger><TabsTrigger className="whitespace-normal break-words px-1 py-3 text-xs sm:text-sm" value="rules">Правила и особенности</TabsTrigger><TabsTrigger className="whitespace-normal break-words px-1 py-3 text-xs sm:text-sm" value="documents">Документы</TabsTrigger></TabsList>
        <TabsContent value="fields" className="space-y-5">
          {!empty&&active.can_configure&&!editor&&<Button onClick={()=>void openTemplates()}>Добавить сведения</Button>}
          {Array.from(new Set(active.fields.map(f=>f.payload_json.group||'Общие сведения'))).map(group=><section key={group}><h2 className="mb-3 font-semibold">{group}</h2><div className="divide-y rounded-xl border bg-card">{active.fields.filter(f=>(f.payload_json.group||'Общие сведения')===group).map(field=><article key={field.id} id={`knowledge-${field.id}`} tabIndex={-1} className="min-w-0 p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><div className="flex flex-col justify-between gap-3 sm:flex-row"><div className="min-w-0"><h3 className="break-words font-medium">{field.payload_json.label}</h3><p className="mt-1 whitespace-pre-wrap break-words text-sm">{scope.type==='network'&&field.payload_json.location_only!==false?'Заполняется в каждой точке':formatKnowledgeValue(field.value_record,field)}{field.value_record?.payload_json.state==='set'&&field.payload_json.unit?` ${field.payload_json.unit}`:''}</p>{field.value_record&&expired(field.value_record)&&<p className="mt-1 text-sm text-destructive">Срок актуальности истёк; значение не используется помощником.</p>}</div>{rowActions(field)}</div>{details(field.value_record||field)}</article>)}</div></section>)}
          {active.can_configure&&<details><summary className="cursor-pointer rounded-sm text-sm focus-visible:ring-2 focus-visible:ring-ring">Настроить структуру полей</summary><div className="mt-3 grid gap-3"><Button variant="outline" onClick={()=>setEditor({kind:'field'})}>Добавить своё поле</Button>{active.fields.filter(owned).map(field=><Button variant="ghost" className="h-auto justify-start whitespace-normal text-left" key={field.id} onClick={()=>setEditor({kind:'field',record:field})}>Настроить «{field.payload_json.label}»</Button>)}</div></details>}
        </TabsContent>
        <TabsContent value="rules" className="space-y-4">
          {active.can_edit&&!editor&&<Button onClick={()=>setEditor({kind:'rule'})}>Добавить правило</Button>}
          {!active.rules.length&&<p className="text-sm text-muted-foreground">Добавьте постоянное правило, например условия приёма или особенности обслуживания. События и временные ограничения относятся к рабочему журналу.</p>}
          {active.rules.map(rule=><article key={rule.id} id={`knowledge-${rule.id}`} tabIndex={-1} className="rounded-xl border bg-card p-4 focus-visible:ring-2 focus-visible:ring-ring"><h3 className="break-words font-medium">{rule.payload_json.label}</h3><p className="mt-2 whitespace-pre-wrap break-words text-sm">{rule.payload_json.text}</p><div className="mt-3">{rowActions(rule)}</div>{details(rule)}</article>)}
        </TabsContent>
        <TabsContent value="documents" className="space-y-4">
          <p className="text-sm text-muted-foreground">PDF, DOCX и TXT до 10 МБ; PDF до 50 страниц, текст до 30 000 символов. Файлы доступны только участникам с разрешением. Использование требует проверки текста.</p>
          {active.can_edit&&!editor&&<Button onClick={()=>{setFile(null);setEditor({kind:'upload'});}}>Загрузить документ</Button>}
          {!active.documents.length&&<p className="text-sm text-muted-foreground">Документы ещё не добавлены. Можно сохранить инструкции, условия обслуживания или сведения о компании.</p>}
          {active.documents.map(doc=><article key={doc.id} id={`knowledge-${doc.id}`} tabIndex={-1} className="rounded-xl border bg-card p-4 focus-visible:ring-2 focus-visible:ring-ring"><h3 className="break-words font-medium">{doc.payload_json.label}</h3><p className="mt-1 text-sm text-muted-foreground">{expired(doc)?'Срок актуальности истёк':doc.payload_json.status==='confirmed'?'Использование подтверждено':doc.payload_json.status==='text_unavailable'?'Нет извлекаемого текста':'Текст требует проверки'}</p><div className="mt-3 flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={()=>void download(doc)}>Скачать файл</Button>{rowActions(doc)}{active.can_edit&&owned(doc)&&<Button variant="ghost" size="sm" onClick={()=>{setFile(null);setEditor({kind:'upload',record:doc});}}>Заменить файл</Button>}</div>{details(doc)}</article>)}
        </TabsContent>
      </Tabs>
      {editor&&!approval&&<section className="rounded-xl border bg-card p-5"><div ref={panel} tabIndex={-1} className="mb-4 rounded-sm focus-visible:ring-2 focus-visible:ring-ring"><h2 className="break-words font-semibold">{editor.kind==='template'?'Выберите предлагаемые поля':editor.kind==='field'?'Настройка поля':editor.kind==='upload'?'Добавить документ':editor.kind==='archive'?'Архивирование':editor.record?.payload_json.label||'Новое правило'}</h2></div>
        {editor.kind==='proposal'&&editor.record&&<form className="grid gap-4" onSubmit={async e=>{e.preventDefault();const version=generation.current;setBusy(true);try{await api('/proposals',{method:'POST',body:JSON.stringify({record_id:editor.record?.id,text:proposalText,request_id:requestKey({operation:'proposal',record_id:editor.record?.id,text:proposalText})})});if(version===generation.current){pendingRequest.current=null;setNotice('Предложение сохранено в рабочем журнале. Постоянные сведения не изменены.');setEditor(null);}}catch(caught){if(version===generation.current)fail(caught);}finally{if(version===generation.current)setBusy(false);}}}><FormField label="Предлагаемое изменение и источник"><Textarea required maxLength={5000} value={proposalText} onChange={e=>setProposalText(e.target.value)} /></FormField><p className="text-sm text-muted-foreground">Предложение появится в рабочем журнале для проверки руководством.</p><div className="flex flex-wrap gap-2"><Button disabled={busy}>Отправить на проверку</Button><Button type="button" variant="outline" onClick={()=>setEditor(null)}>Отмена</Button></div></form>}
        {editor.kind==='field'&&<FieldForm key={editor.record?.id||'new'} record={editor.record} busy={busy} save={c=>void act(c)} cancel={()=>setEditor(null)} />}
        {editor.kind==='value'&&editor.record&&<ValueForm key={editor.record.id} field={editor.record} scopeType={scope.type} canConfigure={active.can_configure} busy={busy} save={c=>void act(c)} cancel={()=>setEditor(null)} />}
        {(editor.kind==='rule'||editor.kind==='document')&&<TextForm key={editor.record?.id||'new'} record={editor.record} kind={editor.kind} localOverride={editor.kind==='rule'&&!!editor.record&&!owned(editor.record)} canConfigure={active.can_configure} busy={busy} save={c=>void act(c)} cancel={()=>setEditor(null)} />}
        {editor.kind==='template'&&<div className="grid gap-4"><FormField label="Набор для типа бизнеса"><select className="w-full rounded-md border bg-background p-2 text-sm" value={template} onChange={e=>{setTemplate(e.target.value);setSelected(templates.find(t=>t.type_key===e.target.value)?.fields.flatMap(f=>f.template_key?[f.template_key]:[])||[]);}}>{templates.map(t=><option key={t.type_key} value={t.type_key}>{t.label}</option>)}</select></FormField><p className="text-sm text-muted-foreground">Набор добавит только выбранные поля. Повторные поля не появятся; тип бизнеса и прежние сведения сохранятся.</p>{templates.find(t=>t.type_key===template)?.fields.map(f=><label key={f.template_key} className="flex items-start gap-2 text-sm"><input type="checkbox" checked={!!f.template_key&&selected.includes(f.template_key)} onChange={e=>{if(f.template_key)setSelected(e.target.checked?[...selected,f.template_key]:selected.filter(k=>k!==f.template_key));}} />{f.label}</label>)}<AudienceField value={audience} onChange={setAudience} /><div className="flex flex-wrap gap-2"><Button disabled={busy||!selected.length} onClick={()=>void act({operation:'template',audience,payload:{type_key:template,fields:selected}})}>Добавить выбранные поля</Button><Button variant="outline" onClick={()=>setEditor({kind:'field'})}>Добавить своё поле</Button><Button variant="ghost" onClick={()=>setEditor(null)}>Отмена</Button></div></div>}
        {editor.kind==='upload'&&<form className="grid gap-4" onSubmit={e=>{e.preventDefault();void upload();}}><FormField label="Документ"><Input type="file" accept=".pdf,.docx,.txt" required onChange={e=>setFile(e.target.files?.[0]||null)} /></FormField>{!editor.record&&<AudienceField value={audience} onChange={setAudience} />}<div className="flex flex-wrap gap-2"><Button disabled={busy||!file}>{busy?'Проверка файла…':'Загрузить и проверить текст'}</Button><Button type="button" variant="outline" onClick={()=>setEditor(null)}>Отмена</Button></div></form>}
        {editor.kind==='archive'&&editor.record&&<div className="grid gap-4"><p className="text-sm">Запись и её история сохранятся. Архивированные сведения перестанут использоваться в работе.</p><div className="flex flex-wrap gap-2"><Button disabled={busy} onClick={()=>void act({operation:'archive',id:editor.record?.id,version:editor.record?.version,archived:true})}>Архивировать запись</Button><Button variant="outline" onClick={()=>setEditor(null)}>Отмена</Button></div></div>}
      </section>}
      {approval?.approval&&<section className="rounded-xl border bg-card p-5"><div ref={panel} tabIndex={-1} className="rounded-sm focus-visible:ring-2 focus-visible:ring-ring"><h2 className="font-semibold">Проверьте изменение из журнала</h2></div><div className="mt-3 grid gap-3 sm:grid-cols-2"><div><p className="text-sm text-muted-foreground">Было</p><p className="whitespace-pre-wrap break-words text-sm">{approval.preview?.before?(approval.preview.before.kind==='value'?formatKnowledgeValue(approval.preview.before,editor?.record):approval.preview.before.payload_json.text||'Не указано'):'Не указано'}</p></div><div><p className="text-sm text-muted-foreground">Станет</p><p className="whitespace-pre-wrap break-words text-sm">{approval.preview?.after?.text||formatPayload(approval.preview?.after,editor?.record?.payload_json)}</p></div></div><p className="my-3 text-sm text-muted-foreground">Источник — рабочий журнал. Нажатие сохранит сведения; внешние действия не выполняются.</p><div className="flex flex-wrap gap-2"><Button disabled={busy} onClick={()=>void confirm()}>Подтвердить изменение</Button><Button variant="outline" onClick={()=>setApproval(null)}>Вернуться к редактированию</Button></div></section>}
      {history&&<section className="rounded-xl border bg-card p-5"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">История: {history.record.payload_json.label}</h2><Button variant="ghost" onClick={()=>setHistory(null)}>Закрыть историю</Button></div><ol className="grid gap-4">{history.items.map(h=><li key={h.id} className="border-b pb-3 text-sm"><p>{date(h.created_at)} · версия {h.after_json.version} · автор {h.actor_id}</p><p className="mt-1 whitespace-pre-wrap break-words">{h.after_json.kind==='value'?formatKnowledgeValue(h.after_json,history.record):h.after_json.payload_json.text||h.after_json.payload_json.label}{h.after_json.archived?' · архивировано':''}</p>{h.after_json.kind==='document'&&<Button variant="outline" size="sm" className="mt-2" onClick={()=>void download(h.after_json,h.after_json.version)}>Скачать эту версию</Button>}</li>)}</ol></section>}
      {active.inventory?.available&&<details className="rounded-xl border p-4"><summary className="cursor-pointer rounded-sm text-sm font-medium focus-visible:ring-2 focus-visible:ring-ring">Сверка с финансовыми ресурсами</summary><div className="mt-3 grid gap-3 text-sm"><p>{active.inventory.message}</p>{active.inventory.classification_notice&&<p>{active.inventory.classification_notice}</p>}{active.inventory.complete&&<p>Активных ресурсов по полному перечню: {active.inventory.active_resource_count}</p>}<ul>{active.inventory.items.map(i=><li className="break-words" key={i.id}>{i.name}</li>)}</ul>{active.inventory.mismatches?.map(m=><p key={m.field_id} className="text-destructive">{m.label}: указано {m.declared}, в полном перечне {m.listed}. Проверьте обе записи.</p>)}<p>Характеристика не создаёт финансовые записи. Наличие места не подтверждает доступность мастера или времени.</p>{active.can_configure&&<Button variant="outline" disabled={busy} onClick={()=>void act({operation:'inventory_complete',version:active.inventory?.version||0,payload:{complete:!active.inventory?.complete}})}>{active.inventory.complete?'Снять подтверждение полноты':'Подтвердить: все активные ресурсы перечислены'}</Button>}<Link className="underline" to="/dashboard/finance">Открыть финансовый учёт</Link></div></details>}
      {active.locations&&<details className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">Сведения точек · {active.locations.total}</summary><div className="mt-3 grid gap-3 text-sm">{active.locations.summaries.map(s=><p key={s.label+s.unit}>{s.label}: {s.value} {s.unit} · заполнено в {s.coverage} из {active.locations?.total} доступных точек</p>)}{active.locations.items.map(l=><Button key={l.id} variant="outline" className="h-auto whitespace-normal" onClick={()=>{onBusinessChange?.(l.id,'business');if(!embedded)navigate(`/dashboard/profile?section=knowledge&business_id=${encodeURIComponent(l.id)}&scope_type=business`);}} disabled={!onBusinessChange}>{l.name}{l.address ? ` · ${l.address}` : ''}</Button>)}</div></details>}
      {!!active.proposals?.length&&<details className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">Предложения команды · {active.proposals.length}</summary><p className="mt-3 text-sm text-muted-foreground">Последние доступные предложения из рабочего журнала. Постоянные сведения меняются после проверки и подтверждения.</p><div className="mt-3 grid gap-3">{active.proposals.map(proposal=><article key={proposal.id} className="border-b pb-3 text-sm"><p>{proposal.original_text}</p><p className="mt-1 text-muted-foreground">{date(proposal.occurred_at)} · {proposal.facts_json.knowledge_proposal.label}</p><Button className="mt-2" variant="outline" disabled={proposal.applied} onClick={()=>{const target=active.fields.find(r=>r.id===proposal.facts_json.knowledge_proposal.record_id)||active.rules.find(r=>r.id===proposal.facts_json.knowledge_proposal.record_id);if(target){setProposalSource(proposal.id);setTab(target.kind==='field'?'fields':'rules');setEditor({kind:target.kind==='field'?'value':'rule',record:target});}}}>{proposal.applied?'Изменение сохранено':'Проверить изменение'}</Button></article>)}</div></details>}
      {!!active.archived?.length&&<details className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">Архив сведений</summary><div className="mt-3 grid gap-3">{active.archived.map(record=><div key={record.id} className="text-sm"><p>{record.payload_json.label}</p>{details(record)}<Button variant="outline" size="sm" disabled={busy||record.kind==='field'&&!active.can_configure} onClick={()=>void act({operation:'archive',id:record.id,version:record.version,archived:false})}>Восстановить</Button></div>)}</div></details>}
      {active.can_configure&&<details className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">Редакторы сведений</summary><p className="mt-3 text-sm text-muted-foreground">Назначенные управляющие меняют значения, правила и документы. Структура, доступ к сведениям, тариф и команда остаются под управлением владельца.</p><div className="mt-3 grid gap-3">{!active.members.length&&<p className="text-sm">Добавьте управляющего в команду, чтобы назначить редактора.</p>}{active.members.map(m=>{const grant=active.editors.find(e=>e.user_id===m.user_id);return <label key={m.user_id} className="flex items-start gap-2 text-sm"><input type="checkbox" checked={!!grant?.enabled} disabled={busy} onChange={e=>void act({operation:'editor',version:grant?.version||0,payload:{user_id:m.user_id,enabled:e.target.checked}})} />{m.name}</label>;})}</div></details>}
      <details className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">Где редактировать другие сведения</summary><div className="mt-3 grid gap-2 text-sm">{active.existing_sources.map(s=><Link key={s.href} className="underline" to={s.href}>{s.label}</Link>)}<p>Рабочий журнал хранит события и наблюдения. «Сегодня» показывает задачи, «Результаты» — выполненную работу и подтверждения.</p></div></details>
      </>}
    </>}
  </div>;
}
