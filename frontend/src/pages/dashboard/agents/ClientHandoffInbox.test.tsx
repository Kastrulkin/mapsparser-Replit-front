import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe,it,expect,vi } from 'vitest';
import { ClientHandoffInbox } from './ClientHandoffInbox';
vi.mock('@/lib/auth_new',()=>({newAuth:{getToken:()=> 'test-token'}}));

describe('staff handoff inbox',()=>{
 it('creates a real internal queue item, accepts, replies and closes without enabling AI',async()=>{
  let exists=false;let state='waiting_for_staff';const paths:string[]=[];
  vi.stubGlobal('fetch',vi.fn(async(input,options)=>{
   const path=String(input);paths.push(path);
   if(path.endsWith('/client-handoff-test')){exists=true;return Response.json({conversation_id:'c'});}
   if(path.endsWith('/client-handoffs/c')){
    const body=JSON.parse(options.body);
    if(body.action==='accept')state='human_active';
    if(body.action==='close')state='closing';
    return Response.json({success:true});
   }
   if(path.includes('/messages'))return Response.json({messages:[]});
   return Response.json({conversations:exists?[{id:'c',client_phone:'test-handoff:c',client_name:'Проверка передачи',current_state:state}]:[]});
  }));
  render(<ClientHandoffInbox businessId="organika"/>);
  fireEvent.click(screen.getByText('Проверка без клиента'));
  fireEvent.click(screen.getByRole('button',{name:'Проверить передачу без клиента'}));
  fireEvent.click(await screen.findByRole('button',{name:'Взять диалог'}));
  await screen.findByLabelText('Ответ в тестовый диалог');
  fireEvent.change(screen.getByLabelText('Ответ в тестовый диалог'),{target:{value:'Администратор подключился'}});
  fireEvent.click(screen.getByRole('button',{name:'Добавить тестовый ответ'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Завершить диалог без включения агента'})).not.toBeDisabled());
  fireEvent.click(screen.getByRole('button',{name:'Завершить диалог без включения агента'}));
  await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('Завершён'));
  expect(paths.some(path=>path.includes('toggle-agent'))).toBe(false);
 });
 it('shows a permission failure instead of claiming handoff success',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json({error:'Нет доступа'},{status:403})));
  render(<ClientHandoffInbox businessId="foreign"/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа');
 });
});

describe('handoff notification link',()=>{
 it('opens exactly the linked conversation and sends only an explicit self test',async()=>{
  const requests:string[]=[];let sent=false;
  vi.stubGlobal('fetch',vi.fn(async(input)=>{
   const path=String(input);requests.push(path);
   if(path.endsWith('/notify-self-test')){sent=true;return Response.json({notification:{status:'sent'}});}
   if(path.includes('/messages'))return Response.json({messages:sent?[{id:'event',sender:'operator',message_type:'handoff_notification',content:JSON.stringify({status:'sent',actor:'private-user'})}]:[]});
   return Response.json({conversations:[{id:'target',client_phone:'test-handoff:target',client_name:'Linked test',current_state:'waiting_for_staff'}]});
  }));
  render(<ClientHandoffInbox businessId="ras" initialConversationId="target"/>);
  await screen.findByRole('button',{name:'Взять диалог'});
  fireEvent.click(screen.getByText('Проверка без клиента'));
  const button=await screen.findByRole('button',{name:'Уведомить меня в Telegram (тест)'});
  expect(requests.some(path=>path.endsWith('/notify-self-test'))).toBe(false);
  fireEvent.click(button);
  fireEvent.click(screen.getByText('История действий'));
  expect(await screen.findByText('Тестовое уведомление отправлено в Telegram. Прочтение не подтверждено.')).toBeVisible();
  expect(requests).toContain('/api/business/ras/client-handoffs/target/notify-self-test');
  expect(screen.queryByText(/private-user/)).not.toBeInTheDocument();
 });
 it('does not load a foreign conversation from a link',async()=>{
  const requests:string[]=[];
  vi.stubGlobal('fetch',vi.fn(async(input)=>{requests.push(String(input));return Response.json({conversations:[]});}));
  render(<ClientHandoffInbox businessId="ras" initialConversationId="foreign"/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Обращение из ссылки недоступно');
  expect(requests.some(path=>path.includes('/messages'))).toBe(false);
 });
});

it('uses the provided mini-app session for conversations and actions',async()=>{
 const headers=()=>({Authorization:'Bearer mini-session'});
 const fetcher=vi.fn(async(_input,options)=>{
  expect(options.headers.Authorization).toBe('Bearer mini-session');
  return Response.json({conversations:[{id:'mini',client_phone:'test-handoff:mini',current_state:'waiting_for_staff'}],messages:[]});
 });
 vi.stubGlobal('fetch',fetcher);
 render(<ClientHandoffInbox businessId="ras" initialConversationId="mini" headers={headers}/>);
 expect(await screen.findByRole('button',{name:'Взять диалог'})).toBeInTheDocument();
});


it('keeps the linked conversation focused and returns to the list without polling reopening it',async()=>{
 const paths:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(input)=>{
  const path=String(input);paths.push(path);
  if(path.includes('/client-dialogue-graph'))return Response.json({graph:{nodes:[],edges:[]},history:[],current_state:'waiting_for_staff'});
  if(path.includes('/messages'))return Response.json({messages:[{id:'m',sender:'client',message_type:'text',content:'Хочу первую стрижку'},{id:'e',sender:'operator',message_type:'handoff_requested',content:'{}'}]});
  return Response.json({conversations:[{id:'focus',client_phone:'test-handoff:focus',client_name:'Мой диалог',current_state:'waiting_for_staff'}]});
 }));
 render(<ClientHandoffInbox businessId="ras" initialConversationId="focus"/>);
 expect(await screen.findByText('Хочу первую стрижку')).toBeVisible();
 fireEvent.click(screen.getByRole('button',{name:'Обновить'}));
 expect(screen.getByText('Хочу первую стрижку')).toBeVisible();
 expect(screen.getByRole('button',{name:'Взять диалог'})).toBeVisible();
 expect(screen.getByRole('button',{name:'Уведомить меня в Telegram (тест)'})).not.toBeVisible();
 expect(paths.some(path=>path.includes('/client-dialogue-graph'))).toBe(false);
 fireEvent.click(screen.getByText('Этапы диалога и граф'));
 await waitFor(()=>expect(paths.some(path=>path.includes('/client-dialogue-graph'))).toBe(true));
 fireEvent.click(screen.getByRole('button',{name:'Все обращения'}));
 expect(await screen.findByRole('heading',{name:'Обращения сотрудникам'})).toHaveFocus();
 fireEvent.click(screen.getByRole('button',{name:'Обновить'}));
 await waitFor(()=>expect(screen.queryByRole('button',{name:'Взять диалог'})).not.toBeInTheDocument());
 expect(screen.getByRole('button',{name:/Мой диалог/})).toBeVisible();
});

it('requires an explicit send for the personal Telegram pilot and keeps text after uncertain delivery',async()=>{
 const writes:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(input,options)=>{
  const path=String(input);
  if(options?.method==='POST') {writes.push(options.body);return Response.json({error:'Доставка не подтверждена. Проверьте Telegram; автоматического повтора нет.'},{status:409});}
  if(path.includes('/messages'))return Response.json({messages:[]});
  return Response.json({conversations:[{id:'pilot',client_phone:'tg-ras-pilot:private',client_name:'Личный тест',current_state:'human_active'}]});
 }));
 render(<ClientHandoffInbox businessId="ras" initialConversationId="pilot"/>);
 const input=await screen.findByRole('textbox',{name:'Ответ клиенту в Telegram'});
 expect(writes).toHaveLength(0);
 fireEvent.change(input,{target:{value:'Ручной ответ'}});
 fireEvent.click(screen.getByRole('button',{name:'Отправить клиенту в Telegram'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Доставка не подтверждена');
 expect(input).toHaveValue('Ручной ответ');
 expect(writes).toHaveLength(1);
});

it('reopens the notified conversation after returning to the list and preserves a pending reply on resume',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(input)=>String(input).includes('/messages')?Response.json({messages:[]}):Response.json({conversations:[{id:'linked',client_phone:'tg-ras-pilot:private',client_name:'Уведомление',current_state:'human_active'}]})));
 const view=render(<ClientHandoffInbox businessId="ras" initialConversationId="linked" reopenRevision={0}/>);
 const input=await screen.findByRole('textbox',{name:'Ответ клиенту в Telegram'});
 fireEvent.change(input,{target:{value:'Ещё не отправленный ответ'}});
 view.rerender(<ClientHandoffInbox businessId="ras" initialConversationId="linked" reopenRevision={1}/>);
 await waitFor(()=>expect(screen.getByRole('textbox')).toHaveValue('Ещё не отправленный ответ'));
 fireEvent.click(screen.getByRole('button',{name:'Все обращения'}));
 expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
 view.rerender(<ClientHandoffInbox businessId="ras" initialConversationId="linked" reopenRevision={2}/>);
 expect(await screen.findByRole('textbox',{name:'Ответ клиенту в Telegram'})).toBeVisible();
});
