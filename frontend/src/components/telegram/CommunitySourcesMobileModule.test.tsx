import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { CommunitySourcesMobileModule } from './CommunitySourcesMobileModule';


describe('CommunitySourcesMobileModule', () => {
  it('shows the included industry pulse before asking for personal sources', async () => {
    render(<CommunitySourcesMobileModule businessId="preview" />);

    expect(await screen.findByText('Бьюти-пульс уже включён')).toBeInTheDocument();
    expect(screen.getByText(/18/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Добавить свои источники' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Добавленные вами' })).toBeInTheDocument();
  });
});
