import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Loader2, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { newAuth } from '@/lib/auth_new';

type CrmRequest = {
  id: string;
  business_id: string;
  business_name?: string;
  crm_name: string;
  crm_url?: string;
  contact?: string;
  note?: string;
  status: string;
  demand_count?: number;
  created_at?: string;
};

const statuses = [
  { value: 'open', label: 'Запрос получен' },
  { value: 'reviewing', label: 'Изучаем подключение' },
  { value: 'planned', label: 'Запланировано' },
  { value: 'connected', label: 'Подключено' },
  { value: 'closed', label: 'Закрыто' },
  { value: 'declined', label: 'Не поддерживаем' },
];

export const CrmIntegrationRequestsAdmin = () => {
  const [items, setItems] = useState<CrmRequest[]>([]);
  const [filter, setFilter] = useState('active');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const suffix = filter === 'active' ? '' : `?status=${encodeURIComponent(filter)}`;
      const result = await newAuth.makeRequest(`/admin/crm-integration-requests${suffix}`, { method: 'GET' });
      setItems(Array.isArray(result?.requests) ? result.requests : []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить CRM-запросы.');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { void load(); }, [load]);

  const visibleItems = useMemo(() => filter === 'active'
    ? items.filter((item) => ['open', 'reviewing', 'planned'].includes(item.status))
    : items, [filter, items]);

  const updateStatus = async (item: CrmRequest, status: string) => {
    setBusyId(item.id);
    setError('');
    try {
      const result = await newAuth.makeRequest(`/admin/crm-integration-requests/${item.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
      setItems((current) => current.map((value) => value.id === item.id ? result.request : value));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось изменить статус.');
    } finally {
      setBusyId('');
    }
  };

  return (
    <div className="space-y-4 p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div><h3 className="text-balance text-base font-semibold text-slate-950">Какие CRM просят подключить</h3><p className="mt-1 text-pretty text-sm text-slate-600">Спрос сгруппирован по CRM, а статус виден пользователю в его бизнесе.</p></div>
        <div className="flex gap-2"><Select value={filter} onValueChange={setFilter}><SelectTrigger className="min-h-11 w-48"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="active">Активные</SelectItem>{statuses.map((status) => <SelectItem key={status.value} value={status.value}>{status.label}</SelectItem>)}</SelectContent></Select><Button type="button" variant="outline" size="icon" className="h-11 w-11" onClick={() => void load()} aria-label="Обновить"><RefreshCw className="h-4 w-4" /></Button></div>
      </div>
      {error ? <div role="alert" className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div> : null}
      {loading ? <div className="flex min-h-32 items-center justify-center text-sm text-slate-500"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Загружаем запросы…</div> : visibleItems.length ? <div className="divide-y divide-slate-100 rounded-2xl bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">{visibleItems.map((item) => <div key={item.id} className="grid gap-3 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_220px] lg:items-center"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><strong className="text-slate-950">{item.crm_name}</strong><span className="rounded-full bg-slate-100 px-2 py-1 text-xs tabular-nums text-slate-600">спрос: {item.demand_count || 1}</span></div><p className="mt-1 text-sm text-slate-600">{item.business_name || item.business_id}</p>{item.note ? <p className="mt-2 text-pretty text-sm text-slate-700">{item.note}</p> : null}<div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">{item.crm_url ? <a className="underline" href={item.crm_url} target="_blank" rel="noreferrer">Сайт CRM</a> : null}{item.contact ? <span>{item.contact}</span> : null}</div></div><Select value={item.status} disabled={busyId === item.id} onValueChange={(status) => void updateStatus(item, status)}><SelectTrigger className="min-h-11"><SelectValue /></SelectTrigger><SelectContent>{statuses.map((status) => <SelectItem key={status.value} value={status.value}>{status.label}</SelectItem>)}</SelectContent></Select></div>)}</div> : <div className="flex min-h-32 items-center justify-center rounded-2xl bg-emerald-50 text-sm text-emerald-800"><CheckCircle2 className="mr-2 h-4 w-4" />В этой очереди запросов нет.</div>}
    </div>
  );
};

export default CrmIntegrationRequestsAdmin;
