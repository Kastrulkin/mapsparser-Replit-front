import '@testing-library/jest-dom/vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { InitialSetupChat } from '@/components/initial-setup/InitialBusinessSetup';
import { useInitialBusinessSetup } from '@/components/initial-setup/useInitialBusinessSetup';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { OperatorPage } from './OperatorPage';

vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));

beforeEach(() => {
  vi.stubEnv('VITE_LOCALOS_INITIAL_SETUP_ENABLED', 'true');
  localStorage.setItem('language', 'ru');
});
afterEach(() => {
  vi.unstubAllEnvs();
  localStorage.removeItem('language');
});

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
  vi.stubEnv('VITE_LOCALOS_INITIAL_SETUP_ENABLED', 'false');
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
  expect(await screen.findByRole('heading', { name: 'Первичная настройка компании' }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Провести SEO-аудит сайта' })).not.toBeInTheDocument();
  const input = screen.getByRole('textbox', { name: 'Сообщение для первичной настройки' });
  fireEvent.change(input, { target: { value: 'Вид деятельности: Веганское мороженое' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(endpoint, {
    action: 'message', message: 'Вид деятельности: Веганское мороженое', revision: 3,
  }));
  const setupChat = await screen.findByRole('log', { name: 'Сообщения настройки' });
  expect(within(setupChat).getByText('Вид деятельности сохранён.')).toBeVisible();
  const setupCard = screen.getByRole('region', { name: 'Первичная настройка компании' });
  expect(screen.getAllByText('Вид деятельности сохранён.')).toHaveLength(1);
  expect(within(setupCard).getByRole('button', { name: 'Сохранить кабинет' })).toBeVisible();
  const queries = screen.getByText('Поисковые запросы');
  expect(screen.getByText('Семантическое ядро', { selector: 'a' })).not.toBeVisible();
  fireEvent.click(queries);
  expect(screen.getByRole('link', { name: 'Семантическое ядро' })).toHaveAttribute('href', '/dashboard/card?tab=keywords&business_id=' + businessId);
  fireEvent.click(screen.getByText('Vegan ice cream', { selector: 'summary > span' }));
  expect(screen.getByText('Vegan ice cream Bangkok')).toBeVisible();
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
  fireEvent.click(await screen.findByText('Услуги'));

  const newRow = await screen.findByRole('button', { name: 'Пошив мерча на заказ Новая услуга' });
  expect(screen.queryByText(added.proposed_description)).not.toBeInTheDocument();
  fireEvent.click(newRow);
  const dialog = within(screen.getByRole('region', { name: added.proposed }));
  expect(dialog.getByText(added.proposed_description)).toBeVisible();
  expect(dialog.queryByText('Текущее описание')).not.toBeInTheDocument();
  expect(dialog.queryByRole('button', { name: 'Оставить исходную' })).not.toBeInTheDocument();
  expect(dialog.queryByRole('textbox')).not.toBeInTheDocument();
  expect(api.post).not.toHaveBeenCalled();

  expect(dialog.queryByRole('button', { name: 'Добавить в услуги' })).not.toBeInTheDocument();
  fireEvent.click(dialog.getByRole('button', { name: 'Закрыть карточку услуги' }));
  expect(newRow).toHaveFocus();

  const existingRow = screen.getByRole('button', { name: 'Vegan ice cream На проверке' });
  fireEvent.click(existingRow);
  expect(existingRow).toHaveAttribute('aria-pressed', 'true');
  const edit = within(screen.getByRole('region', { name: existing.original }));
  expect(edit.getByText('Текущее описание')).toBeVisible();
  expect(edit.getByText(existing.description)).toBeVisible();
  expect(edit.getByText(existing.proposed_description)).toBeVisible();
  expect(edit.queryByRole('button', { name: 'Сохранить вариант' })).not.toBeInTheDocument();
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
  expect(await screen.findByText('Кабинет сохранён')).toBeVisible();
  expect(screen.getByText('Требуется SEO-проверка')).toBeVisible();
  expect(screen.getByText('1 услуга с предложениями')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Проверить черновик' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Провести SEO-аудит сайта' })).not.toBeVisible();
  fireEvent.click(screen.getByText('Сайт', { selector: 'summary > span' }));
  fireEvent.click(screen.getByRole('button', { name: 'Провести SEO-аудит сайта' }));
  await waitFor(() => expect(api.post).toHaveBeenLastCalledWith(endpoint, {
    action: 'website_audit', key: 'site', revision: 3,
  }));
  expect(await screen.findByText('Проверяю страницы…')).toBeVisible();
  expect(await screen.findByText('1 страница · 1 замечание', {}, { timeout: 4000 })).toBeVisible();
  expect(screen.getByRole('link', { name: site })).toBeVisible();
  expect(screen.getByText('Добавьте уникальный title.')).toBeVisible();
});

it('opens the existing setup steps when the server accepts a chat command', async () => {
  const queued = {
    ...setup,
    seo_prepared: false,
    sources: setup.sources.map(source => ({ ...source, status: 'queued' })),
  };
  vi.mocked(api.get).mockImplementation(async path => ({
    data: path === endpoint ? { available: true, setup: queued } : { messages: [], conversation: null },
  }));
  vi.mocked(api.post).mockResolvedValue({
    data: { operator_result: { status: 'queued', capability: 'business.initial_setup', chat_response: 'Первичная настройка начата.' } },
  });
  function Context() {
    const location = useLocation();
    return <><output aria-label="Текущий адрес">{location.search}</output><Outlet context={{
      currentBusinessId: businessId,
      currentBusiness: { id: businessId, name: setup.profile.name },
    }} /></>;
  }

  render(<MemoryRouter initialEntries={['/dashboard/operator?business_id=' + businessId]}>
    <LanguageProvider><Routes><Route element={<Context />}><Route path="/dashboard/operator" element={<OperatorPage />} /></Route></Routes></LanguageProvider>
  </MemoryRouter>);
  const input = await screen.findByRole('textbox', { name: 'Вопрос или поручение для LocalOS' });
  const command = 'Начни первичную настройку ' + setup.sources[0].url;
  fireEvent.change(input, { target: { value: command } });
  fireEvent.keyDown(input, { key: 'Enter' });

  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/operator/chat', expect.objectContaining({ business_id: businessId, message: command })));
  expect(await screen.findByRole('heading', { name: 'Первичная настройка компании' })).toBeVisible();
  await waitFor(() => expect(screen.getByLabelText('Текущий адрес')).toHaveTextContent('setup=1'));
});

it('shows the linked shortlist and offers to label an unclassified photo', async () => {
  const map = 'https://yandex.com/maps/org/fixture/123456';
  const image = 'https://avatars.mds.yandex.net/get-altay/123/facade/XXXL';
  const state = { ...setup, photo_report: {
    status: 'ready', library_count: 2, library_categories: ['Интерьер', 'Команда'],
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
  fireEvent.click(await screen.findByText('Фото для карт'));
  expect(screen.getByText('Интерьер', { selector: 'li' })).toBeVisible();
  expect(screen.getByText('Доснять')).toBeVisible();
  expect(screen.getByText('Снимите дверь крупным планом.')).toBeVisible();
  expect(screen.getByRole('link', { name: 'Открыть медиатеку' })).toHaveAttribute('href', '/dashboard/content?section=media&business_id=' + businessId);
  fireEvent.click(screen.getByText('Подборка с карт'));
  expect(screen.getByRole('link', { name: 'Фасад' })).toHaveAttribute('href', image);
  expect(screen.getByText('Обложка · Фасад')).toBeVisible();
  const sampled = screen.getByText('2 в выборке', { exact: false });
  expect(sampled).not.toBeVisible();
  fireEvent.click(screen.getByText('Проверка площадок'));
  expect(within(sampled).getByRole('link', { name: 'Яндекс Карты' })).toHaveAttribute('href', map);
  expect(screen.getByRole('button', { name: 'Обновить проверку' })).toBeVisible();
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal('navigator', Object.create(navigator, { clipboard: { value: { writeText } } }));
  try {
    fireEvent.click(screen.getByRole('button', { name: 'Скопировать отчёт' }));
    expect(await screen.findByText('Отчёт скопирован.')).toBeVisible();
    const copied = writeText.mock.calls[0][0];
    expect(copied).toContain('В медиатеке 2 фото · Интерьер · Команда');
    expect(copied).toContain('Доснять\n• Снимите дверь крупным планом.');
    expect(copied).toContain(image);
    expect(copied).not.toContain('Google Drive');
  } finally {
    vi.unstubAllGlobals();
  }
  fireEvent.click(screen.getByText('Уточнить фото'));
  fireEvent.change(screen.getByRole('combobox', { name: 'Что показано на фото' }), { target: { value: 'entrance' } });
  fireEvent.click(screen.getByRole('button', { name: 'Добавить в подборку' }));
  await waitFor(() => expect(api.post).toHaveBeenLastCalledWith(endpoint, {
    action: 'photo_pick', key: 'candidate', category: 'entrance', revision: 3,
  }));
  expect(await screen.findByText('Проверяю фото…')).toBeVisible();
});

it.each([false, true])('opens a blank chat and starts from the first link (saved empty setup: %s)', async savedEmptySetup => {
  const empty = savedEmptySetup ? {
    ...setup, started: false, seo_prepared: false, sources: [], services: [],
  } : null;
  vi.mocked(api.get).mockImplementation(async path => ({
    data: path === endpoint ? { available: true, can_edit: true, setup: empty } : { messages: [], conversation: null },
  }));
  vi.mocked(api.post).mockResolvedValue({
    data: { available: true, setup: { ...setup, draft_ready: true, report_ready: true } },
  });
  function Context() {
    return <Outlet context={{ currentBusinessId: businessId, currentBusiness: { id: businessId, name: setup.profile.name } }} />;
  }
  render(<MemoryRouter initialEntries={['/dashboard/operator?setup=1&business_id=' + businessId]}>
    <LanguageProvider><Routes><Route element={<Context />}><Route path="/dashboard/operator" element={<OperatorPage />} /></Route></Routes></LanguageProvider>
  </MemoryRouter>);
  const input = await screen.findByRole('textbox', { name: 'Сообщение для первичной настройки' });
  await waitFor(() => expect(input).toBeEnabled());
  expect(screen.getByTestId('operator-message-list')).toBeEmptyDOMElement();
  expect(input).toHaveAccessibleDescription('Пришлите ссылку на карточку компании. Соберём данные и предложим правки.');
  const map = 'https://yandex.com/maps/org/fixture/123456';
  fireEvent.change(input, { target: { value: map } });
  fireEvent.keyDown(input, { key: 'Enter' });
  await waitFor(() => expect(api.post).toHaveBeenLastCalledWith(endpoint, {
    action: 'start', message: map, auto: true, revision: empty?.revision,
  }));
  expect(await screen.findByRole('heading', { name: 'Первичная настройка компании' })).toBeVisible();
  expect(await screen.findByText('Черновик готов к проверке')).toBeVisible();
  expect(screen.queryByText('Пришлите ссылку на карточку компании. Соберём данные и предложим правки.')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Скачать отчёт PDF' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Сохранить кабинет' })).toBeVisible();
});

it.each([false, true])('shows progress and reconciles an unconfirmed save (committed=%s)', async committed => {
  let saved = false;
  vi.mocked(api.get).mockImplementation(async () => ({ data: { available: true, setup: { ...setup, saved } } }));
  vi.mocked(api.post).mockImplementationOnce((_path, _body, options) => new Promise((_resolve, reject) => {
    options?.signal?.addEventListener('abort', () => {
      saved = committed;
      reject(new DOMException('Aborted', 'AbortError'));
    }, { once: true });
  }));
  function SetupChat() {
    return <InitialSetupChat setup={useInitialBusinessSetup(businessId, true)} isStaff={false} onExit={() => {}} />;
  }
  render(<MemoryRouter><SetupChat /></MemoryRouter>);
  await screen.findByRole('button', { name: 'Сохранить кабинет' });
  vi.useFakeTimers();
  try {
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить кабинет' }));
    expect(screen.getByRole('button', { name: 'Сохраняем кабинет…' })).toBeDisabled();
    expect(screen.getByText('Ждём подтверждения от LocalOS…')).toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    if (committed) {
      expect(screen.getByText('Кабинет сохранён.')).toHaveAttribute('role', 'status');
      expect(screen.getByRole('link', { name: 'Открыть кабинет' })).toBeVisible();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    } else {
      expect(screen.getByRole('alert')).toHaveTextContent('Сервер не подтвердил сохранение. Попробуйте ещё раз.');
      expect(screen.getByRole('button', { name: 'Сохранить кабинет' })).toBeEnabled();
    }
  } finally {
    vi.useRealTimers();
  }
});

it('gives the signed-in owner one direct link to the saved cabinet', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: { available: true, setup: { ...setup, saved: true, viewer_is_owner: true } } });
  function SetupChat() {
    return <InitialSetupChat setup={useInitialBusinessSetup(businessId, true)} isStaff onExit={() => {}} />;
  }
  render(<MemoryRouter><SetupChat /></MemoryRouter>);

  const cabinet = await screen.findByRole('link', { name: 'Открыть кабинет' });
  expect(cabinet).toHaveAttribute('href', expect.stringContaining(`business_id=${businessId}`));
  expect(screen.queryByText('Доступ владельцу')).not.toBeInTheDocument();
});

it('guides the owner from map edits to the calendar, photos and social connections', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: { available: true, setup: { ...setup, saved: true, viewer_is_owner: true } } });
  function SetupChat() {
    return <InitialSetupChat setup={useInitialBusinessSetup(businessId, true)} isStaff={false} onExit={() => {}} />;
  }
  const chatPath = `/dashboard/operator?setup=1&business_id=${businessId}`;
  render(<MemoryRouter initialEntries={[chatPath]}><SetupChat /></MemoryRouter>);

  const guide = within(await screen.findByRole('region', { name: 'Следующий шаг настройки' }));
  expect(guide.getByRole('link', { name: 'Подключить карты' })).toHaveAttribute('href', expect.stringContaining('focus=integrations'));
  fireEvent.click(guide.getByRole('link', { name: 'Перейти к контенту' }));
  const photos = guide.getByRole('link', { name: 'Подключить папку с фото' });
  expect(photos).toHaveAttribute('href', expect.stringContaining('section=media'));
  expect(decodeURIComponent(photos.getAttribute('href') || '')).toContain('setup_step=content');
  expect(guide.getByRole('link', { name: 'Проверить факты' })).toHaveAttribute('href', expect.stringContaining('section=knowledge'));
  fireEvent.click(guide.getByRole('link', { name: 'Дальше к соцсетям' }));
  expect(guide.getByRole('link', { name: 'Подключить соцсети' })).toHaveAttribute('href', expect.stringContaining('focus=channels'));
});

it.each([
  { provisional: true, viewerIsOwner: true, access: { invite_url: 'https://localos.pro/set-password#test' }, caption: 'По этой ссылке владелец задаст пароль и сразу попадёт в кабинет.' },
  { provisional: false, viewerIsOwner: false, access: { login_path: '/dashboard/operator?business_id=pilot-jinlian&setup=1' }, caption: 'Ссылка на кабинет владельца.' },
])('shows the appropriate owner link to staff (provisional=$provisional)', async ({ provisional, viewerIsOwner, access, caption }) => {
  vi.mocked(api.get).mockResolvedValue({ data: {
    available: true, setup: { ...setup, saved: true, provisional, viewer_is_owner: viewerIsOwner },
  } });
  vi.mocked(api.post).mockResolvedValueOnce({ data: access });
  function SetupChat() {
    return <InitialSetupChat setup={useInitialBusinessSetup(businessId, true)} isStaff onExit={() => {}} />;
  }
  render(<MemoryRouter><SetupChat /></MemoryRouter>);

  fireEvent.click(await screen.findByText('Доступ владельцу'));
  fireEvent.change(screen.getByLabelText('Почта владельца'), { target: { value: 'owner@example.com' } });
  fireEvent.click(screen.getByRole('button', { name: 'Подготовить доступ' }));
  expect(await screen.findByText(caption)).toBeVisible();
  expect(screen.getByRole('textbox', { name: 'Ссылка для владельца' })).toHaveValue(
    access.invite_url || window.location.origin + access.login_path,
  );
});

it('updates one result message from map reading to photos and keeps an unread card out of the draft', async () => {
  const map = { ...setup.sources[0], photo_candidate_count: 4 };
  const pending = {
    ...setup, sources: [{ ...map, status: 'queued', service_count: 0, photo_candidate_count: 0 }],
    services: [], seo_prepared: false, draft_status: 'queued',
  };
  const limited = {
    ...pending, sources: [{ ...pending.sources[0], status: 'unavailable', note: 'Яндекс временно ограничил чтение.' }],
    draft_status: 'needs_source',
  };
  let state: object = limited;
  vi.mocked(api.get).mockImplementation(async () => ({ data: { available: true, setup: state } }));
  vi.mocked(api.post).mockResolvedValue({ data: { available: true, setup: pending } });
  function SetupChat() {
    return <InitialSetupChat setup={useInitialBusinessSetup(businessId, true)} isStaff={false} onExit={() => {}} />;
  }
  render(<MemoryRouter><SetupChat /></MemoryRouter>);
  expect(await screen.findByText('Яндекс временно ограничил чтение.')).toBeVisible();
  const result = screen.getByRole('article', { name: 'Нужно уточнить данные' });
  expect(within(result).queryByText('Услуги')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Скачать отчёт PDF' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сбор' }));
  const collecting = await within(result).findByText('Читаю карточки…');
  expect(collecting).toBeVisible();
  expect(result.querySelector('img')).toHaveAttribute('src', expect.stringContaining('logo.png'));
  expect(collecting.closest('summary')?.querySelector('svg')).toHaveClass('motion-safe:animate-spin');
  expect(within(result).queryByText('Проверяю фото…')).not.toBeInTheDocument();

  state = { ...pending, sources: [map], draft_status: 'running' };
  expect(await within(result).findByText('Готовлю предложения…', {}, { timeout: 3500 })).toBeVisible();
  expect(within(result).getByText('Яндекс Карты · прочитано')).toBeVisible();
  expect(within(result).getByText('4 фото на проверку')).toBeVisible();
  expect(within(result).queryByRole('link', { name: 'Каталог услуг' })).not.toBeInTheDocument();
  state = { ...setup, sources: [map], draft_ready: true, photo_report: { status: 'running' } };
  const photoStep = await within(result).findByText('Проверяю 4 фото…', {}, { timeout: 3500 });
  expect(photoStep).toHaveAttribute('role', 'status');
  expect(within(result).getByText('1 запрос')).toBeVisible();
  expect(screen.getByText('1 услуга с предложениями')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Скачать отчёт PDF' })).not.toBeInTheDocument();
  state = { ...setup, sources: [map], draft_ready: true, report_ready: true };
  expect(await screen.findByRole('button', { name: 'Скачать отчёт PDF' }, { timeout: 3500 })).toBeVisible();
  expect(within(result).queryByText('Проверяю 4 фото…')).not.toBeInTheDocument();
  expect(screen.getByRole('article', { name: 'Черновик готов к проверке' })).toBe(result);
  expect(result.querySelectorAll('img')).toHaveLength(1);
  expect(result.querySelector('.motion-safe\\:animate-spin')).toBeNull();
}, 12500);

it('shows a single source retry and keeps the provider and cost out of chat', async () => {
  const source = { ...setup.sources[0], status: 'unavailable', note: 'Яндекс временно ограничил чтение.' };
  const limited = { ...setup, sources: [source], draft_status: 'needs_source' };
  vi.mocked(api.post).mockClear();
  vi.mocked(api.get).mockResolvedValue({ data: { available: true, setup: limited } });
  vi.mocked(api.post).mockResolvedValue({
    data: { available: true, setup: {
      ...limited, sources: [{ ...source, status: 'queued', note: '' }],
      draft_status: 'queued',
    } },
  });
  function SetupChat() {
    return <InitialSetupChat setup={useInitialBusinessSetup(businessId, true)} isStaff onExit={() => {}} />;
  }
  render(<MemoryRouter><SetupChat /></MemoryRouter>);
  const button = await screen.findByRole('button', { name: 'Повторить сбор' });
  expect(screen.queryByText(/Apify|\$0,02/)).not.toBeInTheDocument();
  fireEvent.click(button);
  expect(await screen.findByText('Читаю карточки…')).toBeVisible();
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  expect(screen.queryByText(/Apify|\$0,02/)).not.toBeInTheDocument();
  expect(api.post).toHaveBeenCalledExactlyOnceWith(endpoint, {
    action: 'retry', key: 'map', revision: 3,
  });
});

it('releases a stalled PDF request and downloads the report on retry', async () => {
  vi.mocked(api.get).mockResolvedValue({
    data: { available: true, setup: { ...setup, report_ready: true, draft_ready: true } },
  });
  function SetupChat() {
    return <InitialSetupChat setup={useInitialBusinessSetup(businessId, true)} isStaff={false} onExit={() => {}} />;
  }
  render(<MemoryRouter><SetupChat /></MemoryRouter>);
  const button = await screen.findByRole('button', { name: 'Скачать отчёт PDF' });

  const fetchPdf = vi.fn()
    .mockImplementationOnce((_url: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
      options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
    }))
    .mockResolvedValueOnce(new Response('%PDF-1.4', { headers: { 'content-type': 'application/pdf' } }));
  const createObjectURL = vi.fn(() => 'blob:http://localhost/setup-report');
  const revokeObjectURL = vi.fn();
  class DownloadURL extends URL {
    static createObjectURL = createObjectURL;
    static revokeObjectURL = revokeObjectURL;
  }
  const downloads: { filename: string; attached: boolean }[] = [];
  const clickLink = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    downloads.push({ filename: this.download, attached: this.isConnected });
  });
  vi.stubGlobal('fetch', fetchPdf);
  vi.stubGlobal('URL', DownloadURL);
  vi.useFakeTimers();
  try {
    fireEvent.click(button);
    expect(button).toBeDisabled();
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(button).toBeEnabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Сервер долго не отвечал');
    expect(downloads).toHaveLength(0);

    await act(async () => { fireEvent.click(button); });
    expect(button).toBeEnabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(downloads).toEqual([{ filename: 'LocalOS - Jinlian Vegan Ice Cream.pdf', attached: true }]);
    expect(fetchPdf).toHaveBeenCalledTimes(2);
    expect(fetchPdf.mock.calls[1][0]).toMatch(/\/api\/operator\/initial-setup\/pilot-jinlian\/report$/);
    expect(revokeObjectURL).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:http://localhost/setup-report');
  } finally {
    clickLink.mockRestore();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  }
});
