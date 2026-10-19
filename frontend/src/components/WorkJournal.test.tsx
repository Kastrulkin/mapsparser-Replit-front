import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { WorkJournal } from './WorkJournal';
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
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
 render(<WorkJournal businessId="b" headers={headers}/>, { wrapper: MemoryRouter });
 await user.type(await screen.findByLabelText('Что вы заметили?'),'Клиент отказался');await user.click(screen.getByRole('button',{name:'Отправить наблюдение'}));
 await screen.findByText('Записал отказ');await user.click(await screen.findByRole('button',{name:'Отменить запись'}));
 await waitFor(()=>expect(cancelled).toBe(true));expect(mock.mock.calls.filter(([,i])=>i?.method==='PATCH')).toHaveLength(1);
});
it('ignores delayed journal data after business changes',async()=>{
 let resolveOld:(value:Response)=>void=()=>{};
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('business_id=a')?new Promise<Response>(resolve=>{resolveOld=resolve;}):reply({enabled:false,items:[]})));
 const view=render(<WorkJournal businessId="a" headers={headers}/>, { wrapper: MemoryRouter });
 view.rerender(<WorkJournal businessId="b" headers={headers}/>);
 await screen.findByText('Новый ввод пока отключён. Сохранённая история доступна.');
 resolveOld(new Response(JSON.stringify({enabled:true,items:[note]})));
 await waitFor(()=>expect(screen.queryByText('Клиент отказался')).not.toBeInTheDocument());
});
it('view-only notes have no edit controls',async()=>{
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('/audio/')?reply({input_enabled:false}):reply({enabled:true,role:'viewer',items:[{...note,can_edit:false}]})));
 render(<WorkJournal businessId="b" headers={headers}/>, { wrapper: MemoryRouter });await screen.findAllByText('Клиент отказался');
 expect(screen.queryByRole('button',{name:'Исправить'})).not.toBeInTheDocument();
});
it('clears private entries when access is revoked',async()=>{
 let revoked=false;const user=userEvent.setup();
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('/audio/')?reply({input_enabled:false}):revoked?Promise.resolve(new Response(JSON.stringify({error:'Доступ отозван'}),{status:403})):reply({enabled:true,items:[note]})));
 render(<WorkJournal businessId="b" headers={headers}/>, { wrapper: MemoryRouter });await screen.findAllByText('Клиент отказался');revoked=true;
 await user.click(screen.getByRole('button',{name:'Обновить'}));await screen.findByRole('alert');
 expect(screen.queryByText('Клиент отказался')).not.toBeInTheDocument();
});
it('reviews an observation with its version and clears the inbox on revoked access',async()=>{
 const user=userEvent.setup();let revoked=false;let accepted=false;
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
  const path=String(input);
  if(path.includes('/audio/'))return reply({input_enabled:false});
  if(path.includes('/decision')){expect(JSON.parse(String(init?.body))).toMatchObject({business_id:'b',version:1,status:'in_progress',decision:'Проверить встречу'});accepted=true;return reply({entry:{...note,version:2}});}
  if(path.includes('/review?'))return revoked?Promise.resolve(new Response(JSON.stringify({error:'Право отозвано'}),{status:403})):reply({items:[note]});
  return reply({enabled:true,role:'manager',can_review:true,items:[],members:[]});
 }));
 render(<WorkJournal businessId="b" headers={headers}/>, { wrapper: MemoryRouter });
 await user.click(await screen.findByRole('button',{name:'На разбор'}));
 await user.click(await screen.findByRole('button',{name:'Разобрать'}));
 await user.type(screen.getByLabelText('Комментарий руководства'),'Проверить встречу');
 await user.click(screen.getByRole('button',{name:'Сохранить решение'}));
 await waitFor(()=>expect(accepted).toBe(true));revoked=true;
 await user.click(screen.getByRole('button',{name:'Показать'}));
 await screen.findByRole('alert');expect(screen.queryByText('Клиент отказался')).not.toBeInTheDocument();
});
it('restores the saved digest time when the journal opens',async()=>{
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>{
  const path=String(input);
  if(path.includes('/audio/'))return reply({input_enabled:false});
  if(path.includes('/digest-settings'))return reply({local_time:'09:30',enabled:true});
  return reply({enabled:true,role:'owner',review_enabled:true,can_review:true,items:[],members:[]});
 }));
 render(<WorkJournal businessId="b" headers={headers}/>, { wrapper: MemoryRouter });
 await waitFor(()=>expect(screen.getByLabelText('Время дневной сводки в часовом поясе бизнеса')).toHaveValue('09:30'));
});
it('ignores old digest settings after changing the business',async()=>{
 let resolveOld:(value:Response)=>void=()=>{};
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>{
  const path=String(input);
  if(path.includes('/audio/'))return reply({input_enabled:false});
  if(path.includes('/digest-settings'))return path.includes('business_id=a')?new Promise<Response>(resolve=>{resolveOld=resolve;}):reply({local_time:'11:00',enabled:true});
  return reply({enabled:true,role:'owner',review_enabled:true,can_review:true,items:[],members:[]});
 }));
 const view=render(<WorkJournal businessId="a" headers={headers}/>, { wrapper: MemoryRouter });
 await screen.findByLabelText('Время дневной сводки в часовом поясе бизнеса');
 view.rerender(<WorkJournal businessId="b" headers={headers}/>);
 await waitFor(()=>expect(screen.getByLabelText('Время дневной сводки в часовом поясе бизнеса')).toHaveValue('11:00'));
 resolveOld(new Response(JSON.stringify({local_time:'09:30'})));
 await waitFor(()=>expect(screen.getByLabelText('Время дневной сводки в часовом поясе бизнеса')).toHaveValue('11:00'));
});

it('explains two work areas and preserves unsaved text when switching tabs with keyboard',async()=>{
 const user=userEvent.setup();const mock=vi.fn((input:RequestInfo|URL, _init?:RequestInit)=>{
  const url=String(input);
  if(url.includes('/audio/'))return reply({input_enabled:false});
  if(url.includes('/day-brief'))return reply({date:'2026-10-19',user_id:'u',can_manage:true,can_complete:true,delivery_enabled:false,draft:null,members:[],assignments:[]});
  return reply({enabled:true,role:'owner',items:[]});
 });vi.stubGlobal('fetch',mock);
 render(<MemoryRouter><WorkJournal initialView="day_brief" businessId="b" headers={headers}/></MemoryRouter>);
 expect(screen.getByRole('heading',{name:'Планёрка и журнал',exact:true})).toBeVisible();
 await user.type(await screen.findByRole('textbox',{name:'Фокус дня',exact:true}),'Проверяем витрину');
 const briefing=screen.getByRole('tab',{name:'Планёрка',exact:true});
 briefing.focus();await user.keyboard('{ArrowRight}');
 await waitFor(()=>expect(screen.getByRole('tab',{name:'Журнал',exact:true})).toHaveAttribute('aria-selected','true'));
 expect(screen.queryByRole('textbox',{name:'Фокус дня',exact:true})).not.toBeInTheDocument();
 await user.type(screen.getByRole('textbox',{name:'Что вы заметили?',exact:true}),'У витрины грязное стекло');
 await user.click(screen.getByText('Примеры наблюдений'));
 expect(screen.getByText('Клиент отказался от ухода: сказал, что дорого.')).toBeVisible();
 await user.click(briefing);
 expect(screen.getByRole('textbox',{name:'Фокус дня',exact:true})).toHaveValue('Проверяем витрину');
 await user.click(screen.getByRole('tab',{name:'Журнал',exact:true}));
 expect(screen.getByRole('textbox',{name:'Что вы заметили?',exact:true})).toHaveValue('У витрины грязное стекло');
 expect(mock.mock.calls.every(([,init])=>!init?.method || init.method==='GET')).toBe(true);
});
