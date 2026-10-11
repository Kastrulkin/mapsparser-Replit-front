import '@testing-library/jest-dom/vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { newAuth } from '@/lib/auth_new';
import { GrowthPathsPage } from './GrowthPathsPage';
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
const Scope = () => {
 const [id, setId] = useState('a');
 return <><button onClick={() => setId('b')}>Select B</button><Outlet context={{ currentBusinessId: id }} /></>;
};
const path = (name: string) => ({ paths: [{ flow_type: 'content', status: 'ready', access: { status: 'available' }, action: { id: name, flow_type: 'content', cta_label: name, cta_target: { screen: 'content' } } }] });
it('hides prior context immediately and ignores a late old response', async () => {
 let finishA: (value: unknown) => void = () => undefined;
 let finishB: (value: unknown) => void = () => undefined;
 vi.mocked(newAuth.makeRequest).mockImplementation((url) => {
  if (url.includes('/today/preference?')) return Promise.resolve({});
  return new Promise(resolve => { if (url.endsWith('business_id=a')) finishA = resolve; else finishB = resolve; });
 });
 render(<MemoryRouter><Routes><Route element={<Scope />}><Route index element={<GrowthPathsPage />} /></Route></Routes></MemoryRouter>);
 fireEvent.click(screen.getByText('Select B'));
 await act(async () => finishB(path('B material')));
 expect(screen.getByRole('link', { name: 'B material' })).toHaveAttribute('href', '/dashboard/content?journey_action=B+material&business_id=b');
 await act(async () => finishA(path('A material')));
 expect(screen.queryByText('A material')).not.toBeInTheDocument();
 expect(screen.getByText('B material')).toBeVisible();
});
it('shows source unavailability instead of an empty business', async () => {
 vi.mocked(newAuth.makeRequest).mockRejectedValue(new Error('Source temporarily unavailable'));
 render(<MemoryRouter><Routes><Route element={<Scope />}><Route index element={<GrowthPathsPage />} /></Route></Routes></MemoryRouter>);
 expect(await screen.findByRole('alert')).toHaveTextContent('Source temporarily unavailable');
 expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument();
});

it('uses the existing preference contract and saves only after explicit confirmation', async () => {
 vi.mocked(newAuth.makeRequest).mockReset();
 const preference = {scope_type:'business',scope_id:'a',primary_flow:'maps',available_flows:['maps','content'],revision:7,suggestions_enabled:true};
 vi.mocked(newAuth.makeRequest).mockImplementation((url, options) => {
  if (url === '/operator/today/preference?scope_type=business&scope_id=a') return Promise.resolve({preference:options?.method === 'POST' ? {...preference,primary_flow:'content',revision:8} : preference});
  if (url === '/growth-paths?business_id=a') return Promise.resolve(path('Content work'));
  return Promise.reject(new Error('Unexpected endpoint: '+url));
 });
 render(<MemoryRouter><Routes><Route element={<Scope />}><Route index element={<GrowthPathsPage />} /></Route></Routes></MemoryRouter>);
 fireEvent.click(await screen.findByRole('button',{name:'Выбрать фокус'}));
 expect(vi.mocked(newAuth.makeRequest).mock.calls.filter(([,options])=>options?.method==='POST')).toHaveLength(0);
 fireEvent.click(within(screen.getByRole('region',{name:'Выбрать фокус'})).getByRole('button',{name:'Выбрать фокус'}));
 await waitFor(()=>expect(newAuth.makeRequest).toHaveBeenCalledWith('/operator/today/preference?scope_type=business&scope_id=a',{method:'POST',body:JSON.stringify({action:'set',expected_revision:7,primary_flow:'content'})}));
 expect(await screen.findByRole('button',{name:'Выбранный фокус'})).toBeDisabled();
});

it('distinguishes same-name network locations by their existing addresses', async () => {
 vi.mocked(newAuth.makeRequest).mockImplementation(async (url) => url.includes('/today/preference') ? {} : ({paths:[{flow_type:'content',status:'not_started',access:{status:'available'},locations:[{business_id:'one',business_name:'Одинаковое имя',access:{status:'available'}},{business_id:'two',business_name:'Одинаковое имя',access:{status:'available'}}]}]}));
 render(<MemoryRouter><Routes><Route element={<Outlet context={{currentBusinessId:'network',controlScope:{kind:'network',id:'network'},businesses:[{id:'one',address:'Первый адрес'},{id:'two',address:'Второй адрес'}],onControlScopeChange:vi.fn()}}/>}><Route index element={<GrowthPathsPage/>}/></Route></Routes></MemoryRouter>);
 expect(await screen.findByText('Первый адрес')).toBeInTheDocument();
 expect(screen.getByRole('button',{name:'Открыть контент: Одинаковое имя, Первый адрес'})).toBeInTheDocument();
 expect(screen.getByRole('button',{name:'Открыть контент: Одинаковое имя, Второй адрес'})).toBeInTheDocument();
});
