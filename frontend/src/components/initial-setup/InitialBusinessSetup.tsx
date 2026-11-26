import {
  ArrowUpRight, Building2, ChevronDown, Download, FileText, Images,
  ListChecks, Loader2, MapPin, MessageSquare, Search, UserRoundPlus, X, type LucideIcon,
} from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { getApiEndpoint } from '@/config/api';
import { browserBearerToken, browserCookieAuthEnabled } from '@/lib/browserSessionFetch';
import { setupUrl, useInitialBusinessSetup, visibleError, type Action, type Comparison, type Invite, type PhotoReport, type Setup, type Source, type WebsiteAudit } from './useInitialBusinessSetup';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { LocalOSChatAvatar } from '@/components/operator/LocalOSChatAvatar';
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
    return <p role="status" className="flex items-center gap-2 text-muted-foreground">
      <LocalOSChatAvatar />
      <Loader2 aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin" />
      {audit.status === 'queued' ? 'SEO-проверка в очереди' : 'Проверяем сайт для поиска'}
    </p>;
  }
  if (audit?.status === 'ready') {
    const total = audit.pages.reduce((sum, page) => sum + page.findings.length, 0);
    return <SetupDisclosure title="SEO-аудит сайта" meta={total ? `Правки · ${total}` : 'Замечаний нет'} className="border-t" compact>
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
    </SetupDisclosure>;
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
  return <SetupDisclosure title="Фото для карт" icon={Images} compact meta={ready ? `${ready.library_count} в медиатеке` : pending ? 'Проверяем…' : undefined}>
    <div className="space-y-2 text-sm">
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
            {ready.missing.length === 0 && <p className="mt-1 text-muted-foreground">По чек-листу всё есть</p>}
            {ready.missing.length === 1 && <p className="mt-1 text-muted-foreground">{ready.missing[0].tip}</p>}
            {ready.missing.length > 1 && <>
              <p className="mt-1 text-muted-foreground">{ready.missing.map(item => item.label).join(', ')}</p>
              <SetupDisclosure title="Как снять" compact>
                <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                  {ready.missing.map(item => <li key={item.label}>{item.tip}</li>)}
                </ul>
              </SetupDisclosure>
            </>}
          </div>
        </div>
        {(ready.shortlist.length > 0 || ready.review.length > 0 || ready.sources.length > 0 || ready.rejected > 0 || send) && <div className="divide-y border-b">
          {ready.shortlist.length > 0 && <SetupDisclosure title="Подборка с карт" count={ready.shortlist.length} compact>
            <ul className="space-y-1">
              {ready.shortlist.map(photo => <li key={photo.key} className="flex flex-wrap items-baseline gap-x-2">
                <a className="underline" href={photo.image_url} target="_blank" rel="noreferrer">{photo.label}</a>
                <a className="text-xs text-muted-foreground underline" href={photo.source_url} target="_blank" rel="noreferrer">Карточка-источник</a>
              </li>)}
            </ul>
            {ready.cover && <p className="text-xs text-muted-foreground">Обложка · {ready.cover}</p>}
          </SetupDisclosure>}
          {ready.review.length > 0 && <SetupDisclosure title="Уточнить фото" count={ready.review.length} compact>
            <ul>{ready.review.map(item => <PhotoChoice key={item.key} item={item} send={send} busy={busy} />)}</ul>
          </SetupDisclosure>}
          {(ready.sources.length > 0 || ready.rejected > 0 || send) && <SetupDisclosure title="Проверка площадок" compact>
            <div className="space-y-2 text-xs text-muted-foreground">
              {ready.sources.length > 0 && <ul className="space-y-1">
                {ready.sources.map(source => <li key={source.url}>
                  <a className="underline" href={source.url} target="_blank" rel="noreferrer">{platforms[source.provider] || source.provider}</a>
                  {' · '}{source.status === 'sample' ? `${source.count} в выборке` : 'Галерея не подтверждена'}
                </li>)}
              </ul>}
              {ready.rejected > 0 && <p>Исключено при проверке · {ready.rejected}</p>}
              {send && <Button size="sm" variant="outline" disabled={busy} onClick={() => void send({ action: 'photo_check' })}>Обновить проверку</Button>}
            </div>
          </SetupDisclosure>}
        </div>}
      </>}
      <div className="flex flex-wrap items-center gap-1.5">
        <Button asChild size="sm" variant="ghost" className="min-h-10"><Link to={library}>Открыть медиатеку</Link></Button>
        {ready && <Button size="sm" variant="outline" className="min-h-10" onClick={() => void copyReport()}>Скопировать отчёт</Button>}
        {send && !pending && !ready && <Button size="sm" variant="outline" disabled={busy}
          onClick={() => void send({ action: 'photo_check' })}>Проверить фото</Button>}
      </div>
      {copyStatus && <p role="status">{copyStatus}</p>}
    </div>
  </SetupDisclosure>;
}

function SetupDisclosure({ title, icon: Icon, children, count, meta, compact, open, className }: {
  title: string;
  icon?: LucideIcon;
  children: ReactNode;
  count?: number;
  meta?: string;
  compact?: boolean;
  open?: boolean;
  className?: string;
}) {
  return <details open={open} className={cn('[&[open]>summary>svg:last-child]:rotate-180', !compact && 'rounded-lg border', className)}>
    <summary className={cn('flex cursor-pointer list-none items-center gap-2.5 rounded-md py-2 text-sm font-medium hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden',
      Icon ? 'min-h-11 px-3' : 'min-h-10 px-2')}>
      {Icon && <Icon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />}
      <span className="min-w-0 break-words">{title}</span>
      {count !== undefined && <span className="rounded-md bg-muted px-1.5 py-0.5 text-xs tabular-nums text-muted-foreground">{count}</span>}
      {meta && <span className="ml-auto min-w-0 text-right text-xs font-normal tabular-nums text-muted-foreground">{meta}</span>}
      <ChevronDown aria-hidden="true" className={cn('h-4 w-4 shrink-0 text-muted-foreground', !meta && 'ml-auto')} />
    </summary>
    <div className={cn('space-y-2 pb-3', Icon ? 'px-3' : 'px-2')}>{children}</div>
  </details>;
}

function SetupLink({ path, businessId, children }: { path: string; businessId: string; children: ReactNode }) {
  return <Button size="sm" variant="ghost" asChild>
    <Link to={companyUrl(path, businessId)}>{children}<ArrowUpRight aria-hidden="true" className="ml-1.5 h-3.5 w-3.5" /></Link>
  </Button>;
}

function Keywords({ state }: { state: Setup }) {
  const groups = [
    ...(state.category_keywords?.length ? [{ key: 'activity-type', original: state.activity_type ?? 'Вид деятельности', keywords: state.category_keywords }] : []),
    ...state.services.filter(item => item.keywords.length > 0),
  ];
  if (!groups.length) return <p className="text-xs text-muted-foreground">Запросов пока нет.</p>;
  return <div className="divide-y border-y">
    {groups.map(item => <SetupDisclosure key={item.key} title={item.original} compact>
      <dl className="space-y-2 pb-2 pl-3 text-sm">
        {item.keywords.map(keyword => <div key={keyword.text} className="flex flex-wrap justify-between gap-x-2 gap-y-1">
          <dt>{keyword.text}</dt>
          <dd className="text-xs text-muted-foreground tabular-nums">
            {[typeof keyword.views === 'number' ? keyword.views.toLocaleString('ru-RU') + ' показов' : 'Без частотности', keyword.source, keyword.dated].filter(Boolean).join(' · ')}
          </dd>
        </div>)}
      </dl>
    </SetupDisclosure>)}
  </div>;
}

function Comparisons({ rows }: { rows: Comparison[] }) {
  return <div className="space-y-3">{rows.map(row => <SetupDisclosure key={row.url} title={row.name} meta={platforms[row.platform] || row.platform}>
    <div className="grid gap-3 text-sm sm:grid-cols-2">
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
  </SetupDisclosure>)}</div>;
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
  return <SetupDisclosure title="Доступ владельцу" icon={UserRoundPlus}>
    <form className="space-y-2" onSubmit={async event => {
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
      <label className="block max-w-sm space-y-1 text-sm">Почта владельца<Input type="email" required value={email} onChange={event => { setEmail(event.target.value); setResult(null); }} /></label>
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
  </SetupDisclosure>;
}

function SetupStep({ title, icon: Icon, working = false, children }: {
  title: string; icon: LucideIcon; working?: boolean; children?: ReactNode;
}) {
  const Indicator = working ? Loader2 : Icon;
  return <article className="w-fit max-w-full space-y-2 rounded-2xl border bg-card px-3 py-2.5 text-sm sm:px-4">
    <h3 role={working ? 'status' : undefined} className="flex items-center gap-2 font-medium">
      {working && <LocalOSChatAvatar />}
      <Indicator aria-hidden="true" className={cn('h-4 w-4 shrink-0 text-muted-foreground', working && 'motion-safe:animate-spin')} />
      {title}
    </h3>
    {children}
  </article>;
}

function SetupChatMessages({ activity, notice }: { activity: Setup['activity']; notice: string }) {
  const reply = notice === activity.at(-1)?.reply ? '' : notice;
  if (!activity.length && !reply) return null;
  return <div role="log" aria-label="Сообщения настройки" className="mx-auto max-w-4xl space-y-3">
    {activity.map(item => <div key={item.at} className="flex flex-col gap-2">
      <p className="max-w-[90%] self-end whitespace-pre-wrap break-words rounded-2xl bg-primary px-3 py-2 text-sm text-primary-foreground">
        <span className="sr-only">Вы. </span>{item.message}
      </p>
      <p className="max-w-[90%] self-start whitespace-pre-wrap break-words rounded-2xl border bg-card px-3 py-2 text-sm">
        <span className="sr-only">LocalOS. </span>{item.reply}
      </p>
    </div>)}
    {reply && <div className="flex"><p className="max-w-[90%] rounded-2xl border bg-card px-3 py-2 text-sm">{reply}</p></div>}
  </div>;
}

const sourceGroups: { kind: Source['kind']; label: string }[] = [
  { kind: 'website', label: 'Сайт' }, { kind: 'map', label: 'Карты' }, { kind: 'social', label: 'Соцсети и мессенджеры' },
];

function SetupSources({ state, busy, send }: { state: Setup; busy: boolean; send: (action: Action) => Promise<boolean> }) {
  const profileFields = Object.entries(fieldNames).filter(([key]) => Boolean(state.profile[key]));
  return <>
    {(state.activity_type || profileFields.length > 0) && <dl className="grid gap-x-5 gap-y-2 py-2 text-sm sm:grid-cols-2">
      {state.activity_type && <div className="min-w-0"><dt className="text-xs text-muted-foreground">Вид деятельности</dt>
        <dd className="break-words font-medium">{state.activity_type}</dd></div>}
      {profileFields.map(([key, label]) => <div key={key} className="min-w-0">
        <dt className="text-xs text-muted-foreground">{label}</dt>
        <dd className="break-words font-medium">{state.profile[key]}</dd>
      </div>)}
    </dl>}
    {sourceGroups.map(group => {
      const sources = state.sources.filter(source => source.kind === group.kind);
      if (!sources.length) return null;
      return <section key={group.kind} className="border-t pt-3">
        <h3 className="text-xs font-medium text-muted-foreground">{group.label}</h3>
        <ul className="divide-y">
          {sources.map(source => {
            const name = platforms[source.provider] || (source.kind === 'website' ? 'Сайт' : source.provider);
            return <li key={source.key} className="space-y-1.5 py-1.5 text-sm">
              <div className="flex items-center gap-1.5">
                <div className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
                  <a href={source.url} target="_blank" rel="noreferrer" className="min-w-0 break-words font-medium underline underline-offset-4">
                    {source.competitor ? 'Конкурент · ' : ''}{name}
                  </a>
                  <span className="text-xs text-muted-foreground">{statuses[source.status] || source.status}
                    {source.service_count > 0 && ' · Услуг: ' + source.service_count}
                    {!!source.photo_candidate_count && ' · Фото: ' + source.photo_candidate_count}
                    {source.found_on && ' · Найдено на сайте'}
                  </span>
                </div>
                {state.can_edit && <Button size="icon" variant="ghost" className="shrink-0 text-muted-foreground"
                  aria-label={`Исключить источник «${name}»`} title="Исключить источник" disabled={busy}
                  onClick={() => void send({ action: 'remove', key: source.key })}><X aria-hidden="true" /></Button>}
              </div>
              {source.status === 'ready' && source.note && <p className="text-xs text-muted-foreground">{source.note}</p>}
              {source.kind === 'website' && source.status === 'ready' && <SiteAudit
                audit={source.website_audit} busy={busy}
                onCheck={state.can_edit ? () => void send({ action: 'website_audit', key: source.key }) : undefined}
              />}
            </li>;
          })}
        </ul>
      </section>;
    })}
    {state.profile_choices.length > 0 && <SetupDisclosure title="Найденные контакты и адрес" count={state.profile_choices.length} icon={ListChecks}>
      <ul className="divide-y text-sm">{state.profile_choices.map(item => <li key={item.key} className="space-y-1 py-2">
        <p><strong>{fieldNames[item.field] || item.field}</strong> · {item.text}</p>
        <p className="text-xs text-muted-foreground">Сейчас · {state.profile[item.field] || 'не заполнено'}</p>
        <div className="flex flex-wrap items-center gap-2">
          {item.url && <a className="text-xs underline" href={item.url} target="_blank" rel="noreferrer">Источник</a>}
          {state.can_edit && item.text !== state.profile[item.field] && <Button size="sm" variant="outline" disabled={busy} onClick={() => void send({ action: 'profile', key: item.key })}>Применить</Button>}
        </div>
      </li>)}</ul>
    </SetupDisclosure>}
  </>;
}

const REPORT_DOWNLOAD_TIMEOUT_MS = 15_000;

function SetupReportDownload({ businessId, name }: { businessId: string; name?: string | null }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  const activeRequest = useRef<AbortController | null>(null);
  useEffect(() => () => {
    const request = activeRequest.current;
    activeRequest.current = null;
    request?.abort();
  }, []);

  const download = async () => {
    if (activeRequest.current) return;
    const request = new AbortController();
    activeRequest.current = request;
    const timer = window.setTimeout(() => request.abort(), REPORT_DOWNLOAD_TIMEOUT_MS);
    setDownloading(true);
    setError('');
    try {
      const token = browserBearerToken();
      const response = await fetch(getApiEndpoint('/api' + setupUrl(businessId) + '/report'), {
        cache: 'no-store',
        signal: request.signal,
        credentials: browserCookieAuthEnabled() ? 'include' : 'same-origin',
        headers: token ? { Authorization: 'Bearer ' + token } : {},
      });
      if (!response.ok || !response.headers.get('content-type')?.startsWith('application/pdf')) throw new Error('PDF unavailable');
      const pdf = await response.blob();
      if (request.signal.aborted || activeRequest.current !== request) return;
      const url = URL.createObjectURL(pdf);
      const link = document.createElement('a');
      link.href = url;
      link.download = `LocalOS - ${name?.replace(/[\\/:*?"<>|]/g, '_') || 'первичная настройка'}.pdf`;
      link.hidden = true;
      document.body.appendChild(link);
      try {
        link.click();
      } finally {
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      }
    } catch {
      if (activeRequest.current === request) {
        setError(request.signal.aborted
          ? 'Сервер долго не отвечал. Попробуйте скачать отчёт ещё раз.'
          : 'Не удалось скачать отчёт. Попробуйте ещё раз.');
      }
    } finally {
      window.clearTimeout(timer);
      if (activeRequest.current === request) {
        activeRequest.current = null;
        setDownloading(false);
      }
    }
  };

  return <div className="space-y-1">
    <Button size="sm" variant="outline" disabled={downloading} onClick={() => void download()}>
      <Download aria-hidden="true" />{downloading ? 'Готовим файл…' : 'Скачать отчёт PDF'}
    </Button>
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
  </div>;
}

export function InitialSetupChat({ setup, isStaff, onExit }: { setup: ReturnType<typeof useInitialBusinessSetup>; isStaff: boolean; onExit: () => void }) {
  const { state, send, available, loading, canEdit, error, notice, busy, reading, pendingSources } = setup;
  if (loading || (available === undefined && !error)) return <p role="status">Открываем настройку…</p>;
  if (available !== true) return <div className="space-y-3"><p role="status">{error || 'Настройка для этой компании недоступна.'}</p>
    {error && <Button variant="outline" onClick={() => void setup.refresh()}>Повторить</Button>}
    <Button variant="ghost" onClick={onExit}>Рабочий чат</Button></div>;

  const gathering = reading || pendingSources;
  const sourcesToRead = state?.sources.some(source => source.status === 'added') ?? false;
  const needsSeo = !state?.seo_prepared || state.seo_dirty;
  const preparing = state?.draft_status === 'queued' || state?.draft_status === 'running';
  const draftFailed = state?.draft_status === 'failed';
  const needsSource = state?.draft_status === 'needs_source';
  const canChange = state?.can_edit ?? canEdit;
  const completedSources = state?.sources.filter(source => ['ready', 'unavailable', 'link_only'].includes(source.status)) ?? [];
  const collected = completedSources.filter(source => source.status === 'ready').length;
  const photosFound = completedSources.reduce((sum, source) => sum + (source.photo_candidate_count ?? 0), 0);
  const queryCount = state ? new Set([...state.category_keywords, ...state.services.flatMap(item => item.keywords)]
    .map(keyword => keyword.text.trim().toLowerCase()).filter(Boolean)).size : 0;
  const sourcesDone = !gathering && !sourcesToRead;
  const showAnalysis = Boolean(state?.started && sourcesDone && !needsSource);
  const analysisDone = showAnalysis && !needsSeo && !preparing && !draftFailed;
  const checkingPhotos = state?.photo_report?.status === 'queued' || state?.photo_report?.status === 'running';
  const canReview = analysisDone && !checkingPhotos;
  const saved = Boolean(canReview && state?.saved);
  const contactsToReview = state?.profile_choices.filter(item => item.text !== state.profile[item.field]).length ?? 0;

  return <section className="mx-auto max-w-4xl space-y-3" aria-labelledby="initial-setup-title">
    <header className="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
      <div className="min-w-0">
        <h2 id="initial-setup-title" className="text-sm font-semibold">Первичная настройка компании</h2>
        {state?.profile.name && <p className="break-words text-xs text-muted-foreground">{state.profile.name}</p>}
      </div>
      <Button size="sm" variant="ghost" onClick={onExit}><MessageSquare aria-hidden="true" className="mr-1.5 h-4 w-4" />Рабочий чат</Button>
    </header>
    <SetupChatMessages activity={state?.activity ?? []} notice={notice} />
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

    {!state?.started && !gathering && <SetupStep title="С какой компании начнём?" icon={MessageSquare}>
      <p className="text-muted-foreground">Вставьте ссылку на карточку, сайт или соцсеть.</p>
      {canChange && <Button size="sm" variant="ghost" disabled={busy}
        onClick={() => void send({ action: 'start' })}>Начать с данных кабинета</Button>}
    </SetupStep>}

    {state && (completedSources.length > 0 || state.started && !gathering) && <SetupStep
      title={completedSources.length ? 'Источники' : 'Данные компании'} icon={Building2}>
      {collected > 0 && <p>Прочитано · {collected}{photosFound > 0 && ` · Фото для проверки · ${photosFound}`}</p>}
      {completedSources.filter(source => source.status !== 'ready').map(source => (
        <div key={source.key} className="flex flex-wrap items-center gap-2">
          <p className="max-w-prose text-muted-foreground">{source.note || 'Источник пока недоступен.'}</p>
          {canChange && source.status === 'unavailable' && <Button size="sm" variant="outline" disabled={busy || reading}
            onClick={() => void send({ action: 'retry', key: source.key })}>Повторить сбор</Button>}
        </div>
      ))}
      <SetupDisclosure title="Данные и источники" compact
        meta={contactsToReview ? 'Контакты к проверке · ' + contactsToReview : undefined}>
        <SetupSources state={state} busy={busy} send={send} />
        <SetupLink businessId={state.business_id} path="/dashboard/profile">Профиль компании</SetupLink>
      </SetupDisclosure>
      {sourcesToRead && !gathering && canChange && <Button size="sm" disabled={busy}
        onClick={() => void send({ action: 'read' })}>Собрать данные</Button>}
      {needsSource && <p className="text-muted-foreground">Повторите чтение или пришлите другую ссылку. Можно добавить услуги прямо в чат.</p>}
    </SetupStep>}

    {gathering && <SetupStep title="Собираем данные" icon={Building2} working>
      {state?.sources.filter(source => source.status === 'queued' || source.status === 'running').map(source => (
        <p key={source.key} className="text-muted-foreground">{platforms[source.provider] || (source.kind === 'website' ? 'Сайт' : source.provider)}</p>
      ))}
    </SetupStep>}

    {showAnalysis && preparing && <SetupStep title="Разбираем услуги и поисковые запросы" icon={ListChecks} working />}
    {showAnalysis && !preparing && !analysisDone && <SetupStep
      title={draftFailed ? 'Не удалось подготовить услуги' : 'Подготовим услуги и поисковые запросы'} icon={ListChecks}>
      {!draftFailed && !state?.activity_type && <p className="text-muted-foreground">Уточните вид деятельности или напишите «Услуга: название».</p>}
      {canChange && <Button size="sm" disabled={busy} onClick={() => void send({ action: draftFailed ? 'draft_retry' : 'prepare' })}>
        {draftFailed ? 'Повторить подготовку' : 'Подготовить услуги и SEO'}
      </Button>}
    </SetupStep>}

    {state && analysisDone && <>
      <SetupStep title="Услуги и SEO" icon={ListChecks}>
        {state.services.length > 0 || queryCount > 0
          ? <p>Услуги · {state.services.length} / Запросы · {queryCount}</p>
          : <p className="text-muted-foreground">Услуги не удалось подтвердить. Пришлите прайс или добавьте услугу в чате.</p>}
        {state.services.length > 0 && <SetupDisclosure title="Услуги и правки" count={state.services.length} compact>
          <ServiceProposals key={state.business_id} items={state.services} send={canChange ? send : undefined}
            disabled={busy} error={error} />
          <SetupLink businessId={state.business_id} path="/dashboard/card?tab=services">Каталог услуг</SetupLink>
        </SetupDisclosure>}
        {queryCount > 0 && <SetupDisclosure title="Поисковые запросы" compact>
          <SetupLink businessId={state.business_id} path="/dashboard/card?tab=keywords">Семантическое ядро</SetupLink>
          <Keywords state={state} />
        </SetupDisclosure>}
        {state.facts.length > 0 && <SetupDisclosure title="Факты для контента" count={state.facts.length} icon={FileText} compact>
          <ul className="divide-y text-sm">{state.facts.map(fact => <li key={fact.key} className="space-y-1 py-2">
            <p>{fact.text}</p><div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <a className="underline" href={fact.url} target="_blank" rel="noreferrer">Источник{fact.observed_at && ' · ' + fact.observed_at.slice(0, 10)}</a>
              {fact.accepted ? <span>Сохранено</span> : canChange && <Button size="sm" variant="outline" disabled={busy}
                onClick={() => void send({ action: 'fact', key: fact.key })}>Подтвердить факт</Button>}
            </div>
          </li>)}</ul>
          <SetupLink businessId={state.business_id} path="/dashboard/profile?section=knowledge">Факты о компании</SetupLink>
        </SetupDisclosure>}
        {state.comparisons.length > 0 && <SetupDisclosure title="Конкуренты" count={state.comparisons.length} icon={MapPin} compact>
          <Comparisons rows={state.comparisons} />
          <SetupLink businessId={state.business_id} path="/dashboard/card?tab=competitors">Все конкуренты</SetupLink>
        </SetupDisclosure>}
      </SetupStep>

      {checkingPhotos ? <SetupStep title="Проверяем фото…" icon={Images} working /> :
        <div className="max-w-full rounded-2xl border bg-card px-1">
          <PhotoCheck key={state.business_id} report={state.photo_report} businessId={state.business_id}
            busy={busy} send={canChange ? send : undefined} />
        </div>}

      {canReview && <SetupStep title={saved ? 'Кабинет сохранён' : 'Черновик кабинета готов'} icon={FileText}>
        {!saved && canChange && <p className="text-muted-foreground">Проверьте контакты, правки услуг и факты перед сохранением.</p>}
        <div className="flex flex-wrap items-start gap-2">
          {state.report_ready && <SetupReportDownload key={state.business_id} businessId={state.business_id} name={state.profile.name} />}
          {saved ? <Button size="sm" variant="outline" asChild>
            <Link to={companyUrl('/dashboard/profile', state.business_id)}>Открыть кабинет</Link>
          </Button> : canChange && <Button size="sm" disabled={busy}
            onClick={() => void send({ action: 'save' })}>Сохранить кабинет</Button>}
        </div>
      </SetupStep>}
      {isStaff && saved && <Handoff key={state.business_id} state={state} />}
    </>}
  </section>;
}
