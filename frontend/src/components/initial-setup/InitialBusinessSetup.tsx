import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { setupUrl, useInitialBusinessSetup, visibleError, type Action, type Comparison, type Invite, type PhotoReport, type Setup, type Source, type WebsiteAudit } from './useInitialBusinessSetup';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/services/api';
import { ServiceProposals } from './ServiceProposals';

const fieldNames: Record<string, string> = {
  name: 'Название', city: 'Город', address: 'Адрес', website: 'Сайт', contact_phone: 'Телефон', contact_email: 'Email',
};
const platforms: Record<string, string> = { yandex: 'Яндекс Карты', '2gis': '2ГИС', google: 'Google Maps', telegram: 'Telegram', vk: 'ВКонтакте' };
const statuses: Record<string, string> = {
  added: 'Добавлен', queued: 'В очереди', running: 'Читаем', ready: 'Прочитан',
  unavailable: 'Не удалось прочитать', link_only: 'Есть ссылка',
};

const companyUrl = (path: string, businessId: string) => path + (path.includes('?') ? '&' : '?') + 'business_id=' + encodeURIComponent(businessId);

function SiteAudit({ audit, onCheck, busy }: { audit?: WebsiteAudit; onCheck?: () => void; busy: boolean }) {
  if (audit?.status === 'queued' || audit?.status === 'running') {
    return <p role="status" className="text-muted-foreground">
      {audit.status === 'queued' ? 'SEO-проверка в очереди' : 'Проверяем сайт для поиска'}
    </p>;
  }
  if (audit?.status === 'ready') {
    const total = audit.pages.reduce((sum, page) => sum + page.findings.length, 0);
    return <details className="space-y-2 border-t pt-2">
      <summary className="cursor-pointer font-medium">SEO-аудит сайта · {total ? `Рекомендаций: ${total}` : 'Замечаний нет'}</summary>
      <p className="text-muted-foreground">Проверено страниц: {audit.pages.length} · {new Date(audit.checked_at).toLocaleDateString('ru-RU')}</p>
      {audit.pages.map(page => <div key={page.url} className="space-y-1">
        <a href={page.url} target="_blank" rel="noreferrer" className="break-all underline">{page.url}</a>
        {page.findings.length ? <ul className="space-y-2 pb-2">
          {page.findings.map(finding => <li key={finding.rule}>
            <p className="font-medium">{finding.priority === 'review' ? 'Проверить' : 'Исправить'} · {finding.title}</p>
            <p className="text-muted-foreground">{finding.fix}</p>
          </li>)}
        </ul> : <p className="text-muted-foreground">По проверенным элементам замечаний нет.</p>}
      </div>)}
      {onCheck && <Button size="sm" variant="outline" disabled={busy} onClick={onCheck}>Обновить SEO-аудит</Button>}
    </details>;
  }
  return <>
    {audit?.note && <p className="text-muted-foreground">{audit.note}</p>}
    {onCheck && <Button size="sm" variant="outline" disabled={busy} onClick={onCheck}>
      {audit ? 'Повторить SEO-проверку' : 'Провести SEO-аудит сайта'}
    </Button>}
  </>;
}

const photoCategories = {
  entrance: 'Вход и ориентиры', exterior: 'Фасад', interior: 'Интерьер', team: 'Команда',
  process: 'Рабочий процесс', result: 'Примеры работ', product: 'Продукт',
  bedroom: 'Спальня', kitchen: 'Кухня', bathroom: 'Санузел',
};

function PhotoChoice({ item, send, busy }: {
  item: { key: string; image_url: string; provider: string };
  send?: (action: Action) => Promise<boolean>;
  busy: boolean;
}) {
  const [category, setCategory] = useState('');
  return <li className="flex flex-wrap items-center gap-2 border-t py-2">
    <a className="underline" href={item.image_url} target="_blank" rel="noreferrer">
      Посмотреть фото · {platforms[item.provider] || item.provider}
    </a>
    {send && <>
      <select className="min-w-0 rounded-md border bg-background p-1"
        aria-label="Что показано на фото" value={category} onChange={event => setCategory(event.target.value)}>
        <option value="">Выберите категорию</option>
        {Object.entries(photoCategories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
      <Button size="sm" variant="outline" disabled={busy || !category}
        onClick={() => void send({ action: 'photo_pick', key: item.key, category })}>Добавить в подборку</Button>
    </>}
  </li>;
}

function PhotoCheck({ report, businessId, send, busy }: {
  report?: PhotoReport | null;
  businessId: string;
  send?: (action: Action) => Promise<boolean>;
  busy: boolean;
}) {
  const [copyStatus, setCopyStatus] = useState('');
  const library = companyUrl('/dashboard/content?tab=media', businessId);
  const pending = report?.status === 'queued' || report?.status === 'running';
  const copyReport = async () => {
    if (report?.status !== 'ready') return;
    const inventory = [`В медиатеке ${report.library_count} фото`, ...report.library_categories];
    const lines = [
      'Фото для карт',
      inventory.join(' · '),
      ...(report.missing.length ? ['', 'Доснять', ...report.missing.map(item => '• ' + item.tip)] : []),
      ...(report.shortlist.length ? ['', 'Подборка с карт', ...report.shortlist.map(photo => `• ${photo.label} · ${photo.image_url}`)] : []),
      ...(report.cover ? ['Обложка · ' + report.cover] : []),
      ...(report.note ? [report.note] : []),
      ...(report.sources.length ? ['', 'Источники', ...report.sources.map(source => (platforms[source.provider] || source.provider) + ' · '
        + (source.status === 'sample' ? `${source.count} в выборке` : 'галерея не подтверждена') + ' · ' + source.url)] : []),
      '', 'Медиатека LocalOS · ' + new URL(library, window.location.origin).href,
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopyStatus('Отчёт скопирован.');
    } catch {
      setCopyStatus('Не удалось скопировать отчёт.');
    }
  };
  const ready = report?.status === 'ready' ? report : null;
  return <details className="group/photo rounded-lg border">
    <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 font-medium [&::-webkit-details-marker]:hidden">
      <span>Фото для карт</span>
      {(ready || pending) && <span className="ml-auto text-xs font-normal text-muted-foreground group-open/photo:hidden">
        {ready ? `${ready.library_count} в медиатеке` : 'Проверяем…'}
      </span>}
      <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground group-open/photo:rotate-180" />
    </summary>
    <div className="space-y-2 px-3 pb-3 text-sm">
      {pending && <p role="status" className="text-muted-foreground">Проверяем фото…</p>}
      {report?.note && <p className="text-muted-foreground">{report.note}</p>}
      {ready && <>
        <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-md bg-muted/50 px-3 py-2">
          <div className="min-w-0 flex-1 basis-52">
            <h3 className="font-medium">В медиатеке <span className="tabular-nums">{ready.library_count}</span></h3>
            {ready.library_categories.length > 0 && <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {ready.library_categories.map(label => <li key={label} className="rounded-md border bg-background px-2 py-0.5 text-xs">{label}</li>)}
            </ul>}
          </div>
          <div className="min-w-0 flex-1 basis-40">
            <h3 className="font-medium">Доснять</h3>
            {ready.missing.length > 0 ? <details>
              <summary className="min-h-10 cursor-pointer py-2 text-sm text-muted-foreground">{ready.missing.map(item => item.label).join(', ')}</summary>
              <ul className="space-y-1 pb-1 pl-3 text-xs text-muted-foreground">
                {ready.missing.map(item => <li key={item.label}>{item.tip}</li>)}
              </ul>
            </details> : <p className="mt-1 text-muted-foreground">По чек-листу всё есть</p>}
          </div>
        </div>
        {ready.shortlist.length > 0 && <details className="border-b">
          <summary className="min-h-10 cursor-pointer py-2 font-medium">Подборка с карт · <span className="tabular-nums">{ready.shortlist.length}</span></summary>
          <ul className="space-y-1 pb-2 pl-3">
            {ready.shortlist.map(photo => <li key={photo.key} className="flex flex-wrap items-baseline gap-x-2">
              <a className="underline" href={photo.image_url} target="_blank" rel="noreferrer">{photo.label}</a>
              <a className="text-xs text-muted-foreground underline" href={photo.source_url} target="_blank" rel="noreferrer">Карточка-источник</a>
            </li>)}
          </ul>
          {ready.cover && <p className="pb-2 pl-3 text-xs text-muted-foreground">Обложка · {ready.cover}</p>}
        </details>}
        {ready.review.length > 0 && <details className="border-b">
          <summary className="min-h-10 cursor-pointer py-2 font-medium">Уточнить фото · <span className="tabular-nums">{ready.review.length}</span></summary>
          <ul>{ready.review.map(item => <PhotoChoice key={item.key} item={item} send={send} busy={busy} />)}</ul>
        </details>}
        {(ready.sources.length > 0 || ready.rejected > 0 || send) && <details className="border-b">
          <summary className="min-h-10 cursor-pointer py-2 font-medium">Проверка площадок</summary>
          <div className="space-y-2 pb-2 pl-3 text-xs text-muted-foreground">
            {ready.sources.length > 0 && <ul className="space-y-1">
              {ready.sources.map(source => <li key={source.url}>
                <a className="underline" href={source.url} target="_blank" rel="noreferrer">{platforms[source.provider] || source.provider}</a>
                {' · '}{source.status === 'sample' ? `${source.count} в выборке` : 'Галерея не подтверждена'}
              </li>)}
            </ul>}
            {ready.rejected > 0 && <p>Исключено при проверке · {ready.rejected}</p>}
            {send && <Button size="sm" variant="outline" disabled={busy} onClick={() => void send({ action: 'photo_check' })}>Обновить проверку</Button>}
          </div>
        </details>}
      </>}
      <div className="flex flex-wrap items-center gap-1.5">
        <Button asChild size="sm" variant="ghost" className="min-h-10"><Link to={library}>Открыть медиатеку</Link></Button>
        {ready && <Button size="sm" variant="outline" className="min-h-10" onClick={() => void copyReport()}>Скопировать отчёт</Button>}
        {send && !pending && !ready && <Button size="sm" variant="outline" disabled={busy}
          onClick={() => void send({ action: 'photo_check' })}>Проверить фото</Button>}
      </div>
      {copyStatus && <p role="status">{copyStatus}</p>}
    </div>
  </details>;
}

function ViewLinks({ businessId }: { businessId: string }) {
  return <nav className="flex flex-wrap gap-x-4 gap-y-2 text-sm" aria-label="Данные в кабинете">
    {[
      ['/dashboard/profile', 'Профиль компании'],
      ['/dashboard/card?tab=services', 'Услуги'],
      ['/dashboard/card?tab=keywords', 'Семантическое ядро'],
      ['/dashboard/profile?section=knowledge', 'Факты о компании'],
      ['/dashboard/card?tab=competitors', 'Конкуренты'],
    ].map(([path, text]) => <Link className="font-medium underline underline-offset-4" key={path} to={companyUrl(path, businessId)}>{text}</Link>)}
  </nav>;
}

function Keywords({ state }: { state: Setup }) {
  return <div className="space-y-3">
    <p className="text-sm text-muted-foreground">Город компании · {state.profile.city || 'не указан'}. Частотность из Wordstat. Регион поиска может отличаться от города компании.</p>
    {[...(state.category_keywords?.length ? [{ key: 'activity-type', original: state.activity_type ?? 'Вид деятельности', keywords: state.category_keywords }] : []), ...state.services].map(item => <details className="rounded-lg border p-3" key={item.key}>
      <summary className="cursor-pointer font-medium">{item.original}</summary>
      <ul className="mt-2 space-y-2 text-sm">
        {item.keywords.map(keyword => <li key={keyword.text}>
          <span>{keyword.text}</span>
          <p className="text-muted-foreground">{[keyword.source, keyword.dated, typeof keyword.views === 'number' ? keyword.views.toLocaleString('ru-RU') + ' показов' : 'частотность не подтверждена'].filter(Boolean).join(' · ')}</p>
        </li>)}
      </ul>
    </details>)}
  </div>;
}

function Comparisons({ rows }: { rows: Comparison[] }) {
  return <div className="space-y-3">{rows.map(row => <details key={row.url} className="rounded-lg border p-3">
    <summary className="cursor-pointer font-medium">{row.name} · {platforms[row.platform] || row.platform}</summary>
    <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
      <div><h4 className="font-medium">Ваша компания</h4>
        {row.ours ? <p>Оценка {row.ours.rating || '—'} · Отзывы {row.ours.reviews || '—'}</p> : <p>Нужен снимок вашей карточки на той же площадке.</p>}
        {row.our_checked_at && <p className="text-muted-foreground">Снимок от {row.our_checked_at.slice(0, 10)}</p>}
        {row.our_services.length > 0 && <p className="text-muted-foreground">{row.our_services.join(', ')}</p>}
      </div>
      <div><h4 className="font-medium">Конкурент</h4><p>Оценка {row.theirs?.rating || '—'} · Отзывы {row.theirs?.reviews || '—'}</p>
        {row.checked_at && <p className="text-muted-foreground">Снимок от {row.checked_at.slice(0, 10)}</p>}
        {row.their_services.length > 0 && <p className="text-muted-foreground">{row.their_services.join(', ')}</p>}
      </div>
    </div>
    <a className="mt-2 inline-block text-sm underline" href={row.url} rel="noreferrer" target="_blank">Открыть источник</a>
  </details>)}</div>;
}

export function InitialSetupMenuResult({ businessId, section }: { businessId: string | null | undefined; section: 'competitors' | 'profile' }) {
  const setup = useInitialBusinessSetup(businessId || null, Boolean(businessId));
  const state = setup.state;
  if (!state) return null;
  if (section === 'competitors' && state.comparisons.length) return <section className="space-y-3 rounded-lg border bg-card p-4">
    <h3 className="font-semibold">Сравнение по добавленным карточкам</h3><Comparisons rows={state.comparisons} />
  </section>;
  const savedSocial = state.sources.filter(source => source.kind === 'social' && !source.competitor);
  if (section === 'profile') return <section className="space-y-2 rounded-lg border bg-card p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><h3 className="font-semibold">Первичная настройка</h3><p className="text-sm text-muted-foreground">{state.saved && !state.seo_dirty ? 'Кабинет сохранён' : 'Подготовка продолжается'}</p></div>
      <Button variant="outline" size="sm" asChild><Link to={companyUrl('/dashboard/operator?setup=1', state.business_id)}>Открыть в чате</Link></Button>
    </div>
    {savedSocial.length > 0 && <><h4 className="text-sm font-medium">Публичные соцсети и мессенджеры</h4>
      <ul className="space-y-1">{savedSocial.map(source => <li key={source.key}><a className="text-sm underline" href={source.url} rel="noreferrer" target="_blank">{platforms[source.provider] || source.provider}</a>{source.found_on && <span className="ml-2 text-sm text-muted-foreground">Найдено на сайте</span>}</li>)}</ul></>}
  </section>;
  return null;
}

function Handoff({ state }: { state: Setup }) {
  const [email, setEmail] = useState('');
  const [result, setResult] = useState<Invite | null>(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [copied, setCopied] = useState(false);
  const link = result?.invite_url || (result?.login_path ? window.location.origin + result.login_path : '');
  return <details className="rounded-lg border p-3">
    <summary className="cursor-pointer font-medium">Подготовить доступ владельцу</summary>
    <form className="mt-3 space-y-2" onSubmit={async event => {
      event.preventDefault();
      setPending(true);
      setError('');
      setResult(null);
      setCopied(false);
      try {
        const response = await api.post(setupUrl(state.business_id) + '/owner', { email, revision: state.revision });
        setResult(response.data);
      } catch (err) { setError(visibleError(err)); }
      finally { setPending(false); }
    }}>
      <label className="block space-y-1 text-sm">Почта для входа владельца<Input type="email" required value={email} onChange={event => { setEmail(event.target.value); setResult(null); }} /></label>
      <p className="text-sm text-muted-foreground">Проверьте получателя. Ссылку можно скопировать после подготовки доступа.</p>
      <Button size="sm" disabled={pending || !email.trim()}>Подтвердить получателя</Button>
    </form>
    {error && <p className="mt-2 text-sm text-destructive" role="alert">{error}</p>}
    {result && <div className="mt-2 space-y-2" role="status">
      <p>{result.existing_account ? 'Владелец может войти с существующим паролем.' : 'Ссылка для первого входа подготовлена.'} {result.email}</p>
      <div className="flex flex-wrap gap-2">
        <Input readOnly value={link} className="min-w-0 flex-1" aria-label="Ссылка для владельца" onFocus={event => event.target.select()} />
        <Button size="sm" variant="outline" onClick={() => void navigator.clipboard?.writeText(link).then(() => setCopied(true)).catch(() => setError('Выделите ссылку и скопируйте её вручную.'))}>{copied ? 'Ссылка скопирована' : 'Скопировать ссылку'}</Button>
      </div>
    </div>}
  </details>;
}

export function InitialSetupChat({ setup, isStaff, onExit }: { setup: ReturnType<typeof useInitialBusinessSetup>; isStaff: boolean; onExit: () => void }) {
  const { state, send, available, loading, canEdit, error, notice, busy, reading } = setup;
  if (loading || available === undefined && !error) return <p role="status">Открываем настройку компании…</p>;
  if (available !== true) return <div className="space-y-3"><p role="status">{error || 'Первичная настройка пока недоступна для этой компании.'}</p>
    {error && <Button variant="outline" onClick={() => void setup.refresh()}>Повторить</Button>}
    <Button variant="ghost" onClick={onExit}>Вернуться к рабочему чату</Button></div>;
  const sourceGroups: { kind: Source['kind']; label: string }[] = [
    { kind: 'website', label: 'Сайт' }, { kind: 'map', label: 'Карты' }, { kind: 'social', label: 'Соцсети и мессенджеры' },
  ];
  const stage = !state?.started ? 'Данные компании' : reading ? 'Сбор по источникам' : state.seo_prepared && !state.seo_dirty ? 'Проверка и доступ' : 'Услуги и SEO';
  return <section className="mx-auto max-w-4xl space-y-4 rounded-xl border bg-card p-4" aria-labelledby="initial-setup-title">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><h2 id="initial-setup-title" className="text-lg font-semibold">Первичная настройка компании</h2>
        <p className="text-sm text-muted-foreground">{state?.profile.name || 'Подготовьте профиль, услуги и сведения для контента.'}</p></div>
      <Button size="sm" variant="ghost" onClick={onExit}>Рабочий чат</Button>
    </div>
    <ol className="flex flex-wrap gap-3 border-b pb-2 text-sm" aria-label="Этапы">
      {['Данные компании', 'Сбор по источникам', 'Услуги и SEO', 'Проверка и доступ'].map(label =>
        <li key={label} aria-current={label === stage ? 'step' : undefined} className={label === stage ? 'font-semibold underline underline-offset-4' : 'text-muted-foreground'}>{label}</li>)}
    </ol>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {!state ? canEdit && <Button onClick={() => void send({ action: 'start' })} disabled={busy}>Начать настройку</Button> : <>
      <p className="text-sm">Вставьте ссылку на сайт, карты или соцсеть. Для сравнения напишите «Конкурент:» перед ссылкой на карту.</p>
      <details className="text-sm"><summary className="cursor-pointer">Как дополнить данные</summary><p className="pt-1 text-muted-foreground">Напишите «Вид деятельности: …» или «Услуга: название | описание». Для контактов используйте «Телефон: …» и «Почта: …».</p></details>
      {state.activity.slice(-2).map(item => <div key={item.at} className="space-y-1 text-sm">
        <p className="text-muted-foreground">{item.message}</p><p>{item.reply}</p>
      </div>)}
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        {state.activity_type && <div><dt className="text-muted-foreground">Вид деятельности</dt><dd className="font-medium">{state.activity_type}</dd></div>}
        {Object.entries(fieldNames).filter(([key]) => Boolean(state.profile[key])).map(([key, label]) => <div key={key} className="min-w-0">
          <dt className="text-muted-foreground">{label}</dt><dd className="break-words font-medium">{state.profile[key]}</dd></div>)}
      </dl>
      <details className="rounded-lg border p-3" open={state.sources.length > 0 || undefined}>
        <summary className="cursor-pointer font-medium">Сайт, карты и соцсети · {state.sources.length}</summary>
        {sourceGroups.map(group => <section key={group.kind} className="mt-3 border-t pt-2">
          <h3 className="text-sm font-medium">{group.label}</h3>
          <ul className="divide-y">
          {state.sources.filter(source => source.kind === group.kind).map(source => <li key={source.key} className="space-y-1 py-2 text-sm">
            <div className="flex flex-wrap justify-between gap-x-2">
              <a href={source.url} target="_blank" rel="noreferrer" className="min-w-0 break-all underline">{source.competitor ? 'Конкурент · ' : ''}{platforms[source.provider] || (source.kind === 'website' ? 'Сайт' : source.provider)}</a>
              <span>{statuses[source.status] || source.status}{source.service_count > 0 ? ' · Услуг: ' + source.service_count : ''}</span>
            </div>
            {source.found_on && <p className="text-muted-foreground">Найдено на сайте</p>}
            {source.note && <p className="text-muted-foreground">{source.note}</p>}
            {source.kind === 'website' && source.status === 'ready' && <SiteAudit
              audit={source.website_audit} busy={busy}
              onCheck={state.can_edit ? () => void send({ action: 'website_audit', key: source.key }) : undefined}
            />}
            {state.can_edit && <div className="flex flex-wrap gap-1">
              {source.status === 'unavailable' && <Button size="sm" variant="outline" disabled={busy} onClick={() => void send({ action: 'retry', key: source.key })}>Повторить чтение</Button>}
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => void send({ action: 'remove', key: source.key })}>Исключить из подготовки</Button>
            </div>}
          </li>)}
          </ul>
          {!state.sources.some(source => source.kind === group.kind) && <p className="text-sm text-muted-foreground">Ссылок пока нет.</p>}
        </section>)}
        {!state.sources.length && <p className="mt-2 text-sm text-muted-foreground">Можно продолжить с текущим каталогом и профилем.</p>}
      </details>
      {state.profile_choices.length > 0 && <details className="rounded-lg border p-3">
        <summary className="cursor-pointer font-medium">Проверить найденные контакты и адрес</summary>
        <ul className="mt-2 space-y-2 text-sm">{state.profile_choices.map(item => <li key={item.key} className="space-y-1">
          <p><strong>{fieldNames[item.field] || item.field}</strong> · {item.text}</p><p className="text-muted-foreground">Сейчас · {state.profile[item.field] || 'не заполнено'}</p>
          {item.url && <a className="mr-2 underline" href={item.url} target="_blank" rel="noreferrer">Источник</a>}
          {state.can_edit && item.text !== state.profile[item.field] && <Button size="sm" variant="outline" disabled={busy} onClick={() => void send({ action: 'profile', key: item.key })}>Использовать это значение</Button>}
        </li>)}</ul>
      </details>}
      {state.services.length > 0 && <details className="rounded-lg border p-3"><summary className="mb-2 cursor-pointer font-medium">Услуги и предложенные изменения · {state.services.length}</summary>
        <ServiceProposals key={state.business_id} items={state.services} send={state.can_edit ? send : undefined}
          disabled={busy || state.seo_dirty} error={error} /></details>}
      {state.seo_prepared && (state.services.length > 0 || Boolean(state.category_keywords?.length)) && <details className="space-y-2 rounded-lg border p-3">
        <summary className="cursor-pointer font-medium">Семантическое ядро</summary>
        <Keywords state={state} />
      </details>}
      {state.facts.length > 0 && <details className="rounded-lg border p-3">
        <summary className="cursor-pointer font-medium">Факты для контента · {state.facts.length}</summary>
        <ul className="mt-2 space-y-3 text-sm">{state.facts.map(fact => <li key={fact.key}>
          <p>{fact.text}</p><a className="mr-2 underline" href={fact.url} target="_blank" rel="noreferrer">Источник · {fact.observed_at?.slice(0, 10)}</a>
          {fact.accepted ? <span>Сохранено</span> : state.can_edit && <Button size="sm" variant="outline" disabled={busy} onClick={() => void send({ action: 'fact', key: fact.key })}>Подтвердить факт</Button>}
        </li>)}</ul>
      </details>}
      {state.comparisons.length > 0 && <Comparisons rows={state.comparisons} />}
      {state.started && <PhotoCheck key={state.business_id} report={state.photo_report} businessId={state.business_id}
        busy={busy || reading} send={state.can_edit ? send : undefined} />}
      {reading && <p className="text-sm" role="status">Читаем источники. Можно вернуться позже.</p>}
      {state.can_edit && !state.started && <Button disabled={busy} onClick={() => void send({ action: 'start' })}>Начать настройку</Button>}
      {state.can_edit && state.started && !reading && (state.sources.some(source => source.status === 'added') ?
        <Button disabled={busy} onClick={() => void send({ action: 'read' })}>Собрать данные</Button> :
        !state.seo_prepared || state.seo_dirty ?
          <Button disabled={busy} onClick={() => void send({ action: 'prepare' })}>Разобрать услуги и подобрать запросы</Button> :
          !state.saved && <Button disabled={busy} onClick={() => void send({ action: 'save' })}>Сохранить кабинет</Button>)}
      {state.seo_prepared && !state.services.length && <p className="text-sm text-muted-foreground">Услуг пока не найдено. Добавьте услугу в каталоге или пришлите ссылку на источник.</p>}
      {isStaff && state.saved && !state.seo_dirty && !reading && <Handoff key={state.business_id} state={state} />}
      <ViewLinks businessId={state.business_id} />
    </>}
  </section>;
}
