import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { Audience, FieldType, KnowledgeChange, KnowledgePayload, KnowledgeRecord } from './types';

const fieldTypes: {value: FieldType; label: string}[] = [
  {value:'text',label:'Текст'},{value:'long_text',label:'Длинный текст'},{value:'integer',label:'Целое число'},
  {value:'decimal',label:'Дробное число'},{value:'boolean',label:'Да / нет'},{value:'date',label:'Дата'},
  {value:'url',label:'Ссылка'},{value:'select',label:'Один вариант'},{value:'multi_select',label:'Несколько вариантов'},
];
const selectStyle = 'flex w-full min-w-0 rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
export function FormField({label,children,grouped=false}: {label:string;children:React.ReactNode;grouped?:boolean}) {
  if(grouped)return <fieldset className="grid min-w-0 gap-2 text-sm font-medium"><legend className="mb-2 leading-5">{label}</legend>{children}</fieldset>;
  return <Label className="grid min-w-0 gap-2 leading-5">{label}{children}</Label>;
}
export function AudienceField({value,onChange,disabled=false}: {value:Audience;onChange:(value:Audience)=>void;disabled?:boolean}) {
  return <FormField label="Кому доступны сведения"><select className={selectStyle} value={value} disabled={disabled} onChange={e=>onChange(e.target.value==='management'?'management':'team')}><option value="team">Участникам бизнеса</option><option value="management">Только руководству</option></select></FormField>;
}
export function FieldForm({record,busy,save,cancel}: {record?:KnowledgeRecord;busy:boolean;save:(change:KnowledgeChange)=>void;cancel:()=>void}) {
  const initial=record?.payload_json;
  const [label,setLabel]=useState(initial?.label||'');
  const [kind,setKind]=useState<FieldType>(initial?.type||'text');
  const [group,setGroup]=useState(initial?.group||'Общие сведения');
  const [unit,setUnit]=useState(initial?.unit||'');
  const [hint,setHint]=useState(initial?.hint||'');
  const [minimum,setMinimum]=useState(initial?.min?.toString()||'');
  const [maximum,setMaximum]=useState(initial?.max?.toString()||'');
  const [locationOnly,setLocationOnly]=useState(initial?.location_only!==false);
  const [audience,setAudience]=useState<Audience>(record?.audience||'team');
  const [options,setOptions]=useState(initial?.options||[]);
  return <form className="grid gap-4" onSubmit={e=>{e.preventDefault();save({operation:'field',id:record?.id,version:record?.version,audience,payload:{label,type:kind,group,unit,hint,location_only:locationOnly,options,min:minimum===''?undefined:Number(minimum),max:maximum===''?undefined:Number(maximum)}});}}>
    <FormField label="Название"><Input value={label} maxLength={200} required onChange={e=>setLabel(e.target.value)} autoFocus /></FormField>
    <FormField label="Тип значения"><select className={selectStyle} value={kind} onChange={e=>{const found=fieldTypes.find(t=>t.value===e.target.value);if(found)setKind(found.value);}}>{fieldTypes.map(t=><option key={t.value} value={t.value}>{t.label}</option>)}</select></FormField>
    {record && kind!==initial?.type && <p className="text-sm text-muted-foreground">При сохранении будут проверены все заполненные значения. Несовместимое преобразование не изменит поле.</p>}
    <div className="grid gap-4 sm:grid-cols-2"><FormField label="Группа"><Input value={group} maxLength={200} onChange={e=>setGroup(e.target.value)} /></FormField><FormField label="Единица измерения"><Input value={unit} maxLength={50} placeholder="Например, шт. или м²" onChange={e=>setUnit(e.target.value)} /></FormField></div>
    <FormField label="Подсказка"><Textarea value={hint} maxLength={1000} onChange={e=>setHint(e.target.value)} /></FormField>
    {(kind==='integer'||kind==='decimal') && <div className="grid gap-4 sm:grid-cols-2"><FormField label="Минимум, если нужен"><Input type="number" step="any" value={minimum} onChange={e=>setMinimum(e.target.value)} /></FormField><FormField label="Максимум, если нужен"><Input type="number" step="any" value={maximum} onChange={e=>setMaximum(e.target.value)} /></FormField></div>}
    {(kind==='select'||kind==='multi_select') && <fieldset className="grid gap-3"><legend className="mb-2 text-sm font-medium">Варианты выбора</legend>{options.map(option=><div key={option.id} className="flex min-w-0 items-center gap-2"><Input aria-label="Название варианта" value={option.label} required maxLength={200} onChange={e=>setOptions(options.map(o=>o.id===option.id?{...o,label:e.target.value}:o))} /><label className="flex gap-2 text-sm"><input type="checkbox" checked={option.archived} onChange={e=>setOptions(options.map(o=>o.id===option.id?{...o,archived:e.target.checked}:o))} />Архив</label></div>)}<Button type="button" variant="outline" onClick={()=>setOptions([...options,{id:crypto.randomUUID(),label:'',archived:false}])}>Добавить вариант</Button></fieldset>}
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={locationOnly} onChange={e=>setLocationOnly(e.target.checked)} />Значение относится к отдельной точке. Вместимость не наследуется от сети.</label>
    <AudienceField value={audience} onChange={setAudience} />
    <div className="flex flex-wrap gap-2"><Button disabled={busy}>{busy?'Сохранение…':'Сохранить поле'}</Button><Button type="button" variant="outline" onClick={cancel}>Отмена</Button></div>
  </form>;
}
export function ValueForm({field,scopeType,canConfigure,busy,save,cancel}: {field:KnowledgeRecord;scopeType:string;canConfigure:boolean;busy:boolean;save:(change:KnowledgeChange)=>void;cancel:()=>void}) {
  const record=field.value_record?.scope_type===scopeType?field.value_record:undefined;
  const current=field.value_record?.payload_json;
  const definition=field.payload_json;
  const [state,setState]=useState(current?.state||'unknown');
  const [value,setValue]=useState<string|number|boolean|string[]|null>(current?.value??'');
  const [source,setSource]=useState(current?.source||'Указано пользователем');
  const [until,setUntil]=useState(current?.valid_until||'');
  const [audience,setAudience]=useState<Audience>(field.value_record?.audience||field.audience);
  let control;
  if(definition.type==='boolean')control=<select className={selectStyle} value={value===true?'true':value===false?'false':''} required onChange={e=>setValue(e.target.value==='true')}><option value="">Выберите да или нет</option><option value="true">Да</option><option value="false">Нет</option></select>;
  else if(definition.type==='select')control=<select className={selectStyle} value={typeof value==='string'?value:''} onChange={e=>setValue(e.target.value)} required><option value="">Выберите вариант</option>{definition.options?.filter(o=>!o.archived||value===o.id).map(o=><option key={o.id} value={o.id}>{o.label}{o.archived?' (архив)':''}</option>)}</select>;
  else if(definition.type==='multi_select')control=<div className="grid gap-2">{definition.options?.filter(o=>!o.archived||Array.isArray(value)&&value.includes(o.id)).map(o=><label key={o.id} className="flex gap-2"><input type="checkbox" checked={Array.isArray(value)&&value.includes(o.id)} onChange={e=>{const old=Array.isArray(value)?value:[];setValue(e.target.checked?[...old,o.id]:old.filter(v=>v!==o.id));}} />{o.label}{o.archived?' (архив)':''}</label>)}</div>;
  else if(definition.type==='long_text')control=<Textarea value={typeof value==='string'?value:''} maxLength={10000} onChange={e=>setValue(e.target.value)} required />;
  else control=<Input type={definition.type==='integer'||definition.type==='decimal'?'number':definition.type==='date'?'date':definition.type==='url'?'url':'text'} step={definition.type==='decimal'?'any':'1'} min={definition.min} max={definition.max} value={typeof value==='string'||typeof value==='number'?value:''} onChange={e=>setValue(e.target.value)} required maxLength={2000} />;
  return <form className="grid gap-4" onSubmit={e=>{e.preventDefault();let typed=value;if(state==='set'&&(definition.type==='integer'||definition.type==='decimal'))typed=Number(value);if(state==='set'&&definition.type==='boolean')typed=value===true;save({operation:'value',id:record?.id,version:record?.version,audience,payload:{field_id:field.id,state,value:state==='set'?typed:null,source,valid_until:until||undefined}});}}>
    <p className="text-sm text-muted-foreground">{definition.hint||'Постоянная характеристика. Временные ограничения добавляйте в рабочий журнал.'}</p>
    <FormField label="Состояние значения"><select className={selectStyle} value={state} onChange={e=>{const next=e.target.value;if(next==='set'||next==='unknown'||next==='not_applicable')setState(next);}}><option value="unknown">Не указано</option><option value="set">Указать значение</option><option value="not_applicable">Не применяется</option></select></FormField>
    {state==='set' && <FormField grouped={definition.type==='multi_select'} label={definition.label+(definition.unit?' · '+definition.unit:'')}>{control}</FormField>}
    <FormField label="Источник"><Input value={source} maxLength={1000} onChange={e=>setSource(e.target.value)} /></FormField>
    <FormField label="Актуально до, если нужно"><Input type="date" value={until} onChange={e=>setUntil(e.target.value)} /></FormField>
    <AudienceField value={audience} onChange={setAudience} disabled={!canConfigure||field.audience==='management'} />
    <div className="flex flex-wrap gap-2"><Button disabled={busy}>{busy?'Сохранение…':'Сохранить сведения'}</Button><Button type="button" variant="outline" onClick={cancel}>Отмена</Button></div>
  </form>;
}
export function TextForm({record,kind,localOverride,canConfigure,busy,save,cancel}: {record?:KnowledgeRecord;kind:'rule'|'document';localOverride?:boolean;canConfigure:boolean;busy:boolean;save:(change:KnowledgeChange)=>void;cancel:()=>void}) {
  const [label,setLabel]=useState(record?.payload_json.label||'');
  const [text,setText]=useState(record?.payload_json.text||'');
  const [until,setUntil]=useState(record?.payload_json.valid_until||'');
  const [audience,setAudience]=useState<Audience>(record?.audience||'team');
  const [confirmed,setConfirmed]=useState(false);
  const payload:KnowledgePayload={label,text,valid_until:until||undefined,source:record?.payload_json.source||'Указано пользователем',origin_id:localOverride?record?.id:undefined};
  return <form className="grid gap-4" onSubmit={e=>{e.preventDefault();save({operation:kind,id:localOverride?undefined:record?.id,version:localOverride?undefined:record?.version,audience,payload:{...payload,confirmed:kind==='document'?confirmed:undefined}});}}>
    {localOverride && <p className="text-sm text-muted-foreground">Исключение действует для выбранной точки. Общее правило сети сохранится.</p>}
    <FormField label="Название"><Input required value={label} maxLength={200} onChange={e=>setLabel(e.target.value)} autoFocus /></FormField>
    <FormField label={kind==='document'?'Проверьте извлечённый текст':'Правило или особенность'}><Textarea className="min-h-40" required value={text} maxLength={kind==='document'?30000:10000} onChange={e=>setText(e.target.value)} /></FormField>
    {kind==='document' && <p className="text-sm text-muted-foreground">{record?.payload_json.status==='text_unavailable'?'В файле нет извлекаемого текста. Добавьте текст вручную, чтобы использовать его в работе.':'Проверьте полноту и точность текста перед использованием.'} До подтверждения помощник его не использует.</p>}
    <FormField label="Актуально до, если нужно"><Input type="date" value={until} onChange={e=>setUntil(e.target.value)} /></FormField>
    <AudienceField value={audience} onChange={setAudience} disabled={!!record&&!canConfigure} />
    {kind==='document' && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} />Текст проверен, разрешаю использовать его в подготовке материалов</label>}
    {kind==='rule' && <p className="text-sm text-muted-foreground">Правило станет справочным контекстом. Уже подтверждённые сценарии требуют отдельной повторной проверки.</p>}
    <div className="flex flex-wrap gap-2"><Button disabled={busy}>{busy?'Сохранение…':kind==='document'&&confirmed?'Подтвердить использование':'Сохранить'}</Button><Button type="button" variant="outline" onClick={cancel}>Отмена</Button></div>
  </form>;
}
