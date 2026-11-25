import { getPartnershipWorkspaceCopy } from '@/i18n/partnershipWorkspaceCopy';
import { demoWalkthroughCopy } from './demoWalkthroughCopy';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { DemoRoomPage, DemoRoute } from './DemoWorkspaces';
import { DemoContentPlanPage } from './DemoContentPlanPage';
import { DemoAgentsPage } from './DemoAgentsPage';
import { DemoReviews } from './DemoReviews';
afterEach(()=>{window.localStorage.clear();window.sessionStorage.clear();});
function start(area:'today'|'operator'|'influencers'|'journal'|'finance'|'progress'|'partnerships',demo=true){
 window.localStorage.setItem('language','ru');
 return render(<MemoryRouter><LanguageProvider><Routes><Route element={<Outlet context={{demoMode:demo}}/>}><Route index element={<DemoRoute area={area}><p>Private page</p></DemoRoute>}/><Route path="/dashboard/content" element={<DemoContentPlanPage/>}/></Route></Routes></LanguageProvider></MemoryRouter>);
}
describe('demo walkthrough promises',()=>{
 it.each(['today','operator'] satisfies ('today'|'operator')[])('%s opens the promised coat-care draft',async area=>{start(area);fireEvent.click(await screen.findByRole('link',{name:'Проверить материал'}));expect(await screen.findByRole('textbox',{name:'Текст'})).toHaveValue(demoWalkthroughCopy('ru').taskBody);expect(screen.getByRole('heading',{name:'Совет по уходу за шерстью после SPA-процедур'})).toBeInTheDocument();});
 it('keeps normal business screens intact',async()=>{start('today',false);expect(await screen.findByText('Private page')).toBeInTheDocument();expect(screen.queryByText('Следующий шаг')).not.toBeInTheDocument();});
 it('shows a creator offer without sending',async()=>{start('influencers');fireEvent.click(await screen.findByRole('button'));expect(screen.getByRole('button')).toHaveAttribute('aria-expanded','true');expect(screen.queryByText('demo_route_not_allowed')).not.toBeInTheDocument();});
 it('links dated observations to permanent knowledge',async()=>{start('journal');expect(await screen.findByRole('link',{name:'Знания о бизнесе'})).toHaveAttribute('href','/dashboard/profile?section=knowledge');expect(screen.getByText(/недоступен до пятницы/)).toBeInTheDocument();});
 it('shows finance without contradictory error states',async()=>{start('finance');expect(await screen.findByText('18 000 ₽')).toBeInTheDocument();expect(screen.queryByRole('alert')).not.toBeInTheDocument();expect(screen.queryByRole('link',{name:/чат/i})).not.toBeInTheDocument();});
 it('shows a clearly read-only demo room',async()=>{window.localStorage.setItem('language','ru');const view=render(<MemoryRouter><LanguageProvider><DemoRoomPage/></LanguageProvider></MemoryRouter>);expect(await screen.findByRole('note')).toHaveTextContent(/демо/i);expect(view.container.querySelectorAll('input,textarea,form')).toHaveLength(0);});
 it('opens the synthetic partnership directly from the menu route', async () => {
   start('partnerships');
   expect(await screen.findByRole('heading', { name: 'Ромашка' })).toBeVisible();
   expect(screen.getByRole('link', { name: getPartnershipWorkspaceCopy('ru').demoOpenRoom })).toHaveAttribute('href', '/demo/room');
   expect(screen.queryByText('Private page')).not.toBeInTheDocument();
 });
 it('shows the unanswered reviews used by the automation example', async () => {
   window.localStorage.setItem('language', 'ru');
   render(<MemoryRouter><LanguageProvider><DemoReviews /></LanguageProvider></MemoryRouter>);
   expect(await screen.findAllByRole('listitem')).toHaveLength(demoWalkthroughCopy('ru').reviewTexts.length);
   expect(screen.getByRole('link', { name: 'Открыть автоматизацию ответов' })).toHaveAttribute('href', '/dashboard/agents');
 });
 it('keeps an edited and reviewed draft when reopening it, and clears review after another edit', async () => {
   const view = start('today');
   fireEvent.click(await screen.findByRole('link', { name: 'Проверить материал' }));
   fireEvent.change(await screen.findByRole('textbox', { name: 'Текст' }), { target: { value: 'Проверенный текст' } });
   fireEvent.click(screen.getByRole('button', { name: 'Подтвердить проверку в демо' }));
   expect(screen.getByRole('status')).toHaveTextContent('Проверено владельцем');
   view.unmount();

   start('today');
   fireEvent.click(await screen.findByRole('link', { name: 'Проверить материал' }));
   const draft = await screen.findByRole('textbox', { name: 'Текст' });
   expect(draft).toHaveValue('Проверенный текст');
   expect(screen.getByRole('status')).toHaveTextContent('Проверено владельцем');
   fireEvent.change(draft, { target: { value: 'Новая редакция' } });
   expect(screen.queryByRole('status')).not.toBeInTheDocument();
   expect(screen.getByRole('button', { name: 'Подтвердить проверку в демо' })).toBeEnabled();
 });
 it('inspects and edits before explicit automation confirmation',async()=>{window.localStorage.setItem('language','ru');render(<LanguageProvider><DemoAgentsPage/></LanguageProvider>);fireEvent.click(await screen.findByRole('button',{name:'Запустить на примере'}));fireEvent.click(await screen.findByRole('button',{name:'Проверить черновики'}));expect(screen.getAllByRole('textbox')).toHaveLength(4);expect(screen.queryByText('Проверено владельцем · только в этой вкладке')).not.toBeInTheDocument();fireEvent.change(screen.getAllByRole('textbox')[0],{target:{value:'Исправленный ответ'}});fireEvent.click(screen.getByRole('button',{name:'Подтвердить проверку в демо'}));expect(document.querySelectorAll('time')).toHaveLength(2);expect(screen.getAllByText('Проверено владельцем · только в этой вкладке')).toHaveLength(1);});
});
