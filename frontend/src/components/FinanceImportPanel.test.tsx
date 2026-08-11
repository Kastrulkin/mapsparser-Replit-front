import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import FinanceImportPanel from './FinanceImportPanel';

const response = (payload: object) => Promise.resolve({ json: () => Promise.resolve(payload) });

describe('FinanceImportPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('requires confirmation for columns recognized by their values', async () => {
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url.startsWith('/api/finance/imports')) return response({ success: true, imports: [] });
      if (url === '/api/finance/import-templates') {
        return response({ success: true, templates: { manual: { label: 'Универсальный', description: 'Для выгрузки из CRM' } } });
      }
      if (url.startsWith('/api/finance/import-preview') && options?.method === 'POST') {
        return response({
          success: true,
          rows_total: 2,
          valid_rows: 2,
          failed_rows: 0,
          mapping: { date: 'Колонка A', amount: 'Колонка B' },
          mapping_details: [
            { target: 'date', source: 'Колонка A', confidence: 0.78, method: 'values' },
            { target: 'amount', source: 'Колонка B', confidence: 0.68, method: 'values' },
          ],
          needs_mapping_confirmation: true,
          unmapped_headers: ['Колонка C'],
          preview: [{ date: '2026-08-11', amount: 1200 }],
          errors: [],
        });
      }
      return response({ success: true });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FinanceImportPanel currentBusinessId="business-1" />);

    const file = new File(['Колонка A,Колонка B\n2026-08-11,1200'], 'crm.csv', { type: 'text/csv' });
    await userEvent.upload(screen.getByLabelText('Файл из CRM'), file);
    await userEvent.click(screen.getByRole('button', { name: 'Проверить файл' }));

    expect(await screen.findByText('Нужна быстрая проверка')).toBeVisible();
    expect(screen.getAllByText('Проверьте')).toHaveLength(2);
    expect(screen.getByText(/Это нормально/)).toHaveTextContent('Колонка C');
    expect(screen.getByRole('button', { name: 'Импортировать проверенные строки' })).toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: 'Всё верно, подтвердить' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Импортировать проверенные строки' })).toBeEnabled());
  });
});
