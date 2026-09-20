import '@testing-library/jest-dom/vitest';
import { act, render, screen } from '@testing-library/react';
import { Fragment, StrictMode, useState, type ReactNode } from 'react';
import { Outlet, MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageContext } from '@/i18n/LanguageContext.logic';
import { en } from '@/i18n/locales/en';
import { newAuth } from '@/lib/auth_new';
import { runJourneyCommand, type JourneyAction } from '@/lib/leadJourney';

import { JourneyWorkspaceFocus } from './JourneyWorkspaceFocus';

const mocks = vi.hoisted(() => {
  class TestHttpError extends Error {
    readonly status: number | null;

    constructor(message: string, status: number | null) {
      super(message);
      this.name = 'HttpError';
      this.status = status;
    }
  }
  return { makeRequest: vi.fn(), HttpError: TestHttpError };
});

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: mocks.makeRequest }, HttpError: mocks.HttpError }));
vi.mock('@/lib/leadJourney', () => ({
  createJourneyCommandIdempotencyKey: vi.fn(() => 'detail-command-key'),
  runJourneyCommand: vi.fn(),
}));

Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: { configurable: true, value: () => false },
  setPointerCapture: { configurable: true, value: () => undefined },
  releasePointerCapture: { configurable: true, value: () => undefined },
  scrollIntoView: { configurable: true, value: () => undefined },
});

const action = (id: string): JourneyAction => ({
  id,
  business_id: 'business-1',
  flow_type: 'content',
  entity_type: 'contentplanitem',
  entity_id: 'content-item-1',
  action_type: 'review_content',
  status: 'ready',
  priority: 100,
  title: `Черновик ${id}`,
  description: `Описание ${id}`,
  cta_label: 'Сохранить черновик',
  payload: { draft_text: `Текст ${id}` },
  allowed_commands: ['save_draft'],
  version: 1,
});

const deferredRequest = () => {
  let resolve: (value: { action: JourneyAction }) => void = () => undefined;
  let reject: (reason?: unknown) => void = () => undefined;
  const promise = new Promise<{ action: JourneyAction }>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
};

const DetailNavigation = ({ businessId = 'business-1' }: { businessId?: string | null }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const choose = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('journey_action', id);
    setSearchParams(next);
  };
  return (
    <>
      <button type="button" onClick={() => choose('action-A')}>Открыть A</button>
      <button type="button" onClick={() => choose('action-B')}>Открыть B</button>
      <button type="button" onClick={() => {
        const next = new URLSearchParams(searchParams);
        next.set('foo', 'latest');
        setSearchParams(next);
      }}>Обновить foo</button>
      <button type="button" onClick={() => setSearchParams({})}>Убрать действие</button>
      <output aria-label="Текущий query">{searchParams.toString()}</output>
      <Outlet context={{ currentBusinessId: businessId }} />
    </>
  );
};

const ChildDraft = () => {
  const [value, setValue] = useState('');
  return <label>Заметка рабочей области<input value={value} onChange={(event) => setValue(event.target.value)} /></label>;
};

const renderFocus = (initialEntry: string, businessId?: string | null, children: ReactNode = <p>Независимый дочерний блок</p>, strict = false) => render(
  <LanguageContext.Provider value={{ language: 'ru', setLanguage: vi.fn(), t: en }}>
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/dashboard" element={<DetailNavigation businessId={businessId} />}>
          <Route index element={<JourneyWorkspaceFocus>{children}</JourneyWorkspaceFocus>} />
        </Route>
      </Routes>
    </MemoryRouter>
  </LanguageContext.Provider>,
  { wrapper: strict ? StrictMode : Fragment },
);

describe('JourneyWorkspaceFocus detail loading', () => {
  beforeEach(() => {
    vi.mocked(newAuth.makeRequest).mockReset();
    vi.mocked(runJourneyCommand).mockReset();
  });

  it('does not request a detail when the URL has no journey_action intent', () => {
    renderFocus('/dashboard?foo=latest');

    expect(newAuth.makeRequest).not.toHaveBeenCalled();
    expect(screen.getByText('Независимый дочерний блок')).toBeVisible();
  });

  it('does not request a detail when the business scope is empty', () => {
    renderFocus('/dashboard?journey_action=action-A', null);

    expect(newAuth.makeRequest).not.toHaveBeenCalled();
  });

  it('keeps B visible when B resolves before the older A request', async () => {
    const requestA = deferredRequest();
    const requestB = deferredRequest();
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return requestA.promise;
      if (url === '/journey-actions/action-B?business_id=business-1') return requestB.promise;
      return Promise.resolve({});
    });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A');
    await user.click(screen.getByRole('button', { name: 'Открыть B' }));

    await act(async () => {
      requestB.resolve({ action: action('action-B') });
    });
    expect(await screen.findByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
    await act(async () => {
      requestA.resolve({ action: action('action-A') });
    });

    expect(screen.getByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Черновик action-A' })).not.toBeInTheDocument();
    const openedActions = vi.mocked(newAuth.makeRequest).mock.calls
      .filter(([url]) => url === '/product/events')
      .map(([, options]) => String(options?.body));
    expect(openedActions.some((body) => body.includes('action-A'))).toBe(false);
  });

  it('does not render a late A error or clear B loading while B is still pending', async () => {
    const requestA = deferredRequest();
    const requestB = deferredRequest();
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return requestA.promise;
      if (url === '/journey-actions/action-B?business_id=business-1') return requestB.promise;
      return Promise.resolve({});
    });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A');
    await user.click(screen.getByRole('button', { name: 'Открыть B' }));
    expect(screen.getByLabelText('Загружаем выбранное действие')).toBeVisible();
    await act(async () => {
      requestA.reject(new Error('Ошибка старого A'));
    });

    expect(screen.queryByText('Ошибка старого A')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Загружаем выбранное действие')).toBeVisible();
    await act(async () => {
      requestB.resolve({ action: action('action-B') });
    });
    expect(await screen.findByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
  });

  it('withholds loaded A immediately when the URL intent changes to pending B', async () => {
    const requestB = deferredRequest();
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return Promise.resolve({ action: action('action-A') });
      if (url === '/journey-actions/action-B?business_id=business-1') return requestB.promise;
      return Promise.resolve({});
    });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A');
    expect(await screen.findByRole('heading', { name: 'Черновик action-A' })).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Открыть B' }));
    expect(screen.queryByRole('heading', { name: 'Черновик action-A' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Загружаем выбранное действие')).toBeVisible();
  });

  it('removes A when the journey_action query is removed', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ action: action('action-A') });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A');
    expect(await screen.findByRole('heading', { name: 'Черновик action-A' })).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Убрать действие' }));
    expect(screen.queryByRole('heading', { name: 'Черновик action-A' })).not.toBeInTheDocument();
    expect(screen.getByText('Независимый дочерний блок')).toBeVisible();
  });

  it('retries the current B request after a transient failure and clears the error', async () => {
    let actionBLoads = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-B?business_id=business-1') {
        actionBLoads += 1;
        if (actionBLoads === 1) return Promise.reject(new Error('B временно недоступно'));
        return Promise.resolve({ action: action('action-B') });
      }
      return Promise.resolve({});
    });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-B');
    expect(await screen.findByText('B временно недоступно')).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(await screen.findByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
    expect(screen.queryByText('B временно недоступно')).not.toBeInTheDocument();
    expect(actionBLoads).toBe(2);
  });

  it('keeps the newest overlapping reload for the same B intent', async () => {
    const first = deferredRequest();
    const second = deferredRequest();
    let loads = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-B?business_id=business-1') {
        loads += 1;
        if (loads === 1) return Promise.resolve({ action: action('action-B') });
        return loads === 2 ? first.promise : second.promise;
      }
      return Promise.resolve({});
    });
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: action('action-B'), next_action: null });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-B');
    expect(await screen.findByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    await act(async () => {
      second.resolve({ action: { ...action('action-B'), title: 'Свежий B' } });
    });
    expect(await screen.findByRole('heading', { name: 'Свежий B' })).toBeVisible();
    await act(async () => {
      first.resolve({ action: { ...action('action-B'), title: 'Старый B' } });
    });
    expect(screen.getByRole('heading', { name: 'Свежий B' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Старый B' })).not.toBeInTheDocument();
  });

  it.each([401, 403, 404])('clears a previously visible card after access denial %s', async (status) => {
    let loads = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') {
        loads += 1;
        if (loads === 1) return Promise.resolve({ action: action('action-A') });
        return Promise.reject(new mocks.HttpError(`Denied ${status}`, status));
      }
      return Promise.resolve({});
    });
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: action('action-A'), next_action: null });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A');
    expect(await screen.findByRole('heading', { name: 'Черновик action-A' })).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    expect(await screen.findByText(`Denied ${status}`)).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Черновик action-A' })).not.toBeInTheDocument();
    expect(screen.getByText('Независимый дочерний блок')).toBeVisible();
  });

  it('keeps a network failure visible with its retry instead of clearing the current card', async () => {
    let loads = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') {
        loads += 1;
        if (loads === 1) return Promise.resolve({ action: action('action-A') });
        return Promise.reject(new mocks.HttpError('Network retry', 500));
      }
      return Promise.resolve({});
    });
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: action('action-A'), next_action: null });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A');
    expect(await screen.findByRole('heading', { name: 'Черновик action-A' })).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    expect(await screen.findByText('Network retry')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Черновик action-A' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeVisible();
  });

  it('preserves the JourneyActionCard draft when only an unrelated query value refreshes the same action', async () => {
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return Promise.resolve({ action: action('action-A') });
      return Promise.resolve({});
    });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A&foo=first');
    const draft = await screen.findByDisplayValue('Текст action-A');
    await user.clear(draft);
    await user.type(draft, 'Локальная правка A');

    await user.click(screen.getByRole('button', { name: 'Обновить foo' }));
    expect(await screen.findByDisplayValue('Локальная правка A')).toBeVisible();
  });

  it('preserves an unrelated workspace child draft across A, B and removed intent', async () => {
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return Promise.resolve({ action: action('action-A') });
      if (url === '/journey-actions/action-B?business_id=business-1') return Promise.resolve({ action: action('action-B') });
      return Promise.resolve({});
    });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A', undefined, <ChildDraft />);
    const note = screen.getByRole('textbox', { name: 'Заметка рабочей области' });
    await user.type(note, 'Не потерять заметку');
    await user.click(screen.getByRole('button', { name: 'Открыть B' }));
    expect(await screen.findByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
    expect(screen.getByDisplayValue('Не потерять заметку')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Убрать действие' }));
    expect(screen.getByDisplayValue('Не потерять заметку')).toBeVisible();
  });

  it.each([500, null])('keeps the edited B draft through transient status %s and successful Retry', async (status) => {
    let loads = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-B?business_id=business-1') {
        loads += 1;
        if (loads === 1 || loads === 3) return Promise.resolve({ action: action('action-B') });
        return Promise.reject(new mocks.HttpError('Временная ошибка B', status));
      }
      return Promise.resolve({});
    });
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: action('action-B'), next_action: null });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-B');
    const draft = await screen.findByDisplayValue('Текст action-B');
    await user.clear(draft);
    await user.type(draft, 'Правка B до Retry');
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    expect(await screen.findByText('Временная ошибка B')).toBeVisible();
    expect(screen.getByDisplayValue('Правка B до Retry')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(await screen.findByDisplayValue('Правка B до Retry')).toBeVisible();
    expect(screen.queryByText('Временная ошибка B')).not.toBeInTheDocument();
    expect(loads).toBe(3);
  });

  it('ignores the first StrictMode lifetime after its replacement request succeeds', async () => {
    const first = deferredRequest();
    const second = deferredRequest();
    let loads = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return ++loads === 1 ? first.promise : second.promise;
      return Promise.resolve({});
    });
    renderFocus('/dashboard?journey_action=action-A', undefined, undefined, true);
    expect(loads).toBe(2);
    await act(async () => { second.resolve({ action: { ...action('action-A'), title: 'Текущий ответ' } }); });
    expect(screen.getByRole('heading', { name: 'Текущий ответ' })).toBeVisible();
    await act(async () => { first.resolve({ action: { ...action('action-A'), title: 'Устаревший ответ' } }); });
    expect(screen.getByRole('heading', { name: 'Текущий ответ' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Устаревший ответ' })).not.toBeInTheDocument();
  });

  it('does not navigate from B when a command belonging to the departed A resolves', async () => {
    const pendingCommand = deferredRequest();
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return Promise.resolve({ action: action('action-A') });
      if (url === '/journey-actions/action-B?business_id=business-1') return Promise.resolve({ action: action('action-B') });
      return Promise.resolve({});
    });
    vi.mocked(runJourneyCommand).mockImplementationOnce(() => pendingCommand.promise.then((result) => ({ ...result, next_action: action('action-C') })));
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A');
    expect(await screen.findByRole('heading', { name: 'Черновик action-A' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    await user.click(screen.getByRole('button', { name: 'Открыть B' }));
    expect(await screen.findByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
    await act(async () => { pendingCommand.resolve({ action: action('action-A') }); });
    expect(screen.getByLabelText('Текущий query')).toHaveTextContent('journey_action=action-B');
    expect(screen.getByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
    expect(newAuth.makeRequest).not.toHaveBeenCalledWith('/journey-actions/action-C?business_id=business-1');
  });

  it('retains an edited handoff on transient refresh failure but does not seed a later revisit', async () => {
    const firstB = deferredRequest();
    const revisitB = deferredRequest();
    let loadsB = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return Promise.resolve({ action: action('action-A') });
      if (url === '/journey-actions/action-B?business_id=business-1') return ++loadsB === 1 ? firstB.promise : revisitB.promise;
      return Promise.resolve({});
    });
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: action('action-A'), next_action: action('action-B') });
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A');
    expect(await screen.findByRole('heading', { name: 'Черновик action-A' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    const draft = screen.getByDisplayValue('Текст action-B');
    await user.clear(draft);
    await user.type(draft, 'Правка нового действия');
    await act(async () => { firstB.reject(new mocks.HttpError('Обновление временно недоступно', 500)); });
    expect(screen.getByDisplayValue('Правка нового действия')).toBeVisible();
    expect(screen.getByText('Обновление временно недоступно')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Открыть A' }));
    expect(await screen.findByRole('heading', { name: 'Черновик action-A' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Открыть B' }));
    expect(loadsB).toBe(2);
    expect(screen.queryByRole('heading', { name: 'Черновик action-B' })).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('Правка нового действия')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Загружаем выбранное действие')).toBeVisible();
  });

  it('keeps the latest foo query when a pending current command hands off to B', async () => {
    const pendingCommand = deferredRequest();
    vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
      if (url === '/journey-actions/action-A?business_id=business-1') return Promise.resolve({ action: action('action-A') });
      if (url === '/journey-actions/action-B?business_id=business-1') return new Promise(() => undefined);
      return Promise.resolve({});
    });
    vi.mocked(runJourneyCommand).mockImplementationOnce(() => pendingCommand.promise.then((result) => ({ ...result, next_action: action('action-B') })));
    const user = userEvent.setup();
    renderFocus('/dashboard?journey_action=action-A&foo=first');
    expect(await screen.findByRole('heading', { name: 'Черновик action-A' })).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    await user.click(screen.getByRole('button', { name: 'Обновить foo' }));
    await act(async () => {
      pendingCommand.resolve({ action: action('action-A') });
    });
    expect(await screen.findByRole('heading', { name: 'Черновик action-B' })).toBeVisible();
    expect(screen.getByLabelText('Текущий query')).toHaveTextContent('journey_action=action-B&foo=latest');
  });
});
