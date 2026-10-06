import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PartnershipDraftsSection } from './PartnershipOperationalSections';

describe('search-only partner drafts', () => {
  it('keeps unverified search drafts visible but unavailable for sending', () => {
    const noop = vi.fn();
    render(<PartnershipDraftsSection
      drafts={[{ id: 'draft-1', lead_id: 'lead-1', lead_name: 'Agency One', channel: 'email',
        email: 'info@agency.example', status: 'generated', generated_text: 'Draft body',
        learning_note_json: { search_task_id: 'search-1', manual_review_required: true } }]}
      selectedDraftIds={[]}
      draftView="all"
      draftViewOptions={[{ value: 'all', label: 'Все' }]}
      loading={false}
      onDraftViewChange={noop}
      onRefresh={noop}
      onBulkApprove={noop}
      onBulkDelete={noop}
      onToggleAll={noop}
      onToggleDraft={noop}
      onDraftTextChange={noop}
      onApproveDraft={noop}
    />);
    expect(screen.getByText(/Компания и контакт ещё не подтверждены/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'После проверки' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Утвердить для отправки' })).toBeDisabled();
  });
});
