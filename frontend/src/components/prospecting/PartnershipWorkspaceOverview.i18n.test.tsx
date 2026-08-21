import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { PartnershipWorkspaceOverview } from './PartnershipWorkspaceOverview';

describe('PartnershipWorkspaceOverview localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
  });

  it('renders the Greek partnership workspace without Cyrillic system copy', async () => {
    const { container } = render(
      <LanguageProvider>
        <PartnershipWorkspaceOverview
          workspaceView="pipeline"
          currentBusinessId="demo-business"
          rawLeadCount={0}
          pipelineLeadCount={1}
          visibleDraftsCount={8}
          visibleBatchesCount={0}
          visibleReactionsCount={0}
          onWorkspaceChange={vi.fn()}
        />
      </LanguageProvider>,
    );

    expect(await screen.findByRole('heading', { name: 'Κοινές ενέργειες' })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });
});
