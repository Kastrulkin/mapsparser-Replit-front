import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';
import { mobileJsonHeaders, readMobileJson } from '@/lib/mobileDataClient';
import { PreparedPartnershipMessages } from './PreparedPartnershipMessages';

export type PartnershipCollection = { id: string; business_id: string; business_name: string; business_address: string; company_count: number; touch_count: number; prepared_count: number; created_at?: string };
type Props = { collections?: PartnershipCollection[]; businessId?: string; mobile?: boolean; children?: ReactNode };
export function PartnershipCollections({ collections, businessId, mobile = false, children }: Props) {
  const [loaded, setLoaded] = useState<PartnershipCollection[] | null>(null);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const epoch = useRef(0);
  useEffect(() => {
    const version = ++epoch.current;
    setSelected(''); setLoaded(null); setError('');
    if (collections || !businessId) return;
    const path = `/partnership/results?scope_type=business&scope_id=${encodeURIComponent(businessId)}`;
    const request = mobile ? fetch(`/api${path}`, { headers: mobileJsonHeaders() }).then(readMobileJson<{ collections?: PartnershipCollection[] }>) : newAuth.makeRequest(path);
    void request.then(data => { if (epoch.current === version) { setLoaded(data.collections || []); setSelected(data.collections?.[0]?.id || ''); } }).catch(issue => { if (epoch.current === version) setError(issue instanceof Error ? issue.message : 'Не удалось загрузить подборки.'); });
    return () => { epoch.current++; };
  }, [collections, businessId, mobile, retry]);
  const items = collections || loaded;
  const current = items?.find(item => item.id === selected);
  if (error) return <div role="alert">{error}<Button variant="outline" onClick={() => setRetry(retry + 1)}>Повторить загрузку подборок</Button></div>;
  if (!items) return <p role="status">Загружаем сохранённые подборки…</p>;
  if (!items.length) return <>{children}</>;
  return <section aria-label="Подборки новых партнёров" className="space-y-4">
    {current ? <>
      <Button variant="outline" onClick={() => setSelected('')}>Все подборки по точкам</Button>
      <header className="space-y-1"><h2 className="text-xl font-semibold">{current.business_address || current.business_name}</h2><p className="text-sm text-muted-foreground">{current.business_name} · Компаний: {current.company_count} · Касаний: {current.touch_count}</p></header>
      <PreparedPartnershipMessages key={`${current.business_id}:${current.id}`} businessId={current.business_id} searchTaskId={current.id} mobile={mobile} />
    </> : <>
      <h2 className="text-xl font-semibold">Новые партнёры по точкам</h2>
      <p className="text-sm text-muted-foreground">Выберите адрес, чтобы посмотреть компании и готовые сообщения. Просмотр ничего не отправляет.</p>
      <div className="grid gap-3 sm:grid-cols-2">{items.map((item, index) => <article key={item.id} className="space-y-3 rounded-xl border border-border p-4">
        <h3 className="font-semibold">{item.business_address || item.business_name}</h3><p className="text-sm text-muted-foreground">{item.business_name}</p>
        <p>Компаний: {item.company_count} · Касаний: {item.touch_count}</p>
        {item.created_at && <p className="text-xs text-muted-foreground">Сохранено {new Date(item.created_at).toLocaleDateString('ru-RU')}{items.findIndex(other => other.business_id === item.business_id) === index ? ' · Последняя подборка точки' : ' · Из истории'}</p>}
        <Button variant="outline" className="h-auto min-h-11 w-full whitespace-normal text-left" onClick={() => setSelected(item.id)}>Открыть подборку · {item.business_address || item.business_name}</Button>
      </article>)}</div>
    </>}
  </section>;
}
