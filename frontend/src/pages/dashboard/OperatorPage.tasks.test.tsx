import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { OperatorPage } from './OperatorPage';

vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));
const Context = () => <Outlet context={{currentBusinessId:'business',currentBusiness:{id:'business',name:'Business'}}}/>;
const task = (id: string, name: string) => ({id,business_id:'business',display_name:name,status:'waiting_for_review',
  stage:'На паузе',config:{},state:{},report:{eligible:0},updated_at:'2026-10-13T09:00:00Z'});

it('refreshes new tasks when opened and retains the last list if refresh fails', async () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  localStorage.clear(); localStorage.setItem('language','ru');
  let reads=0;
  vi.mocked(api.get).mockImplementation(async url => {
    if(url==='/partnership/continuations') {
      reads+=1;
      if(reads>2) throw new Error('Temporary failure');
      return {data:{items:[task('old','Старый поиск'), ...(reads>1?[task('new','Новый поиск')]:[])]}};
    }
    return {data:{messages:[],conversation:null}};
  });
  render(<MemoryRouter><LanguageProvider><Routes><Route element={<Context/>}>
    <Route path="/" element={<OperatorPage/>}/>
  </Route></Routes></LanguageProvider></MemoryRouter>);
  await waitFor(()=>expect(reads).toBe(1));
  fireEvent.click(screen.getByRole('button',{name:'Задачи',exact:true}));
  expect(await screen.findByRole('button',{name:/Новый поиск/})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Close',exact:true}));
  fireEvent.click(screen.getByRole('button',{name:'Задачи',exact:true}));
  await waitFor(()=>expect(reads).toBe(3));
  expect(screen.getByRole('button',{name:/Новый поиск/})).toBeInTheDocument();
});
