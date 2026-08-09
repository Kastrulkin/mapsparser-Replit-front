import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import FinanceCrmMobilePanel from './FinanceCrmMobilePanel';

const response = (data: Record<string, unknown>) => Promise.resolve(new Response(JSON.stringify(data), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

describe('FinanceCrmMobilePanel', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows real CRM providers and keeps credentials inside the finance flow', async () => {
    vi.stubGlobal('fetch', vi.fn(() => response({
      success: true,
      providers: [
        { provider: 'mock_demo', label: 'Demo CRM', status: 'available', requires_auth: false },
        { provider: 'yclients', label: 'YCLIENTS', status: 'available', requires_auth: true, description: 'Записи и оплаты', connection: null },
      ],
    })));

    render(<FinanceCrmMobilePanel businessId="business-1" onSynced={vi.fn()} />);

    expect(await screen.findByText('YCLIENTS')).toBeInTheDocument();
    expect(screen.queryByText('Demo CRM')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /YCLIENTS/ }));
    await waitFor(() => expect(screen.getByLabelText('ID филиала YCLIENTS')).toBeVisible());
    expect(screen.getByRole('button', { name: 'Подключить YCLIENTS' })).toBeVisible();
  });

  it('previews a CRM import before exposing the single confirmation', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/providers')) return response({ success: true, providers: [{ provider: 'altegio', label: 'Altegio', status: 'available', requires_auth: true, connection: { status: 'connected', sync_status: 'never_synced' } }] });
      if (url.includes('/preview')) return response({ success: true, provider: 'altegio', preview_token: 'preview-1', period: { start_date: '2026-08-09', end_date: '2026-08-09' }, rows_total: 8, valid_rows: 7, failed_rows: 1, preview_rows: [{ service: 'Стрижка', amount: 1000 }] });
      return response({ success: true });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FinanceCrmMobilePanel businessId="business-1" onSynced={vi.fn()} />);

    await userEvent.click(await screen.findByRole('button', { name: /Altegio/ }));
    expect(screen.queryByRole('button', { name: /Подтвердить/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Проверить данные' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Подтвердить 7' })).toBeVisible());
    expect(screen.getByText('Стрижка · 1000')).toBeVisible();
  });
});
