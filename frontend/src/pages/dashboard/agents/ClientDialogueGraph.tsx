import { Button } from '@/components/ui/button';
import { useEffect, useRef, useState } from 'react';
import { AgentWorkflowGraph } from './workflow-graph';
import { newAuth } from '@/lib/auth_new';

type StateNode={id:string;label:string;x:number;y:number;reachable:boolean};
type Transition={id:string;source:string;target:string;label:string};
type Visit={id:string;from:string;to:string;at:string};
type Snapshot={graph:{nodes:StateNode[];edges:Transition[];note:string;rules?:Array<{id:string;label:string;target:string}>};current_state:string|null;is_agent_paused?:boolean;history:Visit[];history_note:string};
export function ClientDialogueGraph({businessId,conversationId}:{businessId:string;conversationId?:string|null}) {
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null);const [error,setError]=useState('');const [focus,setFocus]=useState('');const [overview,setOverview]=useState(false);
 const revision=useRef(0);
 useEffect(()=>{
  const version=++revision.current;let active=true;setSnapshot(null);setError('');setFocus('');setOverview(false);
  const load=async()=>{try{
   const token=newAuth.getToken();const response=await fetch('/api/business/'+businessId+'/client-dialogue-graph'+(conversationId?'?conversation_id='+encodeURIComponent(conversationId):''),{headers:token?{Authorization:'Bearer '+token}:{}});
   const result=await response.json();if(!response.ok)throw new Error(result.error || 'Не удалось загрузить схему');
   if(!Array.isArray(result.graph?.nodes)||!Array.isArray(result.graph?.edges))throw new Error('Схема временно недоступна. Обновите страницу.');
   if(active&&revision.current===version){setSnapshot(result);setError('');}
  }catch(reason){if(active&&revision.current===version)setError(reason instanceof Error?reason.message:'Не удалось загрузить схему');}};
  void load();const timer=setInterval(()=>void load(),15000);return()=>{active=false;clearInterval(timer);};
 },[businessId,conversationId]);
 if(error)return <p role="alert" className="text-destructive">{error}</p>;
 if(!snapshot)return <p role="status">Загружаем состояния диалога…</p>;
 const name=(id:string)=>snapshot.graph.nodes.find(node=>node.id===id)?.label || id;
 const selected=focus || snapshot.current_state || 'greeting';
 const visited=new Set(snapshot.history.flatMap(item=>[item.from,item.to]));
 const edges=snapshot.graph.edges.filter(edge=>(edge.source===selected && !(snapshot.is_agent_paused && selected===snapshot.current_state && !['waiting_for_staff','human_active'].includes(selected))) || ['booking_request','waiting_for_staff','human_active'].includes(edge.source) || snapshot.history.some(item=>item.from===edge.source&&item.to===edge.target));
 return <section aria-label="Состояния диалога" className="space-y-3 rounded-lg border p-4">
  <h3 className="font-semibold">Состояния и переходы</h3>
  {snapshot.is_agent_paused&&<p className="text-sm">Автоответы на паузе. Переходы агента не выполняются; действия сотрудника доступны по состоянию обращения.</p>}
  <p>{snapshot.current_state?'Текущий этап: '+name(snapshot.current_state):'Общая схема. Выберите диалог, чтобы увидеть текущий этап и историю.'}</p>
  <label className="block text-sm">Показать переходы из этапа<select className="ml-2 rounded-md border bg-background p-2" value={selected} onChange={event=>{setFocus(event.target.value);setOverview(false);}}>{snapshot.graph.nodes.map(node=><option key={node.id} value={node.id}>{node.label}</option>)}</select></label>
  <div className="flex gap-2"><Button variant={overview?'outline':'default'} onClick={()=>setOverview(false)}>Выбранный этап</Button><Button variant={overview?'default':'outline'} onClick={()=>setOverview(true)}>Вся схема</Button></div>
  <AgentWorkflowGraph key={selected+':'+overview} focusNodeIds={overview?undefined:[selected]} steps={[]} graphNodes={snapshot.graph.nodes.map(node=>({id:node.id,position:{x:node.x,y:node.y},data:{label:<div className={'rounded-lg border p-3 '+(node.id===snapshot.current_state?'bg-primary text-primary-foreground':visited.has(node.id)?'bg-accent text-accent-foreground':'bg-background text-foreground')}><strong>{node.label}</strong><div className="text-xs">{node.id===snapshot.current_state?'Текущий этап':visited.has(node.id)?'Пройден':!node.reachable?'Зарезервирован':''}</div></div>},style:{width:220,border:0,padding:0,background:'transparent'},draggable:false}))} graphEdges={edges.map(edge=>({id:edge.id,source:edge.source,target:edge.target,label:edge.label,animated:edge.source===snapshot.current_state,style:{strokeWidth:snapshot.history.some(item=>item.from===edge.source&&item.to===edge.target)?3:1}}))}/>
  <p className="text-sm text-muted-foreground">Показаны переходы выбранного этапа, записанный путь и ветка сотрудника. {snapshot.graph.note}</p>
  <details><summary className="cursor-pointer text-sm">Условия переходов и приоритет</summary><ol className="list-decimal space-y-1 pl-5 text-sm">{snapshot.graph.rules?.map(rule=><li key={rule.id}>{rule.label} → {name(rule.target)}</li>)}</ol></details>
  <h4 className="font-medium">История этапов</h4>
  {snapshot.history.length?<ol className="space-y-1 text-sm">{snapshot.history.map(item=><li key={item.id}>{new Date(item.at).toLocaleString('ru-RU')} · {name(item.from)} → {name(item.to)}</li>)}</ol>:<p className="text-sm">Записанных переходов пока нет.</p>}
  <p className="text-xs text-muted-foreground">{snapshot.history_note}</p>
 </section>;
}
