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
      <Route path="/dashboard/partnerships" element={<div>Существующие партнёрства</div>} />
    </Routes>
  </MemoryRouter>,
);

describe('PromotionHubPage', () => {
  it('separates partnerships from local creator promotion', () => {
    renderHub();

    expect(screen.getByRole('heading', { name: 'Продвижение' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Партнёрские акции/ })).toHaveAttribute('href', '/dashboard/promotion/partnerships');
    expect(screen.getByRole('link', { name: /Локальные авторы/ })).toHaveAttribute('href', '/dashboard/promotion/influencers');
    expect(screen.getByText(/ничего не отправляют/)).toBeInTheDocument();
  });

  it('keeps the hidden pilot on the existing partnerships route', async () => {
    renderHub(false);

    expect(await screen.findByText('Существующие партнёрства')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Продвижение' })).not.toBeInTheDocument();
  });
});
