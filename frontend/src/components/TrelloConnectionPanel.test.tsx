import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TrelloConnectionPanel } from './TrelloConnectionPanel';

vi.mock('@/lib/auth_new', () => ({ newAuth: { getToken: () => 'local-session' } }));
vi.mock('@/lib/browserSessionFetch', () => ({ browserBearerToken: () => '' }));
const boardId = 'a'.repeat(24);
const respond = (data: object, status = 200) => Promise.resolve(new Response(JSON.stringify({ success: true, ...data }), { status }));
const connected = { enabled: true, configured: true, connected: true, boards: [] };

afterEach(() => vi.unstubAllGlobals());

it('selects a board, saves locally, then reads cards without offering Trello writes', async () => {
  const changed = vi.fn();
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn((url: string, options: RequestInit) => {
    calls.push(`${options.method} ${url}`);
    if (url.endsWith('/status')) return respond(connected);
    if (url.endsWith('/boards')) return respond({ boards: [{ id: boardId, name: 'Работа команды' }] });
    if (url.endsWith('/selection')) {
      expect(JSON.parse(String(options.body))).toEqual({ board_ids: [boardId] });
      return respond({ selected_board_ids: [boardId] });
    }
    return respond({ card_count: 1, snapshot: { board: { id: boardId, name: 'Работа команды' }, lists: [{ id: 'list', name: 'В работе' }],
      cards: [{ id: 'card', name: 'Проверить отзывы', idList: 'list', closed: false, due: null }] } });
  }));
  render(<TrelloConnectionPanel businessId="mine" onChanged={changed} />);
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Работа команды' }));
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить выбор' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Загрузить карточки' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Загрузить карточки' }));
  expect(await screen.findByText('Проверить отзывы')).toBeInTheDocument();
  expect(screen.getByText('В работе')).toBeInTheDocument();
  expect(changed).toHaveBeenCalledTimes(2);
  expect(calls).toContain(`POST /api/business/mine/trello/boards/${boardId}/sync`);
  expect(screen.queryByRole('button', { name: /создать карточку|изменить карточку|опубликовать/i })).not.toBeInTheDocument();
});

it('discards a late private response after the business changes', async () => {
  let finishOld: (response: Response) => void = () => undefined;
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (url.includes('/old/')) return new Promise<Response>((resolve) => { finishOld = resolve; });
    return respond({ enabled: false, configured: false, connected: false, boards: [] });
  }));
  const view = render(<TrelloConnectionPanel key="old" businessId="old" onChanged={() => undefined} />);
  view.rerender(<TrelloConnectionPanel key="new" businessId="new" onChanged={() => undefined} />);
  await screen.findByText(/Подключение ещё не настроено/);
  await act(async () => { finishOld(new Response(JSON.stringify({ success: true, ...connected, boards: [{ board_id: boardId, board_name: 'Private old business' }] }))); });
  expect(screen.queryByText('Private old business')).not.toBeInTheDocument();
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
});

it('clears private board data after provider permission loss', async () => {
  let denied = false;
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (denied) return respond({ success: false, error: 'provider_access_denied', message: 'Нет доступа к доске' }, 403);
    if (url.endsWith('/status')) return respond(connected);
    return respond({ boards: [{ id: boardId, name: 'Private Board' }] });
  }));
  render(<TrelloConnectionPanel businessId="mine" onChanged={() => undefined} />);
  await screen.findByRole('checkbox', { name: 'Private Board' });
  denied = true;
  fireEvent.click(screen.getByRole('button', { name: 'Обновить список досок' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа к доске');
  expect(screen.queryByText('Private Board')).not.toBeInTheDocument();
});

it('retains the last board list on a transient error and permits retry', async () => {
  let failed = false;
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (failed) return respond({ success: false, message: 'Повторите позже' }, 502);
    if (url.endsWith('/status')) return respond(connected);
    return respond({ boards: [{ id: boardId, name: 'My Board' }] });
  }));
  render(<TrelloConnectionPanel businessId="mine" onChanged={() => undefined} />);
  await screen.findByRole('checkbox', { name: 'My Board' });
  failed = true;
  fireEvent.click(screen.getByRole('button', { name: 'Обновить список досок' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Повторите позже');
  expect(screen.getByRole('checkbox', { name: 'My Board' })).toBeInTheDocument();
});
