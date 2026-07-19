import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Mail, RefreshCw, ShieldCheck, Unplug } from 'lucide-react';

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
  last_reply_sync_at?: string | null;
  reply_sync_error?: string | null;
};

type OutreachEmailSetupProps = {
  businessId?: string | null;
  scopeType?: 'business' | 'platform';
  compact?: boolean;
  onChanged?: () => void;
};

type MailboxForm = {
  email: string;
  display_name: string;
  username: string;
  password: string;
  smtp_host: string;
  smtp_port: string;
  smtp_security: 'ssl' | 'starttls';
  imap_host: string;
  imap_port: string;
  imap_security: 'ssl' | 'starttls';
};

const emptyForm: MailboxForm = {
  email: '',
  display_name: '',
  username: '',
  password: '',
  smtp_host: '',
  smtp_port: '465',
  smtp_security: 'ssl',
  imap_host: '',
  imap_port: '993',
  imap_security: 'ssl',
};

const accountStatusCopy = (account: SenderAccount) => {
  if (account.status !== 'connected') return 'Отключён';
  if (account.health_status === 'blocked' || account.health_status === 'paused') return 'Отправка приостановлена';
  if (account.reply_sync_error) return 'Нужно проверить ответы';
  if (!account.outreach_enabled) return 'Подключён без права отправки';
  return 'Готов к аутричу';
};

export const OutreachEmailSetup = ({
  businessId = null,
  scopeType = 'business',
  compact = false,
  onChanged,
}: OutreachEmailSetupProps) => {
  const [accounts, setAccounts] = useState<SenderAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [form, setForm] = useState<MailboxForm>(emptyForm);
  const [preflightReady, setPreflightReady] = useState(false);
  const [enableOutreachOnConnect, setEnableOutreachOnConnect] = useState(false);

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
      setAccounts(nextAccounts.filter((item: SenderAccount) => item.channel === 'email'));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить email');
    } finally {
      setLoading(false);
    }
  }, [businessId, scopeType]);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  const account = accounts.find((item) => item.status === 'connected') || accounts[0] || null;

  const updateField = (key: keyof MailboxForm, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    setPreflightReady(false);
    setNotice('');
  };

  const mailboxPayload = () => ({
    ...form,
    username: form.username.trim() || form.email.trim(),
    smtp_port: Number(form.smtp_port),
    imap_port: Number(form.imap_port),
  });

  const runNewPreflight = async () => {
    setBusy('preflight-new');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest('/outreach/sender-accounts/email/preflight', {
        method: 'POST',
        body: JSON.stringify({
          scope_type: scopeType,
          business_id: businessId,
          mailbox: mailboxPayload(),
        }),
      });
      setPreflightReady(true);
      setNotice('SMTP и проверка ответов работают. Письмо не отправлялось.');
    } catch (requestError) {
      setPreflightReady(false);
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить почту');
    } finally {
      setBusy('');
    }
  };

  const connect = async () => {
    if (!preflightReady) return;
    setBusy('connect');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest('/outreach/sender-accounts/email', {
        method: 'POST',
        body: JSON.stringify({
          scope_type: scopeType,
          business_id: businessId,
          outreach_enabled: enableOutreachOnConnect,
          mailbox: mailboxPayload(),
        }),
      });
      setForm(emptyForm);
      setPreflightReady(false);
      setNotice(enableOutreachOnConnect
        ? 'Email подключён. LocalOS сможет отправлять только подтверждённые цепочки и остановит их после ответа.'
        : 'Email подключён без права отправки. Разрешение можно включить отдельно.');
      await loadAccounts();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось подключить email');
    } finally {
      setBusy('');
    }
  };

  const preflightExisting = async () => {
    if (!account) return;
    setBusy('preflight-existing');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest(`/outreach/sender-accounts/${encodeURIComponent(account.id)}/preflight`, {
        method: 'POST',
      });
      setNotice('Отправка и проверка ответов доступны. Тестовое письмо не отправлялось.');
      await loadAccounts();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Проверка не пройдена');
    } finally {
      setBusy('');
    }
  };

  const changePermission = async (enabled: boolean) => {
    if (!account) return;
    setBusy('permission');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest(`/outreach/sender-accounts/${encodeURIComponent(account.id)}/permission`, {
        method: 'PATCH',
        body: JSON.stringify({ outreach_enabled: enabled }),
      });
      setNotice(enabled
        ? 'Отправка разрешена. Проверка ответов включена автоматически.'
        : 'Новые email-касания остановлены. Черновики сохранены.');
      await loadAccounts();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось изменить разрешение');
    } finally {
      setBusy('');
    }
  };

  const disconnect = async () => {
    if (!account || !window.confirm('Отключить email? Будущие касания этого отправителя будут поставлены на паузу.')) return;
    setBusy('disconnect');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest(`/outreach/sender-accounts/${encodeURIComponent(account.id)}`, {
        method: 'DELETE',
      });
      setNotice('Email отключён. Связанные кампании не переключались на другой адрес.');
      await loadAccounts();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось отключить email');
    } finally {
      setBusy('');
    }
  };

  return (
    <section className={compact ? 'space-y-4' : 'rounded-2xl bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_2px_4px_rgba(15,23,42,0.04)]'}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-slate-700" />
            <h3 className="text-balance text-base font-semibold text-slate-950">Email для аутрича</h3>
          </div>
          <p className="mt-1 max-w-2xl text-pretty text-sm leading-6 text-slate-600">
            LocalOS отправляет только подтверждённые сообщения и проверяет входящие ответы перед следующим касанием.
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
            <div>
              <div className="font-semibold text-slate-950">{account.display_name || account.sender_identity}</div>
              {account.display_name ? <div className="mt-1 text-sm text-slate-500">{account.sender_identity}</div> : null}
              <div className="mt-2 text-xs text-slate-500">
                Здоровье отправителя: {account.health_status || 'healthy'} · <span className="tabular-nums">{account.health_score ?? 100}/100</span>
              </div>
            </div>
            <Button variant="outline" onClick={() => void preflightExisting()} disabled={Boolean(busy)} className="min-h-11">
              {busy === 'preflight-existing' ? <RefreshCw className="animate-spin" /> : <ShieldCheck />}
              Проверить без отправки
            </Button>
          </div>

          <div className="flex items-start justify-between gap-4 py-4">
            <div>
              <Label htmlFor={`email-outreach-${account.id}`} className="text-sm font-semibold text-slate-900">Сообщения от вашего имени</Label>
              <p className="mt-1 max-w-xl text-pretty text-sm leading-6 text-slate-600">
                Включает отправку одобренных цепочек и обязательную проверку ответов. Отключение сразу поставит будущие email-касания на паузу.
              </p>
            </div>
            <Switch
              id={`email-outreach-${account.id}`}
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
                <p className="mt-1 text-pretty leading-6">Новые автоматические отправки будут остановлены до успешной проверки подключения.</p>
              </div>
            </div>
          ) : null}

          <div className="pt-4">
            <Button variant="ghost" onClick={() => void disconnect()} disabled={Boolean(busy)} className="min-h-10 px-3 text-slate-600 hover:text-rose-700">
              {busy === 'disconnect' ? <RefreshCw className="animate-spin" /> : <Unplug />}
              Отключить email
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="outreach-email-address">Email отправителя</Label>
              <Input id="outreach-email-address" type="email" value={form.email} onChange={(event) => updateField('email', event.target.value)} placeholder="founder@company.ru" className="mt-2 h-11" autoComplete="email" />
            </div>
            <div>
              <Label htmlFor="outreach-email-name">Имя отправителя</Label>
              <Input id="outreach-email-name" value={form.display_name} onChange={(event) => updateField('display_name', event.target.value)} placeholder="Имя и роль" className="mt-2 h-11" />
            </div>
            <div>
              <Label htmlFor="outreach-email-login">Логин почты</Label>
              <Input id="outreach-email-login" value={form.username} onChange={(event) => updateField('username', event.target.value)} placeholder="Обычно совпадает с email" className="mt-2 h-11" autoComplete="username" />
            </div>
            <div>
              <Label htmlFor="outreach-email-password">Пароль приложения</Label>
              <Input id="outreach-email-password" type="password" value={form.password} onChange={(event) => updateField('password', event.target.value)} placeholder="Хранится в зашифрованном виде" className="mt-2 h-11" autoComplete="new-password" />
            </div>
          </div>

          <details className="rounded-xl bg-slate-50 px-4 py-3">
            <summary className="flex min-h-10 cursor-pointer items-center text-sm font-semibold text-slate-800">Серверы отправки и входящих писем</summary>
            <div className="grid gap-4 pt-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="outreach-smtp-host">SMTP-сервер</Label>
                <Input id="outreach-smtp-host" value={form.smtp_host} onChange={(event) => updateField('smtp_host', event.target.value)} placeholder="smtp.provider.ru" className="mt-2 h-11 bg-white" />
              </div>
              <div className="grid grid-cols-[1fr_1.25fr] gap-2">
                <div>
                  <Label htmlFor="outreach-smtp-port">Порт</Label>
                  <Input id="outreach-smtp-port" inputMode="numeric" value={form.smtp_port} onChange={(event) => updateField('smtp_port', event.target.value)} className="mt-2 h-11 bg-white tabular-nums" />
                </div>
                <div>
                  <Label htmlFor="outreach-smtp-security">Защита</Label>
                  <select id="outreach-smtp-security" value={form.smtp_security} onChange={(event) => updateField('smtp_security', event.target.value)} className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400">
                    <option value="ssl">SSL</option>
                    <option value="starttls">STARTTLS</option>
                  </select>
                </div>
              </div>
              <div>
                <Label htmlFor="outreach-imap-host">IMAP-сервер</Label>
                <Input id="outreach-imap-host" value={form.imap_host} onChange={(event) => updateField('imap_host', event.target.value)} placeholder="imap.provider.ru" className="mt-2 h-11 bg-white" />
              </div>
              <div className="grid grid-cols-[1fr_1.25fr] gap-2">
                <div>
                  <Label htmlFor="outreach-imap-port">Порт</Label>
                  <Input id="outreach-imap-port" inputMode="numeric" value={form.imap_port} onChange={(event) => updateField('imap_port', event.target.value)} className="mt-2 h-11 bg-white tabular-nums" />
                </div>
                <div>
                  <Label htmlFor="outreach-imap-security">Защита</Label>
                  <select id="outreach-imap-security" value={form.imap_security} onChange={(event) => updateField('imap_security', event.target.value)} className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400">
                    <option value="ssl">SSL</option>
                    <option value="starttls">STARTTLS</option>
                  </select>
                </div>
              </div>
            </div>
          </details>

          <div className="flex items-start gap-3 rounded-xl bg-amber-50 px-4 py-3">
            <Switch id="enable-email-outreach-on-connect" checked={enableOutreachOnConnect} onCheckedChange={setEnableOutreachOnConnect} className="mt-0.5 shrink-0" />
            <div>
              <Label htmlFor="enable-email-outreach-on-connect" className="font-semibold text-amber-950">Разрешить отправку сообщений</Label>
              <p className="mt-1 text-pretty text-sm leading-6 text-amber-900">Письма уходят от этого адреса только после подтверждения всей кампании. LocalOS будет проверять ответы и остановит следующие каналы.</p>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <Button variant="outline" onClick={() => void runNewPreflight()} disabled={Boolean(busy) || !form.email || !form.password || !form.smtp_host || !form.imap_host} className="min-h-11">
              {busy === 'preflight-new' ? <RefreshCw className="animate-spin" /> : <ShieldCheck />}
              Проверить без отправки
            </Button>
            <Button onClick={() => void connect()} disabled={Boolean(busy) || !preflightReady} className="min-h-11 bg-slate-950 text-white hover:bg-slate-800">
              {busy === 'connect' ? <RefreshCw className="animate-spin" /> : <CheckCircle2 />}
              Подключить email
            </Button>
          </div>
        </div>
      )}

      {notice ? <div aria-live="polite" className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-pretty text-sm leading-6 text-emerald-900">{notice}</div> : null}
      {error ? <div role="alert" className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-pretty text-sm leading-6 text-rose-900">{error}</div> : null}
    </section>
  );
};

export default OutreachEmailSetup;
