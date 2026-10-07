import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LEAD_JOURNEY_STORAGE_KEY, leadJourneyKeyForFlow } from '@/lib/leadJourney';
import LeadJourneyPage from './LeadJourneyPage';

vi.mock('@/components/SeoMeta', () => ({ default: () => null }));

describe('LeadJourneyPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.scrollTo = vi.fn();
    vi.unstubAllGlobals();
  });

  it('maps singular backend flow names to plural user-facing route keys', () => {
    expect(leadJourneyKeyForFlow('influencer')).toBe('influencers');
    expect(leadJourneyKeyForFlow('partnership')).toBe('partnerships');
    expect(leadJourneyKeyForFlow('maps')).toBe('maps');
    expect(leadJourneyKeyForFlow('content')).toBe('content');
  });

  it('shows four directions, reveals a result, and carries the choice into registration', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/growth']}><LeadJourneyPage /></MemoryRouter>);

    expect(screen.getByRole('button', { name: /Локальные авторы/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Бизнесы рядом/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Карты/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Контент/ })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Карты/ }));
    expect(await screen.findByRole('heading', { name: 'Первое исправление с понятным эффектом' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Показать первое исправление' }));
    expect(await screen.findByRole('heading', { name: 'Первое исправление определено' })).toBeInTheDocument();

    const registrationLink = screen.getByRole('link', { name: /Завершить действие/ });
    expect(registrationLink).toHaveAttribute('href', '/login?tab=register&source=lead_journey&journey=maps');
    await user.click(registrationLink);
    expect(window.localStorage.getItem(LEAD_JOURNEY_STORAGE_KEY)).toBe('maps');
  }, 15_000);

  it('opens an operator-selected content journey without asking to choose again', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/events')) return { ok: true, json: async () => ({ success: true }) };
      return {
        ok: true,
        json: async () => ({
          success: true,
          journey: {
            id: 'journey-content', status: 'preview', source: 'admin', selected_flow: 'content',
            business: { name: 'Студия' },
            opportunities: [
              { flow_type: 'content', entity_type: 'contentplanitem', entity_id: 'item-1', title: 'Как сохранить результат процедуры', summary: 'Полезная тема', reason: 'Подходит услугам студии', mechanic: 'Черновик и календарь', message_excerpt: 'После процедуры важно…' },
              { flow_type: 'maps', entity_type: 'card_audit', entity_id: 'audit-1', title: 'Карты', summary: 'Другой путь', reason: 'Позже' },
            ],
          },
        }),
      };
    }));

    render(<MemoryRouter initialEntries={['/start/content-token']}><Routes><Route path="/start/:token" element={<LeadJourneyPage />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Как сохранить результат процедуры' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Четыре пути к следующему результату' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Подготовить черновик' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Что ещё можно улучшить' })).toBeInTheDocument();
  });

  it('loads a tokenized preview without exposing contacts and keeps the token through registration', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/opportunities/')) {
        return { ok: true, json: async () => ({ success: true, preview: { partial_result: { mechanic: 'Бартер', message_excerpt: 'Здравствуйте!' } } }) };
      }
      if (url.endsWith('/events')) return { ok: true, json: async () => ({ success: true }) };
      return {
        ok: true,
        json: async () => ({
          success: true,
          journey: {
            id: 'journey-1', status: 'preview', source: 'outreach',
            business: { name: 'Студия', city: 'Казань', address: 'ул. Баумана, 1' },
            opportunities: [
              { flow_type: 'influencer', entity_type: 'creator_profile', entity_id: 'creator-1', title: 'Автор Анна', summary: 'Пишет о городе', reason: 'Подходит по географии', mechanic: 'Бартер', message_excerpt: 'Здравствуйте!' },
              { flow_type: 'partnership', entity_type: 'partner', entity_id: 'partner-1', title: 'Кофейня', summary: 'Бизнес рядом', reason: 'Общая аудитория' },
              { flow_type: 'maps', entity_type: 'card_audit', entity_id: 'audit-1', title: 'Добавить услугу', summary: 'Первый шаг', reason: 'Услуга не указана' },
            ],
          },
        }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/start/public-token']}><Routes><Route path="/start/:token" element={<LeadJourneyPage />} /></Routes></MemoryRouter>);

    await user.click(await screen.findByRole('button', { name: /Автор Анна/ }));
    await user.click(screen.getByRole('button', { name: 'Подготовить сообщение автору' }));

    expect(await screen.findByText('Бартер')).toBeInTheDocument();
    const registrationLink = screen.getByRole('link', { name: /Завершить действие/ });
    expect(registrationLink.getAttribute('href')).toContain('journey_token=public-token');
    expect(registrationLink.getAttribute('href')).toContain('business_name=%D0%A1%D1%82%D1%83%D0%B4%D0%B8%D1%8F');
    expect(screen.queryByText(/\+7999/)).not.toBeInTheDocument();
  }, 15_000);
});
