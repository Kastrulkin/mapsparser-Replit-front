import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import ServiceOptimizer from '@/components/ServiceOptimizer';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  Wand2,
  Network,
  Star,
  MessageSquare,
  TrendingUp,
  Plus,
  Search,
  Filter,
  Trash2,
  Edit3,
  AlertCircle,
  CheckCircle2,
  MapPin,
  Sparkles,
  LayoutGrid,
  List,
  Newspaper
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ReviewReplyAssistant from "@/components/ReviewReplyAssistant";
import NewsGenerator from "@/components/NewsGenerator";
import SEOKeywordsTab from "@/components/SEOKeywordsTab";
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';

export const CardOverviewPage = () => {
  const context = useOutletContext<any>();
  const { user, currentBusinessId, currentBusiness } = context || {};
  const { t, language } = useLanguage();

  // Состояния для рейтинга и отзывов
  const [rating, setRating] = useState<number | null>(null);
  const [reviewsTotal, setReviewsTotal] = useState<number>(0);
  const [lastParseDate, setLastParseDate] = useState<string | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // Состояния для услуг
  const [userServices, setUserServices] = useState<any[]>([]);
  const [loadingServices, setLoadingServices] = useState(false);
  const [servicesCurrentPage, setServicesCurrentPage] = useState(1);
  const servicesItemsPerPage = 1000;
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
  const [isNetworkMaster, setIsNetworkMaster] = useState(false);

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
        setLastParseDate(data.last_parse_date || null);
      }
    } catch (e) {
      console.error('Ошибка загрузки сводки:', e);
    } finally {
      setLoadingSummary(false);
    }
  };

  // Состояния для вкладки новостей
  const [externalPosts, setExternalPosts] = useState<any[]>([]);

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
        // Объединяем пользовательские и внешние услуги
        const services = [...(data.services || [])];
        if (data.external_services) {
          // Маркируем или просто добавляем. Можно добавить поле isExternal, если нужно
          services.push(...data.external_services);
        }
        setUserServices(services);
      }
    } catch (e) {
      console.error('Ошибка загрузки услуг:', e);
    } finally {
      setLoadingServices(false);
    }
  };

  const loadExternalPosts = async () => {
    if (!currentBusinessId) return;
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
      console.error('Ошибка загрузки постов:', e);
    }
  };

  // Map Sources Switcher Logic
  const [mapSources, setMapSources] = useState<string[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>('all');

  const loadMapSources = async () => {
    if (!currentBusinessId) return;
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/client-info?business_id=${currentBusinessId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();

      const sources = new Set<string>();
      if (data.mapLinks && Array.isArray(data.mapLinks)) {
        data.mapLinks.forEach((link: any) => {
          const url = link.url || '';
          if (url.includes('yandex')) sources.add('yandex');
          else if (url.includes('2gis')) sources.add('2gis');
          else if (url.includes('google')) sources.add('google');
        });
      }

      // Also check if we have data from sources that are not in mapLinks (legacy support)
      if (externalPosts.length > 0) externalPosts.forEach(p => { if (p.source) sources.add(p.source.toLowerCase()); });
      // We can't check reviews easily here without fetching them, but rely on mapLinks is safer for "configured" maps.

      setMapSources(Array.from(sources));
    } catch (e) { console.error('Error loading map sources', e); }
  };

  useEffect(() => {
    if (currentBusinessId && context) {
      loadSummary();
      loadUserServices();
      loadExternalPosts();
      loadMapSources();
      checkIfNetworkMaster();
    }
  }, [currentBusinessId, context]);

  const checkIfNetworkMaster = async () => {
    if (!currentBusinessId) {
      setIsNetworkMaster(false);
      return;
    }

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/business/${currentBusinessId}/network-locations`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setIsNetworkMaster(data.is_network || false);
      }
    } catch (error) {
      console.error('Ошибка проверки сети:', error);
      setIsNetworkMaster(false);
    }
  };

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
        setSuccess(t.common.success || "Success");
      } else {
        setError(data.error || t.common.error || "Error");
      }
    } catch (e: any) {
      setError((t.common.error || "Error") + ': ' + e.message);
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
          fixedKeywords = service.keywords.map((k: any) => {
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
          setSuccess(t.common.success || "Success");
          await loadUserServices();
        } catch (updateError: any) {
          setError(t.common.error || "Error");
        }
      } else {
        setError(data.error || t.common.error || "Error");
      }
    } catch (e: any) {
      setError((t.common.error || "Error") + ': ' + e.message);
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
      setSuccess(t.common.success || "Success");
    } else {
      throw new Error(data.error || t.common.error || "Error");
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
        setSuccess(t.common.success || "Success");
      } else {
        setError(data.error || t.common.error || "Error");
      }
    } catch (e: any) {
      setError((t.common.error || "Error") + ': ' + e.message);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      {/* Blur Overlay for Network Master Accounts */}
      {isNetworkMaster && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-md">
          <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-8 max-w-md mx-4 text-center")}>
            <div className="mb-6 flex justify-center">
              <div className="w-20 h-20 bg-orange-100 rounded-full flex items-center justify-center shadow-inner">
                <Network className="w-10 h-10 text-orange-600" />
              </div>
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              {t.dashboard.card.networkNotice?.title || "Сетевой аккаунт"}
            </h3>
            <p className="text-gray-600 mb-8 leading-relaxed">
              {t.dashboard.card.networkNotice?.message ||
                "Перейдите на страницу точки, чтобы работать с карточкой точки на картах"}
            </p>
            <Button
              onClick={() => window.location.href = '/dashboard/profile'}
              className="w-full h-12 text-lg shadow-lg bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700"
            >
              {t.dashboard.card.networkNotice?.action || "Выбрать точку"}
            </Button>
          </div>
        </div>
      )}

      <div className={cn("transition-all duration-300", isNetworkMaster ? "pointer-events-none select-none blur-sm opacity-50" : "")}>
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-orange-100 rounded-lg">
                <LayoutGrid className="w-6 h-6 text-orange-600" />
              </div>
              <h1 className="text-3xl font-bold text-gray-900">{t.dashboard.card.title} (Updated)</h1>
            </div>
            <p className="text-gray-600 text-lg">{t.dashboard.card.subtitle}</p>
          </div>
          <div className="flex gap-3">
            {/* Progress Status Badge */}
            <a href="/dashboard/progress" className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg font-medium hover:bg-indigo-100 transition-colors">
              <TrendingUp className="w-4 h-4" />
              <span>{t.dashboard.card.progressTab}</span>
            </a>
            <Button
              onClick={() => setShowWizard(true)}
              className="bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-lg hover:shadow-xl hover:from-amber-600 hover:to-orange-700 transition-all"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              {t.dashboard.card.optimizationWizard}
            </Button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50/80 backdrop-blur-sm border border-red-200 text-red-700 px-6 py-4 rounded-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {success && (
          <div className="bg-emerald-50/80 backdrop-blur-sm border border-emerald-200 text-emerald-700 px-6 py-4 rounded-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2">
            <CheckCircle2 className="w-5 h-5 shrink-0" />
            <p>{success}</p>
          </div>
        )}

        {/* Map Source Switcher */}
        {mapSources.length > 0 && (
          <div className="flex gap-2 mb-6 p-1 bg-gray-100/80 rounded-xl w-fit">
            <button
              onClick={() => setSelectedSource('all')}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-all",
                selectedSource === 'all'
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-900 hover:bg-gray-200/50"
              )}
            >
              Все карты
            </button>
            {mapSources.map(source => (
              <button
                key={source}
                onClick={() => setSelectedSource(source)}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize",
                  selectedSource === source
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-900 hover:bg-gray-200/50"
                )}
              >
                {source}
              </button>
            ))}
          </div>
        )}

        <Tabs defaultValue="services" className="space-y-8">
          <TabsList className="bg-white/50 backdrop-blur-sm p-1 rounded-xl border border-gray-200/50 w-full md:w-auto overflow-x-auto flex-nowrap justify-start [&::-webkit-scrollbar]:hidden">
            <TabsTrigger value="services" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-lg px-6 py-2.5 gap-2">
              <List className="w-4 h-4" />
              {t.dashboard.card.tabServices || "Services"}
            </TabsTrigger>
            <TabsTrigger value="reviews" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-lg px-6 py-2.5 gap-2">
              <MessageSquare className="w-4 h-4" />
              {t.dashboard.card.tabReviews || "Reviews"}
            </TabsTrigger>
            <TabsTrigger value="news" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-lg px-6 py-2.5 gap-2">
              <Newspaper className="w-4 h-4" />
              {t.dashboard.card.tabNews || "News"}
            </TabsTrigger>
            <TabsTrigger value="keywords" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-lg px-6 py-2.5 gap-2">
              <TrendingUp className="w-4 h-4" />
              SEO (Wordstat)
            </TabsTrigger>
          </TabsList>

          <TabsContent value="services" className="space-y-6">
            {/* Rating Summary Card */}
            <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-8 relative overflow-hidden")}>
              <div className="absolute top-0 right-0 p-8 opacity-5">
                <Star className="w-48 h-48" />
              </div>
              <div className="relative z-10">
                <div className="flex justify-between items-start mb-6">
                  <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                    <Star className="w-5 h-5 text-amber-500 fill-amber-500" />
                    {t.dashboard.card.rating || "Rating Overview"}
                  </h3>
                  {lastParseDate && (
                    <div className="text-right">
                      <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">{t.dashboard.card.lastUpdate}</p>
                      <p className="text-sm font-medium text-gray-900">
                        {new Date(lastParseDate).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US', {
                          day: 'numeric',
                          month: 'long',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-8">
                  {loadingSummary ? (
                    <div className="flex items-center gap-2 text-gray-500">
                      <div className="animate-spin rounded-full h-5 w-5 border-2 border-primary border-t-transparent"></div>
                      {t.dashboard.subscription.processing}
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-col">
                        <div className="flex items-baseline gap-2">
                          <span className="text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-gray-900 to-gray-700">
                            {rating != null ? Number(rating).toFixed(1) : '—'}
                          </span>
                          <span className="text-gray-400 font-medium">/ 5.0</span>
                        </div>
                      </div>

                      <div className="h-12 w-px bg-gray-200" />

                      <div className="flex flex-col gap-1">
                        <div className="flex gap-1">
                          {[1, 2, 3, 4, 5].map((star) => (
                            <Star
                              key={star}
                              className={cn(
                                "w-6 h-6",
                                rating !== null && star <= Math.floor(rating)
                                  ? "text-amber-400 fill-amber-400"
                                  : rating !== null && star === Math.ceil(rating) && rating % 1 >= 0.5
                                    ? "text-amber-400 fill-amber-400" // Half star logic could be better but simplified
                                    : "text-gray-200 fill-gray-100"
                              )}
                            />
                          ))}
                        </div>
                        <div className="text-gray-500 font-medium ml-1">
                          {reviewsTotal} {t.dashboard.card.reviews}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Services Section */}
            <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-8")}>
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">{t.dashboard.card.services}</h2>
                  <p className="text-gray-500 mt-1">
                    {t.dashboard.card.servicesSubtitle}
                  </p>
                </div>
                {!showAddService && (
                  <Button onClick={() => setShowAddService(true)} className="bg-primary text-white shadow-md hover:shadow-lg">
                    <Plus className="w-4 h-4 mr-2" />
                    {t.dashboard.card.addService}
                  </Button>
                )}
              </div>

              {/* Add Service Form */}
              {showAddService && (
                <div className="mb-8 bg-gray-50/50 border border-gray-200 rounded-xl p-6 shadow-inner">
                  <h3 className="text-lg font-semibold text-gray-900 mb-6 flex items-center gap-2">
                    <Plus className="w-5 h-5 text-primary" />
                    {t.dashboard.card.addService}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">{t.dashboard.card.category}</label>
                      <input
                        type="text"
                        value={newService.category}
                        onChange={(e) => setNewService({ ...newService, category: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                        placeholder={t.dashboard.card.placeholders.category}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">{t.dashboard.card.serviceName}</label>
                      <input
                        type="text"
                        value={newService.name}
                        onChange={(e) => setNewService({ ...newService, name: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                        placeholder={t.dashboard.card.placeholders.name}
                      />
                    </div>
                    <div className="md:col-span-2 space-y-2">
                      <label className="text-sm font-medium text-gray-700">{t.dashboard.card.description}</label>
                      <textarea
                        value={newService.description}
                        onChange={(e) => setNewService({ ...newService, description: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all min-h-[100px]"
                        placeholder={t.dashboard.card.placeholders.desc}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">{t.dashboard.card.keywords}</label>
                      <input
                        type="text"
                        value={newService.keywords}
                        onChange={(e) => setNewService({ ...newService, keywords: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                        placeholder={t.dashboard.card.placeholders.keywords}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">{t.dashboard.card.price}</label>
                      <input
                        type="text"
                        value={newService.price}
                        onChange={(e) => setNewService({ ...newService, price: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                        placeholder={t.dashboard.card.placeholders.price}
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 justify-end mt-8">
                    <Button onClick={() => setShowAddService(false)} variant="outline" className="border-gray-200 text-gray-600 hover:bg-gray-100">
                      {t.dashboard.card.cancel}
                    </Button>
                    <Button onClick={addService} className="bg-primary text-white">
                      {t.dashboard.card.add}
                    </Button>
                  </div>
                </div>
              )}

              {/* Service Optimizer Wizard Block */}
              {!showAddService && (
                <div className="mb-8 bg-gradient-to-br from-indigo-50 to-violet-50 border border-indigo-100 rounded-xl p-6 flex flex-col md:flex-row justify-between items-center gap-6">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Sparkles className="w-5 h-5 text-indigo-600" />
                      <h3 className="font-semibold text-indigo-900">{t.dashboard.card.seo.title}</h3>
                    </div>
                    <p className="text-indigo-700/80 text-sm leading-relaxed max-w-2xl">
                      {t.dashboard.card.seo.desc1} {t.dashboard.card.seo.desc2}
                    </p>
                  </div>
                  <div className="flex gap-3 shrink-0">
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
                        className="bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                      >
                        <Wand2 className="w-4 h-4 mr-2" />
                        {t.dashboard.card.optimizeAll}
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {/* Services List */}
              <div className="overflow-hidden rounded-xl border border-gray-100">
                <table className="min-w-full divide-y divide-gray-100">
                  <thead className="bg-gray-50/50">
                    <tr>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[150px]">
                        {t.dashboard.card.table.category}
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[200px]">
                        {t.dashboard.card.table.name}
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[300px]">
                        {t.dashboard.card.table.description}
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[120px]">
                        {t.dashboard.card.table.price}
                      </th>
                      <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider w-[120px]">
                        {t.common?.updated || "Updated"}
                      </th>
                      <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider w-[100px]">
                        {t.dashboard.card.table.actions}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-100">
                    {loadingServices ? (
                      <tr>
                        <td className="px-6 py-8 text-center" colSpan={6}>
                          <div className="flex justify-center items-center gap-2 text-gray-500">
                            <div className="animate-spin rounded-full h-5 w-5 border-2 border-primary border-t-transparent"></div>
                            <span>{t.dashboard.subscription.processing}</span>
                          </div>
                        </td>
                      </tr>
                    ) : userServices.length === 0 ? (
                      <tr>
                        <td className="px-6 py-12 text-center text-gray-500" colSpan={5}>
                          <div className="flex flex-col items-center justify-center gap-3">
                            <div className="p-3 bg-gray-50 rounded-full">
                              <Search className="w-8 h-8 text-gray-300" />
                            </div>
                            <p>{t.dashboard.network.noData}</p>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      userServices
                        .slice((servicesCurrentPage - 1) * servicesItemsPerPage, servicesCurrentPage * servicesItemsPerPage)
                        .map((service, index) => (
                          <tr key={service.id || index} className="group hover:bg-gray-50/50 transition-colors">
                            <td className="px-6 py-4 text-sm text-gray-500 font-medium whitespace-nowrap align-top">
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                {service.category}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-900 align-top max-w-[250px]">
                              <div className="space-y-3">
                                {service.name && (
                                  <div className="font-semibold">{service.name}</div>
                                )}
                                {service.optimized_name && (
                                  <div className="mt-2 bg-indigo-50/80 border border-indigo-100 rounded-lg p-3 space-y-2 relative animate-in fade-in">
                                    <div className="text-[10px] text-indigo-600 font-bold uppercase tracking-wider flex items-center gap-1">
                                      <Sparkles className="w-3 h-3" />
                                      {t.dashboard.card.seo.proposal}
                                    </div>
                                    <div className="text-gray-800 leading-snug text-sm">{service.optimized_name}</div>
                                    <div className="flex gap-2 pt-1">
                                      <Button
                                        size="sm"
                                        variant="ghost"
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
                                          setSuccess(t.common.success || "Accepted");
                                          await loadUserServices();
                                        }}
                                        className="h-6 text-xs bg-white text-indigo-600 border border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
                                      >
                                        <CheckCircle2 className="w-3 h-3 mr-1" />
                                        {t.dashboard.card.seo.accept}
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="ghost"
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
                                          setSuccess(t.common.success || "Rejected");
                                          await loadUserServices();
                                        }}
                                        className="h-6 text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                                      >
                                        {t.dashboard.card.seo.reject}
                                      </Button>
                                    </div>
                                  </div>
                                )}
                                {!service.name && !service.optimized_name && (
                                  <span className="text-gray-300 italic">—</span>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-600 align-top max-w-[350px]">
                              <div className="space-y-3">
                                {service.description && (
                                  <div className="leading-relaxed">{service.description}</div>
                                )}
                                {service.optimized_description && (
                                  <div className="mt-2 bg-indigo-50/80 border border-indigo-100 rounded-lg p-3 space-y-2 relative animate-in fade-in">
                                    <div className="text-[10px] text-indigo-600 font-bold uppercase tracking-wider flex items-center gap-1">
                                      <Sparkles className="w-3 h-3" />
                                      {t.dashboard.card.seo.proposal}
                                    </div>
                                    <div className="text-gray-800 leading-relaxed text-sm">{service.optimized_description}</div>
                                    <div className="flex gap-2 pt-1">
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={async () => {
                                          await updateService(service.id, {
                                            category: service.category,
                                            name: service.name,
                                            description: service.optimized_description,
                                            optimized_description: '',
                                            keywords: service.keywords,
                                            price: service.price
                                          });
                                          setSuccess(t.common.success || "Accepted");
                                          await loadUserServices();
                                        }}
                                        className="h-6 text-xs bg-white text-indigo-600 border border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
                                      >
                                        <CheckCircle2 className="w-3 h-3 mr-1" />
                                        {t.dashboard.card.seo.accept}
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={async () => {
                                          await updateService(service.id, {
                                            category: service.category,
                                            name: service.name,
                                            description: service.description,
                                            optimized_description: '',
                                            keywords: service.keywords,
                                            price: service.price
                                          });
                                          setSuccess(t.common.success || "Rejected");
                                          await loadUserServices();
                                        }}
                                        className="h-6 text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                                      >
                                        {t.dashboard.card.seo.reject}
                                      </Button>
                                    </div>
                                  </div>
                                )}
                                {!service.description && !service.optimized_description && (
                                  <span className="text-gray-300 italic">—</span>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 text-sm font-medium text-gray-900 whitespace-nowrap align-top">
                              {service.price ? `${(Number(service.price) / 100).toLocaleString('ru-RU')} ₽` : '—'}
                            </td>
                            <td className="px-6 py-4 text-right text-sm text-gray-500 whitespace-nowrap align-top">
                              {service.updated_at ? new Date(service.updated_at).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US', {
                                day: '2-digit',
                                month: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit'
                              }) : '—'}
                            </td>
                            <td className="px-6 py-4 text-right text-sm text-gray-500 align-top">
                              <div className="flex gap-1 justify-end">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => optimizeService(service.id)}
                                  disabled={optimizingServiceId === service.id}
                                  className="h-8 w-8 text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50"
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
                                  className="h-8 w-8 text-gray-400 hover:text-red-600 hover:bg-red-50"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination controls could go here */}

            </div>
          </TabsContent>

          <TabsContent value="reviews">
            <ReviewReplyAssistant
              businessName={currentBusiness?.name}
              selectedSource={selectedSource}
            />
          </TabsContent>

          <TabsContent value="news">
            <NewsGenerator
              services={(userServices || []).map(s => ({ id: s.id, name: s.name }))}
              businessId={currentBusinessId}
              externalPosts={externalPosts.filter(p => selectedSource === 'all' || (p.source && p.source.toLowerCase().includes(selectedSource)))}
            />
          </TabsContent>

          <TabsContent value="keywords">
            <SEOKeywordsTab />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};
