import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { PartnershipGroupLaunch } from './PartnershipGroupLaunch';
const mocks=vi.hoisted(()=>({request:vi.fn()}));
vi.mock('@/lib/auth_new',()=>({newAuth:{makeRequest:mocks.request}}));
const schedule={telegram_start:'2026-10-23T13:00:00+03:00',email_start:'2026-10-23T14:30:00+03:00',interval_minutes:5};
const preview={digest:'bound-digest',counts:{telegram:16,email:34},company_count:50,touch_count:200,schedule,runtime_ready:true,items:Array.from({length:50},(_,i)=>({campaign_id:`c${i}`,name:`Компания ${i}`,touches:Array.from({length:4},(_,n)=>({id:`t${i}-${n}`,channel:i<16?'telegram':'email',recipient:i<16?`@company${i}`:`company${i}@example.test`,sender_label:i<16?'Telegram · …1234':'sender@example.test',generated_text:'Сохранённый текст',scheduled_at:'2026-10-23T13:00:00+03:00'}))}))};
beforeEach(()=>{mocks.request.mockReset();mocks.request.mockResolvedValue({preview});});
afterEach(()=>{vi.unstubAllGlobals();sessionStorage.clear();});
const open=async()=>{await userEvent.click(screen.getByRole('button',{name:'Проверить запуск группы'}));await screen.findByText('1. Telegram — 16 · 2. Почта — 34');};
it('preview and final review do not approve or queue any message',async()=>{
 render(<PartnershipGroupLaunch businessId="business" collectionId="group"/>);await open();
 expect(screen.getAllByText(/Компания \d+/)).toHaveLength(50);
 expect(screen.getByLabelText('Начало Telegram')).toHaveValue('2026-10-23T13:00');
 await userEvent.click(screen.getByRole('button',{name:'Перейти к итоговой проверке'}));
 expect(screen.getByRole('button',{name:'Подтвердить и поставить в очередь'})).toBeDisabled();
 expect(mocks.request).toHaveBeenCalledTimes(1);
 expect(JSON.parse(mocks.request.mock.calls[0][1].body).action).toBe('preview');
});
it('only explicit text and delivery decisions submit the exact reviewed digest',async()=>{
 render(<PartnershipGroupLaunch businessId="business" collectionId="group"/>);await open();
 await userEvent.click(screen.getByRole('button',{name:'Перейти к итоговой проверке'}));
 const checks=screen.getAllByRole('checkbox');await userEvent.click(checks[0]);
 expect(screen.getByRole('button',{name:'Подтвердить и поставить в очередь'})).toBeDisabled();
 await userEvent.click(checks[1]);mocks.request.mockResolvedValueOnce({launch:{batch_id:'native-batch',company_count:50,touch_count:200}});
 await userEvent.click(screen.getByRole('button',{name:'Подтвердить и поставить в очередь'}));
 expect(await screen.findByRole('heading',{name:'Расписание подтверждено'})).toBeVisible();
 expect(JSON.parse(mocks.request.mock.calls[1][1].body)).toEqual({business_id:'business',action:'confirm',schedule,digest:'bound-digest',reviewed:true,confirmed:true});
});
it('editing dates invalidates the old preview and requires a new check',async()=>{
 render(<PartnershipGroupLaunch businessId="business" collectionId="group"/>);await open();
 fireEvent.change(screen.getByLabelText('Начало Telegram'),{target:{value:'2026-10-23T15:00'}});
 expect(screen.queryByRole('button',{name:'Перейти к итоговой проверке'})).toBeNull();
 expect(mocks.request).toHaveBeenCalledTimes(1);
 await userEvent.click(screen.getByRole('button',{name:'Обновить проверку'}));
 await waitFor(()=>expect(mocks.request).toHaveBeenCalledTimes(2));
 expect(JSON.parse(mocks.request.mock.calls[1][1].body).schedule.telegram_start).toBe('2026-10-23T15:00:00+03:00');
});
it('shows a disabled runtime without offering confirmation',async()=>{
 mocks.request.mockResolvedValue({preview:{...preview,runtime_ready:false,warning:'Отправка выключена'}});
 render(<PartnershipGroupLaunch businessId="business" collectionId="group"/>);await open();
 expect(screen.getByRole('alert')).toHaveTextContent('Отправка выключена');
 expect(screen.getByRole('button',{name:'Перейти к итоговой проверке'})).toBeDisabled();
});
it('uses the miniapp session for Telegram and MAX',async()=>{
 sessionStorage.setItem('localos_mini_session','qa-mini');const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({preview})});vi.stubGlobal('fetch',fetchMock);
 render(<PartnershipGroupLaunch businessId="business" collectionId="group" mobile/>);await open();
 expect(fetchMock.mock.calls[0][0]).toBe('/api/partnership/collections/group/launch');
 expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer qa-mini');
 expect(mocks.request).not.toHaveBeenCalled();
});
it('does not reuse a previous business preview after a scope change',async()=>{
 let old:(value:unknown)=>void=()=>{};mocks.request.mockImplementationOnce(()=>new Promise(resolve=>{old=resolve;}));
 const view=render(<PartnershipGroupLaunch businessId="one" collectionId="old"/>);
 await userEvent.click(screen.getByRole('button',{name:'Проверить запуск группы'}));
 view.rerender(<PartnershipGroupLaunch businessId="two" collectionId="new"/>);
 await act(async()=>{old({preview});await Promise.resolve();});
 expect(screen.queryByText('1. Telegram — 16 · 2. Почта — 34')).toBeNull();
 expect(screen.getByRole('button',{name:'Проверить запуск группы'})).toBeVisible();
});
it('a failed confirmation clears its decision and cannot be silently retried',async()=>{
 render(<PartnershipGroupLaunch businessId="business" collectionId="group"/>);await open();await userEvent.click(screen.getByRole('button',{name:'Перейти к итоговой проверке'}));
 for(const box of screen.getAllByRole('checkbox'))await userEvent.click(box);
 mocks.request.mockRejectedValueOnce(new Error('Тексты изменились'));
 await userEvent.click(screen.getByRole('button',{name:'Подтвердить и поставить в очередь'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Тексты изменились');
 expect(screen.queryByRole('dialog')).toBeNull();expect(screen.queryByRole('button',{name:'Перейти к итоговой проверке'})).toBeNull();
});
it('defaults to first messages and invalidates review when scope changes',async()=>{
 render(<PartnershipGroupLaunch businessId="business" collectionId="group"/>);
 expect(screen.getByLabelText('Только первые обращения. Повторные касания останутся черновиками.')).toBeChecked();await open();
 expect(JSON.parse(mocks.request.mock.calls[0][1].body).schedule.first_touch_only).toBe(true);
 await userEvent.click(screen.getByLabelText('Только первые обращения. Повторные касания останутся черновиками.'));
 expect(screen.queryByRole('button',{name:'Перейти к итоговой проверке'})).toBeNull();
});
it('refreshes the parent queue exactly once after a confirmed launch',async()=>{
 const launched=vi.fn();render(<PartnershipGroupLaunch businessId="business" collectionId="group" onLaunched={launched}/>);await open();
 expect(launched).not.toHaveBeenCalled();await userEvent.click(screen.getByRole('button',{name:'Перейти к итоговой проверке'}));
 for(const box of screen.getAllByRole('checkbox'))await userEvent.click(box);
 mocks.request.mockResolvedValueOnce({launch:{batch_id:'batch',company_count:50,touch_count:50}});
 await userEvent.click(screen.getByRole('button',{name:'Подтвердить и поставить в очередь'}));
 await waitFor(()=>expect(launched).toHaveBeenCalledTimes(1));
});
