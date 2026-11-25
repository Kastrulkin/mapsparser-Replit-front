import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { InitialSetupChat, useInitialBusinessSetup } from '@/components/initial-setup/InitialBusinessSetup';
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

  render(<MemoryRouter initialEntries={['/dashboard/operator?setup=1&business_id=' + businessId]}>
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
  fireEvent.click(screen.getByText('Семантическое ядро', { selector: 'summary' }));
  fireEvent.click(screen.getByText('Vegan ice cream', { selector: 'summary' }));
  expect(screen.getByText('Vegan ice cream Bangkok')).toBeVisible();
});

it('opens the staged setup progress after an explicit setup command with a map link', async () => {
  window.localStorage.clear();
  const queued = {
    ...setup,
    started: true,
    seo_prepared: false,
    sources: setup.sources.map(source => ({ ...source, status: 'queued' })),
  };
  vi.mocked(api.get).mockImplementation(async path => ({
    data: path === endpoint ? { available: true, setup: queued } : { messages: [], conversation: null },
  }));
  vi.mocked(api.post).mockImplementation(async path => ({
    data: path === '/operator/chat' ? {
      conversation_id: 'setup-conversation',
      operator_result: {
        status: 'queued', capability: 'business.initial_setup', credit_charged: false,
        chat_response: 'Первичная настройка начата.',
      },
    } : { available: true, setup: queued },
  }));
  function Context() {
    return <Outlet context={{ currentBusinessId: businessId, currentBusiness: { id: businessId, name: setup.profile.name }, user: { is_superadmin: true } }} />;
  }

  render(<MemoryRouter initialEntries={['/dashboard/operator?business_id=' + businessId]}>
    <LanguageProvider><Routes><Route element={<Context />}><Route path="/dashboard/operator" element={<OperatorPage />} /></Route></Routes></LanguageProvider>
  </MemoryRouter>);
  const input = await screen.findByRole('textbox', { name: 'Задача для Оператора' });
  const command = 'https://yandex.ru/maps/org/mimika/236225549064/ Добавь компанию, проведи первичную настройку';
  fireEvent.change(input, { target: { value: command } });
  fireEvent.keyDown(input, { key: 'Enter' });

  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/operator/chat', expect.objectContaining({
    business_id: businessId,
    message: command,
  })));
  expect(await screen.findByRole('heading', { name: 'Первичная настройка компании' })).toBeVisible();
  expect(screen.getByText('Сбор по источникам', { selector: 'li' })).toHaveAttribute('aria-current', 'step');
  expect(screen.getByText('Читаем источники. Можно вернуться позже.')).toBeVisible();
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

it('reviews new and existing services in the same list and only shows original details when available', async () => {
  const existing = { ...setup.services[0], has_original: true, service_id: 'existing' };
  const added = {
    ...setup.services[0], key: 'new', has_original: false, service_id: 'created-by-setup',
    original: 'Черновое название', description: 'Первичное описание',
    proposed: 'Пошив мерча на заказ', proposed_description: 'Шьём худи и футболки для компаний.',
  };
  const state = { ...setup, services: [existing, added] };
  vi.mocked(api.get).mockResolvedValue({ data: { available: true, setup: state } });
  vi.mocked(api.post).mockClear();
  function SetupChat() {
    const initialSetup = useInitialBusinessSetup(businessId, true);
    return <InitialSetupChat setup={initialSetup} isStaff={false} onExit={() => {}} />;
  }
  render(<MemoryRouter><SetupChat /></MemoryRouter>);
  fireEvent.click(await screen.findByText('Услуги и предложенные изменения · 2'));

  const newRow = await screen.findByRole('button', { name: 'Пошив мерча на заказ Новая услуга' });
  expect(screen.queryByText(added.proposed_description)).not.toBeInTheDocument();
  fireEvent.click(newRow);
  const dialog = within(screen.getByRole('region', { name: added.proposed }));
  expect(dialog.getByText(added.proposed_description)).toBeVisible();
  expect(dialog.queryByText('Текущее описание')).not.toBeInTheDocument();
  expect(dialog.queryByRole('button', { name: 'Оставить исходную' })).not.toBeInTheDocument();
  expect(dialog.queryByRole('textbox')).not.toBeInTheDocument();
  expect(api.post).not.toHaveBeenCalled();

  fireEvent.click(dialog.getByRole('button', { name: 'Изменить' }));
  expect(dialog.getByRole('textbox', { name: 'Описание' })).toHaveValue(added.proposed_description);
  expect(dialog.queryByText(added.proposed_description, { selector: 'p' })).not.toBeInTheDocument();
  const editedName = 'Пошив мерча для компаний';
  fireEvent.change(dialog.getByRole('textbox', { name: 'Название' }), { target: { value: editedName } });
  vi.mocked(api.post).mockRejectedValueOnce({ response: { data: { error: 'Повторите сохранение.' } } });
  fireEvent.click(dialog.getByRole('button', { name: 'Сохранить вариант' }));
  expect(await dialog.findByRole('alert')).toHaveTextContent('Повторите сохранение.');
  expect(dialog.getByRole('textbox', { name: 'Название' })).toHaveValue(editedName);

  vi.mocked(api.post).mockResolvedValueOnce({ data: { available: true, setup: {
    ...state, revision: 4, services: [existing, { ...added, accepted: true, proposed: editedName }],
  } } });
  fireEvent.click(dialog.getByRole('button', { name: 'Сохранить вариант' }));
  const savedRow = await screen.findByRole('button', { name: `${editedName} Сохранено` });
  expect(api.post).toHaveBeenLastCalledWith(endpoint, {
    action: 'service', key: 'new', revision: 3, name: editedName, description: added.proposed_description,
  });
  await waitFor(() => expect(savedRow).toHaveFocus());

  const existingRow = screen.getByRole('button', { name: 'Vegan ice cream На проверке' });
  fireEvent.click(existingRow);
  expect(existingRow).toHaveAttribute('aria-pressed', 'true');
  const edit = within(screen.getByRole('region', { name: existing.original }));
  expect(edit.getByText('Текущее описание')).toBeVisible();
  expect(edit.getByText(existing.description)).toBeVisible();
  expect(edit.getByText(existing.proposed_description)).toBeVisible();
  expect(edit.getByRole('button', { name: 'Оставить исходную' })).toBeVisible();
  fireEvent.click(edit.getByRole('button', { name: 'Закрыть карточку услуги' }));
  expect(existingRow).toHaveFocus();
  expect(existingRow).toHaveAttribute('aria-pressed', 'false');
});

it('uses the same compact service list for saved SEO suggestions in the work chat', async () => {
  vi.mocked(api.post).mockClear();
  vi.mocked(api.get).mockResolvedValue({ data: { conversation: null, messages: [{
    id: 'service-suggestions', role: 'operator', content: 'Подготовлено одно предложение.\nМассаж → Массаж лица',
    result_json: { status: 'completed', optimization_job: { id: 'job' }, service_suggestions: [{
      id: 'suggestion', before_name: 'Массаж', before_description: 'Прежнее описание.',
      optimized_name: 'Массаж лица', seo_description: 'Лимфодренажный массаж лица.',
    }] },
  }] } });
  function Context() {
    return <Outlet context={{ currentBusinessId: businessId, currentBusiness: { id: businessId, name: setup.profile.name } }} />;
  }
  render(<MemoryRouter initialEntries={['/dashboard/operator']}>
    <LanguageProvider><Routes><Route element={<Context />}><Route path="/dashboard/operator" element={<OperatorPage />} /></Route></Routes></LanguageProvider>
  </MemoryRouter>);

  const proposal = await screen.findByRole('button', { name: 'Массаж На проверке' });
  expect(screen.queryByText('Массаж → Массаж лица')).not.toBeInTheDocument();
  expect(screen.queryByText('Лимфодренажный массаж лица.')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Применить предложения' })).toBeVisible();
  fireEvent.click(proposal);
  const detail = within(screen.getByRole('region', { name: 'Массаж' }));
  expect(detail.getByText('Лимфодренажный массаж лица.')).toBeVisible();
  expect(detail.getByText('Прежнее описание.')).toBeVisible();
  expect(api.post).not.toHaveBeenCalled();
});

it('shows the linked shortlist and offers to label an unclassified photo', async () => {
  const map = 'https://yandex.com/maps/org/fixture/123456';
  const image = 'https://avatars.mds.yandex.net/get-altay/123/facade/XXXL';
  const state = { ...setup, photo_report: {
    status: 'ready', library_count: 0, library_categories: [],
    cover: 'Фасад', rejected: 0, checked_at: '2026-11-22T10:00:00Z',
    shortlist: [{ key: 'photo', label: 'Фасад', source_url: map, image_url: image }],
    missing: [{ label: 'Вход и ориентиры', tip: 'Снимите дверь крупным планом.' }],
    sources: [{ url: map, provider: 'yandex', status: 'sample', count: 2 }],
    review: [{ key: 'candidate', image_url: 'https://avatars.mds.yandex.net/get-altay/123/candidate/XXXL', provider: 'yandex' }],
  } };
  vi.mocked(api.get).mockImplementation(async path => ({
    data: path === endpoint ? { available: true, setup: state } : { messages: [], conversation: null },
  }));
  vi.mocked(api.post).mockResolvedValue({
    data: { available: true, setup: { ...state, photo_report: { status: 'queued' } } },
  });
  function Context() {
    return <Outlet context={{ currentBusinessId: businessId, currentBusiness: { id: businessId, name: setup.profile.name } }} />;
  }
  render(<MemoryRouter initialEntries={['/dashboard/operator?setup=1&business_id=' + businessId]}>
    <LanguageProvider><Routes><Route element={<Context />}><Route path="/dashboard/operator" element={<OperatorPage />} /></Route></Routes></LanguageProvider>
  </MemoryRouter>);
  fireEvent.click(await screen.findByText('Фото для карт и отчёт · Готов'));
  expect(screen.getByText('Снимите дверь крупным планом.')).toBeVisible();
  expect(screen.getByRole('link', { name: 'Открыть медиатеку' })).toHaveAttribute('href', '/dashboard/content?tab=media&business_id=' + businessId);
  expect(screen.getByRole('link', { name: 'Фасад' })).toHaveAttribute('href', image);
  expect(screen.getByText(/подборка хранится как ссылки/i)).toBeVisible();
  expect(screen.getByText('Кандидат для обложки — фасад.')).toBeVisible();
  fireEvent.click(screen.getByText('Уточнить, что показано на фото · 1'));
  fireEvent.change(screen.getByRole('combobox', { name: 'Что показано на фото' }), { target: { value: 'entrance' } });
  fireEvent.click(screen.getByRole('button', { name: 'Добавить в подборку' }));
  await waitFor(() => expect(api.post).toHaveBeenLastCalledWith(endpoint, {
    action: 'photo_pick', key: 'candidate', category: 'entrance', revision: 3,
  }));
  expect(await screen.findByText('Проверяем снимки с карт и из медиатеки.')).toBeVisible();
});
