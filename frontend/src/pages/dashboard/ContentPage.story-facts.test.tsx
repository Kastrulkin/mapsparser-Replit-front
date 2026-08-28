import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ErrorBoundary } from '@/components/ErrorBoundary';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { ContentPage } from './ContentPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    getToken: vi.fn(() => ''),
    makeRequest: vi.fn(),
  },
}));

const storyPlan = {
  id: 'plan-1',
  period_days: 30,
  items: [{
    id: 'item-1',
    theme: 'История визита: как ребёнок освоился',
    draft_text: '',
    scheduled_for: '2026-08-28',
    metadata_json: {
      generation_source: 'needs_context',
      content_brief_v1: {
        missing_fields: ['story_facts'],
        questions: ['Что именно произошло во время визита?'],
        sources: [],
      },
      brief_answers: {},
    },
  }],
};

const ContextRoute = () => (
  <Outlet context={{
    currentBusinessId: 'business-1',
    currentBusiness: { id: 'business-1', name: 'Тестовый бизнес' },
    demoMode: false,
  }} />
);

describe('ContentPage story-facts deep link', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
    vi.mocked(newAuth.makeRequest).mockReset();
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/content-plans/context')) return { context: {} };
      if (path.startsWith('/content-plans?')) return { plans: [storyPlan] };
      if (path === '/content-plans/plan-1') return { plan: storyPlan };
      if (path === '/content-plans/plan-1/social-posts') return { posts: [], summary: {} };
      if (path.startsWith('/media-intelligence/posts/')) return { recommendation: null };
      return {};
    });
  });

  it('opens the requested publication and shows its facts form', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/content?plan_id=plan-1&item_id=item-1&focus=story_facts']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route
                path="/dashboard/content"
                element={(
                  <ErrorBoundary>
                    <ContentPage />
                  </ErrorBoundary>
                )}
              />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Нужно немного конкретики')).toBeInTheDocument();
    expect(screen.getByText('Что именно произошло во время визита?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Сохранить и подготовить текст' })).toBeInTheDocument();
  });
});
