import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { ClientCommunicationWorkspace } from './ClientCommunicationWorkspace';
vi.mock('@/components/AIAgentSettings', () => ({ AIAgentSettings: ({ businessId }: { businessId: string }) => <div>settings:{businessId}</div> }));
vi.mock('../ChatsPage', () => ({ ChatsPage: () => <div>live conversations</div>, EmployeeChatTest: () => <div>isolated test</div> }));
const open = (businessId = 'one', selectedId = 'one') => render(<MemoryRouter initialEntries={['/?section=clients']}><Routes><Route element={<Outlet context={{ currentBusinessId: businessId, currentBusiness: { id: selectedId } }} />}><Route index element={<ClientCommunicationWorkspace />} /></Route></Routes></MemoryRouter>);
describe('client communication workspace', () => {
  it('opens existing settings and separates testing from live dialogs', () => {
    open();
    expect(screen.getByText('settings:one')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Проверка ответов' }));
    expect(screen.getByText('isolated test')).toBeTruthy();
    expect(screen.queryByText('live conversations')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Диалоги' }));
    expect(screen.getByText('live conversations')).toBeTruthy();
    expect(screen.queryByText('isolated test')).toBeNull();
  });
  it('does not expose stale business settings during scope changes', () => {
    open('two', 'one');
    expect(screen.queryByText('settings:two')).toBeNull();
    expect(screen.getByRole('status')).toBeTruthy();
  });
});

it('keeps configuration out of the focused handoff screen',()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>Response.json({conversations:[]})));
 render(<MemoryRouter initialEntries={['/?section=clients&view=handoffs']}><Routes><Route element={<Outlet context={{currentBusinessId:'one',currentBusiness:{id:'one'}}}/>}><Route index element={<ClientCommunicationWorkspace/>}/></Route></Routes></MemoryRouter>);
 expect(screen.getByRole('heading',{name:'Сообщения клиентов'})).toBeVisible();
 expect(screen.queryByText(/Настройте ответы и правила работы/)).not.toBeInTheDocument();
 expect(screen.getByRole('button',{name:'Поведение и включение'})).not.toBeVisible();
 fireEvent.click(screen.getByText('Другие разделы общения'));
 expect(screen.getByRole('button',{name:'Поведение и включение'})).toBeVisible();
 fireEvent.click(screen.getByRole('button',{name:'Поведение и включение'}));
 expect(screen.getByText('settings:one')).toBeVisible();
});
