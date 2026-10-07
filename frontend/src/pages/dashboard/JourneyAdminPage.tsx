import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, Clipboard, Eye, Link2, Loader2, RotateCcw, ShieldCheck, UserRound } from 'lucide-react';

import { DashboardEmptyState, DashboardPageHeader, DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';
import { leadJourneyDirections, leadJourneyKeyForFlow, type JourneyOpportunity, type LeadJourneyKey } from '@/lib/leadJourney';
import { cn } from '@/lib/utils';

type AdminContext = { user?: { is_superadmin?: boolean } | null };
type AdminLead = { id: string; name?: string; city?: string; address?: string; category?: string };
type SafePreview = { business_name?: string; business_city?: string; business_address?: string; opportunities: JourneyOpportunity[] };
type CreatedJourney = { id: string; status: string; selected_flow?: string | null; expires_at?: string; public_url?: string; public_path?: string };
type JourneyListItem = CreatedJourney & { lead_name?: string; latest_action?: { title?: string; status?: string } | null; latest_event?: { command?: string; occurred_at?: string } | null };
type Step = 'client' | 'path' | 'preview' | 'link';
type PreviewMode = 'public' | 'registered' | 'paid';
const previewModes: PreviewMode[] = ['public', 'registered', 'paid'];

const flowForKey = (key: LeadJourneyKey) => key === 'influencers' ? 'influencer' : key === 'partnerships' ? 'partnership' : key;

const firstMessage = (flow: LeadJourneyKey, link: string, title: string, mechanic: string, examples: string) => {
  if (flow === 'influencers') return `Мы работаем с микроинфлюенсерами и активными локальными авторами.${examples.trim() ? ` Вот несколько примеров: ${examples.trim().split(/\s+/).join(' ')}` : ''} Для вас подготовили механику: ${mechanic} После регистрации вы сразу попадёте в подборку авторов: ${link}`;
  if (flow === 'partnerships') return `Нашли пример бизнеса с пересекающейся аудиторией и идею партнёрства. Посмотрите предложение: ${link}`;
  if (flow === 'maps') return `Нашли первое изменение карточки, которое стоит сделать сейчас. Посмотрите задачу и объяснение: ${link}`;
  if (flow === 'automation') return `Нашли повторяющуюся задачу, которую можно поручить LocalOS под вашим контролем. Посмотрите сценарий и границы автоматизации: ${link}`;
  if (flow === 'average_ticket') return `Нашли первый безопасный сценарий роста среднего чека. Посмотрите связку услуг и расчёт: ${link}`;
  return `Подготовили тему «${title}» и пример первого материала для вашего бизнеса. Посмотрите черновик: ${link}`;
};

export const JourneyAdminPage = () => {
  const navigate = useNavigate();
  const { user } = useOutletContext<AdminContext>();
  const [step, setStep] = useState<Step>('client');
  const [leads, setLeads] = useState<AdminLead[]>([]);
  const [journeys, setJourneys] = useState<JourneyListItem[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState('');
  const [selectedKey, setSelectedKey] = useState<LeadJourneyKey | null>(null);
  const [preview, setPreview] = useState<SafePreview | null>(null);
  const [previewMode, setPreviewMode] = useState<PreviewMode>('public');
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [reason, setReason] = useState('');
  const [mechanic, setMechanic] = useState('');
  const [excerpt, setExcerpt] = useState('');
  const [barterService, setBarterService] = useState('');
  const [barterValue, setBarterValue] = useState('');
  const [barterThreshold, setBarterThreshold] = useState('3');
  const [barterReward, setBarterReward] = useState('');
  const [barterConstraints, setBarterConstraints] = useState('');
  const [barterValidUntil, setBarterValidUntil] = useState('');
  const [exampleLinks, setExampleLinks] = useState('');
  const [expiresInDays, setExpiresInDays] = useState('30');
  const [created, setCreated] = useState<CreatedJourney | null>(null);
  const [createdMessage, setCreatedMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const selectedLead = leads.find((lead) => lead.id === selectedLeadId) || null;
  const selectedFlow = selectedKey ? flowForKey(selectedKey) : '';
  const selectedOpportunity = preview?.opportunities.find((item) => item.flow_type === selectedFlow) || null;

  const loadJourneys = () => newAuth.makeRequest('/journeys').then((data) => {
    setJourneys(Array.isArray(data.journeys) ? data.journeys : []);
  });

  useEffect(() => {
    if (!user?.is_superadmin) {
      setLoading(false);
      return;
    }
    const params = new URLSearchParams({ compact: '1', include_groups: '0', include_timeline: '0', page_size: '100' });
    Promise.all([
      newAuth.makeRequest(`/admin/prospecting/leads?${params.toString()}`).then((data) => setLeads(Array.isArray(data.leads) ? data.leads : [])),
      loadJourneys(),
    ]).catch((caught) => setError(caught instanceof Error ? caught.message : 'Не удалось загрузить маршруты')).finally(() => setLoading(false));
  }, [user?.is_superadmin]);

  const chooseClient = async () => {
    if (!selectedLeadId) return;
    setBusy('preview');
    setError('');
    try {
      const data = await newAuth.makeRequest(`/journeys/preview?lead_id=${encodeURIComponent(selectedLeadId)}`);
      setPreview(data.preview || null);
      setStep('path');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось подготовить данные клиента');
    } finally {
      setBusy('');
    }
  };

  const choosePath = (key: LeadJourneyKey) => {
    const opportunity = preview?.opportunities.find((item) => item.flow_type === flowForKey(key));
    setSelectedKey(key);
    setTitle(opportunity?.title || 'Первый полезный результат');
    setSummary(opportunity?.summary || 'Покажем один конкретный результат для этого бизнеса.');
    setReason(opportunity?.reason || 'Этот путь соответствует текущей задаче клиента.');
    setMechanic(opportunity?.mechanic || 'Начать с одного безопасного действия.');
    setExcerpt(opportunity?.message_excerpt || '');
    setBarterService('');
    setBarterValue('');
    setBarterThreshold('3');
    setBarterReward('');
    setBarterConstraints('');
    setBarterValidUntil('');
    setExampleLinks(opportunity?.public_url || '');
    setStep('preview');
  };

  const updateBarterService = (service: string) => {
    setBarterService(service);
    if (!service.trim()) return;
    const reward = barterReward.trim() || `${service.trim()} в подарок`;
    setMechanic(`Автор рассказывает о бизнесе и получает ${reward}, если по его рекомендации приходят ${barterThreshold || '3'} новых клиента.`);
  };

  const regenerateBarterMechanic = () => {
    if (!barterService.trim()) return;
    const reward = barterReward.trim() || `${barterService.trim()} в подарок`;
    setMechanic(`Автор рассказывает о бизнесе и получает ${reward}, если по его рекомендации приходят ${barterThreshold || '3'} новых клиента.`);
  };

  const createJourney = async () => {
    if (!selectedKey || !preview || !selectedLeadId) return;
    if (selectedKey === 'influencers' && !barterService.trim()) {
      setError('Укажите услугу, из которой LocalOS подготовит бартерное предложение.');
      return;
    }
    setBusy('create');
    setError('');
    const baseOpportunity = selectedOpportunity;
    const nextOpportunity: JourneyOpportunity = {
      flow_type: flowForKey(selectedKey),
      entity_type: baseOpportunity?.entity_type || `${flowForKey(selectedKey)}_preview`,
      entity_id: baseOpportunity?.entity_id || '',
      title: title.trim(),
      summary: summary.trim(),
      reason: reason.trim(),
      mechanic: mechanic.trim(),
      message_excerpt: excerpt.trim(),
      metrics: selectedKey === 'influencers' ? {
        ...(baseOpportunity?.metrics || {}),
        offer_service: barterService.trim(),
        offer_value: barterValue.trim(),
        offer_threshold: Number(barterThreshold || 3),
        offer_reward: (barterReward.trim() || `${barterService.trim()} в подарок`).trim(),
        offer_constraints: barterConstraints.trim(),
        offer_valid_until: barterValidUntil,
        offer_version: 1,
        offer_status: 'approved',
        example_links: exampleLinks.trim().split(/\s+/).join(' ').slice(0, 160),
      } : baseOpportunity?.metrics || {},
      tasks: baseOpportunity?.tasks || [],
      count: baseOpportunity?.count || 0,
    };
    const opportunities = preview.opportunities.map((item) => item.flow_type === nextOpportunity.flow_type ? nextOpportunity : item);
    try {
      const data = await newAuth.makeRequest('/journeys', {
        method: 'POST',
        body: JSON.stringify({
          lead_id: selectedLeadId,
          selected_flow: nextOpportunity.flow_type,
          selected_entity_type: nextOpportunity.entity_type,
          selected_entity_id: nextOpportunity.entity_id || undefined,
          expires_in_days: Number(expiresInDays || 30),
          source: 'admin_journey_builder',
          preview: { ...preview, opportunities },
        }),
      });
      const publicUrl = String(data.public_url || `${window.location.origin}${data.public_path || ''}`);
      const result = { ...data.journey, public_url: publicUrl, public_path: data.public_path };
      setCreated(result);
      setCreatedMessage(firstMessage(selectedKey, publicUrl, title, mechanic, exampleLinks));
      setStep('link');
      await loadJourneys();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось создать персональную ссылку');
    } finally {
      setBusy('');
    }
  };

  const reset = () => {
    setStep('client');
    setSelectedLeadId('');
    setSelectedKey(null);
    setPreview(null);
    setCreated(null);
    setCreatedMessage('');
    setError('');
  };

  const revoke = async (journeyId: string) => {
    setBusy(journeyId);
    try {
      await newAuth.makeRequest(`/journeys/${encodeURIComponent(journeyId)}/revoke`, { method: 'POST' });
      await loadJourneys();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось отозвать ссылку');
    } finally {
      setBusy('');
    }
  };

  const progress = useMemo(() => ['client', 'path', 'preview', 'link'].indexOf(step) + 1, [step]);

  if (!user?.is_superadmin) return <DashboardEmptyState title="Доступ только для администратора" description="Создание персональных маршрутов меняет публичные ссылки и доступно только superadmin." />;
  if (loading) return <div className="grid min-h-[50vh] place-items-center"><Loader2 className="h-8 w-8 animate-spin text-orange-600" /></div>;

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-12">
      <DashboardPageHeader eyebrow="Bazich admin" title="Маршрут клиента" description="Выберите проблему, проверьте путь глазами клиента и отправьте одну персональную ссылку." icon={Link2} actions={<Button type="button" variant="outline" onClick={() => navigate('/dashboard/bazich')} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><ArrowLeft className="h-4 w-4" />В админку</Button>} />

      <div className="grid grid-cols-4 gap-2" aria-label="Этапы создания маршрута">{['Клиент', 'Проблема', 'Предпросмотр', 'Ссылка'].map((label, index) => <div key={label} className={cn('rounded-2xl px-3 py-3 text-center text-xs font-semibold shadow-[0_0_0_1px_rgba(15,23,42,0.07)]', index + 1 <= progress ? 'bg-slate-950 text-white' : 'bg-white text-slate-500')}><span className="tabular-nums">{index + 1}.</span> {label}</div>)}</div>

      {error ? <section className="rounded-2xl bg-red-50 p-4 text-sm text-red-800 shadow-[0_0_0_1px_rgba(185,28,28,0.12)]">{error}</section> : null}

      {step === 'preview' && selectedKey === 'influencers' ? <DashboardSection title="Примеры авторов для сообщения" description="Добавьте обычные публичные ссылки. Они попадут в готовый текст; отдельная public-страница не нужна."><label className="block text-sm font-medium text-slate-700">По одной ссылке на строку<Textarea value={exampleLinks} onChange={(event) => setExampleLinks(event.target.value)} placeholder={'https://t.me/example\nhttps://vk.com/example'} className="mt-2 min-h-28" /></label></DashboardSection> : null}

      {step === 'preview' && selectedKey === 'influencers' ? <DashboardSection title="Услуга для бартера" description="Укажите услугу — LocalOS сразу соберёт общую механику сотрудничества."><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><label className="block text-sm font-medium text-slate-700">Название услуги<Input value={barterService} onChange={(event) => updateBarterService(event.target.value)} placeholder="Например, стрижка" className="mt-2 min-h-11" /></label><label className="block text-sm font-medium text-slate-700">Обычная стоимость<Input value={barterValue} onChange={(event) => setBarterValue(event.target.value)} placeholder="2 500 ₽" className="mt-2 min-h-11 tabular-nums" /></label><label className="block text-sm font-medium text-slate-700">Сколько клиентов<Input type="number" min="1" value={barterThreshold} onChange={(event) => setBarterThreshold(event.target.value)} onBlur={regenerateBarterMechanic} className="mt-2 min-h-11 tabular-nums" /></label><label className="block text-sm font-medium text-slate-700">Вознаграждение<Input value={barterReward} onChange={(event) => setBarterReward(event.target.value)} onBlur={regenerateBarterMechanic} placeholder={barterService ? `${barterService} в подарок` : 'Услуга в подарок'} className="mt-2 min-h-11" /></label><label className="block text-sm font-medium text-slate-700">Ограничения<Input value={barterConstraints} onChange={(event) => setBarterConstraints(event.target.value)} placeholder="Будни, один автор" className="mt-2 min-h-11" /></label><label className="block text-sm font-medium text-slate-700">Действует до<Input type="date" value={barterValidUntil} onChange={(event) => setBarterValidUntil(event.target.value)} className="mt-2 min-h-11 tabular-nums" /></label></div><div className="mt-5 rounded-2xl bg-orange-50 p-4 text-pretty text-sm leading-6 text-orange-950"><strong className="block">Подготовленное предложение</strong><span>{mechanic || 'Назовите услугу, чтобы увидеть механику.'}</span></div></DashboardSection> : null}

      {step === 'client' ? <DashboardSection title="Для кого создаём маршрут" description="Выберите существующего потенциального клиента. Данные бизнеса используются только для безопасного preview."><Select value={selectedLeadId} onValueChange={setSelectedLeadId}><SelectTrigger className="min-h-12"><SelectValue placeholder="Выберите клиента" /></SelectTrigger><SelectContent>{leads.map((lead) => <SelectItem key={lead.id} value={lead.id}>{[lead.name || 'Без названия', lead.city].filter(Boolean).join(' · ')}</SelectItem>)}</SelectContent></Select><Button type="button" onClick={() => void chooseClient()} disabled={!selectedLeadId || Boolean(busy)} className="mt-5 min-h-11 gap-2 transition-transform active:scale-[0.96]">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserRound className="h-4 w-4" />}Выбрать проблему<ArrowRight className="h-4 w-4" /></Button></DashboardSection> : null}

      {step === 'path' ? <DashboardSection title={`С какой задачей пришёл ${selectedLead?.name || 'клиент'}`} description="Выбранный путь станет главным. Остальные области останутся доступными для просмотра позже."><div className="grid gap-3 md:grid-cols-2">{leadJourneyDirections.map((direction) => <button key={direction.key} type="button" onClick={() => choosePath(direction.key)} className="min-h-36 rounded-[24px] bg-slate-50 p-5 text-left shadow-[0_0_0_1px_rgba(15,23,42,0.07)] transition-[box-shadow,transform] hover:shadow-[0_0_0_1px_rgba(249,115,22,0.35),0_16px_40px_-30px_rgba(15,23,42,0.45)] active:scale-[0.96]"><span className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">{direction.eyebrow}</span><strong className="mt-2 block text-balance text-lg text-slate-950">{direction.title}</strong><span className="mt-2 block text-pretty text-sm leading-6 text-slate-600">{direction.preview}</span></button>)}</div><Button type="button" variant="outline" onClick={() => setStep('client')} className="mt-5 min-h-11">Назад</Button></DashboardSection> : null}

      {step === 'preview' && selectedKey ? <DashboardSection title="Проверьте пример и границу доступа" description="Редактируйте только подтверждённые данные. Полный результат и закрытые контакты в public preview не попадают."><div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]"><div className="space-y-4"><label className="block text-sm font-medium text-slate-700">Заголовок<Input value={title} onChange={(event) => setTitle(event.target.value)} className="mt-2 min-h-11" /></label><label className="block text-sm font-medium text-slate-700">Что увидит клиент<Textarea value={summary} onChange={(event) => setSummary(event.target.value)} className="mt-2 min-h-24" /></label><label className="block text-sm font-medium text-slate-700">Почему это подходит<Textarea value={reason} onChange={(event) => setReason(event.target.value)} className="mt-2 min-h-24" /></label><label className="block text-sm font-medium text-slate-700">Механика<Input value={mechanic} onChange={(event) => setMechanic(event.target.value)} className="mt-2 min-h-11" /></label><label className="block text-sm font-medium text-slate-700">Короткий фрагмент<Textarea value={excerpt} onChange={(event) => setExcerpt(event.target.value)} maxLength={180} className="mt-2 min-h-24" /></label><label className="block text-sm font-medium text-slate-700">Срок ссылки, дней<Input type="number" min="1" max="90" value={expiresInDays} onChange={(event) => setExpiresInDays(event.target.value)} className="mt-2 min-h-11" /></label></div><div><div className="grid grid-cols-3 gap-1 rounded-2xl bg-slate-100 p-1">{previewModes.map((mode) => <button key={mode} type="button" onClick={() => setPreviewMode(mode)} className={cn('min-h-10 rounded-xl px-2 text-xs font-semibold transition-colors', previewMode === mode ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500')}>{mode === 'public' ? 'До входа' : mode === 'registered' ? 'После входа' : 'Оплачено'}</button>)}</div><div className="mt-4 rounded-[24px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_18px_45px_-34px_rgba(15,23,42,0.5)]"><span className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">{leadJourneyDirections.find((item) => item.key === selectedKey)?.eyebrow}</span><h3 className="mt-2 text-balance text-xl font-semibold text-slate-950">{title}</h3><p className="mt-3 text-pretty text-sm leading-6 text-slate-600">{summary}</p><div className="mt-4 rounded-2xl bg-orange-50 p-3 text-sm text-orange-950">{previewMode === 'public' ? 'Виден безопасный пример. Полный результат откроется после регистрации.' : previewMode === 'registered' ? 'Открыт рабочий шаг. Платная генерация объясняется отдельно.' : 'Доступны оплаченные действия, но публикация и отправка всё равно требуют подтверждения.'}</div><Button type="button" className="mt-4 min-h-11 w-full" disabled>{previewMode === 'public' ? 'Продолжить' : previewMode === 'registered' ? 'Открыть рабочий шаг' : 'Выполнить действие'}</Button></div></div></div><div className="mt-6 flex flex-col gap-2 sm:flex-row"><Button type="button" variant="outline" onClick={() => setStep('path')} className="min-h-11">Назад</Button><Button type="button" onClick={() => void createJourney()} disabled={!title.trim() || !summary.trim() || Boolean(busy)} className="min-h-11 gap-2 transition-transform active:scale-[0.96]">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}Создать персональную ссылку</Button></div></DashboardSection> : null}

      {step === 'link' && created ? <DashboardSection title="Маршрут готов" description="Ссылка ведёт на выбранную проблему и после регистрации возвращает клиента к конкретному действию."><div className="rounded-[24px] bg-emerald-50 p-5 shadow-[0_0_0_1px_rgba(5,150,105,0.16)]"><div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-emerald-100 text-emerald-700"><Check className="h-5 w-5" /></span><div><strong className="text-emerald-950">Персональная ссылка создана</strong><p className="mt-1 break-all text-sm text-emerald-900">{created.public_url}</p></div></div></div><label className="mt-5 block text-sm font-medium text-slate-700">Готовое сообщение<Textarea value={createdMessage} onChange={(event) => setCreatedMessage(event.target.value)} className="mt-2 min-h-32" /></label><div className="mt-5 flex flex-col gap-2 sm:flex-row"><Button type="button" onClick={() => void navigator.clipboard.writeText(createdMessage)} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><Clipboard className="h-4 w-4" />Скопировать сообщение</Button><Button type="button" variant="outline" onClick={() => window.open(created.public_url || '', '_blank', 'noopener,noreferrer')} className="min-h-11 gap-2"><Eye className="h-4 w-4" />Открыть глазами клиента</Button><Button type="button" variant="outline" onClick={reset} className="min-h-11 gap-2"><RotateCcw className="h-4 w-4" />Создать ещё</Button></div><p className="mt-5 flex items-start gap-2 text-pretty text-xs leading-5 text-slate-500"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />Ссылка не открывает внешнюю отправку или публикацию без отдельного подтверждения.</p></DashboardSection> : null}

      <DashboardSection title="Последние маршруты" description="Текущий шаг, последнее событие и возможность быстро отозвать ссылку."><div className="divide-y divide-slate-100">{journeys.length ? journeys.map((journey) => { const key = leadJourneyKeyForFlow(journey.selected_flow); const direction = leadJourneyDirections.find((item) => item.key === key); return <div key={journey.id} className="grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><strong className="truncate text-slate-950">{journey.lead_name || 'Клиент'}</strong><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">{direction?.eyebrow || journey.selected_flow || 'Legacy'}</span><span className="rounded-full bg-orange-50 px-2.5 py-1 text-xs font-semibold text-orange-800">{journey.status}</span></div><p className="mt-1 text-pretty text-sm text-slate-600">{journey.latest_action?.title || 'Клиент ещё не зарегистрировался'}</p>{journey.expires_at ? <p className="mt-1 text-xs tabular-nums text-slate-400">Действует до {new Date(journey.expires_at).toLocaleString('ru-RU')}</p> : null}</div><Button type="button" variant="outline" onClick={() => void revoke(journey.id)} disabled={journey.status === 'revoked' || busy === journey.id} className="min-h-10">{journey.status === 'revoked' ? 'Отозвана' : 'Отозвать'}</Button></div>; }) : <p className="py-5 text-sm text-slate-500">Маршрутов пока нет.</p>}</div></DashboardSection>
    </div>
  );
};
