import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { FinancePage } from './FinancePage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

vi.mock('@/components/FinanceFirstStep', () => ({
  default: () => <div data-testid="finance-workspace" />,
}));

vi.mock('@/components/FinanceImportPanel', () => ({ default: () => null }));
vi.mock('@/components/FinanceThresholdsPanel', () => ({ default: () => null }));
vi.mock('@/components/FinancialMetrics', () => ({ default: () => null }));
vi.mock('@/components/ROICalculator', () => ({ default: () => null }));
vi.mock('@/components/TransactionTable', () => ({ default: () => null }));

const ContextRoute = () => <Outlet context={{ currentBusinessId: 'demo-business' }} />;

describe('FinancePage localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'de');
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ requests: [], data_health: null });
  });

  it('renders the finance page heading in German', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/finance']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route path="/dashboard/finance" element={<FinancePage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Finanzen' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Финансы' })).not.toBeInTheDocument();
  });
});
