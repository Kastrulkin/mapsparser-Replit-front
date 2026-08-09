import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, ChevronRight, DatabaseZap, Loader2, RefreshCw, ShieldCheck } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

import { mobileAuthHeaders, mobileJsonHeaders, readMobileJson } from '@/lib/mobileDataClient';

type CrmConnection = {
  status?: string;
  last_sync_at?: string | null;
  sync_status?: string | null;
};

type CrmProvider = {
  provider: string;
  label: string;
  description?: string;
  status?: string;
  requires_auth?: boolean;
  api_base_url?: string;
  connection?: CrmConnection | null;
};

type CrmCredentials = {
  partner_token?: string;
  user_token?: string;
  location_id?: string;
};

type CrmPreview = {
  provider?: string;
  preview_token?: string;
  period?: { start_date?: string; end_date?: string };
  dataset_counts?: Record<string, number>;
  rows_total?: number;
  valid_rows?: number;
  failed_rows?: number;
  preview_rows?: Array<Record<string, unknown>>;
};

type FinanceCrmMobilePanelProps = {
  businessId: string;
  onSynced: () => Promise<void>;
  previewMode?: boolean;
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };

const isoDate = (date: Date) => date.toISOString().slice(0, 10);

const periodFor = (preset: string) => {
  const end = new Date();
  const start = new Date(end);
  if (preset === 'today') return { start: isoDate(start), end: isoDate(end) };
  start.setDate(start.getDate() - (preset === '7_days' ? 6 : 29));
  return { start: isoDate(start), end: isoDate(end) };
};

const syncLabel = (connection?: CrmConnection | null) => {
  if (!connection) return 'Не подключена';
  if (connection.sync_status === 'failed' || connection.sync_status === 'preview_failed') return 'Нужно внимание';
  if (connection.last_sync_at) return `Обновлено ${new Date(connection.last_sync_at).toLocaleDateString('ru-RU')}`;
  return 'Подключена';
};

const previewRowLabel = (row: Record<string, unknown>) => {
  const values = Object.values(row).filter((value) => value !== null && value !== undefined && String(value).trim());
  return values.slice(0, 3).map((value) => String(value)).join(' · ');
};

const previewProviders: CrmProvider[] = [
  { provider: 'yclients', label: 'YCLIENTS', status: 'available', requires_auth: true, connection: { status: 'connected', sync_status: 'never_synced' } },
  { provider: 'altegio', label: 'Altegio', status: 'available', requires_auth: true, connection: null },
];

const FinanceCrmMobilePanel = ({ businessId, onSynced, previewMode = false }: FinanceCrmMobilePanelProps) => {
  const [providers, setProviders] = useState<CrmProvider[]>(previewMode ? previewProviders : []);
  const [openedProvider, setOpenedProvider] = useState('');
  const [credentials, setCredentials] = useState<Record<string, CrmCredentials>>({});
  const [preset, setPreset] = useState('today');
  const [period, setPeriod] = useState(() => periodFor('today'));
  const [previews, setPreviews] = useState<Record<string, CrmPreview>>({});
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadProviders = useCallback(async () => {
    if (!businessId || previewMode) return;
    try {
      const result = await fetch(`/api/finance/crm/providers?business_id=${encodeURIComponent(businessId)}`, { headers: mobileAuthHeaders() })
        .then(readMobileJson<{ providers?: CrmProvider[] }>);
      setProviders((result.providers || []).filter((provider) => provider.provider !== 'mock_demo' && provider.status === 'available'));
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить CRM.');
    }
  }, [businessId, previewMode]);

  useEffect(() => { void loadProviders(); }, [loadProviders]);

  const connectedProviders = useMemo(() => providers.filter((provider) => provider.connection?.status === 'connected'), [providers]);

  const choosePeriod = (value: string) => {
    setPreset(value);
    if (value !== 'custom') setPeriod(periodFor(value));
    setPreviews({});
  };

  const updateCredential = (provider: string, field: keyof CrmCredentials, value: string) => {
    setCredentials((current) => ({ ...current, [provider]: { ...current[provider], [field]: value } }));
  };

  const connect = async (provider: CrmProvider) => {
    const values = credentials[provider.provider] || {};
    if (provider.requires_auth && (!values.partner_token || !values.user_token || !values.location_id)) {
      setError('Заполните ID филиала, partner token и user token.');
      return;
    }
    setBusy(`connect:${provider.provider}`);
    setMessage('');
    setError('');
    try {
      await fetch('/api/finance/crm/connect', {
        method: 'POST',
        headers: mobileJsonHeaders(),
        body: JSON.stringify({
          business_id: businessId,
          provider: provider.provider,
          display_name: provider.label,
          auth_data: provider.requires_auth ? {
            partner_token: values.partner_token,
            user_token: values.user_token,
            api_base_url: provider.api_base_url,
          } : {},
          settings: provider.requires_auth ? { location_id: values.location_id } : {},
        }),
      }).then(readMobileJson);
      setCredentials((current) => ({ ...current, [provider.provider]: {} }));
      setMessage(`${provider.label} подключена. Теперь можно проверить данные.`);
      await loadProviders();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось подключить CRM.');
    } finally {
      setBusy('');
    }
  };

  const inspect = async (provider: CrmProvider) => {
    setBusy(`preview:${provider.provider}`);
    setMessage('');
    setError('');
    try {
      const result = await fetch('/api/finance/crm/preview', {
        method: 'POST',
        headers: mobileJsonHeaders(),
        body: JSON.stringify({ business_id: businessId, provider: provider.provider, from: period.start, to: period.end, sample_limit: 5 }),
      }).then(readMobileJson<CrmPreview>);
      setPreviews((current) => ({ ...current, [provider.provider]: result }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить данные CRM.');
    } finally {
      setBusy('');
    }
  };

  const confirm = async (provider: CrmProvider) => {
    const preview = previews[provider.provider];
    if (!preview?.preview_token) return;
    setBusy(`sync:${provider.provider}`);
    setMessage('');
    setError('');
    try {
      const result = await fetch('/api/finance/crm/sync', {
        method: 'POST',
        headers: mobileJsonHeaders(),
        body: JSON.stringify({
          business_id: businessId,
          provider: provider.provider,
          confirm_preview_token: preview.preview_token,
          period_start: preview.period?.start_date || period.start,
          period_end: preview.period?.end_date || period.end,
        }),
      }).then(readMobileJson<{ rows_imported?: number; rows_skipped?: number; rows_failed?: number; requires_preview?: boolean }>);
      setPreviews((current) => {
        const next = { ...current };
        delete next[provider.provider];
        return next;
      });
      setMessage(`Готово: загружено ${result.rows_imported || 0}, дубли ${result.rows_skipped || 0}, ошибки ${result.rows_failed || 0}.`);
      await Promise.all([loadProviders(), onSynced()]);
    } catch (requestError) {
      setPreviews((current) => {
        const next = { ...current };
        delete next[provider.provider];
        return next;
      });
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить данные CRM.');
    } finally {
      setBusy('');
    }
  };

  return (
    <section className="rounded-[24px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]">
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/15 text-primary"><DatabaseZap className="h-5 w-5" /></span>
        <div className="min-w-0 flex-1">
          <b className="block text-balance text-base">Загрузить данные из CRM</b>
          <p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">ЛокалОС перенесёт записи, оплаты, услуги и загрузку команды. Сначала вы увидите проверку, и только потом подтвердите импорт.</p>
        </div>
      </div>

      {error ? <p role="alert" className="mt-3 rounded-[16px] bg-rose-500/10 p-3 text-pretty text-xs leading-5 text-rose-200 ring-1 ring-inset ring-rose-400/20">{error}</p> : null}
      {message ? <p className="mt-3 rounded-[16px] bg-emerald-500/10 p-3 text-pretty text-xs leading-5 text-emerald-200 ring-1 ring-inset ring-emerald-400/20">{message}</p> : null}

      {connectedProviders.length ? (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-3 gap-1 rounded-[16px] bg-black/20 p-1 ring-1 ring-inset ring-white/[0.06]">
            {[['today', 'Сегодня'], ['7_days', '7 дней'], ['30_days', '30 дней']].map(([value, label]) => <button type="button" key={value} onClick={() => choosePeriod(value)} className={`min-h-11 rounded-[12px] px-2 text-[11px] font-semibold transition-[background-color,color,transform] active:scale-[0.96] ${preset === value ? 'bg-white/[0.1] text-white shadow-[0_4px_14px_rgba(0,0,0,0.2)]' : 'text-zinc-600'}`}>{label}</button>)}
          </div>
          <button type="button" onClick={() => choosePeriod('custom')} className="min-h-11 w-full rounded-[14px] text-xs text-zinc-500 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">{preset === 'custom' ? 'Свой период' : `Период: ${period.start} — ${period.end}`}</button>
          {preset === 'custom' ? <div className="grid grid-cols-2 gap-2"><input aria-label="Начало периода CRM" type="date" value={period.start} onChange={(event) => { setPeriod((current) => ({ ...current, start: event.target.value })); setPreviews({}); }} className="min-h-11 min-w-0 rounded-[14px] bg-zinc-900 px-2 text-xs ring-1 ring-inset ring-white/[0.07]" /><input aria-label="Конец периода CRM" type="date" value={period.end} onChange={(event) => { setPeriod((current) => ({ ...current, end: event.target.value })); setPreviews({}); }} className="min-h-11 min-w-0 rounded-[14px] bg-zinc-900 px-2 text-xs ring-1 ring-inset ring-white/[0.07]" /></div> : null}
        </div>
      ) : null}

      <div className="mt-4 space-y-2">
        {providers.map((provider) => {
          const connected = provider.connection?.status === 'connected';
          const opened = openedProvider === provider.provider;
          const preview = previews[provider.provider];
          const providerBusy = busy.endsWith(provider.provider);
          return (
            <article key={provider.provider} className="overflow-hidden rounded-[18px] bg-black/20 ring-1 ring-inset ring-white/[0.06]">
              <button type="button" aria-expanded={opened} onClick={() => setOpenedProvider(opened ? '' : provider.provider)} className="flex min-h-16 w-full items-center gap-3 px-4 text-left active:scale-[0.99]">
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-[12px] ${connected ? 'bg-emerald-500/10 text-emerald-300' : 'bg-white/[0.05] text-zinc-500'}`}>{connected ? <Check className="h-4 w-4" /> : <DatabaseZap className="h-4 w-4" />}</span>
                <span className="min-w-0 flex-1"><b className="block text-sm">{provider.label}</b><small className={`mt-1 block truncate ${connected ? 'text-emerald-300/70' : 'text-zinc-600'}`}>{syncLabel(provider.connection)}</small></span>
                <ChevronRight className={`h-4 w-4 text-zinc-600 transition-transform ${opened ? 'rotate-90' : ''}`} />
              </button>
              <AnimatePresence initial={false}>
                {opened ? <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={spring} className="overflow-hidden"><div className="border-t border-white/[0.06] p-4">
                  {connected ? <>
                    <p className="text-pretty text-xs leading-5 text-zinc-500">Проверьте, какие данные будут добавлены за выбранный период. Повторные записи ЛокалОС пропустит.</p>
                    {!preview ? <button type="button" disabled={Boolean(busy) || !period.start || !period.end} onClick={() => void inspect(provider)} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-[15px] bg-primary text-sm font-semibold shadow-[0_10px_28px_rgba(255,92,51,0.18)] active:scale-[0.96] disabled:opacity-45">{providerBusy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <RefreshCw className="h-4 w-4" />}{providerBusy ? 'Проверяем CRM…' : 'Проверить данные'}</button> : <div className="mt-3 rounded-[16px] bg-white/[0.035] p-3 ring-1 ring-inset ring-primary/20">
                      <div className="grid grid-cols-3 gap-2 text-center"><span><b className="block text-base tabular-nums">{preview.rows_total || 0}</b><small className="text-[9px] text-zinc-600">Всего</small></span><span><b className="block text-base tabular-nums text-emerald-300">{preview.valid_rows || 0}</b><small className="text-[9px] text-zinc-600">Готово</small></span><span><b className="block text-base tabular-nums text-rose-300">{preview.failed_rows || 0}</b><small className="text-[9px] text-zinc-600">Ошибки</small></span></div>
                      {preview.preview_rows?.length ? <div className="mt-3 space-y-1 border-t border-white/[0.06] pt-3">{preview.preview_rows.slice(0, 3).map((row, index) => <p key={`${provider.provider}-${index}`} className="truncate text-[10px] text-zinc-500">{previewRowLabel(row)}</p>)}</div> : null}
                      <div className="mt-3 flex items-start gap-2 text-[10px] leading-4 text-zinc-600"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />До подтверждения финансовые данные не изменятся.</div>
                      <div className="mt-3 grid grid-cols-2 gap-2"><button type="button" disabled={Boolean(busy)} onClick={() => setPreviews((current) => { const next = { ...current }; delete next[provider.provider]; return next; })} className="min-h-11 rounded-[14px] bg-white/[0.05] text-xs font-semibold ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Отмена</button><button type="button" disabled={Boolean(busy) || !preview.valid_rows} onClick={() => void confirm(provider)} className="min-h-11 rounded-[14px] bg-primary text-xs font-semibold active:scale-[0.96] disabled:opacity-45">{providerBusy ? 'Загружаем…' : `Подтвердить ${preview.valid_rows || 0}`}</button></div>
                    </div>}
                  </> : <>
                    <p className="text-pretty text-xs leading-5 text-zinc-500">{provider.description || 'Подключите CRM, чтобы не вносить статистику вручную.'}</p>
                    <div className="mt-3 space-y-2"><input aria-label={`ID филиала ${provider.label}`} placeholder="ID филиала" value={credentials[provider.provider]?.location_id || ''} onChange={(event) => updateCredential(provider.provider, 'location_id', event.target.value)} className="min-h-11 w-full rounded-[14px] bg-white/[0.04] px-3 text-xs outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><input aria-label={`Partner token ${provider.label}`} type="password" autoComplete="off" placeholder="Partner token" value={credentials[provider.provider]?.partner_token || ''} onChange={(event) => updateCredential(provider.provider, 'partner_token', event.target.value)} className="min-h-11 w-full rounded-[14px] bg-white/[0.04] px-3 text-xs outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><input aria-label={`User token ${provider.label}`} type="password" autoComplete="off" placeholder="User token" value={credentials[provider.provider]?.user_token || ''} onChange={(event) => updateCredential(provider.provider, 'user_token', event.target.value)} className="min-h-11 w-full rounded-[14px] bg-white/[0.04] px-3 text-xs outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /></div>
                    <button type="button" disabled={Boolean(busy)} onClick={() => void connect(provider)} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-[15px] bg-primary text-sm font-semibold active:scale-[0.96] disabled:opacity-45">{providerBusy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <DatabaseZap className="h-4 w-4" />}{providerBusy ? 'Подключаем…' : `Подключить ${provider.label}`}</button>
                  </>}
                </div></motion.div> : null}
              </AnimatePresence>
            </article>
          );
        })}
      </div>
      {!providers.length && !error ? <div className="mt-4 flex min-h-20 items-center justify-center gap-2 text-xs text-zinc-600"><Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" />Загружаем подключения…</div> : null}
    </section>
  );
};

export default FinanceCrmMobilePanel;
