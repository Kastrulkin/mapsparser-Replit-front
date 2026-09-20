import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { ManagedCardGrowthPanel, type ManagedCardGrowth } from './ManagedCardGrowthPanel';

vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

const growth: ManagedCardGrowth = {
  policy_version: '2026-09-11.1',
  goal: {
    value: 'bookings',
    label: 'Больше записей',
    status: 'recommended',
    options: [
      { value: 'bookings', label: 'Больше записей' },
      { value: 'inquiries', label: 'Больше обращений' },
    ],
  },
  card_state: {
    status: 'needs_attention',
    locations: [{
      business_id: 'business-1',
      business_name: 'Тестовая точка',
      critical: true,
      providers: [{
        provider: 'yandex',
        provider_label: 'Яндекс',
        source_state: 'observed',
        observed_at: '2026-09-11T08:00:00+00:00',
        facts: {
          category: { state: 'missing' },
          publications: { state: 'unknown' },
        },
        benchmark: { sample_size: 12, period_days: 90 },
      }],
    }],
  },
  measurement: { status: 'goal_not_confirmed', checkpoints: [] },
  next_actions: [{ id: 'next-1', title: 'Проверить путь записи', business_name: 'Тестовая точка', gate_label: 'Можно обратиться' }],
};

describe('ManagedCardGrowthPanel', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
    vi.mocked(newAuth.makeRequest).mockReset();
  });

  it('distinguishes missing and unknown evidence', async () => {
    render(<LanguageProvider><ManagedCardGrowthPanel businessId="business-1" growth={growth} onUpdated={vi.fn()} /></LanguageProvider>);

    await userEvent.click(await screen.findByText('Яндекс'));

    expect(screen.getByText('Нужно заполнить')).toBeInTheDocument();
    expect(screen.getByText('Нет данных')).toBeInTheDocument();
    expect(screen.getByText(/12 сопоставимых компаний/)).toBeInTheDocument();
  });

  it('confirms the recommended goal', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ success: true });
    const onUpdated = vi.fn();
    render(<LanguageProvider><ManagedCardGrowthPanel businessId="business-1" growth={growth} onUpdated={onUpdated} /></LanguageProvider>);

    await userEvent.click(await screen.findByRole('button', { name: 'Подтвердить цель' }));

    expect(newAuth.makeRequest).toHaveBeenCalledWith('/business/business-1/growth-goal', {
      method: 'PUT',
      body: JSON.stringify({ goal: 'bookings' }),
    });
    expect(onUpdated).toHaveBeenCalled();
  });

  it('uses localized fallback errors instead of leaking a legacy Russian error', async () => {
    window.localStorage.setItem('language', 'es');
    vi.mocked(newAuth.makeRequest).mockRejectedValue(new Error('Старая ошибка сервера'));
    render(<LanguageProvider><ManagedCardGrowthPanel businessId="business-1" growth={growth} onUpdated={vi.fn()} /></LanguageProvider>);

    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar objetivo' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar el objetivo');
    expect(screen.queryByText('Старая ошибка сервера')).not.toBeInTheDocument();
  });

  it('shows a localized empty state when no card locations are available', async () => {
    window.localStorage.setItem('language', 'es');
    const noLocations: ManagedCardGrowth = {
      ...growth,
      card_state: { status: 'needs_attention', locations: [] },
    };
    render(<LanguageProvider><ManagedCardGrowthPanel businessId="business-1" growth={noLocations} onUpdated={vi.fn()} /></LanguageProvider>);

    expect(await screen.findByText('Aún no se recibió el estado de las fichas.')).toBeInTheDocument();
  });

  it('localizes rating labels and does not expose a legacy disclaimer outside Russian', async () => {
    const legacyDisclaimer = 'Старое предупреждение о показателях';
    const originalLocation = growth.card_state?.locations?.[0];
    if (!originalLocation) throw new Error('Test growth fixture has no location');
    const originalProvider = originalLocation.providers[0];
    if (!originalProvider) throw new Error('Test growth fixture has no provider');
    const withBenchmark: ManagedCardGrowth = {
      ...growth,
      baseline: {
        status: 'observed',
        providers: { yandex: { views: 1, clicks: 1, actions: 1 } },
        disclaimer: legacyDisclaimer,
      },
      card_state: {
        ...growth.card_state,
        locations: [{
          ...originalLocation,
          providers: [{
            ...originalProvider,
            benchmark: {
              sample_size: 12,
              period_days: 90,
              metrics: { rating: { median: 4.5, p75: 4.8 } },
              disclaimer_code: 'relative_benchmark',
            },
          }],
        }],
      },
    };
    window.localStorage.setItem('language', 'es');
    render(<LanguageProvider><ManagedCardGrowthPanel businessId="business-1" growth={withBenchmark} onUpdated={vi.fn()} /></LanguageProvider>);

    const managedPanel = (await screen.findByRole('heading', { name: 'Objetivo y estado de las fichas' })).closest('section');
    if (!managedPanel) throw new Error('Managed card panel was not rendered');
    const providerSummary = within(managedPanel).getAllByText('Яндекс').map((element) => element.closest('summary')).find(Boolean);
    if (!providerSummary) throw new Error('Managed provider summary was not rendered');
    await userEvent.click(providerSummary);

    expect(screen.getByText(/Valoración: mediana 4,5/)).toBeInTheDocument();
    const baseline = screen.getByRole('heading', { name: 'Base de 28 días' }).parentElement?.parentElement;
    if (!baseline) throw new Error('Managed baseline was not rendered');
    expect(within(baseline).getByText('Abre la ficha para revisar el siguiente paso.')).toBeInTheDocument();
    expect(screen.queryByText(legacyDisclaimer)).not.toBeInTheDocument();
  });

  it('preserves a raw legacy disclaimer for Russian data without a code', async () => {
    const legacyDisclaimer = 'Старое предупреждение о показателях';
    const legacy: ManagedCardGrowth = {
      ...growth,
      baseline: {
        status: 'observed',
        providers: { yandex: { views: 1, clicks: 1, actions: 1 } },
        disclaimer: legacyDisclaimer,
      },
    };
    render(<LanguageProvider><ManagedCardGrowthPanel businessId="business-1" growth={legacy} onUpdated={vi.fn()} /></LanguageProvider>);

    expect(await screen.findByText(legacyDisclaimer)).toBeInTheDocument();
  });
});
