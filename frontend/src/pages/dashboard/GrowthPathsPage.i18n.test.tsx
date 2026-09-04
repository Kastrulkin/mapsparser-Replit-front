import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { GrowthPathsPage } from './GrowthPathsPage';

vi.mock('@/i18n/LanguageContext', () => ({
  useLanguage: () => ({ language: 'es' }),
}));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));

const Context = () => <Outlet context={{ currentBusinessId: 'business-1' }} />;

describe('GrowthPathsPage Spanish localization', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders six human-language directions in Spanish without a separate map-content direction', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      paths: [
        { flow_type: 'maps', title: 'Карты', status: 'not_started', opportunity: 'Исправить карточку', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть карты', cta_target: { screen: 'progress' } } },
        { flow_type: 'maps_content', title: 'Контент для карточек', status: 'not_started', opportunity: 'Готовить новости', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть новости для карт', cta_target: { screen: 'card_news' } } },
        { flow_type: 'content', title: 'Контент', status: 'not_started', opportunity: 'Подготовить публикацию', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть контент', cta_target: { screen: 'content' } } },
        { flow_type: 'influencer', title: 'Инфлюенсеры', status: 'not_started', opportunity: 'Найти авторов', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть авторов', cta_target: { screen: 'influencers' } } },
        { flow_type: 'partnership', title: 'Партнёрства', status: 'not_started', opportunity: 'Найти партнёра', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть партнёров', cta_target: { screen: 'partnerships' } } },
        { flow_type: 'automation', title: 'Автоматизация', status: 'not_started', opportunity: 'Поручить задачи', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть автоматизацию', cta_target: { screen: 'agents' } } },
        { flow_type: 'average_ticket', title: 'Средний чек', status: 'not_started', opportunity: 'Собрать пакеты услуг', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть средний чек', cta_target: { screen: 'average_ticket' } } },
      ],
    });

    render(<MemoryRouter><Routes><Route element={<Context />}><Route index element={<GrowthPathsPage />} /></Route></Routes></MemoryRouter>);

    expect(await screen.findByRole('heading', { level: 1, name: 'Elige una dirección' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Pon tus fichas al día' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Encuentra creadores locales' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Encuentra negocios para recomendaros' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Deja de pensar cada vez qué publicar' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Descubre qué más ofrecer a cada cliente' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Quita de encima las tareas repetitivas' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Контент для карточек' })).not.toBeInTheDocument();
    expect(screen.getAllByText('Puedes empezar')).toHaveLength(6);
  });
});
