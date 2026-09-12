import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { WorkJournal } from './WorkJournal';
const headers=()=>({Authorization:'Bearer test'});
const reply=(value:unknown)=>Promise.resolve(new Response(JSON.stringify(value),{status:200}));
const note={id:'note',version:1,user_id:'u',can_edit:true,channel:'web',occurred_at:'2026-09-12T10:00:00Z',original_text:'Клиент отказался',is_voided:false,facts_json:{quote:'Клиент отказался'}};
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('saves text through Operator and cancels with a version and unique request',async()=>{
 const user=userEvent.setup();let saved=false;let cancelled=false;
 const mock=vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
  const path=String(input);
  if(path.includes('/audio/config'))return reply({input_enabled:false});
  if(path.endsWith('/operator/chat')){saved=true;expect(JSON.parse(String(init?.body))).toMatchObject({message:'Клиент отказался',business_id:'b'});return reply({conversation_id:'c',chat_response:'Записал отказ'});}
  if(init?.method==='PATCH'){expect(JSON.parse(String(init.body))).toMatchObject({version:1,void:true,business_id:'b'});cancelled=true;return reply({status:'completed'});}
  return reply({enabled:true,role:'member',items:saved?[{...note,is_voided:cancelled}]:[]});
 });vi.stubGlobal('fetch',mock);
 render(<WorkJournal businessId="b" headers={headers}/>);
 await user.type(await screen.findByLabelText('Сообщение Оператору'),'Клиент отказался');await user.click(screen.getByRole('button',{name:'Отправить',exact:true}));
 await screen.findByText('Записал отказ');await user.click(await screen.findByRole('button',{name:'Отменить запись',exact:true}));
 await waitFor(()=>expect(cancelled).toBe(true));expect(mock.mock.calls.filter(([,i])=>i?.method==='PATCH')).toHaveLength(1);
});
it('ignores delayed journal data after business changes',async()=>{
 let resolveOld:(value:Response)=>void=()=>{};
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('business_id=a')?new Promise<Response>(resolve=>{resolveOld=resolve;}):reply({enabled:false,items:[]})));
 const view=render(<WorkJournal businessId="a" headers={headers}/>);
 view.rerender(<WorkJournal businessId="b" headers={headers}/>);
 await screen.findByText('Новый ввод пока отключён. Сохранённая история доступна.');
 resolveOld(new Response(JSON.stringify({enabled:true,items:[note]})));
 await waitFor(()=>expect(screen.queryByText('Клиент отказался')).not.toBeInTheDocument());
});
it('view-only notes have no edit controls',async()=>{
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('/audio/')?reply({input_enabled:false}):reply({enabled:true,role:'viewer',items:[{...note,can_edit:false}]})));
 render(<WorkJournal businessId="b" headers={headers}/>);await screen.findAllByText('Клиент отказался');
 expect(screen.queryByRole('button',{name:'Исправить',exact:true})).not.toBeInTheDocument();
});
it('clears private entries when access is revoked',async()=>{
 let revoked=false;const user=userEvent.setup();
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('/audio/')?reply({input_enabled:false}):revoked?Promise.resolve(new Response(JSON.stringify({error:'Доступ отозван'}),{status:403})):reply({enabled:true,items:[note]})));
 render(<WorkJournal businessId="b" headers={headers}/>);await screen.findAllByText('Клиент отказался');revoked=true;
 await user.click(screen.getByRole('button',{name:'Обновить'}));await screen.findByRole('alert');
 expect(screen.queryByText('Клиент отказался')).not.toBeInTheDocument();
});
