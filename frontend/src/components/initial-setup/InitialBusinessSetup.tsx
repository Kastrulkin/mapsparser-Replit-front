import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/services/api';
import { ServiceProposals, type ServiceProposal } from './ServiceProposals';

type Keyword = { text: string; views: number | null; source: string; dated: string };
type WebsiteAudit =
  | { status: 'queued' | 'running' | 'unavailable'; note?: string }
  | { status: 'ready'; checked_at: string; pages: {
      url: string;
      findings: { rule: string; priority: 'fix' | 'review'; title: string; fix: string }[];
    }[] };
type PhotoReport =
  | { status: 'queued' | 'running' | 'unavailable'; note?: string }
  | { status: 'ready'; checked_at: string; library_categories: string[]; library_count: number;
      missing: { label: string; tip: string }[];
      shortlist: { key: string; label: string; source_url: string; image_url: string }[];
      review: { key: string; image_url: string; card_url: string; provider: string }[];
      sources: { url: string; provider: string; status: 'sample' | 'unavailable'; count: number }[];
      cover?: string | null; rejected: number; note?: string };
type Source = {
  key: string;
  url: string;
  kind: 'website' | 'map' | 'social';
  provider: string;
  status: string;
  note?: string;
  found_on?: string;
  competitor: boolean;
  service_count: number;
  website_audit?: WebsiteAudit;
};
type Finding = { key: string; text: string; url: string; accepted?: boolean; observed_at?: string };
type Comparison = {
  url: string;
  name: string;
  platform: string;
  checked_at: string;
  our_checked_at: string;
  ours?: { rating?: string; reviews?: string };
  theirs?: { rating?: string; reviews?: string };
  our_services: string[];
  their_services: string[];
};
type Setup = {
  business_id: string;
  revision: number;
  can_edit: boolean;
  origin: string;
  provisional: boolean;
  profile: Record<string, string | null>;
  sources: Source[];
  services: ServiceProposal[];
  seo_dirty: boolean;
  seo_prepared: boolean;
  saved: boolean;
  started: boolean;
  activity_type?: string;
  category_keywords: Keyword[];
  photo_report?: PhotoReport | null;
  facts: Finding[];
  profile_choices: (Finding & { field: string })[];
  comparisons: Comparison[];
  activity: { message: string; reply: string; at: string }[];
};
type SetupResponse = { available: boolean; can_edit?: boolean; setup?: Setup | null; message?: string };
type Action = { action: string; key?: string; message?: string; name?: string; description?: string; text?: string; category?: string };
type Invite = { email: string; invite_url?: string; login_path?: string; existing_account: boolean };

const fieldNames: Record<string, string> = {
  name: 'Название', city: 'Город', address: 'Адрес', website: 'Сайт', contact_phone: 'Телефон', contact_email: 'Email',
};
const platforms: Record<string, string> = { yandex: 'Яндекс Карты', '2gis': '2ГИС', google: 'Google Maps', telegram: 'Telegram', vk: 'ВКонтакте' };
const statuses: Record<string, string> = {
  added: 'Добавлен', queued: 'В очереди', running: 'Читаем', ready: 'Прочитан',
  unavailable: 'Не удалось прочитать', link_only: 'Есть ссылка',
};

const setupUrl = (id: string) => '/operator/initial-setup/' + encodeURIComponent(id);
const companyUrl = (path: string, businessId: string) => path + (path.includes('?') ? '&' : '?') + 'business_id=' + encodeURIComponent(businessId);

function visibleError(error: unknown) {
  if (error instanceof Error && error.message) return error.message;
  if (error && typeof error === 'object' && 'response' in error) {
    const response = error.response;
    if (response && typeof response === 'object' && 'data' in response) {
      const data = response.data;
      if (data && typeof data === 'object' && 'error' in data && typeof data.error === 'string') return data.error;
    }
  }
  return 'Не удалось загрузить или сохранить настройку. Попробуйте ещё раз.';
}

export function useInitialBusinessSetup(businessId: string | null, active: boolean) {
  const [data, setData] = useState<SetupResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const context = active ? businessId : null;
  const generation = useRef(0);
  const mutation = useRef(0);
  const scope = useRef<string | null>(null);
  const inFlight = useRef(false);
  scope.current = context;
  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (!context) return;
    const issued = ++generation.current;
    try {
      const response = await api.get(setupUrl(context), { signal });
      if (scope.current === context && generation.current === issued && !signal?.aborted) {
        setData(response.data);
        setError('');
      }
    } catch (err) {
      if (scope.current === context && generation.current === issued && !signal?.aborted) setError(visibleError(err));
    }
  }, [context]);
  useEffect(() => {
    mutation.current += 1;
    setData(null);
    setNotice('');
    setError('');
    setBusy(false);
    inFlight.current = false;
    if (!context) return;
    const controller = new AbortController();
    setLoading(true);
    void refresh(controller.signal).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [context, refresh]);

  const state = context && data?.setup?.business_id === context ? data.setup : null;
  const reading = state?.sources.some(source => source.status === 'queued' || source.status === 'running') ?? false;
  const polling = reading || state?.photo_report?.status === 'queued' || state?.photo_report?.status === 'running'
    || state?.sources.some(source => source.website_audit?.status === 'queued' || source.website_audit?.status === 'running');
  useEffect(() => {
    if (!context || !polling || busy) return;
    const controller = new AbortController();
    const interval = window.setInterval(() => {
      if (!inFlight.current) void refresh(controller.signal);
    }, 2500);
    return () => { window.clearInterval(interval); controller.abort(); };
  }, [context, polling, busy, refresh]);

  const send = async (action: Action) => {
    if (!context || inFlight.current) return false;
    inFlight.current = true;
    generation.current += 1;
    const issued = ++mutation.current;
    const isCurrent = () => scope.current === context && mutation.current === issued;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await api.post(setupUrl(context), { ...action, revision: state?.revision });
      if (!isCurrent()) return false;
      setData(result.data);
      setNotice(result.data.message || '');
      return result.data.available;
    } catch (err) {
      if (!isCurrent()) return false;
      await refresh();
      if (isCurrent()) setError(visibleError(err));
      return false;
    } finally {
      if (isCurrent()) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  };
  return { state, available: data?.available, canEdit: state?.can_edit ?? data?.can_edit ?? false, error, busy, loading, notice, reading, send, refresh };
}

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
    const lines = [
      'Фотографии для карточек',
      `В медиатеке ${report.library_count} фото.`,
      ...(report.library_categories.length ? ['Категории в медиатеке — ' + report.library_categories.join(', ') + '.'] : []),
      ...(report.shortlist.length ? ['Подборка с карт', ...report.shortlist.map(photo => `• ${photo.label} — ${photo.image_url}`)] : []),
      ...(report.cover ? ['Кандидат для обложки — ' + report.cover.toLowerCase() + '.'] : []),
      ...(report.missing.length ? ['Что доснять или подтвердить', ...report.missing.map(item => '• ' + item.tip)] : []),
      ...(report.note ? [report.note] : []),
      ...report.sources.map(source => (platforms[source.provider] || source.provider) + ' — '
        + (source.status === 'sample' ? 'из галереи доступна выборка' : 'галерея не подтверждена') + '. ' + source.url),
      'Медиатека LocalOS — ' + new URL(library, window.location.origin).href,
      'Сохраните согласованные снимки на Яндекс Диске или Google Drive. Подключите папку в разделе «Материалы с Диска» в медиатеке.',
      'Публикация на картах проводится после согласования.',
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopyStatus('Отчёт скопирован.');
    } catch {
      setCopyStatus('Не удалось скопировать автоматически. Выделите и скопируйте текст отчёта.');
    }
  };
  return <details className="rounded-lg border p-3">
    <summary className="cursor-pointer font-medium">Фото для карт и отчёт
      {pending ? ' · Проверяем' : report?.status === 'ready' ? ' · Готов' : ''}
    </summary>
    <div className="mt-2 space-y-3 text-sm">
      {pending && <p role="status">Проверяем снимки с карт и из медиатеки.</p>}
      {!report && <p>Подберём ссылки на фото с карт и покажем, что стоит доснять.</p>}
      {report?.note && <p className="text-muted-foreground">{report.note}</p>}
      {report?.status === 'ready' && <>
        <p>В медиатеке {report.library_count} фото.{report.library_categories.length > 0
          && ' Подтверждено — ' + report.library_categories.join(', ') + '.'}</p>
        {report.shortlist.length > 0 && <div>
          <h3 className="font-medium">Подборка с карт</h3>
          <ul>{report.shortlist.map(photo => <li key={photo.key}>
            <a className="underline" href={photo.image_url} target="_blank" rel="noreferrer">{photo.label}</a>
            {' · '}
            <a className="underline" href={photo.source_url} target="_blank" rel="noreferrer">Карточка-источник</a>
          </li>)}</ul>
        </div>}
        {report.cover && <p>Кандидат для обложки — {report.cover.toLowerCase()}.</p>}
        {report.missing.length > 0 && <div>
          <h3 className="font-medium">Что доснять или подтвердить</h3>
          <ul className="list-disc space-y-1 pl-5">{report.missing.map(item => <li key={item.label}>{item.tip}</li>)}</ul>
        </div>}
        {report.sources.length > 0 && <div>
          <h3 className="font-medium">Проверенные площадки</h3>
          <ul>{report.sources.map(source => <li key={source.url}>
            <a className="underline" href={source.url} target="_blank" rel="noreferrer">{platforms[source.provider] || source.provider}</a>
            {' · '}{source.status === 'sample' ? `Снимков в выборке: ${source.count}` : 'Галерея не подтверждена'}
          </li>)}</ul>
        </div>}
        {report.rejected > 0 && <p className="text-muted-foreground">Не прошли проверку качества или не открылись: {report.rejected}.</p>}
        {report.review.length > 0 && <details>
          <summary className="cursor-pointer">Уточнить, что показано на фото · {report.review.length}</summary>
          <ul className="mt-2">{report.review.map(item => <PhotoChoice key={item.key} item={item} send={send} busy={busy} />)}</ul>
        </details>}
        <p className="text-muted-foreground">После согласования сохраните снимки на Яндекс Диске или Google Drive и подключите папку в медиатеке. Оригиналы останутся в облаке компании.</p>
      </>}
      <div className="flex flex-wrap items-center gap-2">
        <Link className="underline" to={library}>Открыть медиатеку</Link>
        {report?.status === 'ready' && <Button size="sm" variant="outline" onClick={() => void copyReport()}>Скопировать отчёт</Button>}
        {send && !pending && <Button size="sm" variant="outline" disabled={busy}
          onClick={() => void send({ action: 'photo_check' })}>{report ? 'Обновить проверку' : 'Проверить фото'}</Button>}
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
    <p className="text-sm text-muted-foreground">Город компании · {state.profile.city || 'не указан'}. Частотность Wordstat — из сохранённых данных. Регион частотности источника может отличаться.</p>
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
