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
  it('opens the three-direction preview before registration', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Index />
      </MemoryRouter>,
    );

    const demoLink = screen.getByRole('link', { name: 'Посмотреть демо' });
    expect(demoLink).toHaveAttribute('href', '/growth');
    expect(screen.getByRole('link', { name: 'Посмотреть 3 возможности' })).toHaveAttribute('href', '/growth');
  }, 15_000);
});
