import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { newAuth } from '@/lib/auth_new';

type Values = Record<string, number | null>;
type Daily = { date: string; currency: string; values: Values; summary_id?: string; version?: number; notes?: string;
  sources: Record<string, string>; reconciliation_status: string; discrepancies: Record<string, { reported: string; detail: string }>;
  operations: { id: string; amount: string; description?: string; transaction_type?: string }[] };
type Report = { enabled: boolean; settings?: { currency?: string; timezone?: string; today?: string }; days: Daily[];
  voided_summaries?: { id: string; date: string; currency: string }[]; currencies: Record<string, Values>; period_aggregates?: unknown[]; coverage?: { observed_days: number; requested_days: number } };
type Event = { kind: string; created_at: string; channel: string; after_json: { values_json?: Record<string, string>; amount?: string; currency?: string; is_voided?: boolean } };
const labels: Record<string, string> = { revenue: 'Выручка до возвратов', refunds: 'Возвраты', net_revenue: 'После возвратов',
  checks: 'Всего чеков', upsell_checks: 'Чеки с допродажей', average_check: 'Средний чек', upsell_share: 'Доля чеков с допом, %', expenses: 'Расходы' };
const valueText = (value: number | null | undefined) => value === null || value === undefined ? 'Не указано' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(value);

export function FinanceDailyPanel({ businessId, onActive, requestHeaders, openOperator }: { businessId?: string | null; onActive: (active: boolean) => void; requestHeaders?: () => Record<string,string>; openOperator?: () => void }) {
  const [report, setReport] = useState<Report | null>(null);
  const [start, setStart] = useState(''); const [end, setEnd] = useState('');
  const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0); const [history, setHistory] = useState<Record<string, Event[]>>({});
  const scope = useRef(businessId); scope.current = businessId;
  useEffect(() => { setReport(null); setStart(''); setEnd(''); setHistory({}); setError(''); onActive(false); }, [businessId, onActive]);
  useEffect(() => {
    if (!businessId) return;
    const controller = new AbortController(); const business = businessId;
    setLoading(true); setError('');
    const params = new URLSearchParams({ business_id: business });
    if (start) params.set('start', start); if (end) params.set('end', end);
    void (requestHeaders ? fetch(`/api/finance/daily?${params}`, { headers: requestHeaders(), signal: controller.signal }).then((response) => { if (!response.ok) throw new Error('load'); return response.json(); }) : newAuth.makeRequest(`/finance/daily?${params}`, { method: 'GET', signal: controller.signal }))
      .then((data: Report) => { if (!controller.signal.aborted) { setReport(data); onActive(data.enabled || data.days.length > 0 || !!data.voided_summaries?.length); } })
      .catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить итоги. Повторите запрос.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [businessId, start, end, refresh, onActive, requestHeaders]);
  const loadHistory = async (id: string) => {
    const business = businessId;
    try {
      const result: { items: Event[] } = await (requestHeaders ? fetch(`/api/finance/daily/${encodeURIComponent(id)}/history?business_id=${encodeURIComponent(business || '')}`, { headers: requestHeaders() }).then((response) => { if (!response.ok) throw new Error('history'); return response.json(); }) : newAuth.makeRequest(`/finance/daily/${encodeURIComponent(id)}/history?business_id=${encodeURIComponent(business || '')}`, { method: 'GET' }));
      if (scope.current === business) setHistory((previous) => ({ ...previous, [id]: result.items }));
    } catch { if (scope.current === business) setError('Не удалось загрузить историю изменений.'); }
  };
  if (!businessId || (!report?.enabled && !report?.days.length && !report?.voided_summaries?.length && !error)) return null;
  return <section className="space-y-4 rounded-xl border bg-card p-4 text-card-foreground" aria-label="Дневные финансовые итоги">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Итоги дня и сверка</h2>
      <p className="text-sm text-muted-foreground">Продиктуйте итог Оператору, проверьте карточку и подтвердите сохранение.</p></div>
      <Button type="button" variant="outline" onClick={() => setRefresh((value) => value + 1)} disabled={loading}>Обновить</Button></div>
    <p className="text-sm">Валюта: {report?.settings?.currency || 'не задана'} · Часовой пояс: {report?.settings?.timezone || 'не задан'}.</p>
    {!report?.settings?.timezone && <p className="text-sm">Сообщите Оператору часовой пояс и валюту бизнеса, например: «Сохрани настройки финансов: EUR, Europe/Tallinn». Настройка сохранится после подтверждения.</p>}
    {openOperator ? <Button variant="outline" onClick={openOperator}>Внести данные через Оператора</Button> : <Button variant="outline" asChild><Link to="/dashboard/operator">Внести данные через Оператора</Link></Button>}
    <div className="flex flex-wrap gap-3"><label className="text-sm">С даты<Input type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label>
      <label className="text-sm">По дату<Input type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label></div>
    {loading && <p role="status">Загружаю итоги…</p>}{error && <p role="alert">{error}</p>}
    {report?.coverage && <p className="text-sm text-muted-foreground">Данные есть за {report.coverage.observed_days} из {report.coverage.requested_days} дней. Отсутствующие дни не считаются нулевыми.</p>}
    {Object.entries(report?.currencies || {}).map(([currency, values]) => <div key={currency} className="space-y-2"><h3 className="font-medium">Итог периода · {currency === 'UNKNOWN' ? 'валюта записей не указана' : currency}</h3>
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">{Object.entries(labels).map(([key, label]) => <div key={key}><dt className="text-sm text-muted-foreground">{label}</dt><dd className="font-medium">{valueText(values[key])}</dd></div>)}</dl></div>)}
    {!report?.days.length && <p>Дневных данных пока нет. Например: «Сегодня 10 продаж, 2 допа, выручка 350 евро, возвраты 20 евро».</p>}
    {!!report?.period_aggregates?.length && <p role="status">Есть импортированные итоги за несколько дней. Они не распределены по дням и требуют сверки.</p>}
    {report?.days.map((day) => <details key={`${day.date}:${day.currency}`} className="rounded-lg border p-3"><summary className="cursor-pointer font-medium">{day.date} · {day.currency} · {day.summary_id ? 'Подтверждённый итог' : 'По операциям'}{day.reconciliation_status === 'needs_review' ? ' · Требуется сверка' : ''}</summary>
      <div className="mt-3 space-y-3"><dl className="grid grid-cols-2 gap-3">{Object.entries(labels).map(([key, label]) => <div key={key}><dt className="text-sm text-muted-foreground">{label}</dt><dd>{valueText(day.values[key])}{day.sources[key] === 'daily_summary' ? ' · со слов пользователя' : day.sources[key] === 'operations' ? ' · операции' : ''}</dd></div>)}</dl>
        {day.notes && <p>{day.notes}</p>}
        {Object.entries(day.discrepancies).map(([key, value]) => <p key={key}>{labels[key]}: подтверждено {value.reported}, по операциям {value.detail}. Значения не сложены.</p>)}
        {day.reconciliation_status === 'needs_review' && <p>Для изменения сообщите Оператору новый итог за эту дату. До подтверждения текущий итог сохраняется.</p>}
        {!!day.operations.length && <ul className="space-y-1 text-sm">{day.operations.map((operation) => <li key={operation.id}>{operation.description || operation.transaction_type || 'Операция'} · {operation.amount}<Button type="button" variant="ghost" onClick={() => void loadHistory(operation.id)}>История операции</Button>{history[operation.id]?.map((event, index) => <p key={index}>{event.created_at} · {event.channel} · {event.after_json.is_voided ? 'Отменено' : `${event.after_json.amount || ''} ${event.after_json.currency || ''}`}</p>)}{history[operation.id]?.length === 0 && <p>Изменений через Оператора нет.</p>}</li>)}</ul>}
        {day.summary_id && <Button type="button" variant="outline" onClick={() => void loadHistory(day.summary_id || '')}>История изменений</Button>}
        {day.summary_id && history[day.summary_id]?.map((event, index) => <p className="text-sm" key={`${event.created_at}:${index}`}>{event.created_at} · {event.channel} · {event.after_json.is_voided ? 'Отменено' : Object.entries(event.after_json.values_json || {}).map(([key, value]) => `${labels[key] || key}: ${value}`).join('; ')}</p>)}
      </div></details>)}
    {report?.voided_summaries?.map((day) => <details key={day.id} className="rounded-lg border p-3"><summary>{day.date} · {day.currency} · Сводка отменена</summary><Button variant="outline" onClick={() => void loadHistory(day.id)}>История изменений</Button>{history[day.id]?.map((event, index) => <p key={index}>{event.created_at} · {event.after_json.is_voided ? 'Отменено' : Object.entries(event.after_json.values_json || {}).map(([key,value]) => `${labels[key] || key}: ${value}`).join('; ')}</p>)}</details>)}
  </section>;
}
