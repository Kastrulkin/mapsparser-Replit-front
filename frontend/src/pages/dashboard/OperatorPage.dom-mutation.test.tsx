import '@testing-library/jest-dom/vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ErrorBoundary } from '@/components/ErrorBoundary';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { OperatorPage } from './OperatorPage';

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const ContextRoute = () => (
  <Outlet context={{
    currentBusinessId: 'demo-business',
    currentBusiness: { id: 'demo-business', name: 'Тестовый бизнес' },
  }} />
);

const deferredResponse = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
};

describe('OperatorPage DOM ownership', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
  });

  it('stays usable when a browser translator moves the loading label', async () => {
    const historyResponse = deferredResponse<{ data: { messages: never[]; conversation: null } }>();
    vi.mocked(api.get).mockReturnValue(historyResponse.promise);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    render(
      <MemoryRouter initialEntries={['/dashboard/operator']}>
        <LanguageProvider>
          <ErrorBoundary>
            <Routes>
              <Route element={<ContextRoute />}>
                <Route path="/dashboard/operator" element={<OperatorPage />} />
              </Route>
            </Routes>
          </ErrorBoundary>
        </LanguageProvider>
      </MemoryRouter>,
    );

    const loadingLabel = await screen.findByText('Загружаем историю…');
    const textNode = Array.from(loadingLabel.childNodes).find((node) => (
      node.nodeType === Node.TEXT_NODE && node.textContent?.includes('Загружаем историю')
    ));
    const translatedWrapper = document.createElement('font');

    expect(textNode).toBeDefined();
    translatedWrapper.setAttribute('data-external-translation', 'true');
    loadingLabel.insertBefore(translatedWrapper, textNode!);
    translatedWrapper.appendChild(textNode!);

    await act(async () => {
      historyResponse.resolve({ data: { messages: [], conversation: null } });
      await historyResponse.promise;
    });

    expect(screen.queryByText('Что-то пошло не так')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Напишите задачу' })).toBeInTheDocument();
    consoleError.mockRestore();
  });

  it('shows a search preview as conditions, without a false result link', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { conversation: null, messages: [{
      id: 'preview-1', role: 'operator', content: 'Поиск не запущен.',
      result_json: { status: 'completed', capability: 'partnerships.prepare_message',
        search_started: false, result_ref: { href: '/dashboard/partnerships', label: 'Открыть поиск партнёров' } },
    }] } });

    render(
      <MemoryRouter initialEntries={['/dashboard/operator']}>
        <LanguageProvider>
          <ErrorBoundary>
            <Routes><Route element={<ContextRoute />}>
              <Route path="/dashboard/operator" element={<OperatorPage />} />
            </Route></Routes>
          </ErrorBoundary>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Ожидает запуска')).toBeInTheDocument();
    expect(screen.getByText('Поиск ещё не начался')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Начать поиск' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Открыть поиск партнёров' })).not.toBeInTheDocument();
  });

  it('creates the reviewed search through chat and shows the confirmation state', async () => {
    const task = { id: 'search-task', status: 'waiting_for_review', stage: 'Ожидает запуска',
      config: { target_count: 10, max_search_calls: 3 }, state: { search_calls: 1 }, report: { eligible: 2 } };
    vi.mocked(api.get).mockImplementation(async (url) => url === '/partnership/continuations/search-task'
      ? { data: task }
      : url === '/partnership/continuations'
      ? { data: { items: [task] } }
      : { data: { conversation: { id: 'conversation-1' }, messages: [{ id: 'preview-1', role: 'operator',
        content: 'Условия показаны.', result_json: { status: 'completed', capability: 'partnerships.prepare_message', search_started: false } }] } });
    vi.mocked(api.post).mockResolvedValue({ data: { conversation_id: 'conversation-1', operator_result: {
      status: 'approval_required', chat_response: 'Подтвердите запуск.', capability: 'partnerships.continue_outreach', search_started: false,
      task, credit_quote: { total_max: 62 }, approval: { status: 'pending', action_id: 'approval-1', capability: 'partnerships.continue_outreach' },
    } } });
    render(
      <MemoryRouter initialEntries={['/dashboard/operator']}>
        <LanguageProvider><ErrorBoundary><Routes><Route element={<ContextRoute />}>
          <Route path="/dashboard/operator" element={<OperatorPage />} />
        </Route></Routes></ErrorBoundary></LanguageProvider>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Начать поиск' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/operator/chat', expect.objectContaining({
      message: 'Начни поиск по показанным условиям', conversation_id: 'conversation-1',
    })));
    expect(await screen.findByText('Ожидает подтверждения или проверки')).toBeInTheDocument();
    expect(document.body.textContent).toContain('Подходящих с подтверждённым контактом: 2 из 10');
    expect(screen.getByRole('button', { name: 'Начать поиск' })).toBeInTheDocument();
  });

  it('hides confirmation for an old outreach approval with dollar pricing', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { conversation: null, messages: [{
      id: 'old-approval', role: 'operator', content: 'Бюджет поиска до 1.00 USD',
      result_json: { status: 'approval_required', capability: 'partnerships.continue_outreach',
        approval: { status: 'pending', action_id: 'old-action', capability: 'partnerships.continue_outreach' } },
    }] } });
    render(<MemoryRouter initialEntries={['/dashboard/operator']}><LanguageProvider><ErrorBoundary><Routes>
      <Route element={<ContextRoute />}><Route path="/dashboard/operator" element={<OperatorPage />} /></Route>
    </Routes></ErrorBoundary></LanguageProvider></MemoryRouter>);
    expect(await screen.findByText(/Условия этого подтверждения устарели/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Показать актуальные условия' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Подтвердить' })).not.toBeInTheDocument();
  });

  it('shows an active search indicator from a saved task', async () => {
    const task = { id: 'search-task', status: 'running', stage: 'Проверка контактов',
      config: { target_count: 10, max_search_calls: 3 }, state: { search_calls: 1 }, report: { eligible: 2 } };
    vi.mocked(api.get).mockImplementation(async (url) => url === '/partnership/continuations/search-task'
      ? { data: task }
      : url === '/partnership/continuations'
      ? { data: { items: [task] } }
      : { data: { conversation: null, messages: [{ id: 'search-1', role: 'operator', content: 'Поиск запущен.',
        result_json: { status: 'completed', capability: 'partnerships.continue_outreach', task } }] } });
    render(
      <MemoryRouter initialEntries={['/dashboard/operator']}>
        <LanguageProvider><ErrorBoundary><Routes><Route element={<ContextRoute />}>
          <Route path="/dashboard/operator" element={<OperatorPage />} />
        </Route></Routes></ErrorBoundary></LanguageProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByText('Поиск идёт')).toBeInTheDocument();
    expect(document.body.textContent).toContain('Подходящих с подтверждённым контактом: 2 из 10');
  });
});
