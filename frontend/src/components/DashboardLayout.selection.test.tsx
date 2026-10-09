import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useOutletContext } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
const auth=vi.hoisted(()=>({getCurrentUser:vi.fn(), makeRequest:vi.fn()}));
vi.mock('../lib/auth_new', ()=>({newAuth:auth, HttpError:Error}));
vi.mock('./DashboardHeader', ()=>({DashboardHeader:()=>null}));
vi.mock('./DashboardSidebar', ()=>({DashboardSidebar:()=>null}));
vi.mock('./guided-tour/GuidedTourProvider', ()=>({GuidedTourProvider:({children}:{children:ReactNode})=>children, DemoModeBanner:()=>null}));
import { DashboardLayout } from './DashboardLayout';
function Probe(){
  const {controlScope, currentBusinessId, onBusinessChange, onControlScopeChange}=useOutletContext<{currentBusinessId:string; controlScope:{kind:string; id:string}; onBusinessChange:(id:string)=>void; onControlScopeChange:(scope:{kind:'business'; id:string; name:string})=>void}>();
  return <><p>{controlScope.kind}:{controlScope.id}:{currentBusinessId}</p><button onClick={()=>onBusinessChange('network')}>Сеть</button><button onClick={()=>onControlScopeChange({kind:'business', id:'branch', name:'Филиал'})}>Филиал</button></>;
}
it('derives scope from the selected parent or branch, not stale storage', async()=>{
  localStorage.clear();
  localStorage.setItem('selectedBusinessId','branch');
  localStorage.setItem('dashboard_control_scope',JSON.stringify({kind:'network', id:'network', name:'Сеть'}));
  auth.getCurrentUser.mockResolvedValue({id:'owner', email:'owner@example.test', is_superadmin:true, businesses:[{id:'network',network_id:'network',name:'Сеть'},{id:'branch',network_id:'network',name:'Филиал'}]});
  render(<MemoryRouter initialEntries={['/dashboard']}><Routes><Route path="/dashboard" element={<DashboardLayout/>}><Route index element={<Probe/>}/></Route></Routes></MemoryRouter>);
  expect(await screen.findByText('business:branch:branch')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Сеть'}));
  await screen.findByText('network:network:network');
  fireEvent.click(screen.getByRole('button',{name:'Филиал'}));
  await screen.findByText('business:branch:branch');
  expect(JSON.parse(localStorage.getItem('dashboard_control_scope') || '{}').kind).toBe('business');
});
