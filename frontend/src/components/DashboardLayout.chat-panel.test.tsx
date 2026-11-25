import '@testing-library/jest-dom/vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useLocation, useOutletContext } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { api } from '@/services/api';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { DashboardLayout } from './DashboardLayout';

const auth = vi.hoisted(() => ({ getCurrentUser: vi.fn(), makeRequest: vi.fn(), getToken: () => null }));
vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));
vi.mock('@/contexts/CurrencyContext.logic', () => ({ useCurrency: () => ({ currency: 'RUB', setCurrency: vi.fn() }) }));
vi.mock('../lib/auth_new', () => ({ newAuth: auth, HttpError: Error }));
vi.mock('./DashboardSidebar', () => ({ DashboardSidebar: () => null }));
vi.mock('./guided-tour/GuidedTourProvider', () => ({
  GuidedTourProvider: ({ children }: { children: ReactNode }) => children,
  DemoModeBanner: () => null,
}));

function BusinessPage({ title }: { title: string }) {
  const { onBusinessChange } = useOutletContext<{ onBusinessChange: (business: string) => void }>();
  return <><h2>{title}</h2><button type="button" onClick={() => onBusinessChange('jinlian')}>Выбрать Jinlian</button></>;
}

function CurrentRoute() {
  const { pathname, search } = useLocation();
  return <output aria-label="Текущий адрес">{pathname + search}</output>;
}

function open(route: string) {
  return render(<MemoryRouter initialEntries={[route]}><LanguageProvider>
    <CurrentRoute />
    <nav aria-label="Разделы теста">
      <Link to="/dashboard/profile?command=чужое&section=knowledge">Профиль</Link>
      <Link to="/dashboard/content?command=другая-команда&tab=articles">Контент</Link>
      <Link to="/dashboard/operator">Полный чат</Link>
    </nav>
    <Routes><Route path="/dashboard" element={<DashboardLayout />}>
      <Route path="profile" element={<BusinessPage title="Профиль компании" />} />
      <Route path="content" element={<BusinessPage title="Контент компании" />} />
      <Route path="operator" element={null} />
    </Route></Routes>
  </LanguageProvider></MemoryRouter>);
}

function deferred<Value>() {
  let resolve: (value: Value) => void = () => undefined;
  const promise = new Promise<Value>(done => { resolve = done; });
  return { promise, resolve };
}

const textbox = () => screen.findByRole('textbox', { name: 'Вопрос или поручение для LocalOS' }, { timeout: 5000 });
const launcherName = 'Чат с помощником ЛокалОС';
const launcher = () => screen.findByRole('button', { name: launcherName });

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('language', 'ru');
  vi.clearAllMocks();
  auth.getCurrentUser.mockResolvedValue({ id: 'owner', email: 'owner@example.test', businesses: [
    { id: 'hamik', name: 'Хамик', subscription_tier: 'promo', subscription_status: 'active' },
    { id: 'jinlian', name: 'Jinlian', subscription_tier: 'promo', subscription_status: 'active' },
  ] });
  auth.makeRequest.mockResolvedValue({});
  vi.mocked(api.get).mockResolvedValue({ data: { messages: [], conversation: { id: 'chat-hamik' } } });
});

it('keeps the open chat and draft across sections, then expands the same workspace', async () => {
  open('/dashboard/profile?command=ignore-me');
  const trigger = await launcher();
  expect(trigger).toHaveClass('fixed', 'right-0', 'bottom-24');
  expect(within(screen.getByRole('banner')).queryByRole('button', { name: 'Чат с LocalOS' })).toBeNull();
  fireEvent.click(trigger);
  const panel = await screen.findByRole('region', { name: 'Боковой чат' });
  const input = await textbox();
  expect(input).toHaveValue('');
  expect(within(panel).getByText('Хамик')).toBeInTheDocument();
  fireEvent.change(input, { target: { value: 'Подготовь черновик' } });

  fireEvent.click(screen.getByRole('link', { name: /^Контент$/ }));
  expect(await screen.findByRole('heading', { name: 'Контент компании' })).toBeInTheDocument();
  expect(await textbox()).toBe(input);
  expect(input).toHaveValue('Подготовь черновик');

  fireEvent.click(within(panel).getByRole('link', { name: 'Развернуть чат' }));
  await waitFor(() => expect(screen.getByLabelText('Текущий адрес')).toHaveTextContent('/dashboard/operator?business_id=hamik'));
  expect(await textbox()).toBe(input);
  expect(input).toHaveValue('Подготовь черновик');
  expect(vi.mocked(api.get).mock.calls.filter(([path]) => path.includes('/operator/conversations'))).toHaveLength(1);
});

it('continues a request while collapsed and scopes the next workspace to the new company', async () => {
  const reply = deferred<{ data: { conversation_id: string; operator_result: { status: string; chat_response: string } } }>();
  vi.mocked(api.post).mockReturnValue(reply.promise);
  open('/dashboard/profile');
  const button = await launcher();
  fireEvent.click(button);
  const input = await textbox();
  fireEvent.change(input, { target: { value: 'Проверь кабинет' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/operator/chat', expect.objectContaining({
    business_id: 'hamik', conversation_id: 'chat-hamik', message: 'Проверь кабинет',
  })));
  fireEvent.keyDown(input, { key: 'Escape' });
  const restoredLauncher = await launcher();
  expect(restoredLauncher).toHaveFocus();
  expect(restoredLauncher).toHaveAttribute('aria-expanded', 'false');
  await act(async () => reply.resolve({ data: { conversation_id: 'chat-hamik', operator_result: { status: 'completed', chat_response: 'Кабинет проверен' } } }));
  fireEvent.click(restoredLauncher);
  expect((await screen.findAllByText('Кабинет проверен')).length).toBeGreaterThan(0);
  fireEvent.change(await textbox(), { target: { value: 'Приватный черновик Хамика' } });
  fireEvent.click(screen.getByRole('button', { name: 'Выбрать Jinlian' }));
  const panel = await screen.findByRole('region', { name: 'Боковой чат' });
  expect(await within(panel).findByText('Jinlian')).toBeVisible();
  expect(await textbox()).toHaveValue('');
  expect(within(panel).queryByText('Кабинет проверен')).toBeNull();
});

it('keeps a draft started in the full chat when the panel is opened later', async () => {
  open('/dashboard/operator');
  const input = await textbox();
  fireEvent.change(input, { target: { value: 'Продолжить после профиля' } });
  fireEvent.click(screen.getByRole('link', { name: /^Профиль$/ }));
  const button = await launcher();
  expect(button).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(button);
  expect(await textbox()).toBe(input);
  expect(input).toHaveValue('Продолжить после профиля');
});

it('honors the same access as the full chat', async () => {
  auth.getCurrentUser.mockResolvedValue({ id: 'owner', businesses: [
    { id: 'hamik', name: 'Хамик', subscription_access: { tier: 'starter', capabilities: ['maps'] } },
  ] });
  open('/dashboard/profile');
  await screen.findByRole('heading', { name: 'Профиль компании' });
  expect(screen.queryByRole('button', { name: launcherName })).toBeNull();
  fireEvent.click(screen.getByRole('link', { name: 'Полный чат' }));
  expect(await screen.findByRole('heading', { name: /Оператор входит в тариф/ })).toBeInTheDocument();
  expect(api.get).not.toHaveBeenCalledWith('/operator/conversations/current', expect.anything());
});


it('keeps a task response in the expanded chat after navigating while it runs', async () => {
  const response = deferred<{ data: { operator_result: { status: string; chat_response: string; task: { id: string; status: string } } } }>();
  vi.mocked(api.post).mockReturnValue(response.promise);
  open('/dashboard/profile?command=игнорировать');
  fireEvent.click(await launcher());
  const input = await textbox();
  fireEvent.change(input, { target: { value: 'Продолжи поиск' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('link', { name: 'Развернуть чат' }));
  await waitFor(() => expect(screen.getByLabelText('Текущий адрес')).toHaveTextContent('/dashboard/operator?business_id=hamik'));
  await act(async () => response.resolve({ data: { operator_result: {
    status: 'completed', chat_response: 'Поиск готов к проверке', task: { id: 'search-1', status: 'completed' },
  } } }));
  await waitFor(() => expect(screen.getByLabelText('Текущий адрес')).toHaveTextContent('/dashboard/operator?business_id=hamik&search_task_id=search-1'));
  expect((await screen.findAllByText('Поиск готов к проверке')).length).toBeGreaterThan(0);
});
