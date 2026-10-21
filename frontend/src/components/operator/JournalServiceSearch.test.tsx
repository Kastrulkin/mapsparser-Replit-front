import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { JournalServiceSearch } from './JournalServiceSearch';
afterEach(cleanup);
const props={businessId:'b',entryId:'entry',version:2,quote:'Грязные окна',city:'Москва',channel:'max_mini_app'};
const preview={status:'approval_required',chat_response:'Найти мойщика. До 20 кредитов. Ничего не отправляется.',approval:{action_id:'approval',status:'pending'}};
it('reviews source, conditions and costs before explicit confirmation',async()=>{
 const started=vi.fn(async()=>{});const request=vi.fn(async(path:string,init?:RequestInit)=>{
  if(path.endsWith('/preview')){expect(JSON.parse(String(init?.body))).toMatchObject({business_id:'b',version:2,audience:'Мойщик окон',geography:'Москва',mode:'find_only',channel:'max_mini_app'});return preview;}
  return {operator_result:{status:'completed'}};
 });
 render(<JournalServiceSearch {...props} request={request} onStarted={started} onCancel={vi.fn()}/>);
 expect(request).not.toHaveBeenCalled();fireEvent.change(screen.getByLabelText('Кого найти?'),{target:{value:'Мойщик окон'}});
 fireEvent.click(screen.getByRole('button',{name:'Проверить условия и расходы'}));
 await screen.findByText(/До 20 кредитов/);expect(request).toHaveBeenCalledTimes(1);expect(started).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Подтвердить запуск поиска'}));
 await vi.waitFor(()=>expect(started).toHaveBeenCalledTimes(1));
 expect(request.mock.calls[1][0]).toBe('/operator/actions/approval/confirm');
});
it('editing conditions removes the old preview; closing explicitly cancels its pending approval',async()=>{
 const cancelled=vi.fn();const request=vi.fn(async()=>preview);
 render(<JournalServiceSearch {...props} request={request} onStarted={async()=>{}} onCancel={cancelled}/>);
 fireEvent.change(screen.getByLabelText('Кого найти?'),{target:{value:'Мойщик окон'}});
 fireEvent.click(screen.getByRole('button',{name:'Проверить условия и расходы'}));await screen.findByText(/До 20 кредитов/);
 fireEvent.change(screen.getByLabelText('Город, район или адрес'),{target:{value:'Другой район'}});
 expect(screen.queryByRole('button',{name:'Подтвердить запуск поиска'})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Закрыть без запуска'}));await vi.waitFor(()=>expect(cancelled).toHaveBeenCalled());
 expect(request).toHaveBeenLastCalledWith('/operator/actions/approval/reject',expect.objectContaining({method:'POST'}));
});
it('preserves the request when search is not included in the plan',async()=>{
 const request=vi.fn(async()=>({status:'blocked',chat_response:'Для поиска нужен тариф «Привлечение».'}));
 render(<JournalServiceSearch {...props} request={request} onStarted={async()=>{}} onCancel={vi.fn()}/>);
 fireEvent.change(screen.getByLabelText('Кого найти?'),{target:{value:'Мойщик окон'}});
 fireEvent.click(screen.getByRole('button',{name:'Проверить условия и расходы'}));await screen.findByRole('alert');
 expect(screen.getByLabelText('Кого найти?')).toHaveValue('Мойщик окон');expect(screen.queryByRole('button',{name:'Подтвердить запуск поиска'})).not.toBeInTheDocument();
});
