import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, FilePenLine, Handshake, Loader2, MapPinned, Megaphone, ShieldCheck, Sparkles } from 'lucide-react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import SeoMeta from '@/components/SeoMeta';
import { Button } from '@/components/ui/button';
import {
  getLeadJourneyDirection,
  isLeadJourneyKey,
  leadJourneyKeyForFlow,
  leadJourneyDirections,
  loadPublicLeadJourney,
  preparePublicOpportunity,
  saveLeadJourneyIntent,
  saveLeadJourneyToken,
  trackPublicJourneyEvent,
  type JourneyOpportunity,
  type LeadJourneyDirection,
  type LeadJourneyKey,
  type PublicLeadJourney,
} from '@/lib/leadJourney';

const directionIcon = (key: LeadJourneyKey) => key === 'influencers' ? Megaphone : key === 'partnerships' ? Handshake : key === 'content' ? FilePenLine : MapPinned;
const flowForKey = (key: LeadJourneyKey) => key === 'influencers' ? 'influencer' : key === 'partnerships' ? 'partnership' : key;

const DirectionCard = ({ direction, opportunity, onOpen, secondary = false }: { direction: LeadJourneyDirection; opportunity?: JourneyOpportunity; onOpen: () => void; secondary?: boolean }) => {
  const Icon = directionIcon(direction.key);
  return (
    <button type="button" onClick={onOpen} disabled={secondary} className="group flex min-h-64 flex-col rounded-[28px] bg-white p-6 text-left shadow-[0_0_0_1px_rgba(15,23,42,0.07),0_18px_55px_-35px_rgba(15,23,42,0.45)] transition-[box-shadow,transform] enabled:hover:-translate-y-0.5 enabled:hover:shadow-[0_0_0_1px_rgba(249,115,22,0.22),0_24px_70px_-32px_rgba(15,23,42,0.42)] enabled:active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2">
      <span className="grid h-12 w-12 place-items-center rounded-2xl bg-orange-50 text-orange-700"><Icon className="h-6 w-6" /></span>
      <span className="mt-6 text-xs font-bold uppercase tracking-[0.14em] text-orange-700">{direction.eyebrow}</span>
      <strong className="mt-2 text-balance text-xl leading-7 text-slate-950">{opportunity?.title || direction.title}</strong>
      <span className="mt-3 flex-1 text-pretty text-sm leading-6 text-slate-600">{opportunity?.summary || direction.preview}</span>
      {opportunity?.count ? <span className="mt-3 text-xs tabular-nums text-slate-500">Ещё вариантов: {opportunity.count}</span> : null}
      <span className="mt-5 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-slate-950">{secondary ? 'Доступно для исследования после регистрации' : 'Посмотреть возможность'}{!secondary ? <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /> : null}</span>
    </button>
  );
};

export default function LeadJourneyPage() {
  const { token = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialKey = searchParams.get('direction');
  const [selectedKey, setSelectedKey] = useState<LeadJourneyKey | null>(isLeadJourneyKey(initialKey) ? initialKey : null);
  const [prepared, setPrepared] = useState(searchParams.get('step') === 'result' && isLeadJourneyKey(initialKey));
  const [journey, setJourney] = useState<PublicLeadJourney | null>(null);
  const [journeyLoading, setJourneyLoading] = useState(Boolean(token));
  const [journeyError, setJourneyError] = useState('');
  const [preparing, setPreparing] = useState(false);
  const [partialPreview, setPartialPreview] = useState<{ mechanic?: string; message_excerpt?: string } | null>(null);
  const selected = useMemo(() => getLeadJourneyDirection(selectedKey), [selectedKey]);
  const opportunityForKey = (key: LeadJourneyKey | null) => journey?.opportunities.find((item) => item.flow_type === (key ? flowForKey(key) : ''));
  const selectedOpportunity = opportunityForKey(selectedKey);
  const journeySelectedKey = leadJourneyKeyForFlow(journey?.selected_flow);

  useEffect(() => {
    if (!token) return;
    saveLeadJourneyToken(token);
    void loadPublicLeadJourney(token)
      .then((value) => {
        setJourney(value);
        setJourneyError('');
        const selectedFromJourney = leadJourneyKeyForFlow(value.selected_flow);
        if (selectedFromJourney) {
          setSelectedKey(selectedFromJourney);
          setSearchParams({ direction: selectedFromJourney, step: 'detail' }, { replace: true });
        }
        void trackPublicJourneyEvent(token, 'lead_link_opened');
      })
      .catch((error: Error) => setJourneyError(error.message))
      .finally(() => setJourneyLoading(false));
  }, [token]);

  const openDirection = (key: LeadJourneyKey) => {
    setSelectedKey(key);
    setPrepared(false);
    setPartialPreview(null);
    setSearchParams({ direction: key, step: 'detail' });
    window.scrollTo({ top: 0, behavior: 'smooth' });
    const opportunity = opportunityForKey(key);
    if (token && opportunity) void trackPublicJourneyEvent(token, 'opportunity_preview_clicked', opportunity);
  };

  const goBack = () => {
    setSelectedKey(null);
    setPrepared(false);
    setPartialPreview(null);
    setSearchParams({});
  };

  const prepare = async () => {
    if (!selected) return;
    if (token && selectedOpportunity) {
      setPreparing(true);
      try {
        const value = await preparePublicOpportunity(token, selectedOpportunity);
        setPartialPreview(value.partial_result || null);
        void trackPublicJourneyEvent(token, 'partial_result_viewed', selectedOpportunity);
      } catch (error) {
        setJourneyError(error instanceof Error ? error.message : 'Не удалось подготовить результат');
        setPreparing(false);
        return;
      }
      setPreparing(false);
    }
    setPrepared(true);
    setSearchParams({ direction: selected.key, step: 'result' });
  };

  const registrationParams = new URLSearchParams({ tab: 'register', source: 'lead_journey' });
  if (selected) registrationParams.set('journey', selected.key);
  if (token) registrationParams.set('journey_token', token);
  if (journey?.business?.name) registrationParams.set('business_name', journey.business.name);
  if (journey?.business?.city) registrationParams.set('business_city', journey.business.city);
  if (journey?.business?.address) registrationParams.set('business_address', journey.business.address);
  const registrationUrl = `/login?${registrationParams.toString()}`;

  if (journeyLoading) return <main className="grid min-h-screen place-items-center bg-[#f7f7f5]"><div className="text-center"><Loader2 className="mx-auto h-8 w-8 animate-spin text-orange-600" /><p className="mt-3 text-sm text-slate-600">Загружаем персональные возможности…</p></div></main>;
  if (journeyError && !journey) return <main className="grid min-h-screen place-items-center bg-[#f7f7f5] px-4"><section className="max-w-xl rounded-[28px] bg-white p-8 text-center shadow-[0_20px_60px_rgba(15,23,42,0.10)]"><h1 className="text-balance text-2xl font-semibold">Персональная ссылка недоступна</h1><p className="mt-3 text-pretty text-sm leading-6 text-slate-600">{journeyError}</p><Button asChild className="mt-6 min-h-11"><Link to="/">Вернуться на LocalOS</Link></Button></section></main>;

  return (
    <main className="min-h-screen bg-[#f7f7f5] px-4 py-10 text-slate-950 sm:px-6 sm:py-16 lg:px-8">
      <SeoMeta title="Найдите первое действие для новых клиентов — LocalOS" description="Четыре персональных направления роста: локальные авторы, партнёры, карты и контент." path={token ? `/start/${token}` : '/growth'} />
      <div className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between gap-4">
          {selected && !journeySelectedKey ? <button type="button" onClick={goBack} className="inline-flex min-h-11 items-center gap-2 rounded-xl px-2 text-sm font-semibold text-slate-600 transition-colors hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500"><ArrowLeft className="h-4 w-4" />Все направления</button> : <Link to="/" className="inline-flex min-h-11 items-center gap-2 rounded-xl px-2 text-sm font-semibold text-slate-600 transition-colors hover:text-slate-950"><ArrowLeft className="h-4 w-4" />На главную</Link>}
          <span className="inline-flex items-center gap-2 text-sm font-bold"><Sparkles className="h-4 w-4 text-orange-600" />LocalOS</span>
        </div>

        {!selected ? <>
          <section className="mx-auto max-w-4xl pb-10 pt-12 text-center sm:pb-14 sm:pt-16"><span className="text-sm font-bold uppercase tracking-[0.16em] text-orange-700">Персональное превью</span><h1 className="mt-4 text-balance text-4xl font-bold tracking-[-0.045em] sm:text-6xl">Четыре пути к следующему результату</h1><p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-600">Выберите направление. Сначала покажем конкретную возможность и часть готового результата. Регистрация понадобится только для завершения действия.</p></section>
          <section aria-label="Направления роста" className="grid gap-4 md:grid-cols-2">{leadJourneyDirections.map((direction) => <DirectionCard key={direction.key} direction={direction} opportunity={opportunityForKey(direction.key)} onOpen={() => openDirection(direction.key)} />)}</section>
        </> : <section className="mx-auto max-w-4xl pt-10 sm:pt-14">
          <div className="overflow-hidden rounded-[32px] bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_24px_70px_rgba(15,23,42,0.10)]">
            <div className="bg-slate-950 p-6 text-white sm:p-10"><span className="text-sm font-bold uppercase tracking-[0.14em] text-orange-400">{selected.eyebrow}</span><h1 className="mt-3 text-balance text-3xl font-bold tracking-[-0.035em] sm:text-5xl">{prepared ? selected.resultTitle : selectedOpportunity?.title || selected.detailTitle}</h1><p className="mt-5 max-w-2xl text-pretty text-base leading-7 text-slate-300">{prepared ? 'LocalOS определил структуру первого результата. Ниже видно, что именно будет готово к действию.' : selectedOpportunity?.reason || selected.detail}</p></div>
            <div className="p-6 sm:p-10">
              {!prepared ? <><div className="rounded-2xl bg-orange-50 p-5 text-sm leading-6 text-orange-950"><strong className="block text-base">Что произойдёт после нажатия</strong><span className="mt-2 block">LocalOS подготовит первый материал. Ничего не будет отправлено или изменено без вашего подтверждения.</span>{selectedOpportunity?.public_url ? <a href={selectedOpportunity.public_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex min-h-10 items-center font-semibold underline decoration-orange-300 underline-offset-4">Посмотреть публичный пример</a> : null}</div><Button type="button" onClick={() => void prepare()} disabled={preparing} className="mt-6 min-h-12 w-full rounded-xl text-base transition-transform active:scale-[0.96] sm:w-auto">{preparing ? <Loader2 className="h-5 w-5 animate-spin" /> : null}{selected.prepareLabel}<ArrowRight className="h-5 w-5" /></Button></> : <>
                <div className="overflow-hidden rounded-2xl shadow-[0_0_0_1px_rgba(15,23,42,0.10)]">{selected.resultPreview.map((item) => <div key={item} className="flex min-h-16 items-start gap-3 px-4 py-4 shadow-[inset_0_-1px_rgba(15,23,42,0.06)] last:shadow-none sm:px-5"><span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-100 text-emerald-700"><Check className="h-4 w-4" /></span><span className="text-pretty text-sm leading-6 text-slate-700">{item}</span></div>)}</div>
                {partialPreview?.mechanic || selectedOpportunity?.mechanic ? <div className="mt-5 rounded-2xl bg-emerald-50 p-5 text-sm leading-6 text-emerald-950"><strong className="block">Рекомендуемая механика</strong><span className="mt-1 block">{partialPreview?.mechanic || selectedOpportunity?.mechanic}</span>{partialPreview?.message_excerpt || selectedOpportunity?.message_excerpt ? <span className="mt-3 block italic">«{partialPreview?.message_excerpt || selectedOpportunity?.message_excerpt}…»</span> : null}</div> : null}
                <div className="relative mt-5 overflow-hidden rounded-2xl bg-slate-100 p-5"><div className="select-none space-y-2 opacity-30 blur-[3px]" aria-hidden="true"><div className="h-3 w-4/5 rounded bg-slate-500" /><div className="h-3 w-full rounded bg-slate-400" /><div className="h-3 w-2/3 rounded bg-slate-500" /></div><div className="absolute inset-0 grid place-items-center p-5 text-center text-sm font-semibold text-slate-800">{selected.lockedResult}</div></div>
                {journeyError ? <p className="mt-4 text-sm text-red-700">{journeyError}</p> : null}
                <div className="mt-7 grid gap-5 rounded-2xl bg-orange-50 p-5 shadow-[0_0_0_1px_rgba(249,115,22,0.22)] sm:grid-cols-[1fr_auto] sm:items-center"><div><strong className="text-lg">Завершите уже выбранное действие</strong><p className="mt-1 text-pretty text-sm leading-6 text-slate-600">Создайте бизнес-профиль. Выбор сохранится, а кабинет откроет этот шаг.</p></div><Button asChild className="min-h-12 rounded-xl px-5 transition-transform active:scale-[0.96]"><Link to={registrationUrl} onClick={() => { saveLeadJourneyIntent(selected.key); if (token) { saveLeadJourneyToken(token); void trackPublicJourneyEvent(token, 'registration_started', selectedOpportunity); } }}>Завершить действие<ArrowRight className="h-5 w-5" /></Link></Button></div>
              </>}
            </div>
          </div>
          <div className="mt-6 grid gap-3 rounded-2xl bg-white p-5 text-sm text-slate-600 shadow-[0_0_0_1px_rgba(15,23,42,0.06)] sm:grid-cols-3"><span><strong className="block text-slate-950">1. Действие</strong>Готовый материал и ручное подтверждение.</span><span><strong className="block text-slate-950">2. Статус или результат</strong>Ответ, публикация, исправление или отсутствие реакции.</span><span><strong className="block text-slate-950">3. Следующий шаг</strong>Продолжение по фактическому результату.</span></div>
          <p className="mt-5 flex items-start gap-2 text-pretty text-xs leading-5 text-slate-500"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />Внешние отправки и изменения остаются под ручным подтверждением.</p>
          {journeySelectedKey ? <section className="mt-10 border-t border-slate-200 pt-8" aria-label="Другие возможности LocalOS"><h2 className="text-balance text-xl font-semibold text-slate-950">Что ещё можно улучшить</h2><p className="mt-2 text-pretty text-sm text-slate-600">Другие области можно посмотреть позже — выбранное действие сохранится.</p><div className="mt-5 grid gap-3 md:grid-cols-3">{leadJourneyDirections.filter((direction) => direction.key !== journeySelectedKey).map((direction) => <DirectionCard key={direction.key} direction={direction} opportunity={opportunityForKey(direction.key)} onOpen={() => undefined} secondary />)}</div></section> : null}
        </section>}
      </div>
    </main>
  );
}
