import { readFileSync } from 'node:fs';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { ContentPage } from './ContentPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    getToken: vi.fn(() => ''),
    makeRequest: vi.fn(),
  },
}));

const plan = {
  id: 'plan-1',
  period_days: 30,
  items: [{
    id: 'item-1',
    theme: 'Тестовая тема публикации',
    draft_text: 'Готовый текст публикации.',
    scheduled_for: '2026-08-08',
    metadata_json: { generation_source: 'manual' },
  }],
};

function renderContentPage() {
  const ContextRoute = () => (
    <Outlet context={{
      currentBusinessId: 'business-1',
      currentBusiness: { id: 'business-1', name: 'Тестовый бизнес' },
      demoMode: false,
    }} />
  );

  return render(
    <MemoryRouter initialEntries={['/dashboard/content']}>
      <LanguageProvider>
        <Routes>
          <Route element={<ContextRoute />}>
            <Route path="/dashboard/content" element={<ContentPage />} />
          </Route>
        </Routes>
      </LanguageProvider>
    </MemoryRouter>,
  );
}

describe('Content page DOM ownership', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
    document.documentElement.removeAttribute('translate');

    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/content-plans/context')) return { context: {} };
      if (path.startsWith('/content-plans?')) return { plans: [plan] };
      if (path === '/content-plans/plan-1') return { plan };
      if (path === '/content-plans/plan-1/social-posts') return { posts: [], summary: {} };
      if (path.startsWith('/media-intelligence/posts/')) return { recommendation: null };
      if (path.endsWith('/generate-draft')) return new Promise(() => undefined);
      return {};
    });
  });

  it('does not crash when a browser translator encounters a draft action label', async () => {
    const indexHtml = readFileSync('index.html', 'utf8');
    if (/<html[^>]*\btranslate=["']no["']/i.test(indexHtml)) {
      document.documentElement.setAttribute('translate', 'no');
    }

    renderContentPage();
    fireEvent.click(await screen.findByRole('button', { name: /Тестовая тема публикации/ }));
    const generateButton = await screen.findByRole('button', { name: 'Сгенерировать заново' });

    if (!generateButton.closest('[translate="no"]')) {
      const textNode = Array.from(generateButton.childNodes).find((node) => (
        node.nodeType === Node.TEXT_NODE && node.textContent?.includes('Сгенерировать заново')
      ));
      expect(textNode).toBeDefined();
      const translatedWrapper = document.createElement('font');
      generateButton.insertBefore(translatedWrapper, textNode!);
      translatedWrapper.appendChild(textNode!);
    }

    expect(() => fireEvent.click(generateButton)).not.toThrow();
  });
});

describe('Content page manual photo handoff', () => {
  it('offers the original photo for manual placement', () => {
    const source = readFileSync('src/pages/dashboard/ContentPage.tsx', 'utf-8');

    expect(source).toContain('variant=original');
    expect(source).toContain('Скачать оригинал');
    expect(source).toContain('Скачать фото');
    expect(source).toContain('Скопировать фото');
    expect(source).toContain('Исходное фото скачано без уменьшения качества.');
  });
});

describe('Content page publication settings', () => {
  it('keeps item channels and saves the changed date with the item', async () => {
    const itemPlan = {
      ...plan,
      generated_plan_json: {
        selected_channels: ['yandex_maps', 'two_gis', 'google_business', 'telegram', 'vk', 'instagram', 'facebook'],
      },
      items: [{
        ...plan.items[0],
        metadata_json: {
          generation_source: 'manual',
          selected_channels: ['yandex_maps', 'two_gis', 'telegram'],
        },
      }],
    };
    const itemPosts = ['yandex_maps', 'two_gis', 'telegram'].map((platform, index) => ({
      id: `post-${index + 1}`,
      content_plan_item_id: 'item-1',
      platform,
      status: 'needs_review',
      platform_text: 'Готовый текст публикации.',
    }));

    vi.mocked(newAuth.makeRequest).mockImplementation(async (path, options) => {
      if (path.startsWith('/content-plans/context')) return { context: {} };
      if (path.startsWith('/content-plans?')) return { plans: [itemPlan] };
      if (path === '/content-plans/plan-1') return { plan: itemPlan };
      if (path === '/content-plans/plan-1/social-posts') return { posts: itemPosts, summary: {} };
      if (path === '/content-plans/items/item-1' && options?.method === 'PUT') {
        return {
          plan: {
            ...itemPlan,
            items: [{
              ...itemPlan.items[0],
              scheduled_for: '2026-08-10',
            }],
          },
        };
      }
      if (path === '/content-plans/social-posts/bulk-prepare') {
        return { posts: itemPosts, removed_platforms: [], preserved_platforms: [] };
      }
      if (path.startsWith('/media-intelligence/posts/')) return { recommendation: null };
      return {};
    });

    renderContentPage();
    fireEvent.click(await screen.findByRole('button', { name: /Тестовая тема публикации/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Каналы/ }));

    expect(screen.getByRole('button', { name: 'Telegram' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'VK' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Instagram' })).toHaveAttribute('aria-pressed', 'false');

    fireEvent.change(screen.getByLabelText('Дата'), { target: { value: '2026-08-10' } });
    fireEvent.click(await screen.findByRole('button', { name: 'Сохранить изменения' }));

    await waitFor(() => {
      expect(newAuth.makeRequest).toHaveBeenCalledWith('/content-plans/items/item-1', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          theme: 'Тестовая тема публикации',
          scheduled_for: '2026-08-10',
          draft_text: 'Готовый текст публикации.',
          selected_channels: ['yandex_maps', 'two_gis', 'telegram'],
        }),
      }));
    });
  });
});
