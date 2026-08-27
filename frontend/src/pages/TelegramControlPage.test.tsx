import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TelegramControlPage } from './TelegramControlPage';

const jsonResponse = (payload: unknown) => Promise.resolve(new Response(JSON.stringify(payload), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

const openOperator = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(await screen.findByRole('button', { name: 'Ещё' }));
  await user.click(await screen.findByRole('button', { name: 'Оператор' }));
};

const openGrowthPaths = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(await screen.findByRole('button', { name: 'Пути' }));
};

describe('TelegramControlPage scope integrity', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/telegram/control');
    window.localStorage.setItem('localos-mini-onboarding-v3:user-1', 'completed');
    window.sessionStorage.clear();
    Object.defineProperty(window, 'Telegram', {
      configurable: true,
      value: { WebApp: { initData: 'signed-init-data', ready: vi.fn(), expand: vi.fn() } },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it('does not show operator messages from the previous business while the new history loads', async () => {
    const secondHistory = new Promise<Response>(() => undefined);
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
          summary: { attention_items: [] },
          catalog: {
            businesses: [
              { id: 'business-1', name: 'Точка один' },
              { id: 'business-2', name: 'Точка два' },
            ],
            networks: [],
            total_choices: 2,
          },
          navigation: [
            { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
            { key: 'tasks', label: 'В работе', group: 'primary', status: 'available' },
            { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' },
          ],
        });
      }
      if (url.startsWith('/api/operator/mobile/workspace')) {
        return jsonResponse({ items: [], summary: { attention_items: [] } });
      }
      if (url.startsWith('/api/operator/mobile/operator/history')) {
        if (url.includes('scope_id=business-2')) return secondHistory;
        return jsonResponse({ items: [{ id: 'old-message', role: 'operator', content: 'Секрет точки один', status: 'completed' }] });
      }
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') {
        return jsonResponse({
          success: true,
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-2', name: 'Точка два', business_ids: ['business-2'], can_switch: true },
          summary: { attention_items: [] },
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await openOperator(user);
    expect(await screen.findByText('Секрет точки один')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Точка два/ })).toBeInTheDocument());
    await openOperator(user);

    expect(screen.queryByText('Секрет точки один')).not.toBeInTheDocument();
  });

  it('marks Growth paths as the current destination for a review deep link', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: false },
          summary: { attention_items: [] },
          catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }], networks: [], total_choices: 1 },
          resolved_deep_link: { screen: 'reviews', filters: { status: 'unanswered' } },
          navigation: [
            { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
            { key: 'tasks', label: 'В работе', group: 'primary', status: 'available' },
            { key: 'reviews', label: 'Отзывы', group: 'primary', status: 'available' },
            { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' },
          ],
        });
      }
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/reviews')) return jsonResponse({
        items: [{ id: 'review-invalid-date', business_id: 'business-1', author_name: 'Клиент', rating: 5, text: 'Хорошо', published_at: 'not-a-date' }],
        counts: { total: 1, unanswered: 1, drafts: 0 },
        filters: {},
      });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<TelegramControlPage />);

    expect(await screen.findByRole('heading', { name: 'Отзывы' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Отзывы' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Пути' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: 'Сегодня' })).not.toHaveAttribute('aria-current');
    expect(screen.queryByText(/Invalid Date/i)).not.toBeInTheDocument();
    expect(screen.getByText(/дата не указана источником/i)).toBeInTheDocument();
  });

  it('opens the Development overview instead of treating more as an unavailable module', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Весёлая расчёска', business_ids: ['business-1'], can_switch: false },
          summary: { attention_items: [] },
          catalog: { businesses: [{ id: 'business-1', name: 'Весёлая расчёска' }], networks: [], total_choices: 1 },
          navigation: [
            { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
            { key: 'progress', label: 'Прогресс', group: 'primary', status: 'available' },
            { key: 'cards', label: 'Карточки', group: 'more', status: 'available' },
            { key: 'finance', label: 'Финансы', group: 'more', status: 'available' },
          ],
        });
      }
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await openGrowthPaths(user);

    expect(await screen.findByRole('heading', { name: 'Пути роста' })).toBeInTheDocument();
    expect(screen.getByText('Больше клиентов из карт')).toBeInTheDocument();
    expect(screen.queryByText('Раздел пока недоступен')).not.toBeInTheDocument();
  });

  it('does not let a slower response from the previous scope replace the current Today', async () => {
    let resolveBusinessTwo: ((response: Response) => void) | undefined;
    const businessTwoToday = new Promise<Response>((resolve) => { resolveBusinessTwo = resolve; });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: true,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
          summary: { attention_items: [] },
          catalog: {
            businesses: [
              { id: 'business-1', name: 'Точка один' },
              { id: 'business-2', name: 'Точка два' },
              { id: 'business-3', name: 'Точка три' },
            ],
            networks: [],
            total_choices: 3,
          },
          navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }],
        });
      }
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') {
        const payload = JSON.parse(String(init.body || '{}'));
        const suffix = payload.scope_id === 'business-2' ? 'два' : 'три';
        return jsonResponse({
          success: true,
          today_v2_enabled: true,
          selected_scope: { kind: 'business', id: payload.scope_id, name: `Точка ${suffix}`, business_ids: [payload.scope_id], can_switch: true },
          summary: { attention_items: [] },
        });
      }
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/today')) {
        if (url.includes('scope_id=business-2')) return businessTwoToday;
        const title = url.includes('scope_id=business-3') ? 'Приоритет точки три' : 'Приоритет точки один';
        return jsonResponse({ scope: {}, focus_action: { title, reason: 'Тест', cta_label: 'Открыть', screen: 'tasks' } });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    expect(await screen.findByText('Приоритет точки один')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));
    await user.click(screen.getByRole('button', { name: /Точка три/ }));
    expect(await screen.findByText('Приоритет точки три')).toBeInTheDocument();

    resolveBusinessTwo?.(new Response(JSON.stringify({ scope: {}, focus_action: { title: 'Приоритет точки два', reason: 'Устаревший ответ', cta_label: 'Открыть', screen: 'tasks' } }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    await waitFor(() => expect(screen.queryByText('Приоритет точки два')).not.toBeInTheDocument());
    expect(screen.getByText('Приоритет точки три')).toBeInTheDocument();
  });

  it('does not let reviews from the previous scope replace the current business reviews', async () => {
    let resolveBusinessTwo: ((response: Response) => void) | undefined;
    const businessTwoReviews = new Promise<Response>((resolve) => { resolveBusinessTwo = resolve; });
    const reviewsPayload = (businessId: string, author: string) => ({
      scope: { kind: 'business', id: businessId },
      items: [{
        id: `review-${businessId}`,
        business_id: businessId,
        author_name: author,
        rating: 5,
        source: 'Яндекс',
        location_name: businessId,
        text: `Отзыв ${author}`,
        published_at: '2026-08-10T08:00:00Z',
      }],
      counts: { total: 1, unanswered: 1, drafts: 0 },
      filters: {},
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
          summary: { attention_items: [] },
          catalog: {
            businesses: [
              { id: 'business-1', name: 'Точка один' },
              { id: 'business-2', name: 'Точка два' },
              { id: 'business-3', name: 'Точка три' },
            ],
            networks: [],
            total_choices: 3,
          },
          resolved_deep_link: { screen: 'reviews', filters: { status: 'unanswered' } },
          navigation: [
            { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
            { key: 'reviews', label: 'Отзывы', group: 'primary', status: 'available' },
          ],
        });
      }
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') {
        const payload = JSON.parse(String(init.body || '{}'));
        const suffix = payload.scope_id === 'business-2' ? 'два' : 'три';
        return jsonResponse({
          success: true,
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: payload.scope_id, name: `Точка ${suffix}`, business_ids: [payload.scope_id], can_switch: true },
          summary: { attention_items: [] },
        });
      }
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/reviews')) {
        if (url.includes('scope_id=business-2')) return businessTwoReviews;
        if (url.includes('scope_id=business-3')) return jsonResponse(reviewsPayload('business-3', 'Автор три'));
        return jsonResponse(reviewsPayload('business-1', 'Автор один'));
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    expect(await screen.findByText('Автор один')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Точка два/ })).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /Точка два/ }));
    await user.click(await screen.findByRole('button', { name: /Точка три/ }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Точка три/ })).toBeInTheDocument());
    await openGrowthPaths(user);
    await user.click(await screen.findByRole('button', { name: 'Ответить на отзывы' }));
    expect(await screen.findByText('Автор три')).toBeInTheDocument();

    resolveBusinessTwo?.(new Response(JSON.stringify(reviewsPayload('business-2', 'Автор два')), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    await waitFor(() => expect(screen.queryByText('Автор два')).not.toBeInTheDocument());
    expect(screen.getByText('Автор три')).toBeInTheDocument();
  });

  it('does not expose Invalid Date when a content-plan item has an impossible date', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: false },
          summary: { attention_items: [] },
          catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }], networks: [], total_choices: 1 },
          resolved_deep_link: { screen: 'content' },
          navigation: [
            { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
            { key: 'content', label: 'Контент', group: 'more', status: 'available' },
          ],
        });
      }
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/modules/content')) return jsonResponse({
        items: [{
          id: 'content-invalid-date',
          business_id: 'business-1',
          business_name: 'Точка один',
          title: 'Тема из плана',
          subtitle: 'Нужно подготовить текст',
          plan_title: 'Контент-план',
          scheduled_for: '2026-99-99T12:00:00',
        }],
        filters: { allowed_period_days: [7, 14, 30] },
      });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<TelegramControlPage />);

    expect(await screen.findByRole('heading', { name: 'Контент' })).toBeInTheDocument();
    expect(await screen.findByText('Тема из плана')).toBeInTheDocument();
    expect(screen.queryByText(/Invalid Date/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/Без даты/i).length).toBeGreaterThan(0);
  });

  it('does not show a late operator history response from the previous business', async () => {
    let resolveBusinessOne: ((response: Response) => void) | undefined;
    const businessOneHistory = new Promise<Response>((resolve) => { resolveBusinessOne = resolve; });
    const businessTwoHistory = new Promise<Response>(() => undefined);
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
          summary: { attention_items: [] },
          catalog: {
            businesses: [
              { id: 'business-1', name: 'Точка один' },
              { id: 'business-2', name: 'Точка два' },
            ],
            networks: [],
            total_choices: 2,
          },
          navigation: [
            { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
            { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' },
          ],
        });
      }
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/operator/history')) {
        return url.includes('scope_id=business-2') ? businessTwoHistory : businessOneHistory;
      }
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') {
        return jsonResponse({
          success: true,
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-2', name: 'Точка два', business_ids: ['business-2'], can_switch: true },
          summary: { attention_items: [] },
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await openOperator(user);
    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Точка два/ })).toBeInTheDocument());

    resolveBusinessOne?.(new Response(JSON.stringify({
      items: [{ id: 'late-old-message', role: 'operator', content: 'Старый секрет первой точки', status: 'completed' }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    await openOperator(user);

    await waitFor(() => expect(screen.queryByText('Старый секрет первой точки')).not.toBeInTheDocument());
  });

  it('keeps the latest business search results when an earlier request finishes late', async () => {
    let resolveOldSearch: ((response: Response) => void) | undefined;
    const oldSearch = new Promise<Response>((resolve) => { resolveOldSearch = resolve; });
    const bootstrapPayload = (businesses: Array<{ id: string; name: string }>) => ({
      success: true,
      user: { id: 'user-1', name: 'Owner' },
      web_session_token: 'session',
      today_v2_enabled: false,
      selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
      summary: { attention_items: [] },
      catalog: { businesses, networks: [], total_choices: businesses.length },
      navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }],
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        const payload = JSON.parse(String(init?.body || '{}'));
        if (payload.q === 'ста') return oldSearch;
        if (payload.q === 'нов') return jsonResponse(bootstrapPayload([{ id: 'business-new', name: 'Новый салон' }]));
        return jsonResponse(bootstrapPayload([
          { id: 'business-1', name: 'Точка один' },
          { id: 'business-2', name: 'Вторая точка' },
        ]));
      }
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await user.click(await screen.findByRole('button', { name: /Точка один/ }));
    const search = await screen.findByPlaceholderText('Название, город или адрес');
    await user.type(search, 'ста');
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/operator/telegram/bootstrap', expect.objectContaining({ body: expect.stringContaining('"q":"ста"') })));
    await user.clear(search);
    await user.type(search, 'нов');
    expect(await screen.findByText('Новый салон')).toBeInTheDocument();

    resolveOldSearch?.(new Response(JSON.stringify(bootstrapPayload([{ id: 'business-old', name: 'Старый салон' }])), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    await waitFor(() => expect(screen.queryByText('Старый салон')).not.toBeInTheDocument());
    expect(screen.getByText('Новый салон')).toBeInTheDocument();
  });

  it('keeps the latest network-location search results when an earlier request finishes late', async () => {
    let resolveOldSearch: ((response: Response) => void) | undefined;
    const oldSearch = new Promise<Response>((resolve) => { resolveOldSearch = resolve; });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'network', id: 'network-1', name: 'Сеть', business_ids: ['business-1'], can_switch: true },
          summary: { attention_items: [] },
          catalog: { businesses: [], networks: [{ id: 'network-1', name: 'Сеть', locations_count: 2 }], total_choices: 2 },
          navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }],
        });
      }
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/network-locations')) {
        const query = new URL(url, 'https://localos.pro').searchParams.get('q') || '';
        if (query === 'ста') return oldSearch;
        if (query === 'нов') return jsonResponse({ items: [{ id: 'business-new', name: 'Новая точка' }], counts: { total: 1 }, cursor: null });
        return jsonResponse({ items: [], counts: { total: 2 }, cursor: null });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await user.click(await screen.findByRole('button', { name: /Сеть/ }));
    const search = await screen.findByPlaceholderText('Название или адрес точки');
    await user.type(search, 'ста');
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('q=%D1%81%D1%82%D0%B0'), expect.anything()));
    await user.clear(search);
    await user.type(search, 'нов');
    expect(await screen.findByText('Новая точка')).toBeInTheDocument();

    resolveOldSearch?.(new Response(JSON.stringify({ items: [{ id: 'business-old', name: 'Старая точка' }], counts: { total: 1 }, cursor: null }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    await waitFor(() => expect(screen.queryByText('Старая точка')).not.toBeInTheDocument());
    expect(screen.getByText('Новая точка')).toBeInTheDocument();
  });

  it('clears selected reviews when the business scope changes', async () => {
    const reviewPayload = (businessId: string, author: string) => ({
      scope: { kind: 'business', id: businessId },
      items: [{ id: `review-${businessId}`, business_id: businessId, author_name: author, rating: 5, text: 'Хорошо', published_at: '2026-08-10T08:00:00Z' }],
      counts: { total: 1, unanswered: 1, drafts: 0 },
      filters: { locations: [] },
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
          summary: { attention_items: [] },
          catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }, { id: 'business-2', name: 'Точка два' }], networks: [], total_choices: 2 },
          resolved_deep_link: { screen: 'reviews' },
          navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'reviews', label: 'Отзывы', group: 'primary', status: 'available' }],
        });
      }
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') return jsonResponse({
        success: true,
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-2', name: 'Точка два', business_ids: ['business-2'], can_switch: true },
        summary: { attention_items: [] },
      });
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/reviews')) return jsonResponse(url.includes('scope_id=business-2') ? reviewPayload('business-2', 'Автор два') : reviewPayload('business-1', 'Автор один'));
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    expect(await screen.findByText('Автор один')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Выбрать отзыв' }));
    expect(screen.getByText('Выбрано: 1')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));
    await openGrowthPaths(user);
    await user.click(await screen.findByRole('button', { name: 'Ответить на отзывы' }));
    expect(await screen.findByText('Автор два')).toBeInTheDocument();

    expect(screen.queryByText(/Выбрано:/)).not.toBeInTheDocument();
  });

  it('clears a location review filter when the business scope changes', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') {
        return jsonResponse({
          success: true,
          user: { id: 'user-1', name: 'Owner' },
          web_session_token: 'session',
          today_v2_enabled: false,
          selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
          summary: { attention_items: [] },
          catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }, { id: 'business-2', name: 'Точка два' }], networks: [], total_choices: 2 },
          resolved_deep_link: { screen: 'reviews' },
          navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'reviews', label: 'Отзывы', group: 'primary', status: 'available' }],
        });
      }
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') return jsonResponse({
        success: true,
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-2', name: 'Точка два', business_ids: ['business-2'], can_switch: true },
        summary: { attention_items: [] },
      });
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/reviews')) return jsonResponse({
        items: [],
        counts: { total: 0, unanswered: 0, drafts: 0 },
        filters: { locations: url.includes('scope_id=business-2') ? [{ id: 'location-new', name: 'Новая точка' }] : [{ id: 'location-old', name: 'Старая точка' }] },
      });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await screen.findByRole('heading', { name: 'Отзывы' });
    await user.click(screen.getByRole('button', { name: /^Фильтры/ }));
    await user.selectOptions(screen.getByLabelText('Точка'), 'location-old');
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes('location_id=location-old'))).toBe(true));
    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));
    await openGrowthPaths(user);
    await user.click(await screen.findByRole('button', { name: 'Ответить на отзывы' }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes('scope_id=business-2'))).toBe(true));

    expect(fetchMock.mock.calls.some(([input]) => {
      const url = String(input);
      return url.includes('/api/operator/mobile/reviews') && url.includes('scope_id=business-2') && url.includes('location_id=location-old');
    })).toBe(false);
  });

  it('does not append an operator response from the previous business after scope changes', async () => {
    let resolveOldOperator: ((response: Response) => void) | undefined;
    const oldOperatorResponse = new Promise<Response>((resolve) => { resolveOldOperator = resolve; });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') return jsonResponse({
        success: true,
        user: { id: 'user-1', name: 'Owner' },
        web_session_token: 'session',
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
        summary: { attention_items: [] },
        catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }, { id: 'business-2', name: 'Точка два' }], networks: [], total_choices: 2 },
        navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' }],
      });
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') return jsonResponse({
        success: true,
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-2', name: 'Точка два', business_ids: ['business-2'], can_switch: true },
        summary: { attention_items: [] },
      });
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/operator/history')) return jsonResponse({ items: [] });
      if (url === '/api/operator/chat') return oldOperatorResponse;
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await openOperator(user);
    await user.type(await screen.findByPlaceholderText('Напишите задачу'), 'Проверь первую точку');
    await user.click(screen.getByRole('button', { name: 'Отправить задачу' }));
    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));
    await openOperator(user);

    resolveOldOperator?.(new Response(JSON.stringify({ operator_result: { chat_response: 'Результат первой точки', status: 'completed' } }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    await waitFor(() => expect(screen.queryByText('Результат первой точки')).not.toBeInTheDocument());
  });

  it('removes a restored job from the previous business after scope changes', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') return jsonResponse({
        success: true,
        user: { id: 'user-1', name: 'Owner' },
        web_session_token: 'session',
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
        summary: { attention_items: [] },
        active_job: { id: 'job-business-1', kind: 'card_refresh', status: 'running', progress: 25, stage: 'Обновляем первую точку', terminal: false },
        catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }, { id: 'business-2', name: 'Точка два' }], networks: [], total_choices: 2 },
        navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }],
      });
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') return jsonResponse({
        success: true,
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-2', name: 'Точка два', business_ids: ['business-2'], can_switch: true },
        summary: { attention_items: [] },
        active_job: null,
      });
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/jobs/')) return jsonResponse({ job: { id: 'job-business-1', kind: 'card_refresh', status: 'running', progress: 25, stage: 'Обновляем первую точку', terminal: false } });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    expect(await screen.findByRole('dialog', { name: 'Обновляем данные карточки' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Обновляем данные карточки' })).not.toBeInTheDocument());
  });

  it('does not reuse a review deep link from the previous business after scope changes', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') return jsonResponse({
        success: true,
        user: { id: 'user-1', name: 'Owner' },
        web_session_token: 'session',
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: true },
        summary: { attention_items: [] },
        catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }, { id: 'business-2', name: 'Точка два' }], networks: [], total_choices: 2 },
        resolved_deep_link: { screen: 'reviews', item_type: 'review', item_id: 'review-business-1' },
        navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'reviews', label: 'Отзывы', group: 'primary', status: 'available' }],
      });
      if (url === '/api/operator/telegram/scope' && init?.method === 'POST') return jsonResponse({
        success: true,
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-2', name: 'Точка два', business_ids: ['business-2'], can_switch: true },
        summary: { attention_items: [] },
      });
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/reviews')) return jsonResponse({
        items: [],
        counts: { total: 0, unanswered: 0, drafts: 0 },
        filters: { locations: [] },
      });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await screen.findByRole('heading', { name: 'Отзывы' });
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => {
      const url = String(input);
      return url.includes('/api/operator/mobile/reviews') && url.includes('scope_id=business-1') && url.includes('review_id=review-business-1');
    })).toBe(true));

    await user.click(screen.getByRole('button', { name: /Точка один/ }));
    await user.click(await screen.findByRole('button', { name: /Точка два/ }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => {
      const url = String(input);
      return url.includes('/api/operator/mobile/reviews') && url.includes('scope_id=business-2');
    })).toBe(true));
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Где работаем?' })).not.toBeInTheDocument());
    await openGrowthPaths(user);
    await user.click(await screen.findByRole('button', { name: 'Ответить на отзывы' }));
    await screen.findByRole('heading', { name: 'Отзывы' });
    await user.click(screen.getByRole('button', { name: /^\u0424\u0438\u043b\u044c\u0442\u0440\u044b/ }));
    await user.selectOptions(screen.getByLabelText('\u041e\u0446\u0435\u043d\u043a\u0430'), '5');
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => {
      const url = String(input);
      return url.includes('/api/operator/mobile/reviews') && url.includes('scope_id=business-2') && url.includes('rating=5');
    })).toBe(true));

    expect(fetchMock.mock.calls.some(([input]) => {
      const url = String(input);
      return url.includes('/api/operator/mobile/reviews') && url.includes('scope_id=business-2') && url.includes('review_id=review-business-1');
    })).toBe(false);
  });

  it('confirms and rejects governed Operator actions inside the mini-app chat', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') return jsonResponse({
        success: true,
        user: { id: 'user-1', name: 'Owner' },
        web_session_token: 'session',
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: false },
        summary: { attention_items: [] },
        catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }], networks: [], total_choices: 1 },
        navigation: [
          { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
          { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' },
        ],
      });
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/operator/history')) return jsonResponse({
        items: [
          {
            id: 'message-confirm',
            role: 'operator',
            content: 'Применить изменение цены?',
            status: 'approval_required',
            result_json: { approval: { action_id: 'action-confirm' } },
          },
          {
            id: 'message-reject',
            role: 'operator',
            content: 'Отправить сообщение?',
            status: 'approval_required',
            result_json: { approval: { action_id: 'action-reject' } },
          },
        ],
      });
      if (url === '/api/operator/actions/action-confirm/confirm' && init?.method === 'POST') return jsonResponse({
        success: true,
        operator_result: { status: 'completed', chat_response: 'Изменение применено.' },
      });
      if (url === '/api/operator/actions/action-reject/reject' && init?.method === 'POST') return jsonResponse({
        success: true,
        operator_result: { status: 'rejected', chat_response: 'Отправка отклонена.' },
      });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await openOperator(user);
    expect(await screen.findByText('Применить изменение цены?')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Подтвердить' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'Отклонить' })).toHaveLength(2);

    await user.click(screen.getAllByRole('button', { name: 'Подтвердить' })[0]);
    expect(await screen.findByText('Изменение применено.')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Отклонить' })).toHaveLength(1);

    await user.click(screen.getByRole('button', { name: 'Отклонить' }));
    expect(await screen.findByText('Отправка отклонена.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Подтвердить' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes('/api/operator/actions/'))).toHaveLength(2);
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).endsWith('/action-confirm/confirm') && String(init?.body).includes('business-1'))).toBe(true);
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).endsWith('/action-reject/reject') && String(init?.body).includes('business-1'))).toBe(true);
  });

  it('keeps approval controls available after a failed decision request', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/operator/telegram/bootstrap') return jsonResponse({
        success: true,
        user: { id: 'user-1', name: 'Owner' },
        web_session_token: 'session',
        today_v2_enabled: false,
        selected_scope: { kind: 'business', id: 'business-1', name: 'Точка один', business_ids: ['business-1'], can_switch: false },
        summary: { attention_items: [] },
        catalog: { businesses: [{ id: 'business-1', name: 'Точка один' }], networks: [], total_choices: 1 },
        navigation: [{ key: 'operator', label: 'Оператор', group: 'primary', status: 'available' }],
      });
      if (url.startsWith('/api/operator/mobile/workspace')) return jsonResponse({ items: [], summary: { attention_items: [] } });
      if (url.startsWith('/api/operator/mobile/operator/history')) return jsonResponse({
        items: [{
          id: 'message-retry',
          role: 'operator',
          content: 'Применить изменение?',
          status: 'approval_required',
          result_json: { approval: { action_id: 'action-retry' } },
        }],
      });
      if (url === '/api/operator/actions/action-retry/confirm' && init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({
        success: false,
        error: 'Временно не удалось подтвердить.',
      }), { status: 503, headers: { 'Content-Type': 'application/json' } }));
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<TelegramControlPage />);
    await openOperator(user);
    await user.click(await screen.findByRole('button', { name: 'Подтвердить' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Временно не удалось подтвердить.');
    expect(screen.getByRole('button', { name: 'Подтвердить' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Отклонить' })).toBeEnabled();
  });

});
