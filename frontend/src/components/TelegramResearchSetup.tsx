import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, ChevronRight, Loader2, MessageSquareText, RefreshCw, Search, ShieldCheck } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  enabled?: boolean;
  account?: {
    configured?: boolean;
    authorized?: boolean;
    phone?: string;
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
};

export const TelegramResearchSetup = ({ businessId, mode = 'full' }: TelegramResearchSetupProps) => {
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

  const loadStatus = useCallback(async () => {
    if (!businessId) return;
    const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-research/status`);
    setStatus(response || null);
  }, [businessId]);

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
    if (mode !== 'connection' && status?.account?.authorized && dialogs.length === 0) void loadDialogs();
  }, [dialogs.length, loadDialogs, mode, status?.account?.authorized]);

  const requestCode = async () => {
    if (!businessId || !phone.trim() || !apiId.trim() || !apiHash.trim()) return;
    setBusy('connect');
    setError('');
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/telegram-research/connect`, {
        method: 'POST',
        body: JSON.stringify({ phone: phone.trim(), api_id: apiId.trim(), api_hash: apiHash.trim() }),
      });
      if (response.authorized) {
        setMessage('Аккаунт уже подключён. Теперь выберите источники.');
        await loadStatus();
        await loadDialogs();
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
        body: JSON.stringify({ code: code.trim(), password }),
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
      setMessage('Аккаунт подключён. Теперь выберите источники.');
      await loadStatus();
      await loadDialogs();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось завершить подключение');
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

  if (mode === 'connection' && status?.account?.authorized) {
    return (
      <section className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-emerald-950">Аккаунт для исследования подключён</h3>
            <p className="mt-1 text-sm leading-6 text-emerald-800">
              {status.account.phone ? `${status.account.phone} · ` : ''}Источники и слова для поиска настраиваются в разделе «Telegram-радар».
            </p>
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
          <h3 className="text-base font-semibold text-slate-950">Telegram-источники для знаний рынка</h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            LocalOS читает только выбранные вами чаты, ищет повторяющиеся вопросы и ничего в них не отправляет.
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
            <p className="font-semibold text-slate-950">Подключите отдельный аккаунт для чтения источников</p>
            <p className="mt-1 text-sm leading-6 text-slate-600">Данные приложения Telegram можно создать на my.telegram.org. Пароль двухэтапной проверки не сохраняется.</p>
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
                <p className="text-xs text-emerald-800">Выбрано источников: {status.active_sources || 0}</p>
              </div>
            </div>
            <Button type="button" variant="outline" onClick={() => void loadDialogs()} disabled={busy === 'dialogs'} className="min-h-10 bg-white">
              <RefreshCw className={cn('mr-2 h-4 w-4', busy === 'dialogs' && 'animate-spin')} />
              Обновить список
            </Button>
          </div>

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
        </div>
      )}
    </section>
  );
};
