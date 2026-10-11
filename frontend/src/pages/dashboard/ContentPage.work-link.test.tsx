import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { ContentPage } from './ContentPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { getToken: vi.fn(() => ''), makeRequest: vi.fn() } }));
const targetPlan = { id: 'old-plan', business_id: 'business-1', scope_type: 'business', scope_target_id: 'business-1', plan_status: 'archived', items: [{ id: 'target-item', business_id: 'business-1', theme: 'Выбранный материал', draft_text: 'Подготовленный текст', scheduled_for: '2026-08-10' }] };
const ContextRoute = () => {
  const [businessId, setBusinessId] = useState('business-1');
  return <><button onClick={() => setBusinessId('business-2')}>Сменить бизнес</button><Outlet context={{currentBusinessId:businessId,currentBusiness:{id:businessId,name:'Бизнес'},demoMode:false}}/></>;
};
const renderPage = () => render(
  <MemoryRouter initialEntries={['/dashboard/content?plan_id=old-plan&item_id=target-item']}>
    <LanguageProvider><Routes><Route element={<ContextRoute/>}>
      <Route path='/dashboard/content' element={<ContentPage/>}/>
    </Route></Routes></LanguageProvider>
  </MemoryRouter>
);
const mockPlan = (plan: typeof targetPlan) => vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
  if (path.startsWith('/content-plans/context')) return {context:{}};
  if (path.startsWith('/content-plans?')) return {plans:[{id:'latest-plan',items:[]}]};
  if (path === '/content-plans/old-plan') return {plan};
  if (path.endsWith('/social-posts')) return {posts:[],summary:{}};
  return {};
});
describe('Content work deep link', () => {
  beforeEach(() => { window.localStorage.clear();window.localStorage.setItem('language','ru');vi.mocked(newAuth.makeRequest).mockReset(); });
  it('opens the exact item from a plan outside the working list without issuing a command', async () => {
    mockPlan(targetPlan);renderPage();
    expect(await screen.findByDisplayValue('Выбранный материал')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(vi.mocked(newAuth.makeRequest).mock.calls.some(([, options]) => options?.method && options.method !== 'GET')).toBe(false);
    expect(vi.mocked(newAuth.makeRequest).mock.calls.some(([path]) => path === '/content-plans/latest-plan')).toBe(false);
  });
  it('explains a missing item instead of choosing a different item', async () => {
    mockPlan({...targetPlan,items:[{...targetPlan.items[0],id:'other-item',theme:'Другой материал'}]});renderPage();
    expect(await screen.findByText(/Указанная запись недоступна в текущей выборке/)).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('Другой материал')).not.toBeInTheDocument();
  });
  it('withholds a plan belonging to another business', async () => {
    mockPlan({...targetPlan,business_id:'business-2',scope_target_id:'business-2'});renderPage();
    expect(await screen.findByText(/Указанная запись недоступна в текущей выборке/)).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Выбранный материал')).not.toBeInTheDocument();
  });
  it('ignores a previous business response arriving after switching', async () => {
    let finishOld = (value: {plan: typeof targetPlan}) => { void value; };
    const oldResponse = new Promise<{plan: typeof targetPlan}>((resolve) => { finishOld = resolve; });
    let planReads = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/content-plans/context')) return {context:{}};
      if (path.startsWith('/content-plans?')) return {plans:[]};
      if (path === '/content-plans/old-plan') {
        planReads += 1;
        return planReads === 1 ? oldResponse : {plan:{...targetPlan,items:[]}};
      }
      return {};
    });
    renderPage();
    await waitFor(() => expect(planReads).toBe(1));
    fireEvent.click(screen.getByRole('button',{name:'Сменить бизнес'}));
    await waitFor(() => expect(planReads).toBe(2));
    await act(async () => finishOld({plan:targetPlan}));
    expect(screen.queryByDisplayValue('Выбранный материал')).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
