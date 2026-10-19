import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {beforeEach,describe,expect,it,vi} from 'vitest';
import {ContentPersonalization} from './ContentPersonalization';
import {contentRequest} from './contentRequest';
vi.mock('./contentRequest',()=>({contentRequest:vi.fn(),ContentAccessError:class extends Error{}}));
vi.mock('./ContentReferences',()=>({ContentReferences:()=>null}));
const profile={version:7,summary:'Конкретно',preferences:{business_description:'Свои изделия',audience_description:'Команды'},examples:[]};
describe.each(['telegram','max'])('%s content facts',platform=>{
 const headers=()=>({'X-Test-Surface':platform});
 beforeEach(()=>vi.mocked(contentRequest).mockReset());
 it('keeps changes and blocks close and editing while the explicit save is in flight',async()=>{
  let resolveSave:(value:unknown)=>void=()=>{};
  vi.mocked(contentRequest).mockImplementation(async(path,init)=>init?.method==='PATCH'?new Promise(resolve=>{resolveSave=resolve;}):{profile});
  const close=vi.fn();render(<ContentPersonalization businessId="b" open onOpenChange={close} headers={headers}/>);
  const story=await screen.findByRole('textbox',{name:'История основателя'});
  fireEvent.change(story,{target:{value:'Основатель лично проверяет образцы.'}});
  fireEvent.click(screen.getByRole('button',{name:'Как писать',exact:true}));
  fireEvent.click(screen.getByRole('button',{name:'Сохранить',exact:true}));
  await waitFor(()=>expect(contentRequest).toHaveBeenCalledWith('/content-voice',expect.objectContaining({method:'PATCH'}),headers));
  expect(screen.getByRole('textbox',{name:'Как должны звучать тексты'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'О бизнесе',exact:true})).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape',code:'Escape'});
  expect(close).not.toHaveBeenCalled();
  const call=vi.mocked(contentRequest).mock.calls.find(([,init])=>init?.method==='PATCH');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({business_id:'b',expected_version:7,founder_story:'Основатель лично проверяет образцы.',confirm:true});
  await act(async()=>resolveSave({profile:{...profile,version:8}}));
  expect(await screen.findByRole('status')).toHaveTextContent('Готовые посты не изменены');
 });
 it('retains entered company and founder information after a failed save',async()=>{
  vi.mocked(contentRequest).mockImplementation(async(path,init)=>{if(init?.method==='PATCH')throw new Error('Нет сети');return {profile};});
  render(<ContentPersonalization businessId="b" open onOpenChange={vi.fn()} headers={headers}/>);
  fireEvent.change(await screen.findByRole('textbox',{name:'История основателя'}),{target:{value:'Собственный рассказ'}});
  fireEvent.click(screen.getByRole('button',{name:'Как писать',exact:true}));fireEvent.click(screen.getByRole('button',{name:'Сохранить',exact:true}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Нет сети');fireEvent.click(screen.getByRole('button',{name:'О бизнесе',exact:true}));
  expect(screen.getByRole('textbox',{name:'История основателя'})).toHaveValue('Собственный рассказ');
  expect(screen.getByRole('textbox',{name:'Что важно знать о бизнесе'})).toHaveValue('Свои изделия');
 });
});
