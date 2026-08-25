import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { TooltipProvider } from '@/components/ui/tooltip';
import { DashboardSidebar } from './DashboardSidebar';

describe('DashboardSidebar localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
  });

  it('renders the core Greek demo navigation without English or Russian fallbacks', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/dashboard/content']}>
        <LanguageProvider>
          <TooltipProvider>
            <DashboardSidebar />
          </TooltipProvider>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: 'Χειριστής' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Περιεχόμενο' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Αυτοματοποίηση' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Κοινές ενέργειες' })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\b(?:Operator|Content|Agents|Partner Search)\b/);
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('shows promotion whenever the selected business has the server capability', async () => {
    window.localStorage.setItem('language', 'ru');
    render(
      <MemoryRouter initialEntries={['/dashboard/content']}>
        <LanguageProvider>
          <TooltipProvider>
            <DashboardSidebar creatorPromotionAvailable />
          </TooltipProvider>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: 'Продвижение' })).toHaveAttribute('href', '/dashboard/promotion');
    expect(screen.queryByRole('link', { name: 'Партнёрские акции' })).not.toBeInTheDocument();
  });
});
