import { useCallback, useEffect, useState } from "react";
import { getApiEndpoint } from '../config/api';
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { newAuth, type User } from "@/lib/auth_new";
import { BusinessSwitcher } from "@/components/BusinessSwitcher";
import {
  DashboardBusinessInfoSection,
  DashboardInviteSection,
  DashboardMapsToolsSection,
  DashboardProfileSection,
  DashboardReportModal,
  DashboardTabContent,
  DashboardTabsShell,
  DashboardWizardModal,
  DashboardWelcomeSection,
  type DashboardBusiness,
  type DashboardClientInfo,
  type DashboardService,
  type DashboardTabId,
} from "@/components/dashboard/DashboardSections";

type DashboardReport = {
  id: string;
  created_at?: string;
  has_report?: boolean;
};

type DashboardQueueItem = {
  id: string;
};

type DashboardNetwork = {
  id: string;
  name?: string;
};

type DashboardProfileForm = {
  email: string;
  phone: string;
  name: string;
  yandexUrl: string;
};

type DashboardCardAnalysis = Record<string, unknown>;
type DashboardPriceListOptimization = Record<string, unknown>;
type ServiceUpdatePayload = Partial<DashboardService> & Record<string, unknown>;

type DashboardAuthMeResponse = {
  businesses?: DashboardBusiness[];
};

type DashboardNetworksResponse = {
  success?: boolean;
  networks?: DashboardNetwork[];
};

type DashboardServicesResponse = {
  success?: boolean;
  services?: DashboardService[];
  error?: string;
};

const isDashboardNetworksResponse = (value: unknown): value is DashboardNetworksResponse =>
  typeof value === 'object' && value !== null;

const isDashboardServicesResponse = (value: unknown): value is DashboardServicesResponse =>
  typeof value === 'object' && value !== null;

const getErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
};

function getNextReportDate(reports: DashboardReport[]) {
  if (!reports.length) return null;
  const completedReports = reports.filter(report => report.has_report);
  if (!completedReports.length) return null;
  const last = new Date(completedReports[0].created_at);
  return new Date(last.getTime() + 7 * 24 * 60 * 60 * 1000);
}

function getCountdownString(date: Date) {
  const now = new Date();
  const diff = date.getTime() - now.getTime();
  if (diff <= 0) return null;
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  const minutes = Math.floor((diff / (1000 * 60)) % 60);
  return `${days} д. ${hours} ч. ${minutes} мин.`;
}

const Dashboard = () => {
  const [user, setUser] = useState<User | null>(null);
  const [reports, setReports] = useState<DashboardReport[]>([]);
  const [queue, setQueue] = useState<DashboardQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [autoAnalysisUrl, setAutoAnalysisUrl] = useState('');
  const [autoAnalysisLoading, setAutoAnalysisLoading] = useState(false);
  const [form, setForm] = useState<DashboardProfileForm>({ email: "", phone: "", name: "", yandexUrl: "" });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);
  const [timer, setTimer] = useState<string | null>(null);

  // Вкладки
  const [activeTab, setActiveTab] = useState<DashboardTabId>('overview');

  // Услуги
  const [userServices, setUserServices] = useState<DashboardService[]>([]);

  // Бизнесы (для суперадмина)
  const [businesses, setBusinesses] = useState<DashboardBusiness[]>([]);
  const [currentBusinessId, setCurrentBusinessId] = useState<string | null>(null);
  const [currentBusiness, setCurrentBusiness] = useState<DashboardBusiness | null>(null);

  // Сети
  const [networks, setNetworks] = useState<DashboardNetwork[]>([]);
  const [currentNetworkId, setCurrentNetworkId] = useState<string | null>(null);
  const [currentLocationId, setCurrentLocationId] = useState<string | null>(null);
  const [loadingServices, setLoadingServices] = useState(false);
  const [editingService, setEditingService] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [showAddService, setShowAddService] = useState(false);

  // Функция для переключения бизнеса
  const handleBusinessChange = async (businessId: string) => {
    const business = businesses.find(b => b.id === businessId);
    if (business) {
      setCurrentBusinessId(businessId);
      setCurrentBusiness(business);

      // Сохраняем выбор в localStorage
      localStorage.setItem('selectedBusinessId', businessId);

      // НЕ обновляем данные профиля пользователя при переключении бизнеса
      // Данные профиля (email, phone, name) должны оставаться неизменными

      // Обновляем информацию о бизнесе
      setClientInfo({
        businessName: business.name || "",
        businessType: business.business_type || "other",
        address: business.address || "",
        workingHours: business.working_hours || "",
        mapLinks: [],
      });

      // Загружаем данные бизнеса
      try {
        const token = newAuth.getToken();
        if (!token) return;

        const response = await fetch(`/api/business/${businessId}/data`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const data = await response.json();

          // Обновляем услуги
          setUserServices(data.services || []);

          // Обновляем информацию о клиенте
          setClientInfo({
            businessName: data.business.name || '',
            businessType: data.business.business_type || '',
            address: data.business.address || '',
            workingHours: data.business.working_hours || '',
            mapLinks: [],
          });

          // Обновляем данные профиля из профиля бизнеса
          if (data.business_profile) {
            setForm({
              email: data.business_profile.contact_email || user?.email || "",
              phone: data.business_profile.contact_phone || user?.phone || "",
              name: data.business_profile.contact_name || user?.name || "",
              yandexUrl: ""
            });
          }

          // Обновляем ссылку на карты для текущего бизнеса (если есть)
          if (data.business && data.business.yandex_url) {
            setYandexCardUrl(data.business.yandex_url);
          } else {
            setYandexCardUrl('');
          }

        } else {
          const errorData = await response.json();
          console.error('Ошибка загрузки данных бизнеса:', errorData);
        }
      } catch (error) {
        console.error('Ошибка при загрузке данных бизнеса:', error);
      }
    }
  };

  const handleSaveYandexLink = async () => {
    if (!currentBusinessId) {
      setError('Сначала выберите бизнес');
      return;
    }
    if (!yandexCardUrl.trim()) {
      setError('Введите ссылку на карточку на картах');
      return;
    }

    try {
      const response = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/yandex-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({ yandex_url: yandexCardUrl })
      });

      const data = await response.json();
      if (response.ok && data.success) {
        setSuccess('Ссылка на карты сохранена и синхронизация запущена');
      } else {
        setError(data.error || 'Не удалось сохранить ссылку на карты');
      }
    } catch (error: unknown) {
      setError('Ошибка сохранения ссылки на карты: ' + getErrorMessage(error, 'Неизвестная ошибка'));
    }
  };
  const [newService, setNewService] = useState({
    category: '',
    name: '',
    description: '',
    keywords: '',
    price: ''
  });

  // Финансы
  const [showTransactionForm, setShowTransactionForm] = useState(false);

  // Информация о клиенте
  const [clientInfo, setClientInfo] = useState<DashboardClientInfo>({
    businessName: '',
    businessType: '',
    address: '',
    workingHours: '',
    mapLinks: [],
  });
  const [editClientInfo, setEditClientInfo] = useState(false);
  const [savingClientInfo, setSavingClientInfo] = useState(false);
  const [yandexCardUrl, setYandexCardUrl] = useState<string>('');
  const [refreshingMapsData, setRefreshingMapsData] = useState(false);

  // Заполненность профиля
  const profileCompletion = (() => {
    const fieldsTotal = 7; // email, phone, name, businessName, businessType, address, workingHours
    let filled = 0;
    if ((form.email || '').trim()) filled++;
    if ((form.phone || '').trim()) filled++;
    if ((form.name || '').trim()) filled++;
    if ((clientInfo.businessName || '').trim()) filled++;
    if ((clientInfo.businessType || '').trim()) filled++;
    if ((clientInfo.address || '').trim()) filled++;
    if ((clientInfo.workingHours || '').trim()) filled++;
    return Math.round((filled / fieldsTotal) * 100);
  })();

  const connectedMapTypes = Array.from(
    new Set(
      (clientInfo.mapLinks || [])
        .map((link) => String(link.mapType || '').trim().toLowerCase())
        .filter(Boolean)
    )
  );

  const connectedMapLabels = connectedMapTypes.map((mapType) => {
    if (mapType === 'yandex') return 'Яндекс';
    if (mapType === '2gis') return '2ГИС';
    if (mapType === 'google') return 'Google Maps';
    if (mapType === 'apple') return 'Apple Maps';
    return mapType;
  });

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
    } catch (error: unknown) {
      setError(`Ошибка запуска обновления данных с карт: ${getErrorMessage(error, 'Неизвестная ошибка')}`);
    } finally {
      setRefreshingMapsData(false);
    }
  };

  // Загрузка сетей пользователя
  const loadNetworks = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/networks`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const payload: unknown = await response.json();
      if (!isDashboardNetworksResponse(payload)) {
        return;
      }
      const data = payload;
      if (data.success && data.networks && data.networks.length > 0) {
        setNetworks(data.networks);
        // Если есть сети, выбираем первую
        if (!currentNetworkId) {
          setCurrentNetworkId(data.networks[0].id);
        }
      }
    } catch (error: unknown) {
      console.error('Ошибка загрузки сетей:', error);
    }
  }, [currentNetworkId]);

  // Загрузка услуг пользователя
  const loadUserServices = async () => {
    setLoadingServices(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/list`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const payload: unknown = await response.json();
      if (!isDashboardServicesResponse(payload)) {
        return;
      }
      const data = payload;
      if (data.success) {
        setUserServices(data.services || []);
      }
    } catch (error: unknown) {
      console.error('Ошибка загрузки услуг:', error);
    } finally {
      setLoadingServices(false);
    }
  };

  // Добавление новой услуги
  const addService = async () => {
    if (!newService.name.trim()) {
      setError('Название услуги обязательно');
      return;
    }

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/add`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          category: newService.category || 'Общие услуги',
          name: newService.name,
          description: newService.description,
          keywords: newService.keywords.split(',').map(k => k.trim()).filter(k => k),
          price: newService.price,
          business_id: currentBusinessId
        })
      });

      const data = await response.json();
      if (data.success) {
        setNewService({ category: '', name: '', description: '', keywords: '', price: '' });
        setShowAddService(false);
        await loadUserServices();
        setSuccess('Услуга добавлена');
      } else {
        setError(data.error || 'Ошибка добавления услуги');
      }
    } catch (error: unknown) {
      setError('Ошибка добавления услуги: ' + getErrorMessage(error, 'Неизвестная ошибка'));
    }
  };

  // Обновление услуги
  const updateService = async (serviceId: string, updatedData: ServiceUpdatePayload) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/update/${serviceId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(updatedData)
      });

      const data = await response.json();
      if (data.success) {
        setEditingService(null);
        await loadUserServices();
        setSuccess('Услуга обновлена');
      } else {
        setError(data.error || 'Ошибка обновления услуги');
      }
    } catch (error: unknown) {
      setError('Ошибка обновления услуги: ' + getErrorMessage(error, 'Неизвестная ошибка'));
    }
  };

  // Удаление услуги
  const deleteService = async (serviceId: string) => {
    if (!confirm('Вы уверены, что хотите удалить эту услугу?')) return;

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/delete/${serviceId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const data = await response.json();
      if (data.success) {
        await loadUserServices();
        setSuccess('Услуга удалена');
      } else {
        setError(data.error || 'Ошибка удаления услуги');
      }
    } catch (error: unknown) {
      setError('Ошибка удаления услуги: ' + getErrorMessage(error, 'Неизвестная ошибка'));
    }
  };

  // Сохранение информации о клиенте
  const handleSaveClientInfo = async () => {
    setSavingClientInfo(true);
    try {
      const response = await fetch(`${window.location.origin}/api/client-info`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          ...clientInfo,
          businessId: currentBusinessId
        })
      });

      if (response.ok) {
        setEditClientInfo(false);
        setSuccess('Информация о бизнесе сохранена');

        // Обновляем данные текущего бизнеса в списке
        if (currentBusinessId) {
          const updatedBusinesses = businesses.map(b =>
            b.id === currentBusinessId
              ? { ...b, name: clientInfo.businessName, address: clientInfo.address, working_hours: clientInfo.workingHours }
              : b
          );
          setBusinesses(updatedBusinesses);

          // Обновляем текущий бизнес
          const updatedCurrentBusiness = updatedBusinesses.find(b => b.id === currentBusinessId);
          if (updatedCurrentBusiness) {
            setCurrentBusiness(updatedCurrentBusiness);
          }
        }
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка сохранения информации');
      }
    } catch (error) {
      console.error('Ошибка сохранения информации:', error);
      setError('Ошибка сохранения информации');
    } finally {
      setSavingClientInfo(false);
    }
  };

  // Обновление профиля
  const handleUpdateProfile = async () => {
    try {
      // Если есть выбранный бизнес, сохраняем в профиль бизнеса
      if (currentBusinessId) {
        const response = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/profile`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          },
          body: JSON.stringify({
            contact_name: form.name,
            contact_phone: form.phone,
            contact_email: form.email
          })
        });

        if (response.ok) {
          setEditMode(false);
          setSuccess('Профиль бизнеса обновлен');
        } else {
          const errorData = await response.json();
          setError(errorData.error || 'Ошибка обновления профиля бизнеса');
        }
      } else {
        // Если нет выбранного бизнеса, обновляем глобальный профиль
        const { user: updatedUser, error } = await newAuth.updateProfile({
          name: form.name,
          phone: form.phone
        });

        if (error) {
          setError(error);
          return;
        }

        setUser(updatedUser);
        setEditMode(false);
        setSuccess('Профиль обновлен');
      }
    } catch (error) {
      console.error('Ошибка обновления профиля:', error);
      setError('Ошибка обновления профиля');
    }
  };

  // Создание отчета
  const [showCreateReport, setShowCreateReport] = useState(false);
  const [creatingReport, setCreatingReport] = useState(false);
  const [createReportForm, setCreateReportForm] = useState({ yandexUrl: "" });

  const handleCreateReport = async () => {
    if (!createReportForm.yandexUrl.trim()) {
      setError('Введите URL страницы на картах');
      return;
    }

    setCreatingReport(true);
    setError(null);

    try {
      const response = await fetch(`${window.location.origin}/api/create-report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          yandex_url: createReportForm.yandexUrl
        })
      });

      if (response.ok) {
        setSuccess('Отчёт добавлен в очередь обработки');
        setShowCreateReport(false);
        setCreateReportForm({ yandexUrl: "" });
        // Обновляем список отчетов
        window.location.reload();
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка создания отчёта');
      }
    } catch (error) {
      console.error('Ошибка создания отчёта:', error);
      setError('Ошибка создания отчёта');
    } finally {
      setCreatingReport(false);
    }
  };

  // Просмотр отчета
  const [viewingReport, setViewingReport] = useState<string | null>(null);
  const [reportContent, setReportContent] = useState('');
  const [loadingReport, setLoadingReport] = useState(false);

  const handleViewReport = async (reportId: string) => {
    setViewingReport(reportId);
    setLoadingReport(true);
    setReportContent('');

    try {
      const response = await fetch(`${window.location.origin}/api/reports/${reportId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setReportContent(data.content || 'Содержимое отчёта недоступно');
      } else {
        setError('Ошибка загрузки отчёта');
      }
    } catch (error) {
      console.error('Ошибка загрузки отчёта:', error);
      setError('Ошибка загрузки отчёта');
    } finally {
      setLoadingReport(false);
    }
  };

  // Скачивание отчета
  const handleDownloadReport = async (reportId: string) => {
    try {
      const response = await fetch(`${window.location.origin}/api/reports/${reportId}/download`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report-${reportId}.pdf`;
        a.click();
        window.URL.revokeObjectURL(url);
        setSuccess('Отчёт скачан');
      } else {
        setError('Ошибка скачивания отчёта');
      }
    } catch (error) {
      console.error('Ошибка скачивания отчёта:', error);
      setError('Ошибка скачивания отчёта');
    }
  };

  // Функция автоматического анализа карточки
  const handleAutoAnalysis = async () => {
    if (!autoAnalysisUrl.trim()) {
      setError('Введите URL карточки на картах');
      return;
    }

    if (!autoAnalysisUrl.includes('yandex.ru/maps') && !autoAnalysisUrl.includes('google.com/maps')) {
      setError('Введите корректную ссылку на карты');
      return;
    }

    setAutoAnalysisLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(getApiEndpoint('/api/analyze-card-auto'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ url: autoAnalysisUrl })
      });

      const data = await response.json();

      if (data.success) {
        setSuccess('Карточка успешно проанализирована!');
        setAutoAnalysisUrl('');
        // Перезагрузим страницу для обновления отчётов
        window.location.reload();
      } else {
        setError(data.error || 'Ошибка анализа');
      }
    } catch (error) {
      setError('Ошибка соединения с сервером');
    } finally {
      setAutoAnalysisLoading(false);
    }
  };
  const [canCreateReport, setCanCreateReport] = useState<boolean>(false);
  const [paraphrasingService, setParaphrasingService] = useState("");
  const [paraphrasedText, setParaphrasedText] = useState("");
  const [paraphrasing, setParaphrasing] = useState(false);
  const [cardImage, setCardImage] = useState<File | null>(null);
  const [analyzingCard, setAnalyzingCard] = useState(false);
  const [cardAnalysis, setCardAnalysis] = useState<DashboardCardAnalysis | null>(null);
  const [priceListFile, setPriceListFile] = useState<File | null>(null);
  const [optimizingPriceList, setOptimizingPriceList] = useState(false);
  const [priceListOptimization, setPriceListOptimization] = useState<DashboardPriceListOptimization | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Получаем текущего пользователя
        const currentUser = await newAuth.getCurrentUser();

        if (!currentUser) {
          setLoading(false);
          return;
        }

        setUser(currentUser);
        setForm({
          email: currentUser.email || "",
          phone: currentUser.phone || "",
          name: currentUser.name || "",
          yandexUrl: ""
        });

        // Загружаем бизнесы если пользователь суперадмин
        if (currentUser.is_superadmin) {
          // Всегда загружаем businesses отдельно через API для надежности
          try {
            const response = await fetch('/api/auth/me', {
              headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
              }
            });
            if (response.ok) {
              const data = await response.json();
              if (data.businesses && Array.isArray(data.businesses) && data.businesses.length > 0) {
                setBusinesses(data.businesses);
                const savedBusinessId = localStorage.getItem('selectedBusinessId');
                const businessToSelect = savedBusinessId
                  ? data.businesses.find((business) => business.id === savedBusinessId) || data.businesses[0]
                  : data.businesses[0];

                setCurrentBusinessId(businessToSelect.id);
                setCurrentBusiness(businessToSelect);
                localStorage.setItem('selectedBusinessId', businessToSelect.id);
              } else {
                setBusinesses([]);
              }
            } else {
              console.error('Ошибка ответа /api/auth/me:', response.status, response.statusText);
            }
          } catch (error) {
            console.error('Ошибка загрузки бизнесов:', error);
            setBusinesses([]);
          }
        }

        // Получаем отчёты пользователя
        const { reports: userReports, error: reportsError } = await newAuth.getUserReports();
        if (reportsError) {
          console.error('Ошибка загрузки отчётов:', reportsError);
        } else {
          setReports(userReports || []);
        }

        // Получаем очередь пользователя
        const { queue: userQueue, error: queueError } = await newAuth.getUserQueue();
        if (queueError) {
          console.error('Ошибка загрузки очереди:', queueError);
        } else {
          setQueue(userQueue || []);
        }

        // Автозаполняем форму создания отчёта
        setCreateReportForm({
          yandexUrl: ""
        });

        // Загружаем услуги пользователя
        await loadUserServices();

        // Загружаем сети пользователя
        await loadNetworks();

        // Загружаем личную информацию о бизнесе
        try {
          const clientInfoResponse = await fetch(`${window.location.origin}/api/client-info`, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
          });
          if (clientInfoResponse.ok) {
            const clientData = await clientInfoResponse.json();
            setClientInfo(clientData);
          }
        } catch (error) {
          console.error('Ошибка загрузки информации о бизнесе:', error);
        }

      } catch (error) {
        console.error('Ошибка загрузки данных:', error);
        setError('Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    };

    void fetchData();
  }, [loadNetworks]);

  useEffect(() => {
    // Если нет готовых отчётов — можно создавать сразу
    const nextDate = getNextReportDate(reports);
    if (!nextDate) {
      setCanCreateReport(true);
      setTimer('00:00:00');
      return;
    }

    const now = new Date();
    if (nextDate.getTime() <= now.getTime()) {
      setCanCreateReport(true);
      setTimer('00:00:00');
      return;
    }

    setCanCreateReport(false);
    const updateTimer = () => {
      const countdown = getCountdownString(nextDate);
      setTimer(countdown);
      if (!countdown) {
        // Время истекло, обновляем данные
        window.location.reload();
      }
    };
    updateTimer();
    const interval = setInterval(updateTimer, 60000);
    return () => clearInterval(interval);
  }, [reports]);


  const handleDeleteQueueItem = async (queueId: string) => {
    if (!confirm('Вы уверены, что хотите удалить этот отчёт из обработки?')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/users/queue/${queueId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        setSuccess('Отчёт удалён из обработки');
        // Обновляем данные
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка удаления отчёта');
      }
    } catch (error) {
      console.error('Ошибка удаления отчёта:', error);
      setError('Ошибка удаления отчёта');
    }
  };


  // Функция для перефразирования через GigaChat
  const handleParaphraseService = async () => {
    if (!paraphrasingService.trim()) {
      setError('Введите описание услуги для перефразирования');
      return;
    }

    setParaphrasing(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:5002/api/paraphrase', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: paraphrasingService,
          businessType: clientInfo.businessType
        })
      });

      if (response.ok) {
        const data = await response.json();
        setParaphrasedText(data.paraphrased_text);
        setSuccess('Текст успешно перефразирован');
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка перефразирования');
      }
    } catch (error) {
      console.error('Ошибка перефразирования:', error);
      setError('Ошибка перефразирования');
    } finally {
      setParaphrasing(false);
    }
  };

  const handleAnalyzeCard = async () => {
    if (!cardImage) {
      setError('Выберите изображение для анализа');
      return;
    }

    setAnalyzingCard(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('image', cardImage);

      const response = await fetch('http://localhost:5002/api/analyze-card', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setCardAnalysis(data);
        setSuccess('Карточка успешно проанализирована');
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка анализа карточки');
      }
    } catch (error) {
      console.error('Ошибка анализа карточки:', error);
      setError('Ошибка анализа карточки');
    } finally {
      setAnalyzingCard(false);
    }
  };

  const handleOptimizePriceList = async () => {
    if (!priceListFile) {
      setError('Выберите файл прайс-листа для оптимизации');
      return;
    }

    setOptimizingPriceList(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', priceListFile);

      const response = await fetch('http://localhost:5002/api/optimize-pricelist', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setPriceListOptimization(data);
        setSuccess('Прайс-лист успешно оптимизирован');
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка оптимизации прайс-листа');
      }
    } catch (error) {
      console.error('Ошибка оптимизации прайс-листа:', error);
      setError('Ошибка оптимизации прайс-листа');
    } finally {
      setOptimizingPriceList(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Доступ запрещён</h1>
          <p className="text-gray-600 mb-6">Необходима авторизация</p>
          <Button onClick={() => window.location.href = '/login'}>
            Войти
          </Button>
        </div>
      </div>
    );
  }

  const wizardNext = () => {
    // На первом шаге сохраняем ссылку на карты, если она указана
    if (wizardStep === 1) {
      handleSaveYandexLink();
    }
    setWizardStep((step) => {
      if (step === 1) {
        return 2;
      }
      if (step === 2) {
        return 3;
      }
      return step;
    });
  };
  const wizardPrev = () => setWizardStep((step) => {
    if (step === 3) {
      return 2;
    }
    if (step === 2) {
      return 1;
    }
    return step;
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Полупрозрачный хедер с размытием */}
      <div className="fixed top-0 left-0 right-0 z-50 bg-white/70 backdrop-blur-md border-b border-gray-200/50 shadow-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold text-gray-900">Личный кабинет</h1>
            <div className="flex items-center space-x-4 gap-2">
              {user?.is_superadmin && businesses.length > 0 && (
                <BusinessSwitcher
                  businesses={businesses}
                  currentBusinessId={currentBusinessId || undefined}
                  onBusinessChange={handleBusinessChange}
                  isSuperadmin={true}
                />
              )}
              {user?.is_superadmin && businesses.length === 0 && (
                <div className="text-xs text-gray-500 px-2 py-1 bg-gray-100 rounded">
                  Загрузка бизнесов...
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  try {
                    await newAuth.signOut();
                  } finally {
                    // Чистим локальные данные и уходим на страницу входа
                    try { localStorage.clear(); } catch { /* noop */ }
                    window.location.href = "/login";
                  }
                }}
              >
                Выйти
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8 pt-24">
        {/* Приветственный блок + шкала заполненности */}
        <DashboardWelcomeSection
          currentBusiness={currentBusiness}
          profileCompletion={profileCompletion}
        />

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4">
            {success}
          </div>
        )}

        <DashboardProfileSection
          form={form}
          editMode={editMode}
          onEdit={() => setEditMode(true)}
          onCancel={() => setEditMode(false)}
          onSave={handleUpdateProfile}
          onFormChange={setForm}
        />

        <DashboardBusinessInfoSection
          clientInfo={clientInfo}
          editClientInfo={editClientInfo}
          savingClientInfo={savingClientInfo}
          onEdit={() => setEditClientInfo(true)}
          onCancel={() => setEditClientInfo(false)}
          onSave={handleSaveClientInfo}
          onClientInfoChange={setClientInfo}
        />

        {/* Навигация по разделам */}
        <DashboardTabsShell
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <div className="mb-6 bg-gradient-to-r from-gray-50 to-white rounded-lg border-2 border-gray-200 shadow-sm p-4">
          <div className="mt-6">
            <DashboardTabContent
              activeTab={activeTab}
              showTransactionForm={showTransactionForm}
              onToggleTransactionForm={() => setShowTransactionForm((value) => !value)}
              onTransactionSuccess={() => {
                setShowTransactionForm(false);
                setSuccess('Транзакция добавлена успешно!');
              }}
              onTransactionCancel={() => setShowTransactionForm(false)}
              currentNetworkId={currentNetworkId}
              currentBusinessId={currentBusinessId}
              currentLocationId={currentLocationId}
              onLocationChange={setCurrentLocationId}
              showAddService={showAddService}
              newService={newService}
              loadingServices={loadingServices}
              userServices={userServices}
              onShowAddService={() => setShowAddService(true)}
              onHideAddService={() => setShowAddService(false)}
              onNewServiceChange={setNewService}
              onAddService={addService}
              onDeleteService={deleteService}
              onEditService={setEditingService}
            />
          </div>
        </div>

        <DashboardMapsToolsSection
          currentBusinessId={currentBusinessId}
          clientInfo={clientInfo}
          connectedMapTypes={connectedMapTypes}
          connectedMapLabels={connectedMapLabels}
          refreshingMapsData={refreshingMapsData}
          onRefreshMapsData={handleRefreshMapsData}
          userServices={userServices}
        />

        {/* Приглашения */}
        <DashboardInviteSection
          inviteSuccess={inviteSuccess}
          onSuccess={() => setInviteSuccess(true)}
          onError={setError}
        />

        <DashboardWizardModal
          open={showWizard}
          wizardStep={wizardStep}
          yandexCardUrl={yandexCardUrl}
          onYandexCardUrlChange={setYandexCardUrl}
          onClose={() => setShowWizard(false)}
          onPrevious={wizardPrev}
          onNext={wizardNext}
          onComplete={() => {
            setShowWizard(false);
            window.location.href = "/sprint";
          }}
        />

        <DashboardReportModal
          reportId={viewingReport}
          loading={loadingReport}
          reportContent={reportContent}
          onClose={() => setViewingReport(null)}
        />

      </div>
      <Footer />
    </div>
  );
};

export default Dashboard;
