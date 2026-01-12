import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import ServiceOptimizer from '@/components/ServiceOptimizer';
import { useLanguage } from '@/i18n/LanguageContext';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { Wand2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ReviewReplyAssistant from "@/components/ReviewReplyAssistant";
import NewsGenerator from "@/components/NewsGenerator";

export const CardOverviewPage = () => {
  const context = useOutletContext<any>();
  const { user, currentBusinessId, currentBusiness } = context || {};
  const { t, language } = useLanguage();

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
  const [newService, setNewService] = useState({
    category: '',
    name: '',
    description: '',
    keywords: '',
    price: ''
  });
  const [optimizingServiceId, setOptimizingServiceId] = useState<string | null>(null);

  // Состояния для парсера
  const [parseStatus, setParseStatus] = useState<'idle' | 'processing' | 'done' | 'error' | 'queued'>('idle');

  // Общие состояния
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(false);

  // Wizard settings
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

    setLoadingServices(true);
    try {
      const token = localStorage.getItem('auth_token');
      const qs = currentBusinessId ? `?business_id=${currentBusinessId}` : '';
      const response = await fetch(`${window.location.origin}/api/services/list${qs}`, {
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

  useEffect(() => {
    if (currentBusinessId && context) {
      loadSummary();
      loadUserServices();
    }
  }, [currentBusinessId, context]);

  // Если контекст не загружен, показываем загрузку
  if (!context) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">{t.dashboard.subscription.processing}</p>
        </div>
      </div>
    );
  }

  // Добавление услуги
  const addService = async () => {
    if (!newService.name.trim()) {
      setError(t.dashboard.card.serviceName + ' required');
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
        setSuccess(t.success);
      } else {
        setError(data.error || t.error);
      }
    } catch (e: any) {
      setError(t.error + ': ' + e.message);
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

      if (data.success && data.result?.services?.length > 0) {
        const optimized = data.result.services[0];

        // Исправляем keywords
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
          fixedKeywords = typeof service.keywords === 'string' ? [service.keywords] : [];
        }

        const updateData = {
          category: service.category || '',
          name: service.name || '',
          optimized_name: optimized.optimized_name || optimized.optimizedName || '',
          description: service.description || '',
          optimized_description: optimized.seo_description || optimized.seoDescription || '',
          keywords: fixedKeywords,
          price: service.price || ''
        };

        try {
          await updateService(serviceId, updateData);
          setSuccess(t.success);
          await loadUserServices();
        } catch (updateError: any) {
          setError(t.error);
        }
      } else {
        setError(data.error || t.error);
      }
    } catch (e: any) {
      setError(t.error + ': ' + e.message);
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
      setSuccess(t.success);
    } else {
      throw new Error(data.error || t.error);
    }
  };

  // Удаление услуги
  const deleteService = async (serviceId: string) => {
    if (!confirm(t.dashboard.card.deleteConfirm)) return;

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/delete/${serviceId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const data = await response.json();
      if (data.success) {
        await loadUserServices();
        setSuccess(t.success);
      } else {
        setError(data.error || t.error);
      }
    } catch (e: any) {
      setError(t.error + ': ' + e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.dashboard.card.title}</h1>
          <p className="text-gray-600 mt-1">{t.dashboard.card.subtitle}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowWizard(true)}>{t.dashboard.card.optimizationWizard}</Button>
        </div>
      </div>

      {/* Пояснение о парсинге */}
      <p className="text-xs text-gray-500 text-right">
        {t.dashboard.card.parsingNote}
        <a href="/dashboard/progress" className="text-blue-600 underline" target="_blank" rel="noreferrer">
          {t.dashboard.card.progressTab}
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

      <Tabs defaultValue="services" className="space-y-6">
        <TabsList>
          <TabsTrigger value="services">{t.dashboard.card.tabServices || "Services"}</TabsTrigger>
          <TabsTrigger value="reviews">{t.dashboard.card.tabReviews || "Reviews"}</TabsTrigger>
          <TabsTrigger value="news">{t.dashboard.card.tabNews || "News"}</TabsTrigger>
        </TabsList>

        <TabsContent value="services" className="space-y-6">
          {/* Блок с рейтингом и количеством отзывов */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center gap-4">
              {loadingSummary ? (
                <div className="text-gray-500">{t.dashboard.subscription.processing}</div>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <span className="text-3xl font-bold text-gray-900">
                      {rating != null ? Number(rating).toFixed(1) : '—'}
                    </span>
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <span
                          key={star}
                          className={`text-2xl ${rating !== null && star <= Math.floor(rating)
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
                    <span className="font-medium">{reviewsTotal}</span> {t.dashboard.card.reviews}
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
                <h2 className="text-xl font-semibold text-gray-900">{t.dashboard.card.services}</h2>
                <p className="text-sm text-gray-600 mt-1">
                  {t.dashboard.card.servicesSubtitle}
                </p>
              </div>
            </div>

            {/* Форма добавления услуги */}
            {showAddService && (
              <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
                <h3 className="text-lg font-medium text-gray-900 mb-4">{t.dashboard.card.addService}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.card.category}</label>
                    <input
                      type="text"
                      value={newService.category}
                      onChange={(e) => setNewService({ ...newService, category: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder={t.dashboard.card.placeholders.category}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.card.serviceName}</label>
                    <input
                      type="text"
                      value={newService.name}
                      onChange={(e) => setNewService({ ...newService, name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder={t.dashboard.card.placeholders.name}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.card.description}</label>
                    <textarea
                      value={newService.description}
                      onChange={(e) => setNewService({ ...newService, description: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      rows={3}
                      placeholder={t.dashboard.card.placeholders.desc}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.card.keywords}</label>
                    <input
                      type="text"
                      value={newService.keywords}
                      onChange={(e) => setNewService({ ...newService, keywords: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder={t.dashboard.card.placeholders.keywords}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.card.price}</label>
                    <input
                      type="text"
                      value={newService.price}
                      onChange={(e) => setNewService({ ...newService, price: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder={t.dashboard.card.placeholders.price}
                    />
                  </div>
                </div>
                <div className="flex gap-2 mt-4">
                  <Button onClick={addService}>{t.dashboard.card.add}</Button>
                  <Button onClick={() => setShowAddService(false)} variant="outline">{t.dashboard.card.cancel}</Button>
                </div>
              </div>
            )}

            {/* Функционал оптимизатора услуг (только загрузка файла) */}
            <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
              <div className="mb-4">
                <h2 className="text-xl font-semibold text-gray-900 mb-1">{t.dashboard.card.seo.title}</h2>
                <p className="text-sm text-gray-600">{t.dashboard.card.seo.desc1}</p>
                <p className="text-sm text-gray-600 mt-2">{t.dashboard.card.seo.desc2}</p>
                <p className="text-sm text-gray-600 mt-2">{t.dashboard.card.seo.desc3}</p>
                <p className="text-sm text-gray-600 mt-2">{t.dashboard.card.seo.desc4}</p>
              </div>
              <div className="flex gap-2 items-center">
                <Button onClick={() => setShowAddService(true)}>+ {t.dashboard.card.addService}</Button>
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
                      userServices.forEach(s => optimizeService(s.id));
                    }}
                  >
                    {t.dashboard.card.optimizeAll}
                  </Button>
                )}
              </div>
            </div>

            {/* Список услуг */}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t.dashboard.card.table.category}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t.dashboard.card.table.name}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t.dashboard.card.table.description}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t.dashboard.card.table.price}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t.dashboard.card.table.actions}</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {loadingServices ? (
                    <tr>
                      <td className="px-4 py-3 text-gray-500" colSpan={5}>{t.dashboard.subscription.processing}</td>
                    </tr>
                  ) : userServices.length === 0 ? (
                    <tr>
                      <td className="px-4 py-3 text-gray-500" colSpan={5}>{t.dashboard.network.noData}</td>
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
                                <div className="mt-2 bg-primary/5 border border-primary/20 rounded-lg p-4 space-y-2 relative">
                                  <div className="absolute top-0 right-0 p-2 opacity-10">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" /></svg>
                                  </div>
                                  <div className="text-xs text-primary font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5 10 10 0 0 0-10 10" /></svg>
                                    {t.dashboard.card.seo.proposal}
                                  </div>
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
                                        setSuccess(t.success);
                                        await loadUserServices();
                                      }}
                                      className="text-xs h-7 border-gray-300 hover:bg-gray-100"
                                    >
                                      {t.dashboard.card.seo.accept}
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
                                        setSuccess(t.success);
                                        await loadUserServices();
                                      }}
                                      className="text-xs h-7 border-gray-300 text-gray-600 hover:bg-gray-100"
                                    >
                                      {t.dashboard.card.seo.reject}
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
                                <div className="mt-2 bg-primary/5 border border-primary/20 rounded-lg p-4 space-y-2 relative">
                                  <div className="absolute top-0 right-0 p-2 opacity-10">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" /></svg>
                                  </div>
                                  <div className="text-xs text-primary font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5 10 10 0 0 0-10 10" /></svg>
                                    {t.dashboard.card.seo.proposal}
                                  </div>
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
                                        setSuccess(t.success);
                                        await loadUserServices();
                                      }}
                                      className="text-xs h-7 border-gray-300 hover:bg-gray-100"
                                    >
                                      {t.dashboard.card.seo.accept}
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
                                        setSuccess(t.success);
                                        await loadUserServices();
                                      }}
                                      className="text-xs h-7 border-gray-300 text-gray-600 hover:bg-gray-100"
                                    >
                                      {t.dashboard.card.seo.reject}
                                    </Button>
                                  </div>
                                </div>
                              )}
                              {!service.description && !service.optimized_description && (
                                <span className="text-gray-400">—</span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">{service.price}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">
                            <div className="flex gap-1 justify-end">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => optimizeService(service.id)}
                                disabled={optimizingServiceId === service.id}
                                className="h-8 w-8 text-primary hover:text-primary hover:bg-primary/10"
                                title={t.dashboard.card.optimize}
                              >
                                {optimizingServiceId === service.id ? (
                                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary border-t-transparent"></div>
                                ) : (
                                  <Wand2 className="h-4 w-4" />
                                )}
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => deleteService(service.id)}
                                className="h-8 w-8 hover:bg-red-50"
                              >
                                <span className="text-lg">🗑️</span>
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
        </TabsContent>

        <TabsContent value="reviews">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <ReviewReplyAssistant businessName={currentBusiness?.name} />
          </div>
        </TabsContent>

        <TabsContent value="news">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <NewsGenerator
              services={(userServices || []).map(s => ({ id: s.id, name: s.name }))}
              businessId={currentBusinessId}
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};
