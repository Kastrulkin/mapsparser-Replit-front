import type { KnowledgePayload, KnowledgeRecord } from './types';

export function formatKnowledgeValue(record?:KnowledgeRecord|null,definition?:KnowledgeRecord):string {
  return formatPayload(record?.payload_json,definition?.payload_json);
}
export function formatPayload(p?:KnowledgePayload,definition?:KnowledgePayload):string {
  if(!p||p.state==='unknown')return 'Не указано';
  if(p.state==='not_applicable')return 'Не применяется';
  if(typeof p.value==='boolean')return p.value?'Да':'Нет';
  if(p.value===null||p.value===undefined)return 'Не указано';
  const options=definition?.options;
  const label=(id:string)=>options?.find(o=>o.id===id)?.label||id;
  return Array.isArray(p.value)?p.value.map(label).join(', '):typeof p.value==='string'?label(p.value):String(p.value);
}
