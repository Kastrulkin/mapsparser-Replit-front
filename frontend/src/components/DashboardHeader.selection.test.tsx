import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { DashboardHeader } from './DashboardHeader';
vi.mock('../contexts/CurrencyContext', () => ({useCurrency:()=>({currency:'RUB', setCurrency:vi.fn()})}));
vi.mock('../contexts/CurrencyContext.logic', () => ({useCurrency:()=>({currency:'RUB', setCurrency:vi.fn()})}));
vi.mock('./BusinessSwitcher', () => ({BusinessSwitcher:()=> <button>Бизнес</button>}));
vi.mock('./NetworkLocationsSwitcher', () => ({NetworkLocationsSwitcher:()=> <button>Точка</button>}));
vi.mock('./LanguageSwitcher', () => ({LanguageSwitcher:()=> <span>Русский</span>}));
it('does not duplicate the location choice with a scope selector', async () => {
  render(<MemoryRouter><LanguageProvider><DashboardHeader isSuperadmin
    user={{id:'owner', email:'owner@example.test', is_superadmin:true}}
    currentBusiness={{id:'network', network_id:'network', name:'Расчёска'}}
    onBusinessChange={()=>undefined} onControlScopeChange={()=>undefined}/></LanguageProvider></MemoryRouter>);
  expect(await screen.findByRole('button', {name:'Точка'})).toBeInTheDocument();
  expect(screen.getAllByRole('combobox')).toHaveLength(1);
  expect(screen.queryByText(/Текущая точка|NetID/)).not.toBeInTheDocument();
  expect(document.querySelector('header > div')).toHaveClass('flex-wrap');
});
