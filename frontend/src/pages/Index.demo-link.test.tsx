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

describe('Index demo entry', () => {
  it('opens the demo in a separate tab without replacing the landing page', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Index />
      </MemoryRouter>,
    );

    const demoLink = screen.getByRole('link', { name: 'Посмотреть демо' });
    expect(demoLink).toHaveAttribute('href', '/demo');
    expect(demoLink).toHaveAttribute('target', '_blank');
    expect(demoLink).toHaveAttribute('rel', 'noopener noreferrer');
  });
});
