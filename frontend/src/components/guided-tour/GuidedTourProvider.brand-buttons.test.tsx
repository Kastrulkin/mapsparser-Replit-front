import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { DemoModeBanner, GuidedTourProvider } from './GuidedTourProvider';

vi.mock('@/i18n/LanguageContext', () => ({
  useLanguage: () => ({ language: 'ru' }),
}));
vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(async () => ({
      progress: { status: 'not_started', step_key: 'welcome', completed_steps: [] },
    })),
    deactivateDemoSession: vi.fn(),
  },
}));

describe('Guided tour public brand buttons', () => {
  it('uses the gold CTA for the guided-tour welcome action', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/operator']}>
        <GuidedTourProvider user={{ id: 'demo-user', demo_mode: true }}>
          <div>Dashboard</div>
        </GuidedTourProvider>
      </MemoryRouter>,
    );

    const start = await screen.findByRole('button', { name: /Начать/ });
    expect.soft(start).toHaveClass('btn-iridescent');
    expect.soft(start).toHaveClass('active:scale-[0.96]');
  });

  it('uses the same gold CTA and press state in the demo banner', () => {
    render(
      <MemoryRouter>
        <DemoModeBanner />
      </MemoryRouter>,
    );

    const createAccount = screen.getByRole('link');
    expect.soft(createAccount).toHaveClass('btn-iridescent');
    expect.soft(createAccount).toHaveClass('active:scale-[0.96]');
    expect.soft(createAccount).not.toHaveClass('active:scale-[0.98]');
  });
});
