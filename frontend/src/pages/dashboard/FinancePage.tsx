import { useEffect, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { CheckCircle2, FileSpreadsheet, MessageCircle, Send, Wallet } from 'lucide-react';

import FinanceFirstStep from '@/components/FinanceFirstStep';
import FinanceImportPanel from '@/components/FinanceImportPanel';
import FinanceThresholdsPanel from '@/components/FinanceThresholdsPanel';
import FinancialMetrics from '@/components/FinancialMetrics';
import ROICalculator from '@/components/ROICalculator';
import TransactionTable from '@/components/TransactionTable';
import {
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { GrowthDataHealth } from '@/components/growth/DataHealthRhythmStrip';
import { newAuth } from '@/lib/auth_new';
import { trackProductEvent } from '@/lib/productEvents';

const crmStatusLabel = (status?: string) => {
  if (status === 'reviewing') return 'изучаем подключение';
  if (status === 'planned') return 'запланировано';
  if (status === 'connected') return 'подключено';
  if (status === 'closed') return 'закрыто';
  if (status === 'declined') return 'пока не поддерживается';
  return 'запрос получен';
};

export const FinancePage = () => {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId?: string | null }>();
  const [searchParams] = useSearchParams();
  const [dataHealth, setDataHealth] = useState<GrowthDataHealth | null>(null);
  const [crmRequestOpen, setCrmRequestOpen] = useState(false);
  const [crmName, setCrmName] = useState('');
  const [crmUrl, setCrmUrl] = useState('');
  const [crmContact, setCrmContact] = useState('');
  const [crmNote, setCrmNote] = useState('');
  const [crmRequestState, setCrmRequestState] = useState<'idle' | 'pending' | 'success' | 'error'>('idle');
  const [crmLatest, setCrmLatest] = useState<{ crm_name?: string; status?: string } | null>(null);

  const submitCrmRequest = async () => {
    if (!currentBusinessId || !crmName.trim() || crmRequestState === 'pending') return;
    setCrmRequestState('pending');
    try {
      const result = await newAuth.makeRequest(`/business/${currentBusinessId}/crm-integration-requests`, {
        method: 'POST',
        body: JSON.stringify({ crm_name: crmName.trim(), crm_url: crmUrl.trim(), contact: crmContact.trim(), note: crmNote.trim(), scope_type: 'business', scope_id: currentBusinessId }),
      });
      setCrmLatest(result?.request || null);
      setCrmRequestState('success');
      trackProductEvent({ eventName: 'crm_request_created', businessId: currentBusinessId, objectType: 'crm', objectId: crmName.trim() });
    } catch {
      setCrmRequestState('error');
    }
  };

  useEffect(() => {
    if (!currentBusinessId) { setCrmLatest(null); return; }
    void newAuth.makeRequest(`/business/${currentBusinessId}/crm-integration-requests`, { method: 'GET' })
      .then((result) => setCrmLatest(Array.isArray(result?.requests) ? result.requests[0] || null : null))
      .catch(() => setCrmLatest(null));
  }, [currentBusinessId]);

  useEffect(() => {
    if (!currentBusinessId) {
      setDataHealth(null);
      return undefined;
    }
    const controller = new AbortController();
    void newAuth.makeRequest(`/business/${currentBusinessId}/growth-overview`, { method: 'GET', signal: controller.signal })
      .then((data: { data_health?: GrowthDataHealth | null }) => {
        if (!controller.signal.aborted) setDataHealth(data.data_health || null);
      })
      .catch(() => {
        if (!controller.signal.aborted) setDataHealth(null);
      });
    return () => controller.abort();
  }, [currentBusinessId]);

  useEffect(() => {
    trackProductEvent({ eventName: 'statistics_flow_opened', businessId: currentBusinessId, objectType: 'finance' });
  }, [currentBusinessId]);

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-10">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Финансы"
        description="Короткий обзор денег, загрузки и ближайшего управленческого шага."
        icon={Wallet}
      />

      <FinanceFirstStep
        currentBusinessId={currentBusinessId}
        dataHealth={dataHealth}
        initialTab={searchParams.get('tab') === 'import' ? 'settings' : 'overview'}
        setupTools={(
          <div className="space-y-6">
            <FinanceThresholdsPanel currentBusinessId={currentBusinessId} />
            <FinanceImportPanel currentBusinessId={currentBusinessId} />
            <DashboardSection
              title="Как подготовить выгрузку YCLIENTS"
              description="В YCLIENTS откройте отчёт за нужный период, выгрузите его в XLSX или CSV и загрузите выше. Доступ к API и токен не нужны."
            >
              <div className="grid gap-3 text-sm text-slate-700 md:grid-cols-3">
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200"><FileSpreadsheet className="mb-2 h-4 w-4 text-slate-500" />1. Выберите период и выгрузите отчёт.</div>
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200"><FileSpreadsheet className="mb-2 h-4 w-4 text-slate-500" />2. Загрузите файл и проверьте preview.</div>
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200"><FileSpreadsheet className="mb-2 h-4 w-4 text-slate-500" />3. Импортируйте только подтверждённые строки.</div>
              </div>
              <div className="mt-4 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-slate-700 shadow-sm ring-1 ring-slate-200"><MessageCircle className="h-5 w-5" /></span>
                    <div>
                      <div className="font-semibold text-slate-950">У вас другая CRM?</div>
                      <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">Напишите её название — мы сохраним запрос и свяжемся по подключению.</p>
                    </div>
                  </div>
                  {crmRequestState !== 'success' ? (
                    <Button type="button" variant="outline" className="min-h-11 shrink-0 transition-transform active:scale-[0.96]" onClick={() => setCrmRequestOpen((value) => !value)}>
                      Написать, какая у вас CRM
                    </Button>
                  ) : null}
                </div>
                {crmRequestState === 'success' ? (
                  <div className="mt-3 flex items-center gap-2 text-sm font-medium text-emerald-700" role="status"><CheckCircle2 className="h-4 w-4" />Запрос сохранён. Мы сообщим о вариантах подключения.</div>
                ) : crmLatest ? (
                  <div className="mt-3 flex items-center gap-2 rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-700" role="status"><CheckCircle2 className="h-4 w-4 text-slate-500" /><span><strong>{crmLatest.crm_name}</strong> · {crmStatusLabel(crmLatest.status)}</span></div>
                ) : crmRequestOpen ? (
                  <div className="mt-4 grid gap-3 border-t border-slate-200 pt-4">
                    <Input value={crmName} onChange={(event) => setCrmName(event.target.value)} placeholder="Например, МойСклад или Altegio" aria-label="Название CRM" />
                    <Input value={crmUrl} onChange={(event) => setCrmUrl(event.target.value)} placeholder="Ссылка на CRM — необязательно" aria-label="Ссылка на CRM" inputMode="url" />
                    <Input value={crmContact} onChange={(event) => setCrmContact(event.target.value)} placeholder="Telegram, email или телефон — необязательно" aria-label="Контакт для связи" />
                    <Textarea value={crmNote} onChange={(event) => setCrmNote(event.target.value)} placeholder="Какие данные важно загружать: выручка, средний чек, загрузка…" aria-label="Комментарий к CRM" />
                    {crmRequestState === 'error' ? <p className="text-sm text-rose-700" role="alert">Не удалось сохранить запрос. Повторите ещё раз.</p> : null}
                    <Button type="button" className="min-h-11 justify-self-start gap-2 transition-transform active:scale-[0.96]" disabled={!crmName.trim() || crmRequestState === 'pending'} onClick={() => void submitCrmRequest()}>
                      <Send className="h-4 w-4" />{crmRequestState === 'pending' ? 'Сохраняем…' : 'Отправить запрос'}
                    </Button>
                  </div>
                ) : null}
              </div>
            </DashboardSection>
          </div>
        )}
        legacyTools={(
          <div className="space-y-6">
            <FinancialMetrics currentBusinessId={currentBusinessId} />
            <ROICalculator />
            <DashboardSection
              title="Журнал операций"
              description="Все транзакции по текущему бизнесу в одном месте."
            >
              <TransactionTable currentBusinessId={currentBusinessId} />
            </DashboardSection>
          </div>
        )}
      />
    </div>
  );
};
