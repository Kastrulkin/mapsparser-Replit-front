import { useCallback, useEffect, useState } from 'react';
import { BarChart3, Check, CircleAlert, ExternalLink, Loader2, MapPin, MessageSquareText, X } from 'lucide-react';
import { useParams } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';

type RoomDeliverable = {
  id: string;
  platform: string;
  deliverable_type: string;
  due_at?: string | null;
  publication_url?: string | null;
  verification_status: string;
  tracking?: {
    tracked_url?: string | null;
    promo_code?: string | null;
    cta?: string | null;
  };
  measurement_checkpoints?: Array<{
    checkpoint: '24h' | '7d' | '14d';
    status: 'pending' | 'completed' | 'skipped';
    due_at: string;
  }>;
};

type CreatorRoom = {
  status: string;
  display_name: string;
  campaign_title: string;
  campaign_goal: string;
  business_name: string;
  business_city?: string;
  business_address?: string;
  formats?: string[];
  offer?: Record<string, unknown>;
  budget?: Record<string, unknown>;
  period?: Record<string, unknown>;
  agreed_terms?: Record<string, unknown>;
  media_kit_url?: string | null;
  availability_text?: string | null;
  preferred_contact?: string | null;
  deliverables?: RoomDeliverable[];
};

const roomStatus: Record<string, string> = {
  draft: 'Предложение готовится',
  invited: 'Ожидается ваш ответ',
  negotiating: 'Обсуждаем изменения',
  agreed: 'Условия приняты',
  awaiting_content: 'Ожидается материал',
  published: 'Материал передан',
  measuring: 'Собираем статистику',
  completed: 'Коллаборация завершена',
  declined: 'Предложение отклонено',
};

export const CreatorRoomPage = () => {
  const { token = '' } = useParams();
  const [room, setRoom] = useState<CreatorRoom | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [comment, setComment] = useState('');
  const [publicationUrl, setPublicationUrl] = useState('');
  const [selectedDeliverable, setSelectedDeliverable] = useState('');
  const [selectedCheckpoint, setSelectedCheckpoint] = useState('');
  const [reach, setReach] = useState('');
  const [views, setViews] = useState('');
  const [mediaKitUrl, setMediaKitUrl] = useState('');
  const [availability, setAvailability] = useState('');
  const [preferredContact, setPreferredContact] = useState('');
  const [recommendedName, setRecommendedName] = useState('');
  const [recommendedUrl, setRecommendedUrl] = useState('');

  const loadRoom = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/promotion/influencers/public/${encodeURIComponent(token)}`);
      setRoom(response.room || null);
      setMediaKitUrl(String(response.room?.media_kit_url || ''));
      setAvailability(String(response.room?.availability_text || ''));
      setPreferredContact(String(response.room?.preferred_contact || ''));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Ссылка недействительна или истекла.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void loadRoom(); }, [loadRoom]);

  const submit = async (action: string, payload: Record<string, unknown> = {}) => {
    setBusy(action);
    setError('');
    setNotice('');
    try {
      const response = await newAuth.makeRequest(`/promotion/influencers/public/${encodeURIComponent(token)}`, {
        method: 'PATCH',
        body: JSON.stringify({ action, ...payload }),
      });
      setRoom(response.room || null);
      setNotice(action === 'accept' ? 'Условия приняты.' : action === 'decline' ? 'Ответ сохранён.' : 'Данные переданы бизнесу.');
      setComment('');
      setPublicationUrl('');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Не удалось сохранить ответ.');
    } finally {
      setBusy('');
    }
  };

  if (loading) return <main className="grid min-h-screen place-items-center bg-slate-50"><div className="text-center text-sm text-slate-500"><Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin motion-reduce:animate-none" />Открываем предложение</div></main>;
  if (!room) return <main className="grid min-h-screen place-items-center bg-slate-50 p-6"><div className="max-w-md rounded-3xl bg-white p-8 text-center shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><CircleAlert className="mx-auto h-8 w-8 text-rose-600" /><h1 className="mt-4 text-xl font-semibold text-slate-950">Предложение недоступно</h1><p className="mt-2 text-sm leading-6 text-slate-500">{error || 'Попросите бизнес прислать новую приватную ссылку.'}</p></div></main>;

  const deliverables = room.deliverables || [];
  const publishedDeliverables = deliverables.filter((item) => item.publication_url);
  const metricDeliverable = publishedDeliverables.find((item) => item.id === selectedDeliverable);

  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-950 antialiased sm:px-6 sm:py-12">
    <div className="mx-auto max-w-3xl space-y-5">
      <header className="rounded-[30px] bg-slate-950 p-7 text-white shadow-[0_20px_60px_-34px_rgba(15,23,42,0.8)] sm:p-9">
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-300">Приватное предложение</div>
        <h1 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">{room.campaign_title}</h1>
        <p className="mt-3 text-pretty text-sm leading-6 text-slate-300">{room.campaign_goal}</p>
        <div className="mt-6 flex flex-wrap items-center gap-3 text-sm"><span className="rounded-full bg-white/10 px-3 py-1.5">{roomStatus[room.status] || room.status}</span><span className="inline-flex items-center gap-2 text-slate-300"><MapPin className="h-4 w-4" />{[room.business_city, room.business_address].filter(Boolean).join(' · ') || 'Локация указана в условиях'}</span></div>
      </header>

      {error ? <div role="alert" className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div> : null}
      {notice ? <div aria-live="polite" className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div> : null}

      <section className="rounded-[26px] bg-white p-6 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]">
        <div className="text-sm text-slate-500">Предложение от</div><h2 className="mt-1 text-2xl font-semibold">{room.business_name}</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2"><div className="rounded-2xl bg-slate-50 p-4"><div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Форматы</div><div className="mt-2 text-sm leading-6">{room.formats?.join(', ') || 'Уточняются'}</div></div><div className="rounded-2xl bg-slate-50 p-4"><div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Важно</div><div className="mt-2 text-sm leading-6">Платежи выполняются вне LocalOS. Права на материал действуют только если прямо согласованы.</div></div></div>
        {['declined', 'completed'].includes(room.status) ? null : <div className="mt-6 flex flex-wrap gap-3"><Button onClick={() => void submit('accept')} disabled={Boolean(busy)} className="min-h-11 rounded-xl bg-emerald-700 text-white hover:bg-emerald-800">{busy === 'accept' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}Принять условия</Button><Button variant="outline" onClick={() => void submit('decline')} disabled={Boolean(busy)} className="min-h-11 rounded-xl"><X className="mr-2 h-4 w-4" />Отказаться</Button></div>}
      </section>

      <section className="rounded-[26px] bg-white p-6 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><div className="flex items-center gap-3"><MessageSquareText className="h-5 w-5 text-amber-600" /><h2 className="text-xl font-semibold">Предложить изменения</h2></div><Textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Напишите, что хотите изменить: формат, дату, сумму или права" className="mt-4 min-h-28 rounded-xl" /><Button variant="outline" onClick={() => void submit('propose_changes', { comment })} disabled={Boolean(busy) || !comment.trim()} className="mt-3 min-h-11 rounded-xl">Отправить изменения</Button></section>

      <section className="rounded-[26px] bg-white p-6 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><h2 className="text-xl font-semibold">Ваши условия и медиакит</h2><p className="mt-2 text-sm leading-6 text-slate-500">Эти данные будут отмечены как подтверждённые вами и помогут бизнесу подготовить корректное предложение.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><Input value={mediaKitUrl} onChange={(event) => setMediaKitUrl(event.target.value)} placeholder="Ссылка на медиакит" className="min-h-11 rounded-xl" /><Input value={preferredContact} onChange={(event) => setPreferredContact(event.target.value)} placeholder="Предпочитаемый контакт" className="min-h-11 rounded-xl" /><Input value={availability} onChange={(event) => setAvailability(event.target.value)} placeholder="Доступность и ближайшие даты" className="min-h-11 rounded-xl sm:col-span-2" /></div><Button variant="outline" onClick={() => void submit('update_profile', { media_kit_url: mediaKitUrl, preferred_contact: preferredContact, availability_text: availability })} disabled={Boolean(busy) || (!mediaKitUrl.trim() && !preferredContact.trim() && !availability.trim())} className="mt-3 min-h-11 rounded-xl">Сохранить данные</Button></section>

      <section className="rounded-[26px] bg-white p-6 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><h2 className="text-xl font-semibold">Материалы</h2>{deliverables.length ? <div className="mt-4 space-y-2">{deliverables.map((item) => <div key={item.id} className="rounded-xl bg-slate-50 px-4 py-3 text-sm"><div className="flex items-center justify-between gap-3"><span>{item.platform} · {item.deliverable_type}</span>{item.publication_url ? <a href={item.publication_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-slate-500 underline underline-offset-4">Открыть<ExternalLink className="h-3.5 w-3.5" /></a> : <span className="text-slate-500">ожидается</span>}</div>{item.tracking?.cta ? <div className="mt-3 text-xs leading-5 text-slate-600">CTA: {item.tracking.cta}</div> : null}{item.tracking?.promo_code ? <div className="mt-1 text-xs text-slate-600">Промокод: <span className="font-semibold tabular-nums">{item.tracking.promo_code}</span></div> : null}{item.tracking?.tracked_url ? <div className="mt-1 break-all text-xs text-slate-600">Ссылка для публикации: <a href={item.tracking.tracked_url} target="_blank" rel="noreferrer" className="underline underline-offset-4">{item.tracking.tracked_url}</a></div> : null}</div>)}</div> : <p className="mt-2 text-sm text-slate-500">Список ожидаемых материалов пока не добавлен.</p>}<div className="mt-5 flex flex-col gap-3 sm:flex-row"><Input value={publicationUrl} onChange={(event) => setPublicationUrl(event.target.value)} placeholder="Ссылка на опубликованный материал" className="min-h-11 rounded-xl" /><Button onClick={() => void submit('add_publication', { publication_url: publicationUrl, deliverable_id: deliverables.find((item) => !item.publication_url)?.id })} disabled={Boolean(busy) || !publicationUrl.trim()} className="min-h-11 shrink-0 rounded-xl bg-slate-950 text-white">Добавить ссылку</Button></div></section>

      {publishedDeliverables.length ? <section className="rounded-[26px] bg-white p-6 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><div className="flex items-center gap-3"><BarChart3 className="h-5 w-5 text-amber-600" /><h2 className="text-xl font-semibold">Передать статистику</h2></div><select aria-label="Материал" value={selectedDeliverable} onChange={(event) => { setSelectedDeliverable(event.target.value); setSelectedCheckpoint(''); }} className="mt-4 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Выберите материал</option>{publishedDeliverables.map((item) => <option key={item.id} value={item.id}>{item.platform} · {item.deliverable_type}</option>)}</select>{metricDeliverable?.measurement_checkpoints?.length ? <select aria-label="Контрольная точка" value={selectedCheckpoint} onChange={(event) => setSelectedCheckpoint(event.target.value)} className="mt-3 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Выберите период</option>{metricDeliverable.measurement_checkpoints.map((item) => <option key={item.checkpoint} value={item.checkpoint} disabled={item.status === 'completed'}>{item.checkpoint === '24h' ? '24 часа' : item.checkpoint === '7d' ? '7 дней' : '14 дней'}{item.status === 'completed' ? ' · уже передано' : ''}</option>)}</select> : null}<div className="mt-3 grid gap-3 sm:grid-cols-2"><Input value={reach} onChange={(event) => setReach(event.target.value)} inputMode="numeric" placeholder="Охват" className="min-h-11 rounded-xl" /><Input value={views} onChange={(event) => setViews(event.target.value)} inputMode="numeric" placeholder="Просмотры" className="min-h-11 rounded-xl" /></div><p className="mt-3 text-xs leading-5 text-slate-500">Показатели будут отмечены как предоставленные автором и потребуют отдельной интерпретации бизнеса.</p><Button variant="outline" onClick={() => void submit('add_metrics', { deliverable_id: selectedDeliverable, checkpoint: selectedCheckpoint || undefined, reach: Number(reach || 0), views: Number(views || 0) })} disabled={Boolean(busy) || !selectedDeliverable || Boolean(metricDeliverable?.measurement_checkpoints?.length && !selectedCheckpoint)} className="mt-3 min-h-11 rounded-xl">Передать статистику</Button></section> : null}

      <section className="rounded-[26px] bg-white p-6 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><h2 className="text-xl font-semibold">Порекомендовать другого автора</h2><p className="mt-2 text-sm leading-6 text-slate-500">Рекомендация попадёт в ручную проверку и сама по себе не запускает сообщение.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><Input value={recommendedName} onChange={(event) => setRecommendedName(event.target.value)} placeholder="Имя или название" className="min-h-11 rounded-xl" /><Input value={recommendedUrl} onChange={(event) => setRecommendedUrl(event.target.value)} placeholder="Публичная ссылка" className="min-h-11 rounded-xl" /></div><Button variant="outline" onClick={() => void submit('recommend_creator', { display_name: recommendedName, url: recommendedUrl })} disabled={Boolean(busy) || !recommendedName.trim() || !recommendedUrl.trim()} className="mt-3 min-h-11 rounded-xl">Передать рекомендацию</Button></section>
    </div>
  </main>;
};
