import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
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
  period?: {
    start_date: string;
    end_date: string;
  };
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
  setupTools?: React.ReactNode;
  legacyTools?: React.ReactNode;
};

type FinancePeriod = {
  start: string;
  end: string;
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

const formatFinanceTableCell = (key: string, value: KpiValue | string) => {
  if (value == null || value === '') return 'н/д';
  if (key.indexOf('margin') !== -1 || key.indexOf('rate') !== -1 || key === 'occupancy') return percent(value);
  if (key === 'idle_hours') return `${numberValue(value)} ч`;
  if (key.indexOf('hour') !== -1 || key === 'revenue' || key === 'gross_profit') return rub(value);
  if (key === 'visits_count') return numberValue(value);
  return String(value);
};

const tooltipMoney = (value: unknown) => rub(Number(value));
const tooltipPercent = (value: unknown) => percent(Number(value));

const toFiniteNumber = (value: KpiValue) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
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

const dataInputModes = [
  { key: 'entry', title: 'Деньги', text: 'Выручка и расходы' },
  { key: 'service', title: 'Услуга', text: 'Цена, маржа, длительность' },
  { key: 'staff', title: 'Мастер', text: 'Визиты и часы' },
  { key: 'workplace', title: 'Рабочее место', text: 'Доступность и загрузка' },
];

const dateToInputValue = (date: Date) => date.toISOString().slice(0, 10);

const getDefaultFinancePeriod = (): FinancePeriod => {
  const end = new Date();
  const start = new Date(end);
  start.setMonth(start.getMonth() - 3);
  start.setDate(1);
  return {
    start: dateToInputValue(start),
    end: dateToInputValue(end),
  };
};

const getFinancePeriodByPreset = (preset: string): FinancePeriod => {
  const today = new Date();
  const end = new Date(today);
  const start = new Date(today);

  if (preset === 'last_30_days') {
    start.setDate(start.getDate() - 29);
    return { start: dateToInputValue(start), end: dateToInputValue(end) };
  }

  if (preset === 'current_month') {
    start.setDate(1);
    return { start: dateToInputValue(start), end: dateToInputValue(end) };
  }

  if (preset === 'previous_month') {
    start.setMonth(start.getMonth() - 1, 1);
    end.setDate(1);
    end.setDate(0);
    return { start: dateToInputValue(start), end: dateToInputValue(end) };
  }

  if (preset === 'last_year') {
    start.setFullYear(start.getFullYear() - 1);
    start.setDate(start.getDate() + 1);
    return { start: dateToInputValue(start), end: dateToInputValue(end) };
  }

  if (preset === 'all_time') {
    return { start: '', end: '' };
  }

  return getDefaultFinancePeriod();
};

const getMonthPeriod = (value: string): FinancePeriod => {
  const date = value ? new Date(value) : new Date();
  const start = new Date(date.getFullYear(), date.getMonth(), 1);
  const end = new Date(date.getFullYear(), date.getMonth() + 1, 0);
  return { start: dateToInputValue(start), end: dateToInputValue(end) };
};

export const FinanceFirstStep: React.FC<FinanceFirstStepProps> = ({ currentBusinessId, setupTools, legacyTools }) => {
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
  const [activeFinanceTab, setActiveFinanceTab] = useState('overview');
  const [periodPreset, setPeriodPreset] = useState('last_3_months');
  const [period, setPeriod] = useState<FinancePeriod>(getDefaultFinancePeriod);
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
  const [manualPeriod, setManualPeriod] = useState(() => {
    const initial = getDefaultFinancePeriod();
    return {
      periodType: 'custom',
      date: initial.end,
      start: initial.start,
      end: initial.end,
      comment: '',
    };
  });

  const loadDashboard = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    setMessage(null);
    try {
      const token = localStorage.getItem('auth_token');
      const params = new URLSearchParams({ business_id: currentBusinessId });
      if (periodPreset === 'all_time') {
        params.set('range', 'all');
      } else {
        params.set('from', period.start);
        params.set('to', period.end);
      }
      const response = await fetch(
        `/api/finance/dashboard?${params.toString()}`,
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
  }, [currentBusinessId, period.end, period.start, periodPreset]);

  const changePeriodPreset = (preset: string) => {
    setPeriodPreset(preset);
    if (preset !== 'custom') {
      setPeriod(getFinancePeriodByPreset(preset));
    }
  };

  const changePeriod = (nextPeriod: FinancePeriod) => {
    setPeriodPreset('custom');
    setPeriod(nextPeriod);
  };

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

    const manualStart = manualPeriod.start || period.start;
    const manualEnd = manualPeriod.end || period.end;
    const manualDate = manualPeriod.date || manualEnd;
    const commentSuffix = manualPeriod.comment ? ` · ${manualPeriod.comment}` : '';
    const entries = [];
    if (mode === 'entry') {
      if (entry.revenue) entries.push({ date: manualDate, type: 'revenue', category: 'sales', amount: Number(entry.revenue), comment: `Выручка за период ${manualStart} - ${manualEnd}${commentSuffix}` });
      if (entry.rent) entries.push({ date: manualDate, type: 'expense', category: 'rent', amount: Number(entry.rent), comment: `Аренда за период ${manualStart} - ${manualEnd}${commentSuffix}` });
      if (entry.payroll) entries.push({ date: manualDate, type: 'expense', category: 'payroll', amount: Number(entry.payroll), comment: `ФОТ за период ${manualStart} - ${manualEnd}${commentSuffix}` });
      if (entry.materials) entries.push({ date: manualDate, type: 'expense', category: 'materials', amount: Number(entry.materials), comment: `Материалы за период ${manualStart} - ${manualEnd}${commentSuffix}` });
      if (entry.marketing) entries.push({ date: manualDate, type: 'expense', category: 'marketing', amount: Number(entry.marketing), comment: `Маркетинг за период ${manualStart} - ${manualEnd}${commentSuffix}` });
      if (entry.taxes) entries.push({ date: manualDate, type: 'expense', category: 'taxes', amount: Number(entry.taxes), comment: `Налоги за период ${manualStart} - ${manualEnd}${commentSuffix}` });
    }

    const workplaces = mode === 'workplace' ? [{
      client_key: workplace.name || 'workplace',
      name: workplace.name || 'Рабочее место',
      type: workplace.type,
      is_active: true,
    }] : [];

    const payload = {
      business_id: currentBusinessId,
      period_start: manualStart,
      period_end: manualEnd,
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
        period_start: manualStart,
        period_end: manualEnd,
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
  const actionPlanRecommendations = (dashboard?.recommendations || []).slice(0, 3);
  const hiddenActionPlanCount = Math.max((dashboard?.recommendations || []).length - actionPlanRecommendations.length, 0);

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
      setActiveFinanceTab('overview');
      document.getElementById('finance-next-action')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    setActiveInputStep(primaryAction.target);
    setActiveFinanceTab('data');
    document.getElementById('finance-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="space-y-6">
      {!currentBusinessId ? (
        <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Сначала выберите бизнес в верхнем переключателе.
        </div>
      ) : null}

      {message ? (
        <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700 ring-1 ring-slate-200">
          {message}
        </div>
      ) : null}

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <FinanceHeader
          period={period}
          periodPreset={periodPreset}
          actualPeriod={dashboard?.period}
          quality={quality}
          onPeriodPresetChange={changePeriodPreset}
          onPeriodChange={changePeriod}
          onRefresh={loadDashboard}
          loading={loading}
          disabled={!currentBusinessId}
        />

        <div className="mt-5 grid gap-4 xl:grid-cols-[0.9fr_1.25fr]">
          <FinanceKpiGrid
            kpis={kpis}
            statuses={dashboard?.statuses || {}}
            explanations={dashboard?.explanations || {}}
            impact={impact}
          />
          <FinanceRevenueChart history={history} months={historyMonths} onChangeMonths={loadHistory} />
        </div>
      </section>

      <section id="finance-tabs" className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <Tabs value={activeFinanceTab} onValueChange={setActiveFinanceTab}>
          <TabsList className="grid h-auto w-full grid-cols-2 gap-1 lg:grid-cols-6">
            <TabsTrigger value="overview">Обзор</TabsTrigger>
            <TabsTrigger value="data">Данные</TabsTrigger>
            <TabsTrigger value="services">Услуги</TabsTrigger>
            <TabsTrigger value="team">Команда</TabsTrigger>
            <TabsTrigger value="workplaces">Рабочие места</TabsTrigger>
            <TabsTrigger value="settings">Настройки</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-5 pt-5">
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
            <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
              <FinanceAttentionCards
                recommendations={dashboard?.recommendations || []}
                kpis={kpis}
                onOpenPlan={() => {
                  document.getElementById('finance-next-action')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }}
              />
              <FinanceNextAction
                dataState={dataState}
                missing={quality?.missing || []}
                onSecondary={() => {
                  setActiveFinanceTab('data');
                  document.getElementById('finance-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }}
              />
            </div>
            <ImpactPanel impact={impact} />
            <div id="finance-next-action">
              <DashboardSection
                title="Что сделать дальше"
                description="Начните с первого пункта. LocalOS показывает только ближайшие действия, которые влияют на деньги."
              >
                {actionPlanRecommendations.length > 0 ? (
                  <div className="space-y-3">
                    {hiddenActionPlanCount > 0 ? (
                      <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600 ring-1 ring-slate-200">
                        Показаны 3 главных действия. Ещё {hiddenActionPlanCount} появятся после выполнения приоритетных шагов.
                      </div>
                    ) : null}
                    <div className="grid gap-3 md:grid-cols-2">
                      {actionPlanRecommendations.map((item) => (
                        <RecommendationCard
                          key={item.code}
                          item={item}
                          completedActions={completedActions}
                          savingActionKey={savingActionKey}
                          onToggleAction={toggleAction}
                        />
                      ))}
                    </div>
                  </div>
                ) : (
                  <FinanceEmptyState
                    missing={quality?.missing || []}
                    onAddData={() => {
                      setActiveFinanceTab('data');
                      document.getElementById('finance-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }}
                  />
                )}
              </DashboardSection>
            </div>
          </TabsContent>

          <TabsContent value="data" className="space-y-5 pt-5">
            <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
              <Card id="finance-quick-input" className="border-slate-200/80 shadow-sm">
                <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <ClipboardList className="h-4 w-4 text-slate-500" />
                      Добавить данные
                    </CardTitle>
                    <div className="mt-1 text-sm text-slate-500">
                      Вносите по одному блоку: деньги, услугу, мастера или рабочее место.
                    </div>
                  </div>
                  <Button variant="outline" onClick={fillDemoSalon} className="gap-2">
                    <PlayCircle className="h-4 w-4" />
                    Пример
                  </Button>
                </CardHeader>
                <CardContent>
                  <ManualPeriodContext
                    value={manualPeriod}
                    onChange={setManualPeriod}
                  />
                  <div className="mb-4">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Что добавить
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    {dataInputModes.map((step) => (
                      <button
                        key={step.key}
                        type="button"
                        onClick={() => setActiveInputStep(step.key)}
                        className={cn(
                          'rounded-2xl border px-4 py-3 text-left text-sm transition hover:border-slate-300',
                          activeInputStep === step.key
                            ? 'border-slate-950 bg-slate-950 text-white shadow-sm'
                            : 'border-slate-200 bg-white text-slate-700',
                        )}
                      >
                        <div className={cn('font-semibold', activeInputStep === step.key ? 'text-white' : 'text-slate-950')}>
                          {step.title}
                        </div>
                        <div className={cn('mt-1 truncate text-xs', activeInputStep === step.key ? 'text-slate-200' : 'text-slate-500')}>
                          {step.text}
                        </div>
                      </button>
                    ))}
                    </div>
                  </div>
                  <Tabs value={activeInputStep} onValueChange={setActiveInputStep}>
                    <TabsContent value="entry" className="space-y-4 pt-0">
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

                    <TabsContent value="service" className="space-y-4 pt-0">
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

                    <TabsContent value="staff" className="space-y-4 pt-0">
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

                    <TabsContent value="workplace" className="space-y-4 pt-0">
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

              <FinanceDataQualityPanel quality={quality} analyzableItems={analyzableItems} />
            </div>
          </TabsContent>

          <TabsContent value="services" className="pt-5">
            <FinanceTable
              title="Прибыльность услуг"
              icon={Scissors}
              rows={dashboard?.services || []}
              description="Что приносит деньги, занимает время и требует дозаполнения себестоимости."
              columns={[
                ['service_name', 'Услуга'],
                ['revenue', 'Выручка'],
                ['visits_count', 'Продаж'],
                ['gross_margin', 'Маржа'],
                ['revenue_per_hour', 'Выручка/час'],
                ['status', 'Статус'],
              ]}
              formatter={formatFinanceTableCell}
            />
          </TabsContent>

          <TabsContent value="team" className="pt-5">
            <FinanceTable
              title="Команда"
              icon={Users}
              rows={dashboard?.staff || []}
              description="Выручка, загрузка и повторная запись по мастерам."
              columns={[
                ['staff_name', 'Мастер'],
                ['revenue', 'Выручка'],
                ['visits_count', 'Визиты'],
                ['occupancy', 'Загрузка'],
                ['rebooking_rate', 'Повторная запись'],
                ['no_show_rate', 'Неявки'],
              ]}
              formatter={formatFinanceTableCell}
            />
          </TabsContent>

          <TabsContent value="workplaces" className="space-y-5 pt-5">
            <FinanceVisuals history={history} workplaces={dashboard?.workplaces || []} services={dashboard?.services || []} />
            <FinanceTable
              title="Рабочие места"
              icon={Armchair}
              rows={dashboard?.workplaces || []}
              description="Кресла, кабинеты и места: загрузка, простой и деньги за час."
              columns={[
                ['name', 'Место'],
                ['revenue', 'Выручка'],
                ['occupancy', 'Загрузка'],
                ['revenue_per_hour', 'Выручка/час'],
                ['idle_hours', 'Простой'],
              ]}
              formatter={formatFinanceTableCell}
            />
          </TabsContent>

          <TabsContent value="settings" className="space-y-5 pt-5">
            <HistoryPanel history={history} months={historyMonths} onChangeMonths={loadHistory} />
            {setupTools ? <div>{setupTools}</div> : null}
            {legacyTools ? <div>{legacyTools}</div> : null}
          </TabsContent>
        </Tabs>
      </section>
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

type ManualPeriodValue = {
  periodType: string;
  date: string;
  start: string;
  end: string;
  comment: string;
};

const ManualPeriodContext: React.FC<{
  value: ManualPeriodValue;
  onChange: (value: ManualPeriodValue) => void;
}> = ({ value, onChange }) => {
  const [open, setOpen] = React.useState(false);

  const changeType = (periodType: string) => {
    if (periodType === 'day') {
      onChange({ ...value, periodType, start: value.date, end: value.date });
      return;
    }
    if (periodType === 'month') {
      const monthPeriod = getMonthPeriod(value.date);
      onChange({ ...value, periodType, start: monthPeriod.start, end: monthPeriod.end });
      return;
    }
    onChange({ ...value, periodType });
  };

  const changeDate = (date: string) => {
    if (value.periodType === 'day') {
      onChange({ ...value, date, start: date, end: date });
      return;
    }
    if (value.periodType === 'month') {
      const monthPeriod = getMonthPeriod(date);
      onChange({ ...value, date, start: monthPeriod.start, end: monthPeriod.end });
      return;
    }
    onChange({ ...value, date });
  };

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mb-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Период данных</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-700">
            <span className="font-medium text-slate-950">{formatPeriodLabel({ start: value.start, end: value.end })}</span>
            <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
              Источник: вручную
            </span>
          </div>
        </div>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <ChevronDown className={cn('h-4 w-4 transition-transform', open ? 'rotate-180' : '')} />
            {open ? 'Скрыть период' : 'Изменить период'}
          </Button>
        </CollapsibleTrigger>
      </div>
      <CollapsibleContent>
        <div className="mt-4 grid gap-3 md:grid-cols-5">
          <div className="space-y-2">
            <Label>Тип периода</Label>
            <Select value={value.periodType} onValueChange={changeType}>
              <SelectTrigger className="bg-white"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="day">День</SelectItem>
                <SelectItem value="month">Месяц</SelectItem>
                <SelectItem value="custom">Произвольный период</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DateField label={value.periodType === 'month' ? 'Месяц по дате' : 'Дата'} value={value.date} onChange={changeDate} />
          <DateField label="Начало периода" value={value.start} onChange={(start) => onChange({ ...value, periodType: 'custom', start })} />
          <DateField label="Конец периода" value={value.end} onChange={(end) => onChange({ ...value, periodType: 'custom', end })} />
          <TextField label="Комментарий" value={value.comment} onChange={(comment) => onChange({ ...value, comment })} />
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

const DateField: React.FC<FieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input type="date" value={value} onChange={(event) => onChange(event.target.value)} />
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

const humanMetricLabel = (value?: string | null) => {
  const key = String(value || '').trim();
  const labels: Record<string, string> = {
    no_show_rate: 'Неявки',
    rebooking_rate: 'Повторная запись',
    workplace_occupancy: 'Загрузка рабочих мест',
    revenue: 'Выручка',
    operating_profit: 'Прибыль',
    operating_margin: 'Маржа',
    money: 'Деньги',
    aggregate: 'Сводные данные',
  };
  return labels[key] || key.replaceAll('_', ' ');
};

const getQuietStatusBorder = (status?: string) => {
  if (status === 'green') return 'border-emerald-200';
  if (status === 'yellow') return 'border-amber-200';
  if (status === 'red') return 'border-rose-200';
  return 'border-slate-200';
};

const getFinanceImpactDelta = (impact: FinanceImpact | null, metric: string) => {
  const item = (impact?.deltas || []).find((delta) => delta.metric === metric);
  if (!item || item.delta == null) return null;
  const delta = Number(item.delta);
  if (!Number.isFinite(delta) || delta === 0) {
    return { label: 'без изменений', tone: 'bg-slate-50 text-slate-600 ring-1 ring-slate-200' };
  }
  const sign = delta > 0 ? '+' : '';
  return {
    label: `${sign}${rub(delta)} к прошлому периоду`,
    tone: delta > 0
      ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100'
      : 'bg-rose-50 text-rose-700 ring-1 ring-rose-100',
  };
};

const formatPeriodLabel = (period: { start: string; end: string }) => (
  !period.start || !period.end
    ? 'Всё время'
    :
  `${new Date(period.start).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })} - ${new Date(period.end).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' })}`
);

const shortMissingLabel = (missing: string[]) => {
  if (missing.indexOf('расходы') !== -1) return 'не хватает расходов';
  if (missing.indexOf('себестоимость материалов') !== -1) return 'нет себестоимости';
  if (missing.indexOf('выплаты мастерам') !== -1) return 'нет выплат мастерам';
  if (missing.indexOf('повторная запись') !== -1) return 'нет повторной записи';
  if (missing.indexOf('загрузка рабочих мест') !== -1) return 'нет загрузки мест';
  return missing[0] || 'данные заполнены';
};

const FinanceHeader: React.FC<{
  period: FinancePeriod;
  periodPreset: string;
  actualPeriod?: { start_date: string; end_date: string };
  quality?: FinanceDashboard['data_quality'];
  onPeriodPresetChange: (preset: string) => void;
  onPeriodChange: (period: FinancePeriod) => void;
  onRefresh: () => void;
  loading: boolean;
  disabled: boolean;
}> = ({ period, periodPreset, actualPeriod, quality, onPeriodPresetChange, onPeriodChange, onRefresh, loading, disabled }) => {
  const missing = quality?.missing || [];
  const isAllTime = periodPreset === 'all_time';
  const displayedPeriod = actualPeriod
    ? { start: actualPeriod.start_date, end: actualPeriod.end_date }
    : period;
  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 xl:flex-row xl:items-center xl:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-500">Период</span>
        <Select value={periodPreset} onValueChange={onPeriodPresetChange}>
          <SelectTrigger className="h-9 w-[160px] bg-white">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="last_30_days">30 дней</SelectItem>
            <SelectItem value="last_3_months">3 месяца</SelectItem>
            <SelectItem value="current_month">Текущий месяц</SelectItem>
            <SelectItem value="previous_month">Прошлый месяц</SelectItem>
            <SelectItem value="last_year">Год</SelectItem>
            <SelectItem value="all_time">Всё время</SelectItem>
            <SelectItem value="custom">Свой период</SelectItem>
          </SelectContent>
        </Select>
        {!isAllTime ? (
          <>
            <Input
              type="date"
              value={period.start}
              onChange={(event) => onPeriodChange({ ...period, start: event.target.value })}
              className="h-9 w-[150px]"
              disabled={disabled}
            />
            <Input
              type="date"
              value={period.end}
              onChange={(event) => onPeriodChange({ ...period, end: event.target.value })}
              className="h-9 w-[150px]"
              disabled={disabled}
            />
          </>
        ) : null}
        <span className="rounded-full bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
          {isAllTime ? `Всё время: ${formatPeriodLabel(displayedPeriod)}` : formatPeriodLabel(displayedPeriod)}
        </span>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
          Качество: {quality ? `${quality.score}/100` : 'н/д'}
        </span>
        <span className="rounded-full bg-slate-950 px-3 py-1 text-xs font-medium text-white">
          {missing.length > 0 ? shortMissingLabel(missing) : 'готово к анализу'}
        </span>
      </div>
      <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading || disabled} className="gap-2">
        <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
        Обновить
      </Button>
    </div>
  );
};

const FinanceKpiGrid: React.FC<{
  kpis: Record<string, KpiValue>;
  statuses: Record<string, string>;
  explanations: Record<string, string>;
  impact: FinanceImpact | null;
}> = ({ kpis, statuses, explanations, impact }) => {
  const revenueDelta = getFinanceImpactDelta(impact, 'revenue');
  const cards = [
    {
      label: 'Прибыль',
      value: kpis.operating_profit,
      display: metricDisplay(kpis.operating_profit, rub),
      hint: kpis.operating_margin != null ? `Маржа ${percent(kpis.operating_margin)}` : 'Не хватает расходов',
      status: statuses.operating_margin,
      icon: Calculator,
    },
    {
      label: 'Загрузка',
      value: kpis.workplace_occupancy,
      display: metricDisplay(kpis.workplace_occupancy, percent),
      hint: kpis.idle_workplace_hours != null ? `Простой ${numberValue(kpis.idle_workplace_hours)} ч` : 'Нет часов рабочих мест',
      status: statuses.workplace_occupancy,
      icon: Gauge,
    },
    {
      label: 'Повторная запись',
      value: kpis.rebooking_rate,
      display: metricDisplay(kpis.rebooking_rate, percent),
      hint: explanations.rebooking_rate ? 'Нужны записи клиентов' : 'Следующий визит',
      status: statuses.rebooking_rate,
      icon: RefreshCw,
    },
  ];

  return (
    <div className="grid gap-3">
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Выручка</div>
            <div className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
              {kpis.revenue == null ? 'Нет данных' : rub(kpis.revenue)}
            </div>
          </div>
          <CircleDollarSign className="h-5 w-5 text-slate-400" />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <span>Средний чек: {kpis.average_ticket != null ? rub(kpis.average_ticket) : 'н/д'}</span>
          {revenueDelta ? (
            <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium', revenueDelta.tone)}>
              {revenueDelta.label}
            </span>
          ) : null}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {cards.map((card) => {
          const Icon = card.icon;
          const unavailable = card.value == null;
          return (
            <div
              key={card.label}
              className={cn(
                'flex min-h-[116px] flex-col justify-between rounded-2xl border bg-white p-4',
                unavailable ? 'border-slate-200' : getQuietStatusBorder(card.status),
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="truncate text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{card.label}</div>
                <Icon className="h-4 w-4 shrink-0 text-slate-400" />
              </div>
              <div>
                <div className="mt-3 text-xl font-semibold tracking-tight text-slate-950">{card.display}</div>
                <div className="mt-1 truncate text-xs text-slate-500">{card.hint}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const FinanceRevenueChart: React.FC<{
  history: FinanceHistoryPoint[];
  months: number;
  onChangeMonths: (months: number) => void;
}> = ({ history, months, onChangeMonths }) => {
  const trendData = history
    .map((item) => ({
      label: item.label,
      revenue: toFiniteNumber(item.revenue),
    }))
    .filter((item) => item.revenue != null)
    .slice(-12);

  return (
    <Card className="border-slate-200/80 shadow-sm">
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base">Динамика выручки</CardTitle>
          <div className="mt-1 text-sm text-slate-500">Помесячная динамика по выбранным данным.</div>
        </div>
        <div className="flex gap-1">
          {[3, 6, 12].map((item) => (
            <Button key={item} size="sm" variant={months === item ? 'default' : 'outline'} onClick={() => onChangeMonths(item)}>
              {item} мес.
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {trendData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={trendData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="financeHeroRevenueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0f172a" stopOpacity={0.22} />
                  <stop offset="95%" stopColor="#0f172a" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
              <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} tickFormatter={(value) => `${Math.round(Number(value) / 1000)}к`} />
              <Tooltip formatter={(value) => [tooltipMoney(value), 'Выручка']} />
              <Area type="monotone" dataKey="revenue" stroke="#0f172a" fill="url(#financeHeroRevenueGradient)" strokeWidth={2} connectNulls />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-[260px] items-center justify-center rounded-2xl bg-slate-50 px-5 text-center text-sm leading-6 text-slate-500">
            График появится после ввода или импорта выручки.
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const FinanceAttentionCards: React.FC<{
  recommendations: FinanceRecommendation[];
  kpis: Record<string, KpiValue>;
  onOpenPlan: () => void;
}> = ({ recommendations, kpis, onOpenPlan }) => {
  const findRecommendation = (markers: string[]) => recommendations.find((item) => {
    const value = `${item.code} ${item.target_metric} ${item.title} ${item.text}`.toLowerCase();
    return markers.some((marker) => value.includes(marker));
  });
  const attention = [
    {
      title: 'Неявки',
      value: percent(kpis.no_show_rate),
      problem: findRecommendation(['no_show', 'неяв'])?.title || 'Потери из-за несостоявшихся визитов',
      impact: 'Окна заняты в расписании, но не приносят деньги.',
    },
    {
      title: 'Повторная запись',
      value: percent(kpis.rebooking_rate),
      problem: findRecommendation(['rebooking', 'повтор'])?.title || 'Клиенты уходят без следующего визита',
      impact: 'Будущая выручка не закрепляется заранее.',
    },
    {
      title: 'Загрузка рабочих мест',
      value: percent(kpis.workplace_occupancy),
      problem: findRecommendation(['workplace', 'occupancy', 'загруз'])?.title || 'Часть рабочих часов может простаивать',
      impact: 'Кресла и кабинеты есть, но часть времени не монетизируется.',
    },
  ];
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Красные зоны</div>
          <div className="mt-1 text-sm text-slate-500">Три показателя, которые быстрее всего влияют на деньги.</div>
        </div>
        <Button variant="outline" size="sm" onClick={onOpenPlan}>
          План
        </Button>
      </div>
      <div className="mt-4 divide-y divide-slate-100">
        {attention.map((item) => (
          <div key={item.title} className="grid gap-3 py-3 text-sm md:grid-cols-[0.7fr_1.2fr_auto] md:items-center">
            <div>
              <div className="font-medium text-slate-950">{item.title}</div>
              <div className="mt-0.5 text-slate-500">{item.value}</div>
            </div>
            <div>
              <div className="text-slate-700">{item.problem}</div>
              <div className="mt-0.5 text-slate-500">{item.impact}</div>
            </div>
            <Button variant="ghost" size="sm" className="justify-start md:justify-center" onClick={onOpenPlan}>
              Что сделать
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
};

const FinanceNextAction: React.FC<{
  dataState: FinanceDataState;
  missing: string[];
  onSecondary: () => void;
}> = ({ dataState, missing, onSecondary }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4">
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <div className="text-sm font-semibold text-slate-950">Следующее действие</div>
        <div className="mt-1 text-sm leading-6 text-slate-700">
          {dataState === 'ready'
            ? 'Посмотрите план действий и отметьте, что команда уже сделала.'
            : missing.length > 0
              ? `Сначала закройте главный пробел в данных: ${missing[0]}.`
              : 'Начните с базового ввода, чтобы появился первый расчёт.'}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={onSecondary}>Что заполнить</Button>
      </div>
    </div>
  </div>
);

const FinanceEmptyState: React.FC<{ missing: string[]; onAddData: () => void }> = ({ missing, onAddData }) => (
  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">
    <div className="font-semibold text-slate-950">План появится после данных</div>
    <div className="mt-1">
      {missing.length > 0
        ? `Сначала добавьте: ${missing.slice(0, 3).join(', ')}.`
        : 'Сначала добавьте выручку, расходы, услуги, мастеров или рабочие места.'}
    </div>
    <div className="mt-3">
      <Button size="sm" onClick={onAddData}>
        Добавить данные
      </Button>
    </div>
  </div>
);

const FinanceDataQualityPanel: React.FC<{
  quality?: FinanceDashboard['data_quality'];
  analyzableItems: string[];
}> = ({ quality, analyzableItems }) => {
  const score = Math.max(0, Math.min(Number(quality?.score || 0), 100));
  const missing = quality?.missing || [];
  const approximate = quality?.approximate || [];
  return (
    <Card className="border-slate-200/80 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3 text-base">
          <span className="flex items-center gap-2">
            {quality && score >= 70 ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 text-amber-600" />}
            Качество данных
          </span>
          <span className="text-sm font-semibold text-slate-950">{quality ? `${score}/100` : 'н/д'}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className={cn('h-full rounded-full', score >= 70 ? 'bg-emerald-500' : score >= 40 ? 'bg-amber-500' : 'bg-rose-500')}
            style={{ width: `${score}%` }}
          />
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Не хватает</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {missing.length > 0 ? missing.slice(0, 6).map((item) => (
              <span key={item} className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-100">{item}</span>
            )) : (
              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-100">Базовые данные заполнены</span>
            )}
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl bg-slate-50 p-3">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Можно анализировать</div>
            <div className="mt-2 text-sm leading-5 text-slate-700">
              {analyzableItems.length > 0 ? analyzableItems.slice(0, 3).join(', ') : 'Пока недостаточно данных'}
            </div>
          </div>
          <div className="rounded-2xl bg-slate-50 p-3">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Предварительно</div>
            <div className="mt-2 text-sm leading-5 text-slate-700">
              {approximate.length > 0 ? approximate.slice(0, 3).join(', ') : 'Критичных допущений нет'}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

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
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
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
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{copy.text}</p>
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
              label="Рабочее место"
              value={metricDisplay(kpis.revenue_per_workplace, rub)}
              hint={`Выручка за час: ${metricDisplay(kpis.revenue_per_workplace_hour, rub)}`}
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
      'flex min-h-[148px] flex-col justify-between rounded-2xl border bg-white p-4 text-left text-slate-900 shadow-sm transition hover:border-slate-300 hover:shadow-md',
      unavailable ? 'border-amber-200' : status === 'red' ? 'border-rose-200' : status === 'yellow' ? 'border-amber-200' : status === 'green' ? 'border-emerald-200' : 'border-slate-200',
      selected ? 'ring-2 ring-slate-950/20' : '',
    )}
  >
    <div>
      <div className="flex items-center justify-between gap-3">
        <div className="truncate text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</div>
        <Icon className="h-5 w-5 shrink-0 text-slate-400" />
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">{value}</div>
      {hint ? <div className="mt-1 line-clamp-2 text-sm leading-5 text-slate-600">{hint}</div> : null}
    </div>
    {unavailable ? (
      <div className="mt-3 line-clamp-2 rounded-xl bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
        {explanation || 'Нужно дозаполнить данные для расчёта.'}
      </div>
    ) : (
      <div className="mt-3 text-xs font-medium text-slate-500">Открыть расчёт</div>
    )}
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

const FinanceVisuals: React.FC<{
  history: FinanceHistoryPoint[];
  workplaces: Array<Record<string, KpiValue | string>>;
  services: Array<Record<string, KpiValue | string>>;
}> = ({ history, workplaces, services }) => {
  const shortChartLabel = (value: unknown) => {
    const text = String(value || '').replace(/^Рога и копыта\s*[—-]\s*/i, '').trim();
    if (text.length <= 14) return text;
    const words = text.split(/\s+/).filter(Boolean);
    const short = words.slice(0, 2).join(' ');
    return short.length > 14 ? `${short.slice(0, 13)}…` : short;
  };

  const trendData = history
    .map((item) => ({
      label: item.label,
      revenue: toFiniteNumber(item.revenue),
      margin: toFiniteNumber(item.operating_margin),
      occupancy: toFiniteNumber(item.workplace_occupancy),
    }))
    .filter((item) => item.revenue != null || item.margin != null || item.occupancy != null)
    .slice(-6);

  const workplaceData = workplaces
    .map((item) => ({
      name: String(item.name || 'Рабочее место'),
      revenuePerHour: toFiniteNumber(item.revenue_per_hour),
      occupancy: toFiniteNumber(item.occupancy),
    }))
    .filter((item) => item.revenuePerHour != null || item.occupancy != null)
    .slice(0, 8);

  const serviceData = services
    .map((item) => ({
      name: String(item.service_name || item.name || 'Услуга'),
      margin: toFiniteNumber(item.gross_margin),
      revenuePerHour: toFiniteNumber(item.revenue_per_hour),
    }))
    .filter((item) => item.margin != null || item.revenuePerHour != null)
    .slice(0, 8);

  return (
    <div className="mt-6 grid gap-4 xl:grid-cols-3">
      <VisualCard
        title="Динамика денег"
        subtitle="Выручка и маржа по периодам"
        empty={trendData.length < 2 ? 'График появится после двух периодов с данными.' : null}
      >
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={trendData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="financeRevenueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0f172a" stopOpacity={0.22} />
                <stop offset="95%" stopColor="#0f172a" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
            <YAxis yAxisId="revenue" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} tickFormatter={(value) => `${Math.round(Number(value) / 1000)}к`} />
            <YAxis yAxisId="margin" orientation="right" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} tickFormatter={(value) => `${Math.round(Number(value))}%`} />
            <Tooltip formatter={(value, name) => [name === 'revenue' ? tooltipMoney(value) : tooltipPercent(value), name === 'revenue' ? 'Выручка' : 'Маржа']} />
            <Area yAxisId="revenue" type="monotone" dataKey="revenue" stroke="#0f172a" fill="url(#financeRevenueGradient)" strokeWidth={2} connectNulls />
            <Area yAxisId="margin" type="monotone" dataKey="margin" stroke="#059669" fill="transparent" strokeWidth={2} connectNulls />
          </AreaChart>
        </ResponsiveContainer>
      </VisualCard>

      <VisualCard
        title="Рабочие места"
        subtitle="Выручка за час и загрузка"
        empty={workplaceData.length === 0 ? 'Добавьте кресла, кабинеты и часы, чтобы увидеть сравнение.' : null}
      >
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={workplaceData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={shortChartLabel} interval={0} height={52} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} tickFormatter={(value) => `${Math.round(Number(value) / 1000)}к`} />
            <Tooltip formatter={(value, name) => [name === 'revenuePerHour' ? tooltipMoney(value) : tooltipPercent(value), name === 'revenuePerHour' ? 'Выручка/час' : 'Загрузка']} />
            <Bar dataKey="revenuePerHour" fill="#0f172a" radius={[8, 8, 0, 0]} />
            <Bar dataKey="occupancy" fill="#38bdf8" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </VisualCard>

      <VisualCard
        title="Услуги"
        subtitle="Маржа и выручка за час"
        empty={serviceData.length === 0 ? 'Заполните длительность, материалы и выплаты по услугам.' : null}
      >
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={serviceData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={shortChartLabel} interval={0} height={52} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
            <Tooltip formatter={(value, name) => [name === 'revenuePerHour' ? tooltipMoney(value) : tooltipPercent(value), name === 'revenuePerHour' ? 'Выручка/час' : 'Маржа']} />
            <Bar dataKey="margin" fill="#059669" radius={[8, 8, 0, 0]} />
            <Bar dataKey="revenuePerHour" fill="#0f172a" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </VisualCard>
    </div>
  );
};

const VisualCard: React.FC<{
  title: string;
  subtitle: string;
  empty: string | null;
  children: React.ReactNode;
}> = ({ title, subtitle, empty, children }) => (
  <Card className="border-slate-200/80 shadow-sm">
    <CardHeader>
      <CardTitle className="text-base">{title}</CardTitle>
      <div className="text-sm text-slate-500">{subtitle}</div>
    </CardHeader>
    <CardContent>
      {empty ? (
        <div className="flex h-60 items-center justify-center rounded-2xl bg-slate-50 px-5 text-center text-sm leading-6 text-slate-500">
          {empty}
        </div>
      ) : children}
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
  description?: string;
  limit?: number;
  formatter: (key: string, value: KpiValue | string) => string;
}> = ({ title, icon: Icon, rows, columns, description, limit = 12, formatter }) => (
  <Card className="border-slate-200/80 shadow-sm">
    <CardHeader>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-base">
            <Icon className="h-4 w-4 text-slate-500" />
            {title}
          </CardTitle>
          {description ? <div className="mt-1 text-sm text-slate-500">{description}</div> : null}
        </div>
        <span className="w-fit rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
          {rows.length} строк
        </span>
      </div>
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
              {rows.slice(0, limit).map((row, index) => (
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
          Данных пока нет. Добавьте строки во вкладке «Данные».
        </div>
      )}
    </CardContent>
  </Card>
);

export default FinanceFirstStep;
