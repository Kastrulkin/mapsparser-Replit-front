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
