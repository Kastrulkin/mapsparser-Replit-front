import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TooltipProvider } from '@/components/ui/tooltip';
import { newAuth } from '@/lib/auth_new';
import { AdminPage } from './AdminPage';

const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn(), getCurrentUser: vi.fn() } }));
vi.mock('@/lib/browserSessionFetch', () => ({ browserBearerToken: () => 'fixture-token' }));

const reloadBusinesses = vi.fn().mockResolvedValue(undefined);
const createBusiness = vi.fn();

async function openForm() {
  render(<TooltipProvider><MemoryRouter initialEntries={['/dashboard/bazich']}>
    <Routes><Route element={<Outlet context={{ reloadBusinesses }} />}>
      <Route path="/dashboard/bazich" element={<AdminPage />} />
    </Route></Routes>
  </MemoryRouter></TooltipProvider>);
  const trigger = (await screen.findAllByRole('button', { name: 'Создать аккаунт' }))[0];
  trigger.focus();
  fireEvent.click(trigger);
  return trigger;
}

function fillAndSubmit() {
  fireEvent.change(screen.getByPlaceholderText('Например: Салон красоты Элегант'), { target: { value: 'Тестовая студия' } });
  fireEvent.change(screen.getByPlaceholderText('owner@example.com'), { target: { value: 'owner@demo.invalid' } });
  fireEvent.click(screen.getByRole('button', { name: 'Создать бизнес' }));
}

beforeEach(() => {
  reloadBusinesses.mockClear();
  createBusiness.mockReset();
  vi.mocked(newAuth.makeRequest).mockReset().mockResolvedValue({ success: true, users: [] });
  vi.mocked(newAuth.getCurrentUser).mockResolvedValue({ id: 'admin', email: 'admin@demo.invalid', is_superadmin: true });
  vi.stubGlobal('fetch', createBusiness);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('creating a client from the admin panel', () => {
  it('sends the selected catalog entry as the business type', async () => {
    vi.mocked(newAuth.makeRequest).mockImplementation(async path => path === '/business-types'
      ? { types: [{ type_key: 'cafe', label: 'Кафе' }] }
      : { success: true, users: [] });
    createBusiness.mockResolvedValue({ ok: true, json: async () => ({ business_id: 'new-cafe' }) });
    await openForm();
    await screen.findByRole('option', { name: 'Кафе' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Тип бизнеса' }), { target: { value: 'cafe' } });
    fillAndSubmit();
    await waitFor(() => expect(createBusiness).toHaveBeenCalledWith('/api/superadmin/businesses', expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('"business_type":"cafe"'),
    })));
  });

  it('moves focus into the form and returns it when Escape closes the dialog', async () => {
    const trigger = await openForm();
    const dialog = screen.getByRole('dialog', { name: 'Создать новый бизнес' });
    const name = within(dialog).getByRole('textbox', { name: 'Название бизнеса *' });
    expect(name).toHaveFocus();
    fireEvent.keyDown(name, { key: 'Escape' });
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('refreshes the business switcher after creation succeeds', async () => {
    createBusiness.mockResolvedValue({ ok: true, json: async () => ({ business_id: 'new-business' }) });
    await openForm();
    fillAndSubmit();
    await waitFor(() => expect(reloadBusinesses).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole('button', { name: 'Создать бизнес' })).not.toBeInTheDocument();
  });

  it('keeps the draft for retry on an error without refreshing the business switcher', async () => {
    createBusiness.mockResolvedValue({ ok: false, json: async () => ({ error: 'Не удалось создать бизнес' }) });
    await openForm();
    fillAndSubmit();
    await screen.findByText('Не удалось создать бизнес');
    expect(screen.getByDisplayValue('Тестовая студия')).toBeInTheDocument();
    expect(reloadBusinesses).not.toHaveBeenCalled();
  });
});
