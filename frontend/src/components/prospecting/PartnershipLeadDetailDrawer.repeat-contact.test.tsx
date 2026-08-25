import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import PartnershipLeadDetailDrawer from './PartnershipLeadDetailDrawer';

describe('PartnershipLeadDetailDrawer repeat-contact warning', () => {
  it('shows the prior relationship and directs the operator to continue the dialogue', () => {
    render(
      <PartnershipLeadDetailDrawer
        selectedLead={{
          id: 'magic-mile',
          name: 'Волшебная миля',
          city: 'Санкт-Петербург',
          category: 'Семейный парк',
          partnership_stage: 'converted',
          sales_room_url: 'https://localos.pro/room/room-volshebnaya-milya',
          contact_guard: {
            blocked: true,
            reason: 'active_partnership',
            display_status: 'converted',
            warning: 'С партнёром уже был контакт — не начинайте знакомство заново',
            last_contact_at: '2026-08-03T12:00:00+03:00',
            last_contact_channel: 'digital_room',
          },
        }}
        stagePresentation={{ label: 'Договорились', tone: 'success' }}
        auditPresentation={{ label: 'Готов', primary: 'Данные собраны' }}
        onClose={vi.fn()}
        selectedLeadPhotos={[]}
        leadEdit={{
          name: 'Волшебная миля',
          city: 'Санкт-Петербург',
          category: 'Семейный парк',
          address: '',
          phone: '',
          email: 'info@magicmile.ru',
          website: '',
          telegram_url: '',
          whatsapp_url: '',
        }}
        setLeadEdit={vi.fn()}
        onSaveLeadContacts={vi.fn()}
        pilotCohortOptions={[]}
        onPilotCohortChange={vi.fn()}
      />,
    );

    expect(screen.getByText('С партнёром уже был контакт — не начинайте знакомство заново')).toBeInTheDocument();
    expect(screen.getByText(/03\.08\.2026/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Продолжить диалог' })).toHaveAttribute(
      'href',
      'https://localos.pro/room/room-volshebnaya-milya',
    );
    expect(screen.queryByRole('button', { name: /first touch|первое касание/i })).not.toBeInTheDocument();
  });
});
