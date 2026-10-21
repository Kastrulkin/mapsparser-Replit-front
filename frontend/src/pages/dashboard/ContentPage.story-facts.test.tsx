import userEvent from '@testing-library/user-event';
import { fireEvent, render, screen } from '@testing-library/react';
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
  it('enlarges the selected photo and returns to the unsaved publication text', async () => {
    const originalRequest = vi.mocked(newAuth.makeRequest).getMockImplementation();
    const photoPlan = { ...storyPlan, items: [{ ...storyPlan.items[0], draft_text: 'Исходный текст.', metadata_json: { generation_source: 'manual' } }] };
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/content-plans?')) return { plans: [photoPlan] };
      if (path === '/content-plans/plan-1') return { plan: photoPlan };
      if (path.startsWith('/media-intelligence/posts/')) return { recommendation: { status: 'ready', selected_asset: { id: 'photo-1', original_url: 'https://example.test/reference.jpg', why: 'Фото выбранного изделия' }, alternatives: [] } };
      return originalRequest?.(path);
    });
    render(
      <MemoryRouter initialEntries={['/dashboard/content?plan_id=plan-1&item_id=item-1']}>
        <LanguageProvider><Routes><Route element={<ContextRoute />}><Route path="/dashboard/content" element={<ContentPage />} /></Route></Routes></LanguageProvider>
      </MemoryRouter>,
    );
    const user = userEvent.setup();
    const text = await screen.findByRole('textbox', { name: 'Текст публикации' });
    await user.clear(text);
    await user.type(text, 'Несохранённый текст для проверки фото');
    await user.click(await screen.findByRole('button', { name: 'Увеличить фото публикации' }));
    expect(await screen.findByRole('dialog', { name: 'Фото публикации', exact: true })).toBeVisible();
    expect(screen.getByRole('img', { name: 'Фото публикации крупно' })).toHaveAttribute('src', 'https://example.test/reference.jpg');
    await user.click(screen.getByRole('button', { name: 'Закрыть фото', exact: true }));
    expect(screen.queryByRole('dialog', { name: 'Фото публикации', exact: true })).not.toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Текст публикации' })).toHaveValue('Несохранённый текст для проверки фото');
    expect(screen.getByRole('button', { name: 'Увеличить фото публикации' })).toHaveFocus();
  });

  it('requires a deliberate choice before discarding publication edits', async () => {
    render(<MemoryRouter initialEntries={['/dashboard/content?plan_id=plan-1&item_id=item-1']}><LanguageProvider><Routes><Route element={<ContextRoute />}><Route path="/dashboard/content" element={<ContentPage />} /></Route></Routes></LanguageProvider></MemoryRouter>);
    const user = userEvent.setup();
    await user.type(await screen.findByRole('textbox', { name: 'Текст публикации' }), 'Несохранённый текст');
    await user.click(screen.getByRole('button', { name: 'Закрыть', exact: true }));
    expect(await screen.findByRole('alertdialog', { name: 'Закрыть без сохранения?' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Продолжить редактирование' }));
    expect(screen.getByRole('textbox', { name: 'Текст публикации' })).toHaveValue('Несохранённый текст');
    await user.click(screen.getByRole('button', { name: 'Закрыть', exact: true }));
    await user.click(screen.getByRole('button', { name: 'Не сохранять и закрыть' }));
    expect(screen.queryByRole('dialog', { name: 'Публикация' })).not.toBeInTheDocument();
    expect(vi.mocked(newAuth.makeRequest).mock.calls.some(([, options]) => options?.method && options.method !== 'GET')).toBe(false);
  });

  it('explains an unavailable enlarged photo, allows retry and keeps unsaved text', async () => {
    const originalRequest = vi.mocked(newAuth.makeRequest).getMockImplementation();
    const photoPlan = { ...storyPlan, items: [{ ...storyPlan.items[0], draft_text: 'Исходный текст.', metadata_json: { generation_source: 'manual' } }] };
    vi.mocked(newAuth.makeRequest).mockImplementation(async path => {
      if (path.startsWith('/content-plans?')) return { plans: [photoPlan] };
      if (path === '/content-plans/plan-1') return { plan: photoPlan };
      if (path.startsWith('/media-intelligence/posts/')) return { recommendation: { status: 'ready', selected_asset: { id: 'photo-1', original_url: 'https://example.test/missing.jpg' }, alternatives: [] } };
      return originalRequest?.(path);
    });
    render(<MemoryRouter initialEntries={['/dashboard/content?plan_id=plan-1&item_id=item-1']}><LanguageProvider><Routes><Route element={<ContextRoute />}><Route path="/dashboard/content" element={<ContentPage />} /></Route></Routes></LanguageProvider></MemoryRouter>);
    const user = userEvent.setup();
    const text = await screen.findByRole('textbox', { name: 'Текст публикации' });
    await user.clear(text); await user.type(text, 'Не терять правку при ошибке фото');
    await user.click(await screen.findByRole('button', { name: 'Увеличить фото публикации' }));
    fireEvent.error(screen.getByRole('img', { name: 'Фото публикации крупно' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить фото');
    await user.click(screen.getByRole('button', { name: 'Повторить загрузку фото' }));
    expect(screen.getByRole('img', { name: 'Фото публикации крупно' })).toHaveAttribute('src', 'https://example.test/missing.jpg');
    await user.click(screen.getByRole('button', { name: 'Закрыть фото', exact: true }));
    expect(screen.getByRole('textbox', { name: 'Текст публикации' })).toHaveValue('Не терять правку при ошибке фото');
  });
});
