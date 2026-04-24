import type { RefObject } from 'react';
import { CheckCircle2, Edit3, Search, Sparkles, Trash2, Wand2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StickyBottomHorizontalScrollbar } from '@/components/ui/sticky-bottom-horizontal-scrollbar';

export type ServiceTableItem = {
  id?: string;
  category?: string;
  source?: string;
  name?: string;
  optimized_name?: string;
  description?: string;
  optimized_description?: string;
  keywords?: string[] | string;
  price?: string | number;
  updated_at?: string | null;
};

type ServiceTableCopy = {
  category: string;
  source: string;
  name: string;
  description: string;
  price: string;
  updated: string;
  actions: string;
  processing: string;
  emptyFiltered: string;
  emptyDefault: string;
  proposal: string;
  accept: string;
  reject: string;
  optimize: string;
  edit: string;
};

type CardServicesTableProps = {
  tableScrollRef: RefObject<HTMLDivElement | null>;
  copy: ServiceTableCopy;
  services: ServiceTableItem[];
  filteredCount: number;
  loading: boolean;
  servicesSearch: string;
  servicesCategoryFilter: string;
  language: string;
  automationAllowed: boolean;
  automationLockedMessage: string;
  optimizingServiceId: string | null;
  formatServiceSource: (service: ServiceTableItem) => string;
  getOptimizedNameValue: (service: ServiceTableItem) => string;
  getOptimizedDescriptionValue: (service: ServiceTableItem) => string;
  getMatchedKeywords: (draft: string, service: ServiceTableItem) => string[];
  isDraftSimilarToCurrent: (draft: string, current: string) => boolean;
  getDisplayedServiceUpdatedAt: (service: ServiceTableItem) => string | null | undefined;
  onOptimizedNameDraftChange: (serviceId: string, value: string) => void;
  onOptimizedDescriptionDraftChange: (serviceId: string, value: string) => void;
  onAcceptOptimizedName: (service: ServiceTableItem) => Promise<void>;
  onRejectOptimizedName: (service: ServiceTableItem) => Promise<void>;
  onAcceptOptimizedDescription: (service: ServiceTableItem) => Promise<void>;
  onRejectOptimizedDescription: (service: ServiceTableItem) => Promise<void>;
  onOptimizeService: (serviceId: string) => void;
  onEditService: (service: ServiceTableItem) => void;
  onDeleteService: (serviceId: string) => void;
};

function getServiceId(service: ServiceTableItem, fallback: number) {
  return service.id || `service-${fallback}`;
}

export function CardServicesTable({
  tableScrollRef,
  copy,
  services,
  filteredCount,
  loading,
  servicesSearch,
  servicesCategoryFilter,
  language,
  automationAllowed,
  automationLockedMessage,
  optimizingServiceId,
  formatServiceSource,
  getOptimizedNameValue,
  getOptimizedDescriptionValue,
  getMatchedKeywords,
  isDraftSimilarToCurrent,
  getDisplayedServiceUpdatedAt,
  onOptimizedNameDraftChange,
  onOptimizedDescriptionDraftChange,
  onAcceptOptimizedName,
  onRejectOptimizedName,
  onAcceptOptimizedDescription,
  onRejectOptimizedDescription,
  onOptimizeService,
  onEditService,
  onDeleteService,
}: CardServicesTableProps) {
  const locale = language === 'ru' ? 'ru-RU' : 'en-US';

  return (
    <div className="rounded-xl border border-slate-100">
      <div
        ref={tableScrollRef}
        className="overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        <table className="min-w-[1320px] w-full divide-y divide-slate-100">
          <thead className="bg-slate-50/70">
            <tr>
              <th scope="col" className="w-[150px] px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                {copy.category}
              </th>
              <th scope="col" className="w-[150px] px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                {copy.source}
              </th>
              <th scope="col" className="w-[200px] px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                {copy.name}
              </th>
              <th scope="col" className="min-w-[300px] px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                {copy.description}
              </th>
              <th scope="col" className="w-[120px] px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                {copy.price}
              </th>
              <th scope="col" className="w-[120px] px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">
                {copy.updated}
              </th>
              <th scope="col" className="w-[132px] min-w-[132px] px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">
                {copy.actions}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {loading ? (
              <tr>
                <td className="px-6 py-8 text-center" colSpan={7}>
                  <div className="flex items-center justify-center gap-2 text-slate-500">
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
                    <span>{copy.processing}</span>
                  </div>
                </td>
              </tr>
            ) : filteredCount === 0 ? (
              <tr>
                <td className="px-6 py-12 text-center text-slate-500" colSpan={7}>
                  <div className="flex flex-col items-center justify-center gap-3">
                    <div className="rounded-full bg-slate-50 p-3">
                      <Search className="h-8 w-8 text-slate-300" />
                    </div>
                    <p>{servicesSearch || servicesCategoryFilter !== 'all' ? copy.emptyFiltered : copy.emptyDefault}</p>
                  </div>
                </td>
              </tr>
            ) : (
              services.map((service, index) => {
                const serviceId = getServiceId(service, index);
                const optimizedName = getOptimizedNameValue(service);
                const optimizedDescription = getOptimizedDescriptionValue(service);
                const displayedUpdatedAt = getDisplayedServiceUpdatedAt(service);

                return (
                  <tr key={serviceId} className="group transition-colors hover:bg-slate-50/60">
                    <td className="whitespace-nowrap px-6 py-4 align-top text-sm font-medium text-slate-500">
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-800">
                        {service.category}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 align-top text-sm text-slate-500">
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                        {formatServiceSource(service)}
                      </span>
                    </td>
                    <td className="max-w-[250px] px-6 py-4 align-top text-sm text-slate-900">
                      <div className="space-y-3">
                        {service.name ? <div className="font-semibold">{service.name}</div> : null}
                        {service.optimized_name ? (
                          <div className="mt-2 animate-in fade-in space-y-2 rounded-lg border border-indigo-100 bg-indigo-50/80 p-3">
                            <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-indigo-600">
                              <Sparkles className="h-3 w-3" />
                              {copy.proposal}
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {isDraftSimilarToCurrent(optimizedName, service.name || '') ? (
                                <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                                  Похоже на текущее название
                                </span>
                              ) : null}
                              {getMatchedKeywords(optimizedName, service).length > 0 ? (
                                <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                                  SEO-ключи: {getMatchedKeywords(optimizedName, service).slice(0, 3).join(', ')}
                                </span>
                              ) : (
                                <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                                  SEO-ключи не найдены
                                </span>
                              )}
                            </div>
                            <textarea
                              value={optimizedName}
                              onChange={(event) => onOptimizedNameDraftChange(serviceId, event.target.value)}
                              className="min-h-[80px] w-full rounded-md border border-indigo-200 bg-white px-2 py-1 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                            />
                            <div className="flex gap-2 pt-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void onAcceptOptimizedName(service)}
                                className="h-6 border border-indigo-200 bg-white text-xs text-indigo-600 hover:bg-indigo-50 hover:text-indigo-700"
                              >
                                <CheckCircle2 className="mr-1 h-3 w-3" />
                                {copy.accept}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void onRejectOptimizedName(service)}
                                className="h-6 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                              >
                                {copy.reject}
                              </Button>
                            </div>
                          </div>
                        ) : null}
                        {!service.name && !service.optimized_name ? <span className="italic text-slate-300">—</span> : null}
                      </div>
                    </td>
                    <td className="max-w-[350px] px-6 py-4 align-top text-sm text-slate-600">
                      <div className="space-y-3">
                        {service.description ? <div className="leading-relaxed">{service.description}</div> : null}
                        {service.optimized_description ? (
                          <div className="mt-2 animate-in fade-in space-y-2 rounded-lg border border-indigo-100 bg-indigo-50/80 p-3">
                            <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-indigo-600">
                              <Sparkles className="h-3 w-3" />
                              {copy.proposal}
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {isDraftSimilarToCurrent(optimizedDescription, service.description || '') ? (
                                <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                                  Похоже на текущее описание
                                </span>
                              ) : null}
                              {getMatchedKeywords(optimizedDescription, service).length > 0 ? (
                                <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                                  SEO-ключи: {getMatchedKeywords(optimizedDescription, service).slice(0, 3).join(', ')}
                                </span>
                              ) : (
                                <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                                  SEO-ключи не найдены
                                </span>
                              )}
                            </div>
                            <textarea
                              value={optimizedDescription}
                              onChange={(event) => onOptimizedDescriptionDraftChange(serviceId, event.target.value)}
                              className="min-h-[120px] w-full rounded-md border border-indigo-200 bg-white px-2 py-1 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                            />
                            <div className="flex gap-2 pt-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void onAcceptOptimizedDescription(service)}
                                className="h-6 border border-indigo-200 bg-white text-xs text-indigo-600 hover:bg-indigo-50 hover:text-indigo-700"
                              >
                                <CheckCircle2 className="mr-1 h-3 w-3" />
                                {copy.accept}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void onRejectOptimizedDescription(service)}
                                className="h-6 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                              >
                                {copy.reject}
                              </Button>
                            </div>
                          </div>
                        ) : null}
                        {!service.description && !service.optimized_description ? <span className="italic text-slate-300">—</span> : null}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 align-top text-sm font-medium text-slate-900">
                      {service.price ? `${Number(service.price).toLocaleString('ru-RU')} ₽` : '—'}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right align-top text-sm text-slate-500">
                      {displayedUpdatedAt ? new Date(displayedUpdatedAt).toLocaleDateString(locale, {
                        day: '2-digit',
                        month: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      }) : '—'}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right align-top text-sm text-slate-500">
                      <div className="inline-flex min-w-[108px] items-center justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => onOptimizeService(serviceId)}
                          disabled={!automationAllowed || optimizingServiceId === serviceId}
                          className="h-8 w-8 text-indigo-600 hover:bg-indigo-50 hover:text-indigo-700"
                          title={!automationAllowed ? automationLockedMessage : copy.optimize}
                        >
                          {optimizingServiceId === serviceId ? (
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
                          ) : (
                            <Wand2 className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => onEditService(service)}
                          className="h-8 w-8 text-slate-500 hover:bg-blue-50 hover:text-blue-700"
                          title={copy.edit}
                        >
                          <Edit3 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => onDeleteService(serviceId)}
                          className="h-8 w-8 text-slate-400 hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <StickyBottomHorizontalScrollbar targetRef={tableScrollRef} />
    </div>
  );
}
