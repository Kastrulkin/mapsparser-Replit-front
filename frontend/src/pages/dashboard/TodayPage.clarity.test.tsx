import { act, configure, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { newAuth } from '@/lib/auth_new';
import { TodayPage } from './TodayPage';
configure({asyncUtilTimeout:10000});
vi.mock('@/lib/auth_new',()=>({newAuth:{makeRequest:vi.fn()}}));
vi.mock('@/i18n/LanguageContext.logic',()=>({useLanguage:()=>({language:'ru'})}));
const base={as_of:'2026-10-11T10:00:00Z',active_work:[],changes_24h:[],completed_results:[]};
const task=(id:string,status:string)=>({id,title:`Задача ${id}`,status,description:'Проверьте готовый материал',flow:'content',action:{url:`/dashboard/content?item_id=${id}`}});
const Wrapper=({business='b1',kind='business'}:{business?:string;kind?:string})=><Outlet context={{currentBusinessId:business,controlScope:{kind,id:business}}}/>;
const Probe=()=>{const location=useLocation();return <p>{location.pathname+location.search}</p>};
const page=(business='b1',kind='business')=><MemoryRouter initialEntries={['/dashboard/today']}><Routes><Route element={<Wrapper business={business} kind={kind}/>}><Route path='/dashboard/today' element={<TodayPage/>}/><Route path='/dashboard/content' element={<Probe/>}/></Route></Routes></MemoryRouter>;
describe('Today clarity and context',()=>{
 beforeEach(()=>{vi.mocked(newAuth.makeRequest).mockReset();localStorage.clear()});
 it('shows one primary action, all three sections and no duplicate task',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValue({...base,work_sections:{needs_decision:[task('a','edited'),task('b','failed')],continue_work:[task('q','queued')],results:[]}});
  render(page());
  expect(await screen.findByRole('heading',{name:'Задача b'})).toBeInTheDocument();
  expect(screen.getAllByText('Задача b')).toHaveLength(1);
  expect(screen.getByRole('region',{name:'Следующий шаг'})).toBeInTheDocument();
  for(const name of ['Нужно ваше решение','Продолжить работу','Завершено'])expect(screen.getByRole('heading',{name})).toBeInTheDocument();
  expect(screen.getByText('Ожидает запуска')).toBeInTheDocument();
 });
 it('expands remaining supplied tasks using keyboard without refetching',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValue({...base,work_sections:{continue_work:['a','b','c','d','e'].map(id=>task(id,'queued'))}});
  render(page());await screen.findByText('Задача a');
  expect(screen.queryByText('Задача e')).not.toBeInTheDocument();
  screen.getByRole('button',{name:'Показать ещё (5)'}).focus();
  await userEvent.setup().keyboard('{Enter}');
  expect(screen.getByText('Задача e')).toBeInTheDocument();expect(newAuth.makeRequest).toHaveBeenCalledTimes(1);
 });
 it('does not promote a background queue to a primary task',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValue({...base,active_work:[{...task('q','in_progress'),work_status:'queued'}]});
  render(page());await screen.findByText('Задача q');
  expect(within(screen.getByRole('region',{name:'Следующий шаг'})).queryByText('Задача q')).not.toBeInTheDocument();
  expect(screen.getByText('Ожидает запуска')).toBeInTheDocument();
 });
 it('opens the exact material without submitting a command',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValue({...base,work_sections:{needs_decision:[task('a','edited')]}});
  render(page());fireEvent.click(await screen.findByRole('button',{name:'Проверить'}));
  expect(screen.getByText('/dashboard/content?item_id=a')).toBeInTheDocument();expect(newAuth.makeRequest).toHaveBeenCalledTimes(1);
 });
 it.each([401,403,404])('clears private work on HTTP %s',async status=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValueOnce({...base,work_sections:{needs_decision:[task('private','edited')]}}).mockRejectedValueOnce({status});
  render(page());await screen.findByText('Задача private');fireEvent.click(screen.getByRole('button',{name:'Обновить'}));
  await screen.findByText('Нет доступа к данным этого бизнеса. Проверьте вход и выбранный бизнес.');expect(screen.queryByText('Задача private')).not.toBeInTheDocument();
 });
 it('keeps current work on a transient error and retries',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValueOnce({...base,work_sections:{needs_decision:[task('a','edited')]}}).mockRejectedValueOnce({status:503}).mockResolvedValueOnce({...base,work_sections:{needs_decision:[task('b','edited')]}});
  render(page());await screen.findByText('Задача a');fireEvent.click(screen.getByRole('button',{name:'Обновить'}));
  await screen.findByRole('status');expect(screen.getByText('Задача a')).toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'Повторить'}));await screen.findByText('Задача b');
 });
 it('hides old work immediately and ignores a late response across scope kinds',async()=>{
  let late:(data:unknown)=>void=()=>undefined;
  vi.mocked(newAuth.makeRequest).mockResolvedValueOnce({...base,work_sections:{needs_decision:[task('old','edited')]}}).mockReturnValueOnce(new Promise(resolve=>{late=resolve})).mockResolvedValueOnce({...base,work_sections:{needs_decision:[task('new','edited')]}});
  const view=render(page('same'));await screen.findByText('Задача old');fireEvent.click(screen.getByRole('button',{name:'Обновить'}));
  view.rerender(page('same','network'));expect(screen.queryByText('Задача old')).not.toBeInTheDocument();await screen.findByText('Задача new');
  await act(async()=>{late({...base,work_sections:{needs_decision:[task('late','edited')]}})});expect(screen.queryByText('Задача late')).not.toBeInTheDocument();
 });
 it('does not invent empty work when a source is unavailable',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValue({...base,work_source_states:{content:{status:'error'}},active_work:[task('visible','queued')]});
  render(page());await screen.findByText('Задача visible');expect(screen.getByRole('status')).toHaveTextContent('Контент');
  expect(screen.queryByText('В доступных данных нет задач, ожидающих вашего решения.')).not.toBeInTheDocument();
 });
 it('excludes aggregates, undated results and setup stages while keeping evidence links',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValue({...base,completed_results:[{...task('counter','completed'),kind:'aggregate',occurred_at:base.as_of},task('undated','completed'),{...task('real','published'),occurred_at:base.as_of}]});
  render(page());await screen.findByRole('heading',{name:'Задача real'});expect(screen.queryByText('Задача counter')).not.toBeInTheDocument();expect(screen.queryByText('Задача undated')).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Посмотреть подтверждение: Задача real'})).toBeInTheDocument();
 });
 it('labels unknown status and source honestly and folds financial setup',async()=>{
  vi.mocked(newAuth.makeRequest).mockResolvedValue({...base,active_work:[{id:'x',title:'Новая задача',status:'alien',screen:'cards'}],data_health:{source:'alien_source'},data_rhythm:{next_due_at:'2026-07-01T00:00:00Z',completed_periods_8w:0}});
  render(page());await screen.findByText('Новая задача');expect(screen.getByText('Статус не уточнён')).toBeInTheDocument();
  const summary=screen.getByText('Данные для анализа');expect(summary.closest('details')).not.toHaveAttribute('open');
  expect(screen.getByText(/Источник не указан/)).toBeInTheDocument();expect(screen.getByText(/Просрочено:.*июл/)).toBeInTheDocument();
 });
 it('switches to the target point before navigating its task',async()=>{
  const businessChange=vi.fn(),scopeChange=vi.fn();
  vi.mocked(newAuth.makeRequest).mockResolvedValue({...base,work_sections:{needs_decision:[{...task('point','edited'),business_id:'point',business_name:'Филиал'}]}});
  const Context=()=> <Outlet context={{currentBusinessId:'parent',controlScope:{kind:'network',id:'parent'},onBusinessChange:businessChange,onControlScopeChange:scopeChange}}/>;
  render(<MemoryRouter initialEntries={['/dashboard/today']}><Routes><Route element={<Context/>}><Route path='/dashboard/today' element={<TodayPage/>}/><Route path='/dashboard/content' element={<Probe/>}/></Route></Routes></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button',{name:'Проверить'}));expect(businessChange).toHaveBeenCalledWith('point');expect(scopeChange).toHaveBeenCalledWith({kind:'business',id:'point',name:'Филиал'});expect(screen.getByText('/dashboard/content?item_id=point')).toBeInTheDocument();
 });
});
