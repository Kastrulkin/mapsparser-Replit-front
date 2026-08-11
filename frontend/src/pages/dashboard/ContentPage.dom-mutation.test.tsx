import { readFileSync } from 'node:fs';
import { useState } from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

function deferredResponse<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
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

  it('does not replace the selected business plan with a late response from the previous business', async () => {
    const oldContext = deferredResponse<{ context: Record<string, never> }>();
    const oldPlan = {
      ...plan,
      id: 'plan-old',
      items: [{ ...plan.items[0], id: 'item-old', theme: 'Старая точка — 7 августа', scheduled_for: '2026-08-07' }],
    };
    const newPlan = {
      ...plan,
      id: 'plan-new',
      items: [{ ...plan.items[0], id: 'item-new', theme: 'Текущая точка — 10 августа', scheduled_for: '2026-08-10' }],
    };

    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path === '/content-plans/context?business_id=business-old') return oldContext.promise;
      if (path === '/content-plans?business_id=business-old') return { plans: [oldPlan] };
      if (path === '/content-plans/plan-old') return { plan: oldPlan };
      if (path === '/content-plans/plan-old/social-posts') return { posts: [], summary: {} };
      if (path === '/content-plans/context?business_id=business-new') return { context: {} };
      if (path === '/content-plans?business_id=business-new') return { plans: [newPlan] };
      if (path === '/content-plans/plan-new') return { plan: newPlan };
      if (path === '/content-plans/plan-new/social-posts') return { posts: [], summary: {} };
      if (path.startsWith('/media-intelligence/posts/')) return { recommendation: null };
      return {};
    });

    const ContextRoute = () => {
      const [businessId, setBusinessId] = useState('business-old');
      return (
        <>
          <button type="button" onClick={() => setBusinessId('business-new')}>Switch business</button>
          <Outlet context={{
            currentBusinessId: businessId,
            currentBusiness: { id: businessId, name: businessId },
            demoMode: false,
          }} />
        </>
      );
    };

    render(
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

    fireEvent.click(await screen.findByRole('button', { name: 'Switch business' }));
    expect(await screen.findByRole('button', { name: /Текущая точка — 10 августа/ })).toBeInTheDocument();

    await act(async () => {
      oldContext.resolve({ context: {} });
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    });

    expect(newAuth.makeRequest).not.toHaveBeenCalledWith('/content-plans?business_id=business-old', { method: 'GET' });
    expect(screen.queryByRole('button', { name: /Старая точка — 7 августа/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Текущая точка — 10 августа/ })).toBeInTheDocument();
  });

  it('shows only items belonging to the selected location in a shared network plan', async () => {
    const networkPlan = {
      ...plan,
      items: [
        { ...plan.items[0], id: 'item-other', business_id: 'business-other', theme: 'Другая точка — 7 августа', scheduled_for: '2026-08-07' },
        { ...plan.items[0], id: 'item-1', business_id: 'business-1', theme: 'Выбранная точка — 10 августа', scheduled_for: '2026-08-10' },
      ],
    };
    const posts = [
      { id: 'post-other', content_plan_item_id: 'item-other', platform: 'yandex_maps', status: 'published' },
      { id: 'post-current', content_plan_item_id: 'item-1', platform: 'yandex_maps', status: 'published' },
    ];

    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/content-plans/context')) return { context: {} };
      if (path.startsWith('/content-plans?')) return { plans: [networkPlan] };
      if (path === '/content-plans/plan-1') return { plan: networkPlan };
      if (path === '/content-plans/plan-1/social-posts') return { posts, summary: { total: 2, published: 2 } };
      if (path.startsWith('/media-intelligence/posts/')) return { recommendation: null };
      return {};
    });

    renderContentPage();

    expect(await screen.findByRole('button', { name: /Выбранная точка — 10 августа/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Другая точка — 7 августа/ })).not.toBeInTheDocument();
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
        selected_channels: ['yandex_maps', 'google_business', 'telegram', 'vk', 'instagram', 'facebook'],
      },
      items: [{
        ...plan.items[0],
        metadata_json: {
          generation_source: 'manual',
          selected_channels: ['yandex_maps', 'telegram'],
        },
      }],
    };
    const itemPosts = ['yandex_maps', 'telegram'].map((platform, index) => ({
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
    fireEvent.click(await screen.findByRole('button', { name: 'Обновить версии для каналов' }));

    await waitFor(() => {
      expect(newAuth.makeRequest).toHaveBeenCalledWith('/content-plans/items/item-1', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          theme: 'Тестовая тема публикации',
          scheduled_for: '2026-08-10',
          draft_text: 'Готовый текст публикации.',
          selected_channels: ['yandex_maps', 'telegram'],
        }),
      }));
    });
    expect(newAuth.makeRequest).toHaveBeenCalledWith('/content-plans/social-posts/bulk-prepare', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({
        item_ids: ['item-1'],
        platforms: ['yandex_maps', 'telegram'],
        replace_platforms: true,
        force_variants: false,
      }),
    }));
  });

  it('requires platform preview before approval', async () => {
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/content-plans/context')) return { context: {} };
      if (path.startsWith('/content-plans?')) return { plans: [plan] };
      if (path === '/content-plans/plan-1') return { plan };
      if (path === '/content-plans/plan-1/social-posts') return { posts: [], summary: {} };
      if (path.startsWith('/media-intelligence/posts/')) return { recommendation: null };
      return {};
    });

    renderContentPage();
    fireEvent.click(await screen.findByRole('button', { name: /Тестовая тема публикации/ }));

    expect(await screen.findByRole('button', { name: 'Подготовить версии для каналов' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Утвердить' })).not.toBeInTheDocument();
  });
});
