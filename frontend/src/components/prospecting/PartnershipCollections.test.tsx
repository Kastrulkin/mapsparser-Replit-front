import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { PartnershipCollections } from './PartnershipCollections';
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: mocks.request } }));
vi.mock('./PreparedPartnershipMessages', () => ({ PreparedPartnershipMessages: ({ businessId, searchTaskId, mobile }: { businessId: string; searchTaskId: string; mobile: boolean }) => <p>{businessId}:{searchTaskId}:{mobile ? 'mini' : 'web'}</p> }));
const collections = [{ id:'group1',business_id:'one',business_name:'Сеть',business_address:'Первая улица, 1',company_count:50,touch_count:200,prepared_count:50 }, {id:'group2',business_id:'two',business_name:'Сеть',business_address:'Вторая улица, 2',company_count:50,touch_count:200,prepared_count:50}];
beforeEach(() => { mocks.request.mockReset(); mocks.request.mockResolvedValue({ collections: [] }); });
afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });
it('shows both addresses and opens exactly the selected collection without silently choosing a point', async () => {
 render(<PartnershipCollections collections={collections} />);
 expect(screen.getAllByText('Компаний: 50 · Касаний: 200')).toHaveLength(2);
 expect(screen.queryByText('one:group1:web')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Открыть подборку · Вторая улица, 2'}));
 expect(screen.getByText('two:group2:web')).toBeVisible();
 fireEvent.click(screen.getByRole('button',{name:'Все подборки по точкам'}));
 expect(screen.getByRole('button',{name:'Открыть подборку · Первая улица, 1'})).toBeVisible();
 expect(mocks.request).not.toHaveBeenCalled();
});
it('preserves legacy results only when no saved collections exist', async () => {
 render(<PartnershipCollections collections={[]}><p>Действующие партнёры</p></PartnershipCollections>);
 expect(screen.getByText('Действующие партнёры')).toBeVisible();
});
it('uses the miniapp token and opens the latest collection for its point', async () => {
 sessionStorage.setItem('localos_mini_session','test-mini-session');
 const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({collections:[collections[1]]})});vi.stubGlobal('fetch',fetchMock);
 render(<PartnershipCollections businessId="two" mobile />);
 expect(await screen.findByText('two:group2:mini')).toBeVisible();
 expect(fetchMock).toHaveBeenCalledWith('/api/partnership/results?scope_type=business&scope_id=two',{headers:{Authorization:'Bearer test-mini-session','Content-Type':'application/json'}});
 expect(mocks.request).not.toHaveBeenCalled();
});
it('does not confuse a failed request with an empty collection', async () => {
 mocks.request.mockRejectedValue(new Error('Не удалось загрузить'));
 render(<PartnershipCollections businessId="one"><p>Писем пока нет</p></PartnershipCollections>);
 expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить');
 expect(screen.queryByText('Писем пока нет')).toBeNull();
});
it('ignores late results after switching the selected point', async () => {
 let resolveOld:(value:unknown)=>void=()=>{};
 mocks.request.mockImplementationOnce(()=>new Promise(resolve=>{resolveOld=resolve;})).mockResolvedValue({collections:[collections[1]]});
 const view=render(<PartnershipCollections businessId="one" />);
 view.rerender(<PartnershipCollections businessId="two" />);
 expect(await screen.findByText('two:group2:web')).toBeVisible();
 resolveOld({collections:[collections[0]]});
 await waitFor(()=>expect(screen.queryByText('one:group1:web')).toBeNull());
});
