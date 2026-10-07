import { useState } from 'react';
import { Check, Loader2, Send } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';
import { CreatorCityCombobox } from './CreatorCityCombobox';

type DistributionPreview = {
  eligible: number;
  active_accounts: number;
  pending_accounts: number;
  shortlisted: number;
  excluded: number;
  excluded_reasons?: Record<string, number>;
};

type CreatorOfferBuilderProps = {
  businessId: string;
  businessCity?: string;
  cityOptions?: string[];
  onSubmitted: () => Promise<void>;
};

const exclusionLabels: Record<string, string> = {
  excluded_for_business: 'убраны этим бизнесом',
  creator_paused: 'автор на паузе',
  category_blocked: 'категория запрещена автором',
  geography_unknown: 'география не подтверждена',
  geography_mismatch: 'география не подходит',
  topic_mismatch: 'тематика не подходит',
  barter_unconfirmed: 'бартер не подтверждён',
  format_mismatch: 'формат не подходит',
  brand_safety: 'профиль заблокирован',
};

export const CreatorOfferBuilder = ({ businessId, businessCity = '', cityOptions = [], onSubmitted }: CreatorOfferBuilderProps) => {
  const [campaignId, setCampaignId] = useState('');
  const [preview, setPreview] = useState<DistributionPreview | null>(null);
  const [previewFingerprint, setPreviewFingerprint] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState({
    title: '', service: '', benefit: '', resultCondition: '', city: businessCity,
    districts: '', metros: '', topics: '', formats: '', category: '', capacity: '3',
    endAt: '', requirements: '', restrictions: '', rewardType: 'service', rewardTrigger: 'result',
    moneyAmount: '', currency: 'RUB', requiredDeliverablesCount: '1',
    attributionMethod: 'promo_code', promoCode: '', destinationUrl: '', attributionDays: '14', resultTarget: '3',
  });

  const payload = () => ({
    business_id: businessId,
    title: form.title || `Предложение: ${form.service}`,
    goal: form.rewardTrigger === 'result' ? form.resultCondition || 'Получить отклики от локальных авторов' : `Публикаций от автора: ${form.requiredDeliverablesCount}`,
    geography: { city: form.city, districts: form.districts.split(',').map((item) => item.trim()).filter(Boolean), metros: form.metros.split(',').map((item) => item.trim()).filter(Boolean) },
    audience: { topics: form.topics.split(',').map((item) => item.trim()).filter(Boolean) },
    formats: form.formats.split(',').map((item) => item.trim()).filter(Boolean),
    offer: {
      service: form.service,
      benefit: form.rewardType === 'service' ? form.benefit : '',
      reward_type: form.rewardType,
      reward_trigger: form.rewardTrigger,
      result_condition: form.rewardTrigger === 'result' ? form.resultCondition : '',
      result_target: form.rewardTrigger === 'result' ? Number(form.resultTarget) : 0,
      required_deliverables_count: form.rewardTrigger === 'content' ? Number(form.requiredDeliverablesCount) : 1,
      money_amount: form.rewardType === 'money' ? Number(form.moneyAmount) : 0,
      currency: form.currency,
      barter: form.rewardType === 'service',
      compensation: form.rewardType === 'money' ? `${form.moneyAmount} ${form.currency}`.trim() : '',
      category: form.category || form.service,
      capacity: Number(form.capacity),
    },
    period: { end_at: form.endAt ? new Date(`${form.endAt}T23:59:59`).toISOString() : '' },
    constraints: { requirements: form.requirements, restrictions: form.restrictions, usage_rights: { organic_publication: true }, attribution: form.rewardTrigger === 'result' ? { method: form.attributionMethod, promo_code: form.promoCode, destination_url: form.destinationUrl, window_days: Number(form.attributionDays), result_target: Number(form.resultTarget) } : { method: 'publication_count' } },
  });

  const saveDraft = async () => {
    if (campaignId) {
      await newAuth.makeRequest(`/promotion/influencers/campaigns/${encodeURIComponent(campaignId)}`, { method: 'PATCH', body: JSON.stringify(payload()) });
      return campaignId;
    }
    const response = await newAuth.makeRequest('/promotion/influencers/campaigns', { method: 'POST', body: JSON.stringify(payload()) });
    const nextId = String(response.campaign?.id || '');
    if (!nextId) throw new Error('Не удалось создать черновик.');
    setCampaignId(nextId);
    return nextId;
  };

  const calculate = async () => {
    setBusy('preview'); setError(''); setNotice('');
    try {
      const id = await saveDraft();
      const response = await newAuth.makeRequest(`/promotion/influencers/campaigns/${encodeURIComponent(id)}/distribution-preview?business_id=${encodeURIComponent(businessId)}`);
      setPreview(response.preview || null);
      setPreviewFingerprint(JSON.stringify(payload()));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось рассчитать получателей.');
    } finally { setBusy(''); }
  };

  const submit = async () => {
    setBusy('submit'); setError('');
    try {
      if (!campaignId || previewFingerprint !== JSON.stringify(payload())) {
        setError('Условия изменились. Пересчитайте получателей перед отправкой.');
        return;
      }
      const id = campaignId;
      await newAuth.makeRequest(`/promotion/influencers/campaigns/${encodeURIComponent(id)}/submit`, { method: 'POST', body: JSON.stringify({ business_id: businessId }) });
      setNotice('Предложение передано LocalOS. До проверки авторы его не увидят.');
      setSubmitted(true);
      await onSubmitted();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось передать предложение.');
    } finally { setBusy(''); }
  };

  return <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
    <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-600">Новое предложение</p><h2 className="mt-2 text-balance text-2xl font-semibold text-slate-950">Что получит автор и за что?</h2><p className="mt-2 text-pretty text-sm leading-6 text-slate-600">LocalOS проверит условия и выдаст их всем подходящим авторам. Отметка «Подходит» влияет на приоритет, но не ограничивает охват.</p></div>
    {error ? <div role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{error}</div> : null}{notice ? <div className="mt-4 flex gap-2 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800"><Check className="h-4 w-4 shrink-0" />{notice}</div> : null}
    <div className="mt-6 grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-semibold text-slate-700">Название<Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Например, семейная стрижка за результат" className="mt-2" /></label>
      <label className="text-sm font-semibold text-slate-700">Что продвигаем<Input value={form.service} onChange={(event) => setForm({ ...form, service: event.target.value })} placeholder="Детская стрижка" className="mt-2" /></label>
      <label className="text-sm font-semibold text-slate-700">Категория<Input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} placeholder="семейные услуги" className="mt-2" /></label>
      <div className="grid gap-4 rounded-[20px] bg-slate-50 p-4 sm:col-span-2 sm:grid-cols-2">
        <fieldset><legend className="text-sm font-semibold text-slate-800">Что получит автор?</legend><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" aria-pressed={form.rewardType === 'service'} onClick={() => setForm({ ...form, rewardType: 'service' })} className={cn('min-h-11 rounded-xl px-3 text-sm font-semibold transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', form.rewardType === 'service' ? 'bg-slate-950 text-white' : 'bg-white text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}>Услугу</button><button type="button" aria-pressed={form.rewardType === 'money'} onClick={() => setForm({ ...form, rewardType: 'money' })} className={cn('min-h-11 rounded-xl px-3 text-sm font-semibold transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', form.rewardType === 'money' ? 'bg-slate-950 text-white' : 'bg-white text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}>Деньги</button></div></fieldset>
        <fieldset><legend className="text-sm font-semibold text-slate-800">За что?</legend><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" aria-pressed={form.rewardTrigger === 'content'} onClick={() => setForm({ ...form, rewardTrigger: 'content' })} className={cn('min-h-11 rounded-xl px-3 text-sm font-semibold transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', form.rewardTrigger === 'content' ? 'bg-slate-950 text-white' : 'bg-white text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}>За публикации</button><button type="button" aria-pressed={form.rewardTrigger === 'result'} onClick={() => setForm({ ...form, rewardTrigger: 'result' })} className={cn('min-h-11 rounded-xl px-3 text-sm font-semibold transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', form.rewardTrigger === 'result' ? 'bg-slate-950 text-white' : 'bg-white text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}>За результат</button></div></fieldset>
      </div>
      {form.rewardType === 'service' ? <label className="text-sm font-semibold text-slate-700">Какую услугу получит автор<Input value={form.benefit} onChange={(event) => setForm({ ...form, benefit: event.target.value })} placeholder="Бесплатная стрижка" className="mt-2" /></label> : <><label className="text-sm font-semibold text-slate-700">Сумма<Input type="number" min="1" value={form.moneyAmount} onChange={(event) => setForm({ ...form, moneyAmount: event.target.value })} placeholder="5000" className="mt-2 tabular-nums" /></label><label className="text-sm font-semibold text-slate-700">Валюта<select value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })} className="mt-2 min-h-10 w-full rounded-md border border-input bg-background px-3 text-sm font-normal"><option value="RUB">Рубли</option><option value="EUR">Евро</option><option value="USD">Доллары</option></select></label></>}
      {form.rewardTrigger === 'result' ? <><label className="text-sm font-semibold text-slate-700">Условие результата<Input value={form.resultCondition} onChange={(event) => setForm({ ...form, resultCondition: event.target.value })} placeholder="Если придут 3 новых клиента" className="mt-2" /></label><label className="text-sm font-semibold text-slate-700">Целевое количество<Input type="number" min="1" value={form.resultTarget} onChange={(event) => setForm({ ...form, resultTarget: event.target.value })} className="mt-2 tabular-nums" /></label></> : <label className="text-sm font-semibold text-slate-700">Сколько публикаций нужно<Input type="number" min="1" value={form.requiredDeliverablesCount} onChange={(event) => setForm({ ...form, requiredDeliverablesCount: event.target.value })} className="mt-2 tabular-nums" /></label>}
      <CreatorCityCombobox label="Город" value={form.city} options={cityOptions.length ? cityOptions : [businessCity].filter(Boolean)} onChange={(city) => setForm({ ...form, city })} className="text-sm text-slate-700" />
      <label className="text-sm font-semibold text-slate-700">Районы<Input value={form.districts} onChange={(event) => setForm({ ...form, districts: event.target.value })} placeholder="Выборгский" className="mt-2" /></label>
      <label className="text-sm font-semibold text-slate-700">Метро<Input value={form.metros} onChange={(event) => setForm({ ...form, metros: event.target.value })} placeholder="Проспект Просвещения" className="mt-2" /></label>
      <label className="text-sm font-semibold text-slate-700">Темы<Input value={form.topics} onChange={(event) => setForm({ ...form, topics: event.target.value })} placeholder="семья, дети, места" className="mt-2" /></label>
      <label className="text-sm font-semibold text-slate-700">Форматы<Input value={form.formats} onChange={(event) => setForm({ ...form, formats: event.target.value })} placeholder="пост, stories, видео" className="mt-2" /></label>
      <label className="text-sm font-semibold text-slate-700">Количество мест<Input type="number" min="1" value={form.capacity} onChange={(event) => setForm({ ...form, capacity: event.target.value })} className="mt-2 tabular-nums" /></label>
      <label className="text-sm font-semibold text-slate-700">Принимать отклики до<Input type="date" value={form.endAt} onChange={(event) => setForm({ ...form, endAt: event.target.value })} className="mt-2" /></label>
      {form.rewardTrigger === 'result' ? <div className="rounded-[20px] bg-slate-50 p-4 sm:col-span-2"><h3 className="text-balance text-sm font-semibold text-slate-900">Как поймём, что результат достигнут</h3><p className="mt-1 text-pretty text-xs leading-5 text-slate-500">Укажите один понятный способ. Автор увидит его в условиях предложения.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-sm font-semibold text-slate-700">Способ учёта<select value={form.attributionMethod} onChange={(event) => setForm({ ...form, attributionMethod: event.target.value })} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 font-normal"><option value="promo_code">Промокод автора</option><option value="booking_question">Вопрос при записи</option><option value="tracked_link">Отслеживаемая ссылка</option><option value="manual">Ручное подтверждение</option></select></label><label className="text-sm font-semibold text-slate-700">Окно учёта, дней<Input type="number" min="1" value={form.attributionDays} onChange={(event) => setForm({ ...form, attributionDays: event.target.value })} className="mt-2 tabular-nums" /></label>{form.attributionMethod === 'promo_code' ? <label className="text-sm font-semibold text-slate-700 sm:col-span-2">Промокод<Input value={form.promoCode} onChange={(event) => setForm({ ...form, promoCode: event.target.value })} placeholder="Например, ALEXANDR" className="mt-2" /></label> : null}{form.attributionMethod === 'tracked_link' ? <label className="text-sm font-semibold text-slate-700 sm:col-span-2">Ссылка на запись<Input type="url" value={form.destinationUrl} onChange={(event) => setForm({ ...form, destinationUrl: event.target.value })} placeholder="https://..." className="mt-2" /></label> : null}</div></div> : <div className="rounded-[20px] bg-slate-50 p-4 text-sm leading-6 text-slate-600 sm:col-span-2">Выполнение считается по количеству проверенных публикаций, ссылки на которые автор передаст в LocalOS.</div>}
      <label className="text-sm font-semibold text-slate-700 sm:col-span-2">Требования к публикации<Textarea value={form.requirements} onChange={(event) => setForm({ ...form, requirements: event.target.value })} className="mt-2" /></label>
      <label className="text-sm font-semibold text-slate-700 sm:col-span-2">Ограничения<Textarea value={form.restrictions} onChange={(event) => setForm({ ...form, restrictions: event.target.value })} className="mt-2" /></label>
    </div>
    <div className="mt-6 flex flex-wrap gap-3"><Button type="button" variant="outline" onClick={() => void calculate()} disabled={Boolean(busy) || submitted}>{busy === 'preview' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}Рассчитать получателей</Button><Button type="button" onClick={() => void submit()} disabled={Boolean(busy) || !preview || submitted} className="bg-slate-950">{busy === 'submit' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}Передать LocalOS</Button></div>
    {preview ? <div className="mt-6 rounded-2xl bg-slate-50 p-4"><h3 className="font-semibold text-slate-950">Кто получит предложение после проверки</h3><div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">{[['Подходят', preview.eligible], ['С кабинетом', preview.active_accounts], ['После активации', preview.pending_accounts], ['Отмечены «Подходит»', preview.shortlisted], ['Исключены', preview.excluded]].map(([label, value]) => <div key={String(label)}><strong className="block text-xl tabular-nums">{value}</strong><span className="text-xs text-slate-500">{label}</span></div>)}</div>{preview.excluded_reasons ? <div className="mt-4 flex flex-wrap gap-2">{Object.entries(preview.excluded_reasons).map(([reason, count]) => <span key={reason} className="rounded-full bg-white px-3 py-1 text-xs text-slate-600">{exclusionLabels[reason] || reason}: <span className="tabular-nums">{count}</span></span>)}</div> : null}</div> : null}
  </section>;
};
