import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { FinanceDailyPanel } from './FinanceDailyPanel';
const request = vi.hoisted(() => vi.fn());
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: request } }));
afterEach(() => { cleanup(); request.mockReset(); });
const report = { enabled: true, settings: { currency: 'EUR', timezone: 'Europe/Tallinn' }, days: [], currencies: { EUR: { revenue: 350, refunds: 20, net_revenue: 330, checks: 10, upsell_checks: 2, average_check: 35, upsell_share: 20, expenses: null } } };
it('shows gross, refunds and average separately without inventing missing expenses', async () => {
  request.mockResolvedValue(report);
  render(<MemoryRouter><FinanceDailyPanel businessId="b" onActive={vi.fn()} /></MemoryRouter>);
  expect(await screen.findByText('330')).toBeVisible();
  expect(screen.getByText('35')).toBeVisible();
  expect(screen.getByText('Не указано')).toBeVisible();
  expect(screen.queryByText(/₽/)).not.toBeInTheDocument();
});
it('ignores a late result from the previous business', async () => {
  let resolveOld: (value: unknown) => void = () => {};
  request.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; })).mockResolvedValue({ ...report, currencies: { USD: { revenue: 700 } } });
  const active = vi.fn();
  const view = render(<MemoryRouter><FinanceDailyPanel businessId="old" onActive={active} /></MemoryRouter>);
  await waitFor(() => expect(request).toHaveBeenCalled());
  view.rerender(<MemoryRouter><FinanceDailyPanel businessId="new" onActive={active} /></MemoryRouter>);
  expect(await screen.findByText('700')).toBeVisible();
  resolveOld(report);
  await waitFor(() => expect(screen.queryByText('350')).not.toBeInTheDocument());
});
