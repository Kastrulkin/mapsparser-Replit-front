import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw, RotateCcw, Save, SlidersHorizontal } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { cn } from '@/lib/utils';

type ThresholdValue = number | string | null | undefined;

type FinanceThreshold = {
  metric_key?: string;
  label?: string;
  unit?: string;
  profile?: string;
  source?: string;
  green_min?: ThresholdValue;
  green_max?: ThresholdValue;
  yellow_min?: ThresholdValue;
  yellow_max?: ThresholdValue;
  red_rule?: string;
};

type FinanceThresholdsPanelProps = {
  currentBusinessId?: string | null;
  onChanged?: () => void;
};

const metricOrder = [
  'operating_margin',
  'gross_margin',
  'workplace_occupancy',
  'revenue_per_workplace_hour',
  'gross_profit_per_workplace_hour',
  'rebooking_rate',
  'no_show_rate',
  'low_margin_services_share',
  'payroll_share',
  'material_share',
];

const numOrNull = (value: string) => {
  if (value.trim() === '') return null;
  return Number(value);
};

const inputValue = (value: ThresholdValue) => {
  if (value === null || value === undefined) return '';
  return String(value);
};

const unitLabel = (unit?: string) => {
  if (unit === 'RUB') return '₽';
  return unit || '';
};

const sourceTone = (source?: string) => (
  source === 'custom'
    ? 'bg-sky-50 text-sky-700 ring-sky-200'
    : 'bg-slate-50 text-slate-600 ring-slate-200'
);

export const FinanceThresholdsPanel: React.FC<FinanceThresholdsPanelProps> = ({ currentBusinessId, onChanged }) => {
  const [thresholds, setThresholds] = useState<Record<string, FinanceThreshold>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const orderedKeys = useMemo(() => {
    const existing = Object.keys(thresholds);
    const known = metricOrder.filter((key) => existing.includes(key));
    const extra = existing.filter((key) => !metricOrder.includes(key)).sort();
    return [...known, ...extra];
  }, [thresholds]);

  const loadThresholds = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    setMessage(null);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/finance/thresholds?business_id=${currentBusinessId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось загрузить нормы KPI');
        return;
      }
      setThresholds(data.thresholds || {});
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  }, [currentBusinessId]);

  useEffect(() => {
    loadThresholds();
  }, [loadThresholds]);

  const updateThreshold = (metricKey: string, field: keyof FinanceThreshold, value: ThresholdValue) => {
    setThresholds((current) => ({
      ...current,
      [metricKey]: {
        ...(current[metricKey] || {}),
        metric_key: metricKey,
        [field]: value,
      },
    }));
  };

  const saveThresholds = async () => {
    if (!currentBusinessId) return;
    setSaving(true);
    setMessage(null);
    try {
      const token = localStorage.getItem('auth_token');
      const payload = {
        business_id: currentBusinessId,
        thresholds: orderedKeys.map((metricKey) => ({
          ...thresholds[metricKey],
          metric_key: metricKey,
        })),
      };
      const response = await fetch('/api/finance/thresholds', {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось сохранить нормы KPI');
        return;
      }
      setThresholds(data.thresholds || {});
      setMessage('Нормы KPI сохранены. Рекомендации пересчитаются по новым правилам.');
      onChanged?.();
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setSaving(false);
    }
  };

  const resetThresholds = async () => {
    if (!currentBusinessId) return;
    setSaving(true);
    setMessage(null);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/finance/thresholds/reset', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось сбросить нормы KPI');
        return;
      }
      setThresholds(data.thresholds || {});
      setMessage('Нормы сброшены к базовому профилю.');
      onChanged?.();
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setSaving(false);
    }
  };

  const customCount = orderedKeys.filter((metricKey) => thresholds[metricKey]?.source === 'custom').length;

  return (
    <>
      <DashboardSection
        title="Нормы KPI"
        description="Красные, жёлтые и зелёные зоны влияют на статусы и рекомендации. Настройки открываются отдельно, чтобы не перегружать экран."
        actions={
          <Button onClick={() => setOpen(true)} disabled={!currentBusinessId} className="gap-2">
            <SlidersHorizontal className="h-4 w-4" />
            Настроить нормы
          </Button>
        }
      >
        {!currentBusinessId ? (
          <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Сначала выберите бизнес, чтобы настроить нормы KPI.
          </div>
        ) : (
          <div className="grid gap-3 text-sm text-slate-700 md:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Показателей</div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{orderedKeys.length || 'н/д'}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Свои нормы</div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{customCount}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Статус</div>
              <div className="mt-2 text-sm font-medium text-slate-950">
                {loading ? 'Загружаем нормы' : 'Готово к настройке'}
              </div>
            </div>
          </div>
        )}
      </DashboardSection>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] max-w-5xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Нормы KPI</DialogTitle>
            <DialogDescription>
              Настройте пороги под конкретный бизнес. После сохранения статусы и управленческие рекомендации пересчитаются.
            </DialogDescription>
          </DialogHeader>

          {message ? (
            <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700 ring-1 ring-slate-200">
              {message}
            </div>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            {orderedKeys.map((metricKey) => {
              const threshold = thresholds[metricKey] || {};
              return (
                <Card key={metricKey} className="border-slate-200/80 shadow-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-start justify-between gap-3 text-base">
                      <span className="flex items-center gap-2">
                        <SlidersHorizontal className="h-4 w-4 text-slate-500" />
                        {threshold.label || metricKey}
                      </span>
                      <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium ring-1', sourceTone(threshold.source))}>
                        {threshold.source === 'custom' ? 'своя норма' : 'базовая'}
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-3 md:grid-cols-2">
                      <ThresholdField
                        label={`Зелёная зона от ${unitLabel(threshold.unit)}`}
                        value={threshold.green_min}
                        onChange={(value) => updateThreshold(metricKey, 'green_min', numOrNull(value))}
                      />
                      <ThresholdField
                        label={`Зелёная зона до ${unitLabel(threshold.unit)}`}
                        value={threshold.green_max}
                        onChange={(value) => updateThreshold(metricKey, 'green_max', numOrNull(value))}
                      />
                      <ThresholdField
                        label={`Жёлтая зона от ${unitLabel(threshold.unit)}`}
                        value={threshold.yellow_min}
                        onChange={(value) => updateThreshold(metricKey, 'yellow_min', numOrNull(value))}
                      />
                      <ThresholdField
                        label={`Жёлтая зона до ${unitLabel(threshold.unit)}`}
                        value={threshold.yellow_max}
                        onChange={(value) => updateThreshold(metricKey, 'yellow_max', numOrNull(value))}
                      />
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <DialogFooter className="gap-2 sm:space-x-0">
            <Button variant="outline" onClick={loadThresholds} disabled={loading || !currentBusinessId} className="gap-2">
              <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
              Обновить
            </Button>
            <Button variant="outline" onClick={resetThresholds} disabled={saving || !currentBusinessId} className="gap-2">
              <RotateCcw className="h-4 w-4" />
              Сбросить
            </Button>
            <Button onClick={saveThresholds} disabled={saving || !currentBusinessId} className="gap-2">
              <Save className="h-4 w-4" />
              Сохранить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

const ThresholdField: React.FC<{
  label: string;
  value: ThresholdValue;
  onChange: (value: string) => void;
}> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input
      type="number"
      value={inputValue(value)}
      onChange={(event) => onChange(event.target.value)}
    />
  </div>
);

export default FinanceThresholdsPanel;
