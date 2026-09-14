import { useEffect, useId, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { voiceHeaders } from './OperatorVoice';

type Settings = { city?: string | null; currency?: string | null; timezone?: string | null; can_edit?: boolean; conflicts?: string[]; error?: string };

export function BusinessInputSettings({ businessId, onSubmit, disabled, headers = voiceHeaders }: {
  businessId: string; onSubmit: (text: string) => Promise<void>; disabled?: boolean; headers?: () => Record<string, string>;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState<Settings | null>(null);
  const [city, setCity] = useState('');
  const [currency, setCurrency] = useState('');
  const [timezone, setTimezone] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setSaved(null); setCity(''); setCurrency(''); setTimezone(''); setError(''); setLoading(true);
    fetch(`/api/operator/input-settings?business_id=${encodeURIComponent(businessId)}`, { headers: headers(), signal: controller.signal })
      .then(async response => {
        const data: Settings = await response.json();
        if (!response.ok) throw new Error(data.error || 'Настройки недоступны');
        if (controller.signal.aborted) return;
        setSaved(data); setCity(data.city || ''); setCurrency(data.currency || ''); setTimezone(data.timezone || '');
      }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить настройки'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [businessId, open, reload, headers]);
  const submit = async () => {
    const fields = [];
    if (city.trim() && city.trim() !== saved?.city) fields.push(`город: ${city.trim()}`);
    if (currency.trim() && currency.trim().toUpperCase() !== saved?.currency) fields.push(`валюта: ${currency.trim().toUpperCase()}`);
    if (timezone.trim() && timezone.trim() !== saved?.timezone) fields.push(`часовой пояс: ${timezone.trim()}`);
    if (!fields.length) { setError('Измените город, валюту или часовой пояс.'); return; }
    setSubmitting(true); setError('');
    try { await onSubmit('Сохрани настройки бизнеса: ' + fields.join('; ')); setOpen(false); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось подготовить настройки'); }
    finally { setSubmitting(false); }
  };
  return <section className="rounded-xl border border-border p-3 space-y-3">
    <Button type="button" variant="ghost" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>Город и валюта бизнеса</Button>
    {open && <div id={id} className="space-y-3">
      <p className="text-sm text-muted-foreground">Настройте местное время и валюту для дат и сумм. Можно сказать Оператору: «Установи город Таллин и валюту евро». Перед сохранением появится подтверждение в чате.</p>
      {loading && <p role="status">Загружаем настройки…</p>}
      {saved && <>
        {saved.conflicts?.length ? <p role="status">Ранее сохранённые настройки расходятся. Укажите нужные значения.</p> : null}
        {!saved.can_edit && <p>Менять настройки может владелец бизнеса.</p>}
        <fieldset disabled={!saved.can_edit || disabled || submitting} className="space-y-3">
          <label className="block text-sm" htmlFor={`${id}-city`}>Город<Input id={`${id}-city`} value={city} maxLength={120} placeholder="Например, Таллин" onChange={event => { setCity(event.target.value); setTimezone(''); }} /></label>
          <label className="block text-sm" htmlFor={`${id}-currency`}>Валюта<Input id={`${id}-currency`} value={currency} maxLength={3} placeholder="EUR" list={`${id}-currencies`} onChange={event => setCurrency(event.target.value.toUpperCase())} /></label>
          <datalist id={`${id}-currencies`}>{['EUR', 'RUB', 'USD', 'THB', 'KZT', 'GBP', 'AED', 'GEL', 'AMD', 'BYN'].map(value => <option key={value} value={value} />)}</datalist>
          <details><summary className="cursor-pointer text-sm">Часовой пояс</summary><label className="block text-sm mt-2" htmlFor={`${id}-timezone`}>Часовой пояс для дат<Input id={`${id}-timezone`} value={timezone} placeholder="Europe/Tallinn" onChange={event => setTimezone(event.target.value)} /></label><p className="text-xs text-muted-foreground">Для известного города предложим пояс. Если город неоднозначен, уточним его перед сохранением.</p></details>
          <Button type="button" onClick={() => void submit()} disabled={submitting}>{submitting ? 'Готовим…' : 'Проверить изменения в чате'}</Button>
        </fieldset>
      </>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!loading && !saved && <Button variant="outline" onClick={() => setReload(value => value + 1)}>Повторить загрузку</Button>}
    </div>}
  </section>;
}
