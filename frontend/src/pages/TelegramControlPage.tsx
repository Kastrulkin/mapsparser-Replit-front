import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowUpRight, Building2, CheckCircle2, ChevronRight, Loader2, Network, Search, ShieldCheck, Sparkles, Star } from 'lucide-react';

type ControlScope = {
  kind: 'platform' | 'network' | 'business';
  id?: string | null;
  name?: string;
  business_ids?: string[];
  can_switch?: boolean;
};

type Metric = {
  key?: string;
  label?: string;
  value?: string | number | null;
  updated_at?: string | null;
  source?: string;
  source_label?: string;
  status?: string;
};

type AttentionItem = {
  id?: string;
  title?: string;
  description?: string;
  count?: number;
  severity?: string;
  target_scope?: { kind?: string; id?: string };
  cta?: { label?: string; href?: string };
};

type OperatorSummary = {
  scope?: ControlScope;
  as_of?: string;
  metrics?: Metric[];
  attention_items?: AttentionItem[];
  data_warnings?: string[];
  available_actions?: Array<{ key?: string; label?: string; href?: string; callback?: string }>;
};

type ScopeCatalog = {
  platform?: ControlScope | null;
  networks?: Array<{ id?: string; name?: string; locations_count?: number }>;
  businesses?: Array<{ id?: string; name?: string; address?: string; network_id?: string | null; network_name?: string | null }>;
  total_choices?: number;
};

type BootstrapPayload = {
  success?: boolean;
  error?: string;
  selected_scope?: ControlScope | null;
  summary?: OperatorSummary | null;
  catalog?: ScopeCatalog;
  preferences?: {
    favorite_scopes_json?: Array<{ kind?: string; id?: string | null; name?: string }>;
  };
  favorite?: boolean;
  web_session_token?: string | null;
};

const LOCAL_PREVIEW_PAYLOAD: BootstrapPayload = {
  success: true,
  selected_scope: { kind: 'business', id: 'preview-business', name: 'Весёлая расчёска', business_ids: ['preview-business'], can_switch: true },
  summary: {
    scope: { kind: 'business', id: 'preview-business', name: 'Весёлая расчёска', business_ids: ['preview-business'], can_switch: true },
    attention_items: [
      { id: 'reviews', title: 'Отзывы без ответа', description: 'LocalOS нашёл отзывы, где клиенты ещё ждут ответа.', count: 50, severity: 'high', cta: { label: 'Подготовить ответы', href: '/dashboard/card?tab=reviews' } },
      { id: 'drafts', title: 'Черновики готовы', description: 'Осталось только проверить тон и подтвердить.', count: 12, severity: 'medium' },
      { id: 'freshness', title: 'Карточка проверена', description: 'Данные свежие, ошибок нет.', count: 0, severity: 'low' },
    ],
    metrics: [
      { key: 'rating', label: 'Рейтинг на карте', value: '4.8', source_label: 'Яндекс Карты', updated_at: new Date().toISOString() },
      { key: 'provider', label: 'Отзывов на карте', value: 296, source_label: 'Яндекс Карты', updated_at: new Date().toISOString() },
      { key: 'loaded', label: 'Загружено в LocalOS', value: 164, source_label: 'Отзывы LocalOS', updated_at: new Date().toISOString() },
      { key: 'unanswered', label: 'Без ответа', value: 50, source_label: 'Отзывы LocalOS', updated_at: new Date().toISOString() },
    ],
    available_actions: [
      { key: 'reviews', label: 'Отзывы', href: '/dashboard/card?tab=reviews' },
      { key: 'content', label: 'Контент', href: '/dashboard/content' },
      { key: 'finance', label: 'Финансы', href: '/dashboard/finance' },
      { key: 'services', label: 'Услуги', href: '/dashboard/card?tab=services' },
    ],
  },
  catalog: {
    platform: { kind: 'platform', name: 'Вся платформа' },
    networks: [{ id: 'network-preview', name: 'Сеть Beauty Family', locations_count: 12 }],
    businesses: [{ id: 'preview-business', name: 'Весёлая расчёска', address: 'Москва, Тверская, 7' }],
    total_choices: 3,
  },
  preferences: { favorite_scopes_json: [] },
};

type TelegramWebApp = {
  initData?: string;
  ready?: () => void;
  expand?: () => void;
  openLink?: (url: string) => void;
};

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

const webApp = () => window.Telegram?.WebApp;

const scopeIcon = (kind?: string) => {
  if (kind === 'platform') return ShieldCheck;
  if (kind === 'network') return Network;
  return Building2;
};

const formatUpdatedAt = (value?: string | null) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
};

const postTelegramControl = async (
  path: string,
  initData: string,
  body: Record<string, unknown> = {},
): Promise<BootstrapPayload> => {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ init_data: initData, ...body }),
  });
  const payload: BootstrapPayload = await response.json();
  if (!payload || payload.success === false) {
    throw new Error(payload?.error || 'Не удалось загрузить LocalOS.');
  }
  return payload;
};

export const TelegramControlPage = () => {
  const localPreview = ['127.0.0.1', 'localhost'].includes(window.location.hostname) && new URLSearchParams(window.location.search).get('preview') === '1';
  const initData = webApp()?.initData || (localPreview ? 'local-preview' : '');
  const [payload, setPayload] = useState<BootstrapPayload | null>(localPreview ? LOCAL_PREVIEW_PAYLOAD : null);
  const [loading, setLoading] = useState(!localPreview);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState('');
  const [scopePickerOpen, setScopePickerOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [workStage, setWorkStage] = useState(0);
  const [lastCompletedAt, setLastCompletedAt] = useState<Date | null>(null);

  const bootstrap = async (query = '') => {
    if (localPreview) return;
    if (!initData) {
      setError('Откройте этот экран кнопкой внутри Telegram-бота LocalOS.');
      setLoading(false);
      return;
    }
    try {
      const result = await postTelegramControl('/api/operator/telegram/bootstrap', initData, query ? { q: query } : {});
      if (result.web_session_token) window.localStorage.setItem('auth_token', result.web_session_token);
      if (result.selected_scope?.kind === 'business' && result.selected_scope.id) {
        window.localStorage.setItem('selectedBusinessId', result.selected_scope.id);
      }
      setPayload(result);
      setLastCompletedAt(new Date());
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить LocalOS.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    webApp()?.ready?.();
    webApp()?.expand?.();
    void bootstrap();
  }, []);

  useEffect(() => {
    if (!scopePickerOpen || !initData) return;
    const timeoutId = window.setTimeout(() => void bootstrap(searchQuery.trim()), 250);
    return () => window.clearTimeout(timeoutId);
  }, [searchQuery, scopePickerOpen]);

  useEffect(() => {
    if (!loading && !switching) {
      setWorkStage(0);
      return;
    }
    const intervalId = window.setInterval(() => setWorkStage((current) => (current + 1) % 3), 820);
    return () => window.clearInterval(intervalId);
  }, [loading, switching]);

  const selectScope = async (scopeType: string, scopeId?: string | null) => {
    setSwitching(true);
    try {
      const [result] = await Promise.all([
        postTelegramControl('/api/operator/telegram/scope', initData, {
          scope_type: scopeType,
          scope_id: scopeId || null,
        }),
        new Promise((resolve) => window.setTimeout(resolve, 560)),
      ]);
      setPayload((current) => ({
        ...current,
        ...result,
        catalog: current?.catalog,
      }));
      if (result.selected_scope?.kind === 'business' && result.selected_scope.id) {
        window.localStorage.setItem('selectedBusinessId', result.selected_scope.id);
      }
      setScopePickerOpen(false);
      setSearchQuery('');
      setError('');
      setLastCompletedAt(new Date());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось сменить раздел.');
    } finally {
      setSwitching(false);
    }
  };

  const toggleFavorite = async () => {
    if (localPreview) {
      setPayload((current) => ({
        ...current,
        preferences: {
          favorite_scopes_json: current?.preferences?.favorite_scopes_json?.length ? [] : [{ kind: selectedScope?.kind, id: selectedScope?.id, name: selectedScope?.name }],
        },
      }));
      return;
    }
    setSwitching(true);
    try {
      const result = await postTelegramControl('/api/operator/telegram/favorite', initData);
      setPayload((current) => ({ ...current, preferences: result.preferences }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось обновить избранное.');
    } finally {
      setSwitching(false);
    }
  };

  const selectedScope = payload?.selected_scope || payload?.summary?.scope;
  const ScopeIcon = scopeIcon(selectedScope?.kind);
  const attentionItems = payload?.summary?.attention_items || [];
  const metrics = payload?.summary?.metrics || [];
  const warnings = payload?.summary?.data_warnings || [];
  const actions = payload?.summary?.available_actions || [];
  const catalog = payload?.catalog;
  const hasSwitcher = Boolean(selectedScope?.can_switch || Number(catalog?.total_choices || 0) > 1);
  const currentIsFavorite = Boolean(payload?.preferences?.favorite_scopes_json?.some((item) => (
    item.kind === selectedScope?.kind && (item.id || null) === (selectedScope?.id || null)
  )));

  const scopeSubtitle = useMemo(() => {
    if (selectedScope?.kind === 'platform') return 'Операционная картина LocalOS';
    if (selectedScope?.kind === 'network') return `${selectedScope.business_ids?.length || 0} точек в сети`;
    return 'Один бизнес';
  }, [selectedScope]);

  const openAction = (href?: string) => {
    if (!href) return;
    const absolute = href.startsWith('http') ? href : `${window.location.origin}${href}`;
    if (webApp()?.openLink) webApp()?.openLink?.(absolute);
    else window.location.href = absolute;
  };

  const primaryItem = attentionItems[0];
  const primaryHref = primaryItem?.cta?.href || actions.find((action) => action.href)?.href;
  const primaryLabel = primaryItem?.cta?.label || actions.find((action) => action.href)?.label || 'Открыть задачи';
  const workMessages = ['Сверяем доступы', 'Собираем реальные задачи', 'Выбираем главное'];

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center overflow-hidden bg-zinc-950 p-6 text-white antialiased">
        <div className="relative flex w-full max-w-sm flex-col items-center text-center">
          <div className="absolute h-56 w-56 rounded-full bg-primary/15 blur-3xl" aria-hidden="true" />
          <div className="relative grid h-20 w-20 place-items-center rounded-[26px] bg-zinc-900 shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_24px_80px_rgba(255,92,51,0.18)]">
            <div className="absolute inset-2 animate-pulse rounded-[20px] bg-primary/10 motion-reduce:animate-none" />
            <Sparkles className="relative h-7 w-7 text-primary" />
          </div>
          <p className="mt-7 text-xs font-semibold uppercase tracking-[0.18em] text-primary">LocalOS</p>
          <h1 className="mt-2 text-balance text-xl font-semibold tracking-[-0.03em]">Собираем ваш рабочий день</h1>
          <div className="mt-5 flex min-h-6 items-center gap-2 text-sm text-zinc-400" aria-live="polite">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400 motion-reduce:animate-none" />
            {workMessages[workStage]}
          </div>
          <p className="mt-2 text-pretty text-xs leading-5 text-zinc-600">Показываем только то, где нужно ваше решение.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen overflow-hidden bg-zinc-950 text-zinc-100 antialiased selection:bg-primary/30">
      <div className="pointer-events-none fixed inset-x-0 top-0 mx-auto h-80 max-w-xl bg-[radial-gradient(circle_at_top,rgba(255,92,51,0.14),transparent_68%)]" aria-hidden="true" />
      <div className="relative mx-auto min-h-screen max-w-xl pb-10">
        <header className="px-5 pb-5 pt-5">
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary text-[11px] font-black tracking-normal text-white shadow-[0_8px_24px_rgba(255,92,51,0.28)]">LO</span>
              LocalOS
            </div>
            <div className="flex min-h-8 items-center gap-2 rounded-full bg-white/[0.05] px-3 text-[11px] font-medium text-zinc-400 ring-1 ring-inset ring-white/[0.07]">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400 motion-reduce:animate-none" />
              Работает в фоне
            </div>
          </div>
          <button
            type="button"
            onClick={() => hasSwitcher && setScopePickerOpen((current) => !current)}
            disabled={!hasSwitcher}
            className="flex min-h-14 w-full items-center gap-3 rounded-[20px] bg-white/[0.04] px-3 py-2 text-left ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] active:scale-[0.96] hover:bg-white/[0.07] disabled:cursor-default disabled:active:scale-100"
          >
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-primary/15 text-primary ring-1 ring-inset ring-primary/20">
              <ScopeIcon className="h-[19px] w-[19px]" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[15px] font-semibold tracking-[-0.01em]">{selectedScope?.name || 'Рабочий раздел'}</span>
              <span className="mt-0.5 block text-xs text-zinc-500">{scopeSubtitle}</span>
            </span>
            {hasSwitcher ? <ChevronRight className={`h-5 w-5 text-zinc-600 transition-transform ${scopePickerOpen ? 'rotate-90' : ''}`} /> : null}
          </button>
        </header>

        {scopePickerOpen ? (
          <section className="animate-in fade-in slide-in-from-bottom-2 px-5 pb-8 duration-200 motion-reduce:animate-none" aria-label="Выбор бизнеса или сети">
            <div className="mb-4 flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <h1 className="text-balance text-2xl font-semibold tracking-[-0.04em]">Где работаем?</h1>
                <p className="mt-1 text-sm leading-6 text-zinc-500">LocalOS пересоберёт саммари и действия для выбранного масштаба.</p>
              </div>
              <button
                type="button"
                onClick={() => void toggleFavorite()}
                aria-label={currentIsFavorite ? 'Убрать из избранного' : 'Добавить в избранное'}
                className={`grid h-11 w-11 shrink-0 place-items-center rounded-2xl ring-1 ring-inset transition-[background-color,color,transform] active:scale-[0.96] ${currentIsFavorite ? 'bg-primary/15 text-primary ring-primary/25' : 'bg-white/[0.04] text-zinc-600 ring-white/[0.07]'}`}
              >
                <Star className={`h-4 w-4 ${currentIsFavorite ? 'fill-current' : ''}`} />
              </button>
            </div>
            <label className="relative block">
              <Search className="pointer-events-none absolute left-4 top-4 h-4 w-4 text-zinc-600" />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Название, город или адрес"
                className="min-h-12 w-full rounded-2xl bg-white/[0.05] pl-11 pr-4 text-sm text-white outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-600 transition-shadow focus:ring-2 focus:ring-primary/50"
              />
            </label>
            <div className="mt-4 max-h-[62vh] space-y-2 overflow-y-auto pr-1">
              {!searchQuery.trim() && payload?.preferences?.favorite_scopes_json?.length ? (
                <p className="px-1 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-700">Избранное</p>
              ) : null}
              {!searchQuery.trim() ? payload?.preferences?.favorite_scopes_json?.map((favorite) => (
                <ScopeButton
                  key={`favorite-${favorite.kind}-${favorite.id || 'platform'}`}
                  label={favorite.name || 'Избранное'}
                  meta="Быстрый доступ"
                  icon={favorite.kind === 'platform' ? 'platform' : favorite.kind === 'network' ? 'network' : 'business'}
                  busy={switching}
                  onClick={() => void selectScope(favorite.kind || 'business', favorite.id)}
                />
              )) : null}
              {catalog?.platform ? (
                <ScopeButton label="Вся платформа" meta="Операционная картина LocalOS" icon="platform" busy={switching} onClick={() => void selectScope('platform')} />
              ) : null}
              {!searchQuery.trim() ? catalog?.networks?.map((network) => (
                <ScopeButton
                  key={network.id}
                  label={network.name || 'Сеть'}
                  meta={`${network.locations_count || 0} точек`}
                  icon="network"
                  busy={switching}
                  onClick={() => void selectScope('network', network.id)}
                />
              )) : null}
              {catalog?.businesses?.map((business) => (
                <ScopeButton
                  key={business.id}
                  label={business.name || 'Бизнес'}
                  meta={[business.network_name, business.address].filter(Boolean).join(' · ')}
                  icon="business"
                  busy={switching}
                  onClick={() => void selectScope('business', business.id)}
                />
              ))}
            </div>
            {switching ? (
              <div className="mt-4 flex min-h-11 items-center justify-center gap-2 text-sm text-zinc-400" aria-live="polite">
                <Loader2 className="h-4 w-4 animate-spin text-primary motion-reduce:animate-none" />
                {workMessages[workStage]}
              </div>
            ) : null}
          </section>
        ) : (
          <>
            {error ? (
              <div className="mx-5 mb-5 flex gap-3 rounded-2xl bg-rose-500/10 p-4 text-sm text-rose-200 ring-1 ring-inset ring-rose-400/20">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                <p className="text-pretty">{error}</p>
              </div>
            ) : null}

            <section className="px-5 pb-6 pt-2">
              <div className="rounded-[28px] bg-gradient-to-b from-zinc-900 to-zinc-900/70 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)] ring-1 ring-inset ring-white/[0.08]">
                <div className="flex items-center gap-2 text-xs font-medium text-zinc-500">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  LocalOS уже разобрал ситуацию
                </div>
                <div className="mt-4 flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h1 className="text-balance text-[26px] font-semibold leading-8 tracking-[-0.045em]">{primaryItem?.title || 'Всё под контролем'}</h1>
                    {primaryItem?.description ? <p className="mt-2 text-pretty text-sm leading-6 text-zinc-400">{primaryItem.description}</p> : null}
                  </div>
                  {Number(primaryItem?.count || 0) > 0 ? (
                    <span className="shrink-0 rounded-2xl bg-primary/15 px-3 py-2 text-xl font-semibold tabular-nums text-primary ring-1 ring-inset ring-primary/20">{primaryItem?.count}</span>
                  ) : <CheckCircle2 className="h-8 w-8 shrink-0 text-emerald-400" />}
                </div>
                {primaryItem?.target_scope?.id ? (
                  <button
                    type="button"
                    onClick={() => void selectScope('business', primaryItem.target_scope?.id)}
                    className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96] hover:brightness-105"
                  >
                    Разобрать эту точку <ChevronRight className="h-4 w-4" />
                  </button>
                ) : primaryHref ? (
                  <button
                    type="button"
                    onClick={() => openAction(primaryHref)}
                    className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96] hover:brightness-105"
                  >
                    {primaryLabel} <ArrowUpRight className="h-4 w-4" />
                  </button>
                ) : null}
              </div>

              {attentionItems.length > 1 ? (
                <div className="mt-3 divide-y divide-white/[0.06] rounded-[22px] bg-white/[0.035] px-4 ring-1 ring-inset ring-white/[0.06]">
                  {attentionItems.slice(1, 5).map((item, index) => (
                    <button
                      type="button"
                      key={item.id || index}
                      onClick={() => item.target_scope?.id ? void selectScope('business', item.target_scope.id) : openAction(item.cta?.href)}
                      className="flex min-h-16 w-full items-center gap-3 py-3 text-left transition-[opacity,transform] active:scale-[0.98] hover:opacity-80"
                    >
                      <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-xl ${item.severity === 'high' ? 'bg-rose-400/10 text-rose-300' : item.severity === 'medium' ? 'bg-amber-400/10 text-amber-300' : 'bg-emerald-400/10 text-emerald-300'}`}>
                        {item.severity === 'low' ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-zinc-200">{item.title || 'Задача'}</span>
                        {item.description ? <span className="mt-0.5 block truncate text-xs text-zinc-600">{item.description}</span> : null}
                      </span>
                      {Number(item.count || 0) > 0 ? <span className="text-sm font-semibold tabular-nums text-zinc-400">{item.count}</span> : null}
                      <ChevronRight className="h-4 w-4 text-zinc-700" />
                    </button>
                  ))}
                </div>
              ) : null}
            </section>

            <section className="px-5 py-6">
              <div className="flex items-end justify-between gap-3">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-zinc-600">Сверено с источниками</p>
                  <h2 className="mt-1 text-lg font-semibold tracking-[-0.025em]">Текущая картина</h2>
                </div>
                <span className="text-[11px] tabular-nums text-zinc-600">{lastCompletedAt ? `сейчас, ${lastCompletedAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}` : 'сейчас'}</span>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-[22px] bg-white/[0.06] ring-1 ring-inset ring-white/[0.06]">
                {metrics.slice(0, 6).map((metric) => (
                  <div key={metric.key} className="min-w-0 bg-zinc-950 px-4 py-4">
                    <p className="text-[11px] font-medium leading-4 text-zinc-600">{metric.label}</p>
                    <p className="mt-1 truncate text-2xl font-semibold tracking-[-0.04em] tabular-nums text-zinc-100">{metric.value ?? '—'}</p>
                    <p className="mt-1 truncate text-[10px] tabular-nums text-zinc-700">
                      {metric.source_label || metric.source || 'LocalOS'}
                      {metric.updated_at ? ` · ${formatUpdatedAt(metric.updated_at)}` : ''}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {warnings.length ? (
              <section className="px-5 pb-6">
                <div className="rounded-[20px] bg-amber-400/[0.08] p-4 text-sm leading-5 text-amber-100 ring-1 ring-inset ring-amber-300/15">
                  <p className="font-semibold">LocalOS заметил расхождение</p>
                  {warnings.slice(0, 2).map((warning) => <p key={warning} className="mt-1 text-pretty">{warning}</p>)}
                </div>
              </section>
            ) : null}

            <section className="px-5 pb-6 pt-1">
              <h2 className="text-lg font-semibold tracking-[-0.025em]">Остальная работа</h2>
              <p className="mt-1 text-sm text-zinc-600">Сложные шаги LocalOS откроет с готовыми данными и предпросмотром.</p>
              <div className="mt-4 grid grid-cols-2 gap-2">
                {actions.filter((action) => action.href).slice(0, 10).map((action) => (
                  <button
                    key={action.key}
                    type="button"
                    onClick={() => openAction(action.href)}
                    className="flex min-h-12 items-center justify-between rounded-2xl bg-white/[0.045] px-3.5 text-left text-sm font-medium text-zinc-300 ring-1 ring-inset ring-white/[0.06] transition-[background-color,transform] active:scale-[0.96] hover:bg-white/[0.08]"
                  >
                    {action.label}
                    <ArrowUpRight className="h-3.5 w-3.5 text-zinc-700" />
                  </button>
                ))}
              </div>
            </section>

            <section className="mx-5 flex items-center gap-3 rounded-[20px] bg-white/[0.025] px-4 py-3 ring-1 ring-inset ring-white/[0.05]">
              <div className="relative grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-400/10 text-emerald-300">
                <span className="absolute inset-0 animate-ping rounded-xl bg-emerald-400/5 motion-reduce:animate-none" />
                <Sparkles className="relative h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-zinc-300">LocalOS продолжает следить</p>
                <p className="mt-0.5 truncate text-[11px] text-zinc-600">Если появится новая задача, она поднимется сюда.</p>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
};

const ScopeButton = ({
  label,
  meta,
  icon,
  busy,
  onClick,
}: {
  label: string;
  meta?: string;
  icon: 'platform' | 'network' | 'business';
  busy: boolean;
  onClick: () => void;
}) => {
  const Icon = scopeIcon(icon);
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="flex min-h-14 w-full items-center gap-3 rounded-2xl bg-white/[0.045] px-3 py-2 text-left ring-1 ring-inset ring-white/[0.06] transition-[transform,background-color] active:scale-[0.96] hover:bg-white/[0.08] disabled:opacity-60"
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="h-4 w-4" /></span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-zinc-200">{label}</span>
        {meta ? <span className="mt-0.5 block truncate text-xs text-zinc-600">{meta}</span> : null}
      </span>
      <ChevronRight className="h-4 w-4 shrink-0 text-zinc-700" />
    </button>
  );
};

export default TelegramControlPage;
