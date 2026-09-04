import '@testing-library/jest-dom/vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PartnershipsMobileModule } from './PartnershipsMobileModule';

const response = (payload: unknown) => Promise.resolve(new Response(JSON.stringify(payload), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

describe('PartnershipsMobileModule destructive actions', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows the complete safe catalog and shortlist without loading private workflow data', async () => {
    const calls: string[] = [];
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      if (url.startsWith('/api/partnership/leads?')) {
        return response({
          count: 42,
          items: [{ id: 'lead-preview-1', name: 'Публичный партнёр', city: 'Москва', rating: 4.8, reviews_count: 120 }],
          access: { allowed: false, required_tier_name: 'Привлечение' },
          preview: { limited: false, visible_limit: 200, hidden_count: 0, required_tier_name: 'Привлечение' },
        });
      }
      if (url === '/api/partnership/leads/lead-preview-1/shortlist') return response({ success: true, catalog_shortlisted: true });
      return response({ success: false, error: 'private_endpoint_must_not_be_called' });
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<PartnershipsMobileModule scope={{ kind: 'business', id: 'business-1' }} />);

    expect(await screen.findByText('Выберите партнёров с похожей аудиторией')).toBeInTheDocument();
    expect(screen.getByText('Публичный партнёр')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Подготовить сообщения/ })).toHaveAttribute('href', expect.stringContaining('screen%3Dpartnerships'));
    await user.click(screen.getByRole('button', { name: 'Добавить' }));
    expect(await screen.findByRole('button', { name: 'В shortlist' })).toBeInTheDocument();
    expect(calls).toEqual(expect.arrayContaining(['/api/partnership/leads/lead-preview-1/shortlist']));
    expect(calls.filter((url) => !url.includes('/shortlist'))).toHaveLength(1);
  });

  it('creates an Operator preview before deleting a partnership candidate', async () => {
    const calls: Array<{ url: string; method: string }> = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = String(init?.method || 'GET');
      calls.push({ url, method });
      if (url.startsWith('/api/partnership/leads?')) {
        return response({ items: [{ id: 'lead-1', name: 'Партнёр один', city: 'Москва', pipeline_status: 'unprocessed' }] });
      }
      if (url.startsWith('/api/partnership/drafts')) return response({ drafts: [] });
      if (url.startsWith('/api/partnership/send-batches')) return response({ batches: [] });
      if (url.startsWith('/api/partnership/analytics/funnel')) return response({ funnel: [], summary: {} });
      if (url.startsWith('/api/partnership/analytics/outcomes')) return response({ summary: {} });
      if (url.startsWith('/api/partnership/analytics/source-quality')) return response({ items: [] });
      if (url.startsWith('/api/partnership/analytics/blockers')) return response({ blockers: [] });
      return response({ success: true });
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<PartnershipsMobileModule scope={{ kind: 'business', id: 'business-1' }} />);
    await user.click(await screen.findByRole('button', { name: 'Кандидаты' }));
    await user.click(await screen.findByRole('button', { name: /Партнёр один/ }));
    await user.click(screen.getByRole('button', { name: 'Удалить кандидата' }));

    expect(calls.some((call) => call.url === '/api/operator/mobile/actions/preview' && call.method === 'POST')).toBe(true);
    expect(calls.some((call) => call.url.includes('/api/partnership/leads/lead-1') && call.method === 'DELETE')).toBe(false);
  });

  it('keeps the digital room inside the current Mini App WebView', async () => {
    const openWindow = vi.spyOn(window, 'open').mockImplementation(() => null);
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith('/api/partnership/leads?')) return response({ items: [{ id: 'lead-1', name: 'Партнёр один', city: 'Москва', pipeline_status: 'unprocessed', sales_room_slug: 'partner-room' }] });
      if (url.startsWith('/api/partnership/drafts')) return response({ drafts: [] });
      if (url.startsWith('/api/partnership/send-batches')) return response({ batches: [] });
      return response({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<PartnershipsMobileModule scope={{ kind: 'business', id: 'business-1' }} />);
    await user.click(await screen.findByRole('button', { name: 'Кандидаты' }));
    await user.click(await screen.findByRole('button', { name: /Партнёр один/ }));
    await user.click(screen.getByRole('button', { name: 'Открыть цифровую комнату' }));

    expect(openWindow).not.toHaveBeenCalled();
  });

  it('previews draft deletion instead of sending DELETE after a browser confirm', async () => {
    const calls: Array<{ url: string; method: string }> = [];
    let draftDeleted = false;
    const browserConfirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = String(init?.method || 'GET');
      calls.push({ url, method });
      if (url.startsWith('/api/partnership/leads?')) return response({ items: [] });
      if (url.startsWith('/api/partnership/drafts?')) return response({ drafts: draftDeleted ? [] : [{ id: 'draft-1', lead_id: 'lead-1', lead_name: 'Партнёр один', channel: 'email', status: 'draft', generated_text: 'Предложение' }] });
      if (url.startsWith('/api/partnership/send-batches')) return response({ batches: [], ready_drafts: [], reactions: [] });
      if (url === '/api/operator/mobile/actions/preview' && method === 'POST') return response({ success: true, preview: { action_id: 'draft-action-1', capability: 'partnerships.draft.delete', objects: [{ id: 'draft-1', business_name: 'Точка' }], target_businesses: [{ id: 'business-1', name: 'Точка' }], changes: [{ object_id: 'draft-1', label: 'Удалить черновик для Партнёр один' }] } });
      if (url === '/api/operator/mobile/actions/draft-action-1/confirm' && method === 'POST') { draftDeleted = true; return response({ success: true, operator_result: { status: 'completed', draft_id: 'draft-1' } }); }
      return response({ success: true });
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<PartnershipsMobileModule scope={{ kind: 'business', id: 'business-1' }} />);
    await user.click(await screen.findByRole('button', { name: 'Письма' }));
    await user.click(await screen.findByRole('button', { name: 'Удалить черновик' }));

    expect(calls.some((call) => call.url === '/api/operator/mobile/actions/preview' && call.method === 'POST')).toBe(true);
    expect(calls.some((call) => call.url.includes('/api/partnership/drafts/draft-1') && call.method === 'DELETE')).toBe(false);
    expect(browserConfirm).not.toHaveBeenCalled();

    const previewDialog = await screen.findByRole('dialog', { name: 'Проверьте действие' });
    await user.click(within(previewDialog).getByRole('button', { name: 'Удалить черновик' }));

    expect(calls.some((call) => call.url === '/api/operator/mobile/actions/draft-action-1/confirm' && call.method === 'POST')).toBe(true);
    expect(screen.queryByText('Партнёр один')).not.toBeInTheDocument();
  });

  it('does not expose Invalid Date for a malformed send batch timestamp', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith('/api/partnership/leads?')) return response({ items: [] });
      if (url.startsWith('/api/partnership/drafts?')) return response({ drafts: [] });
      if (url.startsWith('/api/partnership/send-batches')) return response({ batches: [{ id: 'batch-1', status: 'draft', created_at: 'not-a-date', items: [] }], ready_drafts: [], reactions: [] });
      return response({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<PartnershipsMobileModule scope={{ kind: 'business', id: 'business-1' }} />);
    await user.click(await screen.findByRole('button', { name: 'Отправка' }));

    expect(await screen.findByText(/Пакет от/)).toBeInTheDocument();
    expect(screen.queryByText(/Invalid Date/i)).not.toBeInTheDocument();
    expect(screen.getByText(/дата неизвестна/i)).toBeInTheDocument();
  });

  it('does not present a historical reconciliation marker as the recipient-visible email body', async () => {
    const historicalMarker = 'Историческая запись: письмо отправлено вручную 25.08.2026 с localosgo@gmail.com; факт подтверждён в папке «Отправленные». Точный текст хранится у почтового провайдера и не подменяется шаблоном LocalOS.';
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith('/api/partnership/leads?')) return response({ items: [] });
      if (url.startsWith('/api/partnership/drafts?')) {
        return response({
          drafts: [{
            id: 'historical-draft-1',
            lead_id: 'lead-1',
            lead_name: 'Гимназия 61',
            channel: 'email',
            status: 'approved',
            approved_text: historicalMarker,
          }],
        });
      }
      if (url.startsWith('/api/partnership/send-batches')) return response({ batches: [], ready_drafts: [], reactions: [] });
      return response({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<PartnershipsMobileModule scope={{ kind: 'business', id: 'business-1' }} />);
    await user.click(await screen.findByRole('button', { name: 'Письма' }));

    expect(screen.queryByDisplayValue(historicalMarker)).not.toBeInTheDocument();
    expect(screen.getByText('Письмо отправлено вручную. Фактический текст сохранён в Gmail.')).toBeInTheDocument();
  });
});
