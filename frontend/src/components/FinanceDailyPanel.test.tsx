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
it('shows a reported month separately from daily totals and exposes its history', async () => {
  request.mockResolvedValue({...report,reported_period_totals:[{id:'period',period_start:'2026-09-01',period_end:'2026-09-30',currency:'EUR',version:1,values_json:{revenue:'50000',checks:'200'}}]});
  render(<MemoryRouter><FinanceDailyPanel businessId="b" onActive={vi.fn()}/></MemoryRouter>);
  expect(await screen.findByText('2026-09-01 — 2026-09-30 · EUR')).toBeVisible();
  expect(screen.getByText(/Они не распределены по дням/)).toBeVisible();
  expect(screen.getByRole('button',{name:'История итога за период'})).toBeInTheDocument();
  expect(screen.getByText('330')).toBeVisible();
});
it('keeps saved period totals visible after input is disabled', async () => {
  request.mockResolvedValue({enabled:false,settings:{currency:'EUR'},days:[],currencies:{},reported_period_totals:[{id:'period',period_start:'2026-09-01',period_end:'2026-09-30',currency:'EUR',version:1,values_json:{revenue:'50000'}}]});
  const active=vi.fn();
  render(<MemoryRouter><FinanceDailyPanel businessId="b" onActive={active}/></MemoryRouter>);
  expect(await screen.findByRole('region',{name:'Финансовые итоги'})).toBeInTheDocument();
  expect(active).toHaveBeenCalledWith(true);
});
