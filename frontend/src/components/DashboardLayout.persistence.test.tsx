import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useOutletContext } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

const auth = vi.hoisted(() => ({ getCurrentUser: vi.fn(), makeRequest: vi.fn() }));
vi.mock('../lib/auth_new', () => ({ newAuth: auth, HttpError: Error }));
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('./DashboardHeader', () => ({ DashboardHeader: () => null }));
vi.mock('./DashboardSidebar', () => ({ DashboardSidebar: () => null }));
vi.mock('./guided-tour/GuidedTourProvider', () => ({
  GuidedTourProvider: ({ children }: { children: ReactNode }) => children, DemoModeBanner: () => null,
}));
import { DashboardLayout } from './DashboardLayout';

function Probe() {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId: string }>();
  return <p>business:{currentBusinessId}</p>;
}

function openRoute(route: string) {
  window.history.replaceState(null, '', route);
  return render(<MemoryRouter initialEntries={[route]}><Routes>
    <Route path="/dashboard" element={<DashboardLayout />}>
      <Route path="content" element={<Probe />} /><Route path="operator" element={<Probe />} />
    </Route>
  </Routes></MemoryRouter>);
}

afterEach(() => window.history.replaceState(null, '', '/'));

it('persists an allowed deep-link business across an unscoped full reload', async () => {
  localStorage.clear();
  localStorage.setItem('selectedBusinessId', 'first');
  auth.getCurrentUser.mockResolvedValue({ id: 'owner', is_superadmin: true,
    businesses: [{ id: 'first', name: 'Первый' }, { id: 'meliora', name: 'Мелиора' }] });
  const initial = openRoute('/dashboard/content?business_id=meliora&scope_type=business');
  await screen.findByText('business:meliora');
  expect(localStorage.getItem('selectedBusinessId')).toBe('meliora');
  initial.unmount();
  openRoute('/dashboard/operator');
  await screen.findByText('business:meliora');
});

it('does not restore a business missing from the authenticated allowed list', async () => {
  localStorage.clear();
  localStorage.setItem('selectedBusinessId', 'forbidden');
  auth.getCurrentUser.mockResolvedValue({ id: 'owner', is_superadmin: false,
    businesses: [{ id: 'allowed', name: 'Разрешённый' }] });
  openRoute('/dashboard/operator');
  await screen.findByText('business:allowed');
  expect(localStorage.getItem('selectedBusinessId')).toBe('allowed');
});
