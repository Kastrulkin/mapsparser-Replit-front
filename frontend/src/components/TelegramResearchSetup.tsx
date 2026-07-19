import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, ChevronRight, Loader2, MessageSquareText, RefreshCw, Search, ShieldCheck, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type ResearchSource = {
  id: string;
  title?: string;
  visibility?: string;
  status?: string;
  sync_status?: string;
  documents_count?: number;
  last_collected_at?: string;
  last_sync_error?: string;
};

type ResearchStatus = {
  scope_type?: 'business' | 'platform';
  enabled?: boolean;
  account?: {
    configured?: boolean;
    authorized?: boolean;
    phone?: string;
    account_id?: string;
    radar_enabled?: boolean;
    outreach_enabled?: boolean;
    reply_sync_enabled?: boolean;
  };
  sources?: ResearchSource[];
  active_sources?: number;
};

type TelegramDialog = {
  telegram_chat_id: string;
  title?: string;
  telegram_username?: string | null;
  visibility?: 'public' | 'private';
  source_type?: string;
  selected?: boolean;
};

const syncLabel = (source: ResearchSource) => {
  if (source.sync_status === 'syncing') return 'Загружаем историю';
  if (source.sync_status === 'queued') return 'Скоро начнём загрузку';
  if (source.sync_status === 'partial') return 'История загружается';
  if (source.sync_status === 'failed') return 'Нужно проверить';
  if (source.sync_status === 'needs_account') return 'Нужно переподключить аккаунт';
  if (source.last_collected_at) return 'Обновляется раз в день';
  return 'Ожидает первого обновления';
};

type TelegramResearchSetupProps = {
  businessId?: string | null;
  mode?: 'full' | 'connection' | 'sources';
  scopeType?: 'business' | 'platform';
};

export const TelegramResearchSetup = ({ businessId, mode = 'full', scopeType = 'business' }: TelegramResearchSetupProps) => {
  const [status, setStatus] = useState<ResearchStatus | null>(null);
  const [dialogs, setDialogs] = useState<TelegramDialog[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [phone, setPhone] = useState('');
  const [apiId, setApiId] = useState('');
  const [apiHash, setApiHash] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [codeRequested, setCodeRequested] = useState(false);
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [preflight, setPreflight] = useState<{ radar?: string; outreach?: string } | null>(null);

  const loadStatus = useCallback(async () => {
    if (!businessId) return;
    const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-research/status?scope_type=${encodeURIComponent(scopeType)}`);
    setStatus(response || null);
  }, [businessId, scopeType]);

  const loadDialogs = useCallback(async () => {
    if (!businessId) return;
    setBusy('dialogs');
    setError('');
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-research/dialogs`);
      const items = Array.isArray(response.dialogs) ? response.dialogs : [];
      setDialogs(items);
      setSelectedIds(items.filter((item: TelegramDialog) => item.selected).map((item: TelegramDialog) => item.telegram_chat_id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось получить список чатов');
    } finally {
      setBusy('');
    }
  }, [businessId]);

  useEffect(() => {
    if (!businessId) return;
    void loadStatus().catch((requestError) => {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить подключение');
    });
  }, [businessId, loadStatus]);

  useEffect(() => {
    if (scopeType === 'business' && mode !== 'connection' && status?.account?.authorized && status.account.radar_enabled && dialogs.length === 0) void loadDialogs();
  }, [dialogs.length, loadDialogs, mode, scopeType, status?.account?.authorized, status?.account?.radar_enabled]);

  const updatePermission = async (key: 'radar_enabled' | 'outreach_enabled', enabled: boolean) => {
    if (!businessId) return;
    setBusy(key);
    setError('');
    try {
      await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-account/permissions`, {
        method: 'PATCH',
        body: JSON.stringify({ [key]: enabled, scope_type: scopeType }),
      });
      setMessage(key === 'radar_enabled'
        ? enabled ? 'Telegram-радар включён.' : 'Радар остановлен. Собранные данные сохранены.'
        : enabled ? 'Отправка разрешена. Проверка ответов и stop-on-reply включены обязательно.' : 'Новые Telegram-касания поставлены на паузу.');
      await loadStatus();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось изменить разрешение');
    } finally {
      setBusy('');
    }
  };

  const disconnectAccount = async () => {
    if (!businessId || !window.confirm('Отключить Telegram-аккаунт? Радар и будущие отправки будут остановлены.')) return;
    setBusy('disconnect');
    setError('');
    try {
      await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-account?scope_type=${encodeURIComponent(scopeType)}`, { method: 'DELETE' });
      setDialogs([]);
      setSelectedIds([]);
      setMessage('Telegram-аккаунт отключён. История и подготовленные черновики сохранены.');
      await loadStatus();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось отключить аккаунт');
    } finally {
      setBusy('');
    }
  };

  const requestCode = async () => {
    if (!businessId || !phone.trim() || !apiId.trim() || !apiHash.trim()) return;
    setBusy('connect');
    setError('');
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-research/connect`, {
        method: 'POST',
        body: JSON.stringify({ phone: phone.trim(), api_id: apiId.trim(), api_hash: apiHash.trim(), scope_type: scopeType }),
      });
      if (response.authorized) {
        setMessage(scopeType === 'platform' ? 'Аккаунт LocalOS подключён. Теперь настройте два разрешения.' : 'Аккаунт уже подключён. Теперь выберите источники.');
        await loadStatus();
        if (mode !== 'connection' && scopeType === 'business') await loadDialogs();
        return;
      }
      setCodeRequested(true);
      setMessage('Код отправлен в Telegram. Введите его ниже.');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось отправить код');
    } finally {
      setBusy('');
    }
  };

  const confirmAccount = async () => {
    if (!businessId) return;
    setBusy('confirm');
    setError('');
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-research/confirm`, {
        method: 'POST',
        body: JSON.stringify({ code: code.trim(), password, scope_type: scopeType }),
      });
      if (response.password_required) {
        setPasswordRequired(true);
        setMessage('У аккаунта включена двухэтапная проверка. Введите пароль.');
        return;
      }
      setCodeRequested(false);
      setPasswordRequired(false);
      setCode('');
      setPassword('');
      setMessage(scopeType === 'platform' ? 'Аккаунт LocalOS подключён. Теперь настройте два разрешения.' : 'Аккаунт подключён. Теперь выберите источники.');
      await loadStatus();
      if (mode !== 'connection' && scopeType === 'business') await loadDialogs();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось завершить подключение');
    } finally {
      setBusy('');
    }
  };

  const runPreflight = async () => {
    if (!businessId) return;
    setBusy('preflight');
    setError('');
    try {
      const [radar, outreach] = await Promise.all([
        newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-account/preflight/radar`, {
          method: 'POST',
          body: JSON.stringify({ scope_type: scopeType }),
        }),
        newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-account/preflight/outreach`, {
          method: 'POST',
          body: JSON.stringify({ scope_type: scopeType }),
        }),
      ]);
      setPreflight({
        radar: radar.ready ? 'Готов' : String(radar.reason_code || 'Нужна проверка'),
        outreach: outreach.ready ? 'Готов' : String(outreach.reason_code || 'Нужна проверка'),
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить готовность Telegram');
    } finally {
      setBusy('');
    }
  };

  const saveSources = async () => {
    if (!businessId) return;
    setBusy('sources');
    setError('');
    try {
      const selected = dialogs.filter((dialog) => selectedIds.includes(dialog.telegram_chat_id));
      await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-research/sources`, {
        method: 'PUT',
        body: JSON.stringify({ sources: selected }),
      });
      await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-research/backfill`, { method: 'POST' });
      setMessage('Источники сохранены. LocalOS загрузит последние 90 дней и продолжит обновлять их автоматически.');
      await loadStatus();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить источники');
    } finally {
      setBusy('');
    }
  };

  const visibleDialogs = useMemo(() => {
    const cleanQuery = query.trim().toLowerCase();
    if (!cleanQuery) return dialogs;
    return dialogs.filter((dialog) => `${dialog.title || ''} ${dialog.telegram_username || ''}`.toLowerCase().includes(cleanQuery));
  }, [dialogs, query]);

  if (!businessId) return null;

  if (mode === 'sources' && !status?.account?.authorized) {
    return (
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sky-50 text-sky-700 ring-1 ring-sky-100">
            <MessageSquareText className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold text-slate-950">Источники Telegram</h3>
            <p className="mt-1 text-sm leading-6 text-slate-600">Сначала подключите отдельный Telegram-аккаунт для чтения выбранных каналов и чатов.</p>
            <Button type="button" variant="outline" asChild className="mt-4 min-h-10 bg-white">
              <Link to="/dashboard/settings?focus=telegram">Подключить аккаунт</Link>
            </Button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sky-50 text-sky-700 ring-1 ring-sky-100">
          <MessageSquareText className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <h3 className="text-balance text-base font-semibold text-slate-950">
            {scopeType === 'platform' ? 'Telegram-аккаунт LocalOS' : 'Telegram-аккаунт бизнеса'}
          </h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {scopeType === 'platform'
              ? 'Этот аккаунт используется только для поиска клиентов LocalOS. Радар и одобренные сообщения разрешаются независимо.'
              : 'Одно подключение для радара этого бизнеса и одобренных сообщений партнёрам. Каждую функцию можно разрешить отдельно.'}
          </p>
        </div>
      </div>

      {error ? <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800 ring-1 ring-rose-100">{error}</div> : null}
      {message ? <div className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-100">{message}</div> : null}
      {status && status.enabled === false ? (
        <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900 ring-1 ring-amber-100">Автоматическое обновление источников пока выключено. Подключение можно подготовить, а для запуска обратитесь в поддержку.</div>
      ) : null}

      {!status?.account?.authorized ? (
        <div className="space-y-4 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
          <div>
            <p className="font-semibold text-slate-950">Подключите Telegram-аккаунт</p>
            <p className="mt-1 text-sm leading-6 text-slate-600">Создайте Telegram API application на my.telegram.org и укажите его данные. Этот же аккаунт можно использовать для радара и сообщений; пароль 2FA не сохраняется.</p>
          </div>
          {!codeRequested ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label htmlFor="telegram-research-phone">Номер телефона</Label>
                <Input id="telegram-research-phone" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+357…" className="mt-1 min-h-11" />
              </div>
              <div>
                <Label htmlFor="telegram-research-api-id">ID приложения</Label>
                <Input id="telegram-research-api-id" value={apiId} onChange={(event) => setApiId(event.target.value)} inputMode="numeric" className="mt-1 min-h-11" />
              </div>
              <div>
                <Label htmlFor="telegram-research-api-hash">Ключ приложения</Label>
                <Input id="telegram-research-api-hash" value={apiHash} onChange={(event) => setApiHash(event.target.value)} type="password" className="mt-1 min-h-11" />
              </div>
              <Button type="button" onClick={() => void requestCode()} disabled={busy === 'connect' || !phone.trim() || !apiId.trim() || !apiHash.trim()} className="min-h-11 bg-slate-950 text-white hover:bg-slate-800 sm:col-span-2">
                {busy === 'connect' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Получить код
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {!passwordRequired ? (
                <div>
                  <Label htmlFor="telegram-research-code">Код из Telegram</Label>
                  <Input id="telegram-research-code" value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" className="mt-1 min-h-11" />
                </div>
              ) : null}
              {passwordRequired ? (
                <div>
                  <Label htmlFor="telegram-research-password">Пароль двухэтапной проверки</Label>
                  <Input id="telegram-research-password" value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" className="mt-1 min-h-11" />
                </div>
              ) : null}
              <Button type="button" onClick={() => void confirmAccount()} disabled={busy === 'confirm' || (!passwordRequired && !code.trim()) || (passwordRequired && !password)} className="min-h-11 w-full bg-slate-950 text-white hover:bg-slate-800">
                {busy === 'confirm' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Подключить аккаунт
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 rounded-2xl bg-emerald-50 px-4 py-3 ring-1 ring-emerald-100 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 shrink-0 text-emerald-700" />
              <div>
                <p className="text-sm font-semibold text-emerald-950">Аккаунт подключён {status.account.phone ? `· ${status.account.phone}` : ''}</p>
                <p className="text-xs text-emerald-800">Один аккаунт · два независимых разрешения</p>
              </div>
            </div>
            {mode !== 'connection' && status.account.radar_enabled ? <Button type="button" variant="outline" onClick={() => void loadDialogs()} disabled={busy === 'dialogs'} className="min-h-10 bg-white">
              <RefreshCw className={cn('mr-2 h-4 w-4', busy === 'dialogs' && 'animate-spin')} />
              Обновить список
            </Button> : null}
          </div>

          <div className="divide-y divide-slate-200 rounded-2xl border border-slate-200 bg-white">
            <div className="flex min-h-20 items-center gap-4 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-950">Telegram-радар</p>
                <p className="mt-1 text-xs leading-5 text-slate-600">Читает только выбранные публичные источники и ищет сигналы. Выключение останавливает новые синхронизации, но сохраняет историю.</p>
              </div>
              <Switch checked={Boolean(status.account.radar_enabled)} disabled={busy === 'radar_enabled'} onCheckedChange={(checked) => void updatePermission('radar_enabled', checked)} aria-label="Использовать для Telegram-радара" />
            </div>
            <div className="flex min-h-20 items-center gap-4 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-950">
                  {scopeType === 'platform' ? 'Сообщения от имени LocalOS' : 'Сообщения от вашего имени'}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-600">Сообщения уходят с личного аккаунта только после approval кампании. Проверка ответов и остановка следующих касаний включаются вместе.</p>
              </div>
              <Switch checked={Boolean(status.account.outreach_enabled)} disabled={busy === 'outreach_enabled'} onCheckedChange={(checked) => void updatePermission('outreach_enabled', checked)} aria-label="Разрешить одобренные сообщения" />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => void runPreflight()} disabled={busy === 'preflight'} className="min-h-10 bg-white">
              <ShieldCheck className="mr-2 h-4 w-4" />{busy === 'preflight' ? 'Проверяем…' : 'Проверить готовность'}
            </Button>
            <Button type="button" variant="outline" asChild className="min-h-10 bg-white"><Link to="/dashboard/telegram-radar">Источники радара</Link></Button>
            <Button type="button" variant="outline" asChild className="min-h-10 bg-white"><Link to="/dashboard/bazich?view=messages">Кампании аутрича</Link></Button>
            {mode === 'connection' ? <Button type="button" variant="ghost" onClick={() => void disconnectAccount()} disabled={busy === 'disconnect'} className="min-h-10 text-rose-700 hover:bg-rose-50 hover:text-rose-800"><Trash2 className="mr-2 h-4 w-4" />Отключить аккаунт</Button> : null}
          </div>

          {preflight ? (
            <div className="grid gap-2 rounded-2xl bg-slate-50 p-3 text-sm text-slate-700 ring-1 ring-slate-200 sm:grid-cols-2">
              <div><span className="font-semibold text-slate-950">Радар:</span> {preflight.radar}</div>
              <div><span className="font-semibold text-slate-950">Аутрич и stop-on-reply:</span> {preflight.outreach}</div>
            </div>
          ) : null}

          {mode !== 'connection' && !status.account.radar_enabled ? (
            <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900 ring-1 ring-amber-100">Telegram-радар выключен. Включите его выше, чтобы выбирать источники и собирать новые сигналы. Разрешённая отправка сообщений продолжает работать независимо.</div>
          ) : null}

          {mode !== 'connection' && status.account.radar_enabled ? <>
          <div>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-slate-950">Какие чаты отслеживать</p>
                <p className="mt-1 text-sm text-slate-600">Для новых источников загружаются последние 90 дней, затем новые сообщения проверяются раз в день.</p>
              </div>
            </div>
            <div className="relative mt-3">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти чат или канал" className="min-h-11 pl-9" />
            </div>
          </div>

          <div className="max-h-80 divide-y divide-slate-100 overflow-y-auto rounded-2xl ring-1 ring-slate-200">
            {busy === 'dialogs' && dialogs.length === 0 ? (
              <div className="flex items-center justify-center gap-2 px-4 py-10 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Загружаем список</div>
            ) : visibleDialogs.length === 0 ? (
              <div className="px-4 py-10 text-center text-sm text-slate-500">Подходящих чатов не найдено.</div>
            ) : visibleDialogs.map((dialog) => {
              const checked = selectedIds.includes(dialog.telegram_chat_id);
              return (
                <label key={dialog.telegram_chat_id} className="flex min-h-14 cursor-pointer items-center gap-3 px-4 py-3 hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => setSelectedIds((current) => checked ? current.filter((id) => id !== dialog.telegram_chat_id) : [...current, dialog.telegram_chat_id])}
                    className="h-5 w-5 rounded border-slate-300 text-slate-950 focus:ring-slate-400"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-slate-900">{dialog.title || 'Telegram'}</span>
                    <span className="block text-xs text-slate-500">{dialog.visibility === 'public' ? 'Публичный источник' : 'Закрытый источник · выводы доступны только этому бизнесу'}</span>
                  </span>
                  {checked ? <Check className="h-4 w-4 text-emerald-600" /> : <ChevronRight className="h-4 w-4 text-slate-300" />}
                </label>
              );
            })}
          </div>

          <Button type="button" onClick={() => void saveSources()} disabled={busy === 'sources'} className="min-h-11 w-full bg-slate-950 text-white hover:bg-slate-800">
            {busy === 'sources' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Сохранить источники · {selectedIds.length}
          </Button>

          {status.sources?.length ? (
            <div className="space-y-2">
              {status.sources.map((source) => (
                <div key={source.id} className="flex items-start justify-between gap-3 rounded-2xl bg-slate-50 px-4 py-3 ring-1 ring-slate-100">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-900">{source.title}</p>
                    <p className={cn('mt-1 text-xs', source.sync_status === 'failed' ? 'text-rose-700' : 'text-slate-500')}>{source.last_sync_error || syncLabel(source)}</p>
                  </div>
                  <span className="shrink-0 text-xs tabular-nums text-slate-500">{source.documents_count || 0} сообщений</span>
                </div>
              ))}
            </div>
          ) : null}
          </> : null}
        </div>
      )}
    </section>
  );
};
