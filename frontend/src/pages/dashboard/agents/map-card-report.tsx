import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { recordValue } from './normalization';
import { mapDate, mapFieldLabels, mapPublicLink, mapRows, mapValue } from './map-card-report.logic';

const labels: Record<string, string> = { google: 'Google', yandex: 'Яндекс', '2gis': '2ГИС' };
const states: Record<string, string> = { observed: 'Есть данные снимка', missing: 'Не найдено в снимке', unknown: 'Нет подтверждения', blocked: 'Недоступно', not_applicable: 'Неприменимо' };
const sourceLabel = (value: unknown, platform: string) => {
  const source = typeof value === 'string' ? value.toLowerCase() : '';
  if (source.includes('business_profile') || source === 'profile') return 'Профиль компании в LocalOS';
  if (source.includes('snapshot') || source.startsWith('mapparse') || source.startsWith('cards')) return `Сохранённый снимок ${platform}`;
  if (source.includes('link')) return 'Подключённая ссылка карточки';
  return 'Сохранённые данные LocalOS';
};
const title = (row: Record<string, unknown>) => typeof row.title === 'string' ? row.title : mapFieldLabels[String(row.field)] || 'Пункт проверки';

export const MapCardReport = ({ result }: { result: Record<string, unknown> }) => {
  const cards = mapRows(result.cards);
  const [selected, setSelected] = useState(String(cards[0]?.provider || 'google'));
  const card = cards.find((item) => item.provider === selected) || cards[0];
  const provider = String(card?.provider || '');
  const name = labels[provider] || 'Карточка компании';
  const checks = mapRows(card?.checks);
  const unknowns = checks.filter((item) => !['observed', 'not_applicable'].includes(String(item.state)));
  const fields = mapRows(card?.fields);
  const editorial = recordValue(result.editorial);
  const aliases: Record<string, string> = { google: 'google', yandex: 'yandex', 'яндекс': 'yandex', '2gis': '2gis', '2гис': '2gis' };
  const suggestions = [...mapRows(editorial?.items), ...mapRows(editorial?.drafts)].filter((item) => aliases[String(item.platform || item.provider || '').toLowerCase()] === provider);
  const questions = Array.isArray(editorial?.exceptions) ? editorial.exceptions.filter((item) => typeof item === 'string').slice(0, 8) : [];
  return <section className="space-y-4" aria-label="Результат работы с карточками">
    <div className="space-y-1"><p className="text-sm font-medium">{typeof result.summary === 'string' ? result.summary : 'Сохранённые данные карточек'}</p><p className="text-xs text-muted-foreground">Данные собраны: {mapDate(result.observed_at)}. Это сохранённые сведения. Текущее состояние карточки требует проверки.</p></div>
    {result.preview === true ? <p role="status" className="rounded-xl bg-muted p-3 text-sm">Это пример проверки. Внешние страницы и AI-провайдер не вызывались.</p> : null}
    {cards.length ? <div className="flex flex-wrap gap-2" role="group" aria-label="Площадка отчёта">{cards.map((item) => <Button key={String(item.provider)} variant={item.provider === provider ? 'default' : 'outline'} size="sm" aria-pressed={item.provider === provider} onClick={() => setSelected(String(item.provider))}>{labels[String(item.provider)] || 'Карточка'}</Button>)}</div> : <p className="text-sm text-muted-foreground">Данных карточек в этом результате нет.</p>}
    {card ? <article className="space-y-4 rounded-xl border border-border bg-background p-4">
      <div><h3 className="text-lg font-semibold">{name}</h3><p role="status" className="mt-1 text-sm font-medium">Недостаточно данных для полной проверки</p></div>
      <div className="rounded-lg bg-muted p-3 text-sm leading-6">
        <p>Внешний вид не проверен</p><p>Для полной проверки нужны актуальные скриншоты публичной карточки.</p>
        {mapPublicLink(card.url) ? <a className="underline underline-offset-2" href={mapPublicLink(card.url)} target="_blank" rel="noopener noreferrer">Открыть карточку</a> : <p className="mt-1">Подтвердите ссылку карточки в разделе «Карты и отзывы».</p>}
      </div>
      <div className="text-sm"><p>Известно по сохранённым данным: {checks.filter((item) => item.state === 'observed').length} пунктов. Нужно уточнить: {unknowns.length}.</p>{unknowns.length ? <ul className="mt-2 list-inside list-disc text-muted-foreground">{unknowns.slice(0, 3).map((item, index) => <li key={index}>{title(item)}</li>)}</ul> : null}</div>
      {fields.length ? <div className="space-y-3"><h4 className="text-sm font-semibold">Что предлагается перенести</h4>{fields.map((field) => <div key={String(field.field)} className="rounded-lg border border-border p-3"><h5 className="text-sm font-semibold">{title(field)}</h5><dl className="mt-2 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-xs text-muted-foreground">Сейчас в сохранённых данных</dt><dd className="mt-1 whitespace-pre-wrap break-words">{mapValue(field.before)}</dd></div><div><dt className="text-xs text-muted-foreground">Предлагается — сверить с владельцем</dt><dd className="mt-1 whitespace-pre-wrap break-words">{mapValue(field.proposed)}</dd></div></dl></div>)}</div> : null}
      {mapRows(card.changes).length ? <div><h4 className="text-sm font-semibold">Изменения с прошлого отчёта</h4><ul className="mt-2 space-y-2 text-sm">{mapRows(card.changes).map((change, index) => <li key={index}>{title(change)}: {mapValue(change.before)} → {mapValue(change.after)}</li>)}</ul></div> : null}
      <details className="rounded-lg border border-border p-3"><summary className="cursor-pointer text-sm font-medium">Все пункты проверки и источники · {checks.length}</summary><ul className="mt-3 divide-y divide-border">{checks.map((check, index) => <li key={index} className="space-y-1 py-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{title(check)}</span><span className="text-muted-foreground">{states[String(check.state)] || 'Нет подтверждения'}</span></div><p className="whitespace-pre-wrap break-words">{mapValue(check.value)}</p><p className="text-xs text-muted-foreground">Источник: {sourceLabel(check.source, name)} · {mapDate(check.observed_at)}</p>{mapPublicLink(check.official_url) ? <a className="inline-block text-xs underline" href={mapPublicLink(check.official_url)} target="_blank" rel="noopener noreferrer">Справка площадки</a> : null}</li>)}</ul></details>
      {suggestions.length ? <details className="rounded-lg border border-border p-3"><summary className="cursor-pointer text-sm font-medium">Предложения AI для {name} — требуют сверки</summary><div className="mt-3 space-y-3">{suggestions.map((suggestion, index) => <dl key={index} className="space-y-3">{Object.entries(recordValue(suggestion.fields) || {}).filter(([key, value]) => ['name', 'title', 'description', 'address', 'website', 'schedule'].includes(key) && typeof value === 'string').map(([key, value]) => <div key={key}><dt className="text-xs font-medium text-muted-foreground">{mapFieldLabels[key]}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm">{mapValue(value)}</dd></div>)}</dl>)}</div></details> : null}
    </article> : null}
    {questions.length ? <details className="rounded-xl border border-border p-3"><summary className="cursor-pointer text-sm font-medium">Что уточнить у владельца · {questions.length}</summary><ul className="mt-3 list-inside list-disc space-y-2 text-sm">{questions.map((item, index) => <li key={index}>{String(item)}</li>)}</ul></details> : null}
    {result.kind === 'preparation' ? <p className="text-sm text-muted-foreground">Предложения требуют проверки владельцем и ручного размещения. Отчёт не подтверждает публикацию изменений.</p> : null}
  </section>;
};
