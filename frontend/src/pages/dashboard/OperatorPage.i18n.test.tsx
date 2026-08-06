import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { OperatorPage } from './OperatorPage';

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const summary = {
  attention_items: [
    {
      id: 'pending_news',
      severity: 'medium',
      title: 'Черновики новостей ждут решения',
      description: 'Проверьте сохранённые материалы перед публикацией или дальнейшей работой.',
      count: 4,
    },
    {
      id: 'map_data_stale',
      severity: 'low',
      title: 'Данные карт стоит обновить',
      description: 'Сейчас показаны последние известные данные. Обновление карт относится к платным внешним действиям.',
      count: 40,
    },
  ],
  metrics: [
    { key: 'provider_rating', label: 'Рейтинг на карте', value: 4.5, source_label: 'Карты' },
    { key: 'provider_reviews_total', label: 'Отзывов на карте', value: 1063, source_label: 'Карты' },
    { key: 'imported_reviews_total', label: 'Загружено в LocalOS', value: 0, source_label: 'Отзывы LocalOS' },
  ],
  data_warnings: [
    'На карте указано 1063 отзывов, в LocalOS загружено 0. Это разные показатели; для полного списка нужно обновить данные.',
  ],
};

const ContextRoute = () => (
  <Outlet context={{ currentBusinessId: 'demo-business', currentBusiness: { id: 'demo-business', name: 'Demo Business' } }} />
);

describe('OperatorPage localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/operator/summary') {
        return Promise.resolve({ data: { summary } });
      }
      return Promise.resolve({ data: { messages: [], conversation: null } });
    });
  });

  it('renders Greek system copy even when the structured summary contains Russian labels', async () => {
    const { container } = render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<OperatorPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Χειριστής' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Τα δεδομένα χαρτών χρειάζονται ενημέρωση · 40')).toBeInTheDocument());
    expect(screen.getByText('Τα προσχέδια ειδήσεων χρειάζονται απόφαση · 4')).toBeInTheDocument();
    expect(screen.getByText(/Βαθμολογία στον χάρτη:/)).toBeInTheDocument();
    expect(screen.getByText(/Κριτικές στους χάρτες:/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Αναφορά προβλήματος' })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
    expect(container.textContent).not.toContain('News drafts need a decision');
    expect(container.textContent).not.toContain('Map data should be updated');
  });
});
