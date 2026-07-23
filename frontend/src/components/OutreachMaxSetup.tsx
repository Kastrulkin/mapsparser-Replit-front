import { useCallback, useEffect, useState } from 'react';
import { ExternalLink, MessageCircle, RefreshCw, ShieldCheck, Unplug } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { newAuth } from '@/lib/auth_new';

type SenderAccount = {
  id: string;
  channel?: string;
  sender_identity?: string | null;
  display_name?: string | null;
  status?: string;
  capabilities?: {
    manual_handoff?: boolean;
    direct_send?: boolean;
    reply_sync?: boolean;
  };
};

type OutreachMaxSetupProps = {
  businessId?: string | null;
  scopeType?: 'business' | 'platform';
  compact?: boolean;
  onChanged?: () => void;
};

export const OutreachMaxSetup = ({
  businessId = null,
  scopeType = 'business',
  compact = false,
  onChanged,
}: OutreachMaxSetupProps) => {
  const [accounts, setAccounts] = useState<SenderAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [phone, setPhone] = useState(scopeType === 'platform' ? '+79214224843' : '');
  const [displayName, setDisplayName] = useState(scopeType === 'platform' ? 'LocalOS · MAX' : '');

  const loadAccounts = useCallback(async () => {
    if (scopeType === 'business' && !businessId) {
      setAccounts([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({ scope_type: scopeType });
      if (businessId) query.set('business_id', businessId);
      const payload = await newAuth.makeRequest(`/outreach/sender-accounts?${query.toString()}`);
      const nextAccounts = Array.isArray(payload?.sender_accounts) ? payload.sender_accounts : [];
      setAccounts(nextAccounts.filter((item: SenderAccount) => item.channel === 'max'));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить MAX');
    } finally {
      setLoading(false);
    }
  }, [businessId, scopeType]);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  const account = accounts.find((item) => item.status === 'connected') || accounts[0] || null;

  const connect = async () => {
    if (!phone.trim()) {
      setError('Укажите номер, на который зарегистрирован аккаунт MAX.');
      return;
    }
    setBusy('connect');
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest('/outreach/sender-accounts/max/manual', {
        method: 'POST',
        body: JSON.stringify({
          scope_type: scopeType,
          business_id: businessId || null,
          phone: phone.trim(),
          display_name: displayName.trim() || null,
        }),
      });
      setNotice(payload?.message || 'MAX добавлен в ручном режиме.');
      await loadAccounts();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось добавить MAX');
    } finally {
      setBusy('');
    }
  };

  const disconnect = async () => {
    if (!account || !window.confirm('Убрать MAX из каналов аутрича? Черновики сохранятся.')) return;
    setBusy('disconnect');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest(`/outreach/sender-accounts/${encodeURIComponent(account.id)}`, { method: 'DELETE' });
      setNotice('MAX отключён. Черновики и история сохранены.');
      await loadAccounts();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось отключить MAX');
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
            <h3 className="text-balance text-base font-semibold text-slate-950">MAX для аутрича</h3>
          </div>
          <p className="mt-1 max-w-2xl text-pretty text-sm leading-6 text-slate-600">
            LocalOS готовит сообщение и хранит историю, а вы отправляете его в приложении MAX.
          </p>
        </div>
        {account?.status === 'connected' ? (
          <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-800">Ручной режим</Badge>
        ) : null}
      </div>

      {loading ? (
        <div className="mt-4 flex min-h-11 items-center gap-2 text-sm text-slate-500">
          <RefreshCw className="h-4 w-4 animate-spin" /> Проверяем подключение…
        </div>
      ) : account?.status === 'connected' ? (
        <div className="mt-5 space-y-4">
          <div className="rounded-2xl bg-slate-50 px-4 py-4 ring-1 ring-slate-200">
            <div className="flex items-start gap-3">
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white text-slate-700 ring-1 ring-slate-200">
                <MessageCircle className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="truncate font-semibold text-slate-950">{account.display_name || 'MAX'}</div>
                <div className="mt-1 font-mono text-sm tabular-nums text-slate-600">{account.sender_identity}</div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl bg-sky-50 px-4 py-4 text-sky-950 ring-1 ring-sky-100">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-sky-700" />
              <div>
                <div className="font-semibold">Автоотправка выключена</div>
                <p className="mt-1 text-pretty text-sm leading-6">
                  Официальный API MAX работает с ботами, а не с личными аккаунтами по номеру. Поэтому LocalOS не читает личные диалоги и ничего не отправляет сам.
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
            <Button variant="ghost" onClick={() => void disconnect()} disabled={Boolean(busy)} className="min-h-10 px-3 text-slate-600 hover:text-rose-700 active:scale-[0.96] transition-transform">
              {busy === 'disconnect' ? <RefreshCw className="animate-spin" /> : <Unplug />}
              Отключить MAX
            </Button>
            <a href="https://dev.max.ru/docs-api" target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-1.5 text-sm text-blue-700 hover:text-blue-800">
              Как работает API MAX <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <div className="rounded-2xl bg-slate-50 px-4 py-4 text-pretty text-sm leading-6 text-slate-700 ring-1 ring-slate-200">
            Добавьте номер MAX как ручной канал. Он появится в цепочках, если у лида найден MAX-контакт. После отправки вы отметите касание или ответ в LocalOS.
          </div>
          <div className="space-y-2">
            <Label htmlFor="max-outreach-phone">Номер аккаунта MAX</Label>
            <Input id="max-outreach-phone" inputMode="tel" autoComplete="tel" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+7 999 123-45-67" className="min-h-11" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max-outreach-name">Как показать аккаунт в LocalOS</Label>
            <Input id="max-outreach-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Например, LocalOS · MAX" className="min-h-11" />
          </div>
          <Button onClick={() => void connect()} disabled={Boolean(busy) || (scopeType === 'business' && !businessId)} className="min-h-11 bg-slate-900 text-white hover:bg-slate-800 active:scale-[0.96] transition-transform">
            {busy === 'connect' ? <RefreshCw className="animate-spin" /> : <MessageCircle />}
            Добавить MAX
          </Button>
        </div>
      )}

      {notice ? <div className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-pretty text-sm leading-6 text-emerald-900">{notice}</div> : null}
      {error ? <div className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-pretty text-sm leading-6 text-rose-900">{error}</div> : null}
    </section>
  );
};
