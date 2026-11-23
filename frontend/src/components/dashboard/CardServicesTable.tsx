import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { CheckCircle2, Edit3, Search, Trash2, Wand2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CardServiceDetail, CardServiceDraft, CardServiceList, CardServiceRow, CardServiceWorkspace } from '@/components/dashboard/CardServiceList';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import type { KeywordMatchLevel, KeywordScore } from '@/components/dashboard/cardServicesLogic';
import { getServiceQuality, serviceProposalStatus } from '@/components/dashboard/cardServicesLogic';
import { ServiceProposalDetail, type SaveServiceProposal, type ServiceProposal } from '@/components/initial-setup/ServiceProposals';

export type ServiceTableItem = {
  id?: string;
  category?: string;
  source?: string;
  is_external?: boolean;
  name?: string;
  optimized_name?: string;
  description?: string;
  optimized_description?: string;
  keywords?: string[] | string;
  price?: string | number;
  updated_at?: string | null;
  fallback_used?: boolean;
  fallback_reason?: string;
  guardrail_reasons?: string[];
  pattern_version_ids?: string[];
  regeneration_status?: string;
  regeneration_attempts?: number;
  setupProposal?: ServiceProposal;
  regeneration_history?: Array<{
    status?: string;
    attempt_no?: number;
    issue_labels_json?: string[];
    after_issue_labels_json?: string[];
    before_optimized_name?: string;
    after_optimized_name?: string;
    error?: string;
    updated_at?: string;
  }>;
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
  demoMode?: boolean;
  tableScrollRef: RefObject<HTMLDivElement | null>;
  copy: ServiceTableCopy;
  services: ServiceTableItem[];
  filteredCount: number;
  loading: boolean;
  saveSetupProposal?: SaveServiceProposal;
  setupProposalDisabled?: boolean;
  setupProposalError?: string;
  servicesSearch: string;
  servicesCategoryFilter: string;
  language: string;
  automationAllowed: boolean;
  automationLockedMessage: string;
  optimizingServiceId: string | null;
  enrichingServiceId: string | null;
  formatServiceSource: (service: ServiceTableItem) => string;
  getOptimizedNameValue: (service: ServiceTableItem) => string;
  getOptimizedDescriptionValue: (service: ServiceTableItem) => string;
  getKeywordScore: (draft: string, service: ServiceTableItem, sourceText?: string) => KeywordScore;
  isDraftSimilarToCurrent: (draft: string, current: string) => boolean;
  getDisplayedServiceUpdatedAt: (service: ServiceTableItem) => string | null | undefined;
  onOptimizedNameDraftChange: (serviceId: string, value: string) => void;
  onOptimizedDescriptionDraftChange: (serviceId: string, value: string) => void;
  onAcceptOptimizedName: (service: ServiceTableItem) => Promise<void>;
  onRejectOptimizedName: (service: ServiceTableItem) => Promise<void>;
  onAcceptOptimizedDescription: (service: ServiceTableItem) => Promise<void>;
  onRejectOptimizedDescription: (service: ServiceTableItem) => Promise<void>;
  onOptimizeService: (serviceId: string) => void;
  onEnrichKeywords: (serviceId: string) => void;
  onEditService: (service: ServiceTableItem) => void;
  onDeleteService: (serviceId: string) => void;
};

type GroupedService = {
  service: ServiceTableItem;
  serviceId: string;
  duplicateCount: number;
};

function getServiceId(service: ServiceTableItem, fallback: number) {
  return service.id || `service-${fallback}`;
}

function normalizeCanonicalText(value: unknown) {
  return String(value || '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getDuplicateKey(service: ServiceTableItem) {
  return [
    normalizeCanonicalText(service.category),
    normalizeCanonicalText(service.name),
    normalizeCanonicalText(service.description),
    normalizeCanonicalText(service.price),
  ].join('|');
}

function getServiceStatus(service: ServiceTableItem) {
  const quality = getServiceQuality(service);
  if (quality.manualReview) {
    return {
      label: 'Нужна проверка',
      className: 'border-rose-200 bg-rose-50 text-rose-700',
      priority: 4,
    };
  }
  if (quality.issueCodes.includes('no_keywords')) {
    return {
      label: 'Без запросов',
      className: 'border-slate-200 bg-slate-50 text-slate-600',
      priority: 3,
    };
  }
  if (quality.issueCodes.includes('fallback_used') || quality.issueCodes.includes('fallback_description')) {
    return {
      label: 'Шаблонное',
      className: 'border-indigo-200 bg-indigo-50 text-indigo-700',
      priority: 2,
    };
  }
  if (quality.needsReview) {
    return {
      label: 'Доработать',
      className: 'border-amber-200 bg-amber-50 text-amber-700',
      priority: 2,
    };
  }
  return {
    label: 'Готово',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    priority: 1,
  };
}

const keywordLevelCopy: Record<KeywordMatchLevel, string> = {
  exact: 'точное',
  normalized: 'словоформа',
  close: 'близкое',
};

const keywordLevelClasses: Record<KeywordMatchLevel, string> = {
  exact: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  normalized: 'border-sky-200 bg-sky-50 text-sky-700',
  close: 'border-amber-200 bg-amber-50 text-amber-700',
};

function KeywordScoreBadges({ score }: { score: KeywordScore }) {
  if (score.total === 0) {
    return (
      <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600">
        запросы не найдены
      </span>
    );
  }

  return (
    <div className="flex flex-wrap gap-1">
      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${score.missingCount > 0 ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
        Найдено {score.found}/{score.total}
      </span>
      {score.matches.slice(0, 4).map((match) => (
        <span
          key={`${match.keyword}-${match.level}`}
          className={`inline-flex max-w-[220px] items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${keywordLevelClasses[match.level]}`}
          title={`${match.keyword}: ${keywordLevelCopy[match.level]}`}
        >
          <span className="truncate">{match.keyword}</span>
          <span className="ml-1 opacity-80">· {keywordLevelCopy[match.level]}</span>
        </span>
      ))}
      {score.missing.length > 0 ? (
        <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600">
          не хватает: {score.missing.slice(0, 2).join(', ')}
        </span>
      ) : null}
    </div>
  );
}

function formatPrice(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return String(value);
  return `${numberValue.toLocaleString('ru-RU')} ₽`;
}

function formatDate(value: string | null | undefined, locale: string) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString(locale, {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getKeywordList(service: ServiceTableItem) {
  if (Array.isArray(service.keywords)) {
    return service.keywords.map((keyword) => String(keyword || '').trim()).filter(Boolean);
  }
  const text = String(service.keywords || '').trim();
  if (!text) return [];
  return text.split(',').map((keyword) => keyword.trim()).filter(Boolean);
}

export function CardServicesTable({
  demoMode = false,
  tableScrollRef,
  copy,
  services,
  filteredCount,
  loading,
  saveSetupProposal,
  setupProposalDisabled = false,
  setupProposalError = '',
  servicesSearch,
  servicesCategoryFilter,
  language,
  automationAllowed,
  automationLockedMessage,
  optimizingServiceId,
  enrichingServiceId,
  formatServiceSource,
  getOptimizedNameValue,
  getOptimizedDescriptionValue,
  getKeywordScore,
  isDraftSimilarToCurrent,
  getDisplayedServiceUpdatedAt,
  onOptimizedNameDraftChange,
  onOptimizedDescriptionDraftChange,
  onAcceptOptimizedName,
  onRejectOptimizedName,
  onAcceptOptimizedDescription,
  onRejectOptimizedDescription,
  onOptimizeService,
  onEnrichKeywords,
  onEditService,
  onDeleteService,
}: CardServicesTableProps) {
  const locale = language === 'ru' ? 'ru-RU' : 'en-US';
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(true);
  const [proposalReviewId, setProposalReviewId] = useState<string | null>(null);
  const proposalDetailId = useId();
  const proposalDetailRef = useRef<HTMLElement | null>(null);
  const selectedRowRef = useRef<HTMLButtonElement | null>(null);
  const activeServiceId = useRef('');

  const groupedServices = useMemo(() => {
    const seen = new Map<string, GroupedService>();
    services.forEach((service, index) => {
      const serviceId = getServiceId(service, index);
      const key = service.setupProposal && !service.setupProposal.service_id ? serviceId : getDuplicateKey(service);
      const existing = seen.get(key);
      if (existing) {
        existing.duplicateCount += 1;
        if (!existing.service.setupProposal && service.setupProposal) {
          existing.service = service;
          existing.serviceId = serviceId;
        }
        return;
      }
      seen.set(key, { service, serviceId, duplicateCount: 1 });
    });
    return Array.from(seen.values());
  }, [services]);

  const selectedGroup = useMemo(() => {
    if (groupedServices.length === 0) return null;
    if (!selectedServiceId) return groupedServices[0];
    return groupedServices.find((item) => item.serviceId === selectedServiceId) || groupedServices[0];
  }, [groupedServices, selectedServiceId]);

  const selectedService = selectedGroup?.service || null;
  const selectedId = selectedGroup?.serviceId || '';
  activeServiceId.current = selectedId;
  const selectedProposal = selectedService?.setupProposal;
  const isNewProposal = Boolean(selectedProposal && !selectedProposal.service_id);
  const reviewingProposal = isDetailOpen && (isNewProposal || selectedId === proposalReviewId);
  const visibleProposal = reviewingProposal ? selectedProposal : undefined;
  const visibleProposalKey = visibleProposal?.key;

  useEffect(() => {
    if (visibleProposalKey && selectedServiceId) proposalDetailRef.current?.focus();
  }, [visibleProposalKey, selectedServiceId]);

  const closeProposal = () => {
    if (activeServiceId.current !== selectedId) return;
    setProposalReviewId(null);
    if (isNewProposal) setIsDetailOpen(false);
    selectedRowRef.current?.focus();
  };
  const selectedQuality = selectedService ? getServiceQuality(selectedService) : null;
  const selectedStatus = selectedService ? getServiceStatus(selectedService) : null;
  const selectedKeywords = selectedService ? getKeywordList(selectedService) : [];
  const selectedOptimizedName = selectedService ? getOptimizedNameValue(selectedService) : '';
  const selectedOptimizedDescription = selectedService ? getOptimizedDescriptionValue(selectedService) : '';
  const selectedNameScore = selectedService ? getKeywordScore(selectedOptimizedName, selectedService, selectedService.name || '') : null;
  const selectedDescriptionScore = selectedService ? getKeywordScore(
    selectedOptimizedDescription,
    selectedService,
    `${selectedService.name || ''} ${selectedService.description || ''}`,
  ) : null;
  const selectedUpdatedAt = selectedService ? getDisplayedServiceUpdatedAt(selectedService) : null;
  const isDetailVisible = isDetailOpen && selectedService && selectedQuality && selectedStatus;

  if (demoMode) {
    return (
      <div ref={tableScrollRef} className="grid gap-4 rounded-3xl border border-slate-200/80 bg-white/90 p-5 shadow-sm md:grid-cols-2">
        {services.map((service, index) => (
          <article key={getServiceId(service, index)} className="rounded-2xl border border-slate-200 bg-white p-5">
            <h3 className="text-lg font-semibold text-slate-950">{service.name}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">{service.description}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {getKeywordList(service).map((keyword) => (
                <span key={keyword} className="rounded-full bg-orange-50 px-3 py-1 text-xs font-medium text-orange-800 ring-1 ring-orange-200">{keyword}</span>
              ))}
            </div>
          </article>
        ))}
      </div>
    );
  }

  return (
    <div ref={tableScrollRef} className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white/90 shadow-sm"
      onKeyDown={event => {
        if (event.key === 'Escape' && visibleProposal) {
          event.stopPropagation();
          closeProposal();
        }
      }}>
      {loading ? (
        <div className="flex items-center justify-center gap-2 px-6 py-14 text-slate-500">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-950" />
          <span>{copy.processing}</span>
        </div>
      ) : filteredCount === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center text-slate-500">
          <div className="rounded-full bg-slate-50 p-3 ring-1 ring-slate-100">
            <Search className="h-8 w-8 text-slate-300" />
          </div>
          <p>{servicesSearch || servicesCategoryFilter !== 'all' ? copy.emptyFiltered : copy.emptyDefault}</p>
        </div>
      ) : (
        <CardServiceWorkspace queue={(
            <CardServiceList
              heading="Очередь услуг"
              description={isDetailOpen ? 'Выберите услугу для проверки' : 'Кликните по услуге, чтобы открыть редактор'}
              count={groupedServices.length}
            >
              {groupedServices.map((item) => {
                const service = item.service;
                const status = service.setupProposal
                  ? serviceProposalStatus({ ...service.setupProposal, has_original: Boolean(service.setupProposal.service_id || service.setupProposal.has_original) })
                  : getServiceStatus(service);
                const isSelected = Boolean(isDetailVisible && selectedId === item.serviceId);
                const isDimmed = Boolean(isDetailVisible && !isSelected);
                const updatedAt = getDisplayedServiceUpdatedAt(service);
                return (
                  <CardServiceRow
                    key={item.serviceId}
                    title={service.name || 'Без названия'}
                    status={status}
                    selected={isSelected}
                    dimmed={isDimmed}
                    buttonRef={selectedId === item.serviceId ? selectedRowRef : undefined}
                    controls={isSelected && visibleProposal ? proposalDetailId : undefined}
                    onClick={() => {
                      setSelectedServiceId(item.serviceId);
                      setIsDetailOpen(true);
                      if (item.serviceId !== selectedId) setProposalReviewId(null);
                      else if (visibleProposal) proposalDetailRef.current?.focus();
                    }}
                    subtitle={(service.category || service.price) ? <>
                      {service.category ? <span className="truncate">{service.category}</span> : null}
                      {service.category && service.price ? <span>·</span> : null}
                      {service.price ? <span>{formatPrice(service.price)}</span> : null}
                    </> : undefined}
                    footer={service.setupProposal && !service.setupProposal.service_id ? undefined : <>
                      <div className="flex min-w-0 items-center gap-1.5">
                        <span className={`truncate rounded-full px-2 py-0.5 ${isSelected ? 'bg-white/10 text-slate-200' : 'bg-slate-100 text-slate-600'}`}>
                          {formatServiceSource(service)}
                        </span>
                        {item.duplicateCount > 1 ? (
                          <span className={`rounded-full px-2 py-0.5 ${isSelected ? 'bg-white/10 text-slate-200' : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'}`}>
                            дубликат ×{item.duplicateCount}
                          </span>
                        ) : null}
                      </div>
                      <span className="shrink-0">{formatDate(updatedAt, locale)}</span>
                    </>}
                  />
                );
              })}
            </CardServiceList>
        )} detail={visibleProposal && selectedService ? (
          <ServiceProposalDetail
            key={JSON.stringify([visibleProposal.key, visibleProposal.proposed, visibleProposal.proposed_description])}
            id={proposalDetailId}
            focusRef={proposalDetailRef}
            item={isNewProposal ? visibleProposal : { ...visibleProposal, has_original: true,
              original: selectedService.name || visibleProposal.original, description: selectedService.description || '' }}
            send={saveSetupProposal}
            disabled={setupProposalDisabled}
            error={setupProposalError}
            onClose={closeProposal}
            backAction={!isNewProposal ? <Button size="sm" variant="ghost" onClick={closeProposal}>К услуге</Button> : undefined}
          />
        ) : isDetailVisible && selectedGroup ? (
          <CardServiceDetail
            title={selectedService.name || 'Без названия'}
            status={selectedStatus}
            badges={<>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {formatServiceSource(selectedService)}
              </span>
              {selectedGroup.duplicateCount > 1 && (
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-amber-200">
                  дубликатов: {selectedGroup.duplicateCount}
                </span>
              )}
            </>}
            metadata={<>
              {selectedService.category && <span>{selectedService.category}</span>}
              {selectedService.price ? <span>{formatPrice(selectedService.price)}</span> : null}
              {selectedUpdatedAt && <span>Обновлено {formatDate(selectedUpdatedAt, locale)}</span>}
            </>}
            description={selectedService.description || 'Описание пока не заполнено.'}
            keywords={selectedKeywords}
            onClose={() => setIsDetailOpen(false)}
            actions={<>
                    {selectedProposal && <Button size="sm" onClick={() => setProposalReviewId(selectedId)}>
                      Проверить предложение
                    </Button>}
                    <Button
                      onClick={() => onOptimizeService(selectedId)}
                      disabled={!automationAllowed || optimizingServiceId === selectedId || selectedQuality.manualReview}
                      size="sm"
                      variant={selectedProposal ? 'outline' : 'default'}
                      className={selectedProposal ? 'h-9' : 'h-9 bg-slate-950 text-white hover:bg-slate-800'}
                      title={selectedQuality.manualReview ? 'Нужна ручная проверка' : !automationAllowed ? automationLockedMessage : copy.optimize}
                    >
                      {optimizingServiceId === selectedId ? (
                        <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white/60 border-t-white" />
                      ) : (
                        <Wand2 className="mr-2 h-4 w-4" />
                      )}
                      {copy.optimize}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => onEditService(selectedService)} className="h-9 border-slate-200 text-slate-700">
                      <Edit3 className="mr-2 h-4 w-4" />
                      {copy.edit}
                    </Button>
                    <TooltipProvider delayDuration={180}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => onEnrichKeywords(selectedId)}
                              disabled={enrichingServiceId === selectedId}
                              className="h-9 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                            >
                              {enrichingServiceId === selectedId ? (
                                <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
                              ) : (
                                <Search className="mr-2 h-4 w-4" />
                              )}
                              Подобрать SEO-запросы
                            </Button>
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="max-w-xs text-xs leading-5">
                          Найдёт безопасные Wordstat-запросы для этой услуги и сохранит их в блок «Запросы для поиска». Карточки на картах не меняет.
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <Button size="sm" variant="ghost" onClick={() => onDeleteService(selectedId)} className="h-9 text-slate-400 hover:bg-red-50 hover:text-red-600">
                      <Trash2 className="h-4 w-4" />
                    </Button>
            </>}
          >
                <div className="space-y-3">
                  <CardServiceDraft title="Предложенное название">
                    {selectedService.optimized_name ? (
                      <>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {isDraftSimilarToCurrent(selectedOptimizedName, selectedService.name || '') ? (
                            <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                              похоже на текущее
                            </span>
                          ) : null}
                          {selectedNameScore ? <KeywordScoreBadges score={selectedNameScore} /> : null}
                        </div>
                        <textarea
                          value={selectedOptimizedName}
                          onChange={(event) => onOptimizedNameDraftChange(selectedId, event.target.value)}
                          className="mt-2 min-h-[52px] w-full rounded-xl border border-slate-200 bg-slate-50/60 px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-300 focus:bg-white focus:ring-2 focus:ring-slate-200"
                        />
                        <div className="mt-2 flex gap-2">
                          <Button size="sm" onClick={() => void onAcceptOptimizedName(selectedService)} className="bg-slate-950 text-white hover:bg-slate-800">
                            <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                            {copy.accept}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => void onRejectOptimizedName(selectedService)} className="text-slate-500 hover:bg-slate-100">
                            {copy.reject}
                          </Button>
                        </div>
                      </>
                    ) : (
                      <p className="mt-3 text-sm leading-6 text-slate-500">SEO-вариант появится после оптимизации.</p>
                    )}
                  </CardServiceDraft>

                  {selectedQuality.needsReview || selectedQuality.manualReview ? (
                    <div className="rounded-2xl border border-amber-200/80 bg-amber-50/80 p-3">
                      <div className="text-sm font-semibold text-amber-900">Что требует внимания</div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedQuality.issueLabels.slice(0, 5).map((label) => (
                          <span key={label} className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
                            {label}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <CardServiceDraft title="Предложенное описание">
                    {selectedService.optimized_description ? (
                      <>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {isDraftSimilarToCurrent(selectedOptimizedDescription, selectedService.description || '') ? (
                            <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                              похоже на текущее
                            </span>
                          ) : null}
                          {selectedDescriptionScore ? <KeywordScoreBadges score={selectedDescriptionScore} /> : null}
                        </div>
                        <textarea
                          value={selectedOptimizedDescription}
                          onChange={(event) => onOptimizedDescriptionDraftChange(selectedId, event.target.value)}
                          className="mt-2 min-h-[104px] w-full rounded-xl border border-slate-200 bg-slate-50/60 px-3 py-2 text-sm leading-6 text-slate-900 outline-none transition focus:border-slate-300 focus:bg-white focus:ring-2 focus:ring-slate-200"
                        />
                        <div className="mt-2 flex gap-2">
                          <Button size="sm" onClick={() => void onAcceptOptimizedDescription(selectedService)} className="bg-slate-950 text-white hover:bg-slate-800">
                            <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                            {copy.accept}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => void onRejectOptimizedDescription(selectedService)} className="text-slate-500 hover:bg-slate-100">
                            {copy.reject}
                          </Button>
                        </div>
                      </>
                    ) : (
                      <p className="mt-3 text-sm leading-6 text-slate-500">Описание появится после оптимизации выбранной услуги.</p>
                    )}
                  </CardServiceDraft>
                </div>
          </CardServiceDetail>
        ) : null} />
      )}
    </div>
  );
}
