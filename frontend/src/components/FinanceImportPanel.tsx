import React, { useCallback, useEffect, useState } from 'react';
import { Download, FileSpreadsheet, History, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { cn } from '@/lib/utils';

type FinanceImportPanelProps = {
  currentBusinessId?: string | null;
  onImported?: () => void;
};

type ImportPreview = {
  rows_total: number;
  valid_rows: number;
  failed_rows: number;
  mapping: Record<string, string>;
  preview: Array<Record<string, unknown>>;
  errors: Array<{ row: number; errors: string[] }>;
};

type ImportTemplateInfo = {
  label: string;
  description: string;
};

type ImportBatch = {
  id: string;
  status: string;
  file_name: string;
  rows_total: number;
  rows_imported: number;
  rows_skipped: number;
  rows_failed: number;
  created_at: string;
};

export const FinanceImportPanel: React.FC<FinanceImportPanelProps> = ({ currentBusinessId, onImported }) => {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [templates, setTemplates] = useState<Record<string, ImportTemplateInfo>>({});
  const [templateProfile, setTemplateProfile] = useState('manual');
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [imports, setImports] = useState<ImportBatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const token = localStorage.getItem('auth_token');

  const loadImports = useCallback(async () => {
    if (!currentBusinessId) return;
    try {
      const response = await fetch(`/api/finance/imports?business_id=${currentBusinessId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (data.success) setImports(data.imports || []);
    } catch (error) {
      setMessage('Не удалось загрузить историю импорта');
    }
  }, [currentBusinessId, token]);

  const loadTemplates = useCallback(async () => {
    try {
      const response = await fetch('/api/finance/import-templates');
      const data = await response.json();
      if (data.success) setTemplates(data.templates || {});
    } catch (error) {
      setMessage('Не удалось загрузить шаблоны импорта');
    }
  }, []);

  useEffect(() => {
    loadImports();
    loadTemplates();
  }, [loadImports, loadTemplates]);

  const buildFormData = () => {
    const formData = new FormData();
    if (file) formData.append('file', file);
    if (currentBusinessId) formData.append('business_id', currentBusinessId);
    formData.append('mapping', JSON.stringify(mapping));
    return formData;
  };

  const runPreview = async () => {
    if (!file || !currentBusinessId) return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`/api/finance/import-preview?business_id=${currentBusinessId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: buildFormData(),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось прочитать файл');
        return;
      }
      setPreview(data);
      setMapping(data.mapping || {});
      setMessage(`Найдено строк: ${data.rows_total}. Готово к импорту: ${data.valid_rows}. Ошибок: ${data.failed_rows}.`);
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  const runImport = async () => {
    if (!file || !currentBusinessId) return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`/api/finance/import-file?business_id=${currentBusinessId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: buildFormData(),
      });
      const data = await response.json();
      if (!data.success) {
        setMessage(data.error || 'Не удалось импортировать файл');
        return;
      }
      setMessage(`Импортировано: ${data.rows_imported}. Пропущено дублей: ${data.rows_skipped}. Ошибок: ${data.rows_failed}.`);
      setPreview(null);
      setFile(null);
      await loadImports();
      if (onImported) onImported();
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardSection
      title="Импорт финансовых данных"
      description="Загрузите CSV/XLSX по шаблону: LocalOS покажет preview, ошибки и пропустит дубли при повторной загрузке."
      actions={
        <Button variant="outline" className="gap-2" onClick={() => window.open(`/api/finance/import-template?profile=${templateProfile}`, '_blank')}>
          <Download className="h-4 w-4" />
          Скачать шаблон
        </Button>
      }
    >
      <div className="grid gap-5 xl:grid-cols-[1fr_0.9fr]">
        <Card className="border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileSpreadsheet className="h-4 w-4 text-slate-500" />
              Файл
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Тип шаблона</Label>
              <Select value={templateProfile} onValueChange={setTemplateProfile}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(templates).map(([key, value]) => (
                    <SelectItem key={key} value={key}>{value.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {templates[templateProfile]?.description ? (
                <div className="text-sm text-slate-500">{templates[templateProfile].description}</div>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label>CSV или XLSX</Label>
              <Input
                type="file"
                accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={(event) => {
                  const selected = event.target.files && event.target.files.length > 0 ? event.target.files[0] : null;
                  setFile(selected);
                  setPreview(null);
                  setMessage(null);
                }}
              />
            </div>

            {message ? (
              <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700 ring-1 ring-slate-200">
                {message}
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={runPreview} disabled={!file || loading || !currentBusinessId} className="gap-2">
                <FileSpreadsheet className="h-4 w-4" />
                Проверить файл
              </Button>
              <Button onClick={runImport} disabled={!file || loading || !currentBusinessId} className="gap-2">
                <Upload className="h-4 w-4" />
                Импортировать
              </Button>
            </div>

            {preview ? (
              <div className="space-y-4">
                <div className="grid gap-2 sm:grid-cols-3">
                  <MiniStat label="Строк" value={preview.rows_total} />
                  <MiniStat label="Готово" value={preview.valid_rows} tone="green" />
                  <MiniStat label="Ошибки" value={preview.failed_rows} tone={preview.failed_rows > 0 ? 'red' : 'default'} />
                </div>
                <MappingEditor mapping={mapping} onChange={setMapping} />
                <PreviewTable rows={preview.preview} />
                {preview.errors.length > 0 ? (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                    <div className="font-semibold">Первые ошибки</div>
                    <div className="mt-2 space-y-1">
                      {preview.errors.slice(0, 5).map((item) => (
                        <div key={item.row}>Строка {item.row}: {(item.errors || []).join(', ')}</div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <History className="h-4 w-4 text-slate-500" />
              История импортов
            </CardTitle>
          </CardHeader>
          <CardContent>
            {imports.length > 0 ? (
              <div className="space-y-3">
                {imports.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-slate-200 p-4 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium text-slate-950">{item.file_name || 'Файл'}</div>
                        <div className="mt-1 text-slate-500">{item.created_at || ''}</div>
                      </div>
                      <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium', item.status === 'completed' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700')}>
                        {item.status}
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-600">
                      <div>Всего: {item.rows_total}</div>
                      <div>ОК: {item.rows_imported}</div>
                      <div>Дубли: {item.rows_skipped}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                Истории импорта пока нет.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardSection>
  );
};

const MiniStat: React.FC<{ label: string; value: number; tone?: 'default' | 'green' | 'red' }> = ({ label, value, tone = 'default' }) => (
  <div className={cn('rounded-2xl border px-4 py-3', tone === 'green' ? 'border-emerald-200 bg-emerald-50' : tone === 'red' ? 'border-rose-200 bg-rose-50' : 'border-slate-200 bg-white')}>
    <div className="text-xs uppercase tracking-[0.12em] text-slate-500">{label}</div>
    <div className="mt-1 text-xl font-semibold text-slate-950">{value}</div>
  </div>
);

const mappingLabels: Record<string, string> = {
  record_type: 'Тип строки',
  date: 'Дата',
  type: 'Доход/расход',
  category: 'Категория',
  amount: 'Сумма',
  service_name: 'Услуга',
  staff_name: 'Мастер',
  workplace_name: 'Рабочее место',
  revenue: 'Выручка',
  visits_count: 'Визиты',
  avg_price: 'Средняя цена',
  duration_minutes: 'Длительность',
  material_cost: 'Материалы',
  staff_payout: 'Выплата мастеру',
  booked_hours: 'Занято часов',
  available_hours: 'Доступно часов',
  no_show_count: 'No-show',
  rebooking_count: 'Повторная запись',
  gross_profit: 'Валовая прибыль',
  external_id: 'Внешний ID',
};

const MappingEditor: React.FC<{
  mapping: Record<string, string>;
  onChange: (mapping: Record<string, string>) => void;
}> = ({ mapping, onChange }) => {
  const entries = Object.entries(mapping);
  if (entries.length === 0) return null;
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="font-semibold text-slate-950">Сопоставление колонок</div>
      <div className="mt-1 text-sm text-slate-500">
        Если LocalOS неверно понял колонку, поправьте название вручную и снова проверьте файл.
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {entries.map(([field, source]) => (
          <div key={field} className="space-y-2">
            <Label>{mappingLabels[field] || field}</Label>
            <Input
              value={source}
              onChange={(event) => onChange({ ...mapping, [field]: event.target.value })}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

const PreviewTable: React.FC<{ rows: Array<Record<string, unknown>> }> = ({ rows }) => {
  if (rows.length === 0) return null;
  const columns = Object.keys(rows[0]).slice(0, 7);
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200">
      <table className="w-full text-xs">
        <thead className="bg-slate-50 text-left text-slate-500">
          <tr>
            {columns.map((column) => <th key={column} className="px-3 py-2 font-medium">{column}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.slice(0, 5).map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column} className="px-3 py-2 text-slate-700">{String(row[column] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default FinanceImportPanel;
