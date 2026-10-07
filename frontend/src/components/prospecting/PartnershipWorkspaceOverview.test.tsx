import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { PartnershipWorkspaceOverview } from './PartnershipWorkspaceOverview';
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
afterEach(cleanup);
const props = { workspaceView: 'raw', rawLeadCount: 41, pipelineLeadCount: 0, visibleDraftsCount: 0, visibleBatchesCount: 0, visibleReactionsCount: 0, onWorkspaceChange: vi.fn() };
it('has one four-stage navigation without duplicate metric tiles or introductory panels', async () => {
  const change = vi.fn();
  render(<PartnershipWorkspaceOverview {...props} onWorkspaceChange={change} />);
  expect(within(screen.getByRole('navigation', { name: 'Этапы аутрича' })).getAllByRole('button')).toHaveLength(4);
  expect(screen.queryByText('Как запустить совместную акцию')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Компании.*41/ })).toHaveAttribute('aria-current', 'page');
  await userEvent.click(screen.getByRole('button', { name: /Письма/ }));
  expect(change).toHaveBeenCalledWith('drafts');
});
it('separates header and navigation so group status can sit above the stage content', () => {
  const view = render(<PartnershipWorkspaceOverview {...props} part="header" />);
  expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  view.rerender(<PartnershipWorkspaceOverview {...props} part="navigation" workspaceView="drafts" />);
  expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Письма/ })).toHaveAttribute('aria-current', 'page');
});
