import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import ReviewReplyAssistant from '@/components/ReviewReplyAssistant';
import NewsGenerator from '@/components/NewsGenerator';
import ServiceOptimizer from '@/components/ServiceOptimizer';

export const CardOverviewPage = () => {
  const context = useOutletContext<any>();
  const { user, currentBusinessId, currentBusiness } = context || {};
  
  // Состояния для рейтинга и отзывов
  const [rating, setRating] = useState<number | null>(null);
  const [reviewsTotal, setReviewsTotal] = useState<number>(0);
  const [loadingSummary, setLoadingSummary] = useState(false);
  
  // Состояния для услуг
  const [userServices, setUserServices] = useState<any[]>([]);
  const [loadingServices, setLoadingServices] = useState(false);
  const [servicesCurrentPage, setServicesCurrentPage] = useState(1);
  const servicesItemsPerPage = 10;
  const [showAddService, setShowAddService] = useState(false);
  const [editingService, setEditingService] = useState<string | null>(null);
  const [editingForm, setEditingForm] = useState({
    category: '',
    name: '',
    description: '',
    keywords: '',
    price: ''
  });
  const [newService, setNewService] = useState({
    category: '',
    name: '',
    description: '',
    keywords: '',
    price: ''
  });
  const [optimizingServiceId, setOptimizingServiceId] = useState<string | null>(null);
  
  // Обновить форму при выборе услуги для редактирования
  useEffect(() => {
    if (!editingService) return;
    
    const service = userServices.find(s => s.id === editingService);
    if (!service) return;
    
    setEditingForm({
      category: service.category || '',
      name: service.name || '',
      description: service.description || '',
      keywords: Array.isArray(service.keywords) ? service.keywords.join(', ') : (service.keywords || ''),
      price: service.price || ''
    });
  }, [editingService, userServices]);
  
  // Состояния для отзывов
  const [externalReviews, setExternalReviews] = useState<any[]>([]);
  const [loadingReviews, setLoadingReviews] = useState(false);
  
  // Состояния для новостей
  const [externalPosts, setExternalPosts] = useState<any[]>([]);
  const [loadingPosts, setLoadingPosts] = useState(false);
  
  // Состояния для парсера
  const [parseStatus, setParseStatus] = useState<'idle' | 'processing' | 'done' | 'error' | 'queued'>('idle');
  
  // Общие состояния
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState<2>(2);
  // Настройки для мастера оптимизации
  const [wizardTone, setWizardTone] = useState<'friendly' | 'professional' | 'premium' | 'youth' | 'business'>('professional');
  const [wizardRegion, setWizardRegion] = useState('');
  const [wizardLength, setWizardLength] = useState(150);
  const [wizardInstructions, setWizardInstructions] = useState('');

  // Загрузка сводки (рейтинг, количество отзывов)
  const loadSummary = async () => {
    if (!currentBusinessId) return;
    setLoadingSummary(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/external/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setRating(data.rating);
        setReviewsTotal(data.reviews_total || 0);
      }
    } catch (e) {
      console.error('Ошибка загрузки сводки:', e);
    } finally {
      setLoadingSummary(false);
    }
  };

  // Загрузка услуг
  const loadUserServices = async () => {
    if (!currentBusinessId) {
      setUserServices([]);
      return;
    }
    
    console.log('🔍 DEBUG loadUserServices: Загружаем услуги для business_id:', currentBusinessId);
    setLoadingServices(true);
    try {
      const token = localStorage.getItem('auth_token');
      const qs = currentBusinessId ? `?business_id=${currentBusinessId}` : '';
      const response = await fetch(`${window.location.origin}/api/services/list${qs}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.success) {
        // Находим обновленную услугу по ID для отладки
        const updatedService = data.services?.find((s: any) => s.id === '3772931e-9796-475b-b439-ee1cc07b1dc9');
        
        // Детальный лог для отладки
        if (updatedService) {
          console.log('🔍 DEBUG loadUserServices: ДЕТАЛЬНЫЙ ЛОГ updatedService', {
            id: updatedService.id,
            name: updatedService.name,
            optimized_name: updatedService.optimized_name,
            optimized_name_type: typeof updatedService.optimized_name,
            optimized_name_length: updatedService.optimized_name?.length,
            has_optimized_name: !!updatedService.optimized_name,
            description: updatedService.description,
            optimized_description: updatedService.optimized_description,
            optimized_description_type: typeof updatedService.optimized_description,
            optimized_description_length: updatedService.optimized_description?.length,
            has_optimized_description: !!updatedService.optimized_description,
            allKeys: Object.keys(updatedService),
            fullService: updatedService // Полный объект для проверки
          });
        } else {
          console.log('❌ DEBUG loadUserServices: Услуга 3772931e-9796-475b-b439-ee1cc07b1dc9 не найдена в списке');
        }
        
        console.log('✅ DEBUG loadUserServices: Услуги загружены', {
          count: data.services?.length,
          firstService: data.services?.[0],
          firstServiceOptimized: data.services?.[0] ? {
            id: data.services[0].id,
            name: data.services[0].name,
            optimized_name: data.services[0].optimized_name,
            has_optimized_name: !!data.services[0].optimized_name,
            description: data.services[0].description,
            optimized_description: data.services[0].optimized_description,
            has_optimized_description: !!data.services[0].optimized_description
          } : null,
          updatedService: updatedService ? {
            id: updatedService.id,
            name: updatedService.name,
            optimized_name: updatedService.optimized_name,
            has_optimized_name: !!updatedService.optimized_name,
            description: updatedService.description,
            optimized_description: updatedService.optimized_description,
            has_optimized_description: !!updatedService.optimized_description,
            allKeys: Object.keys(updatedService)
          } : 'Услуга не найдена'
        });
        setUserServices(data.services || []);
      } else {
        console.error('❌ DEBUG loadUserServices: Ошибка загрузки услуг', data.error);
      }
    } catch (e) {
      console.error('❌ Ошибка загрузки услуг:', e);
    } finally {
      setLoadingServices(false);
    }
  };

  // Загрузка отзывов из парсера
  const loadExternalReviews = async () => {
    if (!currentBusinessId) return;
    setLoadingReviews(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/external/reviews`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setExternalReviews(data.reviews || []);
      }
    } catch (e) {
      console.error('Ошибка загрузки отзывов:', e);
    } finally {
      setLoadingReviews(false);
    }
  };

  // Загрузка новостей из парсера
  const loadExternalPosts = async () => {
    if (!currentBusinessId) return;
    setLoadingPosts(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/external/posts`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setExternalPosts(data.posts || []);
      }
    } catch (e) {
      console.error('Ошибка загрузки новостей:', e);
    } finally {
      setLoadingPosts(false);
    }
  };

  useEffect(() => {
    if (currentBusinessId && context) {
      loadSummary();
      loadUserServices();
      loadExternalReviews();
      loadExternalPosts();
    }
  }, [currentBusinessId, context]);
  
  // Если контекст не загружен, показываем загрузку
  if (!context) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  // Запуск парсера
  const handleRunParser = async () => {
    if (!currentBusinessId) {
      setError('Сначала выберите бизнес');
      return;
    }
    
    setParseStatus('processing');
    setError(null);
    setSuccess(null);
    try {
      const token = localStorage.getItem('auth_token');
      console.log('🚀 Запуск парсера для бизнеса:', currentBusinessId);
      const response = await fetch(`${window.location.origin}/api/admin/yandex/sync/business/${currentBusinessId}`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      console.log('📡 Ответ сервера:', response.status, response.statusText);
      
      let data;
      try {
        data = await response.json();
        console.log('📦 Данные ответа:', data);
      } catch (jsonError) {
        const text = await response.text();
        console.error('❌ Ошибка парсинга JSON:', text);
        setParseStatus('error');
        setError(`Ошибка сервера (${response.status}): ${text.substring(0, 200)}`);
        return;
      }
      
      if (response.ok && data.success) {
        setParseStatus('done');
        setSuccess(data.message || 'Парсер запущен успешно');
        // Перезагружаем данные
        setTimeout(() => {
          loadSummary();
          loadExternalReviews();
          loadExternalPosts();
        }, 2000);
      } else {
        setParseStatus('error');
        const errorMsg = data.error || data.message || 'Ошибка запуска парсера';
        console.error('❌ Ошибка парсера:', errorMsg);
        setError(errorMsg);
      }
    } catch (e: any) {
      console.error('❌ Исключение при запуске парсера:', e);
      setParseStatus('error');
      setError('Ошибка запуска парсера: ' + (e.message || String(e)));
    }
  };

  // Добавление услуги
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

  // Оптимизация услуги
  const optimizeService = async (serviceId: string) => {
    const service = userServices.find(s => s.id === serviceId);
    if (!service) return;
    
    setOptimizingServiceId(serviceId);
    setError(null);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/optimize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          text: service.name + (service.description ? '\n' + service.description : ''),
          business_id: currentBusinessId
        })
      });
      
      const data = await response.json();
      console.log('🔍 DEBUG optimizeService: Ответ от API', {
        success: data.success,
        result: data.result,
        services: data.result?.services,
        firstService: data.result?.services?.[0]
      });
      
      if (data.success && data.result?.services?.length > 0) {
        const optimized = data.result.services[0];
        console.log('🔍 DEBUG optimizeService: Оптимизированная услуга', optimized);
        
        // ВАЖНО: Сохраняем оригинальное описание и название, оптимизированные - отдельно
        // Исправляем keywords - убираем вложенные массивы и строки
        let fixedKeywords = [];
        if (Array.isArray(service.keywords)) {
          fixedKeywords = service.keywords.map(k => {
            if (typeof k === 'string') {
              try {
                const parsed = JSON.parse(k);
                return Array.isArray(parsed) ? parsed : [k];
              } catch {
                return [k];
              }
            }
            return Array.isArray(k) ? k : [k];
          }).flat();
        } else if (service.keywords) {
          try {
            const parsed = JSON.parse(service.keywords);
            fixedKeywords = Array.isArray(parsed) ? parsed : [service.keywords];
          } catch {
            fixedKeywords = typeof service.keywords === 'string' ? [service.keywords] : [];
          }
        }
        
        const updateData = {
          category: service.category || '', // Сохраняем все оригинальные поля
          name: service.name || '', // Оригинальное название не меняем
          optimized_name: optimized.optimized_name || optimized.optimizedName || '', // SEO название сохраняем отдельно
          description: service.description || '', // Оригинальное описание НЕ меняем - это ключевой момент!
          optimized_description: optimized.seo_description || optimized.seoDescription || '', // SEO описание сохраняем отдельно
          keywords: fixedKeywords, // Исправленные ключевые слова
          price: service.price || '' // Оригинальная цена
        };
        
        console.log('🔍 DEBUG optimizeService: Обновляем услугу', {
          serviceId,
          originalName: service.name,
          optimizedName: optimized.optimized_name || optimized.optimizedName,
          originalDescription: service.description,
          optimizedDescription: optimized.seo_description || optimized.seoDescription,
          optimizedObject: optimized, // Полный объект для отладки
          updateData
        });
        
        // Обновляем услугу - сохраняем оптимизированное описание отдельно, оригинальное НЕ меняем
        try {
          await updateService(serviceId, updateData);
          setSuccess('Услуга оптимизирована. Оптимизированное описание сохранено отдельно.');
          // Перезагружаем услуги, чтобы показать обновленные данные
          await loadUserServices();
        } catch (updateError: any) {
          console.error('❌ Ошибка обновления услуги:', updateError);
          setError('Ошибка сохранения оптимизированного описания: ' + (updateError.message || 'Неизвестная ошибка'));
          throw updateError; // Пробрасываем дальше, чтобы finally сработал
        }
      } else {
        setError(data.error || 'Ошибка оптимизации');
      }
    } catch (e: any) {
      setError('Ошибка оптимизации: ' + e.message);
    } finally {
      setOptimizingServiceId(null);
    }
  };

  // Обновление услуги
  const updateService = async (serviceId: string, updatedData: any) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(`${window.location.origin}/api/services/update/${serviceId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(updatedData)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
      throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    if (data.success) {
      setEditingService(null);
      await loadUserServices();
      setSuccess('Услуга обновлена');
    } else {
      throw new Error(data.error || 'Ошибка обновления услуги');
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

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Работа с картами</h1>
          <p className="text-gray-600 mt-1">Управляйте услугами и оптимизируйте карточку организации</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowWizard(true)}>Мастер оптимизации карт</Button>
        </div>
      </div>

      {/* Пояснение о парсинге */}
      <p className="text-xs text-gray-500 text-right">
        Раз в неделю мы будем получать данные, чтобы отслеживать прогресс и давать советы по оптимизации. Данные с карт будут сохраняться тут, а статистика на{' '}
        <a href="/dashboard/progress" className="text-blue-600 underline" target="_blank" rel="noreferrer">
          вкладке Прогресс
        </a>.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
          {success}
        </div>
      )}

      {/* Блок с рейтингом и количеством отзывов */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-4">
          {loadingSummary ? (
            <div className="text-gray-500">Загрузка...</div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <span className="text-3xl font-bold text-gray-900">
                  {rating !== null ? rating.toFixed(1) : '—'}
                </span>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <span
                      key={star}
                      className={`text-2xl ${
                        rating !== null && star <= Math.floor(rating)
                          ? 'text-yellow-400'
                          : rating !== null && star === Math.ceil(rating) && rating % 1 >= 0.5
                          ? 'text-yellow-400'
                          : 'text-gray-300'
                      }`}
                    >
                      ★
                    </span>
                  ))}
                </div>
              </div>
              <div className="text-gray-600">
                <span className="font-medium">{reviewsTotal}</span> отзывов
              </div>
            </>
          )}
        </div>
      </div>

      {/* Услуги */}
      <div className="bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
        boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
      }}>
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Услуги</h2>
            <p className="text-sm text-gray-600 mt-1">
              Текущий вид формулировок услуг на картах. Если есть подключение к парсеру, данные добавляются автоматически.
            </p>
          </div>
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

        {/* Функционал оптимизатора услуг (только загрузка файла) */}
        <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-gray-900 mb-1">Настройте описания услуг для карточки компании на картах</h2>
            <p className="text-sm text-gray-600">🔎 Карты и локальное SEO — это один из самых эффективных каналов продаж.</p>
            <p className="text-sm text-gray-600 mt-2">Правильные названия и описания услуг повышают видимость в поиске, клики на карточку и позиции в выдаче.</p>
            <p className="text-sm text-gray-600 mt-2">Загрузите прайс‑лист — ИИ вернёт краткие SEO‑формулировки в строгом формате с учётом частотности запросов, ваших формулировок и вашего местоположения.</p>
            <p className="text-sm text-gray-600 mt-2">Скопируйте текст и добавьте его в карточку вашей организации на картах.</p>
          </div>
          <div className="flex gap-2 items-center">
            <Button onClick={() => setShowAddService(true)}>+ Добавить услугу</Button>
            <ServiceOptimizer 
              businessName={currentBusiness?.name} 
              businessId={currentBusinessId}
              tone={wizardTone}
              region={wizardRegion}
              descriptionLength={wizardLength}
              instructions={wizardInstructions}
              hideTextInput={true}
            />
            {userServices.length > 0 && (
              <Button 
                variant="outline" 
                onClick={() => {
                  // Оптимизировать все услуги
                  userServices.forEach(s => optimizeService(s.id));
                }}
              >
                Оптимизировать все
              </Button>
            )}
          </div>
        </div>

        {/* Список услуг */}
        <div className="overflow-x-auto">
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
                userServices
                  .slice((servicesCurrentPage - 1) * servicesItemsPerPage, servicesCurrentPage * servicesItemsPerPage)
                  .map((service, index) => (
                  <tr key={service.id || index}>
                    <td className="px-4 py-3 text-sm text-gray-900">{service.category}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      <div className="space-y-3">
                        {service.name && (
                          <div className="text-gray-900">{service.name}</div>
                        )}
                        {service.optimized_name && (
                          <div className="bg-gray-50 border border-gray-200 rounded-md p-3 space-y-2">
                            <div className="text-xs text-gray-500 uppercase tracking-wide font-medium mb-1">Предложение SEO</div>
                            <div className="text-gray-800 leading-relaxed">{service.optimized_name}</div>
                            <div className="flex gap-2 pt-1">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  await updateService(service.id, {
                                    category: service.category,
                                    name: service.optimized_name,
                                    optimized_name: '',
                                    description: service.description,
                                    optimized_description: service.optimized_description,
                                    keywords: service.keywords,
                                    price: service.price
                                  });
                                  setSuccess('Оптимизированное название принято');
                                  await loadUserServices();
                                }}
                                className="text-xs h-7 border-gray-300 hover:bg-gray-100"
                              >
                                Принять
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  await updateService(service.id, {
                                    category: service.category,
                                    name: service.name,
                                    optimized_name: '',
                                    description: service.description,
                                    optimized_description: service.optimized_description,
                                    keywords: service.keywords,
                                    price: service.price
                                  });
                                  setSuccess('Оптимизированное название отклонено');
                                  await loadUserServices();
                                }}
                                className="text-xs h-7 border-gray-300 text-gray-600 hover:bg-gray-100"
                              >
                                Отклонить
                              </Button>
                            </div>
                          </div>
                        )}
                        {!service.name && !service.optimized_name && (
                          <span className="text-gray-400">—</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      <div className="space-y-3">
                        {service.description && (
                          <div className="text-gray-700 leading-relaxed">{service.description}</div>
                        )}
                        {service.optimized_description && (
                          <div className="bg-gray-50 border border-gray-200 rounded-md p-3 space-y-2">
                            <div className="text-xs text-gray-500 uppercase tracking-wide font-medium mb-1">Предложение SEO</div>
                            <div className="text-gray-800 leading-relaxed">{service.optimized_description}</div>
                            <div className="flex gap-2 pt-1">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  await updateService(service.id, {
                                    category: service.category,
                                    name: service.name,
                                    description: service.optimized_description,
                                    optimized_description: '',
                                    keywords: service.keywords,
                                    price: service.price
                                  });
                                  setSuccess('Оптимизированное описание принято');
                                  await loadUserServices();
                                }}
                                className="text-xs h-7 border-gray-300 hover:bg-gray-100"
                              >
                                Принять
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  await updateService(service.id, {
                                    category: service.category,
                                    name: service.name,
                                    description: service.description,
                                    optimized_description: '',
                                    keywords: service.keywords,
                                    price: service.price
                                  });
                                  setSuccess('Оптимизированное описание отклонено');
                                  await loadUserServices();
                                }}
                                className="text-xs h-7 border-gray-300 text-gray-600 hover:bg-gray-100"
                              >
                                Отклонить
                              </Button>
                            </div>
                          </div>
                        )}
                        {!service.description && !service.optimized_description && (
                          <span className="text-gray-400">—</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{service.price || '—'}</td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="outline" 
                          onClick={() => optimizeService(service.id)}
                          disabled={optimizingServiceId === service.id}
                        >
                          {optimizingServiceId === service.id ? 'Оптимизация...' : 'Оптимизировать'}
                        </Button>
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
          
          {/* Пагинация для услуг */}
          {userServices.length > servicesItemsPerPage && (
            <div className="flex items-center justify-between mt-4 px-4">
              <div className="text-sm text-gray-600">
                Показано {((servicesCurrentPage - 1) * servicesItemsPerPage) + 1}-{Math.min(servicesCurrentPage * servicesItemsPerPage, userServices.length)} из {userServices.length}
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setServicesCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={servicesCurrentPage === 1}
                >
                  Назад
                </Button>
                <span className="px-3 py-1 text-sm text-gray-700">
                  Страница {servicesCurrentPage} из {Math.ceil(userServices.length / servicesItemsPerPage)}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setServicesCurrentPage(prev => Math.min(Math.ceil(userServices.length / servicesItemsPerPage), prev + 1))}
                  disabled={servicesCurrentPage >= Math.ceil(userServices.length / servicesItemsPerPage)}
                >
                  Вперед
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Отзывы */}
      <div className="bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
        boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
      }}>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Отзывы</h2>
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
          <ReviewReplyAssistant businessName={currentBusiness?.name} />
        </div>
      </div>

      {/* Новости */}
      <div className="bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
        boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
      }}>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Новости</h2>
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
          <NewsGenerator 
            services={(userServices||[]).map(s=>({ id: s.id, name: s.name }))} 
            businessId={currentBusinessId}
            externalPosts={externalPosts}
          />
        </div>
      </div>

      {/* Модальное окно мастера оптимизации */}
      {showWizard && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[100]" onClick={() => setShowWizard(false)}>
          <div className="bg-white/95 backdrop-blur-md rounded-lg max-w-4xl max-h-[90vh] w-full mx-4 overflow-hidden shadow-2xl border-2 border-gray-300" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center p-4 border-b border-gray-200 bg-gradient-to-r from-white to-gray-50">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-gray-900">Мастер оптимизации карт</h2>
              </div>
              <Button onClick={() => setShowWizard(false)} variant="outline" size="sm">✕</Button>
            </div>
            <div className="p-6 overflow-auto max-h-[calc(90vh-120px)] bg-gradient-to-br from-white to-gray-50/50">
              {/* Шаг 2 */}
              {wizardStep === 2 && (
                <div className="space-y-4">
                  <p className="text-gray-600 mb-4">Опишите, как вы хотите звучать и чего избегать. Это задаст тон для всех текстов.</p>
                  
                  {/* Тон */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Тон</label>
                    <div className="flex flex-wrap gap-2">
                      {[
                        { key: 'friendly', label: 'Дружелюбный' },
                        { key: 'professional', label: 'Профессиональный' },
                        { key: 'premium', label: 'Премиум' },
                        { key: 'youth', label: 'Молодёжный' },
                        { key: 'business', label: 'Деловой' }
                      ].map(tone => (
                        <button 
                          key={tone.key} 
                          type="button"
                          onClick={() => setWizardTone(tone.key as any)}
                          className={`text-xs px-3 py-1 rounded-full border ${
                            wizardTone === tone.key 
                              ? 'bg-blue-600 text-white border-blue-600' 
                              : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                          }`}
                        >
                          {tone.label}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Примеры формулировок для выбранного тона появятся автоматически в подсказках.</p>
                  </div>

                  {/* Регион и длина описания */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Регион (для локального SEO)</label>
                      <input 
                        type="text"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        placeholder="Санкт‑Петербург, м. Чернышевская"
                        value={wizardRegion}
                        onChange={(e) => setWizardRegion(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Длина описания (символов)</label>
                      <input 
                        type="number"
                        min={80}
                        max={200}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        value={wizardLength}
                        onChange={(e) => setWizardLength(Number(e.target.value) || 150)}
                      />
                    </div>
                  </div>

                  {/* Дополнительные инструкции */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Дополнительные инструкции (необязательно)</label>
                    <textarea 
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      rows={3}
                      placeholder="Например: только безаммиачные красители; подчеркнуть опыт мастеров; указать гарантию; избегать эмодзи."
                      value={wizardInstructions}
                      onChange={(e) => setWizardInstructions(e.target.value)}
                    />
                  </div>

                  {/* Формулировки ответов на отзывы */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Понравившиеся формулировки ответов на отзывы (до 5)</label>
                    <div className="space-y-2">
                      {[1,2,3,4,5].map(i => (
                        <input 
                          key={i} 
                          className="w-full px-3 py-2 border border-gray-300 rounded-md" 
                          placeholder="Например: Спасибо за отзыв! Нам важно ваше мнение" 
                        />
                      ))}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Эти формулировки будут использоваться при генерации ответов на отзывы.</p>
                  </div>
                </div>
              )}
              <div className="mt-6 flex justify-end pt-4 border-t border-gray-200">
                <Button onClick={() => setShowWizard(false)}>Готово</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
