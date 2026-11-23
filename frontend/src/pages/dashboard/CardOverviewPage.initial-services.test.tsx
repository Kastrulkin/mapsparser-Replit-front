import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { CardOverviewPage } from './CardOverviewPage';

vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));

const businessId = 'service-review-company';
const existing = {
  id: 'merch', name: 'Пошив мерча', description: 'Шьём мерч для компаний.',
  optimized_name: '',
  keywords: ['пошив мерча'], source: 'initial_setup',
};
const proposal = {
  key: 'merch-proposal', service_id: existing.id, has_original: false,
  original: existing.name, description: existing.description,
  proposed: 'Пошив мерча на заказ', proposed_description: 'Шьём мерч для компаний и мероприятий.',
  keywords: [], accepted: false,
};
const newProposal = {
  ...proposal, key: 'uniform', service_id: null, original: 'Униформа',
  proposed: 'Корпоративная униформа', proposed_description: 'Шьём униформу по заказу.',
};
const setup = {
  business_id: businessId, revision: 1, can_edit: true, services: [proposal, newProposal],
  profile: { city: 'Москва' }, sources: [],
};

function ContextRoute() {
  return <Outlet context={{
    user: { id: 'owner' }, currentBusinessId: businessId,
    currentBusiness: { id: businessId, name: 'Meliora', subscription_tier: 'starter', subscription_status: 'active' },
    businesses: [],
  }} />;
}

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

it('keeps one queue, opens a proposal from its catalogue row and removes the review action after saving', async () => {
  window.localStorage.setItem('language', 'ru');
  let catalogue = [existing];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const data = String(input).includes('/services/list') ? { success: true, services: catalogue } : { success: true };
    return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
  }));
  vi.mocked(api.get).mockResolvedValue({ data: { available: true, setup } });
  vi.mocked(api.post).mockImplementation(async () => {
    catalogue = [{ ...existing, optimized_name: proposal.proposed }];
    return { data: { available: true, setup: { ...setup, revision: 2, services: [{ ...proposal, accepted: true }, newProposal] } } };
  });
  render(<MemoryRouter initialEntries={['/dashboard/card?business_id=' + businessId]}>
    <LanguageProvider><Routes><Route element={<ContextRoute />}>
      <Route path="/dashboard/card" element={<CardOverviewPage />} />
    </Route></Routes></LanguageProvider>
  </MemoryRouter>);

  const newRow = await screen.findByRole('button', { name: /Корпоративная униформа/ });
  expect(newRow).toHaveTextContent('Новая услуга');
  expect(screen.getAllByText('Очередь услуг')).toHaveLength(1);
  expect(screen.getAllByRole('button', { name: /^Пошив мерча\s/ })).toHaveLength(1);
  fireEvent.click(newRow);
  expect(within(screen.getByRole('region', { name: newProposal.proposed })).getByRole('button', { name: 'Добавить в услуги' })).toBeVisible();

  fireEvent.click(screen.getByRole('button', { name: /^Пошив мерча\s/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Проверить предложение' }));
  const review = within(screen.getByRole('region', { name: existing.name }));
  expect(review.getByText(existing.description)).toBeVisible();
  expect(review.getByText(proposal.proposed_description)).toBeVisible();
  fireEvent.click(review.getByRole('button', { name: 'Сохранить вариант' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/operator/initial-setup/' + businessId, {
    action: 'service', key: proposal.key, revision: 1, name: proposal.proposed, description: proposal.proposed_description,
  }));
  expect(await screen.findByDisplayValue(proposal.proposed)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Проверить предложение' })).not.toBeInTheDocument();
  expect(screen.getAllByText('Очередь услуг')).toHaveLength(1);
});

it('shows the saved Wordstat frequency in the standard keyword tab without loading a second semantic core', async () => {
  window.localStorage.setItem('language', 'ru');
  const keyword = { id: 'wordstat-merch', keyword: 'мерч на заказ', views: 518, category: 'Wordstat · Москва', updated_at: '2026-09-30' };
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const data = String(input).includes('/wordstat/keywords')
      ? { success: true, items: [keyword], grouped: { [keyword.category]: [keyword] } }
      : { success: true };
    return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
  }));
  vi.mocked(api.get).mockResolvedValue({ data: { available: true, setup } });

  render(<MemoryRouter initialEntries={['/dashboard/card?business_id=' + businessId + '&tab=keywords']}>
    <LanguageProvider><Routes><Route element={<ContextRoute />}>
      <Route path="/dashboard/card" element={<CardOverviewPage />} />
    </Route></Routes></LanguageProvider>
  </MemoryRouter>);

  const row = await screen.findByRole('row', { name: /мерч на заказ/ });
  expect(within(row).getByText('518')).toBeVisible();
  expect(screen.queryByText('Семантическое ядро компании')).not.toBeInTheDocument();
  expect(api.get).not.toHaveBeenCalledWith('/operator/initial-setup/' + businessId, expect.anything());
});
