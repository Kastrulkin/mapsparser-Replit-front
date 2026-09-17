import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';

import { OutreachEmailSetup } from './OutreachEmailSetup';

vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

describe('OutreachEmailSetup browser fill', () => {
  beforeEach(() => {
    vi.mocked(newAuth.makeRequest).mockReset();
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ success: true, sender_accounts: [] });
  });

  it('keeps a browser-filled email after a parent rerender', async () => {
    const view = render(<OutreachEmailSetup businessId="business-1" compact />);
    const emailInput = await screen.findByLabelText('Email отправителя') as HTMLInputElement;

    emailInput.value = 'riderracs@gmail.com';
    emailInput.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }));
    view.rerender(<OutreachEmailSetup businessId="business-1" compact />);

    expect(emailInput).toHaveValue('riderracs@gmail.com');
  });
});
