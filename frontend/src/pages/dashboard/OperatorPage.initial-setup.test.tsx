import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { InitialSetupMenuResult } from '@/components/initial-setup/InitialBusinessSetup';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { OperatorPage } from './OperatorPage';

vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));

const businessId = 'pilot-jinlian';
const endpoint = '/operator/initial-setup/' + businessId;
const setup = {
  business_id: businessId, revision: 3, can_edit: true, origin: 'staff',
  provisional: false, profile: { name: 'Jinlian Vegan Ice Cream', city: 'Bangkok' },
  started: true, saved: false, seo_prepared: true, seo_dirty: false,
  sources: [{ key: 'map', url: 'https://yandex.com/maps/org/fixture/123456', kind: 'map', provider: 'yandex', status: 'ready', competitor: false, service_count: 1 }],
  services: [{
    key: 'service', original: 'Vegan ice cream', description: 'Wholesale orders',
    proposed: 'Vegan ice cream — Bangkok', proposed_description: 'Wholesale orders in Bangkok',
    keywords: [{ text: 'Vegan ice cream Bangkok', views: 140, source: 'Wordstat', dated: '2026-11-01' }],
  }],
  category_keywords: [], comparisons: [], facts: [], profile_choices: [], activity: [],
};

it('routes the existing chat composer to the selected company and opens the same results through the menu', async () => {
  let state = setup;
  vi.mocked(api.get).mockImplementation(async path => ({
    data: path === endpoint ? { available: true, setup: state } : { messages: [], conversation: null },
  }));
  vi.mocked(api.post).mockImplementation(async () => {
    state = {
      ...state, revision: 4,
      activity: [{ message: 'Вид деятельности: Веганское мороженое', reply: 'Вид деятельности сохранён.', at: '2026-11-22T10:00:00Z' }],
    };
    return { data: { available: true, setup: state } };
  });
  function Context() {
    return <Outlet context={{ currentBusinessId: businessId, currentBusiness: { id: businessId, name: setup.profile.name } }} />;
  }

  const view = render(<MemoryRouter initialEntries={['/dashboard/operator?setup=1&business_id=' + businessId]}>
    <LanguageProvider><Routes><Route element={<Context />}><Route path="/dashboard/operator" element={<OperatorPage />} /></Route></Routes></LanguageProvider>
  </MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'Первичная настройка компании' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Провести SEO-аудит сайта' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Семантическое ядро' })).toHaveAttribute('href', '/dashboard/card?tab=keywords&business_id=' + businessId);
  const input = screen.getByRole('textbox', { name: 'Сообщение для первичной настройки' });
  fireEvent.change(input, { target: { value: 'Вид деятельности: Веганское мороженое' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(endpoint, {
    action: 'message', message: 'Вид деятельности: Веганское мороженое', revision: 3,
  }));
  expect(await screen.findByText('Вид деятельности сохранён.')).toBeInTheDocument();
  view.unmount();

  render(<MemoryRouter><InitialSetupMenuResult businessId={businessId} section="keywords" /></MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'Семантическое ядро компании' })).toBeInTheDocument();
  expect(screen.getByText('Vegan ice cream Bangkok')).toBeInTheDocument();
});

it('refreshes a previously read site and shows the page and proposed SEO fix', async () => {
  const site = 'https://example.com/';
  const website = {
    key: 'site', url: site, kind: 'website', provider: 'website', status: 'ready', competitor: false, service_count: 0,
  };
  const state = { ...setup, sources: [website], saved: true };
  const audited = {
    ...website, website_audit: { status: 'ready', checked_at: '2026-11-22T10:00:00Z', pages: [
      { url: site, findings: [{ rule: 'core-title-present', priority: 'fix', title: 'Отсутствует заголовок страницы', fix: 'Добавьте уникальный title.' }] },
    ] },
  };
  let queued = false;
  vi.mocked(api.get).mockImplementation(async path => ({
    data: path === endpoint ? { available: true, setup: queued ? { ...state, sources: [audited] } : state }
      : { messages: [], conversation: null },
  }));
  vi.mocked(api.post).mockImplementation(async () => {
    queued = true;
    return { data: { available: true, setup: {
      ...state, revision: 4, sources: [{ ...website, website_audit: { status: 'queued' } }],
    } } };
  });
  function Context() {
    return <Outlet context={{ currentBusinessId: businessId, currentBusiness: { id: businessId, name: setup.profile.name } }} />;
  }

  render(<MemoryRouter initialEntries={['/dashboard/operator?setup=1&business_id=' + businessId]}>
    <LanguageProvider><Routes><Route element={<Context />}><Route path="/dashboard/operator" element={<OperatorPage />} /></Route></Routes></LanguageProvider>
  </MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Провести SEO-аудит сайта' }));
  await waitFor(() => expect(api.post).toHaveBeenLastCalledWith(endpoint, {
    action: 'website_audit', key: 'site', revision: 3,
  }));
  expect(await screen.findByText('SEO-проверка в очереди')).toBeInTheDocument();
  fireEvent.click(await screen.findByText('SEO-аудит сайта · Рекомендаций: 1', {}, { timeout: 4000 }));
  expect(screen.getByRole('link', { name: site })).toBeVisible();
  expect(screen.getByText('Добавьте уникальный title.')).toBeVisible();
});
