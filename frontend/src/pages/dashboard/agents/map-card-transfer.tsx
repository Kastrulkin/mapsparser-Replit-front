import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import { recordValue } from './normalization';

type Service = { name: string; price: string; description: string };
type PlatformState = { fields: Record<string, string>; services: Service[]; steps: Record<string, boolean> };
type Progress = { revision: number; platforms: Record<string, PlatformState> };
const platforms = [
  { id: 'google', name: 'Google', url: 'https://business.google.com/', data: 'В профиле компании откройте «Изменить профиль». Перенесите подтверждённые данные и часы работы.', services: 'Откройте раздел услуг в профиле компании. Добавляйте позиции вручную: универсальный импорт этого файла в Google не подключён.', photos: 'Откройте фотографии профиля компании. Добавьте реальные фотографии и выберите логотип и обложку.' },
  { id: 'yandex', name: 'Яндекс', url: 'https://yandex.ru/sprav/', data: 'Откройте компанию в Яндекс Бизнесе → О компании → Данные. Перенесите контакты, адрес, часы работы и доступные для вашей рубрики сведения.', services: 'О компании → Товары и услуги → Загрузить XLS/YML → XLS. Загрузите заполненный XLSX и проверьте предпросмотр. Новый прайс-лист может заменить старый: сначала сохраните его копию.', photos: 'О компании → Фото и видео. Загрузите фотографии в подходящие категории, выберите логотип и главное фото.' },
  { id: '2gis', name: '2ГИС', url: 'https://account.2gis.com/', data: 'Откройте свою компанию в личном кабинете 2ГИС. Проверьте основные сведения, рубрики, контакты, часы работы, вход и этаж. Если доступа нет, выберите «Получить доступ».', services: 'Товары и услуги → Добавить → Из файла. Загрузите CSV, проверьте сопоставление столбцов и предпросмотр. При необходимости используйте шаблон из кабинета.', photos: 'В личном кабинете компании откройте фотографии. Загрузите выбранные изображения и проверьте обложку карточки.' },
];
const stages = [
  { id: 'data', title: 'Данные', confirmation: 'Данные сверены, недостающие сведения отмечены' },
  { id: 'services', title: 'Услуги', confirmation: 'Услуги и цены проверены либо этот раздел не требуется' },
  { id: 'photos', title: 'Фотографии', confirmation: 'Фотографии отобраны и подготовлены' },
  { id: 'submission', title: 'Перенос', confirmation: 'Я перенёс данные в кабинет площадки и отправил изменения на проверку' },
  { id: 'verification', title: 'Проверка', confirmation: 'Я открыл публичную карточку и вручную проверил опубликованные изменения' },
];
const photoLabels: Record<string, string> = { product: 'Продукция', team: 'Команда', interior: 'Интерьер', exterior: 'Вход и фасад', logo: 'Логотип' };
const fieldLabels: Record<string, string> = { name: 'Название', address: 'Адрес', phone: 'Телефон', website: 'Сайт', schedule: 'Часы работы', description: 'Описание компании' };
const objects = (value: unknown) => Array.isArray(value) ? value.map(recordValue).filter((item) => item !== null) : [];
const stringValue = (value: unknown) => value === undefined || value === null ? '' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
const safeLink = (value: unknown) => {
  if (typeof value !== 'string') return '';
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : ''; } catch { return ''; }
};
const descriptionDraft = (result: Record<string, unknown>, provider: string) => {
  const editorial = recordValue(result.editorial);
  const aliases: Record<string, string> = { google: 'google', yandex: 'yandex', 'яндекс': 'yandex', '2gis': '2gis', '2гис': '2gis' };
  const candidate = [...objects(editorial?.items), ...objects(editorial?.drafts)].find((item) => aliases[String(item.platform || item.provider || '').toLowerCase()] === provider);
  const fields = recordValue(candidate?.fields);
  return typeof fields?.description === 'string' ? fields.description : '';
};
const defaults = (result: Record<string, unknown>, provider: string): PlatformState => {
  const card = objects(result.cards).find((item) => item.provider === provider);
  const fields: Record<string, string> = {};
  objects(card?.fields).forEach((field) => { fields[String(field.field)] = stringValue(field.proposed); });
  return { fields, steps: {}, services: objects(result.services).map((service) => ({ name: stringValue(service.name), price: stringValue(service.price), description: stringValue(service.description) })) };
};

export const MapCardTransfer = ({ result, runId }: { result: Record<string, unknown>; runId: string }) => {
  const available = platforms.filter((platform) => objects(result.cards).some((card) => card.provider === platform.id));
  const [provider, setProvider] = useState(available[0]?.id || 'google');
  const [stage, setStage] = useState(0);
  const [progress, setProgress] = useState<Progress>({ revision: 0, platforms: {} });
  const [state, setState] = useState<PlatformState>(() => defaults(result, provider));
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const alive = useRef(true);
  const endpoint = `/agent-runs/${runId}/map-transfer`;
  const platform = platforms.find((item) => item.id === provider) || platforms[0];
  const currentStage = stages[stage];
  const card = objects(result.cards).find((item) => item.provider === provider);
  const load = async () => {
    setLoading(true); setError('');
    try {
      const response = await api.get(endpoint);
      if (!alive.current) return;
      const saved: Progress = response.data.progress;
      setProgress(saved); setState(saved.platforms[provider] || defaults(result, provider)); setDirty(false);
    } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить прогресс.'); }
    finally { if (alive.current) setLoading(false); }
  };
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false; }; }, [runId]); // Mounted with a run-specific key.
  const update = (next: PlatformState) => { setState(next); setDirty(true); setMessage(''); setError(''); };
  const save = async (): Promise<boolean> => {
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await api.patch(endpoint, { platform: provider, revision: progress.revision, state });
      if (!alive.current) return false;
      setProgress(response.data.progress); setDirty(false); setMessage('Прогресс сохранён в LocalOS.'); return true;
    } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : 'Не удалось сохранить. Изменения остались на экране.'); return false; }
    finally { if (alive.current) setBusy(false); }
  };
  const navigate = async (nextProvider: string, nextStage: number) => {
    if (dirty && !await save()) return;
    if (!alive.current) return;
    if (nextProvider !== provider) { setState(progress.platforms[nextProvider] || defaults(result, nextProvider)); setProvider(nextProvider); }
    setStage(nextStage); setMessage('');
  };
  const copy = async (value: string) => {
    try { await navigator.clipboard.writeText(value); if (alive.current) setMessage('Скопировано.'); }
    catch { if (alive.current) setError('Не удалось скопировать. Выделите текст в поле и скопируйте вручную.'); }
  };
  const download = async (kind: string) => {
    if (dirty && !await save()) return;
    setBusy(true); setError('');
    try {
      const response = await api.get(endpoint, { params: { platform: provider, export: kind } });
      if (!alive.current) return;
      const file = response.data.file;
      const bytes = Uint8Array.from(atob(file.content_base64), (char) => char.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: file.mime }));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = file.filename; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage(`Файл «${file.filename}» подготовлен для скачивания.`);
    } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : 'Не удалось подготовить файл.'); }
    finally { if (alive.current) setBusy(false); }
  };
  const toggleStage = (checked: boolean) => {
    const steps = { ...state.steps, [currentStage.id]: checked };
    if (!checked) stages.slice(stage + 1).forEach((item) => { steps[item.id] = false; });
    update({ ...state, steps });
  };
  const setService = (index: number, key: keyof Service, value: string) => update({ ...state, services: state.services.map((item, position) => position === index ? { ...item, [key]: value } : item), steps: { ...state.steps, services: false, submission: false, verification: false } });
  const ready = stages.slice(0, 3).every((item) => state.steps[item.id]);
  const inputClass = 'mt-1 min-h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
  if (loading) return <section aria-label="Мастер оформления"><p role="status">Загружаем сохранённый прогресс…</p></section>;
  return <section aria-label="Мастер оформления" className="space-y-4 rounded-2xl border border-border bg-background p-4 sm:p-5">
    <div><h3 className="text-lg font-semibold">Оформить карточки по шагам</h3><p className="mt-1 text-sm text-muted-foreground">Проверьте пакет, перенесите его в кабинет площадки и отдельно проверьте публикацию. Отметки сохраняются для этого запуска. Внешних изменений LocalOS здесь не выполняет.</p></div>
    <div className="flex flex-wrap gap-2" role="group" aria-label="Площадка оформления">{available.map((item) => <Button key={item.id} variant={provider === item.id ? 'default' : 'outline'} disabled={busy} aria-pressed={provider === item.id} onClick={() => void navigate(item.id, 0)}>{item.name}</Button>)}</div>
    <p className="text-sm font-medium">{platform.name}: {state.steps.verification ? 'Публикация проверена вами вручную' : state.steps.submission ? 'Передано на проверку площадки' : ready ? 'Пакет готов к ручному переносу' : 'Подготовка пакета'} · {stages.filter((item) => state.steps[item.id]).length} из 5 шагов</p>
    <nav aria-label="Шаги оформления" className="flex flex-wrap gap-2">{stages.map((item, index) => <Button key={item.id} variant={stage === index ? 'secondary' : 'ghost'} size="sm" aria-current={stage === index ? 'step' : undefined} disabled={busy} onClick={() => void navigate(provider, index)}>{state.steps[item.id] ? '✓ ' : `${index + 1}. `}{item.title}</Button>)}</nav>
    {error ? <div role="alert" className="space-y-2 text-sm text-destructive"><p>{error}</p><Button variant="outline" size="sm" onClick={() => void load()} disabled={busy}>Загрузить сохранённое</Button><p className="text-muted-foreground">Повторная загрузка заменит несохранённые правки на экране.</p></div> : null}
    {message ? <p role="status" className="text-sm text-muted-foreground">{message}</p> : null}
    <div aria-busy={busy} className="space-y-4">
      <h4 className="font-semibold">Шаг {stage + 1}. {currentStage.title}</h4>
      {stage === 0 ? <>
        <p className="text-sm text-muted-foreground">{platform.data} Название должно соответствовать реальной вывеске. Пустые поля уточните у владельца. Правки здесь изменяют только пакет этого запуска.</p>
        {Object.entries(fieldLabels).map(([key, label]) => <div key={key} className="rounded-xl border border-border p-3">
          <label className="text-sm font-medium">{label}<textarea aria-label={label} disabled={busy} className={inputClass} rows={key === 'description' ? 4 : 2} maxLength={5000} placeholder="Уточнить у владельца" value={state.fields[key] || ''} onChange={(event) => update({ ...state, fields: { ...state.fields, [key]: event.target.value }, steps: {} })} /></label>
          <div className="mt-2 flex items-center justify-between gap-2"><span className="text-xs text-muted-foreground">Источник предложения: профиль бизнеса / ваша правка</span><Button variant="outline" size="sm" disabled={!state.fields[key] || busy} onClick={() => void copy(state.fields[key])}>Скопировать {label.toLowerCase()}</Button></div>
          {key === 'description' && descriptionDraft(result, provider) ? <div className="mt-3 space-y-2 border-t border-border pt-3"><p className="text-xs font-medium text-muted-foreground">AI-вариант — проверьте факты с владельцем перед переносом</p><p className="whitespace-pre-wrap break-words text-sm">{descriptionDraft(result, provider)}</p><Button variant="outline" size="sm" disabled={busy} onClick={() => update({ ...state, fields: { ...state.fields, description: descriptionDraft(result, provider).slice(0, 5000) }, steps: {} })}>Вставить AI-вариант для проверки</Button></div> : null}
        </div>)}
        <details><summary className="cursor-pointer text-sm font-medium">AI-рекомендации — сначала проверьте факты</summary><p className="mt-2 whitespace-pre-wrap break-words text-sm">{stringValue(recordValue(result.editorial)?.summary)}</p><p className="mt-2 text-sm text-muted-foreground">Предложения AI не подтверждают цены, услуги и преимущества компании.</p></details>
      </> : null}
      {stage === 1 ? <>
        <p className="text-sm text-muted-foreground">{platform.services}</p>
        {!state.services.length ? <p className="text-sm">Подтверждённых услуг нет. Скачайте пустой шаблон или добавьте данные владельца. Цены не подставляются автоматически.</p> : null}
        {state.services.map((service, index) => <fieldset key={index} className="space-y-2 rounded-xl border border-border p-3"><legend className="px-1 text-sm font-medium">Услуга {index + 1}</legend>{(['name', 'price', 'description']).map((key) => <label key={key} className="block text-sm">{key === 'name' ? 'Название услуги' : key === 'price' ? 'Точная цена, ₽' : 'Описание услуги'}<input className={inputClass} aria-label={`${key === 'name' ? 'Название услуги' : key === 'price' ? 'Цена услуги' : 'Описание услуги'} ${index + 1}`} disabled={busy} value={key === 'name' ? service.name : key === 'price' ? service.price : service.description} onChange={(event) => { if (key === 'name' || key === 'price' || key === 'description') setService(index, key, event.target.value); }} /></label>)}<div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => void copy(`${service.name}\n${service.price}\n${service.description}`)}>Скопировать услугу {index + 1}</Button><Button variant="ghost" size="sm" disabled={busy} onClick={() => update({ ...state, services: state.services.filter((_, position) => index !== position), steps: { ...state.steps, services: false, submission: false, verification: false } })}>Убрать строку {index + 1}</Button></div></fieldset>)}
        <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || state.services.length >= 100} onClick={() => update({ ...state, services: [...state.services, { name: '', price: '', description: '' }], steps: { ...state.steps, services: false, submission: false, verification: false } })}>Добавить услугу в пакет</Button>{provider !== 'google' ? <Button variant="outline" disabled={busy} onClick={() => void download('services')}>{state.services.length ? 'Скачать услуги' : 'Скачать пустой шаблон'} ({provider === 'yandex' ? 'XLSX' : 'CSV'})</Button> : null}</div>
      </> : null}
      {stage === 2 ? <>
        <p className="text-sm text-muted-foreground">{platform.photos} Проверьте права на изображения, качество, обрезку и соответствие реальному бизнесу.</p>
        <ul className="list-inside list-disc text-sm">{Array.isArray(result.photo_brief) ? result.photo_brief.map((item, index) => <li key={index}>{stringValue(item)}</li>) : null}</ul>
        {objects(result.photos).filter((photo) => safeLink(photo.original_url)).length ? <div className="grid gap-3 sm:grid-cols-2">{objects(result.photos).filter((photo) => safeLink(photo.original_url)).map((photo, index) => <a key={String(photo.id || index)} className="rounded-lg border border-border p-3 text-sm underline" href={safeLink(photo.original_url)} download target="_blank" rel="noopener noreferrer">Скачать / открыть фото {index + 1}{photo.category ? ` · ${(photoLabels[String(photo.category)] || 'Фотография')}` : ''}</a>)}</div> : <p className="text-sm">Доступных фотографий нет. Добавьте фотографии в медиатеку и подготовьте новый пакет.</p>}
      </> : null}
      {stage === 3 ? <>
        <p className="text-sm">Откройте кабинет {platform.name}, выберите нужную компанию и перенесите проверенный пакет. Публикацию подтверждаете в кабинете площадки самостоятельно.</p>
        {!ready ? <p role="alert" className="text-sm text-muted-foreground">Сначала подтвердите шаги «Данные», «Услуги» и «Фотографии».</p> : null}
        <div className="flex flex-wrap gap-2"><Button asChild variant="outline"><a href={platform.url} target="_blank" rel="noopener noreferrer">Открыть кабинет {platform.name}</a></Button><Button variant="outline" disabled={busy} onClick={() => void download('instructions')}>Скачать пакет текстов (TXT)</Button></div>
        <p className="text-sm text-muted-foreground">Отметьте перенос только после отправки изменений в кабинете. Модерация и появление в публичной карточке — отдельный этап.</p>
      </> : null}
      {stage === 4 ? <>
        <p className="text-sm">Дождитесь обработки изменений площадкой. Откройте публичную карточку и сверьте данные, услуги, цены и фотографии. Кабинет управления не заменяет публичную проверку.</p>
        {safeLink(card?.url) ? <Button asChild variant="outline"><a href={safeLink(card?.url)} target="_blank" rel="noopener noreferrer">Открыть публичную карточку</a></Button> : <p className="text-sm text-muted-foreground">Публичная ссылка не подтверждена. Укажите её в разделе «Карты и отзывы», затем подготовьте новый пакет для проверки.</p>}
        <p className="text-sm">Для независимой проверки откройте «Проверка карточек на картах» в списке задач. Автоматическая визуальная проверка пока недоступна. Эта отметка фиксирует только вашу ручную проверку.</p>
      </> : null}
      <label className="flex items-start gap-3 rounded-xl bg-muted p-3 text-sm"><input className="mt-1 h-4 w-4" type="checkbox" checked={Boolean(state.steps[currentStage.id])} disabled={busy || (stage === 3 && !ready) || (stage === 4 && !state.steps.submission)} onChange={(event) => toggleStage(event.target.checked)} /><span>{currentStage.confirmation}</span></label>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"><span className="text-xs text-muted-foreground">{dirty ? 'Есть несохранённые изменения' : 'Прогресс этого пакета'}</span><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || !dirty} onClick={() => void save()}>Сохранить прогресс</Button>{stage < stages.length - 1 ? <Button disabled={busy} onClick={() => void navigate(provider, stage + 1)}>Далее</Button> : <Button disabled={busy} onClick={() => void navigate(available[(available.findIndex((item) => item.id === provider) + 1) % available.length]?.id || provider, 0)}>К следующей площадке</Button>}</div></div>
  </section>;
};
