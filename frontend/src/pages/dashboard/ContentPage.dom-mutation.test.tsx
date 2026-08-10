import { readFileSync } from 'node:fs';

import { fireEvent, render, screen } from '@testing-library/react';
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
