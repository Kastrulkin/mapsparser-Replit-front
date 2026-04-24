import { Filter, Plus, Search, Sparkles, Wand2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import ServiceOptimizer from '@/components/ServiceOptimizer';

type ServiceFormValue = {
  category: string;
  name: string;
  description: string;
  keywords: string;
  price: string;
};

type ServiceCopy = {
  addService: string;
  category: string;
  serviceName: string;
  description: string;
  keywords: string;
  price: string;
  cancel: string;
  add: string;
  save: string;
  edit: string;
  optimizeAll: string;
  seoTitle: string;
  seoDescription: string;
  placeholders: {
    category: string;
    name: string;
    description: string;
    keywords: string;
    price: string;
  };
  search: string;
};

type CardServiceFormProps = {
  copy: ServiceCopy;
  value: ServiceFormValue;
  onChange: (value: ServiceFormValue) => void;
  onCancel: () => void;
  onSubmit: () => void;
};

export const CardServiceAddForm = ({ copy, value, onChange, onCancel, onSubmit }: CardServiceFormProps) => (
  <div className="mb-8 rounded-2xl border border-slate-200 bg-slate-50/70 p-6">
    <h3 className="mb-6 flex items-center gap-2 text-lg font-semibold text-slate-950">
      <Plus className="h-5 w-5 text-primary" />
      {copy.addService}
    </h3>
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-700">{copy.category}</label>
        <input
          type="text"
          value={value.category}
          onChange={(event) => onChange({ ...value, category: event.target.value })}
          className="w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20"
          placeholder={copy.placeholders.category}
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-700">{copy.serviceName}</label>
        <input
          type="text"
          value={value.name}
          onChange={(event) => onChange({ ...value, name: event.target.value })}
          className="w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20"
          placeholder={copy.placeholders.name}
        />
      </div>
      <div className="space-y-2 md:col-span-2">
        <label className="text-sm font-medium text-slate-700">{copy.description}</label>
        <textarea
          value={value.description}
          onChange={(event) => onChange({ ...value, description: event.target.value })}
          className="min-h-[100px] w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20"
          placeholder={copy.placeholders.description}
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-700">{copy.keywords}</label>
        <input
          type="text"
          value={value.keywords}
          onChange={(event) => onChange({ ...value, keywords: event.target.value })}
          className="w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20"
          placeholder={copy.placeholders.keywords}
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-700">{copy.price}</label>
        <input
          type="text"
          value={value.price}
          onChange={(event) => onChange({ ...value, price: event.target.value })}
          className="w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20"
          placeholder={copy.placeholders.price}
        />
      </div>
    </div>
    <div className="mt-8 flex justify-end gap-3">
      <Button onClick={onCancel} variant="outline" className="border-slate-200 text-slate-600 hover:bg-slate-100">{copy.cancel}</Button>
      <Button onClick={onSubmit} className="bg-primary text-white">{copy.add}</Button>
    </div>
  </div>
);

type CardServiceOptimizerPanelProps = {
  copy: ServiceCopy;
  businessName?: string;
  businessId?: string;
  language: string;
  servicesCount: number;
  automationAllowed: boolean;
  automationLockedMessage: string;
  optimizingAll: boolean;
  optimizingServiceId: string | null;
  onOptimizeAll: () => void;
  onServicesImported: () => void;
};

export const CardServiceOptimizerPanel = ({
  copy,
  businessName,
  businessId,
  language,
  servicesCount,
  automationAllowed,
  automationLockedMessage,
  optimizingAll,
  optimizingServiceId,
  onOptimizeAll,
  onServicesImported,
}: CardServiceOptimizerPanelProps) => (
  <div className="mb-8 rounded-2xl border border-indigo-100 bg-indigo-50/70 p-6">
    <div className="mb-4 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-indigo-600" />
          <h3 className="font-semibold text-indigo-950">{copy.seoTitle}</h3>
        </div>
        <p className="max-w-2xl text-sm leading-relaxed text-indigo-800/80">{copy.seoDescription}</p>
      </div>
      {servicesCount > 0 ? (
        <Button
          variant="outline"
          onClick={onOptimizeAll}
          disabled={!automationAllowed || optimizingAll || optimizingServiceId !== null}
          className="shrink-0 border-indigo-200 bg-white text-indigo-700 hover:bg-indigo-50"
          title={!automationAllowed ? automationLockedMessage : copy.optimizeAll}
        >
          <Wand2 className="mr-2 h-4 w-4" />
          {optimizingAll ? 'Оптимизируем...' : copy.optimizeAll}
        </Button>
      ) : null}
    </div>
    {!automationAllowed ? (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        {automationLockedMessage}
      </div>
    ) : (
      <ServiceOptimizer
        businessName={businessName}
        businessId={businessId}
        language={language === 'ru' ? 'ru' : 'en'}
        hideTextInput={true}
        onServicesImported={onServicesImported}
      />
    )}
  </div>
);

type CardServicesMetaStripProps = {
  lastParseDate: string | null;
  noNewServicesFound: boolean;
  locale: string;
};

export const CardServicesMetaStrip = ({ lastParseDate, noNewServicesFound, locale }: CardServicesMetaStripProps) => {
  if (!lastParseDate) return null;

  return (
    <div className="mb-4 flex flex-col gap-1 rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 md:flex-row md:items-center md:justify-between">
      <div className="text-sm text-slate-700">
        <span className="font-semibold text-slate-950">Последний парсинг карточки:</span>{' '}
        {new Date(lastParseDate).toLocaleDateString(locale, {
          day: '2-digit',
          month: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })}
      </div>
      {noNewServicesFound ? <div className="text-sm font-medium text-amber-700">Новых услуг не найдено</div> : null}
    </div>
  );
};

type CardServicesFilterBarProps = {
  copy: ServiceCopy;
  search: string;
  onSearchChange: (value: string) => void;
  categoryFilter: string;
  onCategoryFilterChange: (value: string) => void;
  categories: string[];
  sort: string;
  onSortChange: (value: string) => void;
};

export const CardServicesFilterBar = ({
  copy,
  search,
  onSearchChange,
  categoryFilter,
  onCategoryFilterChange,
  categories,
  sort,
  onSortChange,
}: CardServicesFilterBarProps) => (
  <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
    <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Поиск и фильтры</div>
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={copy.search}
          className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm"
        />
      </div>
      <div className="relative">
        <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <select
          value={categoryFilter}
          onChange={(event) => onCategoryFilterChange(event.target.value)}
          className="w-full appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm"
        >
          <option value="all">Все категории</option>
          {categories.map((category) => <option key={category} value={category}>{category}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        <select value={sort} onChange={(event) => onSortChange(event.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
          <option value="default">Порядок по умолчанию</option>
          <option value="name_asc">Название: А-Я</option>
          <option value="name_desc">Название: Я-А</option>
          <option value="updated_desc">Обновлено: новые</option>
          <option value="updated_asc">Обновлено: старые</option>
          <option value="price_asc">Цена: по возрастанию</option>
          <option value="price_desc">Цена: по убыванию</option>
        </select>
        <Button type="button" variant={sort === 'name_asc' ? 'default' : 'outline'} onClick={() => onSortChange(sort === 'name_asc' ? 'default' : 'name_asc')} className="h-10 shrink-0 px-3" title="Сортировка по алфавиту">
          А-Я
        </Button>
      </div>
    </div>
  </div>
);

type CardServiceEditDialogProps = {
  copy: ServiceCopy;
  value: ServiceFormValue;
  onChange: (value: ServiceFormValue) => void;
  onCancel: () => void;
  onSave: () => void;
};

export const CardServiceEditDialog = ({ copy, value, onChange, onCancel, onSave }: CardServiceEditDialogProps) => (
  <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm">
    <div className="w-full max-w-2xl rounded-2xl border border-slate-100 bg-white p-6 shadow-2xl">
      <h3 className="mb-5 text-lg font-semibold text-slate-950">{copy.edit}</h3>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">{copy.category}</label>
          <input type="text" value={value.category} onChange={(event) => onChange({ ...value, category: event.target.value })} className="w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20" />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">{copy.serviceName}</label>
          <input type="text" value={value.name} onChange={(event) => onChange({ ...value, name: event.target.value })} className="w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20" />
        </div>
        <div className="space-y-2 md:col-span-2">
          <label className="text-sm font-medium text-slate-700">{copy.description}</label>
          <textarea value={value.description} onChange={(event) => onChange({ ...value, description: event.target.value })} className="min-h-[120px] w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20" />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">{copy.keywords}</label>
          <input type="text" value={value.keywords} onChange={(event) => onChange({ ...value, keywords: event.target.value })} className="w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20" />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">{copy.price}</label>
          <input type="text" value={value.price} onChange={(event) => onChange({ ...value, price: event.target.value })} className="w-full rounded-lg border border-slate-200 px-4 py-2 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20" />
        </div>
      </div>
      <div className="mt-6 flex justify-end gap-3">
        <Button variant="outline" className="border-slate-200 text-slate-600 hover:bg-slate-100" onClick={onCancel}>{copy.cancel}</Button>
        <Button className="bg-primary text-white" onClick={onSave}>{copy.save}</Button>
      </div>
    </div>
  </div>
);
