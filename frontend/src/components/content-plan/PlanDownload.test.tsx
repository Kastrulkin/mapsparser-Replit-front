import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PlanDownload } from './PlanDownload';
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: mocks.request } }));
describe('Plan download', () => {
  beforeEach(() => mocks.request.mockReset());
  it('exports the saved plan and clears links when the plan changes', async () => {
    mocks.request.mockResolvedValue({ download_url: '/file/one', filename: 'one.pdf' });
    const view = render(<PlanDownload planId="one" />);
    fireEvent.click(screen.getByText('PDF'));
    await screen.findByText('Сохранить файл');
    expect(mocks.request).toHaveBeenCalledWith('/content-plans/one/export', { method: 'POST', body: '{"format":"pdf"}' });
    view.rerender(<PlanDownload planId="two" />);
    await waitFor(() => expect(screen.queryByText('Сохранить файл')).toBeNull());
  });
  it('requires saving edits first', () => {
    render(<PlanDownload planId="one" dirty />);
    expect(screen.getByText('Excel')).toBeDisabled();
    expect(screen.getByText(/Сначала сохраните/)).toBeVisible();
  });
  it('does not show a late response from another scope', async () => {
    let finish: (value: unknown) => void = () => {};
    mocks.request.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const view = render(<PlanDownload planId="one" />);
    fireEvent.click(screen.getByText('PDF'));
    view.rerender(<PlanDownload planId="two" />);
    finish({ download_url: '/private-one', filename: 'one.pdf' });
    await waitFor(() => expect(screen.queryByText('Сохранить файл')).toBeNull());
  });
});
