import { useEffect, useState } from "react";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { newAuth } from "@/lib/auth_new";
import InviteFriendForm from "@/components/InviteFriendForm";
import ServiceOptimizer from "@/components/ServiceOptimizer";
import ReviewReplyAssistant from "@/components/ReviewReplyAssistant";
import NewsGenerator from "@/components/NewsGenerator";
import FinancialMetrics from "@/components/FinancialMetrics";
import ProgressTracker from "@/components/ProgressTracker";
import ROICalculator from "@/components/ROICalculator";
import TransactionForm from "@/components/TransactionForm";
import { BusinessSwitcher } from "@/components/BusinessSwitcher";
import { NetworkSwitcher } from "@/components/NetworkSwitcher";
import { NetworkDashboard } from "@/components/NetworkDashboard";
import TelegramConnection from "@/components/TelegramConnection";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";

function getNextReportDate(reports: any[]) {
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
  const [user, setUser] = useState<any>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [autoAnalysisUrl, setAutoAnalysisUrl] = useState('');
  const [autoAnalysisLoading, setAutoAnalysisLoading] = useState(false);
  const [form, setForm] = useState({ email: "", phone: "", name: "", yandexUrl: "" });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);
  const [timer, setTimer] = useState<string | null>(null);
  
  // Вкладки
  const [activeTab, setActiveTab] = useState<'overview' | 'finance' | 'progress' | 'network' | 'settings'>('overview');
  
  // Услуги
  const [userServices, setUserServices] = useState<any[]>([]);
  
  // Бизнесы (для суперадмина)
  const [businesses, setBusinesses] = useState<any[]>([]);
  const [currentBusinessId, setCurrentBusinessId] = useState<string | null>(null);
  const [currentBusiness, setCurrentBusiness] = useState<any>(null);
  
  // Сети
  const [networks, setNetworks] = useState<any[]>([]);
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
        businessType: business.business_type || "beauty_salon",
        address: business.address || "",
        workingHours: business.working_hours || ""
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
            workingHours: data.business.working_hours || ''
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

          // Обновляем ссылку на Яндекс.Карты для текущего бизнеса (если есть)
          if (data.business && data.business.yandex_url) {
            setYandexCardUrl(data.business.yandex_url);
          } else {
            setYandexCardUrl('');
          }
          
          console.log(`🔄 Переключились на бизнес: ${business.name}`);
          console.log(`📊 Загружено услуг: ${data.services?.length || 0}`);
          console.log(`📊 Данные бизнеса:`, data.business);
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
      setError('Введите ссылку на карточку Яндекс.Карт');
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
        setSuccess('Ссылка на Яндекс.Карты сохранена и синхронизация запущена');
      } else {
        setError(data.error || 'Не удалось сохранить ссылку на Яндекс.Карты');
      }
    } catch (e: any) {
      setError('Ошибка сохранения ссылки на Яндекс.Карты: ' + e.message);
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
  const [clientInfo, setClientInfo] = useState({
    businessName: '',
    businessType: '',
    address: '',
    workingHours: ''
  });
  const [editClientInfo, setEditClientInfo] = useState(false);
  const [savingClientInfo, setSavingClientInfo] = useState(false);
  const [yandexCardUrl, setYandexCardUrl] = useState<string>('');

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

  // Загрузка сетей пользователя
  const loadNetworks = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/networks`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.success && data.networks && data.networks.length > 0) {
        setNetworks(data.networks);
        // Если есть сети, выбираем первую
        if (!currentNetworkId) {
          setCurrentNetworkId(data.networks[0].id);
        }
      }
    } catch (e) {
      console.error('Ошибка загрузки сетей:', e);
    }
  };

  // Загрузка услуг пользователя
  const loadUserServices = async () => {
    setLoadingServices(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/list`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.success) {
        setUserServices(data.services || []);
      }
    } catch (e) {
      console.error('Ошибка загрузки услуг:', e);
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
    } catch (e: any) {
      setError('Ошибка добавления услуги: ' + e.message);
    }
  };

  // Обновление услуги
  const updateService = async (serviceId: string, updatedData: any) => {
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
    } catch (e: any) {
      setError('Ошибка обновления услуги: ' + e.message);
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
    } catch (e: any) {
      setError('Ошибка удаления услуги: ' + e.message);
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
      setError('Введите URL страницы Яндекс.Карт');
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
      setError('Введите URL карточки на Яндекс.Картах');
      return;
    }

    if (!autoAnalysisUrl.includes('yandex.ru/maps')) {
      setError('Введите корректную ссылку на Яндекс.Карты');
      return;
    }

    setAutoAnalysisLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('http://localhost:8000/api/analyze-card-auto', {
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
  const [cardAnalysis, setCardAnalysis] = useState<any>(null);
  const [priceListFile, setPriceListFile] = useState<File | null>(null);
  const [optimizingPriceList, setOptimizingPriceList] = useState(false);
  const [priceListOptimization, setPriceListOptimization] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Получаем текущего пользователя
        const currentUser = await newAuth.getCurrentUser();
        console.log('Текущий пользователь:', currentUser);
        
        if (!currentUser) {
          console.log('Пользователь не авторизован');
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
          console.log('Суперпользователь обнаружен, businesses из getCurrentUser:', currentUser.businesses);
          
          // Всегда загружаем businesses отдельно через API для надежности
          try {
            const response = await fetch('/api/auth/me', {
              headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
              }
            });
            if (response.ok) {
              const data = await response.json();
              console.log('Ответ /api/auth/me:', data);
              if (data.businesses && Array.isArray(data.businesses) && data.businesses.length > 0) {
                console.log(`Загружено ${data.businesses.length} бизнесов`);
                setBusinesses(data.businesses);
                const savedBusinessId = localStorage.getItem('selectedBusinessId');
                const businessToSelect = savedBusinessId 
                  ? data.businesses.find((b: any) => b.id === savedBusinessId) || data.businesses[0]
                  : data.businesses[0];
                
                setCurrentBusinessId(businessToSelect.id);
                setCurrentBusiness(businessToSelect);
                localStorage.setItem('selectedBusinessId', businessToSelect.id);
              } else {
                console.warn('Бизнесы не найдены в ответе API или пустой массив');
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
          console.log('Отчёты загружены:', userReports);
          setReports(userReports || []);
        }

        // Получаем очередь пользователя
        const { queue: userQueue, error: queueError } = await newAuth.getUserQueue();
        if (queueError) {
          console.error('Ошибка загрузки очереди:', queueError);
        } else {
          console.log('Очередь загружена:', userQueue);
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

    fetchData();
  }, []);

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
      const response = await fetch(`https://beautybot.pro/api/users/queue/${queueId}`, {
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
    // На первом шаге сохраняем ссылку на Яндекс.Карты, если она указана
    if (wizardStep === 1) {
      handleSaveYandexLink();
    }
    setWizardStep((s) => (s < 3 ? ((s + 1) as 1 | 2 | 3) : s));
  };
  const wizardPrev = () => setWizardStep((s) => (s > 1 ? ((s - 1) as 1 | 2 | 3) : s));

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
              <Button variant="outline" size="sm" onClick={() => setShowWizard(true)}>Мастер оптимизации</Button>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  try {
                    await newAuth.signOut();
                  } finally {
                    // Чистим локальные данные и уходим на страницу входа
                    try { localStorage.clear(); } catch {}
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
        <div className="mb-6 bg-gradient-to-br from-white via-gray-50/50 to-white rounded-lg border-2 border-gray-200 shadow-md p-4">
            <p className="text-gray-800 mb-2">👋 Добро пожаловать в <span className="font-semibold">BeautyBot.pro</span>!</p>
            {currentBusiness && (
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  <span className="font-medium">Текущий бизнес:</span> {currentBusiness.name}
                  {currentBusiness.description && (
                    <span className="block text-xs text-blue-600 mt-1">{currentBusiness.description}</span>
                  )}
                </p>
              </div>
            )}
            <p className="text-gray-600 text-sm">
              Это ваш личный центр управления ростом салона.
            </p>
            <p className="text-gray-600 text-sm mt-2">
              Заполните данные о себе и бизнесе — это первый шаг. Далее вы сможете совершенствовать процесс и отслеживать положительные изменения.
            </p>
            <p className="text-gray-600 text-sm mt-2">💡 Помните: вы платите только за результат — 7% от реального роста.</p>

            <div className="mt-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-gray-700">Заполненность профиля</span>
                <span className="text-sm font-medium text-orange-600">{profileCompletion}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded h-3 overflow-hidden">
                <div className={`h-3 rounded ${profileCompletion>=80 ? 'bg-green-500' : profileCompletion>=50 ? 'bg-yellow-500' : 'bg-orange-500'}`} style={{ width: `${profileCompletion}%` }} />
              </div>
            </div>
          </div>

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

          {/* Профиль пользователя */}
          <div className="mb-8 bg-gradient-to-br from-white via-gray-50 to-white rounded-lg border-2 border-gray-300 shadow-md p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">Профиль</h2>
              {!editMode && (
                <Button onClick={() => setEditMode(true)}>Редактировать</Button>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input 
                    type="email" 
                    value={form.email} 
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Имя</label>
                <input 
                  type="text" 
                  value={form.name} 
                  onChange={(e) => setForm({...form, name: e.target.value})}
                  disabled={!editMode}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
                <input 
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm({...form, phone: e.target.value})}
                  disabled={!editMode}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>
            {editMode && (
              <div className="mt-4 flex justify-end">
                <div className="flex gap-2">
                  <Button onClick={handleUpdateProfile}>Сохранить</Button>
                  <Button onClick={() => setEditMode(false)} variant="outline">Отмена</Button>
                </div>
              </div>
          )}
                  </div>
                  
          {/* Информация о бизнесе */}
          <div className="mb-8 bg-gradient-to-br from-white via-orange-50/30 to-white rounded-lg border-2 border-orange-200/50 shadow-md p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">Информация о бизнесе</h2>
              {!editClientInfo && (
                <Button onClick={() => setEditClientInfo(true)}>Редактировать</Button>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Название бизнеса</label>
                        <input 
                  type="text" 
                  value={clientInfo.businessName} 
                  onChange={(e) => setClientInfo({...clientInfo, businessName: e.target.value})}
                  disabled={!editClientInfo}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        />
                      </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Тип бизнеса</label>
                {editClientInfo ? (
                  <Select
                    value={clientInfo.businessType || "beauty_salon"}
                    onValueChange={(v) => setClientInfo({ ...clientInfo, businessType: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите тип" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="beauty_salon">Салон красоты</SelectItem>
                      <SelectItem value="barbershop">Барбершоп</SelectItem>
                      <SelectItem value="spa">SPA/Wellness</SelectItem>
                      <SelectItem value="nail_studio">Ногтевая студия</SelectItem>
                      <SelectItem value="cosmetology">Косметология</SelectItem>
                      <SelectItem value="massage">Массаж</SelectItem>
                      <SelectItem value="brows_lashes">Брови и ресницы</SelectItem>
                      <SelectItem value="makeup">Макияж</SelectItem>
                      <SelectItem value="tanning">Солярий</SelectItem>
                      <SelectItem value="other">Другое</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <input
                    type="text"
                    value={clientInfo.businessType}
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
                    readOnly
                  />
                )}
              </div>
                      <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Адрес</label>
                        <input 
                  type="text" 
                  value={clientInfo.address} 
                  onChange={(e) => setClientInfo({...clientInfo, address: e.target.value})}
                  disabled={!editClientInfo}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        />
                      </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Режим работы</label>
                <input 
                  type="text" 
                  value={clientInfo.workingHours} 
                  onChange={(e) => setClientInfo({...clientInfo, workingHours: e.target.value})}
                  disabled={!editClientInfo}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>
            {editClientInfo && (
              <div className="mt-4 flex justify-end">
                <div className="flex gap-2">
                  <Button onClick={handleSaveClientInfo} disabled={savingClientInfo}>
                    {savingClientInfo ? 'Сохранение...' : 'Сохранить'}
                        </Button>
                  <Button onClick={() => setEditClientInfo(false)} variant="outline">Отмена</Button>
                      </div>
                    </div>
                  )}
                </div>

          {/* Навигация по разделам */}
          <div className="mb-6 bg-gradient-to-r from-gray-50 to-white rounded-lg border-2 border-gray-200 shadow-sm p-4">
            <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
              <button
                onClick={() => setActiveTab('overview')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'overview'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                📊 Обзор
              </button>
              <button
                onClick={() => setActiveTab('finance')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'finance'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                💰 Финансы
              </button>
              <button
                onClick={() => setActiveTab('progress')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'progress'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                🎯 Прогресс
              </button>
              <button
                onClick={() => setActiveTab('settings')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'settings'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                ⚙️ Настройки
              </button>
          </div>

            {/* Контент вкладок */}
            <div className="mt-6">
          {/* Финансовая панель */}
          {activeTab === 'finance' && (
                <div className="space-y-6">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold text-gray-900">💰 Финансовая панель</h2>
                <Button 
                  onClick={() => setShowTransactionForm(!showTransactionForm)}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {showTransactionForm ? 'Скрыть форму' : '+ Добавить транзакцию'}
                </Button>
              </div>

              {showTransactionForm && (
                <TransactionForm 
                  onSuccess={() => {
                    setShowTransactionForm(false);
                    setSuccess('Транзакция добавлена успешно!');
                  }}
                  onCancel={() => setShowTransactionForm(false)}
                />
              )}

              <FinancialMetrics />
              <ROICalculator />
            </div>
          )}

          {/* Прогресс-трекер */}
          {activeTab === 'progress' && (
                <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900">🎯 Ваш прогресс</h2>
              <ProgressTracker />
            </div>
          )}

          {/* Настройки */}
          {activeTab === 'settings' && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900">⚙️ Настройки</h2>
              <TelegramConnection />
            </div>
          )}

          {/* Дашборд сети */}
          {activeTab === 'network' && currentNetworkId && (
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold text-gray-900">🌐 Дашборд сети</h2>
                <NetworkSwitcher
                  networkId={currentNetworkId}
                  currentLocationId={currentLocationId || undefined}
                  onLocationChange={(locationId) => {
                    setCurrentLocationId(locationId);
                    // Можно обновить данные при переключении точки
                  }}
                />
              </div>
              <NetworkDashboard networkId={currentNetworkId} />
            </div>
          )}

          {/* Основной контент (показывается на вкладке overview) */}
          {activeTab === 'overview' && (
            <>
                  {/* Таблица услуг (Обзор) */}
            <div className="mb-8 bg-gradient-to-br from-white via-orange-50/20 to-white rounded-lg border-2 border-orange-200/50 shadow-md p-4">
                    <div className="flex justify-between items-center mb-4">
                      <div className="flex-1 pr-4">
                        <h2 className="text-xl font-semibold text-gray-900">Услуги</h2>
                        <p className="text-sm text-gray-600 mt-1">
                          📋 Ниже в блоке "Настройте описания услуг для карточки компании на картах" загрузите ваш прайс-лист, мы обработаем наименования и описания услуг так, чтобы чаще появляться в поиске. 
                          <br/><br/>
                          Эти наименования сохранятся в ваш список услуг автоматически. 
                          <br/><br/>
                          Вы также можете внести их вручную или потом отредактировать.
                        </p>
                    </div>
                      <Button onClick={() => setShowAddService(true)}>+ Добавить услугу</Button>
        </div>

                    {/* Форма добавления услуги */}
                    {showAddService && (
                      <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <h3 className="text-lg font-medium text-gray-900 mb-4">Добавить новую услугу</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Категория</label>
                <input 
                  type="text" 
                              value={newService.category}
                              onChange={(e) => setNewService({...newService, category: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                              placeholder="Например: Стрижки"
                />
              </div>
              <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Название *</label>
                <input 
                  type="text" 
                              value={newService.name}
                              onChange={(e) => setNewService({...newService, name: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                              placeholder="Например: Женская стрижка"
                />
              </div>
              <div className="md:col-span-2">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Описание</label>
                <textarea 
                              value={newService.description}
                              onChange={(e) => setNewService({...newService, description: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  rows={3}
                              placeholder="Краткое описание услуги"
                />
              </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Ключевые слова</label>
                            <input
                              type="text"
                              value={newService.keywords}
                              onChange={(e) => setNewService({...newService, keywords: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                              placeholder="стрижка, укладка, окрашивание"
                />
              </div>
              <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Цена</label>
                            <input
                              type="text"
                              value={newService.price}
                              onChange={(e) => setNewService({...newService, price: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                              placeholder="Например: 2000 руб"
                />
              </div>
                  </div>
                        <div className="flex gap-2 mt-4">
                          <Button onClick={addService}>Добавить</Button>
                          <Button onClick={() => setShowAddService(false)} variant="outline">Отмена</Button>
                </div>
            </div>
                    )}

                    <div className="overflow-x-auto bg-white border border-gray-200 rounded-lg">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Категория</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Название</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Описание</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Цена</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Действия</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {loadingServices ? (
                            <tr>
                              <td className="px-4 py-3 text-gray-500" colSpan={5}>Загрузка услуг...</td>
                            </tr>
                          ) : userServices.length === 0 ? (
                            <tr>
                              <td className="px-4 py-3 text-gray-500" colSpan={5}>Данные появятся после добавления услуг</td>
                            </tr>
                          ) : (
                            userServices.map((service, index) => (
                              <tr key={service.id || index}>
                                <td className="px-4 py-3 text-sm text-gray-900">{service.category}</td>
                                <td className="px-4 py-3 text-sm font-medium text-gray-900">{service.name}</td>
                                <td className="px-4 py-3 text-sm text-gray-600">{service.description}</td>
                                <td className="px-4 py-3 text-sm text-gray-600">{service.price || '—'}</td>
                                <td className="px-4 py-3 text-sm">
                                  <div className="flex gap-2">
                  <Button 
                                      size="sm" 
                                      variant="outline" 
                                      onClick={() => setEditingService(service.id)}
                                    >
                                      Редактировать
                  </Button>
                    <Button 
                      size="sm"
                                      variant="outline" 
                                      onClick={() => deleteService(service.id)}
                                      className="text-red-600 hover:text-red-700"
                    >
                      Удалить
                    </Button>
                  </div>
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
                    
          {/* Работа с Яндекс Картами (сворачиваемый блок) */}
          <div className="mb-8 bg-gradient-to-br from-white via-gray-50 to-white rounded-lg border-2 border-gray-300 shadow-md">
            <Accordion type="single" collapsible defaultValue="yamaps-tools">
              <AccordionItem value="yamaps-tools">
                <AccordionTrigger className="px-4">
                  <span className="text-xl font-semibold text-gray-900">Работа с Яндекс Картами</span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-8">
                    <div className="bg-white rounded-lg border border-gray-200 p-4">
                      <ServiceOptimizer businessName={clientInfo.businessName} businessId={currentBusinessId} />
                    </div>
                    <div className="bg-white rounded-lg border border-gray-200 p-4">
                      <ReviewReplyAssistant businessName={clientInfo.businessName} />
                    </div>
                    <div className="bg-white rounded-lg border border-gray-200 p-4">
                      <NewsGenerator services={(userServices||[]).map(s=>({ id: s.id, name: s.name }))} />
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>

          {/* Приглашения */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Пригласить друга</h2>
            <InviteFriendForm
              onSuccess={() => setInviteSuccess(true)}
              onError={(error) => setError(error)}
            />
            {inviteSuccess && (
              <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mt-4">
                Приглашение отправлено!
              </div>
            )}
        </div>

      {/* Модальное окно мастера оптимизации - полупрозрачный оверлей */}
      {showWizard && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[100]" onClick={() => setShowWizard(false)}>
          <div className="bg-white/95 backdrop-blur-md rounded-lg max-w-4xl max-h-[90vh] w-full mx-4 overflow-hidden shadow-2xl border-2 border-gray-300" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center p-4 border-b border-gray-200 bg-gradient-to-r from-white to-gray-50">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-gray-900">Мастер оптимизации бизнеса</h2>
                <span className="text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded">Шаг {wizardStep}/3</span>
              </div>
              <Button onClick={() => setShowWizard(false)} variant="outline" size="sm">✕</Button>
            </div>
            <div className="p-6 overflow-auto max-h-[calc(90vh-120px)] bg-gradient-to-br from-white to-gray-50/50">
              {/* Шаг 1 */}
              {wizardStep === 1 && (
                <div className="space-y-4">
                  <p className="text-gray-600 mb-4">Соберём ключевые данные по карточке, чтобы дать точные рекомендации Яндекса.</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Вставьте ссылку на карточку вашего салона в Яндекс.Картах.
                      </label>
                      <input
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        placeholder="https://yandex.ru/maps/org/..."
                        value={yandexCardUrl}
                        onChange={(e) => setYandexCardUrl(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Рейтинг (0–5)</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="4.6" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Количество отзывов</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="128" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Частота обновления фото</label>
                      <div className="flex flex-wrap gap-2">
                        {['Еженедельно','Ежемесячно','Раз в квартал','Редко','Не знаю'].map(x => (
                          <span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>
                        ))}
                      </div>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">Новости (наличие/частота)</label>
                      <div className="flex flex-wrap gap-2 mb-3">
                        {['Да','Нет'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>))}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {['Еженедельно','Ежемесячно','Реже','По событию'].map(x => (
                          <span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>
                        ))}
                      </div>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Текущие тексты/услуги</label>
                      <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={5} placeholder={"Стрижка мужская\nСтрижка женская\nОкрашивание"} />
                    </div>
                  </div>
                </div>
              )}
              {/* Шаг 2 */}
              {wizardStep === 2 && (
                <div className="space-y-4">
                  <p className="text-gray-600 mb-4">Опишите, как вы хотите звучать и чего избегать. Это задаст тон для всех текстов.</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">What do you like?</label>
                      <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Лаконично, экспертно, заботливо, премиально…" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">What do you dislike?</label>
                      <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Без клише, без канцелярита, без агрессивных продаж…" />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">Понравившиеся формулировки (до 5)</label>
                      <div className="space-y-2">
                        {[1,2,3,4,5].map(i => (
                          <input key={i} className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Например: Стрижка, которая держит форму и не требует укладки" />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {/* Шаг 3 */}
              {wizardStep === 3 && (
                <div className="space-y-4">
                  <p className="text-gray-600 mb-4">Немного цифр, чтобы план был реалистичным. Можно заполнить позже.</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Как давно работаете</label>
                      <div className="flex flex-wrap gap-2">
                        {['0–6 мес','6–12 мес','1–3 года','3+ лет'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Постоянные клиенты</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="например, 150" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">CRM</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Например: Yclients" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Расположение</label>
                      <div className="flex flex-wrap gap-2">
                        {['Дом','ТЦ','Двор','Магистраль','Центр','Спальник','Около метро'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Средний чек (₽)</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="2200" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Выручка в месяц (₽)</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="350000" />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Что нравится/не нравится в карточке</label>
                      <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Нравится: фото, тон. Не нравится: мало отзывов, нет новостей…" />
                    </div>
                  </div>
                </div>
              )}
              <div className="mt-6 flex justify-between pt-4 border-t border-gray-200">
                <Button variant="outline" onClick={wizardPrev} disabled={wizardStep===1}>Назад</Button>
                {wizardStep < 3 ? (
                  <Button onClick={wizardNext}>Продолжить</Button>
                ) : (
                  <Button onClick={() => {setShowWizard(false); window.location.href = "/sprint";}}>Сформировать план</Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно просмотра отчёта */}
        {viewingReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-4xl max-h-[90vh] w-full mx-4 overflow-hidden">
            <div className="flex justify-between items-center p-4 border-b">
              <h3 className="text-lg font-semibold">Просмотр отчёта</h3>
              <Button onClick={() => setViewingReport(null)} variant="outline">
                Закрыть
              </Button>
            </div>
            <div className="p-4 overflow-auto max-h-[calc(90vh-80px)]">
              {loadingReport ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
                  <p className="mt-2 text-gray-600">Загрузка отчёта...</p>
                </div>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: reportContent }} />
              )}
            </div>
          </div>
        </div>
        )}

      </div>
      <Footer />
    </div>
  );
};

export default Dashboard;
