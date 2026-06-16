import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import {
  BadgeCheck,
  CalendarDays,
  CircleDollarSign,
  Edit3,
  Loader2,
  MessageSquareText,
  PackageCheck,
  Plus,
  RefreshCcw,
  Save,
  Sparkles,
  TrendingUp,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import {
  DashboardCompactMetricsRow,
  DashboardEmptyState,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { useToast } from '@/hooks/use-toast';
import { newAuth } from '@/lib/auth_new';

type OutletContext = {
  currentBusinessId?: string | null;
};

type ServiceItem = {
  id: string;
  category: string;
  name: string;
  optimized_name?: string;
  price?: string;
};

type AverageTicketAddon = {
  id: string;
  service_id: string;
  service: string;
  category: string;
  price: string;
  offer_timing: string;
  priority: string;
  compatibility: string;
  reason: string;
  admin_script: string;
  master_script: string;
  expected_effect: string;
  status: string;
  main_service_id?: string;
  main_service?: string;
  main_category?: string;
};

type AverageTicketRow = {
  main_service_id: string;
  main_service: string;
  main_category: string;
  recommended_addons: AverageTicketAddon[];
};

type AverageTicketPackage = {
  id?: string;
  name?: string;
  services?: string[];
  service_ids?: string[];
  service_names?: string[];
  base_total?: number;
  package_price?: number | null;
  bonus_text?: string;
  positioning?: string;
  offer_timing?: string;
  script?: string;
  status?: string;
};

type AverageTicketMatrix = {
  upsell_matrix?: AverageTicketRow[];
  cross_sell_pairs?: Array<{
    from_category?: string;
    to_category?: string;
    reason?: string;
    status?: string;
  }>;
  packages?: AverageTicketPackage[];
  risks?: string[];
  implementation_priorities?: string[];
  generation_mode?: string;
  generation_note?: string;
};

type LatestMatrix = {
  id: string;
  status: string;
  matrix: AverageTicketMatrix;
  generated_at?: string;
  updated_at?: string;
};

type AverageTicketStats = {
  main_services?: number;
  links?: number;
  active_links?: number;
  accepted_links?: number;
  packages?: number;
  cross_sell_pairs?: number;
};

type AverageTicketEvent = {
  id?: string;
  event_type: string;
  link_id?: string;
  package_id?: string;
  booking_id?: string;
  amount?: number | null;
};

type DailyPlanItem = {
  booking_id: string;
  time?: string | null;
  client?: string;
  service_id?: string;
  service_name?: string;
  master_id?: string;
  status?: string;
  recommendations: AverageTicketAddon[];
  events: AverageTicketEvent[];
};

type AverageTicketKpis = {
  average_ticket?: number | null;
  average_ticket_delta_30d?: number | null;
  add_on_rate?: number | null;
  upsell_conversion?: number | null;
  cross_sell_rate?: number | null;
  package_sales?: number | null;
  package_conversion?: number | null;
  upsell_revenue?: number | null;
  potential_growth?: number | null;
  average_ticket_with_upsell?: number | null;
  average_ticket_without_upsell?: number | null;
  events?: Record<string, number>;
  by_master?: Array<{ master_id: string; offered: number; bought: number; conversion?: number | null }>;
  by_category?: Array<{ category: string; offered: number; bought: number; conversion?: number | null }>;
};

type AverageTicketOverview = {
  services_count?: number;
  services?: ServiceItem[];
  latest_matrix?: LatestMatrix | null;
  stats?: AverageTicketStats;
  kpis?: AverageTicketKpis;
  daily_plan?: DailyPlanItem[];
  packages?: AverageTicketPackage[];
};

type LinkWithRow = {
  row: AverageTicketRow;
  addon: AverageTicketAddon;
};

const rub = (value?: number | null) => {
  if (value == null) return 'н/д';
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(value);
};

const pct = (value?: number | null) => {
  if (value == null) return 'н/д';
  return `${value}%`;
};

const serviceName = (item?: ServiceItem) => item?.optimized_name || item?.name || '';

const timingLabel: Record<string, string> = {
  before_visit: 'До визита',
  during_visit: 'Во время',
  checkout: 'На выходе',
  next_visit: 'Следующий визит',
};

const compatibilityLabel: Record<string, string> = {
  same_visit: 'Можно сейчас',
  next_visit: 'Следующий визит',
  consultation_required: 'Через консультацию',
  avoid: 'Не совмещать',
};

const statusLabel: Record<string, string> = {
  draft: 'Черновик',
  active: 'Активно',
  disabled: 'Отключено',
};

const eventLabel: Record<string, string> = {
  offered: 'Предложили',
  bought: 'Купил',
  declined: 'Отказ',
  next_visit_booked: 'Следующий визит',
  package_offered: 'Пакет предложен',
  package_bought: 'Пакет куплен',
};

const flattenLinks = (matrix?: AverageTicketMatrix | null): LinkWithRow[] => {
  const rows = matrix?.upsell_matrix || [];
  return rows.flatMap((row) =>
    (row.recommended_addons || []).map((addon) => ({
      row,
      addon,
    })),
  );
};

const emptyLinkDraft: AverageTicketAddon = {
  id: '',
  service_id: '',
  service: '',
  category: '',
  price: '',
  offer_timing: 'during_visit',
  priority: 'medium',
  compatibility: 'same_visit',
  reason: '',
  admin_script: '',
  master_script: '',
  expected_effect: 'add_on',
  status: 'draft',
};

export const AverageTicketPage = () => {
  const { currentBusinessId } = useOutletContext<OutletContext>();
  const { toast } = useToast();
  const [overview, setOverview] = useState<AverageTicketOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editLink, setEditLink] = useState<LinkWithRow | null>(null);
  const [editDraft, setEditDraft] = useState<AverageTicketAddon>(emptyLinkDraft);
  const [manualLinkOpen, setManualLinkOpen] = useState(false);
  const [manualLink, setManualLink] = useState({
    main_service_id: '',
    addon_service_id: '',
    reason: '',
    admin_script: '',
    master_script: '',
    offer_timing: 'during_visit',
    compatibility: 'same_visit',
    status: 'draft',
  });
  const [packageOpen, setPackageOpen] = useState(false);
  const [packageDraft, setPackageDraft] = useState({
    name: '',
    service_ids: '',
    package_price: '',
    bonus_text: '',
    positioning: '',
    script: '',
    status: 'draft',
  });
  const [editingPackageId, setEditingPackageId] = useState<string | null>(null);

  const matrix = overview?.latest_matrix?.matrix || null;
  const links = useMemo(() => flattenLinks(matrix), [matrix]);
  const services = overview?.services || [];
  const activeLinks = overview?.stats?.active_links || 0;
  const totalLinks = overview?.stats?.links || 0;
  const packages = overview?.packages || matrix?.packages || [];

  const loadOverview = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    try {
      const data = await newAuth.makeRequest(`/average-ticket/overview?business_id=${encodeURIComponent(currentBusinessId)}`);
      setOverview(data);
    } catch (error) {
      toast({
        title: 'Не удалось загрузить Допродажи',
        description: error instanceof Error ? error.message : 'Проверьте соединение и попробуйте снова.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [currentBusinessId, toast]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const refreshFromResponse = (data: AverageTicketOverview) => {
    setOverview((previous) => ({
      ...(previous || {}),
      latest_matrix: data.latest_matrix ?? previous?.latest_matrix,
      stats: data.stats ?? previous?.stats,
      kpis: data.kpis ?? previous?.kpis,
      packages: data.packages ?? previous?.packages,
    }));
  };

  const generateMatrix = async () => {
    if (!currentBusinessId) return;
    setGenerating(true);
    try {
      const data = await newAuth.makeRequest('/average-ticket/generate', {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      refreshFromResponse(data);
      toast({
        title: data.generation_mode === 'fallback' ? 'Матрица собрана локально' : 'Матрица сгенерирована',
        description: data.generation_mode === 'fallback'
          ? 'GigaChat не дал валидный результат, поэтому LocalOS собрал безопасный черновик по правилам.'
          : 'Черновик связок готов к проверке.',
      });
      void loadOverview();
    } catch (error) {
      toast({
        title: 'Генерация не удалась',
        description: error instanceof Error ? error.message : 'Попробуйте позже.',
        variant: 'destructive',
      });
    } finally {
      setGenerating(false);
    }
  };

  const patchLink = async (payload: Record<string, string>) => {
    if (!currentBusinessId || !overview?.latest_matrix?.id) return;
    setSaving(true);
    try {
      const data = await newAuth.makeRequest(`/average-ticket/matrix/${overview.latest_matrix.id}/link?business_id=${encodeURIComponent(currentBusinessId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      refreshFromResponse(data);
      setEditLink(null);
    } catch (error) {
      toast({
        title: 'Связка не сохранилась',
        description: error instanceof Error ? error.message : 'Попробуйте ещё раз.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const createManualLink = async () => {
    if (!currentBusinessId || !overview?.latest_matrix?.id) return;
    setSaving(true);
    try {
      const data = await newAuth.makeRequest(`/average-ticket/matrix/${overview.latest_matrix.id}/link?business_id=${encodeURIComponent(currentBusinessId)}`, {
        method: 'POST',
        body: JSON.stringify(manualLink),
      });
      refreshFromResponse(data);
      setManualLinkOpen(false);
    } catch (error) {
      toast({
        title: 'Связка не добавилась',
        description: error instanceof Error ? error.message : 'Проверьте услуги и попробуйте ещё раз.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const savePackage = async () => {
    if (!currentBusinessId) return;
    setSaving(true);
    try {
      const endpoint = editingPackageId
        ? `/average-ticket/packages/${editingPackageId}?business_id=${encodeURIComponent(currentBusinessId)}`
        : `/average-ticket/packages?business_id=${encodeURIComponent(currentBusinessId)}`;
      const data = await newAuth.makeRequest(endpoint, {
        method: editingPackageId ? 'PATCH' : 'POST',
        body: JSON.stringify({
          ...packageDraft,
          service_ids: packageDraft.service_ids.split(',').map((item) => item.trim()).filter(Boolean),
        }),
      });
      refreshFromResponse(data);
      setPackageOpen(false);
      setEditingPackageId(null);
      setPackageDraft({ name: '', service_ids: '', package_price: '', bonus_text: '', positioning: '', script: '', status: 'draft' });
    } catch (error) {
      toast({
        title: 'Пакет не сохранился',
        description: error instanceof Error ? error.message : 'Проверьте состав пакета.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const openPackageEditor = (item?: AverageTicketPackage) => {
    setEditingPackageId(item?.id || null);
    setPackageDraft({
      name: item?.name || '',
      service_ids: (item?.service_ids || []).join(', '),
      package_price: item?.package_price == null ? '' : String(item.package_price),
      bonus_text: item?.bonus_text || '',
      positioning: item?.positioning || '',
      script: item?.script || '',
      status: item?.status || 'draft',
    });
    setPackageOpen(true);
  };

  const recordEvent = async (eventType: string, item: DailyPlanItem, addon: AverageTicketAddon) => {
    if (!currentBusinessId) return;
    setSaving(true);
    try {
      await newAuth.makeRequest(`/average-ticket/events?business_id=${encodeURIComponent(currentBusinessId)}`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: eventType,
          matrix_id: overview?.latest_matrix?.id,
          link_id: addon.id,
          booking_id: item.booking_id,
          main_service_id: item.service_id || addon.main_service_id,
          addon_service_id: addon.service_id,
          master_id: item.master_id,
          client_name: item.client,
          amount: eventType === 'bought' ? addon.price : undefined,
        }),
      });
      await loadOverview();
    } catch (error) {
      toast({
        title: 'Результат не сохранился',
        description: error instanceof Error ? error.message : 'Попробуйте ещё раз.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (link: LinkWithRow) => {
    setEditLink(link);
    setEditDraft({
      ...emptyLinkDraft,
      ...link.addon,
    });
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-10">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Допродажи"
        description="Допродажи, кросс-продажи скрипты, пакеты и план предложений по реальным записям. Финансы остаются источником диагноза, здесь работает операционная команда."
        icon={CircleDollarSign}
        actions={
          <>
            <Button variant="outline" className="gap-2" onClick={() => setManualLinkOpen(true)} disabled={!matrix}>
              <Plus className="h-4 w-4" />
              Связка
            </Button>
            <Button asChild variant="outline" className="gap-2">
              <Link to="/dashboard/finance">
                <TrendingUp className="h-4 w-4" />
                Финансы
              </Link>
            </Button>
            <Button variant="outline" className="gap-2" onClick={loadOverview} disabled={loading || !currentBusinessId}>
              <RefreshCcw className="h-4 w-4" />
              Обновить
            </Button>
            <Button className="gap-2" onClick={generateMatrix} disabled={generating || !currentBusinessId}>
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Сгенерировать
            </Button>
          </>
        }
      />

      {!currentBusinessId ? (
        <DashboardEmptyState title="Выберите бизнес" description="Матрица среднего чека строится по услугам конкретного бизнеса." />
      ) : (
        <>
          <DashboardCompactMetricsRow
            items={[
              { label: 'Средний чек', value: rub(overview?.kpis?.average_ticket), hint: `30 дней: ${pct(overview?.kpis?.average_ticket_delta_30d)}` },
              { label: 'Add-on rate', value: pct(overview?.kpis?.add_on_rate), hint: 'Доля визитов с допродажей' },
              { label: 'Выручка допродаж', value: rub(overview?.kpis?.upsell_revenue), hint: 'По событиям купил/пакет куплен', tone: overview?.kpis?.upsell_revenue ? 'positive' : 'default' },
              { label: 'Пакеты', value: overview?.kpis?.package_sales ?? 0, hint: `Конверсия: ${pct(overview?.kpis?.package_conversion)}` },
              { label: 'Потенциал', value: rub(overview?.kpis?.potential_growth), hint: 'Оценка по активным связкам' },
            ]}
          />

          {loading ? (
            <DashboardSection>
              <div className="flex items-center justify-center py-12 text-sm text-slate-500">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Загружаем раздел...
              </div>
            </DashboardSection>
          ) : !matrix ? (
            <DashboardEmptyState
              title="Матрица ещё не создана"
              description="LocalOS возьмёт услуги из “Работы с картами” и подготовит черновик допродаж, скриптов и пакетов."
              action={<Button className="gap-2" onClick={generateMatrix} disabled={generating}><Sparkles className="h-4 w-4" />Сгенерировать черновик</Button>}
            />
          ) : (
            <Tabs defaultValue="daily" className="space-y-6">
              <TabsList className="grid w-full grid-cols-2 lg:w-auto lg:grid-cols-4">
                <TabsTrigger value="daily">План на день</TabsTrigger>
                <TabsTrigger value="matrix">Матрица</TabsTrigger>
                <TabsTrigger value="scripts">Скрипты</TabsTrigger>
                <TabsTrigger value="packages">Пакеты</TabsTrigger>
              </TabsList>

              <TabsContent value="daily" className="space-y-6">
                <DashboardSection
                  title="План на день"
                  description="Реальные записи на сегодня: время, клиент, основная услуга, предложение, скрипт и фиксация результата."
                >
                  {(overview?.daily_plan || []).length > 0 ? (
                    <div className="grid gap-3">
                      {(overview?.daily_plan || []).map((item) => (
                        <div key={item.booking_id} className="rounded-lg border border-slate-200 p-4">
                          <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                            <div>
                              <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                                <CalendarDays className="h-4 w-4 text-slate-400" />
                                {item.time || 'Время не указано'} · {item.client || 'Клиент'}
                              </div>
                              <div className="mt-1 text-sm text-slate-600">{item.service_name || 'Услуга не указана'}</div>
                            </div>
                            <Badge variant="outline">{item.status || 'запись'}</Badge>
                          </div>
                          <div className="mt-4 grid gap-3">
                            {item.recommendations.map((addon) => (
                              <div key={`${item.booking_id}-${addon.id}`} className="rounded-lg bg-slate-50 p-3">
                                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                  <div className="max-w-3xl">
                                    <div className="font-medium text-slate-950">Предложить: {addon.service}</div>
                                    <div className="mt-1 text-xs text-slate-500">{timingLabel[addon.offer_timing] || addon.offer_timing} · {addon.price || 'цена не указана'}</div>
                                    <p className="mt-2 text-sm leading-6 text-slate-700">{addon.admin_script || addon.master_script || addon.reason}</p>
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    <Button size="sm" variant="outline" disabled={saving} onClick={() => recordEvent('offered', item, addon)}>Предложили</Button>
                                    <Button size="sm" disabled={saving} onClick={() => recordEvent('bought', item, addon)}>Купил</Button>
                                    <Button size="sm" variant="ghost" disabled={saving} onClick={() => recordEvent('declined', item, addon)}>Отказ</Button>
                                    <Button size="sm" variant="outline" disabled={saving} onClick={() => recordEvent('next_visit_booked', item, addon)}>Следующий визит</Button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <DashboardEmptyState
                      title="На сегодня нет подходящих записей"
                      description="Нужны реальные записи и активные связки матрицы. Включите связки или проверьте расписание."
                    />
                  )}
                </DashboardSection>
              </TabsContent>

              <TabsContent value="matrix" className="space-y-6">
                <DashboardSection
                  title="Матрица допродаж"
                  description={`Активные связки: ${activeLinks}/${totalLinks}. Можно редактировать причину, скрипты, момент предложения и совместимость.`}
                >
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Основная услуга</TableHead>
                          <TableHead>Что предложить</TableHead>
                          <TableHead>Когда</TableHead>
                          <TableHead>Совместимость</TableHead>
                          <TableHead>Статус</TableHead>
                          <TableHead className="text-right">Действия</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {links.map((link) => (
                          <TableRow key={link.addon.id}>
                            <TableCell className="min-w-64 align-top">
                              <div className="font-medium text-slate-950">{link.row.main_service}</div>
                              <div className="text-xs text-slate-500">{link.row.main_category}</div>
                            </TableCell>
                            <TableCell className="min-w-72 align-top">
                              <div className="font-medium text-slate-950">{link.addon.service}</div>
                              <div className="text-xs text-slate-500">{link.addon.category} · {link.addon.price || 'цена не указана'}</div>
                              <p className="mt-2 text-sm leading-6 text-slate-600">{link.addon.reason}</p>
                            </TableCell>
                            <TableCell className="align-top">{timingLabel[link.addon.offer_timing] || link.addon.offer_timing}</TableCell>
                            <TableCell className="align-top">{compatibilityLabel[link.addon.compatibility] || link.addon.compatibility}</TableCell>
                            <TableCell className="align-top">
                              <Badge variant={link.addon.status === 'active' ? 'default' : link.addon.status === 'disabled' ? 'secondary' : 'outline'}>
                                {statusLabel[link.addon.status] || link.addon.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="align-top">
                              <div className="flex justify-end gap-2">
                                <Button size="sm" variant="outline" onClick={() => openEdit(link)}>
                                  <Edit3 className="mr-2 h-4 w-4" />
                                  Править
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => patchLink({ link_id: link.addon.id, status: link.addon.status === 'active' ? 'disabled' : 'active' })}>
                                  {link.addon.status === 'active' ? 'Отключить' : 'Включить'}
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </DashboardSection>
              </TabsContent>

              <TabsContent value="scripts" className="space-y-6">
                <DashboardSection title="Скрипты" description="Скрипты привязаны к связке, чтобы администратор и мастер говорили об одной ценности.">
                  <div className="grid gap-4 lg:grid-cols-2">
                    {links.slice(0, 24).map(({ row, addon }) => (
                      <div key={`script-${addon.id}`} className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-slate-950">{row.main_service}</div>
                            <div className="text-sm text-slate-600">→ {addon.service}</div>
                          </div>
                          <MessageSquareText className="h-5 w-5 shrink-0 text-slate-400" />
                        </div>
                        <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
                          <p><span className="font-medium text-slate-950">Администратор:</span> {addon.admin_script || 'Скрипт не заполнен.'}</p>
                          <p><span className="font-medium text-slate-950">Мастер:</span> {addon.master_script || 'Скрипт не заполнен.'}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </DashboardSection>
              </TabsContent>

              <TabsContent value="packages" className="space-y-6">
                <DashboardSection
                  title="Пакетные предложения"
                  description="Пакеты собираются вручную из услуг “Работы с картами”, с расчётом суммы по прайсу и отдельной пакетной ценой или бонусом."
                  actions={<Button className="gap-2" onClick={() => openPackageEditor()}><Plus className="h-4 w-4" />Пакет</Button>}
                >
                  {packages.length > 0 ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      {packages.map((item, index) => (
                        <div key={item.id || `${item.name || 'package'}-${index}`} className="rounded-lg border border-slate-200 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <h3 className="font-semibold text-slate-950">{item.name || 'Пакет без названия'}</h3>
                            <div className="flex items-center gap-2">
                              <Button size="sm" variant="outline" onClick={() => openPackageEditor(item)}>
                                <Edit3 className="mr-2 h-4 w-4" />
                                Править
                              </Button>
                              <PackageCheck className="h-5 w-5 shrink-0 text-slate-400" />
                            </div>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-600">{item.positioning || 'Позиционирование не заполнено.'}</p>
                          <div className="mt-3 text-sm text-slate-700">
                            {(item.service_names || item.services || []).join(' + ') || 'Состав не заполнен'}
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2 text-sm">
                            <Badge variant="outline">Сумма: {rub(item.base_total)}</Badge>
                            <Badge variant="outline">Пакет: {rub(item.package_price)}</Badge>
                            <Badge variant={item.status === 'active' ? 'default' : 'secondary'}>{statusLabel[item.status || 'draft'] || item.status}</Badge>
                          </div>
                          <p className="mt-3 text-sm leading-6 text-slate-700">{item.script || item.bonus_text || 'Скрипт не заполнен.'}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <DashboardEmptyState title="Пакеты пока не собраны" description="Создайте первый пакет из существующих услуг: система посчитает сумму и сохранит пакетную цену." />
                  )}
                </DashboardSection>
              </TabsContent>
            </Tabs>
          )}

          {overview?.kpis?.by_category?.length ? (
            <DashboardSection title="Конверсии" description="Первые агрегаты по событиям: предложили, купили и конверсия по категориям.">
              <div className="grid gap-3 md:grid-cols-3">
                {overview.kpis.by_category.slice(0, 6).map((item) => (
                  <div key={item.category} className="rounded-lg bg-slate-50 p-4 text-sm ring-1 ring-slate-200">
                    <div className="font-semibold text-slate-950">{item.category}</div>
                    <div className="mt-2 text-slate-600">Предложили: {item.offered} · Купили: {item.bought}</div>
                    <div className="mt-1 text-slate-600">Конверсия: {pct(item.conversion)}</div>
                  </div>
                ))}
              </div>
            </DashboardSection>
          ) : null}

          {matrix?.implementation_priorities?.length ? (
            <DashboardSection title="Что улучшить в первую очередь">
              <div className="grid gap-3 md:grid-cols-3">
                {matrix.implementation_priorities.map((item) => (
                  <div key={item} className="flex gap-3 rounded-lg bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">
                    <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </DashboardSection>
          ) : null}
        </>
      )}

      <Dialog open={Boolean(editLink)} onOpenChange={(open) => !open && setEditLink(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Редактировать связку</DialogTitle>
            <DialogDescription>{editLink?.row.main_service} → {editLink?.addon.service}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label>Причина</Label>
              <Textarea value={editDraft.reason} onChange={(event) => setEditDraft({ ...editDraft, reason: event.target.value })} />
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>Скрипт администратора</Label>
                <Textarea value={editDraft.admin_script} onChange={(event) => setEditDraft({ ...editDraft, admin_script: event.target.value })} />
              </div>
              <div className="grid gap-2">
                <Label>Скрипт мастера</Label>
                <Textarea value={editDraft.master_script} onChange={(event) => setEditDraft({ ...editDraft, master_script: event.target.value })} />
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="grid gap-2">
                <Label>Когда</Label>
                <Select value={editDraft.offer_timing} onValueChange={(value) => setEditDraft({ ...editDraft, offer_timing: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(timingLabel).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Совместимость</Label>
                <Select value={editDraft.compatibility} onValueChange={(value) => setEditDraft({ ...editDraft, compatibility: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(compatibilityLabel).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Статус</Label>
                <Select value={editDraft.status} onValueChange={(value) => setEditDraft({ ...editDraft, status: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(statusLabel).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditLink(null)}>Отмена</Button>
            <Button disabled={saving} onClick={() => patchLink({ link_id: editDraft.id, reason: editDraft.reason, admin_script: editDraft.admin_script, master_script: editDraft.master_script, offer_timing: editDraft.offer_timing, compatibility: editDraft.compatibility, status: editDraft.status })}>
              <Save className="mr-2 h-4 w-4" />
              Сохранить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={manualLinkOpen} onOpenChange={setManualLinkOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Добавить связку вручную</DialogTitle>
            <DialogDescription>Выберите две услуги из “Работы с картами” и задайте правила предложения.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>Основная услуга</Label>
                <Select value={manualLink.main_service_id} onValueChange={(value) => setManualLink({ ...manualLink, main_service_id: value })}>
                  <SelectTrigger><SelectValue placeholder="Выберите услугу" /></SelectTrigger>
                  <SelectContent>{services.map((item) => <SelectItem key={item.id} value={item.id}>{serviceName(item)}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Допуслуга</Label>
                <Select value={manualLink.addon_service_id} onValueChange={(value) => setManualLink({ ...manualLink, addon_service_id: value })}>
                  <SelectTrigger><SelectValue placeholder="Выберите допуслугу" /></SelectTrigger>
                  <SelectContent>{services.map((item) => <SelectItem key={item.id} value={item.id}>{serviceName(item)}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <Textarea placeholder="Причина" value={manualLink.reason} onChange={(event) => setManualLink({ ...manualLink, reason: event.target.value })} />
            <Textarea placeholder="Скрипт администратора" value={manualLink.admin_script} onChange={(event) => setManualLink({ ...manualLink, admin_script: event.target.value })} />
            <Textarea placeholder="Скрипт мастера" value={manualLink.master_script} onChange={(event) => setManualLink({ ...manualLink, master_script: event.target.value })} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setManualLinkOpen(false)}>Отмена</Button>
            <Button disabled={saving || !manualLink.main_service_id || !manualLink.addon_service_id} onClick={createManualLink}>Добавить</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={packageOpen} onOpenChange={(open) => {
        setPackageOpen(open);
        if (!open) setEditingPackageId(null);
      }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingPackageId ? 'Редактировать пакет' : 'Новый пакет'}</DialogTitle>
            <DialogDescription>Состав укажите ID услуг через запятую. ID видны в списке ниже, источник тот же: “Работа с картами”.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <Input placeholder="Название пакета" value={packageDraft.name} onChange={(event) => setPackageDraft({ ...packageDraft, name: event.target.value })} />
            <Textarea placeholder="ID услуг через запятую" value={packageDraft.service_ids} onChange={(event) => setPackageDraft({ ...packageDraft, service_ids: event.target.value })} />
            <Input placeholder="Пакетная цена" value={packageDraft.package_price} onChange={(event) => setPackageDraft({ ...packageDraft, package_price: event.target.value })} />
            <Input placeholder="Бонус" value={packageDraft.bonus_text} onChange={(event) => setPackageDraft({ ...packageDraft, bonus_text: event.target.value })} />
            <Select value={packageDraft.status} onValueChange={(value) => setPackageDraft({ ...packageDraft, status: value })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="draft">Черновик</SelectItem>
                <SelectItem value="active">Активен</SelectItem>
                <SelectItem value="disabled">Отключен</SelectItem>
              </SelectContent>
            </Select>
            <Textarea placeholder="Позиционирование" value={packageDraft.positioning} onChange={(event) => setPackageDraft({ ...packageDraft, positioning: event.target.value })} />
            <Textarea placeholder="Скрипт продажи" value={packageDraft.script} onChange={(event) => setPackageDraft({ ...packageDraft, script: event.target.value })} />
            <div className="max-h-40 overflow-auto rounded-lg border border-slate-200 p-3 text-xs text-slate-600">
              {services.slice(0, 120).map((item) => <div key={item.id}>{item.id} · {serviceName(item)} · {item.price || 'цена не указана'}</div>)}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPackageOpen(false)}>Отмена</Button>
            <Button disabled={saving || !packageDraft.name || !packageDraft.service_ids} onClick={savePackage}>
              {editingPackageId ? 'Сохранить пакет' : 'Создать пакет'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AverageTicketPage;
