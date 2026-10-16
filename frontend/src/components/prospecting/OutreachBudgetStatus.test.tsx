import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OutreachBudgetStatus } from './OutreachBudgetStatus';
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: mocks.request } }));
describe('OutreachBudgetStatus', () => {
  beforeEach(() => { mocks.request.mockReset(); });
  it('shows manual mode and actual limits without starting preparation', async () => {
    mocks.request.mockResolvedValue({ success: true, limits: { daily_tokens: 100000, monthly_tokens: 300000, daily_calls: 20, operation_calls: 4 }, used: { daily_tokens: 1000, monthly_tokens: 2000, daily_calls: 1 }, warning: false });
    render(<OutreachBudgetStatus />);
    await screen.findByText(/За сутки:/);
    expect(screen.getByText(/только по вашей команде/)).toBeTruthy();
    expect(mocks.request).toHaveBeenCalledExactlyOnceWith('/admin/prospecting/ai-budget');
  });
  it('shows separate DeepSeek caps and its warning without starting AI', async () => {
    const giga = { limits: { daily_tokens: 100000, monthly_tokens: 300000, daily_calls: 20, operation_calls: 4 }, used: { daily_tokens: 0, monthly_tokens: 0, daily_calls: 0 }, warning: false };
    const deepseek = { limits: { daily_tokens: 300000, monthly_tokens: 1000000, daily_calls: 20, operation_calls: 4 }, used: { daily_tokens: 250000, monthly_tokens: 250000, daily_calls: 3 }, warning: true };
    mocks.request.mockResolvedValue({ success: true, ...giga, providers: { gigachat: giga, deepseek } });
    render(<OutreachBudgetStatus />);
    expect(await screen.findByRole('group', { name: 'DeepSeek' })).toBeTruthy();
    expect(screen.getByRole('alert').textContent).toContain('DeepSeek');
    expect(mocks.request).toHaveBeenCalledTimes(1);
  });
  it('makes an unavailable budget visible', async () => {
    mocks.request.mockRejectedValue(new Error('unavailable'));
    render(<OutreachBudgetStatus />);
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('генерации заблокированы'));
  });
});
