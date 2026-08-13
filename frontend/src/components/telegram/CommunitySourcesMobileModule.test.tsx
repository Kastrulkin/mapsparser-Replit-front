import '@testing-library/jest-dom/vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { CommunitySourcesMobileModule } from './CommunitySourcesMobileModule';

const response = (payload: unknown) => Promise.resolve(new Response(JSON.stringify(payload), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

describe('CommunitySourcesMobileModule destructive actions', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows the included industry pulse before asking for personal sources', async () => {
    render(<CommunitySourcesMobileModule businessId="preview" />);

    expect(await screen.findByText('Бьюти-пульс уже включён')).toBeInTheDocument();
    expect(screen.getByText(/^18$/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Добавить свои источники' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Добавленные вами' })).toBeInTheDocument();
    expect(screen.getByText('Радар следит за новыми сообщениями')).toBeInTheDocument();
    expect(screen.getByText('Главные темы попадают в «Сегодня»')).toBeInTheDocument();
    expect(screen.getByText('Подходящие темы используются для публикаций')).toBeInTheDocument();
  });

  it('connects a public source to the personal pulse and content selection', async () => {
    let loadedAfterAdd = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = String(init?.method || 'GET');
      if (url === '/api/business/business-1/community-sources' && method === 'POST') {
        loadedAfterAdd = true;
        return response({
          success: true,
          destinations: ['radar', 'community_pulse', 'content_ideas'],
          superadmin_notification: 'queued',
          message: 'Источник подключён. ЛокалОС следит за новыми сообщениями, добавляет важное в «Сегодня» и учитывает темы при подготовке публикаций.',
        });
      }
      if (url === '/api/business/business-1/community-sources' && method === 'GET') {
        return response({ items: loadedAfterAdd ? [{ id: 'source-1', title: 'Beauty Owners', canonical_url: 'https://t.me/beauty_owners', sync_status: 'queued' }] : [] });
      }
      return response({ success: true });
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<CommunitySourcesMobileModule businessId="business-1" />);
    await user.type(await screen.findByPlaceholderText('https://t.me/channel'), 'https://t.me/beauty_owners');
    await user.click(screen.getByRole('button', { name: 'Начать следить' }));

    expect(await screen.findByText(/Источник подключён/)).toBeInTheDocument();
    expect(await screen.findByText('Beauty Owners')).toBeInTheDocument();
    const postCall = fetchMock.mock.calls.find((call) => String(call[0]).endsWith('/community-sources') && String(call[1]?.method) === 'POST');
    expect(postCall).toBeTruthy();
    expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({ url: 'https://t.me/beauty_owners', interval_hours: 24 });
  });

  it('previews subscription removal instead of calling DELETE directly', async () => {
    const calls: Array<{ url: string; method: string }> = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = String(init?.method || 'GET');
      calls.push({ url, method });
      if (url === '/api/business/business-1/community-sources' && method === 'GET') {
        return response({ items: [{ id: 'source-1', title: 'Beauty Owners', canonical_url: 'https://t.me/beauty', sync_status: 'ready', topics_json: ['Маркетинг'], schedule_json: { interval_hours: 24 } }] });
      }
      if (url === '/api/operator/mobile/actions/preview' && method === 'POST') {
        return response({ success: true, preview: { action_id: 'action-1', capability: 'community_sources.unsubscribe', objects: [{ id: 'source-1', business_name: 'Точка' }], target_businesses: [{ id: 'business-1', name: 'Точка' }], changes: [{ object_id: 'source-1', label: 'Перестать следить: Beauty Owners' }] } });
      }
      return response({ success: true, operator_result: { status: 'completed', source_id: 'source-1' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<CommunitySourcesMobileModule businessId="business-1" />);
    await user.click(await screen.findByRole('button', { name: 'Настроить' }));
    await user.click(screen.getByRole('button', { name: 'Не отслеживать' }));
    const dialog = await screen.findByRole('dialog', { name: 'Перестать следить?' });
    await user.click(within(dialog).getByRole('button', { name: 'Не отслеживать' }));

    expect(calls.some((call) => call.url === '/api/operator/mobile/actions/preview' && call.method === 'POST')).toBe(true);
    expect(calls.some((call) => call.url.includes('/community-sources/source-1') && call.method === 'DELETE')).toBe(false);

    const previewDialog = await screen.findByRole('dialog', { name: 'Проверьте действие' });
    await user.click(within(previewDialog).getByRole('button', { name: 'Не отслеживать' }));

    expect(calls.some((call) => call.url === '/api/operator/mobile/actions/action-1/confirm' && call.method === 'POST')).toBe(true);
    expect(screen.queryByText('Beauty Owners')).not.toBeInTheDocument();
  });
});
