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
    expect(container.querySelector('a[href="/dashboard/growth-paths"]')).not.toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/progress"]')).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/more"]')).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/content"]')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Профиль и бизнес' })).not.toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/finance"]')).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/chats"]')).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('shows the fixed grouped Russian navigation', async () => {
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
    expect(screen.getByRole('link', { name: 'Управление через чат' })).toHaveAttribute('href', '/dashboard/operator');
    expect(screen.queryByRole('link', { name: 'Пути роста' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Контент' })).toHaveAttribute('href', '/dashboard/content');
    expect(screen.getByRole('link', { name: 'Результаты' })).toHaveAttribute('href', '/dashboard/progress');
    expect(screen.getByRole('link', { name: 'Инфлюенсеры' })).toHaveAttribute('href', '/dashboard/influencers');
  });

  it('keeps direct work areas in the Turkish navigation', async () => {
    window.localStorage.setItem('language', 'tr');
    render(
      <MemoryRouter initialEntries={['/dashboard/today']}>
        <LanguageProvider>
          <TooltipProvider>
            <DashboardSidebar />
          </TooltipProvider>
        </LanguageProvider>
      </MemoryRouter>,
    );

    await screen.findAllByRole('link');
    expect(document.querySelector('a[href="/dashboard/growth-paths"]')).not.toBeInTheDocument();
    expect(document.querySelector('a[href="/dashboard/more"]')).toBeInTheDocument();
    expect(document.querySelector('a[href="/dashboard/progress"]')).toBeInTheDocument();
  });
});
