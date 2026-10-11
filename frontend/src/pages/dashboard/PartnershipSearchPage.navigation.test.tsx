import { Profiler } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Link, Outlet, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { PartnershipSearchPage } from './PartnershipSearchPage';

vi.mock('@/i18n/LanguageContext', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn(() => new Promise(() => undefined)) } }));
vi.mock('@/lib/subscriptionAccess', () => ({ getCapabilityAccessForBusiness: () => ({ allowed: false }) }));
vi.mock('@/components/prospecting/PartnershipResults', () => ({ PartnershipResults: () => <p>Договорённости сети</p> }));

const context = {
  currentBusinessId: 'business-a', currentBusiness: { id: 'business-a' },
  businesses: [], user: {}, controlScope: { kind: 'network', id: 'network-a' },
  onBusinessChange: vi.fn(), onControlScopeChange: vi.fn(),
};

function WorkShell() {
  return <><nav><Link to="/influencers">Инфлюенсеры</Link><Link to="/average-ticket">Средний чек</Link><Link to="/agents">Автоматизация</Link></nav><Outlet context={context} /></>;
}

// A bounded commit budget aborts an update loop instead of hanging the test runner.
function mountWorkspace() {
  let commits = 0;
  render(<MemoryRouter initialEntries={['/partnerships']}><Routes><Route element={<WorkShell />}>
    <Route path="partnerships" element={<Profiler id="partnerships" onRender={() => {
      commits += 1;
      if (commits > 30) throw new Error('Partnerships keeps rendering without any data or user change');
    }}><PartnershipSearchPage /></Profiler>} />
    {['influencers', 'average-ticket', 'agents'].map(path => <Route key={path} path={path} element={<h1>{path}</h1>} />)}
  </Route></Routes></MemoryRouter>);
  return () => commits;
}

describe('leaving partnerships while data is pending', () => {
  it('settles without repeated state updates even with no drafts', () => {
    const commits = mountWorkspace();
    expect(screen.getByRole('heading', { name: 'Партнёрства сети' })).toBeInTheDocument();
    expect(commits()).toBeLessThan(10);
  });
  it.each([['Инфлюенсеры', 'influencers'], ['Средний чек', 'average-ticket'], ['Автоматизация', 'agents']])('opens %s without waiting for partnership requests', async (label, path) => {
    mountWorkspace();
    await userEvent.click(screen.getByRole('link', { name: label }));
    expect(screen.getByRole('heading', { name: path })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Партнёрства сети' })).not.toBeInTheDocument();
  });
});
