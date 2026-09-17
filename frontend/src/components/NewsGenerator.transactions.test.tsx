import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { en } from '@/i18n/locales/en';
import NewsGenerator from './NewsGenerator';

vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'en', t: en }) }));

function ContextRoute() {
  return <Outlet context={{ user: { id: 'owner', demo_mode: false } }} />;
}

describe('news generated from transactions', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      success: true,
      news: [], examples: [],
      transactions: [
        { id: 'without-services', transaction_date: '2026-09-17', amount: 1500 },
        { id: 'with-services', transaction_date: '2026-09-16', amount: 2000, services: ['Haircut'] },
      ],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));
  });
  afterEach(() => vi.unstubAllGlobals());

  it('uses the translated fallback for a transaction without services and keeps the selector usable', async () => {
    render(<MemoryRouter><Routes><Route element={<ContextRoute />}>
      <Route index element={<NewsGenerator services={[]} businessId="business-1" />} />
    </Route></Routes></MemoryRouter>);
    fireEvent.click(screen.getByRole('checkbox', { name: en.dashboard.card.newsGenerator.generateFromTransaction }));
    const fallback = await screen.findByRole('option', { name: `2026-09-17 - ${en.dashboard.card.services} - 1500₽` });
    expect(fallback).toHaveValue('without-services');
    expect(screen.getByRole('option', { name: '2026-09-16 - Haircut - 2000₽' })).toBeInTheDocument();
    const selector = fallback.closest('select');
    if (!selector) throw new Error('Transaction selector not rendered');
    fireEvent.change(selector, { target: { value: 'without-services' } });
    expect(selector).toHaveValue('without-services');
  });
});
