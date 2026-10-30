import type { ReactNode } from 'react';
import { render,screen,waitFor } from '@testing-library/react';
import { describe,it,expect,vi } from 'vitest';
import { ClientDialogueGraph } from './ClientDialogueGraph';
vi.mock('@/lib/auth_new',()=>({newAuth:{getToken:()=> 'token'}}));
vi.mock('./workflow-graph',()=>({AgentWorkflowGraph:({graphNodes}:{graphNodes:Array<{id:string;data:{label:ReactNode}}>})=><div>{graphNodes.map(node=><div key={node.id}>{node.data.label}</div>)}</div>}));
const data=(current:string)=>({graph:{nodes:[{id:'greeting',label:'Начало',x:0,y:0,reachable:true},{id:'waiting_for_staff',label:'Очередь сотруднику',x:1,y:1,reachable:true}],edges:[{id:'e',source:'greeting',target:'waiting_for_staff',label:'Нужен человек'}],note:'Правила runtime'},current_state:current,history:[{id:'h',from:'greeting',to:'waiting_for_staff',at:'2026-10-30T12:00:00Z'}],history_note:'Только записанные переходы'});
describe('client state graph',()=>{
 it('shows actual current state and recorded history',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json(data('waiting_for_staff'))));
  render(<ClientDialogueGraph businessId="org" conversationId="c"/>);
  expect(await screen.findByText('Текущий этап: Очередь сотруднику')).toBeInTheDocument();
  expect(screen.getByText(/Начало → Очередь сотруднику/)).toBeInTheDocument();
  expect(screen.getByText('Текущий этап')).toBeInTheDocument();
 });
 it('rejects malformed snapshots without a render crash',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json({})));
  render(<ClientDialogueGraph businessId="org"/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Схема временно недоступна');
 });
 it('clears the selected conversation on a scope change',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(input)=>Response.json({...data(String(input).includes('/other/')?'greeting':'waiting_for_staff'),history:[]})));
  const view=render(<ClientDialogueGraph businessId="org" conversationId="c"/>);
  await screen.findByText('Текущий этап: Очередь сотруднику');
  view.rerender(<ClientDialogueGraph businessId="other" conversationId="d"/>);
  await waitFor(()=>expect(screen.queryByText('Текущий этап: Очередь сотруднику')).not.toBeInTheDocument());
  expect(await screen.findByText('Текущий этап: Начало')).toBeInTheDocument();
 });
});
