import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, useLocation } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { GuidedTourProvider } from './GuidedTourProvider';
import { GUIDED_TOUR_VERSION } from './tourConfig';
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('@/lib/auth_new', () => ({ newAuth: {
  makeRequest: vi.fn((path: string, options?: RequestInit) => {
    if (path.endsWith('/events')) return new Promise(() => undefined);
    if (options?.method === 'GET') return Promise.resolve({progress:{tour_version:GUIDED_TOUR_VERSION,status:'active',step_key:'today-nav',completed_steps:['welcome']}});
    return Promise.resolve({success:true});
  }),
} }));
const Location = () => <p>Route: {useLocation().pathname}</p>;
it('opens the next screen even when event recording has not responded', async () => {
  const user=userEvent.setup();
  render(<MemoryRouter initialEntries={['/dashboard/today']}>
    <GuidedTourProvider user={{id:'demo-slow-events',email:'demo@example.test',demo_mode:true}}><Location /></GuidedTourProvider>
  </MemoryRouter>);
  await user.click(await screen.findByRole('button',{name:'Дальше'}));
  await screen.findByRole('heading',{name:'Следующий шаг'});
  await user.click(screen.getByRole('button',{name:'Дальше'}));
  expect(await screen.findByText('Route: /dashboard/operator')).toBeVisible();
});

it('returns to the step route even when its menu target exists on another screen', async () => {
  const scroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype,'scrollIntoView');
  Object.defineProperty(HTMLElement.prototype,'scrollIntoView',{configurable:true,value:vi.fn()});
  const rect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(new DOMRect(0,0,120,40));
  const user = userEvent.setup();
  try {
    render(<MemoryRouter initialEntries={['/dashboard/today']}>
      <GuidedTourProvider user={{id:'demo-return',email:'demo@example.test',demo_mode:true}}>
        <span data-tour-target="nav-today">Сегодня в меню</span>
        <Link to="/dashboard/content">Открыть материал</Link><Location />
      </GuidedTourProvider>
    </MemoryRouter>);
    await screen.findByRole('button',{name:'Дальше'});
    await user.click(screen.getByRole('link',{name:'Открыть материал'}));
    expect(await screen.findByText('Route: /dashboard/content')).toBeVisible();
    await user.click(await screen.findByRole('button',{name:'Вернуться к шагу'}));
    expect(await screen.findByText('Route: /dashboard/today')).toBeVisible();
  } finally { rect.mockRestore(); if(scroll) Object.defineProperty(HTMLElement.prototype,'scrollIntoView',scroll); else Reflect.deleteProperty(HTMLElement.prototype,'scrollIntoView'); }
});
