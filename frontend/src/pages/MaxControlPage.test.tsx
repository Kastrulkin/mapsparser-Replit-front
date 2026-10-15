import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LanguageContext } from '@/i18n/LanguageContext.logic';
import { en } from '@/i18n/locales/en';
import { workCoherenceCopy } from '@/i18n/workCoherenceCopy';
import TelegramControlPage from './TelegramControlPage';

const json = (payload: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } }));
const bootstrap = {
  success: true, user: { id: 'max-user', name: 'Owner' }, today_v2_enabled: false,
  selected_scope: { kind: 'business', id: 'business-1', name: 'MAX Business', business_ids: ['business-1'], can_switch: false },
  web_session_token: 'max-session', summary: { attention_items: [] }, catalog: { businesses: [], total_choices: 1 },
  navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' }],
};
const renderControl = () => render(<LanguageContext.Provider value={{ language: 'ru', setLanguage: vi.fn(), t: en }}><TelegramControlPage /></LanguageContext.Provider>);

beforeEach(() => {
  window.history.replaceState({}, '', '/max/control');
  window.WebApp = { initData: 'signed-max-data' };
  window.localStorage.setItem('localos-mini-onboarding-v3:max-user', 'completed');
});
afterEach(() => { vi.unstubAllGlobals(); delete window.WebApp; window.localStorage.clear(); window.sessionStorage.clear(); window.history.replaceState({}, '', '/'); });

it('uses MAX bootstrap and shared mobile APIs, with a separate Operator channel', async () => {
  const calls: Array<{ url: string; body?: string }> = [];
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input); calls.push({ url, body: typeof init?.body === 'string' ? init.body : undefined });
    if (url === '/api/operator/max/bootstrap') return json(bootstrap);
    if (url.startsWith('/api/operator/mobile/workspace')) return json({ items: [], summary: { attention_items: [] } });
    if (url.startsWith('/api/operator/mobile/operator/history')) return json({ items: [{ id: 'm1', role: 'operator', content: 'История MAX', status: 'completed' }] });
    return json({});
  }));
  renderControl();
  const navigation = await screen.findByRole('navigation', { name: 'Главное меню' });
  await userEvent.click(within(navigation).getByRole('button', { name: workCoherenceCopy('ru').chat }));
  expect(await screen.findByText('История MAX')).toBeInTheDocument();
  expect(calls.some(call => call.url === '/api/operator/max/bootstrap' && call.body?.includes('signed-max-data'))).toBe(true);
  expect(calls.some(call => call.url.includes('/api/operator/telegram/'))).toBe(false);
  expect(window.sessionStorage.getItem('localos_mini_session')).toBe('max-session');
});

it('shows account linking on a valid unbound identity and removes the previous session', async () => {
  window.sessionStorage.setItem('localos_mini_session', 'previous-account');
  vi.stubGlobal('fetch', vi.fn(() => json({ success: false, code: 'max_link_required', error: 'Подключите аккаунт' }, 401)));
  renderControl();
  expect(await screen.findByRole('heading', { name: 'Подключите свой LocalOS к MAX' })).toBeVisible();
  expect(window.sessionStorage.getItem('localos_mini_session')).toBeNull();
  expect(screen.queryByText('MAX Business')).not.toBeInTheDocument();
});

it('keeps the entered linking code after a rejected attempt', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => String(input) === '/api/max/link'
    ? json({ success: false, error: 'Код истёк' }, 409)
    : json({ success: false, code: 'max_link_required', error: 'Подключите аккаунт' }, 401)));
  renderControl();
  const user = userEvent.setup();
  const code = await screen.findByLabelText('Код из кабинета LocalOS');
  await user.type(code, 'synthetic-expired-code');
  await user.click(screen.getByRole('button', { name: 'Подключить аккаунт' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Код истёк'));
  expect(code).toHaveValue('synthetic-expired-code');
});
