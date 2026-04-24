import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

type GeoProvider = 'google' | 'yandex' | 'both';

type ImportFileError = {
  row?: number;
  error?: string;
};

type PartnershipRawIntakeControlsProps = {
  loading: boolean;
  linksText: string;
  onLinksTextChange: (value: string) => void;
  onImportLinks: () => void;
  onRefreshLeads: () => void;
  importFileContent: string;
  importFileName: string;
  importFileFormat: string;
  importFileErrors: ImportFileError[];
  onImportFilePick: (file: File | null) => void;
  onImportFile: () => void;
  onDownloadCsvTemplate: () => void;
  geoProvider: GeoProvider;
  onGeoProviderChange: (value: GeoProvider) => void;
  geoCity: string;
  onGeoCityChange: (value: string) => void;
  geoCategory: string;
  onGeoCategoryChange: (value: string) => void;
  geoQuery: string;
  onGeoQueryChange: (value: string) => void;
  geoRadiusKm: string;
  onGeoRadiusKmChange: (value: string) => void;
  geoLimit: string;
  onGeoLimitChange: (value: string) => void;
  onGeoSearch: () => void;
  onResetGeoSearch: () => void;
};

function normalizeGeoProvider(value: string): GeoProvider | null {
  if (value === 'google' || value === 'yandex' || value === 'both') {
    return value;
  }
  return null;
}

export function PartnershipRawIntakeControls({
  loading,
  linksText,
  onLinksTextChange,
  onImportLinks,
  onRefreshLeads,
  importFileContent,
  importFileName,
  importFileFormat,
  importFileErrors,
  onImportFilePick,
  onImportFile,
  onDownloadCsvTemplate,
  geoProvider,
  onGeoProviderChange,
  geoCity,
  onGeoCityChange,
  geoCategory,
  onGeoCategoryChange,
  geoQuery,
  onGeoQueryChange,
  geoRadiusKm,
  onGeoRadiusKmChange,
  geoLimit,
  onGeoLimitChange,
  onGeoSearch,
  onResetGeoSearch,
}: PartnershipRawIntakeControlsProps) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
      <div className="space-y-5 rounded-3xl border border-slate-200/80 bg-white/95 p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Вариант 1</div>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">Импортировать готовый список</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Если партнёры уже собраны, вставьте ссылки или загрузите файл. LocalOS добавит их во входящий список и сохранит контакты.
            </p>
          </div>
        </div>

        <div className="space-y-3 rounded-2xl bg-slate-50/80 p-4">
          <div className="text-sm font-medium text-slate-800">Ссылки на карты</div>
          <Textarea
            rows={5}
            value={linksText}
            onChange={(event) => onLinksTextChange(event.target.value)}
            placeholder="Вставьте ссылки на Яндекс Карты, по одной на строку"
            className="border-slate-200 bg-white"
          />
          <div className="flex flex-wrap gap-2">
            <Button className="bg-slate-950 text-white hover:bg-slate-800" onClick={onImportLinks} disabled={loading}>
              Добавить партнёров
            </Button>
            <Button variant="outline" onClick={onRefreshLeads} disabled={loading}>
              Обновить список
            </Button>
          </div>
        </div>

        <div className="space-y-3 rounded-2xl border border-slate-100 bg-white p-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Импорт файла партнёров</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              CSV / JSON / JSONL. Поля: <code>name, source_url, city, category, phone, email, website, telegram_url, whatsapp_url</code>.
            </p>
          </div>
          <div className="flex flex-col gap-2 md:flex-row md:items-center">
            <Input
              type="file"
              accept=".csv,.json,.jsonl,text/csv,application/json"
              onChange={(event) => onImportFilePick(event.target.files?.[0] || null)}
            />
            <Button onClick={onImportFile} disabled={loading || !importFileContent.trim()}>
              Импортировать файл
            </Button>
            <Button variant="outline" onClick={onDownloadCsvTemplate} disabled={loading}>
              Скачать CSV-шаблон
            </Button>
          </div>
          {importFileName ? (
            <p className="text-xs text-muted-foreground">
              Файл: {importFileName} {importFileFormat ? `(${importFileFormat.toUpperCase()})` : ''}
            </p>
          ) : null}
          {importFileErrors.length > 0 ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <div className="mb-1 font-medium">Ошибки валидации (первые {importFileErrors.length})</div>
              <div className="max-h-32 space-y-1 overflow-auto">
                {importFileErrors.map((err, idx) => (
                  <div key={`${err.row || 'x'}-${idx}`}>
                    Строка {err.row || '?'}: {err.error || 'ошибка'}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="space-y-5 rounded-3xl border border-slate-200/80 bg-white/95 p-6 shadow-sm">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Вариант 2</div>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">Найти партнёров на карте</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Задайте город, категорию и радиус. LocalOS найдёт компании рядом с вами и добавит их во входящий список.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">Источник</div>
            <Select
              value={geoProvider}
              onValueChange={(value) => {
                const nextProvider = normalizeGeoProvider(value);
                if (nextProvider) onGeoProviderChange(nextProvider);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Источник поиска" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="google">Google Maps</SelectItem>
                <SelectItem value="yandex">Яндекс Карты</SelectItem>
                <SelectItem value="both">Оба источника</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">Город</div>
            <Input value={geoCity} onChange={(event) => onGeoCityChange(event.target.value)} placeholder="Например, Санкт-Петербург" />
          </div>
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">Категория</div>
            <Input value={geoCategory} onChange={(event) => onGeoCategoryChange(event.target.value)} placeholder="Например, салон красоты" />
          </div>
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">Запрос</div>
            <Input value={geoQuery} onChange={(event) => onGeoQueryChange(event.target.value)} placeholder="Например, маникюр у метро" />
          </div>
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">Радиус, км</div>
            <Input value={geoRadiusKm} onChange={(event) => onGeoRadiusKmChange(event.target.value)} placeholder="Радиус (км)" type="number" min={1} max={100} />
          </div>
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">Лимит результатов</div>
            <Input value={geoLimit} onChange={(event) => onGeoLimitChange(event.target.value)} placeholder="Лимит" type="number" min={1} max={200} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          <Button className="bg-slate-950 text-white hover:bg-slate-800" onClick={onGeoSearch} disabled={loading}>
            Найти партнёров
          </Button>
          <Button variant="outline" onClick={onResetGeoSearch} disabled={loading}>
            Сбросить
          </Button>
        </div>
      </div>
    </div>
  );
}
