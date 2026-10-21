import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach,expect,it,vi} from 'vitest';
import JobProgressSheet from './JobProgressSheet';
import {PartnershipsMobileModule} from './PartnershipsMobileModule';
afterEach(()=>vi.unstubAllGlobals());
const response=(value:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}}));
it('waits for review without claiming background progress',()=>{
 render(<JobProgressSheet job={{id:'review',status:'waiting_for_review',progress:100,stage:'План требует проверки'}} onClose={()=>undefined}/>);
 expect(screen.getByRole('heading',{name:'Проверьте результат'})).toBeInTheDocument();
 expect(screen.queryByText('ЛокалОС работает')).not.toBeInTheDocument();
 expect(screen.queryByText(/Работа продолжится/)).not.toBeInTheDocument();
 expect(screen.getByText(/до вашего решения/)).toBeVisible();
});
it('does not describe a completed plan as still generating',()=>{
 render(<JobProgressSheet job={{id:'done',kind:'content_plan_generate',status:'completed',progress:100}} onClose={()=>undefined}/>);
 expect(screen.getByRole('heading',{name:'Результат готов'})).toBeVisible();
});
it('allows clearing the editor, disables blank approval, and keeps edits on stale save',async()=>{
 const calls:string[]=[];
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>{
  const url=String(input);calls.push(url);
  if(url.endsWith('/save'))return response({error:'Письмо изменилось. Обновите список.'},409);
  if(url.startsWith('/api/partnership/drafts?'))return response({drafts:[{id:'draft',lead_id:'lead',lead_name:'Клиника',channel:'email',status:'generated',generated_text:'Первый текст',review_digest:'v1'}]});
  return response({items:[],batches:[],ready_drafts:[],reactions:[]});
 }));
 const user=userEvent.setup();render(<PartnershipsMobileModule scope={{kind:'business',id:'business'}}/>);
 await user.click(await screen.findByRole('button',{name:'Письма'}));
 const field=await screen.findByRole('textbox',{name:'Текст письма: Клиника'});
 expect(screen.getByText('Эл. почта · Черновик')).toBeVisible();
 await user.clear(field);expect(field).toHaveValue('');
 expect(screen.getByRole('button',{name:'Утвердить письмо'})).toBeDisabled();
 await user.type(field,'Мой проверенный текст');
 await user.click(screen.getByRole('button',{name:'Сохранить черновик без отправки'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Письмо изменилось');
 expect(field).toHaveValue('Мой проверенный текст');
 expect(calls.some(url=>url.includes('/approve')||url.includes('/confirm'))).toBe(false);
});
it('warns about a legal contact without replacing existing client data',async()=>{
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).startsWith('/api/partnership/leads?')?response({items:[{id:'lead',name:'Клиника',email:'jur@example.test'}]}):response({items:[],drafts:[],batches:[],ready_drafts:[],reactions:[]})));
 const user=userEvent.setup();render(<PartnershipsMobileModule scope={{kind:'business',id:'business'}}/>);
 await user.click(await screen.findByRole('button',{name:'Кандидаты'}));
 await user.click(await screen.findByRole('button',{name:/Клиника/}));
 expect(await screen.findByRole('note')).toHaveTextContent('служебный или юридический адрес');
});
