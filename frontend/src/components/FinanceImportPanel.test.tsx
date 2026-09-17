import '@testing-library/jest-dom/vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import FinanceImportPanel from './FinanceImportPanel';

const response = (payload: object) => Promise.resolve({ json: () => Promise.resolve(payload) });

const deferredResponse = () => {
  let resolveResponse: ((value: { json: () => Promise<object> }) => void) | null = null;
  const promise = new Promise<{ json: () => Promise<object> }>((resolve) => {
    resolveResponse = resolve;
  });

  return {
    promise,
    resolve: (payload: object) => {
      if (resolveResponse) {
        resolveResponse({ json: () => Promise.resolve(payload) });
      }
    },
  };
};

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

  it('ignores a preview that finishes after the business scope changes', async () => {
    const previewA = deferredResponse();
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url === '/api/finance/imports?business_id=business-a') return response({ success: true, imports: [] });
      if (url === '/api/finance/imports?business_id=business-b') return response({ success: true, imports: [] });
      if (url === '/api/finance/import-templates') return response({ success: true, templates: {} });
      if (url === '/api/finance/import-preview?business_id=business-a' && options?.method === 'POST') return previewA.promise;
      return response({ success: true });
    });
    vi.stubGlobal('fetch', fetchMock);

    const view = render(<FinanceImportPanel currentBusinessId="business-a" />);
    const file = new File(['date,amount\n2026-08-11,1200'], 'business-a.csv', { type: 'text/csv' });
    await userEvent.upload(screen.getByLabelText('Файл из CRM'), file);
    await userEvent.click(screen.getByRole('button', { name: 'Проверить файл' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/finance/import-preview?business_id=business-a',
      expect.objectContaining({ method: 'POST' }),
    ));

    view.rerender(<FinanceImportPanel currentBusinessId="business-b" />);
    await act(async () => {
      previewA.resolve({
        success: true,
        rows_total: 1,
        valid_rows: 1,
        failed_rows: 0,
        mapping: { amount: 'amount' },
        preview: [{ amount: 1200 }],
        errors: [],
      });
    });

    expect(screen.getByText('Если названия колонок незнакомы, после проверки файла их можно сопоставить вручную.')).toBeVisible();
    expect(screen.queryByText('Сопоставление колонок')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Импортировать проверенные строки' })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalledWith(
      '/api/finance/import-file?business_id=business-b',
      expect.anything(),
    );
  });

  it('clears a completed preview and import history when the business changes', async () => {
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url === '/api/finance/imports?business_id=business-a') {
        return response({
          success: true,
          imports: [{
            id: 'import-a',
            status: 'completed',
            file_name: 'business-a-history.csv',
            rows_total: 1,
            rows_imported: 1,
            rows_skipped: 0,
            rows_failed: 0,
            created_at: '2026-09-18',
          }],
        });
      }
      if (url === '/api/finance/imports?business_id=business-b') return response({ success: true, imports: [] });
      if (url === '/api/finance/import-templates') return response({ success: true, templates: {} });
      if (url === '/api/finance/import-preview?business_id=business-a' && options?.method === 'POST') {
        return response({
          success: true,
          rows_total: 1,
          valid_rows: 1,
          failed_rows: 0,
          mapping: { amount: 'amount' },
          preview: [{ amount: 1200 }],
          errors: [],
        });
      }
      return response({ success: true });
    });
    vi.stubGlobal('fetch', fetchMock);

    const view = render(<FinanceImportPanel currentBusinessId="business-a" />);
    expect(await screen.findByText('business-a-history.csv')).toBeVisible();
    await userEvent.upload(
      screen.getByLabelText('Файл из CRM'),
      new File(['amount\n1200'], 'business-a.csv', { type: 'text/csv' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Проверить файл' }));
    expect(await screen.findByText('Сопоставление колонок')).toBeVisible();

    view.rerender(<FinanceImportPanel currentBusinessId="business-b" />);

    expect(screen.queryByText('business-a-history.csv')).not.toBeInTheDocument();
    expect(screen.queryByText('Сопоставление колонок')).not.toBeInTheDocument();
    expect(screen.getByText('Если названия колонок незнакомы, после проверки файла их можно сопоставить вручную.')).toBeVisible();
    expect(screen.getByLabelText('Файл из CRM')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Импортировать проверенные строки' })).toBeDisabled();
  });

  it('clears the native file input after import so the same file can be checked again', async () => {
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url === '/api/finance/imports?business_id=business-a') return response({ success: true, imports: [] });
      if (url === '/api/finance/import-templates') return response({ success: true, templates: {} });
      if (url === '/api/finance/import-preview?business_id=business-a' && options?.method === 'POST') {
        return response({
          success: true,
          rows_total: 1,
          valid_rows: 1,
          failed_rows: 0,
          mapping: { amount: 'amount' },
          preview: [{ amount: 1200 }],
          errors: [],
        });
      }
      if (url === '/api/finance/import-file?business_id=business-a' && options?.method === 'POST') {
        return response({ success: true, rows_imported: 1, rows_skipped: 0, rows_failed: 0 });
      }
      return response({ success: true });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FinanceImportPanel currentBusinessId="business-a" />);
    const input = screen.getByLabelText('Файл из CRM');
    const file = new File(['amount\n1200'], 'same-file.csv', { type: 'text/csv' });
    await userEvent.upload(input, file);
    await userEvent.click(screen.getByRole('button', { name: 'Проверить файл' }));
    await screen.findByText('Сопоставление колонок');
    await userEvent.click(screen.getByRole('button', { name: 'Импортировать проверенные строки' }));
    expect(await screen.findByText(/Импортировано: 1/)).toBeVisible();
    expect(input).toHaveValue('');

    await userEvent.upload(input, file);
    await userEvent.click(screen.getByRole('button', { name: 'Проверить файл' }));
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/finance/import-preview?business_id=business-a',
      expect.objectContaining({ method: 'POST' }),
    ));
  });
});
