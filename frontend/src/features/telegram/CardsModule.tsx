import { useMobileJobPolling } from '@/components/telegram/useMobileJobPolling';
import ActionPreviewSheet,{ type MobileActionPreview } from '@/components/telegram/ActionPreviewSheet';
import JobProgressSheet from '@/components/telegram/JobProgressSheet';
import { type MobileScope } from '@/components/telegram/ScopeProvider.logic';
import { useLatestCallback } from '@/hooks/useLatestCallback';
import { confirmMobileAction,loadMobileJob,mobileAuthHeaders,mobileJsonHeaders,mobileScopeQuery,readMobileJson,type MobileJob } from '@/lib/mobileDataClient';
import {
MapPinned,
RefreshCw,
Settings
} from 'lucide-react';
import { useEffect,useState } from 'react';
import { dateLabel,providerName } from './format';
import { Empty,InlineError,MetricMini,StatusPill } from './shared';
import type { ModuleItem } from './types';
const readJson = readMobileJson;
const scopeQuery = mobileScopeQuery;
const authHeaders = mobileJsonHeaders;
const authOnlyHeaders = mobileAuthHeaders;

const monthlyRefreshCost = (interval: string, cost: number) => Math.ceil((30 * 24) / Math.max(Number(interval) || 24, 1)) * cost;

export const CardsModule = ({ scope, items, reload }: { scope?: MobileScope; items: ModuleItem[]; reload: () => Promise<void> }) => {
  const [editing, setEditing] = useState('');
  const [interval, setInterval] = useState('24');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<MobileActionPreview | null>(null);
  const [refreshPreview, setRefreshPreview] = useState<MobileActionPreview | null>(null);
  const [activeJob, setActiveJob] = useState<MobileJob | null>(null);
  const saveSchedule = async (item: ModuleItem, enabled: boolean) => {
    setBusy(item.id || 'schedule');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'cards.schedule.update', input: { business_id: item.business_id || item.id, enabled, interval_hours: Number(interval) } }) }).then(readJson<{ preview?: MobileActionPreview }>);
      setPreview(result.preview || null); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить график.'); }
    finally { setBusy(''); }
  };
  const confirmSchedule = async () => {
    if (!preview?.action_id) return;
    setBusy(preview.action_id);
    try {
      await fetch(`/api/operator/mobile/actions/${preview.action_id}/confirm`, { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }) }).then(readJson);
      setPreview(null); await reload(); setEditing(''); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить график.'); }
    finally { setBusy(''); }
  };
  const prepareRefresh = async (item: ModuleItem) => {
    setBusy(`refresh:${item.id || ''}`); setError('');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'cards.refresh', input: { business_id: item.business_id || item.id, source: 'all' } }) }).then(readJson<{ preview?: MobileActionPreview }>);
      setRefreshPreview(result.preview || null);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить обновление.'); }
    finally { setBusy(''); }
  };
  const confirmRefresh = async () => {
    if (!refreshPreview?.action_id) return;
    setBusy(refreshPreview.action_id); setError('');
    try {
      const result = await confirmMobileAction(refreshPreview.action_id, scope);
      const jobId = String(result.operator_result?.job_id || '');
      setRefreshPreview(null);
      if (jobId) {
        const loaded = await loadMobileJob(jobId, scope);
        setActiveJob(loaded.job || null);
      }
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось запустить обновление.'); }
    finally { setBusy(''); }
  };
  const reloadEffect = useLatestCallback(reload);
  useMobileJobPolling({ job: activeJob, scope, onJob: setActiveJob, onComplete: (completedJob) => { if (completedJob.status === 'completed') void reloadEffect(); } });
  return <div>
    <div className="mb-4 rounded-[22px] bg-primary/[0.08] p-4 ring-1 ring-inset ring-primary/15"><div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-primary/15 text-primary"><RefreshCw className="h-5 w-5" /></span><div><b className="block text-sm">Данные из Яндекса и 2ГИС</b><p className="mt-1 text-xs leading-5 text-zinc-500">ЛокалОС проверяет карточки по вашему графику и показывает, когда данные были собраны в последний раз.</p></div></div></div>
    {error ? <InlineError text={error} /> : null}
    {items.length ? <div className="space-y-2">{items.map((item) => <article key={item.id} className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><b className="block text-sm leading-5">{item.title || item.business_name}</b><small className="mt-1 block truncate text-zinc-600">{item.subtitle || item.business_name}</small></div><StatusPill value={item.status} /></div><div className="mt-4 flex flex-wrap gap-2">{(item.provider_sources || []).filter(Boolean).map((source) => <span key={source} className="rounded-full bg-white/[0.05] px-3 py-1.5 text-[11px] font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07]">{providerName(source)}</span>)}</div><div className="mt-4 grid grid-cols-3 gap-2 text-center"><MetricMini label="Рейтинг" value={item.rating} /><MetricMini label="Отзывы" value={item.reviews_count} /><MetricMini label="SEO" value={item.seo_score} /></div><div className="mt-4 rounded-[16px] bg-black/20 p-3 text-xs leading-5 ring-1 ring-inset ring-white/[0.05]"><p className="text-zinc-400">Последняя проверка: <b className="font-medium text-zinc-200">{dateLabel(item.parse_updated_at || item.review_sync_last_run_at || item.updated_at)}</b></p><p className="mt-1 text-zinc-400">{item.review_sync_enabled ? <>Следующее обновление: <b className="font-medium text-zinc-200">{dateLabel(item.review_sync_next_run_at)}</b></> : 'Автоматическое обновление выключено'}</p><p className="mt-1 text-zinc-600">Одно обновление — {item.refresh_cost_credits || 10} кредитов</p></div>{editing === item.id ? <div className="mt-3 rounded-[18px] bg-white/[0.035] p-3 ring-1 ring-inset ring-white/[0.06]"><label className="text-[11px] text-zinc-500">Как часто проверять<select value={interval} onChange={(event) => setInterval(event.target.value)} className="mt-2 min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-sm text-zinc-200 ring-1 ring-inset ring-white/[0.07]"><option value="24">Каждый день</option><option value="48">Раз в 2 дня</option><option value="168">Раз в неделю</option><option value="336">Раз в 2 недели</option></select></label><p className="mt-3 text-pretty text-[11px] leading-5 text-zinc-500">Чем чаще проверка, тем быстрее ЛокалОС заметит новые отзывы и изменения в карточке. Но кредиты будут расходоваться быстрее: при этом графике — до <b className="font-semibold tabular-nums text-zinc-300">{monthlyRefreshCost(interval, item.refresh_cost_credits || 10)} кредитов за 30 дней</b>.</p><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" disabled={busy === item.id} onClick={() => void saveSchedule(item, false)} className="min-h-11 rounded-[14px] bg-white/[0.05] text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Выключить</button><button type="button" disabled={busy === item.id} onClick={() => void saveSchedule(item, true)} className="min-h-11 rounded-[14px] bg-primary text-xs font-semibold active:scale-[0.96]">{busy === item.id ? 'Сохраняем…' : 'Сохранить график'}</button></div></div> : <div className="mt-3 grid grid-cols-2 gap-2"><button type="button" onClick={() => { setInterval(String(item.review_sync_interval_hours || 24)); setEditing(item.id || 'schedule'); }} className="min-h-11 rounded-[14px] bg-white/[0.05] px-3 text-xs font-semibold ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]"><Settings className="mr-1.5 inline h-4 w-4" />График</button><button type="button" disabled={Boolean(busy)} onClick={() => void prepareRefresh(item)} className="min-h-11 rounded-[14px] bg-primary px-3 text-xs font-semibold text-white transition-transform active:scale-[0.96] disabled:opacity-50"><RefreshCw className="mr-1.5 inline h-4 w-4" />Обновить</button></div>}</article>)}</div> : <Empty icon={MapPinned} title="Карточки не подключены" text="Добавьте ссылки на Яндекс и 2ГИС в настройках бизнеса — после этого ЛокалОС начнёт следить за обновлениями." />}
    <ActionPreviewSheet preview={preview} busy={Boolean(busy)} confirmLabel="Сохранить график" onCancel={() => setPreview(null)} onConfirm={() => void confirmSchedule()} />
    <ActionPreviewSheet preview={refreshPreview} busy={Boolean(busy)} confirmLabel="Обновить карточки" onCancel={() => setRefreshPreview(null)} onConfirm={() => void confirmRefresh()} />
    <JobProgressSheet job={activeJob} onClose={() => { setActiveJob(null); if (activeJob?.status === 'completed') void reload(); }} />
  </div>;
};
