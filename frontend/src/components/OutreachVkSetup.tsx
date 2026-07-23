import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ExternalLink, KeyRound, MessageCircle, RefreshCw, ShieldCheck, Unplug } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { newAuth } from '@/lib/auth_new';


type SenderAccount = {
  id: string;
  channel?: string;
  sender_identity?: string | null;
  display_name?: string | null;
  status?: string;
  outreach_enabled?: boolean;
  reply_sync_enabled?: boolean;
  health_status?: string;
  health_score?: number;
  reply_sync_error?: string | null;
  capabilities?: {
    account_kind?: string;
    provider?: string;
    group_id?: string;
    profile_url?: string;
    avatar_url?: string | null;
  };
};

type OutreachVkSetupProps = {
  businessId?: string | null;
  scopeType?: 'business' | 'platform';
  compact?: boolean;
  onChanged?: () => void;
};

const accountStatusCopy = (account: SenderAccount) => {
  if (account.status !== 'connected') return 'Отключён';
  if (account.health_status === 'blocked' || account.health_status === 'paused') return 'Отправка приостановлена';
  if (account.reply_sync_error) return 'Нужно проверить ответы';
  if (!account.outreach_enabled) return 'Подключён без права отправки';
  return 'Готов к аутричу';
};

export const OutreachVkSetup = ({
  businessId = null,
  scopeType = 'business',
  compact = false,
  onChanged,
}: OutreachVkSetupProps) => {
  const [accounts, setAccounts] = useState<SenderAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [communityUrl, setCommunityUrl] = useState(scopeType === 'platform' ? 'https://vk.ru/localospro' : '');
  const [accessKey, setAccessKey] = useState('');

  const loadAccounts = useCallback(async () => {
    if (scopeType === 'business' && !businessId) {
      setAccounts([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const query = new URLSearchParams({ scope_type: scopeType });
      if (businessId) query.set('business_id', businessId);
      const payload = await newAuth.makeRequest(`/outreach/sender-accounts?${query.toString()}`);
      const nextAccounts = Array.isArray(payload?.sender_accounts) ? payload.sender_accounts : [];
      setAccounts(nextAccounts.filter((item: SenderAccount) => item.channel === 'vk'));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить VK');
    } finally {
      setLoading(false);
    }
  }, [businessId, scopeType]);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  const account = accounts.find((item) => item.status === 'connected') || accounts[0] || null;
  const senderNameNeedsReview = scopeType === 'platform'
    && Boolean(account?.display_name)
    && !String(account?.display_name || '').toLowerCase().includes('localos');

  const connect = async () => {
    if (!communityUrl.trim() || !accessKey.trim()) {
      setError('Укажите ссылку на сообщество и вставьте ключ с правом на сообщения.');
      return;
    }
    setBusy('connect');
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest('/outreach/sender-accounts/vk/community/connect', {
        method: 'POST',
        body: JSON.stringify({
          scope_type: scopeType,
          business_id: businessId || null,
          community_url: communityUrl.trim(),
          access_token: accessKey.trim(),
        }),
      });
      setAccessKey('');
      setNotice(payload?.message || 'Собщество VK подключено без права отправки.');
      await loadAccounts();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось подключить сообщество VK');
    } finally {
      setBusy('');
    }
  };

  const preflight = async () => {
    if (!account) return;
    setBusy('preflight');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest(`/outreach/sender-accounts/${encodeURIComponent(account.id)}/preflight`, { method: 'POST' });
      setNotice('Сообщения сообщества и проверка ответов доступны. Тестовое сообщение не отправлялось.');
      await loadAccounts();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Проверка VK не пройдена');
    } finally {
      setBusy('');
    }
  };

  const changePermission = async (enabled: boolean) => {
    if (!account) return;
    if (enabled && !window.confirm(`Получатели увидят отправителя «${account.display_name || 'VK-сообщество'}». Разрешить одобренные отправки?`)) return;
    setBusy('permission');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest(`/outreach/sender-accounts/${encodeURIComponent(account.id)}/permission`, {
        method: 'PATCH',
        body: JSON.stringify({ outreach_enabled: enabled }),
      });
      setNotice(enabled
        ? 'Отправка разрешена. LocalOS будет проверять ответы перед каждым следующим касанием.'
        : 'Новые VK-касания остановлены. Черновики сохранены.');
      await loadAccounts();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось изменить разрешение VK');
    } finally {
      setBusy('');
    }
  };

  const disconnect = async () => {
    if (!account || !window.confirm('Отключить VK для аутрича? Будущие VK-касания будут поставлены на паузу.')) return;
    setBusy('disconnect');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest(`/outreach/sender-accounts/${encodeURIComponent(account.id)}`, { method: 'DELETE' });
      setNotice('VK отключён. Кампании не переключались на другой аккаунт.');
      await loadAccounts();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось отключить VK');
    } finally {
      setBusy('');
    }
  };

  return (
    <section className={compact ? 'space-y-4' : 'rounded-2xl bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_2px_4px_rgba(15,23,42,0.04)]'}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-slate-700" />
            <h3 className="text-balance text-base font-semibold text-slate-950">VK-сообщество для аутрича</h3>
          </div>
          <p className="mt-1 max-w-2xl text-pretty text-sm leading-6 text-slate-600">
            Получатель увидит название и аватар сообщества. После подключения отправка всё равно включается отдельно.
          </p>
        </div>
        {account ? (
          <Badge variant="outline" className={account.outreach_enabled && !account.reply_sync_error
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
            : 'border-amber-200 bg-amber-50 text-amber-800'}>
            {accountStatusCopy(account)}
          </Badge>
        ) : null}
      </div>

      {loading ? (
        <div className="mt-4 flex min-h-11 items-center gap-2 text-sm text-slate-500">
          <RefreshCw className="h-4 w-4 animate-spin" /> Проверяем подключение…
        </div>
      ) : account ? (
        <div className="mt-5 divide-y divide-slate-100">
          <div className="flex flex-col gap-3 pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              {account.capabilities?.avatar_url ? (
                <img src={account.capabilities.avatar_url} alt="" className="h-11 w-11 rounded-full object-cover shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]" />
              ) : (
                <div className="grid h-11 w-11 place-items-center rounded-full bg-slate-100 text-slate-600"><MessageCircle className="h-5 w-5" /></div>
              )}
              <div className="min-w-0">
                <div className="truncate font-semibold text-slate-950">{account.display_name || `VK-сообщество ${account.sender_identity}`}</div>
                {account.capabilities?.profile_url ? (
                  <a href={account.capabilities.profile_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex min-h-6 items-center gap-1 text-sm text-blue-700 hover:text-blue-800">
                    Открыть сообщество <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : null}
              <div className="mt-2 text-xs text-slate-500">
                Состояние отправителя: {account.health_status || 'healthy'} · <span className="tabular-nums">{account.health_score ?? 100}/100</span>
              </div>
              </div>
            </div>
            <Button variant="outline" onClick={() => void preflight()} disabled={Boolean(busy)} className="min-h-11 active:scale-[0.96] transition-transform">
              {busy === 'preflight' ? <RefreshCw className="animate-spin" /> : <ShieldCheck />}
              Проверить без отправки
            </Button>
          </div>

          {senderNameNeedsReview ? (
            <div className="flex gap-3 py-4 text-sm text-amber-950">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
              <div>
                <div className="font-semibold">Получатели увидят «{account.display_name}»</div>
                <p className="mt-1 text-pretty leading-6">Для аутрича LocalOS лучше сначала переименовать сообщество. Текущее имя будет показано в каждом диалоге.</p>
              </div>
            </div>
          ) : null}

          <div className="flex items-start justify-between gap-4 py-4">
            <div>
              <Label htmlFor={`vk-outreach-${account.id}`} className="text-sm font-semibold text-slate-900">Сообщения от имени сообщества</Label>
              <p className="mt-1 max-w-xl text-pretty text-sm leading-6 text-slate-600">
                Только одобренные сообщения. LocalOS проверяет ответы лишь в диалогах, куда отправляла эта кампания, и останавливает остальные каналы после ответа.
              </p>
              <p className="mt-2 max-w-xl text-pretty text-xs leading-5 text-slate-500">
                VK может запретить первое сообщение, если получатель не разрешил сообщения от сообществ. Такой контакт не будет обходиться скрыто через другой VK-аккаунт.
              </p>
            </div>
            <Switch
              id={`vk-outreach-${account.id}`}
              checked={Boolean(account.outreach_enabled)}
              disabled={Boolean(busy) || account.status !== 'connected'}
              onCheckedChange={(checked) => void changePermission(checked)}
              className="mt-1 shrink-0"
            />
          </div>

          {account.reply_sync_error ? (
            <div className="flex gap-3 py-4 text-sm text-amber-900">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <div className="font-semibold">Ответы сейчас не проверяются</div>
                <p className="mt-1 text-pretty leading-6">Новые отправки заблокированы до успешной проверки подключения.</p>
              </div>
            </div>
          ) : null}

          <div className="flex flex-col-reverse gap-2 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <Button variant="ghost" onClick={() => void disconnect()} disabled={Boolean(busy)} className="min-h-10 px-3 text-slate-600 hover:text-rose-700">
              {busy === 'disconnect' ? <RefreshCw className="animate-spin" /> : <Unplug />}
              Отключить VK-аутрич
            </Button>
            <span className="text-xs text-slate-500">Ключ хранится в зашифрованном виде</span>
          </div>
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <div className="rounded-xl bg-slate-50 px-4 py-4 text-slate-700">
            <div className="flex items-start gap-3 text-pretty text-sm leading-6">
              <KeyRound className="mt-0.5 h-5 w-5 shrink-0 text-slate-600" />
              <div>
                <div className="font-semibold text-slate-900">Создайте ключ в управлении сообществом</div>
                <p className="mt-1">Откройте «Управление → Работа с API → Ключи доступа» и разрешите доступ к сообщениям. LocalOS проверит ключ, но ничего не отправит.</p>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="vk-community-url">Ссылка на сообщество</Label>
            <Input id="vk-community-url" value={communityUrl} onChange={(event) => setCommunityUrl(event.target.value)} placeholder="https://vk.ru/mybusiness" className="min-h-11" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="vk-community-key">Ключ доступа с правом на сообщения</Label>
            <Input id="vk-community-key" type="password" autoComplete="off" value={accessKey} onChange={(event) => setAccessKey(event.target.value)} placeholder="Вставьте ключ VK" className="min-h-11" />
            <p className="text-xs leading-5 text-slate-500">Ключ зашифруется и не будет показан после подключения.</p>
          </div>
          <Button onClick={() => void connect()} disabled={Boolean(busy) || (scopeType === 'business' && !businessId)} className="min-h-11 bg-slate-900 text-white hover:bg-slate-800 active:scale-[0.96] transition-transform">
              {busy === 'connect' ? <RefreshCw className="animate-spin" /> : <MessageCircle />}
              Проверить и подключить
          </Button>
        </div>
      )}

      {notice ? <div className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-pretty text-sm leading-6 text-emerald-900">{notice}</div> : null}
      {error ? <div className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-pretty text-sm leading-6 text-rose-900">{error}</div> : null}
    </section>
  );
};
