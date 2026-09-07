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
    expect(screen.getByRole('link', { name: 'Δημιουργοί' })).toHaveAttribute('href', '/dashboard/influencers');
    expect(container.querySelector('a[href="/dashboard/content"]')).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/influencers"]')).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/partnerships"]')).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/agents"]')).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/more"]')).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('keeps Growth Paths out of the stable Russian sidebar', async () => {
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
    expect(screen.queryByRole('link', { name: 'Пути роста' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Управление через чат' })).toHaveAttribute('href', '/dashboard/operator');
    expect(screen.getByRole('link', { name: 'Контент' })).toHaveAttribute('href', '/dashboard/content');
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
    expect(document.querySelector('a[href="/dashboard/content"]')).toBeInTheDocument();
    expect(document.querySelector('a[href="/dashboard/influencers"]')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'İçerik üreticileri' })).toHaveAttribute('href', '/dashboard/influencers');
    expect(document.querySelector('a[href="/dashboard/agents"]')).toBeInTheDocument();
  });
});
