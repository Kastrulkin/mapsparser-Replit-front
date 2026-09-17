import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { ContentRules } from './ContentRules';
const headers=()=>({Authorization:'Bearer test'});
const reply=(data:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(data),{status}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('allows manager to save a rule without chat or publication',async()=>{
  const fetcher=vi.fn((url:string,options?:RequestInit)=>reply(options?.method?{rule:{id:'r'}}:{rules:[],can_manage:true}));
  vi.stubGlobal('fetch',fetcher);const user=userEvent.setup();render(<ContentRules businessId="b" headers={headers}/>);
  await user.type(await screen.findByLabelText('Добавьте ограничение'),'Не обещаем любые мультфильмы');
  await user.click(screen.getByRole('button',{name:'Сохранить правило'}));
  await waitFor(()=>expect(fetcher.mock.calls.some(([,options])=>options?.method==='POST')).toBe(true));
  const call=fetcher.mock.calls.find(([,options])=>options?.method==='POST');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({business_id:'b',text:'Не обещаем любые мультфильмы',status:'active'});
});
it('employee sees proposal instructions without write controls',async()=>{
  vi.stubGlobal('fetch',vi.fn(()=>reply({rules:[],can_manage:false})));
  render(<ContentRules businessId="b" headers={headers}/>);
  expect(await screen.findByText(/Предложите изменение через Оператора/)).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Сохранить правило'})).not.toBeInTheDocument();
});
it('stale business responses cannot expose previous rules',async()=>{
  let finish:(response:Response)=>void=()=>undefined;
  vi.stubGlobal('fetch',vi.fn((url:string)=>url.includes('business_id=a')?new Promise<Response>(resolve=>{finish=resolve;}):reply({rules:[],can_manage:false})));
  const view=render(<ContentRules businessId="a" headers={headers}/>);view.rerender(<ContentRules businessId="b" headers={headers}/>);
  await screen.findByText(/Предложите изменение/);
  finish(new Response(JSON.stringify({rules:[{id:'r',text:'Чужие правила',status:'active',version:1}],can_manage:true})));
  await waitFor(()=>expect(screen.queryByText('Чужие правила')).not.toBeInTheDocument());
});
it('conflict is visible and does not pretend the edit succeeded',async()=>{
  vi.stubGlobal('fetch',vi.fn((url:string,options?:RequestInit)=>options?.method?reply({error:'Правило изменилось'},409):reply({rules:[],can_manage:true})));
  render(<ContentRules businessId="b" headers={headers}/>);const user=userEvent.setup();
  await user.type(await screen.findByLabelText('Добавьте ограничение'),'Ограничение');await user.click(screen.getByRole('button',{name:'Сохранить правило'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Правило изменилось');
});
