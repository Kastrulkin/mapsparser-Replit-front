import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Armchair,
  ArrowRight,
  Calculator,
  ChevronDown,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  ClipboardList,
  Gauge,
  PlayCircle,
  RefreshCw,
  Save,
  Scissors,
  Target,
  Users,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { cn } from '@/lib/utils';

type KpiValue = number | string | null | undefined;

type FinanceDashboard = {
  kpis: Record<string, KpiValue>;
  explanations: Record<string, string>;
  data_quality: {
    score: number;
    missing: string[];
    approximate: string[];
    precise: string[];
    blocked: string[];
    can_analyze?: string[];
  };
  recommendations: Array<FinanceRecommendation>;
  action_logs?: FinanceActionLog[];
  action_impact?: FinanceImpact;
  period_history?: FinanceHistoryPoint[];
  services: Array<Record<string, KpiValue | string>>;
  staff: Array<Record<string, KpiValue | string>>;
  workplaces: Array<Record<string, KpiValue | string>>;
  statuses: Record<string, string>;
};

type FinanceRecommendation = {
  code: string;
  title: string;
  text: string;
  severity: string;
  target_metric?: string | null;
  data_needed?: string[];
  actions?: {
    today?: string[];
    seven_days?: string[];
    regular?: string[];
  };
  localos_actions?: Array<{
    label: string;
    description?: string;
    route: string;
  }>;
};

type FinanceActionLog = {
  action_key: string;
  status: string;
  completed_at?: string | null;
};

type FinanceImpact = {
  completed_actions_count: number;
  period: { start_date: string; end_date: string };
  previous_period: { start_date: string; end_date: string };
  deltas: Array<{ metric: string; current: KpiValue; previous: KpiValue; delta: KpiValue; direction: string }>;
};

type FinanceHistoryPoint = {
  label: string;
  period_start: string;
  period_end: string;
  revenue?: KpiValue;
  operating_margin?: KpiValue;
  no_show_rate?: KpiValue;
  rebooking_rate?: KpiValue;
  workplace_occupancy?: KpiValue;
  revenue_per_workplace_hour?: KpiValue;
  data_quality_score?: KpiValue;
};

type FinanceFirstStepProps = {
  currentBusinessId?: string | null;
};

const rub = (value: KpiValue) => {
  if (value == null) return 'н/д';
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(Number(value));
};

const numberValue = (value: KpiValue) => {
  if (value == null) return 'н/д';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(Number(value));
};

const percent = (value: KpiValue) => {
  if (value == null) return 'н/д';
  return `${numberValue(value)}%`;
};

const minutesFromHours = (value: string) => Math.round(Number(value || 0) * 60);

const statusTone = (status?: string) => {
  if (status === 'green') return 'border-emerald-200 bg-emerald-50 text-emerald-900';
  if (status === 'yellow') return 'border-amber-200 bg-amber-50 text-amber-900';
  if (status === 'red') return 'border-rose-200 bg-rose-50 text-rose-900';
  return 'border-slate-200 bg-white text-slate-900';
};

const workplaceLabels: Record<string, string> = {
  hair_chair: 'Парикмахерское кресло',
  nail_place: 'Nail-место',
  cosmetology_room: 'Кабинет косметологии',
  massage_room: 'Массажный кабинет',
  other: 'Другое',
};

const starterSteps = [
  { key: 'entry', title: '1. Деньги', text: 'Выручка и основные расходы за 3 месяца.' },
  { key: 'service', title: '2. Услуги', text: 'Цена, длительность, материалы и выплата мастеру.' },
  { key: 'staff', title: '3. Мастера', text: 'Выручка, часы, визиты, неявки и повторная запись.' },
  { key: 'workplace', title: '4. Кресла', text: 'Сколько мест доступно, занято и сколько они приносят.' },
];

export const FinanceFirstStep: React.FC<FinanceFirstStepProps> = ({ currentBusinessId }) => {
  const [dashboard, setDashboard] = useState<FinanceDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingActionKey, setSavingActionKey] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [historyMonths, setHistoryMonths] = useState(6);
  const [history, setHistory] = useState<FinanceHistoryPoint[]>([]);
  const [impact, setImpact] = useState<FinanceImpact | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<FinanceMetricKey | null>(null);
  const [activeInputStep, setActiveInputStep] = useState('entry');
  const [entry, setEntry] = useState({
    revenue: '',
    rent: '',
    payroll: '',
    materials: '',
    marketing: '',
    taxes: '',
  });
  const [service, setService] = useState({
    service_name: '',
    category: '',
    revenue: '',
    visits_count: '',
    avg_price: '',
    duration_minutes: '',
    material_cost: '',
    staff_payout: '',
  });
  const [staff, setStaff] = useState({
    staff_name: '',
    role: '',
    revenue: '',
    visits_count: '',
    booked_hours: '',
    available_hours: '',
    no_show_count: '',
    rebooking_count: '',
  });
  const [workplace, setWorkplace] = useState({
    name: '',
    type: 'hair_chair',
    available_hours: '',
    booked_hours: '',
    revenue: '',
    gross_profit: '',
  });

  const period = useMemo(() => {
    const end = new Date();
    const start = new Date(end);
    start.setMonth(start.getMonth() - 3);
    start.setDate(1);
    return {
      start: start.toISOString().slice(0, 10),
      end: end.toISOString().slice(0, 10),
    };
  }, []);

  const loadDashboard = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    setMessage(null);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(
        `/api/finance/dashboard?business_id=${currentBusinessId}&from=${period.start}&to=${period.end}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось загрузить финансовые данные');
        return;
      }
      setDashboard(data);
      setHistory(data.period_history || []);
      setImpact(data.action_impact || null);
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  }, [currentBusinessId, period.end, period.start]);

  const loadHistory = useCallback(async (months: number) => {
    if (!currentBusinessId) return;
    setHistoryMonths(months);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/finance/history?business_id=${currentBusinessId}&months=${months}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (data.success) setHistory(data.history || []);
    } catch (error) {
      setMessage('Не удалось загрузить историю периодов');
    }
  }, [currentBusinessId]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const saveManualData = async (mode: 'entry' | 'service' | 'staff' | 'workplace') => {
    if (!currentBusinessId) return;
    setSaving(true);
    setMessage(null);

    const entries = [];
    if (mode === 'entry') {
      if (entry.revenue) entries.push({ date: period.end, type: 'revenue', category: 'sales', amount: Number(entry.revenue), comment: 'Выручка за период' });
      if (entry.rent) entries.push({ date: period.end, type: 'expense', category: 'rent', amount: Number(entry.rent), comment: 'Аренда' });
      if (entry.payroll) entries.push({ date: period.end, type: 'expense', category: 'payroll', amount: Number(entry.payroll), comment: 'ФОТ' });
      if (entry.materials) entries.push({ date: period.end, type: 'expense', category: 'materials', amount: Number(entry.materials), comment: 'Материалы' });
      if (entry.marketing) entries.push({ date: period.end, type: 'expense', category: 'marketing', amount: Number(entry.marketing), comment: 'Маркетинг' });
      if (entry.taxes) entries.push({ date: period.end, type: 'expense', category: 'taxes', amount: Number(entry.taxes), comment: 'Налоги' });
    }

    const workplaces = mode === 'workplace' ? [{
      client_key: workplace.name || 'workplace',
      name: workplace.name || 'Рабочее место',
      type: workplace.type,
      is_active: true,
    }] : [];

    const payload = {
      business_id: currentBusinessId,
      period_start: period.start,
      period_end: period.end,
      entries,
      services: mode === 'service' ? [{
        service_name: service.service_name || 'Услуга',
        category: service.category,
        revenue: Number(service.revenue || 0),
        visits_count: Number(service.visits_count || 0),
        avg_price: Number(service.avg_price || 0),
        duration_minutes: Number(service.duration_minutes || 0),
        material_cost: Number(service.material_cost || 0),
        staff_payout: Number(service.staff_payout || 0),
      }] : [],
      staff: mode === 'staff' ? [{
        staff_name: staff.staff_name || 'Мастер',
        role: staff.role,
        revenue: Number(staff.revenue || 0),
        visits_count: Number(staff.visits_count || 0),
        booked_minutes: minutesFromHours(staff.booked_hours),
        available_minutes: minutesFromHours(staff.available_hours),
        no_show_count: Number(staff.no_show_count || 0),
        rebooking_count: Number(staff.rebooking_count || 0),
      }] : [],
      workplaces,
      workplace_metrics: mode === 'workplace' ? [{
        workplace_client_key: workplace.name || 'workplace',
        period_start: period.start,
        period_end: period.end,
        available_minutes: minutesFromHours(workplace.available_hours),
        booked_minutes: minutesFromHours(workplace.booked_hours),
        revenue: Number(workplace.revenue || 0),
        gross_profit: Number(workplace.gross_profit || 0),
      }] : [],
    };

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/finance/manual-entry', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось сохранить данные');
        return;
      }
      setMessage('Данные сохранены, показатели пересчитаны');
      if (mode === 'entry') setEntry({ revenue: '', rent: '', payroll: '', materials: '', marketing: '', taxes: '' });
      if (mode === 'service') setService({ service_name: '', category: '', revenue: '', visits_count: '', avg_price: '', duration_minutes: '', material_cost: '', staff_payout: '' });
      if (mode === 'staff') setStaff({ staff_name: '', role: '', revenue: '', visits_count: '', booked_hours: '', available_hours: '', no_show_count: '', rebooking_count: '' });
      if (mode === 'workplace') setWorkplace({ name: '', type: 'hair_chair', available_hours: '', booked_hours: '', revenue: '', gross_profit: '' });
      await loadDashboard();
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setSaving(false);
    }
  };

  const kpis = dashboard?.kpis || {};
  const quality = dashboard?.data_quality;
  const analyzableItems = (quality?.can_analyze && quality.can_analyze.length > 0)
    ? quality.can_analyze
    : (quality?.precise || []);
  const hasFinanceData = Boolean(
    (Number(kpis.revenue || 0) > 0)
    || (dashboard?.services || []).length
    || (dashboard?.staff || []).length
    || (dashboard?.workplaces || []).length,
  );
  const dataState = getFinanceDataState(hasFinanceData, quality?.score || 0, quality?.missing || []);
  const priorityItems = useMemo(() => {
    const items = [];
    if (!hasFinanceData) {
      items.push('Заполнить выручку и основные расходы: это даст первый отчёт доходов и расходов и понимание плюс/минус.');
      items.push('Добавить хотя бы одно рабочее место: тогда появится выручка на кресло и простой.');
      items.push('Добавить 3-5 ключевых услуг: станет видно, где прибыль, а где занятость без денег.');
      return items;
    }
    for (const recommendation of dashboard?.recommendations || []) {
      if (items.length >= 3) break;
      items.push(recommendation.title);
    }
    for (const missing of quality?.missing || []) {
      if (items.length >= 3) break;
      items.push(`Дозаполнить: ${missing}`);
    }
    return items;
  }, [dashboard?.recommendations, hasFinanceData, quality?.missing]);
  const primaryAction = getPrimaryFinanceAction(dataState, quality?.missing || []);

  const fillDemoSalon = () => {
    setEntry({
      revenue: '1280000',
      rent: '180000',
      payroll: '520000',
      materials: '135000',
      marketing: '85000',
      taxes: '90000',
    });
    setService({
      service_name: 'Окрашивание волос',
      category: 'Волосы',
      revenue: '420000',
      visits_count: '42',
      avg_price: '10000',
      duration_minutes: '180',
      material_cost: '85000',
      staff_payout: '155000',
    });
    setStaff({
      staff_name: 'Анна',
      role: 'Стилист',
      revenue: '520000',
      visits_count: '58',
      booked_hours: '145',
      available_hours: '190',
      no_show_count: '4',
      rebooking_count: '34',
    });
    setWorkplace({
      name: 'Кресло 1',
      type: 'hair_chair',
      available_hours: '190',
      booked_hours: '145',
      revenue: '520000',
      gross_profit: '280000',
    });
    setActiveInputStep('entry');
    setMessage('Заполнил пример салона в формах. Можно посмотреть структуру данных или сохранить блоки по очереди.');
  };

  const completedActions = useMemo(() => {
    const done = new Set<string>();
    for (const item of dashboard?.action_logs || []) {
      if (item.status === 'completed') done.add(item.action_key);
    }
    return done;
  }, [dashboard?.action_logs]);

  const toggleAction = async (
    recommendation: FinanceRecommendation,
    bucket: string,
    actionText: string,
    completed: boolean,
  ) => {
    if (!currentBusinessId) return;
    const actionKey = buildActionKey(recommendation.code, bucket, actionText);
    setSavingActionKey(actionKey);
    setMessage(null);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/finance/actions', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          business_id: currentBusinessId,
          recommendation_code: recommendation.code,
          action_key: actionKey,
          action_bucket: bucket,
          action_text: actionText,
          status: completed ? 'completed' : 'pending',
          period_start: period.start,
          period_end: period.end,
        }),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось сохранить действие');
        return;
      }
      setDashboard((current) => current ? { ...current, action_logs: data.actions || [] } : current);
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setSavingActionKey(null);
    }
  };

  const runPrimaryAction = () => {
    if (primaryAction.target === 'red-flags') {
      document.getElementById('finance-red-flags')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    setActiveInputStep(primaryAction.target);
    document.getElementById('finance-quick-input')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="space-y-6">
      <DashboardSection
        title="Финансовый обзор"
        description="Сначала смотрим на состояние данных, ключевые показатели и ближайшее действие. Детальный ввод и таблицы ниже."
        actions={
          <Button variant="outline" onClick={loadDashboard} disabled={loading || !currentBusinessId} className="gap-2">
            <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
            Обновить
          </Button>
        }
      >
        {!currentBusinessId ? (
          <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Сначала выберите бизнес в верхнем переключателе.
          </div>
        ) : null}

        {message ? (
          <div className="mb-4 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700 ring-1 ring-slate-200">
            {message}
          </div>
        ) : null}

        <ExecutiveFinanceSummary
          dataState={dataState}
          period={period}
          quality={quality}
          kpis={kpis}
          explanations={dashboard?.explanations || {}}
          statuses={dashboard?.statuses || {}}
          history={history}
          priorityItems={priorityItems}
          primaryActionLabel={primaryAction.label}
          onPrimaryAction={runPrimaryAction}
          selectedMetric={selectedMetric}
          onSelectMetric={setSelectedMetric}
        />

        {selectedMetric ? (
          <MetricDrilldown
            metric={selectedMetric}
            kpis={kpis}
            explanations={dashboard?.explanations || {}}
            quality={quality}
            servicesCount={dashboard?.services?.length || 0}
            staffCount={dashboard?.staff?.length || 0}
            workplacesCount={dashboard?.workplaces?.length || 0}
            onClose={() => setSelectedMetric(null)}
          />
        ) : null}

        <div className="mt-6 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <ImpactPanel impact={impact} />
          <HistoryPanel history={history} months={historyMonths} onChangeMonths={loadHistory} />
        </div>

        <div id="finance-quick-input" className="mt-6 rounded-3xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                <Gauge className="h-4 w-4" />
                Быстрый ввод
              </div>
              <div className="mt-1 text-base font-semibold text-slate-950">
                {hasFinanceData ? 'Дозаполните недостающие данные' : 'Начните с 5 чисел'}
              </div>
            </div>
            <Button variant="outline" onClick={fillDemoSalon} className="gap-2">
              <PlayCircle className="h-4 w-4" />
              Показать пример салона
            </Button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            {starterSteps.map((step) => (
              <button
                key={step.key}
                type="button"
                onClick={() => setActiveInputStep(step.key)}
                className={cn(
                  'rounded-2xl border bg-white p-3 text-left text-sm transition hover:border-slate-300',
                  activeInputStep === step.key ? 'border-slate-950 ring-2 ring-slate-200' : 'border-slate-200',
                )}
              >
                <div className="font-semibold text-slate-950">{step.title}</div>
                <div className="mt-1 leading-5 text-slate-600">{step.text}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <Card className="border-slate-200/80 shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ClipboardList className="h-4 w-4 text-slate-500" />
                Мини-мастер ввода
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs value={activeInputStep} onValueChange={setActiveInputStep}>
                <TabsList className="grid h-auto w-full grid-cols-2 gap-1 md:grid-cols-4">
                  <TabsTrigger value="entry">Доходы и расходы</TabsTrigger>
                  <TabsTrigger value="service">Услуги</TabsTrigger>
                  <TabsTrigger value="staff">Мастера</TabsTrigger>
                  <TabsTrigger value="workplace">Кресла</TabsTrigger>
                </TabsList>

                <TabsContent value="entry" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <MoneyField label="Выручка" value={entry.revenue} onChange={(value) => setEntry({ ...entry, revenue: value })} />
                    <MoneyField label="Аренда" value={entry.rent} onChange={(value) => setEntry({ ...entry, rent: value })} />
                    <MoneyField label="ФОТ" value={entry.payroll} onChange={(value) => setEntry({ ...entry, payroll: value })} />
                    <MoneyField label="Материалы" value={entry.materials} onChange={(value) => setEntry({ ...entry, materials: value })} />
                    <MoneyField label="Маркетинг" value={entry.marketing} onChange={(value) => setEntry({ ...entry, marketing: value })} />
                    <MoneyField label="Налоги" value={entry.taxes} onChange={(value) => setEntry({ ...entry, taxes: value })} />
                  </div>
                  <SaveButton disabled={saving} onClick={() => saveManualData('entry')} />
                </TabsContent>

                <TabsContent value="service" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-4">
                    <TextField label="Услуга" value={service.service_name} onChange={(value) => setService({ ...service, service_name: value })} />
                    <TextField label="Категория" value={service.category} onChange={(value) => setService({ ...service, category: value })} />
                    <MoneyField label="Выручка" value={service.revenue} onChange={(value) => setService({ ...service, revenue: value })} />
                    <NumberField label="Продаж" value={service.visits_count} onChange={(value) => setService({ ...service, visits_count: value })} />
                    <MoneyField label="Средняя цена" value={service.avg_price} onChange={(value) => setService({ ...service, avg_price: value })} />
                    <NumberField label="Минут" value={service.duration_minutes} onChange={(value) => setService({ ...service, duration_minutes: value })} />
                    <MoneyField label="Материалы" value={service.material_cost} onChange={(value) => setService({ ...service, material_cost: value })} />
                    <MoneyField label="Выплата мастеру" value={service.staff_payout} onChange={(value) => setService({ ...service, staff_payout: value })} />
                  </div>
                  <SaveButton disabled={saving} onClick={() => saveManualData('service')} />
                </TabsContent>

                <TabsContent value="staff" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-4">
                    <TextField label="Мастер" value={staff.staff_name} onChange={(value) => setStaff({ ...staff, staff_name: value })} />
                    <TextField label="Роль" value={staff.role} onChange={(value) => setStaff({ ...staff, role: value })} />
                    <MoneyField label="Выручка" value={staff.revenue} onChange={(value) => setStaff({ ...staff, revenue: value })} />
                    <NumberField label="Визиты" value={staff.visits_count} onChange={(value) => setStaff({ ...staff, visits_count: value })} />
                    <NumberField label="Занято часов" value={staff.booked_hours} onChange={(value) => setStaff({ ...staff, booked_hours: value })} />
                    <NumberField label="Доступно часов" value={staff.available_hours} onChange={(value) => setStaff({ ...staff, available_hours: value })} />
                    <NumberField label="Неявки" value={staff.no_show_count} onChange={(value) => setStaff({ ...staff, no_show_count: value })} />
                    <NumberField label="Повторные записи" value={staff.rebooking_count} onChange={(value) => setStaff({ ...staff, rebooking_count: value })} />
                  </div>
                  <SaveButton disabled={saving} onClick={() => saveManualData('staff')} />
                </TabsContent>

                <TabsContent value="workplace" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <TextField label="Название места" value={workplace.name} onChange={(value) => setWorkplace({ ...workplace, name: value })} />
                    <div className="space-y-2">
                      <Label>Тип</Label>
                      <Select value={workplace.type} onValueChange={(value) => setWorkplace({ ...workplace, type: value })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Object.entries(workplaceLabels).map(([value, label]) => (
                            <SelectItem key={value} value={value}>{label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <NumberField label="Доступно часов" value={workplace.available_hours} onChange={(value) => setWorkplace({ ...workplace, available_hours: value })} />
                    <NumberField label="Занято часов" value={workplace.booked_hours} onChange={(value) => setWorkplace({ ...workplace, booked_hours: value })} />
                    <MoneyField label="Выручка" value={workplace.revenue} onChange={(value) => setWorkplace({ ...workplace, revenue: value })} />
                    <MoneyField label="Валовая прибыль" value={workplace.gross_profit} onChange={(value) => setWorkplace({ ...workplace, gross_profit: value })} />
                  </div>
                  <SaveButton disabled={saving} onClick={() => saveManualData('workplace')} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          <Card className="border-slate-200/80 shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                {quality && quality.score >= 70 ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 text-amber-600" />}
                Качество данных: {quality ? `${quality.score}/100` : 'н/д'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <InfoList title="Уже можно анализировать" items={analyzableItems} empty="Пока нет достаточных данных для выводов." />
              <InfoList title="Не хватает" items={quality?.missing || []} empty="Базовые поля заполнены." />
              <InfoList title="Считается приблизительно" items={quality?.approximate || []} empty="Критичных допущений нет." />
              <div className="rounded-2xl bg-slate-50 p-4 text-slate-700">
                <div className="font-medium text-slate-950">Прогресс</div>
                <div className="mt-2 space-y-1">
                  <ProgressLine done={(quality?.missing || []).indexOf('расходы') === -1} label="Достаточно для отчёта доходов и расходов" />
                  <ProgressLine done={(quality?.missing || []).indexOf('себестоимость материалов') === -1} label="Достаточно для маржи услуг" />
                  <ProgressLine done={(quality?.missing || []).indexOf('загрузка рабочих мест') === -1} label="Достаточно для загрузки кресел" />
                  <ProgressLine done={(quality?.missing || []).indexOf('повторная запись') === -1} label="Достаточно для повторной записи" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </DashboardSection>

      <div className="grid gap-6 xl:grid-cols-3">
        <FinanceTable
          title="Прибыльность услуг"
          icon={Scissors}
          rows={dashboard?.services || []}
          columns={[
            ['service_name', 'Услуга'],
            ['gross_margin', 'Маржа'],
            ['revenue_per_hour', 'Выручка/час'],
            ['status', 'Статус'],
          ]}
          formatter={(key, value) => key.includes('margin') ? percent(value) : key.includes('hour') ? rub(value) : String(value || 'н/д')}
        />
        <FinanceTable
          title="Мастера"
          icon={Users}
          rows={dashboard?.staff || []}
          columns={[
            ['staff_name', 'Мастер'],
            ['revenue', 'Выручка'],
            ['occupancy', 'Загрузка'],
            ['rebooking_rate', 'Повторная запись'],
          ]}
          formatter={(key, value) => key === 'revenue' ? rub(value) : key.includes('rate') || key === 'occupancy' ? percent(value) : String(value || 'н/д')}
        />
        <FinanceTable
          title="Кресла и кабинеты"
          icon={Armchair}
          rows={dashboard?.workplaces || []}
          columns={[
            ['name', 'Место'],
            ['occupancy', 'Загрузка'],
            ['revenue_per_hour', 'Выручка/час'],
            ['idle_hours', 'Простой'],
          ]}
          formatter={(key, value) => key.includes('hour') ? rub(value) : key === 'occupancy' ? percent(value) : key === 'idle_hours' ? `${numberValue(value)} ч` : String(value || 'н/д')}
        />
      </div>

      <div id="finance-red-flags">
        <DashboardSection title="Красные зоны и следующие действия" description="Рекомендации появляются только из введённых данных. Если данных мало, система сначала покажет, что дозаполнить.">
          <div className="grid gap-3 md:grid-cols-2">
            {(dashboard?.recommendations || []).map((item) => (
              <RecommendationCard
                key={item.code}
                item={item}
                completedActions={completedActions}
                savingActionKey={savingActionKey}
                onToggleAction={toggleAction}
              />
            ))}
          </div>
        </DashboardSection>
      </div>
    </div>
  );
};

type FieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
};

const TextField: React.FC<FieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input value={value} onChange={(event) => onChange(event.target.value)} />
  </div>
);

const NumberField: React.FC<FieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input type="number" min="0" value={value} onChange={(event) => onChange(event.target.value)} />
  </div>
);

const MoneyField: React.FC<FieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input type="number" min="0" value={value} onChange={(event) => onChange(event.target.value)} placeholder="₽" />
  </div>
);

const SaveButton: React.FC<{ disabled: boolean; onClick: () => void }> = ({ disabled, onClick }) => (
  <Button onClick={onClick} disabled={disabled} className="gap-2">
    <Save className="h-4 w-4" />
    Сохранить и пересчитать
  </Button>
);

type FinanceDataState = 'empty' | 'partial' | 'ready';

type PrimaryFinanceAction = {
  label: string;
  target: 'entry' | 'service' | 'staff' | 'workplace' | 'red-flags';
};

type FinanceMetricKey = 'profit' | 'break_even' | 'workplace_revenue' | 'workplace_occupancy';

const metricMeta: Record<FinanceMetricKey, {
  title: string;
  source: string;
  formula: string;
  missing: string[];
  action: string;
}> = {
  profit: {
    title: 'Прибыль и маржа',
    source: 'Доходы, расходы, ФОТ, материалы и выплаты мастерам.',
    formula: 'Операционная прибыль = выручка - расходы. Маржа = прибыль / выручка.',
    missing: ['расходы', 'ФОТ', 'себестоимость материалов', 'выплаты мастерам'],
    action: 'Дозаполнить расходы и себестоимость, затем проверить услуги с низкой маржей.',
  },
  break_even: {
    title: 'Точка безубыточности',
    source: 'Постоянные расходы и валовая маржа.',
    formula: 'Точка безубыточности = постоянные расходы / валовая маржа.',
    missing: ['расходы', 'постоянные расходы', 'себестоимость материалов', 'выплаты мастерам'],
    action: 'Заполнить расходы и маржу услуг, чтобы увидеть минимальную дневную цель.',
  },
  workplace_revenue: {
    title: 'Выручка на рабочее место',
    source: 'Активные кресла/кабинеты, выручка и доступные часы.',
    formula: 'Выручка на кресло = выручка / активные рабочие места.',
    missing: ['рабочие места', 'доступные часы рабочих мест', 'выручка по рабочим местам'],
    action: 'Добавить рабочие места и часы, чтобы видеть, какие места приносят деньги.',
  },
  workplace_occupancy: {
    title: 'Загрузка рабочих мест',
    source: 'Доступные и занятые минуты по креслам, кабинетам или рабочим местам.',
    formula: 'Загрузка = занятые часы / доступные часы.',
    missing: ['рабочие места', 'доступные часы рабочих мест', 'занятые часы рабочих мест'],
    action: 'Заполнить расписание и занятые часы, затем искать простои по дням и местам.',
  },
};

const getFinanceDataState = (hasFinanceData: boolean, qualityScore: number, missing: string[]): FinanceDataState => {
  if (!hasFinanceData) return 'empty';
  if (qualityScore >= 70 && missing.length <= 2) return 'ready';
  return 'partial';
};

const getPrimaryFinanceAction = (state: FinanceDataState, missing: string[]): PrimaryFinanceAction => {
  if (state === 'empty') return { label: 'Начать учёт', target: 'entry' };
  if (state === 'ready') return { label: 'Проверить красные зоны', target: 'red-flags' };
  if (missing.indexOf('расходы') !== -1) return { label: 'Заполнить расходы', target: 'entry' };
  if (missing.indexOf('рабочие места') !== -1 || missing.indexOf('загрузка рабочих мест') !== -1) {
    return { label: 'Добавить рабочие места', target: 'workplace' };
  }
  if (missing.indexOf('себестоимость материалов') !== -1 || missing.indexOf('выплаты мастерам') !== -1) {
    return { label: 'Дозаполнить услуги', target: 'service' };
  }
  return { label: 'Дозаполнить данные', target: 'entry' };
};

const stateCopy: Record<FinanceDataState, { label: string; title: string; text: string; tone: string }> = {
  empty: {
    label: 'Нет данных',
    title: 'Начните с короткого учёта',
    text: 'Достаточно выручки, расходов и рабочих мест, чтобы увидеть первую финансовую картину.',
    tone: 'border-amber-200 bg-amber-50',
  },
  partial: {
    label: 'Данных мало',
    title: 'Анализируем то, что уже есть',
    text: 'Показатели по выручке и загрузке уже полезны. Для прибыли и маржи нужно дозаполнить расходы и себестоимость.',
    tone: 'border-sky-200 bg-sky-50',
  },
  ready: {
    label: 'Дашборд готов',
    title: 'Можно смотреть красные зоны',
    text: 'Данных достаточно для управленческого обзора. Следующий шаг - проверить проблемы и действия.',
    tone: 'border-emerald-200 bg-emerald-50',
  },
};

const metricDisplay = (value: KpiValue, formatter: (input: KpiValue) => string) => (
  value == null ? 'Не хватает данных' : formatter(value)
);

const metricIsUnavailable = (value: KpiValue) => value == null;

const ExecutiveFinanceSummary: React.FC<{
  dataState: FinanceDataState;
  period: { start: string; end: string };
  quality?: FinanceDashboard['data_quality'];
  kpis: Record<string, KpiValue>;
  explanations: Record<string, string>;
  statuses: Record<string, string>;
  history: FinanceHistoryPoint[];
  priorityItems: string[];
  primaryActionLabel: string;
  onPrimaryAction: () => void;
  selectedMetric: FinanceMetricKey | null;
  onSelectMetric: (metric: FinanceMetricKey) => void;
}> = ({ dataState, period, quality, kpis, explanations, statuses, history, priorityItems, primaryActionLabel, onPrimaryAction, selectedMetric, onSelectMetric }) => {
  const copy = stateCopy[dataState];
  const qualityScore = quality?.score;
  const qualityPercent = Math.max(0, Math.min(Number(qualityScore || 0), 100));

  return (
    <div className={cn('rounded-3xl border p-5 shadow-sm sm:p-6', copy.tone)}>
      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 ring-1 ring-slate-200">
                  {copy.label}
                </span>
                <span className="rounded-full bg-white/60 px-3 py-1 text-xs text-slate-600 ring-1 ring-slate-200">
                  {period.start} - {period.end}
                </span>
              </div>
              <h3 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">{copy.title}</h3>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-700">{copy.text}</p>
            </div>
            <Button onClick={onPrimaryAction} className="gap-2">
              {primaryActionLabel}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <ExecutiveMetricCard
              metricKey="profit"
              icon={CircleDollarSign}
              label="Прибыль"
              value={metricDisplay(kpis.operating_profit, rub)}
              hint={`Маржа: ${metricDisplay(kpis.operating_margin, percent)}`}
              explanation={explanations.operating_profit || explanations.operating_margin}
              unavailable={metricIsUnavailable(kpis.operating_profit)}
              status={statuses.operating_margin}
              selected={selectedMetric === 'profit'}
              onSelect={onSelectMetric}
            />
            <ExecutiveMetricCard
              metricKey="break_even"
              icon={Calculator}
              label="Безубыточность"
              value={metricDisplay(kpis.break_even_revenue, rub)}
              hint={`Дневная цель: ${metricDisplay(kpis.daily_revenue_target, rub)}`}
              explanation={explanations.break_even_revenue || explanations.daily_revenue_target}
              unavailable={metricIsUnavailable(kpis.break_even_revenue)}
              selected={selectedMetric === 'break_even'}
              onSelect={onSelectMetric}
            />
            <ExecutiveMetricCard
              metricKey="workplace_revenue"
              icon={Armchair}
              label="Кресло"
              value={metricDisplay(kpis.revenue_per_workplace, rub)}
              hint={`Кресло-час: ${metricDisplay(kpis.revenue_per_workplace_hour, rub)}`}
              explanation={explanations.revenue_per_workplace || explanations.revenue_per_workplace_hour}
              unavailable={metricIsUnavailable(kpis.revenue_per_workplace)}
              status={statuses.workplace_occupancy}
              selected={selectedMetric === 'workplace_revenue'}
              onSelect={onSelectMetric}
            />
            <ExecutiveMetricCard
              metricKey="workplace_occupancy"
              icon={Clock3}
              label="Загрузка"
              value={metricDisplay(kpis.workplace_occupancy, percent)}
              hint={`Простой: ${metricDisplay(kpis.idle_workplace_hours, numberValue)} ч`}
              explanation={explanations.workplace_occupancy || explanations.idle_workplace_hours}
              unavailable={metricIsUnavailable(kpis.workplace_occupancy)}
              status={statuses.workplace_occupancy}
              selected={selectedMetric === 'workplace_occupancy'}
              onSelect={onSelectMetric}
            />
          </div>

          <MiniTrendBars history={history} />
        </div>

        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-1">
          <div className="rounded-2xl bg-white/75 p-4 ring-1 ring-slate-200">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Качество данных</div>
                <div className="mt-1 text-2xl font-semibold text-slate-950">{qualityScore == null ? 'н/д' : `${qualityScore}/100`}</div>
              </div>
              {qualityScore != null && qualityScore >= 70 ? (
                <CheckCircle2 className="h-8 w-8 text-emerald-600" />
              ) : (
                <AlertTriangle className="h-8 w-8 text-amber-600" />
              )}
            </div>
            <div className="mt-3 text-sm leading-6 text-slate-600">
              {(quality?.missing || []).length > 0
                ? `Не хватает: ${(quality?.missing || []).slice(0, 3).join(', ')}.`
                : 'Критичных пробелов в данных нет.'}
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  qualityPercent >= 70 ? 'bg-emerald-500' : qualityPercent >= 40 ? 'bg-amber-500' : 'bg-rose-500',
                )}
                style={{ width: `${qualityPercent}%` }}
              />
            </div>
          </div>

          <div className="rounded-2xl bg-white/75 p-4 ring-1 ring-slate-200">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <Target className="h-4 w-4" />
              3 главные точки внимания
            </div>
            <div className="mt-3 space-y-2">
              {priorityItems.slice(0, 3).map((item, index) => (
                <div key={`${item}-${index}`} className="flex gap-3 rounded-xl bg-slate-50 p-3 text-sm leading-5 text-slate-700">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-950 text-xs font-semibold text-white">{index + 1}</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ExecutiveMetricCard: React.FC<{
  metricKey: FinanceMetricKey;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint?: string;
  explanation?: string;
  unavailable?: boolean;
  status?: string;
  selected: boolean;
  onSelect: (metric: FinanceMetricKey) => void;
}> = ({ metricKey, icon: Icon, label, value, hint, explanation, unavailable = false, status, selected, onSelect }) => (
  <button
    type="button"
    onClick={() => onSelect(metricKey)}
    className={cn(
      'rounded-2xl border bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md',
      unavailable ? 'border-amber-200 bg-amber-50 text-amber-950' : statusTone(status),
      selected ? 'ring-2 ring-slate-950/20' : '',
    )}
  >
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs font-semibold uppercase tracking-[0.14em] opacity-70">{label}</div>
      <Icon className="h-5 w-5 shrink-0 opacity-70" />
    </div>
    <div className="mt-3 min-h-8 text-xl font-semibold tracking-tight">{value}</div>
    {hint ? <div className="mt-1 text-sm opacity-75">{hint}</div> : null}
    {unavailable ? (
      <div className="mt-3 rounded-xl bg-white/70 px-3 py-2 text-xs leading-5 ring-1 ring-amber-200">
        {explanation || 'Нужно дозаполнить данные для расчёта.'}
      </div>
    ) : null}
    <div className="mt-3 text-xs font-medium opacity-70">Нажмите, чтобы посмотреть расчёт</div>
  </button>
);

const MetricDrilldown: React.FC<{
  metric: FinanceMetricKey;
  kpis: Record<string, KpiValue>;
  explanations: Record<string, string>;
  quality?: FinanceDashboard['data_quality'];
  servicesCount: number;
  staffCount: number;
  workplacesCount: number;
  onClose: () => void;
}> = ({ metric, kpis, explanations, quality, servicesCount, staffCount, workplacesCount, onClose }) => {
  const meta = metricMeta[metric];
  const missing = (quality?.missing || []).filter((item) => meta.missing.indexOf(item) !== -1);

  return (
    <div className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Детализация KPI</div>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">{meta.title}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">{meta.source}</p>
        </div>
        <Button variant="outline" size="sm" onClick={onClose}>Скрыть</Button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <DrilldownCard title="Как считается" text={meta.formula} />
        <DrilldownCard
          title="Что мешает точности"
          text={missing.length > 0 ? missing.join(', ') : 'Критичных пробелов для этого KPI не видно.'}
        />
        <DrilldownCard title="Следующее действие" text={meta.action} />
      </div>
      <div className="mt-4 grid gap-2 text-sm text-slate-600 sm:grid-cols-4">
        <div className="rounded-2xl bg-slate-50 p-3">Выручка: <span className="font-medium text-slate-950">{rub(kpis.revenue)}</span></div>
        <div className="rounded-2xl bg-slate-50 p-3">Услуги: <span className="font-medium text-slate-950">{servicesCount}</span></div>
        <div className="rounded-2xl bg-slate-50 p-3">Мастера: <span className="font-medium text-slate-950">{staffCount}</span></div>
        <div className="rounded-2xl bg-slate-50 p-3">Рабочие места: <span className="font-medium text-slate-950">{workplacesCount}</span></div>
      </div>
      {Object.keys(explanations).length > 0 ? (
        <div className="mt-4 rounded-2xl bg-amber-50 p-3 text-sm leading-6 text-amber-900 ring-1 ring-amber-200">
          {Object.values(explanations).slice(0, 2).join(' ')}
        </div>
      ) : null}
    </div>
  );
};

const DrilldownCard: React.FC<{ title: string; text: string }> = ({ title, text }) => (
  <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{title}</div>
    <div className="mt-2 text-sm leading-6 text-slate-700">{text}</div>
  </div>
);

const MiniTrendBars: React.FC<{ history: FinanceHistoryPoint[] }> = ({ history }) => {
  const points = history
    .filter((item) => Number(item.revenue || 0) > 0)
    .slice(-6);
  if (points.length < 2) {
    return (
      <div className="rounded-2xl bg-white/60 p-4 text-sm text-slate-600 ring-1 ring-slate-200">
        Динамика появится после нескольких периодов с выручкой.
      </div>
    );
  }
  const maxRevenue = Math.max(...points.map((item) => Number(item.revenue || 0)), 1);
  return (
    <div className="rounded-2xl bg-white/70 p-4 ring-1 ring-slate-200">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Динамика выручки</div>
          <div className="mt-1 text-sm text-slate-600">Последние периоды с данными</div>
        </div>
        <div className="text-sm font-semibold text-slate-950">{rub(points[points.length - 1]?.revenue)}</div>
      </div>
      <div className="mt-4 flex h-24 items-end gap-2">
        {points.map((item) => {
          const height = Math.max(12, Math.round((Number(item.revenue || 0) / maxRevenue) * 96));
          return (
            <div key={item.period_start} className="flex min-w-0 flex-1 flex-col items-center gap-2">
              <div
                className="w-full rounded-t-xl bg-slate-900/85"
                style={{ height: `${height}px` }}
                title={`${item.label}: ${rub(item.revenue)}`}
              />
              <div className="max-w-full truncate text-[10px] text-slate-500">{item.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const metricLabels: Record<string, string> = {
  revenue: 'Выручка',
  operating_margin: 'Маржа',
  no_show_rate: 'Неявки',
  rebooking_rate: 'Повторная запись',
  workplace_occupancy: 'Загрузка',
  revenue_per_workplace_hour: 'Выручка/час',
  gross_profit_per_workplace_hour: 'Прибыль/час',
};

const formatMetric = (metric: string, value: KpiValue) => {
  if (metric.includes('revenue') || metric.includes('profit')) return rub(value);
  if (metric.includes('margin') || metric.includes('rate') || metric.includes('occupancy')) return percent(value);
  return numberValue(value);
};

const ImpactPanel: React.FC<{ impact: FinanceImpact | null }> = ({ impact }) => (
  <Card className="border-slate-200/80 shadow-sm">
    <CardHeader>
      <CardTitle className="text-base">Влияние действий</CardTitle>
    </CardHeader>
    <CardContent className="space-y-3 text-sm">
      {impact ? (
        <>
          <div className="rounded-2xl bg-slate-50 p-4 text-slate-700">
            Отмечено действий: <span className="font-semibold text-slate-950">{impact.completed_actions_count}</span>. Сравниваем текущий период с предыдущим таким же периодом.
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {(impact.deltas || []).slice(0, 6).map((item) => (
              <div key={item.metric} className="rounded-2xl border border-slate-200 bg-white p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-slate-500">{metricLabels[item.metric] || item.metric}</div>
                <div className="mt-1 font-semibold text-slate-950">{formatMetric(item.metric, item.current)}</div>
                <div className={cn('mt-1 text-xs', item.direction === 'up' ? 'text-emerald-700' : item.direction === 'down' ? 'text-rose-700' : 'text-slate-500')}>
                  {item.delta == null ? 'нет сравнения' : `${item.direction === 'up' ? '+' : ''}${formatMetric(item.metric, item.delta)}`}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="rounded-2xl bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          Данных для сравнения пока нет.
        </div>
      )}
    </CardContent>
  </Card>
);

const HistoryPanel: React.FC<{
  history: FinanceHistoryPoint[];
  months: number;
  onChangeMonths: (months: number) => void;
}> = ({ history, months, onChangeMonths }) => (
  <Card className="border-slate-200/80 shadow-sm">
    <CardHeader>
      <CardTitle className="flex flex-wrap items-center justify-between gap-3 text-base">
        <span>История периодов</span>
        <div className="flex gap-1">
          {[3, 6, 12].map((item) => (
            <Button key={item} size="sm" variant={months === item ? 'default' : 'outline'} onClick={() => onChangeMonths(item)}>
              {item} мес.
            </Button>
          ))}
        </div>
      </CardTitle>
    </CardHeader>
    <CardContent>
      {history.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.12em] text-slate-500">
                <th className="pb-3 pr-3">Период</th>
                <th className="pb-3 pr-3">Выручка</th>
                <th className="pb-3 pr-3">Маржа</th>
                <th className="pb-3 pr-3">Неявки</th>
                <th className="pb-3 pr-3">Загрузка</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {history.map((item) => (
                <tr key={item.period_start}>
                  <td className="py-3 pr-3 font-medium text-slate-900">{item.label}</td>
                  <td className="py-3 pr-3">{rub(item.revenue)}</td>
                  <td className="py-3 pr-3">{percent(item.operating_margin)}</td>
                  <td className="py-3 pr-3">{percent(item.no_show_rate)}</td>
                  <td className="py-3 pr-3">{percent(item.workplace_occupancy)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-2xl bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          История появится после ввода или импорта данных за несколько месяцев.
        </div>
      )}
    </CardContent>
  </Card>
);

const InfoList: React.FC<{ title: string; items: string[]; empty: string }> = ({ title, items, empty }) => (
  <div>
    <div className="font-medium text-slate-950">{title}</div>
    <div className="mt-2 flex flex-wrap gap-2">
      {items.length > 0 ? items.map((item) => (
        <span key={item} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{item}</span>
      )) : <span className="text-slate-500">{empty}</span>}
    </div>
  </div>
);

const ProgressLine: React.FC<{ done: boolean; label: string }> = ({ done, label }) => (
  <div className="flex items-center gap-2">
    <span className={cn('h-2.5 w-2.5 rounded-full', done ? 'bg-emerald-500' : 'bg-amber-400')} />
    <span>{label}</span>
  </div>
);

const buildActionKey = (recommendationCode: string, bucket: string, actionText: string) => (
  `${recommendationCode}:${bucket}:${actionText.trim().toLowerCase()}`
);

const RecommendationCard: React.FC<{
  item: FinanceRecommendation;
  completedActions: Set<string>;
  savingActionKey: string | null;
  onToggleAction: (item: FinanceRecommendation, bucket: string, actionText: string, completed: boolean) => void;
}> = ({ item, completedActions, savingActionKey, onToggleAction }) => {
  const [showFullPlan, setShowFullPlan] = useState(false);
  const actions = item.actions || {};
  const dataNeeded = item.data_needed || [];
  const localosActions = item.localos_actions || [];
  const actionItems = [
    ...(actions.today || []).map((text) => ({ bucket: 'today', title: 'Сегодня', text })),
    ...(actions.seven_days || []).map((text) => ({ bucket: 'seven_days', title: '7 дней', text })),
    ...(actions.regular || []).map((text) => ({ bucket: 'regular', title: 'Регулярно', text })),
  ];
  const completedCount = actionItems.filter((action) => completedActions.has(buildActionKey(item.code, action.bucket, action.text))).length;
  const totalCount = actionItems.length;

  return (
    <div className={cn('rounded-2xl border p-4', item.severity === 'high' ? 'border-rose-200 bg-rose-50' : item.severity === 'low' ? 'border-slate-200 bg-slate-50' : 'border-amber-200 bg-amber-50')}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="font-semibold text-slate-950">{item.title}</div>
        {item.target_metric ? (
          <span className="rounded-full bg-white/70 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
            {item.target_metric}
          </span>
        ) : null}
      </div>
      <div className="mt-1 text-sm leading-6 text-slate-700">{item.text}</div>
      {totalCount > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-medium text-slate-600">
          <span>Выполнено: {completedCount}/{totalCount}</span>
          {dataNeeded.slice(0, 3).map((itemName) => (
            <span key={itemName} className="rounded-full bg-white/70 px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200">
              {itemName}
            </span>
          ))}
        </div>
      ) : null}

      <div className="mt-4 rounded-xl bg-white/70 p-3 ring-1 ring-slate-200">
        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Сделать сегодня</div>
        <ul className="mt-2 space-y-1.5 text-sm leading-5 text-slate-700">
          {(actions.today || []).slice(0, 2).map((actionText) => {
            const actionKey = buildActionKey(item.code, 'today', actionText);
            const checked = completedActions.has(actionKey);
            return (
              <li key={actionText} className="flex gap-2">
                <Checkbox
                  checked={checked}
                  disabled={savingActionKey === actionKey}
                  onCheckedChange={(value) => onToggleAction(item, 'today', actionText, value === true)}
                  className="mt-0.5"
                />
                <span className={cn(checked ? 'text-slate-400 line-through' : '')}>{actionText}</span>
              </li>
            );
          })}
          {(actions.today || []).length === 0 ? <li className="text-slate-500">Нет срочных действий.</li> : null}
        </ul>
      </div>

      {localosActions.length > 0 ? (
        <div className="mt-4 rounded-xl bg-white/70 p-3 ring-1 ring-slate-200">
          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            Что сделать в LocalOS
          </div>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {localosActions.map((action) => (
              <a
                key={`${action.route}-${action.label}`}
                href={action.route}
                className="group flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm transition hover:border-blue-200 hover:bg-blue-50"
              >
                <span>
                  <span className="font-medium text-slate-950">{action.label}</span>
                  {action.description ? (
                    <span className="mt-0.5 block text-xs leading-5 text-slate-500">{action.description}</span>
                  ) : null}
                </span>
                <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-400 transition group-hover:text-blue-600" />
              </a>
            ))}
          </div>
        </div>
      ) : null}

      <Collapsible open={showFullPlan} onOpenChange={setShowFullPlan}>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm" className="mt-4 gap-2">
            {showFullPlan ? 'Скрыть полный план' : 'Показать полный план'}
            <ChevronDown className={cn('h-4 w-4 transition-transform', showFullPlan ? 'rotate-180' : '')} />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-4 grid gap-3 lg:grid-cols-3">
          <ActionList
            recommendation={item}
            bucket="today"
            title="Сегодня"
            items={actions.today || []}
            completedActions={completedActions}
            savingActionKey={savingActionKey}
            onToggleAction={onToggleAction}
          />
          <ActionList
            recommendation={item}
            bucket="seven_days"
            title="7 дней"
            items={actions.seven_days || []}
            completedActions={completedActions}
            savingActionKey={savingActionKey}
            onToggleAction={onToggleAction}
          />
          <ActionList
            recommendation={item}
            bucket="regular"
            title="Регулярно"
            items={actions.regular || []}
            completedActions={completedActions}
            savingActionKey={savingActionKey}
            onToggleAction={onToggleAction}
          />
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};

const ActionList: React.FC<{
  recommendation: FinanceRecommendation;
  bucket: string;
  title: string;
  items: string[];
  completedActions: Set<string>;
  savingActionKey: string | null;
  onToggleAction: (item: FinanceRecommendation, bucket: string, actionText: string, completed: boolean) => void;
}> = ({ recommendation, bucket, title, items, completedActions, savingActionKey, onToggleAction }) => (
  <div className="rounded-xl bg-white/70 p-3 ring-1 ring-slate-200">
    <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{title}</div>
    <ul className="mt-2 space-y-1.5 text-sm leading-5 text-slate-700">
      {items.length > 0 ? items.map((item) => {
        const actionKey = buildActionKey(recommendation.code, bucket, item);
        const checked = completedActions.has(actionKey);
        return (
        <li key={item} className="flex gap-2">
          <Checkbox
            checked={checked}
            disabled={savingActionKey === actionKey}
            onCheckedChange={(value) => onToggleAction(recommendation, bucket, item, value === true)}
            className="mt-0.5"
          />
          <span className={cn(checked ? 'text-slate-400 line-through' : '')}>{item}</span>
        </li>
        );
      }) : (
        <li className="text-slate-500">Нет срочных действий.</li>
      )}
    </ul>
  </div>
);

const FinanceTable: React.FC<{
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  rows: Array<Record<string, KpiValue | string>>;
  columns: Array<[string, string]>;
  formatter: (key: string, value: KpiValue | string) => string;
}> = ({ title, icon: Icon, rows, columns, formatter }) => (
  <Card className="border-slate-200/80 shadow-sm">
    <CardHeader>
      <CardTitle className="flex items-center gap-2 text-base">
        <Icon className="h-4 w-4 text-slate-500" />
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent>
      {rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.12em] text-slate-500">
                {columns.map(([key, label]) => <th key={key} className="pb-3 pr-3 font-semibold">{label}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.slice(0, 6).map((row, index) => (
                <tr key={`${title}-${index}`} className="text-slate-800">
                  {columns.map(([key]) => (
                    <td key={key} className="py-3 pr-3 align-top">
                      {formatter(key, row[key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-2xl bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          Данных пока нет. Добавьте хотя бы одну строку в быстром вводе.
        </div>
      )}
    </CardContent>
  </Card>
);

export default FinanceFirstStep;
