import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PreparedCabinetInvite } from './PreparedCabinetInvite';
import { newAuth } from '@/lib/auth_new';
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
const sections = ['services','reviews','content','partnerships','influencers'].map(key => ({ key, label:key, href:'/dashboard/' + key, items:[{source_id:key+'-1',title:key+' title',text:key+' text'}] }));
beforeEach(() => vi.clearAllMocks());
describe('prepare an owner cabinet', () => {
  it('previews five existing sections and saves references with the observed version', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ version:'v1', saved:false, sections, requests:[], events:{} });
    render(<PreparedCabinetInvite businessId="business-a" disabled={false} />);
    fireEvent.click(screen.getByRole('button',{name:'Приглашение в подготовленный кабинет'}));
    await screen.findByText('services title');
    const save = screen.getByRole('button',{name:'Открыть выбранные материалы владельцу'});
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);
    await screen.findByText('Выбранные материалы доступны владельцу.');
    expect(newAuth.makeRequest).toHaveBeenCalledWith('/superadmin/businesses/business-a/prepared-cabinet', {
      method:'PUT',body:JSON.stringify({selection:Object.fromEntries(sections.map(section=>[section.key,[section.items[0].source_id]])),version:'v1'}),
    });
  });
  it('keeps the handoff disabled when any section is empty', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({version:'v1',saved:false,sections:sections.map(section=>section.key==='reviews'?{...section,items:[]}:section),requests:[],events:{}});
    render(<PreparedCabinetInvite businessId="business-a" disabled={false} />);
    fireEvent.click(screen.getByRole('button',{name:'Приглашение в подготовленный кабинет'}));
    await screen.findByText('services title');
    expect(screen.getByRole('button',{name:'Открыть выбранные материалы владельцу'})).toBeDisabled();
  });
});
