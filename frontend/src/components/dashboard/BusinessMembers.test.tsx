import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { BusinessMembers } from './BusinessMembers';
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn(() => Promise.reject(new Error('Not configured'))) } }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const response = (name: string) => new Response(JSON.stringify({ members: [{
  id: name, name, email: 'staff@example.ru', is_active: false,
  access: [{ role: 'member', scope: 'business' }, { role: 'viewer', scope: 'network' }],
}] }));

it('shows real roles, account status and both access sources', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response('Анна')));
  render(<BusinessMembers businessId="b" isRu />);
  expect(await screen.findByText('Анна')).toBeInTheDocument();
  expect(screen.getByText('Аккаунт отключён')).toBeInTheDocument();
  expect(screen.getByText('Сотрудник · Этот бизнес')).toBeInTheDocument();
  expect(screen.getByText('Наблюдатель · Через сеть')).toBeInTheDocument();
});

it('clears previous users immediately and ignores a late response after switching', async () => {
  let finish: (value: Response) => void = () => undefined;
  vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('business_id=a')
    ? new Promise<Response>(resolve => { finish = resolve; }) : Promise.resolve(response('Новый бизнес'))));
  const view = render(<BusinessMembers businessId="a" isRu />);
  view.rerender(<BusinessMembers businessId="b" isRu />);
  expect(await screen.findByText('Новый бизнес')).toBeInTheDocument();
  await act(async () => finish(response('Старый бизнес')));
  expect(screen.queryByText('Старый бизнес')).not.toBeInTheDocument();
  view.rerender(<BusinessMembers businessId={null} isRu />);
  expect(screen.queryByText('Новый бизнес')).not.toBeInTheDocument();
  expect(screen.getByText('Выберите бизнес, чтобы увидеть его пользователей.')).toBeInTheDocument();
});

it('removes private data on access failure and supports retry', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{}', { status: 403 })).mockResolvedValueOnce(response('Анна'));
  vi.stubGlobal('fetch', fetcher);
  render(<BusinessMembers businessId="b" isRu />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить');
  await userEvent.setup().click(screen.getByRole('button', { name: 'Повторить загрузку' }));
  expect(await screen.findByText('Анна')).toBeInTheDocument();
});
