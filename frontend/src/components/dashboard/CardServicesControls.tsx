import { useState } from 'react';
import { Filter, LayoutGrid, Plus, Search, Sparkles, Wand2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import ServiceOptimizer from '@/components/ServiceOptimizer';
import type { ServiceCatalogCompressionSuggestion } from '@/components/dashboard/cardServicesLogic';

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
  regeneratingProblematic: boolean;
  optimizingServiceId: string | null;
  problemRegenerationStatus: string | null;
  onOptimizeAll: () => void;
  onRegenerateProblematic: () => void;
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
  regeneratingProblematic,
  optimizingServiceId,
  problemRegenerationStatus,
  onOptimizeAll,
  onRegenerateProblematic,
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
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
          <Button
            onClick={onOptimizeAll}
            disabled={!automationAllowed || optimizingAll || regeneratingProblematic || optimizingServiceId !== null}
            className="bg-indigo-700 text-white hover:bg-indigo-800"
            title={!automationAllowed ? automationLockedMessage : copy.optimizeAll}
          >
            <Wand2 className="mr-2 h-4 w-4" />
            {optimizingAll ? 'Оптимизируем...' : copy.optimizeAll}
          </Button>
          <Button
            variant="outline"
            onClick={onRegenerateProblematic}
            disabled={!automationAllowed || optimizingAll || regeneratingProblematic || optimizingServiceId !== null}
            className="border-indigo-200 bg-white text-indigo-700 hover:bg-indigo-50"
            title={!automationAllowed ? automationLockedMessage : 'Улучшить до 10 самых слабых описаний'}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            {regeneratingProblematic ? 'Улучшаем...' : 'Слабые описания'}
          </Button>
        </div>
      ) : null}
    </div>
    <div className="mb-4 rounded-xl border border-indigo-100 bg-white px-4 py-3 text-sm text-indigo-800">
      <div className="font-medium">Улучшить слабые описания</div>
      <div className="mt-1 text-indigo-700/80">
        LocalOS найдёт до 10 услуг, где не хватает важных запросов или описание выглядит слишком шаблонно, и предложит более сильные варианты.
      </div>
      {problemRegenerationStatus ? <div className="mt-2 font-medium">{problemRegenerationStatus}</div> : null}
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
  qualityFilter: string;
  onQualityFilterChange: (value: string) => void;
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
  qualityFilter,
  onQualityFilterChange,
  categories,
  sort,
  onSortChange,
}: CardServicesFilterBarProps) => (
  <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
    <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Поиск и фильтры</div>
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
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
      <div className="relative">
        <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <select
          value={qualityFilter}
          onChange={(event) => onQualityFilterChange(event.target.value)}
          className="w-full appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm"
        >
          <option value="all">Все по качеству</option>
          <option value="needs_review">Требуют доработки</option>
          <option value="manual_review">Нужна ручная проверка</option>
          <option value="good">ОК</option>
          <option value="missing_keywords">Не хватает запросов</option>
          <option value="weak_matches_only">Слабое совпадение</option>
          <option value="fallback">Шаблонные описания</option>
          <option value="no_keywords">Нет ключей</option>
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

type CardServiceCatalogCompressionDialogProps = {
  suggestion: ServiceCatalogCompressionSuggestion;
  onClose: () => void;
};

type CompressionDialogTab = 'recommendations' | 'groups' | 'rules';

const compressionTabs: Array<{ id: CompressionDialogTab; label: string }> = [
  { id: 'recommendations', label: 'Рекомендации' },
  { id: 'groups', label: 'Группировка' },
  { id: 'rules', label: 'Общие правила' },
];

export const CardServiceCatalogCompressionDialog = ({
  suggestion,
  onClose,
}: CardServiceCatalogCompressionDialogProps) => {
  const [activeTab, setActiveTab] = useState<CompressionDialogTab>('recommendations');

  return (
    <div
      className="fixed inset-0 z-[85] flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl ring-1 ring-black/10"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-slate-100 px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
                <LayoutGrid className="h-3.5 w-3.5" />
                Меню услуг
              </div>
              <h3 className="text-balance text-xl font-semibold text-slate-950">Сократить и сгруппировать услуги</h3>
              <p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-600">
                Предложение показывает, как сделать меню понятнее для клиента. LocalOS ничего не меняет в услугах автоматически.
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              className="h-10 w-10 shrink-0 p-0 text-slate-500 transition-[background-color,color,transform] duration-150 ease-out active:scale-[0.96] hover:bg-slate-100 hover:text-slate-950"
              aria-label="Закрыть"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200/70">
              <div className="text-xs font-medium text-slate-500">Сейчас</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-950">{suggestion.beforeCount}</div>
              <div className="text-xs text-slate-500">услуг в списке</div>
            </div>
            <div className="rounded-2xl bg-emerald-50 p-4 ring-1 ring-emerald-100">
              <div className="text-xs font-medium text-emerald-700">После группировки</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-emerald-950">{suggestion.estimatedAfterCount}</div>
              <div className="text-xs text-emerald-700/80">примерная цель</div>
            </div>
            <div className="rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-100">
              <div className="text-xs font-medium text-amber-700">Приоритет</div>
              <div className="mt-1 text-lg font-semibold text-amber-950">
                {suggestion.highPriority ? 'Высокий' : 'Средний'}
              </div>
              <div className="text-xs text-amber-700/80">только рекомендация</div>
            </div>
          </div>
        </div>

        <div className="border-b border-slate-100 px-6 pt-4">
          <div className="flex gap-2 overflow-x-auto pb-4 [&::-webkit-scrollbar]:hidden">
            {compressionTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`min-h-10 rounded-xl px-4 text-sm font-medium transition-[background-color,color,box-shadow] duration-150 ease-out ${
                  activeTab === tab.id
                    ? 'bg-slate-950 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-950'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {activeTab === 'recommendations' ? (
            <div className="space-y-5">
              <div className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200/70">
                <div className="text-sm font-semibold text-slate-950">Что сделать в первую очередь</div>
                <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">{suggestion.summary}</p>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {suggestion.groups.slice(0, 6).map((group) => (
                  <div key={group.id} className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-950">{group.title}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          {group.currentCount} → {group.recommendedCount} позиций
                        </div>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium tabular-nums text-slate-600">
                        -{Math.max(0, group.currentCount - group.recommendedCount)}
                      </span>
                    </div>
                    <p className="mt-3 text-pretty text-sm leading-6 text-slate-600">{group.action}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {activeTab === 'groups' ? (
            <div className="space-y-4">
              {suggestion.groups.length > 0 ? suggestion.groups.map((group) => (
                <div key={group.id} className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <h4 className="text-balance text-base font-semibold text-slate-950">{group.title}</h4>
                      <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">{group.reason}</p>
                    </div>
                    <div className="shrink-0 rounded-xl bg-slate-50 px-3 py-2 text-sm font-semibold tabular-nums text-slate-700 ring-1 ring-slate-200">
                      {group.currentCount} → {group.recommendedCount}
                    </div>
                  </div>
                  <div className="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700">
                    {group.action}
                  </div>
                  {group.examples.length > 0 ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {group.examples.map((example) => (
                        <span key={example} className="max-w-full truncate rounded-full bg-white px-3 py-1.5 text-xs text-slate-600 ring-1 ring-slate-200">
                          {example}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              )) : (
                <div className="rounded-2xl bg-slate-50 p-5 text-sm text-slate-600 ring-1 ring-slate-200">
                  Явных перегруженных групп не найдено. Можно использовать общие правила и ручную проверку категорий.
                </div>
              )}
            </div>
          ) : null}

          {activeTab === 'rules' ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {suggestion.generalRecommendations.map((recommendation, index) => (
                <div key={recommendation} className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200/70">
                  <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Правило {index + 1}
                  </div>
                  <p className="text-pretty text-sm leading-6 text-slate-700">{recommendation}</p>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-100 bg-slate-50/80 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-pretty text-xs leading-5 text-slate-500">
            Это окно не сохраняет изменения. Следующий этап — отдельный approval-flow для применения группировки.
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            className="border-slate-200 bg-white text-slate-700 transition-[background-color,color,transform] duration-150 ease-out active:scale-[0.96] hover:bg-slate-100"
          >
            Закрыть
          </Button>
        </div>
      </div>
    </div>
  );
};

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
