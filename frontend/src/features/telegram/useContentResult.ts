import { useEffect, useMemo, useState } from 'react';
import { mobileAuthHeaders, readMobileJson } from '@/lib/mobileDataClient';
import { currentResultPlan, type ResultPlan } from '@/lib/mobileWorkResults';
import type { ModuleItem } from './types';

async function fetchSaved(url: string, signal: AbortSignal) {
  const request = new AbortController();
  const cancel = () => request.abort();
  signal.addEventListener('abort', cancel, { once: true });
  const timeout = window.setTimeout(cancel, 15000);
  try { return await fetch(url, { headers: mobileAuthHeaders(), signal: request.signal }); }
  catch (error) { if (request.signal.aborted && !signal.aborted) throw new Error('Загрузка заняла слишком много времени. Откройте план ещё раз.'); throw error; }
  finally { window.clearTimeout(timeout); signal.removeEventListener('abort', cancel); }
}

export function useContentResult(businessId: string, source: ModuleItem[], selected: string, focusItemId?: string) {
  const scopedSource = useMemo(() => source.filter(item => !businessId || !item.business_id || item.business_id === businessId), [source, businessId]);
  const [catalog, setCatalog] = useState<{ businessId: string; plans: ResultPlan[] }>({ businessId: '', plans: [] });
  const [loaded, setLoaded] = useState<{ businessId: string; planId: string; items: ModuleItem[] } | null>(null);
  const [deniedBusiness, setDeniedBusiness] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const fallback = useMemo(() => [...new Set(scopedSource.map(item => item.plan_id).filter(Boolean))].map(id => {
    const items = scopedSource.filter(item => item.plan_id === id);
    return { id: id || '', title: items[0]?.plan_title, items_count: items.length, ready_count: items.filter(item => item.draft_text?.trim()).length };
  }), [scopedSource]);
  const denied = deniedBusiness === businessId && Boolean(businessId);
  const plans = denied ? [] : catalog.businessId === businessId ? catalog.plans : fallback;
  const current = currentResultPlan(plans);
  const focused = scopedSource.find(item => item.id === focusItemId)?.plan_id;
  const activeId = (plans.some(plan => plan.id === selected) ? selected : focused || current?.id) || fallback[0]?.id || '';
  useEffect(() => {
    if (!businessId) return;
    const abort = new AbortController();
    setError('');
    fetchSaved(`/api/content-plans?business_id=${encodeURIComponent(businessId)}`, abort.signal).then(response => { if (!abort.signal.aborted && [401,403].includes(response.status)) setDeniedBusiness(businessId); return response; }).then(readMobileJson<{ plans?: ResultPlan[] }>).then(data => {
      if (!abort.signal.aborted) setCatalog({ businessId, plans: data.plans || [] });
    }).catch(reason => { if (!abort.signal.aborted) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить историю планов.'); });
    return () => abort.abort();
  }, [businessId, scopedSource]);
  useEffect(() => {
    if (!businessId || !activeId) { setLoaded(null); return; }
    const abort = new AbortController();
    setLoading(true); setError('');
    fetchSaved(`/api/content-plans/${encodeURIComponent(activeId)}`, abort.signal).then(response => { if (!abort.signal.aborted && [401,403].includes(response.status)) setDeniedBusiness(businessId); return response; }).then(readMobileJson<{ plan?: ResultPlan & { items?: Array<ModuleItem & { theme?: string; goal?: string; metadata_json?: { selected_photo_asset_id?: string } }> } }>).then(data => {
      if (abort.signal.aborted) return;
      const plan = data.plan;
      if (!plan || plan.id !== activeId) throw new Error('Не удалось получить выбранный план. Повторите открытие.');
      const scopedItems = (plan.items || []).filter(item => !item.business_id || item.business_id === businessId).map(item => {
        const initial = scopedSource.find(value => value.id === item.id);
        return { ...initial, ...item, title: item.theme || item.title, subtitle: item.goal || item.subtitle, plan_id: plan.id, plan_title: plan.title, plan_period_days: plan.period_days, version: item.version || item.updated_at, selected_photo_asset_id: initial?.selected_photo_asset_id || item.selected_photo_asset_id || item.metadata_json?.selected_photo_asset_id };
      });
      setLoaded({ businessId, planId: activeId, items: scopedItems });
    }).catch(reason => { if (!abort.signal.aborted) { setLoaded(null); setError(reason instanceof Error ? reason.message : 'Не удалось открыть план.'); } }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [businessId, activeId, scopedSource]);
  const items = denied ? [] : loaded?.businessId === businessId && loaded.planId === activeId ? loaded.items : scopedSource.filter(item => item.plan_id === activeId || !activeId);
  return { plans, currentId: current?.id, activeId, items, loading, error, denied };
}
