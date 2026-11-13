import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { newAuth } from '@/lib/auth_new';
import { ConnectionHelpButton } from './ConnectionHelpButton';
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
beforeEach(()=>vi.clearAllMocks());
it('saves a question with business and service, then shows its persistent number',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValue({request_id:'saved-request'});
  render(<ConnectionHelpButton businessId="business-a" business="Company" service="Telegram" />);
  fireEvent.click(screen.getByRole('button',{name:'Помогите настроить подключение'}));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Cannot find permissions'}});
  fireEvent.click(screen.getByRole('button',{name:'Отправить запрос команде'}));
  await screen.findByText('Номер обращения saved-request');
  expect(newAuth.makeRequest).toHaveBeenCalledWith('/business/business-a/connection-help',expect.objectContaining({method:'POST'}));
  const mutation=vi.mocked(newAuth.makeRequest).mock.calls.find(call=>call[1]?.method==='POST');
  const body=JSON.parse(mutation?.[1]?.body?.toString() || '{}');
  expect(body).toMatchObject({service:'Telegram',message:'Cannot find permissions'});
  expect(body.request_id).toHaveLength(36);
});
it('retains the request key after a temporary failure for safe retry',async()=>{
  let attempted=false;
  vi.mocked(newAuth.makeRequest).mockImplementation(async (_path,options) => {
    if (!options) return {requests:[]};
    if (!attempted) {attempted=true;throw new Error('Temporary failure');}
    return {request_id:'saved'};
  });
  render(<ConnectionHelpButton businessId="business-a" />);
  fireEvent.click(screen.getByRole('button',{name:'Помогите настроить подключение'}));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Help please'}});
  fireEvent.click(screen.getByRole('button',{name:'Отправить запрос команде'}));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button',{name:'Отправить запрос команде'}));
  await screen.findByText('Номер обращения saved');
  const calls=vi.mocked(newAuth.makeRequest).mock.calls.filter(call=>call[1]?.method==='POST');
  expect(calls[0][1]?.body).toBe(calls[1][1]?.body);
});
