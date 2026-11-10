import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { YouGileConnectionPanel } from './YouGileConnectionPanel';
import { mapIntegrationsState } from '@/pages/dashboard/settings/integrationsRegistryState';

vi.mock('@/lib/auth_new', () => ({ newAuth: { getToken: () => 'test-session' } }));
vi.mock('@/lib/browserSessionFetch', () => ({ browserBearerToken: () => '' }));
afterEach(() => vi.unstubAllGlobals());
const json = (body: object, status = 200) => new Response(JSON.stringify({ success: true, ...body }), { status });
const connected = { enabled: true, connected: true, configured: true, can_configure: true, can_write: true,
  selection: { project_id: 'project', board_id: 'board', column_id: 'column', board_name: 'Поручения', column_name: 'Новые' } };
const tasks = { items: [], users: [{ id: 'anna', name: 'Анна' }], columns: [{ id: 'column', title: 'Новые' }] };

describe('customer YouGile panel', () => {
  it('connects a key and walks through project, board and column selection', async () => {
    let linked = false;
    const request = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/connection')) { linked = true; return Promise.resolve(json({})); }
      if (url.endsWith('/status')) return Promise.resolve(json({ ...connected, connected: linked, configured: false }));
      if (url.includes('/catalog?project_id=project&board_id=board')) return Promise.resolve(json({ items: [{ id: 'column', title: 'Новые' }] }));
      if (url.includes('/catalog?project_id=project')) return Promise.resolve(json({ items: [{ id: 'board', title: 'Поручения' }] }));
      if (url.endsWith('/catalog')) return Promise.resolve(json({ items: [{ id: 'project', title: 'Команда' }] }));
      if (url.endsWith('/selection')) return Promise.resolve(json({}));
      throw new Error(url + init?.method);
    });
    vi.stubGlobal('fetch', request);
    render(<YouGileConnectionPanel businessId="mine" onChanged={vi.fn()} />);
    fireEvent.change(await screen.findByLabelText('API-ключ вашей команды YouGile'), { target: { value: 'secret-client-key' } });
    fireEvent.click(screen.getByRole('button', { name: 'Подключить YouGile' }));
    await screen.findByRole('option', { name: 'Команда' });
    expect(screen.queryByDisplayValue('secret-client-key')).toBeNull();
    fireEvent.change(screen.getByLabelText('Проект'), { target: { value: 'project' } });
    await screen.findByRole('option', { name: 'Поручения' });
    fireEvent.change(screen.getByLabelText('Доска'), { target: { value: 'board' } });
    await screen.findByRole('option', { name: 'Новые' });
    fireEvent.change(screen.getByLabelText('Колонка для новых задач'), { target: { value: 'column' } });
    fireEvent.click(screen.getByRole('button', { name: 'Использовать эту доску' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith('/api/business/mine/yougile/selection', expect.objectContaining({ method: 'PUT', body: JSON.stringify({ project_id: 'project', board_id: 'board', column_id: 'column' }) })));
  });

  it('shows the exact preview and writes only after a separate confirmation', async () => {
    const request = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/status')) return Promise.resolve(json(connected));
      if (url.endsWith('/catalog')) return Promise.resolve(json({ items: [] }));
      if (url.endsWith('/tasks')) return Promise.resolve(json(tasks));
      if (url.endsWith('/preview')) return Promise.resolve(json({ operator_result: { status: 'approval_required', chat_response: 'Создать: собрать фото. Исполнитель: Анна.', approval: { action_id: 'review-1' } } }));
      if (url.endsWith('/confirm')) return Promise.resolve(json({ operator_result: { status: 'completed', chat_response: 'Задача создана в YouGile.' } }));
      throw new Error(url);
    });
    vi.stubGlobal('fetch', request);
    render(<YouGileConnectionPanel businessId="mine" onChanged={vi.fn()} />);
    await screen.findByText(/На доске пока нет задач/);
    fireEvent.click(screen.getByText('Новое поручение'));
    fireEvent.change(screen.getByLabelText('Что нужно сделать'), { target: { value: 'Собрать фото' } });
    fireEvent.change(screen.getByLabelText('Ответственный'), { target: { value: 'anna' } });
    fireEvent.click(screen.getByRole('button', { name: 'Проверить поручение' }));
    expect(await screen.findByRole('region', { name: 'Проверка поручения' })).toHaveTextContent('Исполнитель: Анна');
    expect(request.mock.calls.some(([url]) => String(url).endsWith('/confirm'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить в YouGile' }));
    await screen.findByText('Задача создана в YouGile.');
    expect(request).toHaveBeenCalledWith('/api/operator/actions/review-1/confirm', expect.objectContaining({ method: 'POST', body: JSON.stringify({ business_id: 'mine' }) }));
  });

  it('does not show a late response after switching business', async () => {
    let release: (response: Response) => void = () => {};
    const old = new Promise<Response>(resolve => { release = resolve; });
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => String(input).includes('/mine/') ? old : Promise.resolve(json({ enabled: false }))));
    const view = render(<YouGileConnectionPanel businessId="mine" onChanged={vi.fn()} />);
    view.rerender(<YouGileConnectionPanel businessId="other" onChanged={vi.fn()} />);
    await screen.findByText('Подключение YouGile пока выключено администратором.');
    release(json(connected));
    await waitFor(() => expect(screen.queryByText(/Рабочая доска/)).toBeNull());
  });

  it('removes private tasks on permission failure', async () => {
    let denied = false;
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/status')) return Promise.resolve(json({ ...connected, can_configure: false, can_write: false }));
      if (denied) return Promise.resolve(json({ success: false, error: 'Доступ отозван' }, 403));
      return Promise.resolve(json({ ...tasks, items: [{ id: 'task', title: 'Личное поручение', completed: false, columnId: 'column' }] }));
    }));
    render(<YouGileConnectionPanel businessId="mine" onChanged={vi.fn()} />);
    await screen.findByText('Личное поручение');
    denied = true;
    fireEvent.click(screen.getByRole('button', { name: 'Обновить задачи' }));
    await screen.findByRole('alert');
    expect(screen.queryByText('Личное поручение')).toBeNull();
    expect(screen.queryByText('Новое поручение')).toBeNull();
  });

  it('distinguishes connection from a configured task destination', () => {
    expect(mapIntegrationsState({ yougileStatus: { connected: true, configured: false } }).find(service => service.id === 'yougile')?.status).toBe('action_required');
    expect(mapIntegrationsState({ yougileStatus: { connected: true, configured: true } }).find(service => service.id === 'yougile')?.status).toBe('connected');
  });
});
