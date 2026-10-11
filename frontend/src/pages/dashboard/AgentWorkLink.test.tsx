import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
const calls = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('@/services/api', () => ({ api: calls }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { getCurrentUserSync: () => null, getCurrentUser: async () => null, getToken: () => null } }));
vi.mock('@/lib/browserSessionFetch', () => ({ browserAuthenticationAvailable: () => false }));
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('./agents/view', () => ({ AgentBlueprintsView: ({ scope }: { scope: { activeRun: { id: string } | null; selectedBlueprint: { id: string } | null; error: string | null } }) => <div><p>Run: {scope.activeRun?.id}</p><p>Employee: {scope.selectedBlueprint?.id}</p>{scope.error ? <p role="alert">{scope.error}</p> : null}</div> }));
import { AgentBlueprintsPage } from './AgentBlueprintsPage';
const Context = () => <Outlet context={{ currentBusinessId: 'business', currentBusiness: { id: 'business' }, demoMode: false }} />;
const mount = () => render(<MemoryRouter initialEntries={['/dashboard/agents?run_id=selected-run']}><Routes><Route element={<Context />}><Route path="/dashboard/agents" element={<AgentBlueprintsPage />} /></Route></Routes></MemoryRouter>);
const employees = [{ id: 'employee-a', business_id: 'business', name: 'A', status: 'draft', category: 'custom' }, { id: 'employee-b', business_id: 'business', name: 'B', status: 'draft', category: 'custom' }];
const route = (url: string, blueprint = 'employee-b') => {
 if (url === '/agent-blueprints') return Promise.resolve({ data: { blueprints: employees.map(item => ({ ...item })) } });
 if (url === '/agent-runs/selected-run') return Promise.resolve({ data: { run: { id: 'selected-run', blueprint_id: blueprint, status: 'completed', steps: [], artifacts: [], approvals: [] } } });
 if (url === '/agent-blueprints/employee-a' || url === '/agent-blueprints/employee-b') return Promise.resolve({ data: { blueprint: employees.find(item => url.endsWith(item.id)), versions: [], runs: [] } });
 return Promise.resolve({ data: {} });
};
beforeEach(() => { calls.get.mockReset(); calls.post.mockReset(); });
describe('specific employee work links', () => {
 it('opens the linked run and selects its employee without starting work', async () => {
  calls.get.mockImplementation((url: string) => route(url)); mount();
  expect(await screen.findByText('Run: selected-run')).toBeVisible();
  expect(screen.getByText('Employee: employee-b')).toBeVisible();
  expect(calls.post).not.toHaveBeenCalled();
 });
 it('does not display a run belonging to a different business', async () => {
  calls.get.mockImplementation((url: string) => route(url, 'another-business-employee')); mount();
  expect(await screen.findByRole('alert')).toBeVisible();
  expect(screen.queryByText('Run: selected-run')).not.toBeInTheDocument();
  expect(calls.post).not.toHaveBeenCalled();
 });
});
