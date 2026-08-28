import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, BarChart3, CircleAlert, MessageSquareText, Radio, RefreshCw } from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';

import type { ControlScope } from '@/components/DashboardLayout';
import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { Button } from '@/components/ui/button';
import { communityFeedTimeLabel, type CommunityFeedPayload } from '@/lib/communityFeed';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type FeedContext = {
  currentBusinessId?: string | null;
  controlScope?: ControlScope | null;
};

const feedQuery = (businessId: string, scope?: ControlScope | null, cursor = '') => {
  const params = new URLSearchParams({ limit: '20' });
  params.set('scope_type', scope?.kind || 'business');
  params.set('scope_id', scope?.id || businessId);
  if (cursor) params.set('cursor', cursor);
  return params;
};

const feedPlatformLabel = (platform?: string) => {
  const normalized = String(platform || '').trim().toLowerCase();
  if (normalized === 'telegram') return 'Telegram';
  if (normalized === 'whatsapp') return 'WhatsApp';
  if (normalized === 'vk' || normalized === 'vkontakte') return 'VK';
  return platform || 'Источник';
};

const feedSourceInitials = (source?: string) => {
  const words = String(source || '').trim().split(/\s+/).filter(Boolean);
  if (!words.length) return 'ЛО';
  return words.slice(0, 2).map((word) => word.slice(0, 1)).join('').toLocaleUpperCase('ru-RU');
};

export const CommunityFeedPage = () => {
  const { currentBusinessId, controlScope } = useOutletContext<FeedContext>();
  const [payload, setPayload] = useState<CommunityFeedPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [trendPeriod, setTrendPeriod] = useState('month');

  const load = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    setError('');
    try {
      const result = await newAuth.makeRequest(`/operator/feed?${feedQuery(currentBusinessId, controlScope).toString()}`);
      setPayload(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить ленту.');
    } finally {
      setLoading(false);
    }
  }, [controlScope?.id, controlScope?.kind, currentBusinessId]);

  useEffect(() => { void load(); }, [load]);

  const loadMore = async () => {
    if (!currentBusinessId || !payload?.cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const result = await newAuth.makeRequest(`/operator/feed?${feedQuery(currentBusinessId, controlScope, payload.cursor).toString()}`);
      setPayload((current) => current ? { ...current, items: [...(current.items || []), ...(result.items || [])], cursor: result.cursor } : result);
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить продолжение ленты.');
    } finally {
      setLoadingMore(false);
    }
  };

  const trends = payload?.topic_trends || [];
  const activeTrend = trends.find((trend) => trend.key === trendPeriod) || trends[0];
  const updatedLabel = useMemo(() => communityFeedTimeLabel(payload?.as_of), [payload?.as_of]);

  if (!currentBusinessId) {
    return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Выберите бизнес, чтобы открыть ленту.</div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-10">
      <DashboardPageHeader
        eyebrow="Лента"
        title="Сообщения и новости вашей индустрии"
        description="Публичные отраслевые источники, главные темы и новые сообщения собраны отдельно от списка действий на сегодня."
        icon={Radio}
        actions={<Button type="button" variant="outline" onClick={() => void load()} disabled={loading} className="min-h-11 gap-2"><RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />Обновить</Button>}
      />

      {error ? <div role="alert" className="flex gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div> : null}

      {loading && !payload ? <div className="grid gap-4 md:grid-cols-2" aria-label="Загрузка ленты"><div className="h-64 animate-pulse rounded-3xl bg-slate-200/70" /><div className="h-64 animate-pulse rounded-3xl bg-slate-200/70" /></div> : null}

      {!loading || payload ? <>
        {(payload?.inbound_items || []).length ? <section className="rounded-[28px] bg-slate-950 p-5 text-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.8)] sm:p-6" aria-labelledby="feed-inbound-title"><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-orange-500/15 text-orange-300"><MessageSquareText className="h-5 w-5" /></span><div><h2 id="feed-inbound-title" className="text-balance text-xl font-semibold">Ответы по вашим кампаниям</h2><p className="mt-1 text-pretty text-sm text-slate-400">Входящие от авторов и партнёров. Ответ уже остановил будущие касания.</p></div></div><div className="mt-4 divide-y divide-white/10">{(payload?.inbound_items || []).map((item) => <article key={item.id} className="py-4"><div className="flex flex-wrap items-center gap-2 text-xs text-slate-400"><strong className="text-slate-200">{item.sender_name}</strong><span>·</span><span>{item.channel}</span><span>·</span><time className="tabular-nums" dateTime={item.received_at}>{communityFeedTimeLabel(item.received_at)}</time></div><p className="mt-2 whitespace-pre-line text-pretty text-sm leading-6 text-slate-300">{item.text}</p><Link to={item.flow_type === 'influencer' ? '/dashboard/influencers?section=messages' : '/dashboard/partnerships'} className="mt-3 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-orange-300">Открыть работу<ArrowUpRight className="h-4 w-4" /></Link></article>)}</div></section> : null}

        {trends.length ? <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="community-trends-title">
          <div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-orange-50 text-orange-700"><BarChart3 className="h-5 w-5" /></span><div><h2 id="community-trends-title" className="text-xl font-semibold text-slate-950">Главные темы в динамике</h2><p className="mt-1 text-sm text-slate-600">Самые частые темы по смыслу сообщений из подключённых источников.</p></div></div>
          <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Период статистики">{trends.map((trend) => <button key={trend.key} type="button" role="tab" aria-selected={activeTrend?.key === trend.key} onClick={() => setTrendPeriod(trend.key)} className={cn('min-h-10 rounded-xl px-4 text-sm font-semibold transition-[background-color,color,transform] active:scale-[0.96]', activeTrend?.key === trend.key ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-600')}>{trend.label}</button>)}</div>
          {activeTrend ? <div className="mt-5 grid gap-3 sm:grid-cols-2">{activeTrend.topics.slice(0, 6).map((topic, index) => <div key={topic.key} className="rounded-2xl bg-slate-50 p-4"><div className="flex items-start justify-between gap-3"><span className="text-sm font-medium text-slate-900"><span className="mr-2 font-mono text-xs tabular-nums text-slate-400">0{index + 1}</span>{topic.title}</span><strong className="tabular-nums text-slate-950">{topic.percent}%</strong></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200"><span className="block h-full rounded-full bg-orange-500" style={{ width: `${Math.min(100, topic.percent)}%` }} /></div></div>)}</div> : null}
        </section> : null}

        <section aria-labelledby="community-topics-title">
          <div className="mb-3 flex items-end justify-between gap-4"><div><h2 id="community-topics-title" className="text-xl font-semibold text-slate-950">Обсуждают сегодня</h2><p className="mt-1 text-sm text-slate-600">Короткая выжимка повторяющихся тем за последние 24 часа.</p></div><span className="text-xs text-slate-500">Обновлено {updatedLabel}</span></div>
          {(payload?.topics || []).length ? <div className="grid gap-3 md:grid-cols-3">{(payload?.topics || []).slice(0, 3).map((topic) => <article key={topic.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><span className="text-xs font-semibold uppercase tracking-[0.12em] text-orange-700">{topic.eyebrow || 'Тема'}</span><h3 className="mt-2 text-balance text-lg font-semibold text-slate-950">{topic.title || 'Важная тема'}</h3><p className="mt-2 text-pretty text-sm leading-6 text-slate-600">{topic.description}</p>{topic.source_url ? <a href={topic.source_url} target="_blank" rel="noreferrer" className="mt-4 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-orange-700">Открыть источник<ArrowUpRight className="h-4 w-4" /></a> : null}</article>)}</div> : null}
        </section>

        <section aria-labelledby="community-messages-title" className="rounded-[28px] bg-slate-100/80 p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_18px_50px_-38px_rgba(15,23,42,0.35)] sm:p-6">
          <div className="flex items-end justify-between gap-4"><div><h2 id="community-messages-title" className="text-balance text-xl font-semibold text-slate-950">Новые сообщения</h2><p className="mt-1 text-sm text-slate-500">Нажмите на сообщение, чтобы открыть его в источнике.</p></div><span className="hidden text-xs tabular-nums text-slate-500 sm:block">Обновлено {updatedLabel}</span></div>
          {(payload?.items || []).length ? <div className="mt-5 space-y-3">{(payload?.items || []).map((item) => {
            const sourceName = item.source_name || feedPlatformLabel(item.platform);
            const showTitle = Boolean(item.title && item.title.trim().toLocaleLowerCase('ru-RU') !== sourceName.trim().toLocaleLowerCase('ru-RU'));
            return <article key={item.id} className="flex items-start gap-3">
              <span aria-hidden="true" className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-slate-950 text-xs font-semibold text-white shadow-[0_0_0_1px_rgba(0,0,0,0.1),0_4px_12px_-6px_rgba(15,23,42,0.55)]">{feedSourceInitials(sourceName)}</span>
              <a href={item.url} target="_blank" rel="noreferrer" className="group block min-w-0 max-w-4xl flex-1 rounded-[22px] rounded-tl-md bg-white px-4 py-3.5 text-left shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_2px_5px_rgba(15,23,42,0.05)] transition-[box-shadow,transform] hover:shadow-[0_0_0_1px_rgba(15,23,42,0.09),0_5px_14px_rgba(15,23,42,0.08)] active:scale-[0.96]">
                <span className="flex items-center justify-between gap-3"><strong className="truncate text-sm text-slate-950">{sourceName}</strong><span className="shrink-0 text-[11px] font-medium text-slate-400">{feedPlatformLabel(item.platform)}</span></span>
                {showTitle ? <h3 className="mt-1.5 text-balance text-[15px] font-semibold leading-5 text-slate-900">{item.title}</h3> : null}
                <span className="mt-1.5 block line-clamp-4 whitespace-pre-line text-pretty text-sm leading-6 text-slate-600">{item.text}</span>
                <span className="mt-2 flex items-center justify-end gap-1.5 text-[11px] tabular-nums text-slate-400"><time dateTime={item.published_at}>{communityFeedTimeLabel(item.published_at)}</time><ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" /></span>
              </a>
            </article>;
          })}</div> : <div className="py-12 text-center"><MessageSquareText className="mx-auto h-7 w-7 text-slate-400" /><h3 className="mt-3 font-semibold text-slate-950">Сообщений пока нет</h3><p className="mt-2 text-sm text-slate-600">Добавьте публичные источники, и LocalOS соберёт здесь отраслевые новости.</p><Link to="/dashboard/more" className="mt-4 inline-flex min-h-10 items-center text-sm font-semibold text-orange-700">Открыть подключения</Link></div>}
          {payload?.cursor ? <Button type="button" variant="outline" className="mt-4 min-h-11 w-full" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? 'Загружаем…' : 'Показать ещё'}</Button> : null}
        </section>
      </> : null}
    </div>
  );
};
