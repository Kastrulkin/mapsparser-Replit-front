import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate, useOutletContext, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  ArrowRight,
  Network,
  Star,
  MessageSquare,
  TrendingUp,
  Plus,
  AlertCircle,
  CheckCircle2,
  MapPin,
  LayoutGrid,
  List,
  Newspaper,
  Trophy,
  RefreshCw,
  FileSearch,
  Info
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';
import { getAutomationAccessForBusiness } from '@/lib/subscriptionAccess';
import { pickNetworkRepresentative } from '@/lib/networkRepresentative';
import { CardServicesTable } from '@/components/dashboard/CardServicesTable';
import { CompetitorsTab, KeywordsTab, NewsTab, ReviewsTab } from '@/components/dashboard/CardOverviewTabs';
import {
  CardServiceAddForm,
  CardServiceEditDialog,
  CardServiceOptimizerPanel,
  CardServicesFilterBar,
  CardServicesMetaStrip,
} from '@/components/dashboard/CardServicesControls';
import {
  formatMapSourceTab,
  formatServiceSource,
  getDisplayedServiceUpdatedAt,
  getMatchedKeywords,
  isDraftSimilarToCurrent,
} from '@/components/dashboard/cardServicesLogic';
import { useCardServiceController } from '@/components/dashboard/useCardServiceController';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import {
  createManualCompetitor,
  extractMapSources,
  fetchManualCompetitors,
  loadCardClientInfo,
  loadCardExternalPosts,
  loadCardExternalSummary,
  loadCardParseStatus,
  loadCardServices,
  loadNetworkLocationsState,
  loadOperationsLearningMetrics,
  normalizeParseRefreshPolicy,
  refreshCardDataFromSource,
  removeManualCompetitor,
  requestManualCompetitorAudit,
} from '@/components/dashboard/cardOverviewApi';

const CARD_FIRST_RUN_COPY: Record<string, {
  title: string;
  bodyMissingMap: string;
  statusMissingMap: string;
  helpMissingMap: string;
  goToProfile: string;
}> = {
  ru: {
    title: 'Как работать с данными карточки',
    bodyMissingMap: 'Сохраните ссылку на карту в «Профиль и бизнес». Потом вернитесь сюда и обновите данные.',
    statusMissingMap: 'Нужна ссылка на карту',
    helpMissingMap: 'Добавьте ссылку и сохраните изменения.',
    goToProfile: 'Перейти в «Профиль и бизнес»',
  },
  en: {
    title: 'How card data works',
    bodyMissingMap: 'Save the map link in “Profile & Business”. Then come back here and refresh the data.',
    statusMissingMap: 'Map link required',
    helpMissingMap: 'Add the link and save the changes.',
    goToProfile: 'Go to Profile & Business',
  },
  ar: {
    title: 'كيفية العمل مع بيانات البطاقة',
    bodyMissingMap: 'احفظ رابط البطاقة أولاً في «الملف الشخصي والنشاط التجاري». ثم ارجع إلى هنا وحدّث البيانات.',
    statusMissingMap: 'رابط الخريطة مطلوب',
    helpMissingMap: 'أضف الرابط واحفظ التغييرات.',
    goToProfile: 'الانتقال إلى الملف الشخصي والنشاط التجاري',
  },
  de: {
    title: 'So arbeiten Sie mit den Kartendaten',
    bodyMissingMap: 'Speichern Sie zuerst den Kartenlink unter „Profil & Unternehmen“. Kehren Sie dann hierher zurück und aktualisieren Sie die Daten.',
    statusMissingMap: 'Kartenlink erforderlich',
    helpMissingMap: 'Fügen Sie den Link hinzu und speichern Sie die Änderungen.',
    goToProfile: 'Zu Profil & Unternehmen',
  },
  el: {
    title: 'Πώς να δουλέψετε με τα δεδομένα της κάρτας',
    bodyMissingMap: 'Αποθηκεύστε πρώτα τον σύνδεσμο χάρτη στο «Προφίλ & Επιχείρηση». Μετά επιστρέψτε εδώ και ενημερώστε τα δεδομένα.',
    statusMissingMap: 'Απαιτείται σύνδεσμος χάρτη',
    helpMissingMap: 'Προσθέστε τον σύνδεσμο και αποθηκεύστε τις αλλαγές.',
    goToProfile: 'Μετάβαση στο Προφίλ & Επιχείρηση',
  },
  es: {
    title: 'Cómo trabajar con los datos de la ficha',
    bodyMissingMap: 'Guarda primero el enlace del mapa en «Perfil y negocio». Luego vuelve aquí y actualiza los datos.',
    statusMissingMap: 'Se necesita un enlace del mapa',
    helpMissingMap: 'Añade el enlace y guarda los cambios.',
    goToProfile: 'Ir a Perfil y negocio',
  },
  fr: {
    title: 'Comment utiliser les données de la fiche',
    bodyMissingMap: 'Enregistrez d’abord le lien de la carte dans « Profil et entreprise ». Revenez ensuite ici pour actualiser les données.',
    statusMissingMap: 'Lien de carte requis',
    helpMissingMap: 'Ajoutez le lien puis enregistrez les modifications.',
    goToProfile: 'Aller à Profil et entreprise',
  },
  ha: {
    title: 'Yadda ake aiki da bayanan katin',
    bodyMissingMap: 'Da farko a ajiye hanyar taswira a cikin “Profile & Business”. Sannan a dawo nan a sabunta bayanan.',
    statusMissingMap: 'Ana bukatar hanyar taswira',
    helpMissingMap: 'Ƙara hanyar sannan a ajiye canje-canjen.',
    goToProfile: 'Je zuwa Profile & Business',
  },
  th: {
    title: 'วิธีใช้งานข้อมูลการ์ดธุรกิจ',
    bodyMissingMap: 'บันทึกลิงก์แผนที่ใน “Profile & Business” ก่อน แล้วค่อยกลับมาที่นี่เพื่ออัปเดตข้อมูล',
    statusMissingMap: 'ต้องมีลิงก์แผนที่',
    helpMissingMap: 'เพิ่มลิงก์และบันทึกการเปลี่ยนแปลง',
    goToProfile: 'ไปที่ Profile & Business',
  },
  tr: {
    title: 'Kart verileriyle nasıl çalışılır',
    bodyMissingMap: 'Önce harita bağlantısını “Profil ve İşletme” bölümüne kaydedin. Sonra buraya dönüp verileri güncelleyin.',
    statusMissingMap: 'Harita bağlantısı gerekli',
    helpMissingMap: 'Bağlantıyı ekleyin ve değişiklikleri kaydedin.',
    goToProfile: 'Profil ve İşletme bölümüne git',
  },
};

type ServicesSort = 'default' | 'name_asc' | 'name_desc' | 'updated_desc' | 'updated_asc' | 'price_asc' | 'price_desc';
type CardTabValue = 'services' | 'reviews' | 'news' | 'keywords' | 'competitors';
type ReviewFocusValue = 'all' | 'negative' | 'needs_reply';

const isCardTabValue = (value: string): value is CardTabValue =>
  value === 'services' || value === 'reviews' || value === 'news' || value === 'keywords' || value === 'competitors';

const isReviewFocusValue = (value: string): value is ReviewFocusValue =>
  value === 'all' || value === 'negative' || value === 'needs_reply';

const toServicesSort = (value: string): ServicesSort => {
  if (
    value === 'default' ||
    value === 'name_asc' ||
    value === 'name_desc' ||
    value === 'updated_desc' ||
    value === 'updated_asc' ||
    value === 'price_asc' ||
    value === 'price_desc'
  ) {
    return value;
  }
  return 'default';
};

export const CardOverviewPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const servicesTableScrollRef = useRef<HTMLDivElement | null>(null);
  const context = useOutletContext<any>();
  const { user, currentBusinessId, currentBusiness, businesses, onBusinessChange } = context || {};
  const { t, language } = useLanguage();
  const isRu = language === 'ru';
  const aiLearningTooltip = isRu
    ? 'Система учитывает, как вы редактируете предложения по услугам, отзывам и новостям, и постепенно подстраивает следующие рекомендации под ваш стиль.'
    : 'The system learns from how you edit service, review, and news suggestions and gradually adapts future recommendations to your style.';
  const firstRunCopy = CARD_FIRST_RUN_COPY[language] ?? CARD_FIRST_RUN_COPY.en;
  const automationAccess = getAutomationAccessForBusiness(currentBusiness);
  const automationLockedMessage = automationAccess.message || 'Автоматизация доступна только после оплаты тарифа.';
  const initialTabParam = String(searchParams.get('tab') || '').trim().toLowerCase();
  const initialReviewFocusParam = String(searchParams.get('review_filter') || '').trim().toLowerCase();
  const [activeTab, setActiveTab] = useState<CardTabValue>(isCardTabValue(initialTabParam) ? initialTabParam : 'services');
  const reviewFocus = isReviewFocusValue(initialReviewFocusParam) ? initialReviewFocusParam : 'all';

  // Состояния для рейтинга и отзывов
  const [rating, setRating] = useState<number | null>(null);
  const [reviewsTotal, setReviewsTotal] = useState<number>(0);
  const [lastParseDate, setLastParseDate] = useState<string | null>(null);
  const [competitors, setCompetitors] = useState<any[]>([]);
  const [manualCompetitors, setManualCompetitors] = useState<any[]>([]);
  const [manualCompetitorUrl, setManualCompetitorUrl] = useState('');
  const [manualCompetitorName, setManualCompetitorName] = useState('');
  const [addingManualCompetitor, setAddingManualCompetitor] = useState(false);
  const [requestingAuditId, setRequestingAuditId] = useState<string | null>(null);
  const [deletingManualCompetitorId, setDeletingManualCompetitorId] = useState<string | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // Состояния для услуг
  const [userServices, setUserServices] = useState<any[]>([]);
  const [loadingServices, setLoadingServices] = useState(false);
  const [servicesLastParseDate, setServicesLastParseDate] = useState<string | null>(null);
  const [servicesNoNewFromParse, setServicesNoNewFromParse] = useState(false);
  const [servicesCurrentPage, setServicesCurrentPage] = useState(1);
  const servicesItemsPerPage = 1000;
  const [servicesSearch, setServicesSearch] = useState('');
  const [servicesCategoryFilter, setServicesCategoryFilter] = useState('all');
  const [servicesSort, setServicesSort] = useState<ServicesSort>('default');

  // Состояния для парсера
  // parsequeue canonical status: 'completed'; API and backend also accept legacy 'done'
  const [parseStatus, setParseStatus] = useState<'idle' | 'processing' | 'completed' | 'done' | 'error' | 'queued'>('idle');
  const [parseStatusError, setParseStatusError] = useState<string | null>(null);
  const [refreshingCardData, setRefreshingCardData] = useState(false);
  const [parseRefreshPolicy, setParseRefreshPolicy] = useState<{
    can_refresh: boolean;
    reason: string | null;
    message: string | null;
    cooldown_days: number;
    last_completed_at: string | null;
    cooldown_until: string | null;
    invite_override_available: boolean;
    accepted_invites_count: number;
  }>({
    can_refresh: true,
    reason: null,
    message: null,
    cooldown_days: 7,
    last_completed_at: null,
    cooldown_until: null,
    invite_override_available: false,
    accepted_invites_count: 0,
  });

  // Общие состояния
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isNetworkMaster, setIsNetworkMaster] = useState(false);
  const [operationsLearning, setOperationsLearning] = useState<Record<string, any>>({});

  useEffect(() => {
    const nextTabParam = String(searchParams.get('tab') || '').trim().toLowerCase();
    if (isCardTabValue(nextTabParam) && nextTabParam !== activeTab) {
      setActiveTab(nextTabParam);
    }
    if (!nextTabParam && activeTab !== 'services') {
      setActiveTab('services');
    }
  }, [activeTab, searchParams]);

  const isNetworkRepresentative = useMemo(() => {
    const businessId = String(currentBusinessId || '').trim();
    const networkId = String(currentBusiness?.network_id || '').trim();
    if (!businessId || !networkId) {
      return false;
    }

    if (businessId === networkId) {
      return true;
    }

    if (!Array.isArray(businesses)) {
      return false;
    }

    const sameNetworkBusinesses = businesses.filter((item: any) => String(item?.network_id || '').trim() === networkId);
    if (sameNetworkBusinesses.length === 0) {
      return false;
    }

    const representative = pickNetworkRepresentative(sameNetworkBusinesses, networkId);
    return String(representative?.id || '').trim() === businessId;
  }, [businesses, currentBusiness, currentBusinessId]);

  // Загрузка сводки (рейтинг, количество отзывов)
  const loadSummary = async () => {
    if (!currentBusinessId) return;
    setLoadingSummary(true);
    try {
      const { data } = await loadCardExternalSummary(currentBusinessId, isNetworkRepresentative);
      if (data.success) {
        setRating(data.rating);
        setReviewsTotal(data.reviews_total || 0);
        setLastParseDate(data.last_parse_date || null);
        try {
          if (data.competitors) {
            setCompetitors(typeof data.competitors === 'string' ? JSON.parse(data.competitors) : data.competitors);
          } else {
            setCompetitors([]);
          }
        } catch (e) {
          console.error("Error parsing competitors:", e);
          setCompetitors([]);
        }
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
      const { data } = await loadCardServices({
        businessId: currentBusinessId,
        scopeNetwork: isNetworkRepresentative,
        source: selectedSource,
      });
      if (data.success) {
        setServicesLastParseDate(data.last_parse_date || null);
        setServicesNoNewFromParse(Boolean(data.no_new_services_found));
        // Объединяем пользовательские и внешние услуги
        const services = [...(data.services || [])];
        if (data.external_services) {
          services.push(...data.external_services.map((service: any) => ({
            ...service,
            source: service.source || 'external',
          })));
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
      const { data } = await loadCardExternalPosts(currentBusinessId, isNetworkRepresentative);
      if (data.success) {
        setExternalPosts(data.posts || []);
      }
    } catch (e) {
      console.error('Ошибка загрузки постов:', e);
    }
  };

  const loadParseStatus = async () => {
    if (!currentBusinessId) {
      setParseStatus('idle');
      return;
    }
    try {
      const { response, data } = await loadCardParseStatus(currentBusinessId);
      if (response.ok && data.success) {
        const nextStatus = String(data.status || 'idle').trim().toLowerCase();
        setParseStatusError(String(data.error_message || '').trim() || null);
        setParseRefreshPolicy(normalizeParseRefreshPolicy(data.refresh_policy));
        if (nextStatus === 'completed' || nextStatus === 'done' || nextStatus === 'processing' || nextStatus === 'queued' || nextStatus === 'error') {
          setParseStatus(nextStatus);
        } else {
          setParseStatus('idle');
        }
      }
    } catch (e) {
      console.error('Ошибка загрузки статуса парсинга:', e);
    }
  };

  const loadManualCompetitors = async () => {
    if (!currentBusinessId) return;
    try {
      const { data } = await fetchManualCompetitors(currentBusinessId);
      if (data.success) {
        setManualCompetitors(Array.isArray(data.competitors) ? data.competitors : []);
      }
    } catch (e) {
      console.error('Ошибка загрузки ручных конкурентов:', e);
    }
  };

  const addManualCompetitor = async () => {
    if (!currentBusinessId) return;
    const url = manualCompetitorUrl.trim();
    if (!url) {
      setError('Укажите ссылку на конкурента');
      return;
    }
    try {
      setAddingManualCompetitor(true);
      setError(null);
      const { response: res, data } = await createManualCompetitor(currentBusinessId, {
        url,
        name: manualCompetitorName.trim(),
      });
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Не удалось добавить конкурента');
      }
      setManualCompetitorUrl('');
      setManualCompetitorName('');
      setSuccess('Конкурент добавлен');
      await loadManualCompetitors();
    } catch (e: any) {
      setError(e.message || 'Не удалось добавить конкурента');
    } finally {
      setAddingManualCompetitor(false);
    }
  };

  const requestAudit = async (competitorId: string) => {
    if (!currentBusinessId) return;
    try {
      setRequestingAuditId(competitorId);
      setError(null);
      const { response: res, data } = await requestManualCompetitorAudit(currentBusinessId, competitorId);
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Не удалось отправить запрос на аудит');
      }
      setSuccess('Запрос на аудит отправлен суперадмину');
      await loadManualCompetitors();
    } catch (e: any) {
      setError(e.message || 'Не удалось отправить запрос на аудит');
    } finally {
      setRequestingAuditId(null);
    }
  };

  const deleteManualCompetitor = async (competitorId: string) => {
    if (!currentBusinessId) return;
    if (!window.confirm('Удалить этого конкурента из списка?')) return;
    try {
      setDeletingManualCompetitorId(competitorId);
      setError(null);
      const { response: res, data } = await removeManualCompetitor(currentBusinessId, competitorId);
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Не удалось удалить конкурента');
      }
      setSuccess('Конкурент удалён');
      await loadManualCompetitors();
    } catch (e: any) {
      setError(e.message || 'Не удалось удалить конкурента');
    } finally {
      setDeletingManualCompetitorId(null);
    }
  };

  // Map Sources Switcher Logic
  const [mapSources, setMapSources] = useState<string[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>('all');
  const [hasConfiguredMapLink, setHasConfiguredMapLink] = useState(false);
  const [hasSupportedConfiguredMapLink, setHasSupportedConfiguredMapLink] = useState(false);

  const loadMapSources = async () => {
    if (!currentBusinessId) return;
    try {
      const { data } = await loadCardClientInfo(currentBusinessId);
      const mapState = extractMapSources(data, externalPosts);
      setMapSources(mapState.sources);
      setHasConfiguredMapLink(mapState.hasConfiguredMapLink);
      setHasSupportedConfiguredMapLink(mapState.hasSupportedConfiguredMapLink);
    } catch (e) { console.error('Error loading map sources', e); }
  };

  const loadOperationsLearning = async () => {
    if (!user?.is_superadmin) {
      setOperationsLearning({});
      return;
    }
    try {
      const { response: res, data } = await loadOperationsLearningMetrics();
      if (!res.ok) {
        setOperationsLearning({});
        return;
      }
      const items = Array.isArray(data.items) ? data.items : [];
      const byCapability: Record<string, any> = {};
      for (const item of items) {
        const key = String(item?.capability || '').trim();
        if (key) byCapability[key] = item;
      }
      setOperationsLearning(byCapability);
    } catch {
      setOperationsLearning({});
    }
  };

  useEffect(() => {
    if (currentBusinessId && context) {
      loadSummary();
      loadUserServices();
      loadExternalPosts();
      loadManualCompetitors();
      loadMapSources();
      checkIfNetworkMaster();
      loadOperationsLearning();
      loadParseStatus();
    }
  }, [currentBusinessId, context, selectedSource, isNetworkRepresentative]);

  useEffect(() => {
    if (parseStatus !== 'processing' && parseStatus !== 'queued') {
      return undefined;
    }

    const timer = window.setInterval(() => {
      loadParseStatus();
      loadSummary();
      loadUserServices();
      loadExternalPosts();
    }, 10000);

    return () => window.clearInterval(timer);
  }, [parseStatus, currentBusinessId, selectedSource, isNetworkRepresentative]);

  useEffect(() => {
    setServicesCurrentPage(1);
  }, [servicesSearch, servicesCategoryFilter, servicesSort, currentBusinessId]);

  const serviceCategories = useMemo(() => {
    const set = new Set<string>();
    for (const service of userServices) {
      const category = (service?.category || '').toString().trim();
      if (category) set.add(category);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b, language === 'ru' ? 'ru' : 'en'));
  }, [userServices, language]);

  const filteredServices = useMemo(() => {
    const sourceMatches = (service: any) => {
      if (selectedSource === 'all') return true;
      const source = String(service?.source || '').trim().toLowerCase();
      if (selectedSource === '2gis') return source === '2gis';
      if (selectedSource === 'yandex') return source === 'yandex_maps' || source === 'yandex_business';
      if (selectedSource === 'google') return source === 'google_maps' || source === 'google_business';
      if (selectedSource === 'apple') return source === 'apple_maps' || source === 'apple_business';
      return source.includes(selectedSource);
    };

    const query = servicesSearch.trim().toLowerCase();
    const list = userServices.filter((service) => {
      if (!sourceMatches(service)) return false;
      if (servicesCategoryFilter !== 'all' && (service?.category || '') !== servicesCategoryFilter) {
        return false;
      }
      if (!query) return true;
      const haystack = [
        service?.name,
        service?.optimized_name,
        service?.description,
        service?.optimized_description,
        service?.category,
        Array.isArray(service?.keywords) ? service.keywords.join(' ') : (service?.keywords || ''),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(query);
    });

    if (servicesSort === 'default') {
      return list;
    }

    const normalizePrice = (value: any): number => {
      const n = Number(value);
      return Number.isFinite(n) ? n : Number.POSITIVE_INFINITY;
    };

    const sorted = [...list];
    sorted.sort((a, b) => {
      switch (servicesSort) {
        case 'name_asc':
          return String(a?.name || '').localeCompare(String(b?.name || ''), language === 'ru' ? 'ru' : 'en');
        case 'name_desc':
          return String(b?.name || '').localeCompare(String(a?.name || ''), language === 'ru' ? 'ru' : 'en');
        case 'updated_asc':
          return new Date(a?.updated_at || 0).getTime() - new Date(b?.updated_at || 0).getTime();
        case 'updated_desc':
          return new Date(b?.updated_at || 0).getTime() - new Date(a?.updated_at || 0).getTime();
        case 'price_asc':
          return normalizePrice(a?.price) - normalizePrice(b?.price);
        case 'price_desc':
          return normalizePrice(b?.price) - normalizePrice(a?.price);
        default:
          return 0;
      }
    });
    return sorted;
  }, [userServices, servicesSearch, servicesCategoryFilter, servicesSort, language, selectedSource]);

  const pagedServices = useMemo(
    () => filteredServices.slice((servicesCurrentPage - 1) * servicesItemsPerPage, servicesCurrentPage * servicesItemsPerPage),
    [filteredServices, servicesCurrentPage, servicesItemsPerPage]
  );

  const selectedSyncSource = useMemo(() => {
    if (selectedSource !== 'all') {
      return selectedSource;
    }
    if (mapSources.includes('yandex')) {
      return 'yandex';
    }
    if (mapSources.includes('2gis')) {
      return '2gis';
    }
    return mapSources[0] || '';
  }, [mapSources, selectedSource]);

  const canRefreshCardData = selectedSyncSource === 'yandex' || selectedSyncSource === '2gis';
  const refreshBlockedByPolicy = !parseRefreshPolicy.can_refresh;
  const refreshBlockedByActiveParse = parseStatus === 'processing' || parseStatus === 'queued';
  const canTriggerRefresh = canRefreshCardData && !refreshBlockedByPolicy && !refreshBlockedByActiveParse;

  const formatRefreshDate = (isoValue: string | null) => {
    if (!isoValue) {
      return null;
    }
    const parsedDate = new Date(isoValue);
    if (Number.isNaN(parsedDate.getTime())) {
      return isoValue;
    }
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(parsedDate);
  };

  const parseStatusLabel = useMemo(() => {
    if (!hasConfiguredMapLink) {
      return firstRunCopy.statusMissingMap;
    }
    if (parseRefreshPolicy.reason === 'active_parse') {
      return isRu ? 'Сбор данных уже выполняется' : 'Data collection is already running';
    }
    if (parseRefreshPolicy.reason === 'weekly_cooldown' && parseRefreshPolicy.cooldown_until) {
      const formattedDate = formatRefreshDate(parseRefreshPolicy.cooldown_until);
      if (formattedDate) {
        return isRu ? `Следующее обновление доступно ${formattedDate}` : `Next refresh will be available on ${formattedDate}`;
      }
    }
    switch (parseStatus) {
      case 'processing':
        return isRu ? 'Сбор данных выполняется' : 'Data collection in progress';
      case 'queued':
        return isRu ? 'Сбор данных в очереди' : 'Data collection is queued';
      case 'completed':
      case 'done':
        return isRu ? 'Данные карточки обновлены' : 'Card data updated';
      case 'error':
        return isRu ? 'Не удалось обновить данные' : 'Could not update card data';
      default:
        return isRu ? 'Данные карточки ещё не обновлялись' : 'Card data has not been collected yet';
    }
  }, [firstRunCopy.statusMissingMap, hasConfiguredMapLink, isRu, parseRefreshPolicy.cooldown_until, parseRefreshPolicy.reason, parseStatus]);

  const parseStatusHelpText = useMemo(() => {
    if (!hasConfiguredMapLink) {
      return firstRunCopy.helpMissingMap;
    }
    if (!hasSupportedConfiguredMapLink) {
      return isRu
        ? 'Ссылка на карту сохранена, но для обновления данных сейчас поддерживаются только Яндекс и 2ГИС.'
        : 'A map link is saved, but data refresh is currently supported only for Yandex and 2GIS.';
    }
    if (parseStatus === 'error' && parseStatusError) {
      const raw = parseStatusError
        .replace(/^error:\s*/i, '')
        .replace(/^parsed entity mismatch for source url\s*\|?\s*/i, '')
        .trim();

      if (raw) {
        return isRu
          ? `Не удалось обновить карточку: ссылка ведёт на другую организацию (${raw}). Проверьте ссылку на карту во вкладке «Профиль и бизнес».`
          : `We could not update the listing because the map link points to a different business (${raw}). Check the map link in Profile & Business.`;
      }
    }
    if (parseStatus === 'processing' || parseStatus === 'queued' || parseRefreshPolicy.reason === 'active_parse') {
      return isRu ? 'Собираем данные. Это может занять несколько минут.' : 'We are collecting data. This may take a few minutes.';
    }
    if (parseRefreshPolicy.reason === 'weekly_cooldown') {
      const formattedDate = formatRefreshDate(parseRefreshPolicy.cooldown_until);
      if (formattedDate) {
        return isRu
          ? `Обновить данные карточки можно раз в неделю. Следующее обновление будет доступно ${formattedDate}. Если пригласить друга, обновление станет доступно раньше.`
          : `Card data can be refreshed once a week. The next refresh will be available on ${formattedDate}. Inviting a friend unlocks it earlier.`;
      }
      return isRu
        ? 'Обновить данные карточки можно раз в неделю. Если пригласить друга, обновление станет доступно раньше.'
        : 'Card data can be refreshed once a week. Inviting a friend unlocks it earlier.';
    }
    if (parseRefreshPolicy.invite_override_available && parseRefreshPolicy.accepted_invites_count > 0 && parseRefreshPolicy.last_completed_at) {
      return isRu
        ? 'У вас уже есть приглашённый друг, поэтому обновление доступно раньше стандартного недельного интервала.'
        : 'You already invited a friend, so refresh is available earlier than the standard weekly interval.';
    }
    return null;
  }, [firstRunCopy.helpMissingMap, hasConfiguredMapLink, hasSupportedConfiguredMapLink, isRu, parseRefreshPolicy.accepted_invites_count, parseRefreshPolicy.cooldown_until, parseRefreshPolicy.invite_override_available, parseRefreshPolicy.last_completed_at, parseRefreshPolicy.reason, parseStatus, parseStatusError]);

  const handleRefreshCardData = async () => {
    if (!currentBusinessId || !canRefreshCardData) {
      return;
    }

    try {
      setRefreshingCardData(true);
      setError(null);
      setSuccess(null);
      const { response, data } = await refreshCardDataFromSource(currentBusinessId, selectedSyncSource);
      if (!response.ok || !data.success) {
        if (data.refresh_policy) {
          setParseRefreshPolicy(normalizeParseRefreshPolicy(data.refresh_policy));
        }
        throw new Error(data.message || data.error || 'Не удалось запустить обновление данных карточки');
      }

      setParseStatus('queued');
      setSuccess('Собираем данные. Это может занять несколько минут. После завершения аудит и показатели обновятся автоматически.');
      loadParseStatus();
    } catch (e: any) {
      setError(e?.message || 'Не удалось запустить обновление данных карточки');
      setParseStatus('error');
    } finally {
      setRefreshingCardData(false);
    }
  };

  const checkIfNetworkMaster = async () => {
    if (!currentBusinessId) {
      setIsNetworkMaster(false);
      return;
    }

    try {
      const { response, data } = await loadNetworkLocationsState(currentBusinessId);

      if (response.ok) {
        const masterFlag = Boolean(data.is_network_master ?? data.is_network);
        const memberFlag = Boolean(data.is_network_member ?? currentBusiness?.network_id);
        const isLegacyMasterById = String(data.network_id || '') === String(currentBusinessId);
        const parentBusinessId = String(data.parent_business_id || '').trim();
        const isParentLocation = parentBusinessId.length > 0 && parentBusinessId === String(currentBusinessId || '').trim();
        setIsNetworkMaster(masterFlag && !memberFlag && isLegacyMasterById && !isParentLocation);
      }
    } catch (error) {
      console.error('Ошибка проверки сети:', error);
      setIsNetworkMaster(false);
    }
  };

  const serviceControlsCopy = {
    addService: t.dashboard.card.addService,
    category: t.dashboard.card.category,
    serviceName: t.dashboard.card.serviceName,
    description: t.dashboard.card.description,
    keywords: t.dashboard.card.keywords,
    price: t.dashboard.card.price,
    cancel: t.dashboard.card.cancel,
    add: t.dashboard.card.add,
    save: t.dashboard.card.save || t.dashboard.card.add,
    edit: t.dashboard.card.edit || 'Редактирование услуги',
    optimizeAll: t.dashboard.card.optimizeAll,
    seoTitle: t.dashboard.card.seo.title,
    seoDescription: t.dashboard.card.seo.desc1 + ' ' + t.dashboard.card.seo.desc2,
    placeholders: {
      category: t.dashboard.card.placeholders.category,
      name: t.dashboard.card.placeholders.name,
      description: t.dashboard.card.placeholders.desc,
      keywords: t.dashboard.card.placeholders.keywords,
      price: t.dashboard.card.placeholders.price,
    },
    search: t.dashboard.card.search || 'Найти услугу',
  };
  const serviceLastParseDate = servicesLastParseDate || lastParseDate;
  const serviceController = useCardServiceController({
    userServices,
    setUserServices,
    currentBusinessId,
    automationAllowed: automationAccess.automationAllowed,
    automationLockedMessage,
    loadUserServices,
    setError,
    setSuccess,
    copy: {
      serviceName: t.dashboard.card.serviceName,
      deleteConfirm: t.dashboard.card.deleteConfirm,
      success: t.common.success || 'Success',
      error: t.common.error || 'Error',
      accepted: t.common.success || 'Accepted',
      rejected: t.common.success || 'Rejected',
    },
  });
  const {
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
  } = serviceController;

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
        <DashboardPageHeader
          eyebrow={isRu ? 'Карточка бизнеса' : 'Business listing'}
          icon={LayoutGrid}
          title={t.dashboard.card.title}
          description={t.dashboard.card.subtitle}
          actions={(
            <>
              <Button
                type="button"
                onClick={handleRefreshCardData}
                disabled={!currentBusinessId || refreshingCardData || !canTriggerRefresh}
                className="bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-300"
                title={isRu ? 'Запускает сбор свежих данных по вашей карточке на карте.' : 'Starts collecting fresh data from your map listing.'}
              >
                <RefreshCw className={cn("mr-2 h-4 w-4", refreshingCardData ? "animate-spin" : "")} />
                {refreshingCardData ? (isRu ? 'Запускаем обновление...' : 'Starting refresh...') : (isRu ? 'Обновить данные карточки' : 'Refresh card data')}
              </Button>
              <a
                href="/dashboard/progress"
                title={isRu ? 'Открывает аудит карточки, метрики и историю изменений.' : 'Opens the listing audit, metrics, and change history.'}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-100"
              >
                <FileSearch className="w-4 h-4" />
                <span>{t.dashboard.card.progressTab}</span>
              </a>
            </>
          )}
        />

        <DashboardCompactMetricsRow
          className="mt-6"
          items={[
            {
              label: isRu ? 'Рейтинг' : 'Rating',
              value: rating != null ? Number(rating).toFixed(1) : '—',
              hint: isRu ? 'Средняя оценка карточки на карте.' : 'Average map listing rating.',
            },
            {
              label: isRu ? 'Отзывы' : 'Reviews',
              value: reviewsTotal,
              hint: isRu ? 'Текущий объём отзывов в карточке.' : 'Current review volume in the listing.',
            },
            {
              label: isRu ? 'Последнее обновление' : 'Last refresh',
              value: lastParseDate
                ? new Date(lastParseDate).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US')
                : '—',
              hint: isRu ? 'Когда данные в разделе обновлялись в последний раз.' : 'When the section data was last refreshed.',
            },
            {
              label: isRu ? 'Источники карт' : 'Map sources',
              value: mapSources.length || 0,
              hint: isRu ? 'Подключённые карточки для этой точки.' : 'Connected map profiles for this location.',
            },
          ]}
        />

        <DashboardActionPanel
          className="mt-6"
          tone="amber"
          title={firstRunCopy.title}
          description={!hasConfiguredMapLink
            ? firstRunCopy.bodyMissingMap
            : (isRu ? (
              <>
                Обновляйте карточку здесь, а аудит и историю изменений проверяйте в <span className="font-semibold">«Прогрессе»</span>.
                Если нужно изменить ссылку или точку входа, это делается через <span className="font-semibold">«Профиль и бизнес»</span>.
              </>
            ) : (
              <>
                Refresh the listing here, and review the audit and history in <span className="font-semibold">Progress</span>.
                If you need to change the source link, do it in <span className="font-semibold">Profile &amp; Business</span>.
              </>
            ))}
          status={(
            <span>
              {isRu ? 'Сейчас: ' : 'Now: '}
              <span className="font-semibold">{parseStatusLabel}</span>
              {hasConfiguredMapLink && !canRefreshCardData && mapSources.length > 0
                ? (isRu ? ' · Обновление сейчас поддержано для Яндекс и 2ГИС.' : ' · Refresh is currently supported for Yandex and 2GIS.')
                : ''}
              {parseStatusHelpText ? (
                <span className="mt-1 block font-normal text-slate-600">{parseStatusHelpText}</span>
              ) : null}
            </span>
          )}
          actions={!hasConfiguredMapLink ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/dashboard/profile')}
              className="border-slate-200 bg-white text-slate-800 hover:bg-slate-100"
              title={isRu ? 'Открывает раздел, где нужно сохранить ссылку на карту перед первым аудитом.' : 'Opens the section where you need to save the map link before the first audit.'}
            >
              <ArrowRight className="mr-2 h-4 w-4" />
              {firstRunCopy.goToProfile}
            </Button>
          ) : (
            <a
              href="/dashboard/progress"
              title={isRu ? 'Открывает аудит карточки, бизнес-метрики и историю изменений после сбора данных.' : 'Opens the listing audit, business metrics, and change history after data collection.'}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-100"
            >
              <TrendingUp className="h-4 w-4" />
              {isRu ? 'Открыть прогресс' : 'Open progress'}
            </a>
          )}
        />

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
          <div className="mb-6 inline-flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-slate-50/80 p-2">
            <button
              onClick={() => setSelectedSource('all')}
              className={cn(
                "rounded-xl px-4 py-2 text-sm font-medium transition-all",
                selectedSource === 'all'
                  ? "bg-white text-slate-950 shadow-sm ring-1 ring-slate-200"
                  : "text-slate-500 hover:bg-white hover:text-slate-900"
              )}
            >
              Все карты
            </button>
            {mapSources.map(source => (
              <button
                key={source}
                onClick={() => setSelectedSource(source)}
                className={cn(
                  "rounded-xl px-4 py-2 text-sm font-medium capitalize transition-all",
                  selectedSource === source
                    ? "bg-white text-slate-950 shadow-sm ring-1 ring-slate-200"
                    : "text-slate-500 hover:bg-white hover:text-slate-900"
                )}
              >
                {formatMapSourceTab(source)}
              </button>
            ))}
          </div>
        )}

        <Tabs
          value={activeTab}
          onValueChange={(value) => {
            const nextTab = isCardTabValue(value) ? value : 'services';
            setActiveTab(nextTab);
            const nextParams = new URLSearchParams(searchParams);
            if (nextTab === 'services') {
              nextParams.delete('tab');
            } else {
              nextParams.set('tab', nextTab);
            }
            if (nextTab !== 'reviews') {
              nextParams.delete('review_filter');
            } else if (!nextParams.get('review_filter')) {
              nextParams.set('review_filter', 'all');
            }
            setSearchParams(nextParams, { replace: true });
          }}
          className="space-y-8"
        >
          <TabsList className="flex w-full justify-start overflow-x-auto rounded-2xl border border-slate-200 bg-slate-50/80 p-1.5 [&::-webkit-scrollbar]:hidden">
            <TabsTrigger value="services" className="gap-2 rounded-xl px-5 py-2.5 text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm">
              <List className="w-4 h-4" />
              {t.dashboard.card.tabServices || "Services"}
            </TabsTrigger>
            <TabsTrigger value="reviews" className="gap-2 rounded-xl px-5 py-2.5 text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm">
              <MessageSquare className="w-4 h-4" />
              {t.dashboard.card.tabReviews || "Reviews"}
            </TabsTrigger>
            <TabsTrigger value="news" className="gap-2 rounded-xl px-5 py-2.5 text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm">
              <Newspaper className="w-4 h-4" />
              {t.dashboard.card.tabNews || "News"}
            </TabsTrigger>
            <TabsTrigger value="keywords" className="gap-2 rounded-xl px-5 py-2.5 text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm">
              <TrendingUp className="w-4 h-4" />
              SEO (Wordstat)
            </TabsTrigger>
            <TabsTrigger value="competitors" className="gap-2 rounded-xl px-5 py-2.5 text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm">
              <Trophy className="w-4 h-4" />
              Конкуренты
            </TabsTrigger>
          </TabsList>

          {user?.is_superadmin && (
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
              <div className="flex items-center justify-between gap-2 mb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-indigo-900">Обучение ИИ (30 дней)</h3>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          className="inline-flex items-center justify-center rounded-full text-indigo-500 transition-colors hover:text-indigo-700"
                          aria-label={aiLearningTooltip}
                        >
                          <Info className="h-4 w-4" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-sm text-xs leading-5">
                        {aiLearningTooltip}
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <p className="text-xs text-indigo-700">Улучшения по услугам, отзывам и новостям</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-indigo-200 text-indigo-800 hover:bg-indigo-100"
                  onClick={loadOperationsLearning}
                >
                  Обновить
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
                {[
                  { key: 'services.optimize', label: 'Оптимизация услуг' },
                  { key: 'reviews.reply', label: 'Ответы на отзывы' },
                  { key: 'news.generate', label: 'Генерация новостей' },
                ].map((row) => {
                  const metric = operationsLearning[row.key] || {};
                  return (
                    <div key={row.key} className="rounded-lg border border-indigo-100 bg-white p-3">
                      <div className="font-medium text-gray-900">{row.label}</div>
                      <div className="text-xs text-gray-600 mt-1">
                        raw: {metric.accepted_raw_pct ?? 0}% · edited: {metric.edited_before_accept_pct ?? 0}%
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        Принято: {metric.accepted_total ?? 0} · prompt: {metric.prompt_version || '—'}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}


          <TabsContent value="competitors" className="space-y-6">
            <CompetitorsTab
              manualCompetitorUrl={manualCompetitorUrl}
              onManualCompetitorUrlChange={setManualCompetitorUrl}
              manualCompetitorName={manualCompetitorName}
              onManualCompetitorNameChange={setManualCompetitorName}
              addingManualCompetitor={addingManualCompetitor}
              onAddManualCompetitor={addManualCompetitor}
              manualCompetitors={manualCompetitors}
              competitors={competitors}
              requestingAuditId={requestingAuditId}
              deletingManualCompetitorId={deletingManualCompetitorId}
              onRequestAudit={requestAudit}
              onDeleteManualCompetitor={deleteManualCompetitor}
            />
          </TabsContent>

          <TabsContent value="services" className="space-y-6">
            {/* Rating Summary Card */}
            <DashboardSection title={t.dashboard.card.rating || "Rating Overview"} description="Короткая сводка по рейтингу и отзывам карточки.">
                <div className="flex justify-between items-start mb-5">
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
            </DashboardSection>

            {/* Services Section */}
            <DashboardSection
              title={t.dashboard.card.services}
              description={t.dashboard.card.servicesSubtitle}
              actions={!showAddService ? (
                <Button onClick={() => setShowAddService(true)} className="bg-primary text-white shadow-sm">
                  <Plus className="w-4 h-4 mr-2" />
                  {t.dashboard.card.addService}
                </Button>
              ) : null}
            >
              {showAddService ? (
                <CardServiceAddForm
                  copy={serviceControlsCopy}
                  value={newService}
                  onChange={setNewService}
                  onCancel={() => setShowAddService(false)}
                  onSubmit={addService}
                />
              ) : (
                <CardServiceOptimizerPanel
                  copy={serviceControlsCopy}
                  businessName={currentBusiness?.name}
                  businessId={currentBusinessId}
                  language={language}
                  servicesCount={userServices.length}
                  automationAllowed={automationAccess.automationAllowed}
                  automationLockedMessage={automationLockedMessage}
                  optimizingAll={optimizingAll}
                  optimizingServiceId={optimizingServiceId}
                  onOptimizeAll={optimizeAllServices}
                  onServicesImported={loadUserServices}
                />
              )}

              <CardServicesMetaStrip
                lastParseDate={serviceLastParseDate}
                noNewServicesFound={servicesNoNewFromParse}
                locale={language === 'ru' ? 'ru-RU' : 'en-US'}
              />

              <CardServicesFilterBar
                copy={serviceControlsCopy}
                search={servicesSearch}
                onSearchChange={setServicesSearch}
                categoryFilter={servicesCategoryFilter}
                onCategoryFilterChange={setServicesCategoryFilter}
                categories={serviceCategories}
                sort={servicesSort}
                onSortChange={(value) => setServicesSort(toServicesSort(value))}
              />

              <CardServicesTable
                tableScrollRef={servicesTableScrollRef}
                copy={{
                  category: t.dashboard.card.table.category,
                  source: 'Источник',
                  name: t.dashboard.card.table.name,
                  description: t.dashboard.card.table.description,
                  price: t.dashboard.card.table.price,
                  updated: t.common?.updated || 'Updated',
                  actions: t.dashboard.card.table.actions,
                  processing: t.dashboard.subscription.processing,
                  emptyFiltered: 'Ничего не найдено по выбранным фильтрам',
                  emptyDefault: t.dashboard.network.noData,
                  proposal: t.dashboard.card.seo.proposal,
                  accept: t.dashboard.card.seo.accept,
                  reject: t.dashboard.card.seo.reject,
                  optimize: t.dashboard.card.optimize,
                  edit: t.dashboard.card.edit || 'Редактировать',
                }}
                services={pagedServices}
                filteredCount={filteredServices.length}
                loading={loadingServices}
                servicesSearch={servicesSearch}
                servicesCategoryFilter={servicesCategoryFilter}
                language={language}
                automationAllowed={automationAccess.automationAllowed}
                automationLockedMessage={automationLockedMessage}
                optimizingServiceId={optimizingServiceId}
                formatServiceSource={formatServiceSource}
                getOptimizedNameValue={getOptimizedNameValue}
                getOptimizedDescriptionValue={getOptimizedDescriptionValue}
                getMatchedKeywords={getMatchedKeywords}
                isDraftSimilarToCurrent={isDraftSimilarToCurrent}
                getDisplayedServiceUpdatedAt={(service) =>
                  getDisplayedServiceUpdatedAt(service, servicesLastParseDate, lastParseDate, servicesNoNewFromParse)
                }
                onOptimizedNameDraftChange={(serviceId, value) => setOptimizedNameDrafts((prev) => ({ ...prev, [serviceId]: value }))}
                onOptimizedDescriptionDraftChange={(serviceId, value) => setOptimizedDescriptionDrafts((prev) => ({ ...prev, [serviceId]: value }))}
                onAcceptOptimizedName={acceptOptimizedServiceName}
                onRejectOptimizedName={rejectOptimizedServiceName}
                onAcceptOptimizedDescription={acceptOptimizedServiceDescription}
                onRejectOptimizedDescription={rejectOptimizedServiceDescription}
                onOptimizeService={(serviceId) => optimizeService(serviceId)}
                onEditService={openEditService}
                onDeleteService={deleteService}
              />

            </DashboardSection>
          </TabsContent>

          <TabsContent value="reviews">
            <ReviewsTab
              automationAllowed={automationAccess.automationAllowed}
              automationLockedMessage={automationLockedMessage}
              businessName={currentBusiness?.name}
              selectedSource={selectedSource}
              aggregateScope={isNetworkRepresentative ? 'network' : 'business'}
              onOpenLocation={onBusinessChange}
              initialFilter={reviewFocus}
            />
          </TabsContent>

          <TabsContent value="news">
            <NewsTab
              automationAllowed={automationAccess.automationAllowed}
              automationLockedMessage={automationLockedMessage}
              services={(userServices || []).map((service) => ({ id: String(service.id || ''), name: String(service.name || '') }))}
              businessId={currentBusinessId}
              externalPosts={externalPosts}
              selectedSource={selectedSource}
            />
          </TabsContent>

          <TabsContent value="keywords">
            <KeywordsTab businessId={currentBusinessId} />
          </TabsContent>
        </Tabs>
        {editingService ? (
          <CardServiceEditDialog
            copy={serviceControlsCopy}
            value={editServiceForm}
            onChange={setEditServiceForm}
            onCancel={() => setEditingService(null)}
            onSave={saveEditedService}
          />
        ) : null}
      </div>
    </div>
  );
};
