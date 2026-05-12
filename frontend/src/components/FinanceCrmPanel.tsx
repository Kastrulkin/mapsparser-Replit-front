import React, { useCallback, useEffect, useState } from 'react';
import { Cable, CheckCircle2, ExternalLink, RefreshCw, ShieldCheck } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

type FinanceCrmPanelProps = {
  currentBusinessId?: string | null;
  onSynced?: () => void;
  surface?: 'section' | 'embedded';
};

type CrmConnection = {
  provider: string;
  status: string;
  display_name?: string;
  last_sync_at?: string | null;
  sync_status?: string | null;
  error_log?: Array<Record<string, unknown>>;
};

type CrmProvider = {
  provider: string;
  label: string;
  status: string;
  description: string;
  requires_auth: boolean;
  docs_url?: string;
  api_base_url?: string;
  required_auth_fields?: string[];
  required_settings_fields?: string[];
  capabilities?: string[];
  notes?: string[];
  connection?: CrmConnection | null;
};

type CrmCredentials = {
  partner_token?: string;
  user_token?: string;
  location_id?: string;
};

type CrmPreview = {
  provider: string;
  preview_token?: string;
  period?: {
    start_date?: string;
    end_date?: string;
  };
  will_write: boolean;
  dataset_counts: Record<string, number>;
  normalized_counts: Record<string, number>;
  rows_total: number;
  valid_rows: number;
  failed_rows: number;
  preview_rows?: Array<Record<string, unknown>>;
  errors?: Array<{ row?: number; errors?: string[] }>;
};

export const FinanceCrmPanel: React.FC<FinanceCrmPanelProps> = ({ currentBusinessId, onSynced, surface = 'section' }) => {
  const [providers, setProviders] = useState<CrmProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningProvider, setRunningProvider] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [credentials, setCredentials] = useState<Record<string, CrmCredentials>>({});
  const [previews, setPreviews] = useState<Record<string, CrmPreview>>({});

  const token = localStorage.getItem('auth_token');

  const loadProviders = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    try {
      const response = await fetch(`/api/finance/crm/providers?business_id=${currentBusinessId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось загрузить CRM');
        return;
      }
      setProviders(data.providers || []);
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  }, [currentBusinessId, token]);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const updateCredential = (provider: string, key: keyof CrmCredentials, value: string) => {
    setCredentials((current) => ({
      ...current,
      [provider]: {
        ...(current[provider] || {}),
        [key]: value,
      },
    }));
  };

  const connectProvider = async (provider: CrmProvider) => {
    if (!currentBusinessId) return;
    setRunningProvider(provider.provider);
    setMessage(null);
    const providerCredentials = credentials[provider.provider] || {};
    if (provider.requires_auth) {
      const missing = [];
      if (!providerCredentials.partner_token) missing.push('partner token');
      if (!providerCredentials.user_token) missing.push('user token');
      if (!providerCredentials.location_id) missing.push('ID филиала');
      if (missing.length) {
        setMessage(`Для ${provider.label} нужно заполнить: ${missing.join(', ')}.`);
        setRunningProvider(null);
        return;
      }
    }
    try {
      const response = await fetch('/api/finance/crm/connect', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          business_id: currentBusinessId,
          provider: provider.provider,
          display_name: provider.label,
          auth_data: provider.requires_auth ? {
            partner_token: providerCredentials.partner_token,
            user_token: providerCredentials.user_token,
            api_base_url: provider.api_base_url,
          } : {},
          settings: provider.requires_auth ? {
            location_id: providerCredentials.location_id,
          } : {},
        }),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось подключить CRM');
        return;
      }
      setMessage(`${provider.label} подключена. Теперь можно запустить синхронизацию.`);
      await loadProviders();
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setRunningProvider(null);
    }
  };

  const syncProvider = async (provider: string) => {
    if (!currentBusinessId) return;
    const preview = previews[provider];
    if (!preview?.preview_token) {
      setMessage('Сначала проверьте данные CRM. После preview можно подтвердить импорт.');
      return;
    }
    setRunningProvider(provider);
    setMessage(null);
    try {
      const response = await fetch('/api/finance/crm/sync', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          business_id: currentBusinessId,
          provider,
          confirm_preview_token: preview.preview_token,
          period_start: preview.period?.start_date,
          period_end: preview.period?.end_date,
        }),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось синхронизировать CRM');
        if (data.requires_preview) {
          setPreviews((current) => {
            const next = { ...current };
            delete next[provider];
            return next;
          });
        }
        return;
      }
      setMessage(`Синхронизировано: ${data.rows_imported}. Дубли: ${data.rows_skipped}. Ошибки: ${data.rows_failed}.`);
      await loadProviders();
      if (onSynced) onSynced();
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setRunningProvider(null);
    }
  };

  const previewProvider = async (provider: string) => {
    if (!currentBusinessId) return;
    setRunningProvider(provider);
    setMessage(null);
    try {
      const response = await fetch('/api/finance/crm/preview', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ business_id: currentBusinessId, provider, sample_limit: 5 }),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось проверить CRM');
        return;
      }
      setPreviews((current) => ({ ...current, [provider]: data }));
      setMessage(`Preview готов: валидных строк ${data.valid_rows}, ошибок ${data.failed_rows}. В финансы ничего не записано.`);
      await loadProviders();
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setRunningProvider(null);
    }
  };

  const content = (
    <>
      {message ? (
        <div className="mb-4 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700 ring-1 ring-slate-200">
          {message}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        {providers.map((provider) => {
          const connected = provider.connection?.status === 'connected';
          const running = runningProvider === provider.provider;
          const previewReady = Boolean(previews[provider.provider]?.preview_token);
          return (
            <Card key={provider.provider} className="border-slate-200/80 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-3 text-base">
                  <span className="flex items-center gap-2">
                    <Cable className="h-4 w-4 text-slate-500" />
                    {provider.label}
                  </span>
                  <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium', connected ? 'bg-emerald-50 text-emerald-700' : provider.status === 'available' ? 'bg-sky-50 text-sky-700' : 'bg-slate-100 text-slate-600')}>
                    {connected ? 'connected' : provider.status}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <p className="leading-6 text-slate-600">{provider.description}</p>
                {provider.docs_url ? (
                  <a
                    href={provider.docs_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-900"
                  >
                    Документация API
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : null}
                {provider.capabilities?.length ? (
                  <div className="flex flex-wrap gap-2">
                    {provider.capabilities.map((capability) => (
                      <span key={capability} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                        {capability}
                      </span>
                    ))}
                  </div>
                ) : null}
                {provider.requires_auth && !connected ? (
                  <div className="space-y-3 rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                    <div className="grid gap-3">
                      <div className="space-y-1.5">
                        <Label htmlFor={`${provider.provider}-location`}>ID филиала / location_id</Label>
                        <Input
                          id={`${provider.provider}-location`}
                          value={credentials[provider.provider]?.location_id || ''}
                          onChange={(event) => updateCredential(provider.provider, 'location_id', event.target.value)}
                          placeholder="Например: 123456"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`${provider.provider}-partner`}>Partner token</Label>
                        <Input
                          id={`${provider.provider}-partner`}
                          type="password"
                          value={credentials[provider.provider]?.partner_token || ''}
                          onChange={(event) => updateCredential(provider.provider, 'partner_token', event.target.value)}
                          placeholder="Токен приложения"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`${provider.provider}-user`}>User token</Label>
                        <Input
                          id={`${provider.provider}-user`}
                          type="password"
                          value={credentials[provider.provider]?.user_token || ''}
                          onChange={(event) => updateCredential(provider.provider, 'user_token', event.target.value)}
                          placeholder="Токен пользователя с правами филиала"
                        />
                      </div>
                    </div>
                    {provider.notes?.length ? (
                      <div className="space-y-1 text-xs leading-5 text-slate-500">
                        {provider.notes.map((note) => (
                          <div key={note}>{note}</div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <div className="rounded-2xl bg-slate-50 p-3 text-slate-700">
                  <div className="flex items-center gap-2 font-medium text-slate-950">
                    {connected ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <ShieldCheck className="h-4 w-4 text-slate-500" />}
                    Статус
                  </div>
                  <div className="mt-2 space-y-1">
                    <div>Подключение: {provider.connection?.status || 'нет'}</div>
                    <div>Синхронизация: {provider.connection?.sync_status || 'не запускалась'}</div>
                    <div>Последний запуск: {provider.connection?.last_sync_at || 'нет'}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant={connected ? 'outline' : 'default'}
                    disabled={provider.status !== 'available' || running || !currentBusinessId}
                    onClick={() => connectProvider(provider)}
                  >
                    {connected ? 'Переподключить' : 'Подключить'}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!connected || running || !currentBusinessId}
                    onClick={() => previewProvider(provider.provider)}
                    className="gap-2"
                  >
                    <RefreshCw className={cn('h-4 w-4', running ? 'animate-spin' : '')} />
                    Проверить данные
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!connected || running || !currentBusinessId || !previewReady}
                    onClick={() => syncProvider(provider.provider)}
                    className="gap-2"
                  >
                    <RefreshCw className={cn('h-4 w-4', running ? 'animate-spin' : '')} />
                    Подтвердить импорт
                  </Button>
                </div>
                {connected && !previewReady ? (
                  <div className="rounded-xl bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800 ring-1 ring-amber-100">
                    Импорт откроется после проверки данных. Preview действует ограниченное время и защищает от случайной записи не той выгрузки.
                  </div>
                ) : null}
                {previews[provider.provider] ? (
                  <CrmPreviewSummary preview={previews[provider.provider]} />
                ) : null}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );

  if (surface === 'embedded') {
    return (
      <div className="space-y-4 rounded-3xl border border-slate-200 bg-slate-50/70 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-950">CRM для финансов</h3>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              Подключите YCLIENTS или Altegio, чтобы подтягивать записи, оплаты, услуги, мастеров и рабочие места в финансовую модель.
            </p>
          </div>
          <Button variant="outline" onClick={loadProviders} disabled={loading || !currentBusinessId} className="gap-2">
            <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
            Обновить
          </Button>
        </div>
        {content}
      </div>
    );
  }

  return (
    <DashboardSection
      title="CRM-синхронизация"
      description="CRM будет отдавать записи, оплаты, услуги, мастеров и рабочие места в ту же финансовую модель. Сейчас доступен безопасный Demo CRM адаптер для проверки потока."
      actions={
        <Button variant="outline" onClick={loadProviders} disabled={loading || !currentBusinessId} className="gap-2">
          <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
          Обновить
        </Button>
      }
    >
      {content}
    </DashboardSection>
  );
};

const crmDatasetLabels: Record<string, string> = {
  appointments: 'Записи',
  payments: 'Оплаты',
  clients: 'Клиенты',
  services: 'Услуги',
  staff: 'Мастера',
  workplaces: 'Рабочие места',
};

const normalizedLabels: Record<string, string> = {
  entry: 'Доходы/расходы',
  service: 'Услуги',
  staff: 'Мастера',
  workplace: 'Рабочие места',
};

const CrmPreviewSummary: React.FC<{ preview: CrmPreview }> = ({ preview }) => (
  <div className="space-y-3 rounded-2xl border border-sky-100 bg-sky-50/70 p-3 text-slate-700">
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
      <div className="font-medium text-slate-950">Preview без записи в финансы</div>
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
        {preview.preview_token ? 'готово к подтверждению' : preview.will_write ? 'будет запись' : 'только проверка'}
      </div>
    </div>
    <div className="grid gap-2 sm:grid-cols-3">
      <PreviewMetric label="Всего строк" value={preview.rows_total} />
      <PreviewMetric label="Готово к импорту" value={preview.valid_rows} />
      <PreviewMetric label="Ошибок" value={preview.failed_rows} tone={preview.failed_rows > 0 ? 'warning' : 'default'} />
    </div>
    <div className="grid gap-3 lg:grid-cols-2">
      <PreviewCounts title="CRM отдала" counts={preview.dataset_counts} labels={crmDatasetLabels} />
      <PreviewCounts title="LocalOS распознал" counts={preview.normalized_counts} labels={normalizedLabels} />
    </div>
    {preview.errors?.length ? (
      <div className="rounded-xl bg-white/80 p-3 text-xs leading-5 text-rose-700 ring-1 ring-rose-100">
        {preview.errors.slice(0, 3).map((error, index) => (
          <div key={`${error.row || 'row'}-${index}`}>
            Строка {error.row || '?'}: {(error.errors || []).join(', ')}
          </div>
        ))}
      </div>
    ) : null}
  </div>
);

const PreviewMetric: React.FC<{ label: string; value: number; tone?: 'default' | 'warning' }> = ({ label, value, tone = 'default' }) => (
  <div className={cn('rounded-xl bg-white/80 px-3 py-2 ring-1', tone === 'warning' ? 'ring-amber-200' : 'ring-sky-100')}>
    <div className="text-xs text-slate-500">{label}</div>
    <div className="text-lg font-semibold text-slate-950">{value}</div>
  </div>
);

const PreviewCounts: React.FC<{ title: string; counts: Record<string, number>; labels: Record<string, string> }> = ({ title, counts, labels }) => (
  <div className="rounded-xl bg-white/80 p-3 ring-1 ring-sky-100">
    <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{title}</div>
    <div className="space-y-1">
      {Object.entries(counts || {}).map(([key, value]) => (
        <div key={key} className="flex items-center justify-between gap-3 text-xs">
          <span>{labels[key] || key}</span>
          <span className="font-semibold text-slate-950">{value}</span>
        </div>
      ))}
    </div>
  </div>
);

export default FinanceCrmPanel;
