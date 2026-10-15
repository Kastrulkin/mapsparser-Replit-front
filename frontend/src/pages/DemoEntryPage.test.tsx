import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import DemoEntryPage from './DemoEntryPage';
import { newAuth } from '@/lib/auth_new';
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('@/lib/auth_new', () => ({ newAuth: {
  activateDemoSession: vi.fn(), deactivateDemoSession: vi.fn(), getCurrentUser: vi.fn(),
} }));
function renderEntry() {
  render(<MemoryRouter initialEntries={['/demo']}><Routes>
    <Route path="/demo" element={<DemoEntryPage />} />
    <Route path="/dashboard/today" element={<p>Today destination</p>} />
  </Routes></MemoryRouter>);
}
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); vi.clearAllMocks(); });
describe('demo starts at current daily work', () => {
  it('opens Today for a fresh session even with an older server start path', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({token:'demo_test',business_id:'demo-business',start_path:'/dashboard/operator'})));
    renderEntry();
    expect(await screen.findByText('Today destination', {}, {timeout:5000})).toBeVisible();
    expect(newAuth.activateDemoSession).toHaveBeenCalledWith('demo_test');
    expect(localStorage.getItem('demo_selectedBusinessId')).toBe('demo-business');
  });
  it('reuses a valid isolated demo session without creating another', async () => {
    localStorage.setItem('demo_auth_token','demo_existing');
    vi.mocked(newAuth.getCurrentUser).mockResolvedValue({id:'demo-user',email:'demo@example.test',demo_mode:true,demo_scope_business_id:'demo-business'});
    const request=vi.spyOn(globalThis,'fetch');
    renderEntry();
    expect(await screen.findByText('Today destination', {}, {timeout:5000})).toBeVisible();
    expect(request).not.toHaveBeenCalled();
  });
  it('offers retry when the demo is unavailable', async () => {
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('{}',{status:503}));
    renderEntry();
    expect(await screen.findByRole('button',{name:/Повторить/})).toBeVisible();
    expect(newAuth.deactivateDemoSession).toHaveBeenCalledWith(true);
  });
});
