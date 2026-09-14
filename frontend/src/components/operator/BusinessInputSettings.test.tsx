import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { BusinessInputSettings } from './BusinessInputSettings';

const headers = () => ({ Authorization: 'Bearer test' });
const reply = (data: unknown) => Promise.resolve(new Response(JSON.stringify(data)));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('saves the profile fields without sending a chat command', async () => {
  const fetcher=vi.fn((url: string, options?: RequestInit) => reply(options?.method === 'PATCH' ? {city:'Пхукет',currency:'THB',timezone:'Asia/Bangkok',can_edit:true,version:2} : {city:'Таллин',currency:'EUR',timezone:'Europe/Tallinn',can_edit:true,version:1}));
  vi.stubGlobal('fetch', fetcher); const user=userEvent.setup();
  render(<BusinessInputSettings businessId="b" headers={headers} />);
  const city=await screen.findByLabelText('Город');
  await user.clear(city); await user.type(city,'Пхукет');
  await user.clear(screen.getByLabelText('Валюта')); await user.type(screen.getByLabelText('Валюта'),'THB');
  await user.click(screen.getByRole('button',{name:'Сохранить'}));
  expect(await screen.findByRole('status')).toHaveTextContent('Настройки бизнеса сохранены');
  const call=fetcher.mock.calls.find(([,options])=>options?.method==='PATCH');
  expect(call?.[0]).toBe('/api/operator/input-settings?business_id=b');
  const payload=JSON.parse(String(call?.[1]?.body));
  expect(payload).toMatchObject({city:'Пхукет',currency:'THB',settingsVersion:1});
  expect(payload.timezone).toBeUndefined();
  expect(screen.getByLabelText('Город')).toHaveValue('Пхукет');
});

it('does not offer editing to a read-only member', async () => {
  vi.stubGlobal('fetch',vi.fn(()=>reply({can_edit:false})));
  render(<BusinessInputSettings businessId="b" headers={headers} />);
  expect(await screen.findByLabelText('Город')).toBeDisabled();
});

it('ignores late settings from the previous business', async () => {
  let finish:(response:Response)=>void=()=>undefined;
  vi.stubGlobal('fetch',vi.fn((url:string)=>url.includes('business_id=a') ? new Promise<Response>(resolve=>{finish=resolve;}) : reply({city:'Пхукет',can_edit:true})));
  const view=render(<BusinessInputSettings businessId="a" headers={headers} />);
  view.rerender(<BusinessInputSettings businessId="b" headers={headers} />);
  await waitFor(()=>expect(screen.getByLabelText('Город')).toHaveValue('Пхукет'));
  finish(new Response(JSON.stringify({city:'Старый бизнес',can_edit:true})));
  await waitFor(()=>expect(screen.getByLabelText('Город')).toHaveValue('Пхукет'));
});
