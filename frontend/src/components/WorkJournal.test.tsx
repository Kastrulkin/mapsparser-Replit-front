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
 await waitFor(()=>expect(cancelled).toBe(true));await screen.findByText('Запись отменена. Она останется в истории.');expect(screen.queryByText('Записал отказ')).not.toBeInTheDocument();expect(mock.mock.calls.filter(([,i])=>i?.method==='PATCH')).toHaveLength(1);
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

it('keeps knowledge proposals inside MAX instead of switching to Telegram',async()=>{
 window.history.replaceState({},'', '/max/control');
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('/audio/')?reply({input_enabled:false}):reply({enabled:true,role:'member',items:[note]})));
 render(<WorkJournal businessId="b" headers={headers} embedded/>, { wrapper: MemoryRouter });
 const link=await screen.findByRole('link',{name:'Предложить изменение сведений'});
 expect(link.getAttribute('href')).toContain('/max/control?screen=business_knowledge');
 expect(link.getAttribute('href')).toContain('scope_id=b');
 expect(link.getAttribute('href')).toContain('source_entry=note');
 window.history.replaceState({},'', '/');
});
it('creates an owner-reviewed task from an observation without a chat planner',async()=>{
 const user=userEvent.setup(); let created=false;
 const accepted={...note,version:2,review_status:'in_progress'};
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
  const path=String(input);
  if(path.includes('/audio/'))return reply({input_enabled:false});
  if(path.includes('/review?'))return reply({items:[accepted]});
  if(path.endsWith('/note/actions') && init?.method==='POST'){
   expect(JSON.parse(String(init.body))).toMatchObject({business_id:'b',version:2,kind:'task',title:'Найти мойщика окон',text:'Запросить стоимость, ничего не обещать'});
   created=true;return reply({action:{id:'action',version:1,status:'ready',title:'Найти мойщика окон'}});
  }
  if(path.endsWith('/operator/chat'))throw new Error('Task form must not require a planner');
  return reply({enabled:true,role:'manager',can_review:true,items:[accepted],members:[]});
 }));
 render(<WorkJournal businessId="b" headers={headers}/>, {wrapper:MemoryRouter});
 await user.click(await screen.findByRole('button',{name:'На разбор'}));
 await user.click(await screen.findByRole('button',{name:'Назначить задачу'}));
 await user.type(screen.getByLabelText('Задача'),'Найти мойщика окон');
 await user.type(screen.getByLabelText('Подробности'),'Запросить стоимость, ничего не обещать');
 await user.click(screen.getByRole('button',{name:'Создать задачу'}));
 await waitFor(()=>expect(created).toBe(true));
 await screen.findByText(/Найти мойщика окон ·/);
 expect(screen.queryByRole('region',{name:'Задача по наблюдению'})).not.toBeInTheDocument();
});
it('edits the employee note directly with the observed version and current platform',async()=>{
 const user=userEvent.setup();let edited=false;
 window.history.replaceState({},'', '/max/control');
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
  const path=String(input);
  if(path.includes('/audio/'))return reply({input_enabled:false});
  if(path.endsWith('/operator/chat'))throw new Error('A literal correction needs no planner');
  if(init?.method==='PATCH'){
   expect(JSON.parse(String(init.body))).toMatchObject({business_id:'b',version:1,void:false,text:'У входа грязные окна',channel:'max_mini_app'});
   edited=true;return reply({status:'completed'});
  }
  return reply({enabled:true,role:'member',items:[{...note,facts_json:{quote:edited?'У входа грязные окна':'Клиент отказался'}}]});
 }));
 render(<WorkJournal businessId="b" headers={headers} embedded/>, {wrapper:MemoryRouter});
 await user.click(await screen.findByRole('button',{name:'Исправить'}));
 await user.clear(screen.getByLabelText('Исправленный текст'));await user.type(screen.getByLabelText('Исправленный текст'),'У входа грязные окна');
 await user.click(screen.getByRole('button',{name:'Сохранить исправление'}));
 await waitFor(()=>expect(edited).toBe(true));await screen.findByText('У входа грязные окна');
 window.history.replaceState({},'', '/');
});
it('reuses the request identity after a lost response instead of creating a duplicate observation',async()=>{
 const user=userEvent.setup();let attempts=0;const identifiers:string[]=[];
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
  const path=String(input);
  if(path.includes('/audio/'))return reply({input_enabled:false});
  if(path.endsWith('/operator/chat')){
   const body=JSON.parse(String(init?.body));identifiers.push(body.request_id);attempts++;
   if(attempts===1)return Promise.reject(new TypeError('Failed to fetch'));
   return reply({conversation_id:'c',status:'completed',chat_response:'Наблюдение сохранено'});
  }
  return reply({enabled:true,role:'member',items:attempts>1?[note]:[]});
 }));
 render(<WorkJournal businessId="b" headers={headers}/>,{wrapper:MemoryRouter});
 await user.type(await screen.findByLabelText('Что вы заметили?'),'Клиент отказался');
 await user.click(screen.getByRole('button',{name:'Отправить наблюдение'}));
 await screen.findByRole('alert');expect(screen.getByLabelText('Что вы заметили?')).toHaveValue('Клиент отказался');
 await user.click(screen.getByRole('button',{name:'Отправить наблюдение'}));
 await screen.findByText('Наблюдение сохранено');
 expect(identifiers).toHaveLength(2);expect(identifiers[0]).toBe(identifiers[1]);
 expect(screen.getAllByRole('button',{name:'Исправить'})).toHaveLength(1);
});

it('shows the author beside a visible journal entry',async()=>{
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('/audio/')?reply({input_enabled:false}):reply({enabled:true,role:'owner',items:[{...note,author_name:'Тестовый сотрудник'}]})));
 render(<WorkJournal businessId="b" headers={headers}/>, { wrapper: MemoryRouter });
 expect(await screen.findByText(/Автор: Тестовый сотрудник/)).toBeVisible();
});

it('explains an empty filtered journal and restores entries when filters are reset',async()=>{
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('/audio/')?reply({input_enabled:false}):reply({enabled:true,items:String(input).includes('query=')?[]:[note]})));
 const user=userEvent.setup();render(<WorkJournal businessId="b" headers={headers}/>, { wrapper: MemoryRouter });
 await screen.findAllByText('Клиент отказался');
 await user.type(screen.getByRole('textbox',{name:'Поиск',exact:true}),'нет-совпадений');
 expect(await screen.findByText('По этим условиям записей нет. Измените поиск или дату.')).toBeVisible();
 await user.click(screen.getByRole('button',{name:'Сбросить фильтры'}));
 expect(await screen.findAllByText('Клиент отказался')).not.toHaveLength(0);
 expect(screen.getByRole('textbox',{name:'Поиск',exact:true})).toHaveValue('');
});
