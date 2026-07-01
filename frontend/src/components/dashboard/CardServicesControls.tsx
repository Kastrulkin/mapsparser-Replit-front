import { useMemo, useState } from 'react';
import { Filter, LayoutGrid, Plus, Search, Sparkles, Wand2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import ServiceOptimizer from '@/components/ServiceOptimizer';
import type { ServiceCatalogCompressionSuggestion } from '@/components/dashboard/cardServicesLogic';
import type { ServiceTableItem } from '@/components/dashboard/CardServicesTable';
import {
  applyServiceCompressionDraft,
  createServiceCompressionDraft,
  rollbackServiceCompressionDraft,
  updateServiceCompressionDraft,
} from '@/components/dashboard/cardOverviewApi';

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
  services: ServiceTableItem[];
  businessId?: string;
  categories: string[];
  onApplied: (message: string) => Promise<void> | void;
  onClose: () => void;
};

type CompressionDialogTab = 'suggestions' | 'editor' | 'review';

type CompressionTarget = {
  category?: string;
  name?: string;
  description?: string;
  keywords?: string[];
  price?: string;
};

type CompressionGroup = {
  id: string;
  title?: string;
  reason?: string;
  action?: 'apply' | 'skip' | 'promotion';
  action_text?: string;
  source_service_ids?: string[];
  current_count?: number;
  recommended_count?: number;
  target?: CompressionTarget;
  examples?: string[];
};

type CompressionDraft = {
  id: string;
  status: string;
  before_count: number;
  after_count: number;
  groups_json: CompressionGroup[];
  created_service_ids?: string[];
  archived_service_ids?: string[];
};

const compressionTabs: Array<{ id: CompressionDialogTab; label: string }> = [
  { id: 'suggestions', label: 'Предложения' },
  { id: 'editor', label: 'Редактор групп' },
  { id: 'review', label: 'Проверка и применение' },
];

const compressionGroupActions: Array<'apply' | 'skip' | 'promotion'> = ['apply', 'skip', 'promotion'];

const groupActionLabels: Record<string, string> = {
  apply: 'Применить',
  skip: 'Оставить как есть',
  promotion: 'Вынести в акции',
};

const normalizeDraftGroups = (value: unknown): CompressionGroup[] => {
  if (!Array.isArray(value)) return [];
  return value.map((item, index) => {
    const record = item && typeof item === 'object' ? Object.fromEntries(Object.entries(item)) : {};
    const targetRecord = record.target && typeof record.target === 'object' ? Object.fromEntries(Object.entries(record.target)) : {};
    const action = String(record.action || 'apply');
    return {
      id: String(record.id || `group-${index}`),
      title: String(record.title || 'Группа услуг'),
      reason: String(record.reason || ''),
      action: action === 'skip' || action === 'promotion' ? action : 'apply',
      action_text: String(record.action_text || ''),
      source_service_ids: Array.isArray(record.source_service_ids) ? record.source_service_ids.map((id) => String(id)) : [],
      current_count: Number(record.current_count || 0),
      recommended_count: Number(record.recommended_count || 0),
      target: {
        category: String(targetRecord.category || ''),
        name: String(targetRecord.name || ''),
        description: String(targetRecord.description || ''),
        keywords: Array.isArray(targetRecord.keywords) ? targetRecord.keywords.map((keyword) => String(keyword)) : [],
        price: String(targetRecord.price || ''),
      },
      examples: Array.isArray(record.examples) ? record.examples.map((example) => String(example)) : [],
    };
  });
};

export const CardServiceCatalogCompressionDialog = ({
  suggestion,
  services,
  businessId,
  categories,
  onApplied,
  onClose,
}: CardServiceCatalogCompressionDialogProps) => {
  const [activeTab, setActiveTab] = useState<CompressionDialogTab>('suggestions');
  const [draft, setDraft] = useState<CompressionDraft | null>(null);
  const [groups, setGroups] = useState<CompressionGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const serviceById = useMemo(() => {
    const map = new Map<string, ServiceTableItem>();
    services.forEach((service) => {
      if (service.id && !service.is_external) map.set(String(service.id), service);
    });
    return map;
  }, [services]);

  const activeGroups = groups.filter((group) => group.action === 'apply' || group.action === 'promotion');
  const archivedCount = new Set(activeGroups.flatMap((group) => group.source_service_ids || [])).size;
  const createdCount = activeGroups.filter((group) => group.action === 'apply').length;
  const estimatedAfterCount = draft ? Math.max(0, Number(draft.before_count || 0) - archivedCount + createdCount) : suggestion.estimatedAfterCount;
  const selectedGroup = groups.find((group) => group.id === selectedGroupId) || groups[0] || null;
  const selectedServices = selectedGroup ? (selectedGroup.source_service_ids || []).map((id) => serviceById.get(id)).filter(Boolean) : [];
  const usedServiceIds = new Set(groups.flatMap((group) => group.source_service_ids || []));
  const addableServices = services.filter((service) => service.id && !service.is_external && !usedServiceIds.has(String(service.id))).slice(0, 80);

  const updateGroup = (groupId: string, patch: Partial<CompressionGroup>) => {
    setGroups((prev) => prev.map((group) => group.id === groupId ? { ...group, ...patch } : group));
  };

  const updateGroupTarget = (groupId: string, patch: Partial<CompressionTarget>) => {
    setGroups((prev) => prev.map((group) => (
      group.id === groupId
        ? { ...group, target: { ...(group.target || {}), ...patch } }
        : group
    )));
  };

  const createDraft = async () => {
    if (!businessId) {
      setErrorMessage('Не выбран бизнес для группировки услуг');
      return;
    }
    setPending(true);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const { response, data } = await createServiceCompressionDraft({ business_id: businessId });
      if (!response.ok || !data.success) throw new Error(data.error || 'Не удалось создать черновик');
      const nextDraft: CompressionDraft = data.draft;
      const nextGroups = normalizeDraftGroups(nextDraft.groups_json);
      setDraft(nextDraft);
      setGroups(nextGroups);
      setSelectedGroupId(nextGroups[0]?.id || null);
      setActiveTab('editor');
      setStatusMessage('Черновик создан. Проверьте группы и отредактируйте итоговые услуги.');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Не удалось создать черновик');
    } finally {
      setPending(false);
    }
  };

  const saveDraft = async () => {
    if (!draft) return null;
    setPending(true);
    setErrorMessage(null);
    try {
      const { response, data } = await updateServiceCompressionDraft(draft.id, { groups });
      if (!response.ok || !data.success) throw new Error(data.error || 'Не удалось сохранить черновик');
      const nextDraft: CompressionDraft = data.draft;
      setDraft(nextDraft);
      setStatusMessage('Черновик сохранён.');
      return nextDraft;
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Не удалось сохранить черновик');
      return null;
    } finally {
      setPending(false);
    }
  };

  const applyDraft = async () => {
    if (!draft) return;
    const ok = window.confirm(`Будет создано ${createdCount} объединённых услуг, ${archivedCount} исходных услуг будут скрыты из активного меню. Внешние карты не изменятся.`);
    if (!ok) return;
    const saved = await saveDraft();
    if (!saved) return;
    setPending(true);
    setErrorMessage(null);
    try {
      const { response, data } = await applyServiceCompressionDraft(saved.id);
      if (!response.ok || !data.success) throw new Error(data.error || 'Не удалось применить группировку');
      setDraft(data.draft);
      setStatusMessage(`Меню сокращено: было ${saved.before_count}, стало ${data.draft?.after_count ?? estimatedAfterCount}. Откат доступен в этом черновике.`);
      await onApplied('Меню услуг сгруппировано. Исходные строки скрыты из активного списка.');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Не удалось применить группировку');
    } finally {
      setPending(false);
    }
  };

  const rollbackDraft = async () => {
    if (!draft) return;
    const ok = window.confirm('Откатить группировку: скрыть созданные объединённые услуги и вернуть исходные строки?');
    if (!ok) return;
    setPending(true);
    setErrorMessage(null);
    try {
      const { response, data } = await rollbackServiceCompressionDraft(draft.id);
      if (!response.ok || !data.success) throw new Error(data.error || 'Не удалось откатить группировку');
      setDraft(data.draft);
      setStatusMessage('Группировка откачена, исходные услуги возвращены.');
      await onApplied('Группировка услуг откачена. Исходные услуги возвращены.');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Не удалось откатить группировку');
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[85] flex items-start justify-center overflow-y-auto bg-black/30 p-3 backdrop-blur-sm sm:p-5"
      onClick={onClose}
    >
      <div
        className="my-auto flex h-[calc(100dvh-24px)] min-h-[720px] w-full max-w-[min(1500px,calc(100vw-24px))] flex-col overflow-hidden rounded-3xl bg-white shadow-2xl ring-1 ring-black/10 sm:h-[calc(100dvh-40px)] sm:max-w-[min(1500px,calc(100vw-40px))]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="shrink-0 border-b border-slate-100 px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
                <LayoutGrid className="h-3.5 w-3.5" />
                Меню услуг
              </div>
              <h3 className="text-balance text-xl font-semibold text-slate-950">Сократить и сгруппировать услуги</h3>
              <p className="mt-2 max-w-4xl text-pretty text-sm leading-6 text-slate-600">
                Рабочий редактор: создайте черновик, объедините похожие услуги, назначьте категории и примените только после проверки.
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
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200/70">
              <div className="text-xs font-medium text-slate-500">Сейчас</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-950">{suggestion.beforeCount}</div>
              <div className="text-xs text-slate-500">услуг в списке</div>
            </div>
            <div className="rounded-2xl bg-emerald-50 p-3 ring-1 ring-emerald-100">
              <div className="text-xs font-medium text-emerald-700">После группировки</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-emerald-950">{estimatedAfterCount}</div>
              <div className="text-xs text-emerald-700/80">по текущему черновику</div>
            </div>
            <div className="rounded-2xl bg-amber-50 p-3 ring-1 ring-amber-100">
              <div className="text-xs font-medium text-amber-700">Приоритет</div>
              <div className="mt-1 text-lg font-semibold text-amber-950">
                {suggestion.highPriority ? 'Высокий' : 'Средний'}
              </div>
              <div className="text-xs text-amber-700/80">{draft ? draft.status : 'черновик не создан'}</div>
            </div>
          </div>
        </div>

        <div className="shrink-0 border-b border-slate-100 px-6 pt-3">
          <div className="flex gap-2 overflow-x-auto pb-3 [&::-webkit-scrollbar]:hidden">
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
          {statusMessage ? <div className="mb-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-100">{statusMessage}</div> : null}
          {errorMessage ? <div className="mb-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-100">{errorMessage}</div> : null}

          {activeTab === 'suggestions' ? (
            <div className="space-y-5">
              <div className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200/70">
                <div className="text-sm font-semibold text-slate-950">Создать рабочий черновик</div>
                <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">{suggestion.summary}</p>
                <Button type="button" onClick={createDraft} disabled={pending || !businessId} className="mt-4 bg-slate-950 text-white hover:bg-slate-800">
                  {pending ? 'Готовим черновик...' : draft ? 'Пересоздать черновик' : 'Создать черновик группировки'}
                </Button>
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

          {activeTab === 'editor' ? (
            !draft ? (
              <div className="rounded-2xl bg-slate-50 p-5 text-sm text-slate-600 ring-1 ring-slate-200">
                Сначала создайте черновик на вкладке “Предложения”.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(320px,0.75fr)_minmax(640px,1.25fr)]">
                <div className="space-y-3 xl:sticky xl:top-0 xl:self-start">
                  <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600 ring-1 ring-slate-200/70">
                    <div className="font-semibold text-slate-950">Применяются не все услуги сразу</div>
                    <div className="mt-1">
                      Выберите группу и поставьте “Оставить как есть”, чтобы исключить её целиком. Внутри группы снимите чекбокс с услуги, чтобы не скрывать конкретную строку.
                    </div>
                  </div>
                  {groups.map((group) => (
                    <button
                      key={group.id}
                      type="button"
                      onClick={() => setSelectedGroupId(group.id)}
                      className={`w-full rounded-2xl border px-4 py-3 text-left transition-[background-color,border-color,color] duration-150 ${
                        selectedGroup?.id === group.id ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-900 hover:bg-slate-50'
                      }`}
                    >
                      <div className="text-sm font-semibold">{group.title}</div>
                      <div className={`mt-1 text-xs ${selectedGroup?.id === group.id ? 'text-slate-300' : 'text-slate-500'}`}>
                        {(group.source_service_ids || []).length} → {group.action === 'apply' ? 1 : 0} · {groupActionLabels[group.action || 'apply']}
                      </div>
                    </button>
                  ))}
                </div>

                {selectedGroup ? (
                  <div className="space-y-4 rounded-2xl bg-white p-5 ring-1 ring-slate-200">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">{selectedGroup.title}</div>
                      <p className="mt-1 text-sm leading-6 text-slate-600">{selectedGroup.reason}</p>
                    </div>

                      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                        {compressionGroupActions.map((action) => (
                          <button
                          key={action}
                          type="button"
                          onClick={() => updateGroup(selectedGroup.id, { action })}
                          className={`rounded-xl border px-3 py-2 text-sm font-medium transition-colors ${
                            selectedGroup.action === action ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                          }`}
                        >
                          {groupActionLabels[action]}
                        </button>
                        ))}
                      </div>
                      <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200/70">
                        {selectedGroup.action === 'apply'
                          ? 'Эта группа будет применена: LocalOS создаст одну объединённую услугу и скроет выбранные исходные строки.'
                          : selectedGroup.action === 'promotion'
                            ? 'Эти строки будут вынесены из активного меню как акции после подтверждения. Новая услуга не создаётся.'
                            : 'Эта группа исключена из применения. Услуги останутся в активном меню без изменений.'}
                      </div>

                    {selectedGroup.action === 'apply' ? (
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <label className="text-sm font-medium text-slate-700">
                          Категория
                          <input
                            list="service-compression-categories"
                            value={selectedGroup.target?.category || ''}
                            onChange={(event) => updateGroupTarget(selectedGroup.id, { category: event.target.value })}
                            className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
                          />
                        </label>
                        <label className="text-sm font-medium text-slate-700">
                          Цена или диапазон
                          <input
                            value={selectedGroup.target?.price || ''}
                            onChange={(event) => updateGroupTarget(selectedGroup.id, { price: event.target.value })}
                            className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
                          />
                        </label>
                        <label className="text-sm font-medium text-slate-700 md:col-span-2">
                          Итоговое название
                          <input
                            value={selectedGroup.target?.name || ''}
                            onChange={(event) => updateGroupTarget(selectedGroup.id, { name: event.target.value })}
                            className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
                          />
                        </label>
                        <label className="text-sm font-medium text-slate-700 md:col-span-2">
                          Описание с вариантами
                          <textarea
                            value={selectedGroup.target?.description || ''}
                            onChange={(event) => updateGroupTarget(selectedGroup.id, { description: event.target.value })}
                            rows={7}
                            className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
                          />
                        </label>
                        <label className="text-sm font-medium text-slate-700 md:col-span-2">
                          Ключевые слова через запятую
                          <input
                            value={(selectedGroup.target?.keywords || []).join(', ')}
                            onChange={(event) => updateGroupTarget(selectedGroup.id, { keywords: event.target.value.split(',').map((item) => item.trim()).filter(Boolean) })}
                            className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
                          />
                        </label>
                      </div>
                    ) : null}

                    <datalist id="service-compression-categories">
                      {categories.map((category) => <option key={category} value={category} />)}
                    </datalist>

                    <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200/70">
                      <div className="mb-3 text-sm font-semibold text-slate-950">Исходные услуги в группе</div>
                      <div className="mb-3 text-xs leading-5 text-slate-500">
                        Снимите чекбокс, если услугу нельзя объединять с этой группой.
                      </div>
                      <div className="max-h-[min(52dvh,520px)] space-y-2 overflow-y-auto pr-1">
                        {selectedServices.map((service) => (
                          <label key={service?.id} className="flex items-start gap-2 rounded-xl bg-white px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-200">
                            <input
                              type="checkbox"
                              checked
                              onChange={() => updateGroup(selectedGroup.id, {
                                source_service_ids: (selectedGroup.source_service_ids || []).filter((id) => id !== service?.id),
                              })}
                              className="mt-1"
                            />
                            <span className="min-w-0">
                              <span className="block truncate font-medium text-slate-950">{service?.name || 'Без названия'}</span>
                              <span className="block truncate text-xs text-slate-500">{service?.category || 'Без категории'} · {service?.price || 'без цены'}</span>
                            </span>
                          </label>
                        ))}
                      </div>
                      {addableServices.length > 0 ? (
                        <select
                          className="mt-3 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
                          value=""
                          onChange={(event) => {
                            const value = event.target.value;
                            if (!value) return;
                            updateGroup(selectedGroup.id, {
                              source_service_ids: [...(selectedGroup.source_service_ids || []), value],
                            });
                          }}
                        >
                          <option value="">Добавить услугу в группу</option>
                          {addableServices.map((service) => (
                            <option key={service.id} value={service.id}>{service.name || 'Без названия'}</option>
                          ))}
                        </select>
                      ) : null}
                    </div>

                    <div className="flex justify-end gap-2">
                      <Button type="button" variant="outline" onClick={saveDraft} disabled={pending}>
                        {pending ? 'Сохраняем...' : 'Сохранить правки'}
                      </Button>
                      <Button type="button" onClick={() => setActiveTab('review')} className="bg-slate-950 text-white hover:bg-slate-800">
                        Перейти к проверке
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl bg-slate-50 p-5 text-sm text-slate-600 ring-1 ring-slate-200">
                    Нет групп для редактирования. Можно создать обычные категории вручную в списке услуг.
                  </div>
                )}
              </div>
            )
          ) : null}

          {activeTab === 'review' ? (
            !draft ? (
              <div className="rounded-2xl bg-slate-50 p-5 text-sm text-slate-600 ring-1 ring-slate-200">
                Сначала создайте черновик на вкладке “Предложения”.
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                    <div className="text-xs text-slate-500">Новые объединённые услуги</div>
                    <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-950">{createdCount}</div>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                    <div className="text-xs text-slate-500">Будут скрыты из активного меню</div>
                    <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-950">{archivedCount}</div>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                    <div className="text-xs text-slate-500">Итоговое количество</div>
                    <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-950">{estimatedAfterCount}</div>
                  </div>
                </div>

                <div className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
                  <div className="mb-3 text-sm font-semibold text-slate-950">Что будет применено</div>
                  <div className="space-y-3">
                    {activeGroups.map((group) => (
                      <div key={group.id} className="rounded-xl bg-slate-50 px-4 py-3 text-sm ring-1 ring-slate-200/70">
                        <div className="font-medium text-slate-950">
                          {group.action === 'apply' ? group.target?.name || group.title : group.title}
                        </div>
                        <div className="mt-1 text-slate-600">
                          {groupActionLabels[group.action || 'apply']} · {(group.source_service_ids || []).length} исходных услуг
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex flex-col gap-2 rounded-2xl bg-amber-50 p-4 text-sm text-amber-900 ring-1 ring-amber-100">
                  <div className="font-semibold">Внешние карты не изменятся.</div>
                  <div>LocalOS создаст новые активные услуги и скроет исходные строки через мягкий архив. Удаления не будет.</div>
                </div>
              </div>
            )
          ) : null}
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-100 bg-slate-50/80 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-pretty text-xs leading-5 text-slate-500">
            Черновик можно применить только вручную. Откат возвращает исходные услуги в активное меню.
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            {draft?.status === 'applied' ? (
              <Button type="button" variant="outline" onClick={rollbackDraft} disabled={pending} className="border-amber-200 bg-white text-amber-800 hover:bg-amber-50">
                Откатить группировку
              </Button>
            ) : null}
            {draft && draft.status !== 'applied' ? (
              <Button type="button" onClick={applyDraft} disabled={pending || activeGroups.length === 0} className="bg-emerald-700 text-white hover:bg-emerald-800">
                {pending ? 'Применяем...' : 'Применить группировку'}
              </Button>
            ) : null}
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
