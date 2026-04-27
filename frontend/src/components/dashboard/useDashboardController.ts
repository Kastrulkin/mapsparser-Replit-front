import { useEffect, useMemo, useState } from "react";
import { newAuth, type User } from "@/lib/auth_new";
import type {
  DashboardBusiness,
  DashboardClientInfo,
  DashboardService,
  DashboardTabId,
} from "@/components/dashboard/DashboardSections";
import {
  addDashboardService,
  buildDashboardClientInfo,
  buildDashboardProfileForm,
  deleteDashboardService,
  fetchDashboardBootstrap,
  fetchDashboardBusinessData,
  fetchDashboardServices,
  saveDashboardBusinessProfile,
  saveDashboardClientInfo,
} from "@/components/dashboard/dashboardData";

type DashboardProfileForm = {
  email: string;
  phone: string;
  name: string;
  yandexUrl: string;
};

type NewServiceState = {
  category: string;
  name: string;
  description: string;
  keywords: string;
  price: string;
};

const emptyClientInfo = (): DashboardClientInfo => ({
  businessName: "",
  businessType: "",
  address: "",
  workingHours: "",
  mapLinks: [],
});

const emptyProfileForm = (): DashboardProfileForm => ({
  email: "",
  phone: "",
  name: "",
  yandexUrl: "",
});

const emptyNewService = (): NewServiceState => ({
  category: "",
  name: "",
  description: "",
  keywords: "",
  price: "",
});

const getErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
};

export const useDashboardController = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState<DashboardProfileForm>(emptyProfileForm());
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<DashboardTabId>('overview');
  const [userServices, setUserServices] = useState<DashboardService[]>([]);
  const [businesses, setBusinesses] = useState<DashboardBusiness[]>([]);
  const [currentBusinessId, setCurrentBusinessId] = useState<string | null>(null);
  const [currentBusiness, setCurrentBusiness] = useState<DashboardBusiness | null>(null);
  const [currentNetworkId, setCurrentNetworkId] = useState<string | null>(null);
  const [currentLocationId, setCurrentLocationId] = useState<string | null>(null);
  const [loadingServices, setLoadingServices] = useState(false);
  const [showAddService, setShowAddService] = useState(false);
  const [newService, setNewService] = useState<NewServiceState>(emptyNewService());
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [clientInfo, setClientInfo] = useState<DashboardClientInfo>(emptyClientInfo());
  const [editClientInfo, setEditClientInfo] = useState(false);
  const [savingClientInfo, setSavingClientInfo] = useState(false);
  const [refreshingMapsData, setRefreshingMapsData] = useState(false);

  const profileCompletion = useMemo(() => {
    const fieldsTotal = 7;
    let filled = 0;
    if (form.email.trim()) filled++;
    if (form.phone.trim()) filled++;
    if (form.name.trim()) filled++;
    if (clientInfo.businessName.trim()) filled++;
    if (clientInfo.businessType.trim()) filled++;
    if (clientInfo.address.trim()) filled++;
    if (clientInfo.workingHours.trim()) filled++;
    return Math.round((filled / fieldsTotal) * 100);
  }, [clientInfo.address, clientInfo.businessName, clientInfo.businessType, clientInfo.workingHours, form.email, form.name, form.phone]);

  const connectedMapTypes = useMemo(() => Array.from(
    new Set(
      clientInfo.mapLinks
        .map((link) => String(link.mapType || '').trim().toLowerCase())
        .filter(Boolean)
    )
  ), [clientInfo.mapLinks]);

  const connectedMapLabels = useMemo(() => connectedMapTypes.map((mapType) => {
    if (mapType === 'yandex') return 'Яндекс';
    if (mapType === '2gis') return '2ГИС';
    if (mapType === 'google') return 'Google Maps';
    if (mapType === 'apple') return 'Apple Maps';
    return mapType;
  }), [connectedMapTypes]);

  const loadUserServices = async () => {
    setLoadingServices(true);
    try {
      const loadedServices = await fetchDashboardServices();
      setUserServices(loadedServices);
    } catch (loadError: unknown) {
      console.error('Ошибка загрузки услуг:', loadError);
    } finally {
      setLoadingServices(false);
    }
  };

  const handleBusinessChange = async (businessId: string) => {
    const business = businesses.find((item) => item.id === businessId);
    if (!business) {
      return;
    }

    setCurrentBusinessId(businessId);
    setCurrentBusiness(business);
    localStorage.setItem('selectedBusinessId', businessId);
    setClientInfo(buildDashboardClientInfo(business));

    try {
      const data = await fetchDashboardBusinessData(businessId);
      if (!data) {
        return;
      }
      setUserServices(data.services || []);
      setClientInfo(buildDashboardClientInfo(data.business || null));
      if (data.business_profile) {
        setForm(buildDashboardProfileForm(user, data.business_profile));
      }
    } catch (loadError: unknown) {
      console.error('Ошибка при загрузке данных бизнеса:', loadError);
    }
  };

  const handleRefreshMapsData = async () => {
    if (!currentBusinessId) {
      setError('Сначала выберите бизнес');
      return;
    }

    if (connectedMapTypes.length === 0) {
      setError('Для этого бизнеса ещё не добавлены ссылки на карты');
      return;
    }

    const sourceByMapType: Record<string, string> = {
      yandex: 'apify_yandex',
      '2gis': 'apify_2gis',
      google: 'apify_google',
      apple: 'apify_apple',
    };

    const sourcesToRefresh = connectedMapTypes
      .map((mapType) => sourceByMapType[mapType] || '')
      .filter(Boolean);

    if (sourcesToRefresh.length === 0) {
      setError('Не нашли подходящие Apify-коннекторы для подключённых карт');
      return;
    }

    setRefreshingMapsData(true);
    setError(null);
    setSuccess(null);

    try {
      const results = await Promise.allSettled(
        sourcesToRefresh.map((source) =>
          newAuth.makeRequest('/admin/prospecting/business-parse-apify', {
            method: 'POST',
            body: JSON.stringify({
              business_id: currentBusinessId,
              source,
            }),
          })
        )
      );

      const successCount = results.filter((result) => result.status === 'fulfilled').length;
      const failedResults = results.filter((result) => result.status === 'rejected');

      if (successCount > 0) {
        setSuccess(`Запустили обновление данных с карт: ${connectedMapLabels.join(', ')}. Задачи поставлены в очередь на Apify-парсинг.`);
      }

      if (failedResults.length > 0) {
        const firstFailure = failedResults[0];
        if (firstFailure.status === 'rejected') {
          setError(String(firstFailure.reason?.message || firstFailure.reason || 'Не удалось запустить обновление данных с карт'));
        }
      }
    } catch (refreshError: unknown) {
      setError(`Ошибка запуска обновления данных с карт: ${getErrorMessage(refreshError, 'Неизвестная ошибка')}`);
    } finally {
      setRefreshingMapsData(false);
    }
  };

  const addService = async () => {
    if (!newService.name.trim()) {
      setError('Название услуги обязательно');
      return;
    }

    try {
      const result = await addDashboardService(currentBusinessId, newService);
      if (!result.success) {
        setError(result.error || 'Ошибка добавления услуги');
        return;
      }
      setNewService(emptyNewService());
      setShowAddService(false);
      await loadUserServices();
      setSuccess('Услуга добавлена');
    } catch (saveError: unknown) {
      setError(`Ошибка добавления услуги: ${getErrorMessage(saveError, 'Неизвестная ошибка')}`);
    }
  };

  const deleteService = async (serviceId: string) => {
    if (!confirm('Вы уверены, что хотите удалить эту услугу?')) {
      return;
    }

    try {
      const result = await deleteDashboardService(serviceId);
      if (!result.success) {
        setError(result.error || 'Ошибка удаления услуги');
        return;
      }
      await loadUserServices();
      setSuccess('Услуга удалена');
    } catch (deleteError: unknown) {
      setError(`Ошибка удаления услуги: ${getErrorMessage(deleteError, 'Неизвестная ошибка')}`);
    }
  };

  const handleSaveClientInfo = async () => {
    setSavingClientInfo(true);
    try {
      const result = await saveDashboardClientInfo(currentBusinessId, clientInfo);
      if (!result.success) {
        setError(result.error || 'Ошибка сохранения информации');
        return;
      }

      setEditClientInfo(false);
      setSuccess('Информация о бизнесе сохранена');

      if (currentBusinessId) {
        const updatedBusinesses = businesses.map((business) =>
          business.id === currentBusinessId
            ? { ...business, name: clientInfo.businessName, address: clientInfo.address, working_hours: clientInfo.workingHours }
            : business
        );
        setBusinesses(updatedBusinesses);
        const updatedCurrentBusiness = updatedBusinesses.find((business) => business.id === currentBusinessId);
        if (updatedCurrentBusiness) {
          setCurrentBusiness(updatedCurrentBusiness);
        }
      }
    } catch (saveError: unknown) {
      console.error('Ошибка сохранения информации:', saveError);
      setError('Ошибка сохранения информации');
    } finally {
      setSavingClientInfo(false);
    }
  };

  const handleUpdateProfile = async () => {
    try {
      if (currentBusinessId) {
        const result = await saveDashboardBusinessProfile(currentBusinessId, form);
        if (!result.success) {
          setError(result.error || 'Ошибка обновления профиля бизнеса');
          return;
        }
        setEditMode(false);
        setSuccess('Профиль бизнеса обновлен');
        return;
      }

      const result = await newAuth.updateProfile({
        name: form.name,
        phone: form.phone,
      });

      if (result.error) {
        setError(result.error);
        return;
      }

      setUser(result.user);
      setEditMode(false);
      setSuccess('Профиль обновлен');
    } catch (updateError: unknown) {
      console.error('Ошибка обновления профиля:', updateError);
      setError('Ошибка обновления профиля');
    }
  };

  const handleSignOut = async () => {
    try {
      await newAuth.signOut();
    } finally {
      try {
        localStorage.clear();
      } catch {
        // noop
      }
      window.location.href = '/login';
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const currentUser = await newAuth.getCurrentUser();
        if (!currentUser) {
          setLoading(false);
          return;
        }

        setUser(currentUser);
        setForm(buildDashboardProfileForm(currentUser));
        const bootstrap = await fetchDashboardBootstrap(currentUser);
        setBusinesses(bootstrap.businesses);
        setCurrentBusinessId(bootstrap.currentBusinessId);
        setCurrentBusiness(bootstrap.currentBusiness);
        setUserServices(bootstrap.userServices);
        setCurrentNetworkId(bootstrap.currentNetworkId);
        if (bootstrap.clientInfo) {
          setClientInfo(bootstrap.clientInfo);
        }
        if (bootstrap.currentBusinessId) {
          localStorage.setItem('selectedBusinessId', bootstrap.currentBusinessId);
        }
      } catch (loadError: unknown) {
        console.error('Ошибка загрузки данных:', loadError);
        setError('Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    };

    void fetchData();
  }, []);

  return {
    user,
    loading,
    editMode,
    setEditMode,
    form,
    setForm,
    error,
    setError,
    success,
    setSuccess,
    inviteSuccess,
    setInviteSuccess,
    activeTab,
    setActiveTab,
    userServices,
    businesses,
    currentBusinessId,
    currentBusiness,
    currentNetworkId,
    currentLocationId,
    setCurrentLocationId,
    loadingServices,
    showAddService,
    setShowAddService,
    newService,
    setNewService,
    showTransactionForm,
    setShowTransactionForm,
    clientInfo,
    setClientInfo,
    editClientInfo,
    setEditClientInfo,
    savingClientInfo,
    refreshingMapsData,
    profileCompletion,
    connectedMapTypes,
    connectedMapLabels,
    handleBusinessChange,
    handleRefreshMapsData,
    addService,
    deleteService,
    handleSaveClientInfo,
    handleUpdateProfile,
    handleSignOut,
  };
};
