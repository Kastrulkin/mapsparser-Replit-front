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
    expect(screen.getByRole('link', { name: 'Πράκτορες' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Αναζήτηση συνεργατών' })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\b(?:Operator|Content|Agents|Partner Search)\b/);
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });
});
