import { useLatestCallback } from '@/hooks/useLatestCallback';
import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/services/api';
import { mapDate, mapPublicLink, mapRows, mapValue } from './map-card-report.logic';
import { recordValue } from './normalization';

const labels: Record<string, string> = { google: 'Google', yandex: 'Яндекс', '2gis': '2ГИС' };
const methods: Record<string, string> = { google_api: 'Google API', native: 'Встроенный парсер', apify: 'Apify — платное чтение', owner_confirmation: 'Подтверждение владельца' };
const days: Record<string, string> = { MONDAY: 'Пн', TUESDAY: 'Вт', WEDNESDAY: 'Ср', THURSDAY: 'Чт', FRIDAY: 'Пт', SATURDAY: 'Сб', SUNDAY: 'Вс' };
const clock = (value: unknown) => {
  const time = recordValue(value);
  return time ? `${String(time.hours || 0).padStart(2, '0')}:${String(time.minutes || 0).padStart(2, '0')}` : '';
};
const calendarDate = (value: unknown) => {
  const date = recordValue(value);
  return date ? `${String(date.day || '').padStart(2, '0')}.${String(date.month || '').padStart(2, '0')}.${date.year || ''}` : 'Дата не указана';
};
const auditValue = (value: unknown): string => {
  const row = recordValue(value);
  if (Array.isArray(row?.periods)) return mapRows(row.periods).map((p) => `${days[String(p.openDay)] || p.openDay}: ${clock(p.openTime)} — ${days[String(p.closeDay)] || p.closeDay} ${clock(p.closeTime)}`).join('\n');
  if (Array.isArray(row?.specialHourPeriods)) return mapRows(row.specialHourPeriods).map((p) => `${calendarDate(p.startDate)}: ${p.closed ? 'Закрыто' : `${clock(p.openTime)} — ${clock(p.closeTime)}`}`).join('\n');
  if (Array.isArray(value)) return value.map((v) => { const item = recordValue(v); return item && typeof item.day === 'string' && typeof item.hours === 'string' ? `${item.day}: ${item.hours}` : typeof v === 'string' ? v : mapValue(v); }).join('\n');
  return mapValue(value);
};

export function MapCardInitialAudit({ runId }: { runId: string }) {
  const [cards, setCards] = useState<Record<string, unknown>[]>([]);
  const [provider, setProvider] = useState('google');
  const [method, setMethod] = useState('google_api');
  const [url, setUrl] = useState('');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const alive = useRef(true);
  const serial = useRef(0);
  const endpoint = `/agent-runs/${runId}/map-initial-audit`;
  const load = useLatestCallback(async () => {
    const request = ++serial.current;
    setBusy(true); setError('');
    try {
      const response = await api.get(endpoint);
      if (alive.current && request === serial.current) setCards(mapRows(response.data.workspace?.cards));
    } catch { if (alive.current && request === serial.current) setError('Не удалось загрузить проверку. Сохранённые данные остались на экране.'); }
    finally { if (alive.current && request === serial.current) setBusy(false); }
  });
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false; serial.current += 1; }; }, [runId, load]);
  const card = cards.find((item) => item.provider === provider);
  const audit = mapRows(card?.attempts).find((item) => item.method === method) || recordValue(card?.audit);
  const combined = mapRows(card?.combined_checks);
  const checks = combined.length ? combined : mapRows(audit?.checks);
  const start = async (action = 'parse') => {
    const request = ++serial.current;
    setBusy(true); setError('');
    try {
      const response = await api.post(endpoint, { action, previous_attempt_id: action === 'retry_failed_once' ? audit?.id : undefined, provider, method, url: url || card?.url || '', paid_consent: method === 'apify' && consent });
      if (alive.current && request === serial.current) { setCards(mapRows(response.data.workspace?.cards)); setConsent(false); }
    } catch (reason) { if (alive.current && request === serial.current) setError(reason instanceof Error ? reason.message : 'Проверка не запущена.'); }
    finally { if (alive.current && request === serial.current) setBusy(false); }
  };
  const attempted = audit?.method === method && (method === 'google_api' || audit?.url === (url || card?.url));
  const canRetry = attempted && audit?.status === 'blocked' && method === 'apify' && consent;
  return <section aria-label="Начальная проверка заполненности" className="space-y-4 rounded-xl border border-border p-4">
    <div className="space-y-1"><h3 className="font-semibold">Проверка заполненности карточек</h3><p className="text-sm text-muted-foreground">Входит в первый запуск первичного оформления: часы, контакты, фото, услуги и остальные пункты. Ниже — черновики правок на проверку. Сохранённые попытки используются повторно; платное чтение — только после отдельного согласования. Изменения не публикуются.</p></div>
    <div role="group" aria-label="Площадка начальной проверки" className="flex flex-wrap gap-2">{Object.entries(labels).map(([id, label]) => <Button key={id} size="sm" variant={provider === id ? 'default' : 'outline'} disabled={busy} aria-pressed={provider === id} onClick={() => { setProvider(id); setMethod(String(cards.find((item) => item.provider === id)?.default_method || (id === 'google' ? 'google_api' : 'native'))); setUrl(''); setConsent(false); setError(''); }}>{label}</Button>)}</div>
    <label className="block space-y-1 text-sm"><span>Способ чтения</span><select aria-label="Способ чтения" className="h-10 w-full rounded-md border border-input bg-background px-3" value={method} disabled={busy} onChange={(event) => { setMethod(event.target.value); setConsent(false); }}>
      <option value={provider === 'google' ? 'google_api' : 'native'}>{provider === 'google' ? 'Google API — без AI' : 'Встроенный парсер — без Apify и AI'}</option><option value="apify">Apify — только после согласования расходов</option>
    </select></label>
    {method !== 'google_api' ? <label className="block space-y-1 text-sm"><span>Публичная ссылка на карточку {labels[provider]}</span><Input value={url || String(card?.url || '')} disabled={busy} onChange={(event) => { setUrl(event.target.value); setConsent(false); }} placeholder="https://…" /></label> : <p className="text-sm text-muted-foreground">Читает подключённую карточку Google. Фото и публичный внешний вид требуют отдельного чтения страницы через Apify.</p>}
    {method !== 'google_api' && !(url || card?.url) ? <p role="status" className="text-sm text-muted-foreground">Не удалось проверить: публичная ссылка на карточку {labels[provider]} не добавлена. Вставьте ссылку выше, чтобы начать чтение.</p> : null}
    {method === 'apify' ? <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={consent} disabled={busy} onChange={(event) => setConsent(event.target.checked)} /><span>Разрешаю один запуск Apify для этой карточки: одна компания, до 180 секунд, лимит оплаты за события $0.50. Без повторов и переключения на другой парсер. Если тариф не поддерживает лимит, запуск будет остановлен.</span></label> : null}
    <div className="flex flex-wrap gap-2"><Button disabled={busy || (Boolean(attempted) && !canRetry) || (method === 'apify' && !consent) || (method !== 'google_api' && !(url || card?.url))} onClick={() => void start(canRetry ? 'retry_failed_once' : 'parse')}>{busy ? 'Загрузка…' : canRetry ? 'Новая согласованная попытка Apify' : attempted ? 'Попытка уже сохранена' : method === 'apify' ? 'Запустить согласованное чтение Apify' : 'Проверить заполненность'}</Button><Button variant="outline" disabled={busy} onClick={() => void load()}>Обновить результат</Button>{provider !== 'google' && !(url || card?.url) ? <Button variant="outline" disabled={busy || audit?.status === 'not_created'} onClick={() => void start('confirm_not_created')}>Карточки пока нет</Button> : null}</div>
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {audit ? <div className="space-y-3">
      <p role="status" className="text-sm">{methods[String(audit.method)]}: {audit.status === 'completed' ? 'чтение завершено' : audit.status === 'queued' ? 'в очереди' : audit.status === 'reading' ? 'читаем карточку' : audit.status === 'not_created' ? 'карточка пока не создана' : 'не удалось проверить'}. Дата: {mapDate(audit.observed_at || audit.requested_at)}.</p>
      {typeof audit.reason === 'string' ? <p className="text-sm text-muted-foreground">{audit.reason}</p> : null}
      {mapPublicLink(audit.url) ? <a className="text-sm underline" href={mapPublicLink(audit.url)} target="_blank" rel="noopener noreferrer">Открыть проверенную карточку</a> : null}
      {checks.length ? <div className="space-y-4"><p className="text-sm font-medium">Сводка по прочитанным источникам</p>{[
        { title: 'Заполнено', states: ['observed'] }, { title: 'Чего не хватает', states: ['missing'] }, { title: 'Не удалось проверить', states: ['unknown', 'blocked'] },
      ].map((group) => { const rows = checks.filter((check) => group.states.includes(String(check.state))); return <details key={group.title} open={group.title === 'Чего не хватает'} className="border-t border-border pt-3"><summary className="cursor-pointer text-sm font-semibold">{group.title} · {rows.length}</summary>{rows.length ? <ul className="mt-2 divide-y divide-border">{rows.map((check) => <li key={String(check.field)} className="py-2 text-sm"><p className="font-medium">{String(check.title)}</p>{check.source ? <p className="text-xs text-muted-foreground">{methods[String(check.source)] || 'Источник проверки'} · {mapDate(check.observed_at)}</p> : null}{check.state === 'observed' ? <p className="whitespace-pre-wrap break-words">{auditValue(check.value)}</p> : null}{typeof check.evidence === 'string' && check.evidence ? <p className="text-muted-foreground">{check.evidence}</p> : null}</li>)}</ul> : <p className="text-sm text-muted-foreground">{group.title === 'Чего не хватает' ? 'Подтверждённых пробелов не обнаружено. Это не означает, что все поля проверены.' : 'Нет пунктов.'}</p>}</details>; })}</div> : null}
      <p className="text-xs text-muted-foreground">Наличие фото и качество оформления — разные проверки. Пустое поле в ответе парсера не доказывает, что его нет на площадке. Внешний вид, качество фото и отсутствие дублей этим отчётом не подтверждаются.</p>
    </div> : <p className="text-sm text-muted-foreground">Начальное чтение этой площадки ещё не выполнено.</p>}
  </section>;
}
