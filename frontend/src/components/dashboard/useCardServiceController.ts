import { useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { ServiceTableItem } from '@/components/dashboard/CardServicesTable';
import {
  createCardService,
  enrichProblematicServiceKeywords,
  enrichServiceKeywords,
  loadProblematicServicesRegenerationJob,
  optimizeCardService,
  removeCardService,
  startProblematicServicesRegeneration,
  updateCardService,
} from '@/components/dashboard/cardOverviewApi';
import { getServiceQuality } from '@/components/dashboard/cardServicesLogic';

type ServiceFormValue = {
  category: string;
  name: string;
  description: string;
  keywords: string;
  price: string;
};

type CardServiceControllerArgs = {
  userServices: ServiceTableItem[];
  setUserServices: Dispatch<SetStateAction<any[]>>;
  currentBusinessId?: string;
  automationAllowed: boolean;
  automationLockedMessage: string;
  loadUserServices: () => Promise<void>;
  setError: (value: string | null) => void;
  setSuccess: (value: string | null) => void;
  copy: {
    serviceName: string;
    deleteConfirm: string;
    success: string;
    error: string;
    accepted: string;
    rejected: string;
  };
};

const emptyServiceForm: ServiceFormValue = {
  category: '',
  name: '',
  description: '',
  keywords: '',
  price: '',
};

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const normalizeKeywords = (keywords: ServiceTableItem['keywords']) => {
  if (Array.isArray(keywords)) {
    return keywords.map((keyword) => {
      if (typeof keyword === 'string') {
        try {
          const parsed = JSON.parse(keyword);
          return Array.isArray(parsed) ? parsed : [keyword];
        } catch {
          return [keyword];
        }
      }
      return Array.isArray(keyword) ? keyword : [keyword];
    }).flat();
  }
  if (keywords) {
    return typeof keywords === 'string' ? [keywords] : [];
  }
  return [];
};

const serviceNeedsRegeneration = (service: ServiceTableItem) => {
  return getServiceQuality(service).needsReview;
};

const buildRegenerationInstructions = (service: ServiceTableItem) => {
  const quality = getServiceQuality(service);
  const instructions = [
    'Сохрани смысл исходной услуги и исправь только проблему качества SEO-предложения.',
  ];
  if (quality.keywordScore.missing.length > 0) {
    instructions.push(`Сохрани SEO-ключи: ${quality.keywordScore.missing.slice(0, 5).join(', ')}.`);
  }
  if (quality.issueCodes.includes('weak_matches_only')) {
    instructions.push('Замени слабое близкое совпадение на более точное вхождение ключа без потери смысла.');
  }
  if (quality.issueCodes.includes('fallback_used') || quality.issueCodes.includes('fallback_description')) {
    instructions.push('Не возвращай шаблонное описание; сделай короткое точное описание в одно предложение.');
  }
  if (quality.issueCodes.includes('guardrail_reasons')) {
    instructions.push('Не добавляй неподтвержденные обещания, зоны, препараты, объемы или аудиторию.');
  }
  if (quality.issueCodes.includes('name_unchanged')) {
    instructions.push('Улучшить название можно только за счет релевантного ключа и сохраненных атрибутов.');
  }
  return instructions.join(' ');
};

export function useCardServiceController({
  userServices,
  setUserServices,
  currentBusinessId,
  automationAllowed,
  automationLockedMessage,
  loadUserServices,
  setError,
  setSuccess,
  copy,
}: CardServiceControllerArgs) {
  const [showAddService, setShowAddService] = useState(false);
  const [editingService, setEditingService] = useState<string | null>(null);
  const [newService, setNewService] = useState<ServiceFormValue>(emptyServiceForm);
  const [editServiceForm, setEditServiceForm] = useState<ServiceFormValue>(emptyServiceForm);
  const [optimizingServiceId, setOptimizingServiceId] = useState<string | null>(null);
  const [enrichingServiceId, setEnrichingServiceId] = useState<string | null>(null);
  const [optimizingAll, setOptimizingAll] = useState(false);
  const [enrichingProblematic, setEnrichingProblematic] = useState(false);
  const [regeneratingProblematic, setRegeneratingProblematic] = useState(false);
  const [problemRegenerationStatus, setProblemRegenerationStatus] = useState<string | null>(null);
  const [optimizedNameDrafts, setOptimizedNameDrafts] = useState<Record<string, string>>({});
  const [optimizedDescriptionDrafts, setOptimizedDescriptionDrafts] = useState<Record<string, string>>({});

  const patchServiceInState = (serviceId: string, patch: Record<string, any>) => {
    const nowIso = new Date().toISOString();
    setUserServices((prev) =>
      prev.map((item) => (
        item.id === serviceId
          ? {
              ...item,
              ...patch,
              updated_at: nowIso,
            }
          : item
      ))
    );
  };

  const resolvedQualityPatch = {
    fallback_used: false,
    fallback_reason: '',
    guardrail_reasons: [],
    pattern_version_ids: [],
    regeneration_status: '',
    regeneration_history: [],
  };

  const updateService = async (
    serviceId: string,
    updatedData: Record<string, any>,
    options?: { reload?: boolean; showSuccess?: boolean }
  ) => {
    const { response, data } = await updateCardService(serviceId, updatedData);

    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
    }

    if (!data.success) {
      throw new Error(data.error || copy.error);
    }

    setEditingService(null);
    if (options?.reload !== false) {
      await loadUserServices();
    }
    if (options?.showSuccess !== false) {
      setSuccess(copy.success);
    }
  };

  const addService = async () => {
    if (!newService.name.trim()) {
      setError(`${copy.serviceName} required`);
      return;
    }

    try {
      const { data } = await createCardService({
        category: newService.category || 'Общие услуги',
        name: newService.name,
        description: newService.description,
        keywords: newService.keywords.split(',').map((keyword) => keyword.trim()).filter(Boolean),
        price: newService.price,
        business_id: currentBusinessId,
      });
      if (data.success) {
        setNewService(emptyServiceForm);
        setShowAddService(false);
        await loadUserServices();
        setSuccess(copy.success);
      } else {
        setError(data.error || copy.error);
      }
    } catch (error: any) {
      setError(`${copy.error}: ${error.message}`);
    }
  };

  const optimizeService = async (
    serviceId: string,
    options?: { silent?: boolean }
  ): Promise<'ok' | 'rate_limited' | 'error'> => {
    if (!automationAllowed) {
      if (!options?.silent) setError(automationLockedMessage);
      return 'error';
    }

    const service = userServices.find((item) => item.id === serviceId);
    if (!service) return 'error';

    setOptimizingServiceId(serviceId);
    if (!options?.silent) setError(null);

    try {
      const { response, data } = await optimizeCardService({
        text: String(service.name || '') + (service.description ? `\n${service.description}` : ''),
        business_id: currentBusinessId,
        service_category: service.category || '',
        instructions: buildRegenerationInstructions(service),
      });
      const errorText = String(data?.error || '');
      const isRateLimited =
        response.status === 429 ||
        errorText.includes('429') ||
        errorText.toLowerCase().includes('rate limit');

      if (data.success && data.result?.services?.length > 0) {
        const optimized = data.result.services[0];
        const updateData = {
          category: service.category || '',
          name: service.name || '',
          optimized_name: String(optimized.optimized_name || optimized.optimizedName || '').trim(),
          description: service.description || '',
          optimized_description: String(optimized.seo_description || optimized.seoDescription || '').trim(),
          keywords: normalizeKeywords(service.keywords),
          price: service.price || '',
          fallback_used: Boolean(optimized.fallback_used),
          fallback_reason: String(optimized.fallback_reason || '').trim(),
          guardrail_reasons: Array.isArray(optimized.guardrail_reasons) ? optimized.guardrail_reasons : [],
          pattern_version_ids: Array.isArray(optimized.pattern_version_ids) ? optimized.pattern_version_ids : [],
        };
        const statePatch = {
          ...updateData,
        };

        try {
          await updateService(serviceId, updateData, { reload: false, showSuccess: false });
          patchServiceInState(serviceId, statePatch);
          if (!options?.silent) setSuccess(copy.success);
          return 'ok';
        } catch {
          if (!options?.silent) setError(copy.error);
          return 'error';
        }
      }

      if (!options?.silent) setError(data.error || copy.error);
      return isRateLimited ? 'rate_limited' : 'error';
    } catch (error: any) {
      const text = String(error?.message || '');
      const isRateLimited = text.includes('429') || text.toLowerCase().includes('rate limit');
      if (!options?.silent) setError(`${copy.error}: ${text}`);
      return isRateLimited ? 'rate_limited' : 'error';
    } finally {
      setOptimizingServiceId(null);
    }
  };

  const optimizeAllServices = async () => {
    if (!userServices.length) return;
    if (!automationAllowed) {
      setError(automationLockedMessage);
      return;
    }

    setOptimizingAll(true);
    setError(null);
    setSuccess(null);

    let okCount = 0;
    let errorCount = 0;
    let rateLimitedCount = 0;

    for (const service of userServices) {
      const serviceId = service.id;
      if (!serviceId) continue;
      const result = await optimizeService(serviceId, { silent: true });
      if (result === 'ok') {
        okCount += 1;
        await sleep(1200);
        continue;
      }
      if (result === 'rate_limited') {
        rateLimitedCount += 1;
        await sleep(20000);
      } else {
        errorCount += 1;
        await sleep(1200);
      }
    }

    if (okCount > 0 && rateLimitedCount === 0 && errorCount === 0) {
      setSuccess(`Оптимизировано услуг: ${okCount}`);
    } else if (okCount > 0) {
      setError(`Оптимизировано: ${okCount}. Ошибок: ${errorCount}. Лимит GigaChat (429): ${rateLimitedCount}.`);
    } else {
      setError(`Оптимизация не выполнена. Ошибок: ${errorCount}. Лимит GigaChat (429): ${rateLimitedCount}.`);
    }

    setOptimizingAll(false);
  };

  const regenerateProblematicServices = async () => {
    if (!userServices.length) return;
    if (!automationAllowed) {
      setError(automationLockedMessage);
      return;
    }
    if (!currentBusinessId) {
      setError('Не выбран бизнес для повторной генерации');
      return;
    }

    setRegeneratingProblematic(true);
    setError(null);
    setSuccess(null);
    setProblemRegenerationStatus('Ищем до 10 услуг, которые стоит переписать сильнее');

    const targetServices = userServices.filter(serviceNeedsRegeneration);
    if (targetServices.length === 0) {
      setSuccess('Нет плохих предложений для повторной генерации');
      setProblemRegenerationStatus(null);
      setRegeneratingProblematic(false);
      return;
    }

    try {
      const { response, data } = await startProblematicServicesRegeneration({
        business_id: currentBusinessId,
        limit: 10,
        requested_by: 'ui',
      });

      if (!response.ok || !data.success || !data.job?.id) {
        throw new Error(data.error || copy.error);
      }

      let latestJob = data.job;
      if (String(latestJob.status || '') === 'awaiting_confirmation') {
        const ok = window.confirm(
          `Найдено проблемных услуг: ${latestJob.total_problem_count || targetServices.length}. Запустить перегенерацию до ${latestJob.limit || 10} услуг?`
        );
        if (!ok) {
          setProblemRegenerationStatus(null);
          setRegeneratingProblematic(false);
          return;
        }
        const confirmed = await startProblematicServicesRegeneration({
          business_id: currentBusinessId,
          job_id: String(latestJob.id),
          limit: 10,
          confirm: true,
          requested_by: 'ui',
        });
        if (!confirmed.response.ok || !confirmed.data.success || !confirmed.data.job?.id) {
          throw new Error(confirmed.data.error || copy.error);
        }
        latestJob = confirmed.data.job;
      }
      setProblemRegenerationStatus(latestJob.message || 'Job запущен');

      for (let attempt = 0; attempt < 60; attempt += 1) {
        if (['completed', 'rate_limited', 'failed', 'cancelled'].includes(String(latestJob.status || ''))) {
          break;
        }
        await sleep(3000);
        const statusResult = await loadProblematicServicesRegenerationJob(String(latestJob.id));
        if (statusResult.response.ok && statusResult.data.success) {
          latestJob = statusResult.data.job;
          const processedCount = Array.isArray(latestJob.processed) ? latestJob.processed.length : 0;
          setProblemRegenerationStatus(`Job ${latestJob.status}: обработано ${processedCount}/${latestJob.selected || 0}`);
        }
      }

      await loadUserServices();

      const fixed = Number(latestJob.fixed || 0);
      const failed = Number(latestJob.failed || 0);
      const manual = Number(latestJob.manual_review || 0);
      const remaining = latestJob.remaining ?? 'неизвестно';
      if (latestJob.status === 'rate_limited') {
        const cooldown = latestJob.cooldown_until ? ` Пауза до ${new Date(latestJob.cooldown_until).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}.` : '';
        setError(`Остановлено из-за лимита GigaChat. Исправлено: ${fixed}. Осталось: ${remaining}.${cooldown}`);
      } else if (failed > 0 || manual > 0) {
        setError(`Исправлено: ${fixed}. Ошибок: ${failed}. Ручная проверка: ${manual}. Осталось: ${remaining}.`);
      } else {
        setSuccess(`Повторно оптимизировано: ${fixed}. Осталось проблемных: ${remaining}.`);
      }
      setProblemRegenerationStatus(null);
    } catch (error: any) {
      setError(`${copy.error}: ${error.message}`);
      setProblemRegenerationStatus(null);
    }
    setRegeneratingProblematic(false);
  };

  const enrichKeywordsForService = async (serviceId: string) => {
    if (!serviceId) return;
    setEnrichingServiceId(serviceId);
    setError(null);
    setSuccess(null);
    try {
      const { response, data } = await enrichServiceKeywords({ service_id: serviceId, limit: 8 });
      if (!response.ok || !data.success) {
        throw new Error(data.error || copy.error);
      }
      await loadUserServices();
      const enrichment = data.enrichment || {};
      if (data.saved) {
        setSuccess(`Запросы найдены и сохранены: ${(enrichment.keywords || []).slice(0, 3).join(', ')}`);
      } else if (enrichment.status === 'blocked') {
        setError('Безопасные запросы не сохранены: найденные варианты не подошли по смыслу.');
      } else {
        setError('Безопасные запросы не найдены. Нужна ручная проверка.');
      }
    } catch (error: any) {
      setError(`${copy.error}: ${error.message}`);
    } finally {
      setEnrichingServiceId(null);
    }
  };

  const enrichProblematicKeywords = async () => {
    if (!currentBusinessId) {
      setError('Не выбран бизнес для поиска запросов');
      return;
    }
    setEnrichingProblematic(true);
    setError(null);
    setSuccess(null);
    try {
      const { response, data } = await enrichProblematicServiceKeywords({ business_id: currentBusinessId, limit: 10 });
      if (!response.ok || !data.success) {
        throw new Error(data.error || copy.error);
      }
      await loadUserServices();
      if (Number(data.saved || 0) > 0) {
        setSuccess(`Запросы найдены для услуг: ${data.saved}`);
      } else {
        setError('Безопасные запросы автоматически не найдены. Проверьте спорные услуги вручную.');
      }
    } catch (error: any) {
      setError(`${copy.error}: ${error.message}`);
    } finally {
      setEnrichingProblematic(false);
    }
  };

  const deleteService = async (serviceId: string) => {
    if (!window.confirm(copy.deleteConfirm)) return;

    try {
      const { data } = await removeCardService(serviceId);
      if (data.success) {
        await loadUserServices();
        setSuccess(copy.success);
      } else {
        setError(data.error || copy.error);
      }
    } catch (error: any) {
      setError(`${copy.error}: ${error.message}`);
    }
  };

  const openEditService = (service: ServiceTableItem) => {
    setEditingService(service.id || null);
    setEditServiceForm({
      category: service.category || '',
      name: service.name || '',
      description: service.description || '',
      keywords: Array.isArray(service.keywords) ? service.keywords.join(', ') : String(service.keywords || ''),
      price: service.price ? String(service.price) : '',
    });
  };

  const saveEditedService = async () => {
    if (!editingService) return;
    const original = userServices.find((service) => service.id === editingService);
    if (!original) return;
    const nameChanged = editServiceForm.name.trim() !== String(original.name || '').trim();
    const descriptionChanged = editServiceForm.description.trim() !== String(original.description || '').trim();
    const manualTextChanged = nameChanged || descriptionChanged;
    await updateService(editingService, {
      category: editServiceForm.category || '',
      name: editServiceForm.name || '',
      description: editServiceForm.description || '',
      keywords: editServiceForm.keywords.split(',').map((keyword) => keyword.trim()).filter(Boolean),
      price: editServiceForm.price || '',
      optimized_name: manualTextChanged ? '' : original.optimized_name || '',
      optimized_description: manualTextChanged ? '' : original.optimized_description || '',
      ...resolvedQualityPatch,
    });
    setEditingService(null);
  };

  const getOptimizedNameValue = (service: ServiceTableItem) => {
    if (!service.id) return service.optimized_name || '';
    if (optimizedNameDrafts[service.id] !== undefined) return optimizedNameDrafts[service.id];
    return service.optimized_name || '';
  };

  const getOptimizedDescriptionValue = (service: ServiceTableItem) => {
    if (!service.id) return service.optimized_description || '';
    if (optimizedDescriptionDrafts[service.id] !== undefined) return optimizedDescriptionDrafts[service.id];
    return service.optimized_description || '';
  };

  const acceptOptimizedServiceName = async (service: ServiceTableItem) => {
    const serviceId = service.id;
    if (!serviceId) return;
    const acceptedOptimizedName = getOptimizedNameValue(service).trim();
    const payload = {
      category: service.category,
      name: acceptedOptimizedName || service.optimized_name,
      optimized_name: '',
      description: service.description,
      optimized_description: service.optimized_description,
      keywords: service.keywords,
      price: service.price,
      ...resolvedQualityPatch,
    };
    await updateService(serviceId, payload, { reload: false, showSuccess: false });
    patchServiceInState(serviceId, payload);
    setOptimizedNameDrafts((prev) => {
      const next = { ...prev };
      delete next[serviceId];
      return next;
    });
    setSuccess(copy.accepted);
  };

  const rejectOptimizedServiceName = async (service: ServiceTableItem) => {
    const serviceId = service.id;
    if (!serviceId) return;
    const payload = {
      category: service.category,
      name: service.name,
      optimized_name: '',
      description: service.description,
      optimized_description: service.optimized_description,
      keywords: service.keywords,
      price: service.price,
      ...resolvedQualityPatch,
    };
    await updateService(serviceId, payload, { reload: false, showSuccess: false });
    patchServiceInState(serviceId, payload);
    setOptimizedNameDrafts((prev) => {
      const next = { ...prev };
      delete next[serviceId];
      return next;
    });
    setSuccess(copy.rejected);
  };

  const acceptOptimizedServiceDescription = async (service: ServiceTableItem) => {
    const serviceId = service.id;
    if (!serviceId) return;
    const acceptedOptimizedDescription = getOptimizedDescriptionValue(service).trim();
    const payload = {
      category: service.category,
      name: service.name,
      description: acceptedOptimizedDescription || service.optimized_description,
      optimized_description: '',
      keywords: service.keywords,
      price: service.price,
      ...resolvedQualityPatch,
    };
    await updateService(serviceId, payload, { reload: false, showSuccess: false });
    patchServiceInState(serviceId, payload);
    setOptimizedDescriptionDrafts((prev) => {
      const next = { ...prev };
      delete next[serviceId];
      return next;
    });
    setSuccess(copy.accepted);
  };

  const rejectOptimizedServiceDescription = async (service: ServiceTableItem) => {
    const serviceId = service.id;
    if (!serviceId) return;
    const payload = {
      category: service.category,
      name: service.name,
      description: service.description,
      optimized_description: '',
      keywords: service.keywords,
      price: service.price,
      ...resolvedQualityPatch,
    };
    await updateService(serviceId, payload, { reload: false, showSuccess: false });
    patchServiceInState(serviceId, payload);
    setOptimizedDescriptionDrafts((prev) => {
      const next = { ...prev };
      delete next[serviceId];
      return next;
    });
    setSuccess(copy.rejected);
  };

  return {
    showAddService,
    setShowAddService,
    editingService,
    setEditingService,
    newService,
    setNewService,
    editServiceForm,
    setEditServiceForm,
    optimizingServiceId,
    enrichingServiceId,
    optimizingAll,
    enrichingProblematic,
    regeneratingProblematic,
    problemRegenerationStatus,
    addService,
    optimizeService,
    optimizeAllServices,
    regenerateProblematicServices,
    enrichKeywordsForService,
    enrichProblematicKeywords,
    getOptimizedNameValue,
    getOptimizedDescriptionValue,
    setOptimizedNameDrafts,
    setOptimizedDescriptionDrafts,
    acceptOptimizedServiceName,
    rejectOptimizedServiceName,
    acceptOptimizedServiceDescription,
    rejectOptimizedServiceDescription,
    openEditService,
    saveEditedService,
    deleteService,
  };
}
