import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TooltipProvider } from '@/components/ui/tooltip';
import { newAuth } from '@/lib/auth_new';
import type { BusinessRecord } from '@/types/business';
import { ProfilePage } from './ProfilePage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
vi.mock('@/i18n/LanguageContext.logic', async () => { const { ru } = await import('@/i18n/locales/ru'); return { useLanguage: () => ({ language: 'ru', t: ru }) }; });
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock('@/components/NetworkManagement', () => ({ NetworkManagement: () => null }));
vi.mock('@/components/business-knowledge/BusinessKnowledge', () => ({ BusinessKnowledge: () => null }));
vi.mock('@/components/SubscriptionManagement', () => ({ SubscriptionManagement: () => null }));
vi.mock('@/components/dashboard/BusinessMembers', () => ({ BusinessMembers: () => null }));
vi.mock('@/components/dashboard/BusinessAdditionalSettings', () => ({ BusinessAdditionalSettings: () => null }));
vi.mock('@/components/UserTokenUsageSummary', () => ({ UserTokenUsageSummary: () => null }));
vi.mock('@/components/operator/ContentRules', () => ({ ContentRules: () => null }));

const business: BusinessRecord = { id: 'new-business', name: 'Рога и копыта', owner_id: 'new-user' };
let savedMapLinks: { url: string }[] = [];
const Context = () => <Outlet context={{ user: { id: 'new-user', email: 'onboarding@example.test', name: 'Тестовый пользователь' }, currentBusinessId: business.id, currentBusiness: business, businesses: [business], setBusinesses: vi.fn(), updateBusiness: vi.fn(), reloadBusinesses: vi.fn() }} />;
function renderProfile() {
  render(<TooltipProvider><MemoryRouter initialEntries={['/dashboard/profile']}><Routes><Route element={<Context />}><Route path="/dashboard/profile" element={<ProfilePage />} /></Route></Routes></MemoryRouter></TooltipProvider>);
}
beforeEach(() => {
  savedMapLinks = [];
  business.subscription_tier = 'trial';
  business.subscription_status = 'active';
  Element.prototype.scrollIntoView = vi.fn();
  vi.mocked(newAuth.makeRequest).mockReset();
  window.localStorage.clear();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, status: 'idle' }) }));
  vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
    if (path.startsWith('/client-info')) return { businessName: business.name, address: 'Тестовая улица, 1', city: 'Санкт-Петербург', workingHours: '', mapLinks: savedMapLinks };
    if (path === '/business-types') return { types: [{ type_key: 'other', label: 'Другое' }] };
    return { success: true, is_network: false, locations: [] };
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('new business profile setup', () => {
  it('waits for the saved business data before allowing editing', async () => {
    const defaultRequest = vi.mocked(newAuth.makeRequest).getMockImplementation();
    let finishLoad: (data: { businessName: string; mapLinks: [] }) => void = () => undefined;
    const pending = new Promise<{ businessName: string; mapLinks: [] }>(resolve => { finishLoad = resolve; });
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path, options) => {
      if (path.startsWith('/client-info')) return pending;
      return defaultRequest?.(path, options);
    });
    renderProfile();
    const edit = screen.getByTitle('Открывает редактирование данных бизнеса, ссылки на карту и параметров для аудита.');
    expect(edit).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Добавить ссылку на карту' })).toBeDisabled();
    finishLoad({ businessName: business.name, mapLinks: [] });
    await screen.findByDisplayValue(business.name);
    expect(edit).toBeEnabled();
    fireEvent.click(edit);
    expect(screen.getByDisplayValue(business.name)).toBeEnabled();
  });

  it('opens and focuses the time-zone field when saving a new city requires it', async () => {
    const defaultRequest = vi.mocked(newAuth.makeRequest).getMockImplementation();
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path, options) => {
      if (path === '/client-info' && options?.method === 'POST') {
        throw new Error('Укажите часовой пояс для нового города.');
      }
      return defaultRequest?.(path, options);
    });
    renderProfile();
    await screen.findByDisplayValue(business.name);
    fireEvent.click(screen.getByTitle('Открывает редактирование данных бизнеса, ссылки на карту и параметров для аудита.'));
    fireEvent.change(screen.getByDisplayValue('Санкт-Петербург'), { target: { value: 'Новый учебный город' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    await screen.findByText('Укажите часовой пояс для нового города.');
    const timezone = screen.getByLabelText('Часовой пояс бизнеса');
    expect(timezone.closest('details')).toHaveAttribute('open');
    expect(timezone).toHaveFocus();
    expect(screen.getByDisplayValue('Новый учебный город')).toBeEnabled();
  });
});
