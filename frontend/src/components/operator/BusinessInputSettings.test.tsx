import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { BusinessInputSettings } from './BusinessInputSettings';

const headers = () => ({ Authorization: 'Bearer test' });
const reply = (data: unknown) => Promise.resolve(new Response(JSON.stringify(data)));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('prepares city and currency through chat without writing settings directly', async () => {
  vi.stubGlobal('fetch', vi.fn(() => reply({ city: 'Таллин', currency: 'EUR', timezone: 'Europe/Tallinn', can_edit: true })));
  const submit = vi.fn(() => Promise.resolve()); const user = userEvent.setup();
  render(<BusinessInputSettings businessId="b" onSubmit={submit} headers={headers} />);
  await user.click(screen.getByRole('button', { name: 'Город и валюта бизнеса' }));
  const city = await screen.findByLabelText('Город');
  await user.clear(city); await user.type(city, 'Пхукет');
  await user.clear(screen.getByLabelText('Валюта')); await user.type(screen.getByLabelText('Валюта'), 'THB');
  await user.click(screen.getByRole('button', { name: 'Проверить изменения в чате' }));
  expect(submit).toHaveBeenCalledExactlyOnceWith('Сохрани настройки бизнеса: город: Пхукет; валюта: THB');
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('does not offer editing to a read-only member', async () => {
  vi.stubGlobal('fetch', vi.fn(() => reply({ can_edit: false })));
  const user = userEvent.setup();
  render(<BusinessInputSettings businessId="b" onSubmit={vi.fn()} headers={headers} />);
  await user.click(screen.getByRole('button', { name: 'Город и валюта бизнеса' }));
  expect(await screen.findByLabelText('Город')).toBeDisabled();
});

it('ignores late settings from the previous business', async () => {
  let finish: (response: Response) => void = () => undefined;
  vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('business_id=a') ? new Promise<Response>(resolve => { finish = resolve; }) : reply({ city: 'Пхукет', can_edit: true })));
  const user = userEvent.setup(); const submit = vi.fn();
  const view = render(<BusinessInputSettings businessId="a" onSubmit={submit} headers={headers} />);
  await user.click(screen.getByRole('button', { name: 'Город и валюта бизнеса' }));
  view.rerender(<BusinessInputSettings businessId="b" onSubmit={submit} headers={headers} />);
  await waitFor(() => expect(screen.getByLabelText('Город')).toHaveValue('Пхукет'));
  finish(new Response(JSON.stringify({ city: 'Старый бизнес', can_edit: true })));
  await waitFor(() => expect(screen.getByLabelText('Город')).toHaveValue('Пхукет'));
});
