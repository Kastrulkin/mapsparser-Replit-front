import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { PartnershipsMobileModule } from './PartnershipsMobileModule';
const response=(value:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}}));
afterEach(()=>vi.unstubAllGlobals());
function setup(existing=false,status='queued'){
 const calls:{url:string;method:string}[]=[]; let readyNow=false;
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
  const url=String(input), method=init?.method||'GET';calls.push({url,method});
  if(url.includes('/leads?'))return response({items:[{id:'qa-lead',name:'QA Партнёр',active_workstream_id:'qa-work',pipeline_status:'unprocessed'}]});
  if(url.includes('/drafts?'))return response({drafts:existing||readyNow?[{id:'qa-letter',lead_id:'qa-lead',lead_name:'QA Партнёр',status:'draft',channel:'email',generated_text:'Тестовое письмо для проверки, без отправки.'}]:[]});
  if(url.endsWith('/draft-offer'))return response({success:true,accepted:true,job:{id:'qa-job',status:'queued'},message:'Подготовка началась'},202);
  if(url.includes('/contact-intelligence?')){readyNow=status==='ready'; return response({success:true,job:{id:'qa-job',status,error:status==='limited'?'Лимит расхода AI достигнут':status==='failed'?'private provider failure':null},first_message:status==='ready'?{id:'qa-letter'}:null});}
  return response({drafts:[],batches:[],items:[],counts:{}});
 }));
 render(<PartnershipsMobileModule scope={{kind:'business',id:'qa-business'}}/>);
 return {calls,user:userEvent.setup()};
}
it('opens an existing letter without queuing another generation',async()=>{
 const {calls,user}=setup(true);
 await user.click(await screen.findByRole('button',{name:'Кандидаты'}));
 await user.click(await screen.findByRole('button',{name:/QA Партнёр/}));
 await user.click(await screen.findByRole('button',{name:'Открыть письмо',exact:true}));
 expect(await screen.findByText('Тестовое письмо для проверки, без отправки.')).toBeVisible();
 expect(calls.every(c=>c.method==='GET')).toBe(true);
});
it.each(['queued','failed','needs_contact'])('shows %s preparation state inside the selected partner card',async status=>{
 const {calls,user}=setup(false,status);
 await user.click(await screen.findByRole('button',{name:'Кандидаты'}));
 await user.click(await screen.findByRole('button',{name:/QA Партнёр/}));
 const card=screen.getByRole('dialog');
 await user.click(within(card).getByRole('button',{name:'Подготовить письмо',exact:true}));
 expect(await within(card).findByRole('status')).toBeVisible();
 expect(within(card).queryByText('Готово. Данные обновлены.')).not.toBeInTheDocument();
 expect(within(card).queryByText('private provider failure')).not.toBeInTheDocument();
 if(status==='queued'){
  await user.click(within(card).getByRole('button',{name:'Проверить готовность письма'}));
  expect(calls.filter(c=>c.url.endsWith('/draft-offer'))).toHaveLength(1);
 }
});

it('opens the result after a ready check without repeating generation',async()=>{
 const {calls,user}=setup(false,'ready');
 await user.click(await screen.findByRole('button',{name:'Кандидаты'}));
 await user.click(await screen.findByRole('button',{name:/QA Партнёр/}));
 await user.click(screen.getByRole('button',{name:'Подготовить письмо',exact:true}));
 await user.click(await screen.findByRole('button',{name:'Открыть письмо',exact:true}));
 expect(await screen.findByText('Тестовое письмо для проверки, без отправки.')).toBeVisible();
 expect(calls.filter(c=>c.url.endsWith('/draft-offer'))).toHaveLength(1);
 expect(calls.some(c=>/send|approve/.test(c.url)&&c.method==='POST')).toBe(false);
});
it.each(['network','server'])('retains a draft with a clear %s error and no internal details',async failure=>{
 const {user}=setup(true);
 const original=window.fetch;
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
  if(String(input).endsWith('/save'))return failure==='network'?Promise.reject(new TypeError('Failed to fetch')):response({error:'private SQL detail'},503);
  return original(input,init);
 }));
 await user.click(await screen.findByRole('button',{name:'Письма',exact:true}));
 const field=await screen.findByRole('textbox',{name:'Текст письма: QA Партнёр'});
 await user.clear(field); await user.type(field,'Несохранённая правка');
 await user.click(screen.getByRole('button',{name:'Сохранить черновик без отправки'}));
 expect(await screen.findByRole('alert')).toHaveTextContent(failure==='network'?'Нет связи с LocalOS':'не смог подтвердить результат');
 expect(field).toHaveValue('Несохранённая правка');
 expect(screen.queryByText('private SQL detail')).not.toBeInTheDocument();
});

it('explains a provider limit without claiming a new letter is ready',async()=>{
 const {user}=setup(false,'limited');
 await user.click(await screen.findByRole('button',{name:'Кандидаты'}));
 await user.click(await screen.findByRole('button',{name:/QA Партнёр/}));
 await user.click(screen.getByRole('button',{name:'Подготовить письмо',exact:true}));
 expect(await screen.findByRole('status')).toHaveTextContent('Лимит генерации исчерпан');
});
it('protects letter edits and review controls while a save response is pending',async()=>{
 const {user}=setup(true);const original=window.fetch;let finish:(value:Response)=>void=()=>{};
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>String(input).endsWith('/save')?new Promise<Response>(resolve=>{finish=resolve}):original(input,init)));
 await user.click(await screen.findByRole('button',{name:'Письма',exact:true}));
 const field=await screen.findByRole('textbox',{name:'Текст письма: QA Партнёр'});
 await user.clear(field);await user.type(field,'Проверяемая версия');
 await user.click(screen.getByRole('button',{name:'Сохранить черновик без отправки'}));
 expect(field).toBeDisabled();
 expect(screen.getByRole('button',{name:'Утвердить письмо'})).toBeDisabled();
 expect(screen.getByRole('button',{name:'Удалить черновик'})).toBeDisabled();
 expect(screen.getByRole('button',{name:'Сохраняем…',exact:true})).toBeDisabled();
 await user.type(field,' это нельзя потерять');expect(field).toHaveValue('Проверяемая версия');
 finish(new Response(JSON.stringify({success:true}),{status:200}));
 await screen.findByText('Черновик сохранён. Отправка не разрешена.');
});
