import { useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { ServiceTableItem } from '@/components/dashboard/CardServicesTable';
import {
  createCardService,
  optimizeCardService,
  removeCardService,
  updateCardService,
} from '@/components/dashboard/cardOverviewApi';

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
  const [optimizingAll, setOptimizingAll] = useState(false);
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
        };

        try {
          await updateService(serviceId, updateData, { reload: false, showSuccess: false });
          patchServiceInState(serviceId, updateData);
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
    await updateService(editingService, {
      category: editServiceForm.category || '',
      name: editServiceForm.name || '',
      description: editServiceForm.description || '',
      keywords: editServiceForm.keywords.split(',').map((keyword) => keyword.trim()).filter(Boolean),
      price: editServiceForm.price || '',
      optimized_name: original.optimized_name || '',
      optimized_description: original.optimized_description || '',
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
    optimizingAll,
    addService,
    optimizeService,
    optimizeAllServices,
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
