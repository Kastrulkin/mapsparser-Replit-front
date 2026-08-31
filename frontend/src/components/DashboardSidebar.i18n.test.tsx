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

    expect(await screen.findByRole('link', { name: 'Σήμερα' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Χειριστής' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Διαδρομές ανάπτυξης' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ροή' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Αποτελέσματα' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Περισσότερα' })).toHaveAttribute('href', '/dashboard/more');
    expect(container.textContent).not.toMatch(/\b(?:Today|Operator|Growth paths|Feed|Results|More)\b/);
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('shows the guided more entry without requiring a business capability', async () => {
    window.localStorage.setItem('language', 'ru');
    render(
      <MemoryRouter initialEntries={['/dashboard/content']}>
        <LanguageProvider>
          <TooltipProvider>
            <DashboardSidebar />
          </TooltipProvider>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: 'Ещё' })).toHaveAttribute('href', '/dashboard/more');
    expect(screen.queryByRole('link', { name: 'Продвижение' })).not.toBeInTheDocument();
  });

  it('keeps chat-based operator control in the guided navigation', async () => {
    window.localStorage.setItem('language', 'ru');
    render(
      <MemoryRouter initialEntries={['/dashboard/today']}>
        <LanguageProvider>
          <TooltipProvider>
            <DashboardSidebar />
          </TooltipProvider>
        </LanguageProvider>
      </MemoryRouter>,
    );

    const links = await screen.findAllByRole('link');
    const labels = links.map((link) => link.textContent?.trim()).filter(Boolean);
    expect(screen.getByRole('link', { name: 'Оператор' })).toHaveAttribute('href', '/dashboard/operator');
    expect(labels.indexOf('Оператор')).toBeGreaterThan(labels.indexOf('Сегодня'));
    expect(labels.indexOf('Оператор')).toBeLessThan(labels.indexOf('Пути роста'));
  });
});
