import {
  ArrowUpRight, Building2, Check, ChevronDown, Download, FileText, Globe, Images,
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
import { SetupFollowThrough } from './SetupFollowThrough';

const fieldNames: Record<string, string> = {
  name: 'Название', city: 'Город', address: 'Адрес', website: 'Сайт', contact_phone: 'Телефон', contact_email: 'Email',
};
const platforms: Record<string, string> = {
  yandex: 'Яндекс Карты', '2gis': '2ГИС', google: 'Google Maps', telegram: 'Telegram', vk: 'ВКонтакте',
  whatsapp: 'WhatsApp', instagram: 'Instagram', facebook: 'Facebook', youtube: 'YouTube', max: 'MAX',
};
const statuses: Record<string, string> = {
  added: 'Добавлен', queued: 'В очереди', running: 'Читаем', ready: 'Прочитан',
  unavailable: 'Не удалось прочитать', link_only: 'Есть ссылка',
};

const companyUrl = (path: string, businessId: string) => path + (path.includes('?') ? '&' : '?') + 'business_id=' + encodeURIComponent(businessId);

function SiteAudit({ audit, onCheck, busy }: { audit?: WebsiteAudit; onCheck?: () => void; busy: boolean }) {
  if (audit?.status === 'queued' || audit?.status === 'running') return null;
  if (audit?.status === 'ready') {
    return <div className="space-y-3 border-t pt-2">
      <p className="text-xs text-muted-foreground">Проверка от {new Date(audit.checked_at).toLocaleDateString('ru-RU')}</p>
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
    </div>;
  }
  return !audit && onCheck
    ? <Button size="sm" variant="outline" disabled={busy} onClick={onCheck}>Провести SEO-аудит сайта</Button>
    : null;
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
  const library = companyUrl('/dashboard/content?section=media', businessId);
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
  return <div className="space-y-2 text-sm">
      {ready?.note && <p className="text-muted-foreground">{ready.note}</p>}
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
        {send && !pending && !report && <Button size="sm" variant="outline" disabled={busy}
          onClick={() => void send({ action: 'photo_check' })}>Проверить фото</Button>}
      </div>
      {copyStatus && <p role="status">{copyStatus}</p>}
    </div>;
}

function SetupDisclosure({ title, icon: Icon, children, count, meta, compact, open, className, id, working }: {
  title: string;
  icon?: LucideIcon;
  children: ReactNode;
  count?: number;
  meta?: string;
  compact?: boolean;
  open?: boolean;
  className?: string;
  id?: string;
  working?: boolean;
}) {
  return <details id={id} open={open} className={cn('[&[open]>summary>svg:last-child]:rotate-180', !compact && 'rounded-lg border', className)}>
    <summary className={cn('flex cursor-pointer list-none items-center gap-2.5 rounded-md py-2 text-sm font-medium hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden',
      Icon ? (id ? 'min-h-10 px-3 py-1.5' : 'min-h-11 px-3') : 'min-h-10 px-2')}>
      {working ? <Loader2 aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground motion-safe:animate-spin" />
        : Icon && <Icon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />}
      <span className="min-w-0 break-words">{title}</span>
      {count !== undefined && <span className="rounded-md bg-muted px-1.5 py-0.5 text-xs tabular-nums text-muted-foreground">{count}</span>}
      {meta && <span role={id ? 'status' : undefined} className="ml-auto min-w-0 text-right text-xs font-normal tabular-nums text-muted-foreground">{meta}</span>}
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
      <Button size="sm" disabled={pending || !email.trim()}>Подготовить доступ</Button>
    </form>
    {error && <p className="mt-2 text-sm text-destructive" role="alert">{error}</p>}
    {result && <div className="mt-2 space-y-2">
      <p role="status">{result.already_signed_in ? 'Вы уже в своём аккаунте.'
        : result.invite_url ? 'По этой ссылке владелец задаст пароль и сразу попадёт в кабинет.'
          : 'Ссылка на кабинет владельца.'}</p>
      {!result.already_signed_in && link && <div className="flex flex-wrap gap-2">
        <Input readOnly value={link} className="min-w-0 flex-1" aria-label="Ссылка для владельца" onFocus={event => event.target.select()} />
        <Button size="sm" variant="outline" onClick={() => void navigator.clipboard?.writeText(link).then(() => setCopied(true)).catch(() => setError('Выделите ссылку и скопируйте её вручную.'))}>{copied ? 'Ссылка скопирована' : 'Скопировать ссылку'}</Button>
      </div>}
    </div>}
  </SetupDisclosure>;
}

function SetupResultRow({ id, title, icon: Icon, summary, working, complete, actions, children }: {
  id: string; title: string; icon: LucideIcon; summary: string; working?: boolean; complete?: boolean; actions?: ReactNode; children?: ReactNode;
}) {
  return <div>
    {children ? <SetupDisclosure id={id} title={title} icon={complete ? Check : Icon} compact working={working} meta={summary}>
      {children}
    </SetupDisclosure> : <div className="flex min-h-10 items-center gap-2.5 px-3 py-1.5 text-sm">
      {working ? <Loader2 aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground motion-safe:animate-spin" />
        : <Icon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />}
      <span className="font-medium">{title}</span>
      <span role="status" className="ml-auto min-w-0 text-right text-xs text-muted-foreground">{summary}</span>
    </div>}
    {actions && <div className="space-y-1 px-3 pb-2 text-xs text-muted-foreground">{actions}</div>}
  </div>;
}

const progressReplies = new Set([
  'Ссылки появились в списке источников.',
  'Ссылки появились в списке источников. Ход чтения виден рядом с чатом.',
  'Проверьте статус чтения в списке источников.',
  'Подготовка черновика запущена.',
  'Чтение добавленных источников запущено.',
  'Проверка фото запущена.',
  'SEO-проверка сайта запущена.',
]);

function SetupChatMessages({ activity, notice }: { activity: Setup['activity']; notice: string }) {
  const message = notice.replace(/^Подготовка началась\. Данные компании уже в карточке\.\s*/, '');
  const reply = progressReplies.has(message) || message === activity.at(-1)?.reply ? '' : message;
  if (!activity.length && !reply) return null;
  return <div role="log" aria-label="Сообщения настройки" className="mx-auto max-w-4xl space-y-3">
    {activity.map(item => <div key={item.at} className="flex flex-col gap-2">
      <p className="max-w-[90%] self-end whitespace-pre-wrap break-words rounded-2xl bg-primary px-3 py-2 text-sm text-primary-foreground">
        <span className="sr-only">Вы. </span>{item.message}
      </p>
      {item.reply && !progressReplies.has(item.reply) && <p className="max-w-[90%] self-start whitespace-pre-wrap break-words rounded-2xl border bg-card px-3 py-2 text-sm">
        <span className="sr-only">LocalOS. </span>{item.reply}
      </p>}
    </div>)}
    {reply && <div className="flex"><p className="max-w-[90%] rounded-2xl border bg-card px-3 py-2 text-sm">{reply}</p></div>}
  </div>;
}

const countInRussian = new Intl.PluralRules('ru');
function counted(count: number, forms: { one: string; few: string; many: string }) {
  const form = countInRussian.select(count);
  return count + ' ' + (form === 'one' || form === 'few' ? forms[form] : forms.many);
}

function sourceName(source: Source) {
  if (source.kind === 'website') {
    try { return new URL(source.url).hostname; }
    catch { return 'Сайт'; }
  }
  return platforms[source.provider] || source.provider;
}

function pending(status?: string) {
  return status === 'queued' || status === 'running';
}

function sourceFailed(source: Source) {
  return source.status === 'unavailable' || source.website_audit?.status === 'unavailable';
}

function SetupProfile({ state }: { state: Setup }) {
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
    {state.profile_choices.length > 0 && <ul className="divide-y border-t text-sm">{state.profile_choices.map(item => <li key={item.key} className="space-y-1 py-2">
      <p><strong>{fieldNames[item.field] || item.field}</strong> · {item.text}</p>
      <p className="text-xs text-muted-foreground">Сейчас · {state.profile[item.field] || 'не заполнено'}</p>
      <div className="flex flex-wrap items-center gap-2">
        {item.url && <a className="text-xs underline" href={item.url} target="_blank" rel="noreferrer">Источник</a>}
      </div>
    </li>)}</ul>}
  </>;
}

function SetupSources({ sources, state, busy, send }: { sources: Source[]; state: Setup; busy: boolean; send: (action: Action) => Promise<boolean> }) {
  return <ul className="divide-y">
    {sources.map(source => {
      const name = sourceName(source);
      const discoverySource = state.sources.find(item => item.url === source.found_on);
      return <li key={source.key} className="space-y-1.5 py-1.5 text-sm">
        <div className="flex items-center gap-1.5">
          <div className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
            <a href={source.url} target="_blank" rel="noreferrer" className="min-w-0 break-words font-medium underline underline-offset-4">
              {source.competitor ? 'Конкурент · ' : ''}{name}
            </a>
            <span className="text-xs text-muted-foreground">{statuses[source.status] || source.status}
              {source.service_count > 0 && ' · Услуг: ' + source.service_count}
              {!!source.photo_candidate_count && ' · Фото: ' + source.photo_candidate_count}
              {source.found_on && (discoverySource?.kind === 'map' ? ' · Найдено в карточке' : ' · Найдено на сайте')}
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
  </ul>;
}

function SourceProblems({ sources, canEdit, busy, send }: {
  sources: Source[]; canEdit: boolean; busy: boolean; send: (action: Action) => Promise<boolean>;
}) {
  const failures = sources.filter(sourceFailed);
  return failures.map(source => {
    const auditFailed = source.status !== 'unavailable' && source.website_audit?.status === 'unavailable';
    const note = auditFailed && source.website_audit?.status === 'unavailable' ? source.website_audit.note : source.note;
    return <div key={source.key} className="flex flex-wrap items-center gap-x-2">
      <p>{note || (auditFailed ? 'Не удалось проверить сайт.' : `Не удалось прочитать: ${sourceName(source)}.`)}</p>
      {canEdit && <Button size="sm" variant="outline" disabled={busy}
        onClick={() => void send({ action: auditFailed ? 'website_audit' : 'retry', key: source.key })}>
        {auditFailed ? 'Повторить проверку сайта' : 'Повторить сбор'}
      </Button>}
    </div>;
  });
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
  const { state, send, available, loading, canEdit, error, notice, busy, saving, saveError, reading, pendingSources } = setup;
  if (loading || (available === undefined && !error)) return <p role="status">Открываем чат…</p>;
  if (available !== true) return <div className="space-y-3"><p role="status">{error || 'Настройка для этой компании недоступна.'}</p>
    {error && <Button variant="outline" onClick={() => void setup.refresh()}>Повторить</Button>}
    <Button variant="ghost" onClick={onExit}>Рабочий чат</Button></div>;

  const gathering = reading || pendingSources;
  const hasProgress = state?.started || state?.sources.length || state?.activity.length || state?.seo_prepared;
  if (!hasProgress && !gathering) return error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null;

  const sources = state?.sources ?? [];
  const maps = sources.filter(source => source.kind === 'map');
  const sites = sources.filter(source => source.kind === 'website');
  const socials = sources.filter(source => source.kind === 'social');
  const sourcesToRead = sources.some(source => source.status === 'added');
  const mapsReading = maps.some(source => pending(source.status));
  const sitesReading = sites.some(source => pending(source.status));
  const checkingSite = sites.some(source => pending(source.website_audit?.status));
  const socialsReading = socials.some(source => pending(source.status));
  const readyMaps = maps.filter(source => source.status === 'ready' && !source.competitor);
  const mapNames = [...new Set(readyMaps.map(sourceName))].join(', ');
  const socialNames = [...new Set(socials.map(sourceName))].join(', ');
  const pages = sites.flatMap(source => source.website_audit?.status === 'ready' ? source.website_audit.pages : []);
  const fixes = pages.reduce((sum, page) => sum + page.findings.length, 0);
  const siteFailed = sites.some(sourceFailed);

  const needsSeo = !state?.seo_prepared || state.seo_dirty;
  const preparing = pending(state?.draft_status) && !gathering && !sourcesToRead;
  const draftFailed = state?.draft_status === 'failed';
  const needsSource = state?.draft_status === 'needs_source';
  const showServices = state?.seo_prepared || (state?.started && !gathering && !sourcesToRead && !needsSource);
  const analysisDone = Boolean(showServices && !needsSeo && !state?.draft_status && !gathering && !sourcesToRead);
  const canChange = state?.can_edit ?? canEdit;
  const report = state?.photo_report;
  const checkingPhotos = pending(report?.status);
  const photosFound = readyMaps.reduce((sum, source) => sum + (source.photo_candidate_count ?? 0), 0);
  const reviewPhotos = report?.status === 'ready' ? report.review.length : photosFound;
  const showPhotos = !!report || photosFound > 0 || analysisDone;
  const queryCount = state ? new Set([...state.category_keywords, ...state.services.flatMap(item => item.keywords)]
    .map(keyword => keyword.text.trim().toLowerCase()).filter(Boolean)).size : 0;
  const contactsToReview = state?.profile_choices.filter(item => item.text !== state.profile[item.field]).length ?? 0;
  const canReview = analysisDone && !checkingPhotos && !checkingSite;
  const saved = Boolean(state?.saved);
  const working = gathering || preparing || checkingPhotos || checkingSite;
  const showGathering = gathering && !mapsReading && !sitesReading && !socialsReading;
  const hasIssues = !!(needsSource || draftFailed || siteFailed || report?.status === 'unavailable'
    || sources.some(source => source.status === 'unavailable'));

  return <section className="mx-auto max-w-3xl space-y-3" aria-labelledby="initial-setup-title">
    <header className="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
      <div className="min-w-0">
        <h2 id="initial-setup-title" className="text-sm font-semibold">Первичная настройка компании</h2>
        {state?.profile.name && <p className="break-words text-xs text-muted-foreground">{state.profile.name}</p>}
      </div>
      <Button size="sm" variant="ghost" onClick={onExit}><MessageSquare aria-hidden="true" className="mr-1.5 h-4 w-4" />Рабочий чат</Button>
    </header>
    <SetupChatMessages activity={state?.activity ?? []} notice={notice} />
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

    <article aria-labelledby="setup-result-title" className="w-full min-w-0 rounded-2xl border bg-card px-2.5 py-2 text-sm sm:px-3.5">
      <header className="flex items-center gap-2.5 px-2.5 pb-2">
        <LocalOSChatAvatar />
        <h3 id="setup-result-title" className="min-w-0 font-semibold">
          {working ? 'Готовлю кабинет' : saved ? 'Кабинет сохранён' : canReview ? 'Черновик готов к проверке'
            : hasIssues ? 'Нужно уточнить данные' : 'Результаты настройки'}
        </h3>
      </header>
      {showGathering && <p role="status" className="flex items-center gap-2 px-3 py-2 text-muted-foreground">
        <Loader2 aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin" />Собираю данные…
      </p>}
      {state && <div className="divide-y border-t">
        {maps.length > 0 && <SetupResultRow id="setup-result-maps" title="Карты" icon={MapPin} working={mapsReading}
          complete={readyMaps.length > 0 && !maps.some(sourceFailed)}
          summary={mapsReading ? 'Читаю карточки…' : mapNames ? `${mapNames} · прочитано` : (maps.some(sourceFailed)
            ? 'Карточка недоступна' : 'Карточки добавлены')}
          actions={maps.some(sourceFailed) && <SourceProblems sources={maps} busy={busy || reading} canEdit={canChange} send={send} />}>
          <SetupSources sources={maps} state={state} busy={busy} send={send} />
        </SetupResultRow>}
        {sites.length > 0 && <SetupResultRow id="setup-result-site" title="Сайт" icon={Globe} working={sitesReading || checkingSite}
          complete={pages.length > 0 && !siteFailed}
          summary={sitesReading || checkingSite ? 'Проверяю страницы…'
            : pages.length > 0 ? [
              counted(pages.length, { one: 'страница', few: 'страницы', many: 'страниц' }),
              fixes ? counted(fixes, { one: 'замечание', few: 'замечания', many: 'замечаний' }) : 'без замечаний',
            ].join(' · ') : siteFailed ? 'Не удалось проверить' : 'Требуется SEO-проверка'}
          actions={siteFailed && <SourceProblems sources={sites} busy={busy || reading} canEdit={canChange} send={send} />}>
          <SetupSources sources={sites} state={state} busy={busy} send={send} />
        </SetupResultRow>}
        {socials.length > 0 && <SetupResultRow id="setup-result-socials" title="Соцсети" icon={MessageSquare} working={socialsReading}
          complete={!socials.some(source => source.status === 'added' || sourceFailed(source))}
          summary={socialsReading ? 'Проверяю ссылки…' : socialNames}
          actions={socials.some(sourceFailed) && <SourceProblems sources={socials} busy={busy || reading} canEdit={canChange} send={send} />}>
          <SetupSources sources={socials} state={state} busy={busy} send={send} />
        </SetupResultRow>}
        <SetupResultRow id="setup-result-profile" title="Данные компании" icon={Building2}
          summary={contactsToReview ? 'Есть данные для проверки' : state.profile.address ? 'Профиль и адрес' : 'Профиль'}>
          <SetupProfile state={state} />
          <SetupLink businessId={state.business_id} path="/dashboard/profile">Профиль компании</SetupLink>
        </SetupResultRow>
        {showServices && <SetupResultRow id="setup-result-services" title="Услуги" icon={ListChecks} working={preparing}
          complete={!needsSeo && state.services.length > 0}
          summary={preparing ? 'Готовлю предложения…' : draftFailed ? 'Не удалось подготовить' : needsSeo ? 'Нужна подготовка'
            : state.services.length ? counted(state.services.length, { one: 'услуга', few: 'услуги', many: 'услуг' }) + ' с предложениями'
              : 'Пришлите прайс или добавьте услуги'}
          actions={!preparing && !gathering && (needsSeo || draftFailed) && canChange
            ? <Button size="sm" variant="outline" disabled={busy} onClick={() => void send({ action: draftFailed ? 'draft_retry' : 'prepare' })}>
                {draftFailed ? 'Повторить подготовку' : 'Подготовить услуги и запросы'}
              </Button> : undefined}>
          {state.seo_prepared && state.services.length > 0 ? <>
            <SetupLink businessId={state.business_id} path="/dashboard/card?tab=services">Каталог услуг</SetupLink>
            <ServiceProposals key={state.business_id} items={state.services} />
          </> : undefined}
        </SetupResultRow>}
        {state.seo_prepared && queryCount > 0 && <SetupResultRow id="setup-result-keywords" title="Поисковые запросы" icon={Search}
          complete={!needsSeo} summary={counted(queryCount, { one: 'запрос', few: 'запроса', many: 'запросов' })}>
          <SetupLink businessId={state.business_id} path="/dashboard/card?tab=keywords">Семантическое ядро</SetupLink>
          <Keywords state={state} />
        </SetupResultRow>}
        {showPhotos && <SetupResultRow id="setup-result-photos" title="Фото для карт" icon={Images} working={checkingPhotos}
          complete={report?.status === 'ready' && !reviewPhotos && !report.missing.length}
          summary={checkingPhotos ? photosFound ? `Проверяю ${photosFound} фото…` : 'Проверяю фото…'
            : report?.status === 'unavailable' ? 'Нужна повторная проверка'
            : reviewPhotos ? `${reviewPhotos} фото на проверку`
            : report?.status === 'ready' ? `${report.library_count} фото в медиатеке` : 'Нужна проверка'}
          actions={report?.status === 'ready' && report.missing.length ? <p>Доснять: {report.missing.map(item => item.label.toLowerCase()).join(', ')}.</p>
            : report?.status === 'unavailable' ? <>
              {report.note && <p>{report.note}</p>}
              {canChange && <Button size="sm" variant="outline" disabled={busy}
                onClick={() => void send({ action: 'photo_check' })}>Повторить проверку фото</Button>}
            </> : undefined}>
          <PhotoCheck key={state.business_id} report={report} businessId={state.business_id} busy={busy} send={canChange ? send : undefined} />
        </SetupResultRow>}
        {state.facts.length > 0 && <SetupResultRow id="setup-result-facts" title="Факты для контента" icon={FileText}
          summary={counted(state.facts.length, { one: 'факт', few: 'факта', many: 'фактов' })}>
          <ul className="divide-y text-sm">{state.facts.map(fact => <li key={fact.key} className="space-y-1 py-2">
            <p>{fact.text}</p><div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <a className="underline" href={fact.url} target="_blank" rel="noreferrer">Источник{fact.observed_at && ' · ' + fact.observed_at.slice(0, 10)}</a>
              {fact.accepted && <span>Сохранено</span>}
            </div>
          </li>)}</ul>
          <SetupLink businessId={state.business_id} path="/dashboard/profile?section=knowledge">Факты о компании</SetupLink>
        </SetupResultRow>}
        {state.comparisons.length > 0 && <SetupResultRow id="setup-result-competitors" title="Конкуренты" icon={Search}
          summary={counted(state.comparisons.length, { one: 'сравнение', few: 'сравнения', many: 'сравнений' })}>
          <Comparisons rows={state.comparisons} />
          <SetupLink businessId={state.business_id} path="/dashboard/card?tab=competitors">Все конкуренты</SetupLink>
        </SetupResultRow>}
      </div>}
      {state && (canReview || needsSource || (sourcesToRead && !gathering) || saveError) && <footer className="space-y-2 border-t px-2.5 pt-2">
        {needsSource && !gathering && <p className="text-muted-foreground">Пришлите другую ссылку или добавьте услуги в чат.</p>}
        {sourcesToRead && !gathering && canChange && <Button size="sm" disabled={busy}
          onClick={() => void send({ action: 'read' })}>Собрать данные</Button>}
        {saveError && <p role="alert" className="text-xs text-destructive">{saveError}</p>}
        {canReview && <>
          {(saved || canChange) && !saveError && <p role="status" className="text-xs text-muted-foreground">
            {saved ? 'Кабинет сохранён.' : saving ? 'Ждём подтверждения от LocalOS…' : 'Собранные данные, услуги и факты сохранятся в LocalOS.'}
          </p>}
          <div className="flex flex-wrap items-start gap-2">
            {saved ? <Button size="sm" asChild>
              <Link to={companyUrl('/dashboard/profile', state.business_id)}>Открыть кабинет</Link>
            </Button> : canChange && <Button size="sm" className={cn('min-w-44', saving && 'disabled:opacity-100')} disabled={busy} aria-busy={saving}
                onClick={() => void send({ action: 'save' })}>
                {saving && <Loader2 aria-hidden="true" className="motion-safe:animate-spin" />}
                {saving ? 'Сохраняем кабинет…' : 'Сохранить кабинет'}
              </Button>}
            {state.report_ready && <SetupReportDownload key={state.business_id} businessId={state.business_id} name={state.profile.name} />}
          </div>
          {isStaff && saved && (state.provisional || !state.viewer_is_owner) && <Handoff key={state.business_id} state={state} />}
          {saved && canChange && <SetupFollowThrough key={state.business_id} businessId={state.business_id} />}
        </>}
      </footer>}
    </article>
  </section>;
}
