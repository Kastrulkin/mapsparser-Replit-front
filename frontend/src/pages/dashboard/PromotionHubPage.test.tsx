import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { PromotionHubPage } from './PromotionHubPage';


const AvailableContext = () => <Outlet context={{ currentBusinessId: 'business-1', currentBusiness: { creator_promotion_available: true } }} />;
const UnavailableContext = () => <Outlet context={{ currentBusinessId: 'business-1', currentBusiness: { creator_promotion_available: false } }} />;

const renderHub = (available = true) => render(
  <MemoryRouter initialEntries={['/dashboard/promotion']}>
    <Routes>
      <Route element={available ? <AvailableContext /> : <UnavailableContext />}>
        <Route path="/dashboard/promotion" element={<PromotionHubPage />} />
      </Route>
    </Routes>
  </MemoryRouter>,
);

describe('PromotionHubPage', () => {
  it('separates partnerships from local creator promotion', () => {
    renderHub();

    expect(screen.getByRole('heading', { name: 'Продвижение' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Партнёрские акции/ })).toHaveAttribute('href', '/dashboard/promotion/partnerships');
    expect(screen.getByRole('link', { name: /Локальные авторы/ })).toHaveAttribute('href', '/dashboard/influencers');
    expect(screen.getByText(/ничего не отправляют/)).toBeInTheDocument();
  });

  it('keeps the hub visible while unavailable creator promotion stays non-interactive', () => {
    renderHub(false);

    expect(screen.getByRole('heading', { name: 'Продвижение' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Партнёрские акции/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Локальные авторы/ })).not.toBeInTheDocument();
    expect(screen.getByText('Подключаем поэтапно')).toBeInTheDocument();
  });
});
