import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { newAuth } from '@/lib/auth_new';
import { mobileJsonHeaders, readMobileJson } from '@/lib/mobileDataClient';

type Schedule = { telegram_start: string; email_start: string; interval_minutes: number; first_touch_only?: boolean };
type Touch = { id: string; channel: string; recipient: string; sender_label: string; subject?: string; generated_text: string; scheduled_at: string; contact_source?: string };
type Item = { campaign_id: string; name: string; address?: string; touches: Touch[] };
type Preview = { digest: string; counts: { telegram: number; email: number }; company_count: number; touch_count: number; schedule: Schedule; runtime_ready: boolean; valid_until?: string; warning?: string; items: Item[] };
type Response = { preview?: Preview; launch?: { batch_id: string; company_count: number; touch_count: number } };
const moment = (value: string) => new Date(value).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow', dateStyle: 'short', timeStyle: 'short' });
const inputValue = (value: string) => {
  const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
  return parts.replace(' ', 'T');
};
export function PartnershipGroupLaunch({ businessId, collectionId, mobile = false }: { businessId: string; collectionId: string; mobile?: boolean }) {
  const [opened, setOpened] = useState(false), [preview, setPreview] = useState<Preview | null>(null), [schedule, setSchedule] = useState<Schedule | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [confirmation, setConfirmation] = useState(false);
  const [reviewed, setReviewed] = useState(false), [confirmed, setConfirmed] = useState(false), [receipt, setReceipt] = useState<Response['launch']>(undefined);
  const [firstOnly, setFirstOnly] = useState(true);
  const epoch = useRef(0);
  useEffect(() => { epoch.current++; setOpened(false); setPreview(null); setSchedule(null); setError(''); setBusy(false); setConfirmation(false); setReviewed(false); setConfirmed(false); setReceipt(undefined); return () => { epoch.current++; }; }, [businessId, collectionId, mobile]);
  const request = (data: object) => {
    const path = `/partnership/collections/${encodeURIComponent(collectionId)}/launch`;
    const options = { method: 'POST', body: JSON.stringify({ business_id: businessId, ...data }) };
    return mobile ? fetch(`/api${path}`, { ...options, headers: mobileJsonHeaders() }).then(readMobileJson<Response>) : newAuth.makeRequest(path, options);
  };
  const check = async () => {
    const version = ++epoch.current; setOpened(true); setBusy(true); setError(''); setPreview(null); setReviewed(false); setConfirmed(false);
    try { const result: Response = await request({ action: 'preview', schedule: { ...schedule, first_touch_only: firstOnly } }); if (epoch.current !== version) return; if (!result.preview) throw new Error('Проверка не завершена. Повторите загрузку.'); setPreview(result.preview); setSchedule(result.preview.schedule); }
    catch (issue) { if (epoch.current === version) setError(issue instanceof Error ? issue.message : 'Не удалось проверить группу.'); }
    finally { if (epoch.current === version) setBusy(false); }
  };
  const change = (value: Schedule) => { epoch.current++; setSchedule(value); setPreview(null); setError(''); setReviewed(false); setConfirmed(false); setConfirmation(false); setBusy(false); };
  const approve = async () => {
    if (!preview || !reviewed || !confirmed || busy || !preview.runtime_ready) return;
    const version = epoch.current; setBusy(true); setError('');
    try { const result: Response = await request({ action: 'confirm', schedule, digest: preview.digest, reviewed, confirmed }); if (epoch.current !== version) return; if (!result.launch) throw new Error('Статус не подтверждён. Обновите группу перед повтором.'); setReceipt(result.launch); setConfirmation(false); }
    catch (issue) { if (epoch.current === version) { setError(issue instanceof Error ? issue.message : 'Подтверждение не завершено. Обновите группу перед повтором.'); setConfirmation(false); setReviewed(false); setConfirmed(false); setPreview(null); } }
    finally { if (epoch.current === version) setBusy(false); }
  };
  const senderLabels = (channel: string) => Array.from(new Set((preview?.items || []).filter(item => item.touches[0].channel === channel).map(item => item.touches[0].sender_label))).join(', ') || 'Нет получателей';
  const firstRange = (channel: string) => { const dates = (preview?.items || []).filter(item => item.touches[0].channel === channel).map(item => item.touches[0].scheduled_at).sort(); return dates.length ? `${moment(dates[0])} — ${moment(dates[dates.length - 1])} МСК` : 'Нет получателей'; };
  if (receipt) return <section aria-label="Статус запуска группы" className="space-y-2 rounded-xl border border-border p-4"><h2 className="text-xl font-semibold">Расписание подтверждено</h2><p>Компаний: {receipt.company_count} · касаний в очереди: {receipt.touch_count}. Отправка начнётся по расписанию после штатных проверок. Постановка в очередь не означает доставку.</p></section>;
  return <section aria-label="Запуск подборки партнёров" className="space-y-4 rounded-xl border border-border bg-card p-4 text-card-foreground">
    <h2 className="text-xl font-semibold">Запустить эту подборку</h2>
    <p className="text-sm text-muted-foreground">Сначала компании с выбранным Telegram-контактом, затем остальные по почте. Одной компании — один канал. Готовые тексты сохранятся.</p>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={firstOnly} disabled={busy || confirmation} onChange={event => { setFirstOnly(event.target.checked); epoch.current++; setPreview(null); setReviewed(false); setConfirmed(false); }} />Только первые обращения. Повторные касания останутся черновиками.</label>
    {!opened ? <Button onClick={() => void check()}>Проверить запуск группы</Button> : <>
      {busy && <p role="status">Проверяем получателей, историю LocalOS, отправителей и даты… Ничего не отправляем.</p>}
      {error && <p role="alert">{error}</p>}
      {schedule && <fieldset disabled={busy} className="space-y-3"><legend className="font-semibold">Расписание · московское время</legend>
        <label className="block text-sm">Начало Telegram<input type="datetime-local" className="mt-1 min-h-11 w-full rounded-md border border-border bg-background p-2" value={inputValue(schedule.telegram_start)} onChange={event => { if (event.target.value) change({ ...schedule, telegram_start: event.target.value + ':00+03:00' }); }} /></label>
        <label className="block text-sm">Начало почты<input type="datetime-local" className="mt-1 min-h-11 w-full rounded-md border border-border bg-background p-2" value={inputValue(schedule.email_start)} onChange={event => { if (event.target.value) change({ ...schedule, email_start: event.target.value + ':00+03:00' }); }} /></label>
        <label className="block text-sm">Интервал между компаниями<select className="mt-1 min-h-11 w-full rounded-md border border-border bg-background p-2" value={schedule.interval_minutes} onChange={event => { const interval = [3,5,10,15,30,60].find(value => String(value) === event.target.value); if (interval) change({ ...schedule, interval_minutes: interval }); }}><option value="3">3 минуты</option><option value="5">5 минут</option><option value="10">10 минут</option><option value="15">15 минут</option><option value="30">30 минут</option><option value="60">60 минут</option></select></label>
        <p className="text-xs text-muted-foreground">Рабочие дни, с 10:00 до 18:00 по Москве. Выходные и позднее время переносятся на ближайшее рабочее окно. Почта начинается после первых Telegram-обращений. Интервалы повторных касаний сохранены; любой ответ остановит дальнейшие сообщения. Лимит отправителя может перенести фактическую отправку.</p>
      </fieldset>}
      {!busy && <Button variant="outline" onClick={() => void check()}>{schedule ? 'Обновить проверку' : 'Повторить проверку'}</Button>}
      {preview && <>
        <p className="font-semibold">1. Telegram — {preview.counts.telegram} · 2. Почта — {preview.counts.email}</p>
        <p className="text-sm">Telegram: {senderLabels('telegram')} · {firstRange('telegram')}</p><p className="text-sm">Почта: {senderLabels('email')} · {firstRange('email')}</p>
        <p className="text-sm">Всего {preview.touch_count} касаний для {preview.company_count} компаний. Сейчас это только проверка, очередь не создана.</p>
        {preview.valid_until && <p className="text-xs text-muted-foreground">Проверка расписания действительна до {moment(preview.valid_until)} МСК. После этого обновите проверку.</p>}
        {preview.warning && <p role="alert">{preview.warning}</p>}
        <div className="space-y-2">{preview.items.map(item => <details key={item.campaign_id} className="rounded-lg border border-border p-3"><summary className="min-h-11 cursor-pointer text-sm font-medium">{item.name} · {item.touches[0].channel === 'telegram' ? 'Telegram' : 'Почта'} · {moment(item.touches[0].scheduled_at)}</summary><p className="text-sm text-muted-foreground">{item.address}</p><p className="mt-2 break-words text-sm">Кому: {item.touches[0].recipient}</p><p className="text-sm">Отправитель: {item.touches[0].sender_label}</p>{item.touches[0].contact_source && <a className="text-sm underline" href={item.touches[0].contact_source} target="_blank" rel="noopener noreferrer">Источник контакта</a>}{item.touches.map((touch,index) => <div key={touch.id} className="mt-3 space-y-2 border-t border-border pt-3"><h3 className="font-semibold">{index === 0 ? 'Первое обращение' : `Повторное касание ${index}`}</h3><p className="text-sm">{moment(touch.scheduled_at)} МСК</p>{touch.subject && <p className="text-sm">Тема: {touch.subject}</p>}<p className="whitespace-pre-wrap break-words text-sm">{touch.generated_text}</p></div>)}</details>)}</div>
        <Button disabled={!preview.runtime_ready || busy} onClick={() => { setReviewed(false); setConfirmed(false); setConfirmation(true); }}>Перейти к итоговой проверке</Button>
      </>}
    </>}
    <Dialog open={confirmation} onOpenChange={open => { if (!busy) setConfirmation(open); }}><DialogContent className="max-h-[85dvh] overflow-y-auto"><DialogHeader><DialogTitle>Проверьте запуск подборки</DialogTitle><DialogDescription>Это подтверждение поставит сохранённые сообщения в штатную очередь LocalOS. Ничего не отправится до выбранного времени.</DialogDescription></DialogHeader>{preview && <div className="space-y-3"><div className="space-y-1 rounded-md border border-border p-3"><h3 className="font-semibold">1. Telegram · получателей: {preview.counts.telegram}</h3><p className="text-sm">{senderLabels('telegram')}</p><p className="text-sm">{firstRange('telegram')}</p></div><div className="space-y-1 rounded-md border border-border p-3"><h3 className="font-semibold">2. Почта · получателей: {preview.counts.email}</h3><p className="text-sm">{senderLabels('email')}</p><p className="text-sm">{firstRange('email')}</p></div><p>Всего {preview.company_count} получателей и {preview.touch_count} касаний. {firstOnly ? 'Повторные касания не запускаются.' : 'Повторные касания прекратятся при ответе.'} Отправители указаны у каждой компании.</p><label className="flex min-h-11 gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} disabled={busy} />Я проверил все тексты, получателей и отправителей этой подборки.</label><label className="flex min-h-11 gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={busy} />Разрешаю поставить эти {preview.touch_count} касаний в очередь на показанные даты.</label><Button disabled={!reviewed || !confirmed || busy} onClick={() => void approve()}>Подтвердить и поставить в очередь</Button><Button variant="outline" disabled={busy} onClick={() => setConfirmation(false)}>Вернуться без подтверждения</Button></div>}</DialogContent></Dialog>
  </section>;
}
