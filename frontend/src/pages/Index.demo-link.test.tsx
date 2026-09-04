import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import Index from './Index';

vi.mock('@/components/Footer', () => ({ default: () => null }));
vi.mock('@/components/SeoMeta', () => ({ default: () => null }));
vi.mock('@/content/useLocalizedCollections', () => ({
  useLocalizedCases: () => ({ cases: [], isLoading: false }),
}));
vi.mock('@/i18n/LanguageContext', () => ({
  useLanguage: () => ({ language: 'ru' }),
}));

describe('Index lead journey entry', () => {
  it('opens the six-direction preview before registration', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Index />
      </MemoryRouter>,
    );

    const demoLink = screen.getByRole('link', { name: 'Посмотреть демо' });
    expect(demoLink).toHaveAttribute('href', '/demo');
    expect(demoLink).toHaveAttribute('target', '_blank');
    expect(demoLink).toHaveClass('btn-iridescent');
    const opportunitiesLink = screen.getByRole('link', { name: 'Выбрать из 6 направлений' });
    expect(opportunitiesLink).toHaveAttribute('href', '/growth');
    expect(opportunitiesLink).toHaveClass('btn-iridescent', 'min-h-20', 'w-full', 'justify-between');
    const tasksLink = screen.getByRole('link', { name: 'Посмотреть, что можно передать LocalOS' });
    expect(tasksLink).toHaveClass('min-h-20', 'w-full', 'justify-between');
  }, 15_000);
});
