import { useState, useEffect, useRef, type ReactNode } from 'react';
import { useLocation, useOutletContext, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { newAuth } from '@/lib/auth_new';
import { Network, MapPin, User, Building2, Clock, Mail, Phone, Edit2, ShieldCheck, AlertTriangle, CheckCircle2, ArrowRight, FileSearch, Plus, Trash2, Info, ExternalLink } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';
import { cn } from '@/lib/utils';
import { SubscriptionManagement } from '@/components/SubscriptionManagement';
import { UserTokenUsageSummary } from '@/components/UserTokenUsageSummary';
import { useToast } from '@/hooks/use-toast';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';

type ProfileStatusItem = {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: 'default' | 'positive' | 'warning';
};

const ProfileStatusStrip = ({
  items,
  action,
  note,
  title,
}: {
  items: ProfileStatusItem[];
  action: ReactNode;
  note: ReactNode;
  title: string;
}) => (
  <section className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-sm">
    <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          {title}
        </div>
        <div className="mt-1 text-sm leading-6 text-slate-600">
          {note}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        {action}
      </div>
    </div>
    <div className="grid gap-px bg-slate-100 md:grid-cols-2 2xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="min-w-0 bg-white px-5 py-4">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'h-2.5 w-2.5 rounded-full',
                item.tone === 'positive'
                  ? 'bg-emerald-400'
                  : item.tone === 'warning'
                    ? 'bg-amber-400'
                    : 'bg-slate-300'
              )}
            />
            <div className="truncate text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {item.label}
            </div>
          </div>
          <div className="mt-2 truncate text-lg font-semibold text-slate-950">
            {item.value}
          </div>
          {item.hint ? (
            <div className="mt-1 line-clamp-2 text-sm leading-5 text-slate-600">
              {item.hint}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  </section>
);

const defaultBusinessTypeOptions: Array<{ type_key: string; label: string }> = [
  { type_key: 'beauty_salon', label: 'Салон красоты' },
  { type_key: 'barbershop', label: 'Барбершоп' },
  { type_key: 'spa', label: 'SPA/Wellness' },
  { type_key: 'nail_studio', label: 'Ногтевая студия' },
  { type_key: 'cosmetology', label: 'Косметология' },
  { type_key: 'massage', label: 'Массаж' },
  { type_key: 'brows_lashes', label: 'Брови и ресницы' },
  { type_key: 'makeup', label: 'Макияж' },
  { type_key: 'tanning', label: 'Солярий' },
  { type_key: 'auto_service', label: 'СТО (Автосервис)' },
  { type_key: 'gas_station', label: 'АЗС (Автозаправка)' },
  { type_key: 'cafe', label: 'Кафе' },
  { type_key: 'school', label: 'Школа' },
  { type_key: 'workshop', label: 'Мастерская' },
  { type_key: 'shoe_repair', label: 'Ремонт обуви' },
  { type_key: 'gym', label: 'Спортзал' },
  { type_key: 'shawarma', label: 'Шаверма' },
  { type_key: 'theater', label: 'Театр' },
  { type_key: 'hotel', label: 'Отель' },
  { type_key: 'guest_house', label: 'Гостевой дом' },
  { type_key: 'other', label: 'Другое' },
];

const FieldHint = ({ text }: { text: string }) => (
  <Tooltip>
    <TooltipTrigger asChild>
      <button
        type="button"
        className="inline-flex items-center justify-center rounded-full text-slate-400 transition-colors hover:text-slate-600"
        aria-label={text}
      >
        <Info className="h-4 w-4" />
      </button>
    </TooltipTrigger>
    <TooltipContent className="max-w-xs text-xs leading-5">
      {text}
    </TooltipContent>
  </Tooltip>
);

const isGoogleMapUrl = (value: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return false;
  if (normalized.includes('google.com/maps') || normalized.includes('maps.app.goo.gl') || normalized.includes('share.google')) {
    return true;
  }
  if (
    (normalized.includes('maps.google.') || normalized.includes('google.com')) &&
    (
      normalized.includes('?cid=') ||
      normalized.includes('&cid=') ||
      normalized.includes('?ludocid=') ||
      normalized.includes('&ludocid=') ||
      normalized.includes('?kgmid=') ||
      normalized.includes('&kgmid=')
    )
  ) {
    return true;
  }
  return (
    normalized.includes('google.com/search') &&
    (
      normalized.includes('stick=') ||
      normalized.includes('kgmid=') ||
      normalized.includes('ludocid=') ||
      normalized.includes('cid=')
    )
  );
};

export const ProfilePage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, currentBusinessId, currentBusiness, updateBusiness, businesses, setBusinesses, reloadBusinesses, onBusinessChange } = useOutletContext<any>();
  const [editMode, setEditMode] = useState(false);
  const [editClientInfo, setEditClientInfo] = useState(false);
  const { t, language } = useLanguage();
  const { toast } = useToast();
  const isRu = language === 'ru';
  const previousParseStatusRef = useRef<string>('idle');
  const businessInfoSectionRef = useRef<HTMLElement | null>(null);
  const subscriptionSectionRef = useRef<HTMLDivElement | null>(null);

  // Функция для преобразования значения типа бизнеса в читаемый текст
  const getBusinessTypeLabel = (type: string): string => {
    const apiType = businessTypes.find((x) => x.type_key === type);
    if (apiType?.label) return apiType.label;
    const typeKey = type as keyof typeof t.dashboard.profile.businessTypes;
    return t.dashboard.profile.businessTypes[typeKey] || type || '';
  };
  const [savingClientInfo, setSavingClientInfo] = useState(false);
  const [form, setForm] = useState({ email: "", phone: "", name: "" });
  const [clientInfo, setClientInfo] = useState({
    businessName: '',
    businessType: '',
    address: '',
    city: '',
    citySuggestion: '',
    website: '',
    workingHours: '',
    mapLinks: [] as { id?: string; url: string; mapType?: string }[]
  });
  const [savedClientInfo, setSavedClientInfo] = useState({
    businessName: '',
    businessType: '',
    address: '',
    city: '',
    citySuggestion: '',
    website: '',
    workingHours: '',
    mapLinks: [] as { id?: string; url: string; mapType?: string }[]
  });
  // parsequeue canonical status: 'completed'; API and backend also accept legacy 'done'
  const [parseStatus, setParseStatus] = useState<'idle' | 'processing' | 'completed' | 'done' | 'error' | 'queued' | 'captcha'>('idle');
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [retryInfo, setRetryInfo] = useState<{ hours: number; minutes: number } | null>(null);
  const [retryCountdown, setRetryCountdown] = useState<{ hours: number; minutes: number } | null>(null);
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
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [sendingCredentials, setSendingCredentials] = useState(false);
  const [networkLocations, setNetworkLocations] = useState<any[]>([]);
  const [isNetwork, setIsNetwork] = useState(false);
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [businessTypes, setBusinessTypes] = useState<Array<{ type_key: string; label: string }>>([]);
  const [isNetworkMaster, setIsNetworkMaster] = useState(false);
  const hasMapLinks = (clientInfo.mapLinks || []).some((link) => String(link?.url || '').trim().length > 0);
  const hasSavedMapLinks = (savedClientInfo.mapLinks || []).some((link) => String(link?.url || '').trim().length > 0);
  const effectiveBusinessId = currentBusinessId || (Array.isArray(businesses) && businesses.length === 1 ? businesses[0]?.id || null : null);

  const normalizeMapLinks = (links: { id?: string; url: string; mapType?: string }[]) =>
    (Array.isArray(links) ? links : [])
      .map((link) => ({
        url: String(link?.url || '').trim(),
        mapType: String(link?.mapType || '').trim(),
      }))
      .filter((link) => link.url.length > 0)
      .sort((a, b) => a.url.localeCompare(b.url));

  const normalizeClientInfoForCompare = (value: typeof clientInfo) => ({
    businessName: String(value.businessName || '').trim(),
    businessType: String(value.businessType || '').trim(),
    address: String(value.address || '').trim(),
    city: String(value.city || '').trim(),
    website: String(value.website || '').trim(),
    workingHours: String(value.workingHours || '').trim(),
    mapLinks: normalizeMapLinks(value.mapLinks),
  });
  const hasUnsavedClientInfoChanges = JSON.stringify(normalizeClientInfoForCompare(clientInfo)) !== JSON.stringify(normalizeClientInfoForCompare(savedClientInfo));

  const detectMapType = (url: string) => {
    const normalized = String(url || '').toLowerCase();
    if (!normalized) return 'other';
    if (normalized.includes('yandex.ru') || normalized.includes('yandex.com')) return 'yandex';
    if (normalized.includes('2gis.ru') || normalized.includes('2gis.com')) return '2gis';
    if (isGoogleMapUrl(normalized)) return 'google';
    if (normalized.includes('maps.apple.com')) return 'apple';
    return 'other';
  };

  const supportedMapSource = (() => {
    const links = Array.isArray(clientInfo.mapLinks) ? clientInfo.mapLinks : [];
    for (const link of links) {
      const type = detectMapType(String(link?.url || ''));
      if (type === 'yandex') return 'yandex';
      if (type === '2gis') return '2gis';
    }
    return null;
  })();
  const formatRefreshDate = (isoValue: string | null) => {
    if (!isoValue) return null;
    const parsedDate = new Date(isoValue);
    if (Number.isNaN(parsedDate.getTime())) return isoValue;
    return new Intl.DateTimeFormat(isRu ? 'ru-RU' : 'en-US', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(parsedDate);
  };

  const parseStatusLabel = (() => {
    if (parseRefreshPolicy.reason === 'active_parse') {
      return isRu ? 'Сейчас собираем данные карточки' : 'We are collecting listing data now';
    }
    if (parseStatus === 'completed' || parseStatus === 'done') {
      return isRu ? 'Аудит готов' : 'Audit is ready';
    }
    if (parseStatus === 'processing') {
      return isRu ? 'Сбор данных выполняется' : 'Data collection in progress';
    }
    if (parseStatus === 'queued') {
      return isRu ? 'Сбор данных в очереди' : 'Data collection is queued';
    }
    if (parseStatus === 'error') {
      return isRu ? 'Последний запуск завершился с ошибкой' : 'The latest run ended with an error';
    }
    if (!hasMapLinks) {
      return isRu ? 'Сначала добавьте ссылку на карту' : 'Add a map link first';
    }
    if (hasUnsavedClientInfoChanges) {
      return isRu ? 'Сначала сохраните изменения в информации о бизнесе' : 'Save the business info changes first';
    }
    return isRu ? 'Можно запускать первый аудит' : 'Ready to start the first audit';
  })();

  const parseStatusHelpText = (() => {
    if (!hasMapLinks) {
      return isRu
        ? 'Добавьте ссылку на карту в этом разделе, чтобы LocalOS смог спарсить карточку и собрать аудит.'
        : 'Add a map link in this section so LocalOS can parse the listing and build the audit.';
    }
    if (hasUnsavedClientInfoChanges) {
      return isRu
        ? 'Вы изменили данные бизнеса, но ещё не сохранили их. Сначала нажмите «Сохранить», чтобы запуск аудита использовал актуальную ссылку на карту.'
        : 'You changed the business info but have not saved it yet. Click “Save” first so the audit uses the current map link.';
    }
    if (!supportedMapSource) {
      return isRu
        ? 'Автосбор данных сейчас поддержан для Яндекс и 2ГИС. Если ссылка ведёт на другой сервис, аудит автоматически не запустится.'
        : 'Automatic data collection is currently supported for Yandex and 2GIS. Links to other services will not start the audit automatically.';
    }
    if (parseRefreshPolicy.reason === 'active_parse' || parseStatus === 'processing' || parseStatus === 'queued') {
      return isRu
        ? 'После завершения мы покажем уведомление, а сам аудит появится во вкладке «Прогресс».'
        : 'When the collection finishes, we will show a notification and the audit will appear in the Progress tab.';
    }
    if (parseRefreshPolicy.reason === 'weekly_cooldown') {
      const formattedDate = formatRefreshDate(parseRefreshPolicy.cooldown_until);
      if (formattedDate) {
        return isRu
          ? `Повторный сбор доступен ${formattedDate}. Если пригласить друга, доступ откроется раньше.`
          : `The next refresh will be available on ${formattedDate}. Inviting a friend unlocks it earlier.`;
      }
    }
    if (parseStatus === 'completed' || parseStatus === 'done') {
      return isRu
        ? 'Откройте «Прогресс», чтобы посмотреть аудит и статистику карточки.'
        : 'Open Progress to review the audit and listing metrics.';
    }
    if (parseStatus === 'error') {
      return isRu
        ? 'Если аудит не собрался, проверьте ссылку на карту и запустите сбор в разделе «Работа с картами».'
        : 'If the audit did not complete, check the map link and run collection in Maps workspace.';
    }
    return isRu
      ? 'После сохранения ссылки перейдите в «Работа с картами», чтобы обновить данные карточки.'
      : 'After saving the link, go to Maps workspace to refresh listing data.';
  })();

  const businessInfoHelperText = isRu
    ? 'Добавьте ваш город, тип бизнеса и ссылку на бизнес на картах. Это нужно для сбора данных по заполнению вашей карточки, расчёта показателей, SEO-оптимизации и создания аудита.'
    : 'Add your city, business type, and business map link. This is needed to collect listing data, calculate metrics, prepare SEO optimization, and generate the audit.';
  const fieldHints = {
    businessName: isRu
      ? 'Название используется в карточке бизнеса, аудите и аналитике.'
      : 'The name is used in the business listing, audit, and analytics.',
    businessType: isRu
      ? 'Тип бизнеса помогает подобрать правильные проверки, KPI и рекомендации в аудите.'
      : 'The business type helps choose the right checks, KPIs, and audit recommendations.',
    address: isRu
      ? 'Укажите фактический адрес бизнеса. Это помогает сверять данные карточки с реальным бизнесом.'
      : 'Enter the actual business address. This helps match the listing with the real business.',
    city: isRu
      ? 'Город нужен для локального SEO, расчёта показателей и корректной геопривязки бизнеса.'
      : 'The city is needed for local SEO, metric calculation, and correct geo context.',
    workingHours: isRu
      ? 'Часы работы используются для проверки заполненности карточки и актуальности данных.'
      : 'Working hours are used to verify listing completeness and data accuracy.',
    website: isRu
      ? 'Сайт используется в карточке бизнеса, генерации новостей и описаний, а также как источник фактов о компании.'
      : 'The website is used in the business profile, news generation, descriptions, and as a factual source about the company.',
    mapLinks: isRu
      ? 'Добавьте ссылку на карточку в Яндекс или 2ГИС. По ней LocalOS запускает сбор данных и создаёт аудит.'
      : 'Add the listing link from Yandex or 2GIS. LocalOS uses it to collect data and create the audit.',
  };

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const shouldFocusSubscription = (
      location.hash === '#subscription' ||
      params.get('focus') === 'subscription' ||
      params.get('payment') === 'required'
    );
    if (!shouldFocusSubscription) return;
    window.setTimeout(() => {
      subscriptionSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 120);
  }, [location.hash, location.search]);

  useEffect(() => {
    const checkIfNetworkMaster = async () => {
      if (!currentBusinessId) {
        setIsNetworkMaster(false);
        return;
      }
      try {
        const data = await newAuth.makeRequest(`/business/${currentBusinessId}/network-locations`);
        setIsNetworkMaster(data.is_network || false);
        if (data.locations) setNetworkLocations(data.locations);
      } catch (error) {
        console.error('Network check error:', error);
      }
    };
    checkIfNetworkMaster();
  }, [currentBusinessId]);

  useEffect(() => {
    // Если есть currentBusiness и это не наш бизнес, загружаем данные владельца
    if (currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id) {
      // Показываем данные владельца из currentBusiness (если есть) или загружаем
      if (currentBusiness.owner_email || currentBusiness.owner_name) {
        setForm({
          email: currentBusiness.owner_email || "",
          phone: currentBusiness.owner_phone || "",
          name: currentBusiness.owner_name || ""
        });
      } else {
        // Загружаем данные владельца бизнеса через API
        loadOwnerData();
      }
    } else if (user) {
      // Показываем данные текущего пользователя
      setForm({
        email: user.email || "",
        phone: user.phone || "",
        name: user.name || ""
      });
    }
  }, [user, currentBusiness, currentBusinessId]);

  const loadOwnerData = async () => {
    if (!currentBusinessId) return;

    try {
      const data = await newAuth.makeRequest(`/client-info?business_id=${currentBusinessId}`);
      if (data.owner) {
        // Показываем данные владельца бизнеса
        setForm({
          email: data.owner.email || "",
          phone: data.owner.phone || "",
          name: data.owner.name || ""
        });
      }
    } catch (error) {
      console.error('Ошибка загрузки данных владельца:', error);
    }
  };

  useEffect(() => {
    const loadBusinessTypes = async () => {
      try {
        const data = await newAuth.makeRequest('/business-types');
        if (Array.isArray(data.types)) {
          setBusinessTypes(data.types);
        }
      } catch (e) {
        console.error('Ошибка загрузки типов бизнеса:', e);
      }
    };
    loadBusinessTypes();
  }, []);

  useEffect(() => {
    const loadClientInfo = async () => {
      try {
        const qs = currentBusinessId ? `?business_id=${currentBusinessId}` : '';
        const data = await newAuth.makeRequest(`/client-info${qs}`);

        // Если есть данные владельца бизнеса и это не наш бизнес, обновляем форму
        if (data.owner && currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id) {
          setForm({
            email: data.owner.email || "",
            phone: data.owner.phone || "",
            name: data.owner.name || ""
          });
        }

        // Загружаем точки сети ТОЛЬКО если текущий бизнес является частью сети
        if (currentBusiness?.network_id) {
          loadNetworkLocations();
        }

        // Нормализуем mapLinks: сервер возвращает объекты с полями id, url, mapType, createdAt
        const normalizedMapLinks = (data.mapLinks && Array.isArray(data.mapLinks)
          ? data.mapLinks.map((link: any) => ({
            id: link.id,
            url: link.url || '',
            mapType: link.mapType || link.map_type
          }))
          : []);

        const businessType = data.businessType || currentBusiness?.business_type || '';
        const nextClientInfo = {
          businessName: data.businessName || '',
          businessType: businessType,
          address: data.address || '',
          city: data.city ?? '',
          citySuggestion: data.citySuggestion ?? '',
          website: data.website || data.site || '',
          workingHours: data.workingHours || t.dashboard.profile.workingHoursPlaceholder,
          mapLinks: normalizedMapLinks
        };
        setClientInfo(nextClientInfo);
        setSavedClientInfo(nextClientInfo);
      } catch (error) {
        console.error('Ошибка загрузки информации о бизнесе:', error);
      }
    };
    loadClientInfo();
  }, [currentBusinessId]);

  const loadParseStatus = async () => {
    if (!effectiveBusinessId) {
      setParseStatus('idle');
      return;
    }

    try {
      const response = await fetch(`${window.location.origin}/api/business/${effectiveBusinessId}/parse-status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success) {
        return;
      }

      const nextStatusRaw = String(data.status || 'idle').trim().toLowerCase();
      const nextStatus = (
        nextStatusRaw === 'processing' ||
        nextStatusRaw === 'completed' ||
        nextStatusRaw === 'done' ||
        nextStatusRaw === 'error' ||
        nextStatusRaw === 'queued' ||
        nextStatusRaw === 'captcha'
      ) ? nextStatusRaw : 'idle';

      setParseErrors(Array.isArray(data.errors) ? data.errors.map((item: unknown) => String(item || '').trim()).filter(Boolean) : []);
      const refreshPolicy = data.refresh_policy && typeof data.refresh_policy === 'object' ? data.refresh_policy : {};
      setParseRefreshPolicy({
        can_refresh: Boolean(refreshPolicy.can_refresh ?? true),
        reason: String(refreshPolicy.reason || '').trim() || null,
        message: String(refreshPolicy.message || '').trim() || null,
        cooldown_days: Number(refreshPolicy.cooldown_days || 7),
        last_completed_at: String(refreshPolicy.last_completed_at || '').trim() || null,
        cooldown_until: String(refreshPolicy.cooldown_until || '').trim() || null,
        invite_override_available: Boolean(refreshPolicy.invite_override_available),
        accepted_invites_count: Number(refreshPolicy.accepted_invites_count || 0),
      });
      setParseStatus(nextStatus);
    } catch (loadError) {
      console.error('Ошибка загрузки статуса парсинга:', loadError);
    }
  };

  useEffect(() => {
    void loadParseStatus();
  }, [effectiveBusinessId]);

  useEffect(() => {
    if (parseStatus !== 'processing' && parseStatus !== 'queued') {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void loadParseStatus();
    }, 10000);

    return () => window.clearInterval(timer);
  }, [parseStatus, effectiveBusinessId]);

  useEffect(() => {
    const previousStatus = previousParseStatusRef.current;
    if ((previousStatus === 'processing' || previousStatus === 'queued') && (parseStatus === 'completed' || parseStatus === 'done')) {
      const message = isRu
        ? 'Аудит карточки готов. Откройте вкладку «Прогресс», чтобы посмотреть результат.'
        : 'The card audit is ready. Open the Progress tab to review it.';
      setSuccess(message);
      toast({
        title: isRu ? 'Аудит готов' : 'Audit ready',
        description: message,
      });
    }
    if ((previousStatus === 'processing' || previousStatus === 'queued') && parseStatus === 'error') {
      const description = parseErrors[0] || (isRu ? 'Не удалось завершить сбор данных карточки.' : 'Could not complete the listing data collection.');
      toast({
        title: isRu ? 'Сбор данных завершился с ошибкой' : 'Data collection ended with an error',
        description,
        variant: 'destructive',
      });
    }
    previousParseStatusRef.current = parseStatus;
  }, [isRu, parseErrors, parseStatus, toast]);

  const loadNetworkLocations = async () => {
    if (!currentBusinessId) return;

    try {
      setLoadingLocations(true);
      const data = await newAuth.makeRequest(`/business/${currentBusinessId}/network-locations`);
      setIsNetwork(data.is_network || false);
      setNetworkLocations(data.locations || []);
    } catch (error) {
      console.error('Ошибка загрузки точек сети:', error);
    } finally {
      setLoadingLocations(false);
    }
  };

  const handleUpdateProfile = async () => {
    try {
      if (currentBusinessId) {
        const data = await newAuth.makeRequest(`/business/${currentBusinessId}/profile`, {
          method: 'POST',
          body: JSON.stringify({
            contact_name: form.name,
            contact_phone: form.phone,
            contact_email: form.email
          })
        });

        // newAuth.makeRequest throws if not success/ok, assuming success
        setEditMode(false);
        setSuccess(t.dashboard.profile.profileUpdated);
      } else {
        const { user: updatedUser, error } = await newAuth.updateProfile({
          name: form.name,
          phone: form.phone
        });

        if (error) {
          setError(error);
          return;
        }

        setEditMode(false);
        setSuccess(t.dashboard.profile.profileUpdated);
      }
    } catch (error: any) {
      console.error('Ошибка обновления профиля:', error);
      setError(error.message || t.dashboard.profile.errorSave);
    }
  };

  const handleSaveClientInfo = async () => {
    const looksLikeUrl = (value: string) => {
      const text = value.trim().toLowerCase();
      if (!text) return false;
      return (
        text.includes('://') ||
        text.startsWith('www.') ||
        text.includes('yandex.') ||
        text.includes('2gis.') ||
        isGoogleMapUrl(text) ||
        text.includes('maps.apple.com')
      );
    };

    // Определяем бизнес: если не выбран, пытаемся найти автоматически
    let effectiveBusinessId = currentBusinessId;

    if (!effectiveBusinessId) {
      // Если бизнес не выбран, пытаемся найти автоматически
      if (businesses && businesses.length > 0) {
        // Если только один бизнес - используем его
        if (businesses.length === 1) {
          effectiveBusinessId = businesses[0].id;
        }
        // Если есть название бизнеса в clientInfo - ищем по имени
        else if (clientInfo.businessName) {
          const foundBusiness = businesses.find((b: any) =>
            b.name && b.name.toLowerCase().trim() === clientInfo.businessName.toLowerCase().trim()
          );
          if (foundBusiness) {
            effectiveBusinessId = foundBusiness.id;
          }
        }
      }
    }

    // Если бизнес не определён - проверяем, можно ли сохранить без него
    if (!effectiveBusinessId) {
      // Если бизнесов много - просим выбрать
      if (businesses && businesses.length > 1) {
        setError(t.dashboard.profile.selectBusinessToSave);
        setSavingClientInfo(false);
        return;
      }

      // Если бизнесов нет, но есть название - разрешаем сохранение (сохранится в ClientInfo)
      if ((!businesses || businesses.length === 0) && clientInfo.businessName && clientInfo.businessName.trim()) {
        // Продолжаем без businessId - данные сохранятся в ClientInfo
      } else if (!clientInfo.businessName || !clientInfo.businessName.trim()) {
        setError(t.dashboard.profile.businessName + ' required'); // Could be better localized
        setSavingClientInfo(false);
        return;
      } else {
        setError(t.common.error);
        setSavingClientInfo(false);
        return;
      }
    }

    setSavingClientInfo(true);
    try {
      if (looksLikeUrl(clientInfo.address || '')) {
        setError(isRu ? 'Поле «Адрес» не должно содержать ссылку. Добавьте ссылку отдельно в блоке карт.' : 'The address field must not contain a link. Add the map URL separately in the map links section.');
        return;
      }
      if (looksLikeUrl(clientInfo.city || '')) {
        setError(isRu ? 'Поле «Город» не должно содержать ссылку. Добавьте ссылку отдельно в блоке карт.' : 'The city field must not contain a link. Add the map URL separately in the map links section.');
        return;
      }

      // Фильтруем пустые ссылки перед отправкой
      const validMapLinks = (clientInfo.mapLinks || [])
        .map(link => typeof link === 'string' ? link : link.url)
        .filter(url => url && url.trim());

      const payload: any = {
        ...clientInfo,
        workingHours: clientInfo.workingHours || t.dashboard.profile.workingHoursPlaceholder,
        city: (clientInfo.city || '').trim() || undefined,
        mapLinks: validMapLinks.map(url => ({ url: url.trim() }))
      };

      // Добавляем businessId только если он определён
      if (effectiveBusinessId) {
        payload.businessId = effectiveBusinessId;
      }

      await newAuth.makeRequest('/client-info', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      // Всегда перезагружаем данные после сохранения для синхронизации
      // Если businessId был определён - используем его, иначе загружаем без параметра
      const qs = effectiveBusinessId ? `?business_id=${effectiveBusinessId}` : '';
      let reloadData;
      try {
        reloadData = await newAuth.makeRequest(`/client-info${qs}`);
      } catch (e) {
        console.error("Reload failed", e);
      }

      if (reloadData) {
        const normalizedMapLinks = (reloadData.mapLinks && Array.isArray(reloadData.mapLinks)
          ? reloadData.mapLinks.map((link: any) => ({
            id: link.id,
            url: link.url || '',
            mapType: link.mapType || link.map_type
          }))
          : []);
        const businessType = reloadData.businessType || currentBusiness?.business_type || '';
        const nextClientInfo = {
          businessName: reloadData.businessName || '',
          businessType: businessType,
          address: reloadData.address || '',
          city: reloadData.city ?? '',
          citySuggestion: reloadData.citySuggestion ?? '',
          website: reloadData.website || reloadData.site || '',
          workingHours: reloadData.workingHours || t.dashboard.profile.workingHoursPlaceholder,
          mapLinks: normalizedMapLinks
        };
        setClientInfo(nextClientInfo);
        setSavedClientInfo(nextClientInfo);
      }

      setEditClientInfo(false);
      setSuccess(t.dashboard.profile.saveSuccess);

      // Обновляем название бизнеса в списке businesses локально
      if (effectiveBusinessId && updateBusiness) {
        updateBusiness(effectiveBusinessId, {
          name: clientInfo.businessName,
          business_type: clientInfo.businessType,
          address: clientInfo.address,
          site: clientInfo.website,
          website: clientInfo.website,
          working_hours: clientInfo.workingHours
        });
      }

      // Перезагружаем список бизнесов из API для синхронизации (особенно важно для суперадмина)
      if (reloadBusinesses) {
        await reloadBusinesses();
      }

    } catch (error: any) {
      console.error('Ошибка сохранения информации:', error);
      // Проверяем, не истёк ли токен
      if (error.message && error.message.includes('401')) {
        setError(t.common.error);
        localStorage.removeItem('auth_token');
        setTimeout(() => {
          window.location.href = '/login';
        }, 2000);
      } else {
        setError(error.message || t.dashboard.profile.errorSave);
      }
    } finally {
      setSavingClientInfo(false);
    }
  };

  // Функция для обратного отсчёта времени до повтора
  const startCountdown = (initialHours: number, initialMinutes: number) => {
    // Устанавливаем начальное значение
    setRetryCountdown({ hours: initialHours, minutes: initialMinutes });

    let currentHours = initialHours;
    let currentMinutes = initialMinutes;
    let timeoutId: NodeJS.Timeout | null = null;

    const updateCountdown = () => {
      // Проверяем, не закончилось ли время
      if (currentHours === 0 && currentMinutes === 0) {
        setRetryCountdown(null);
        return;
      }

      // Уменьшаем время
      if (currentMinutes > 0) {
        currentMinutes--;
      } else if (currentHours > 0) {
        currentHours--;
        currentMinutes = 59;
      }

      // Обновляем состояние
      setRetryCountdown({ hours: currentHours, minutes: currentMinutes });

      // Планируем следующее обновление через минуту
      timeoutId = setTimeout(updateCountdown, 60000);
    };

    // Первое обновление через минуту (чтобы сразу показать начальное время)
    timeoutId = setTimeout(updateCountdown, 60000);

    // Возвращаем функцию очистки для возможности отмены
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  };

  const profileCompletion = (() => {
    const fieldsTotal = 10;
    let filled = 0;
    if ((form.email || '').trim()) filled++;
    if ((form.phone || '').trim()) filled++;
    if ((form.name || '').trim()) filled++;
    if ((clientInfo.businessName || '').trim()) filled++;
    if ((clientInfo.businessType || '').trim()) filled++;
    if ((clientInfo.address || '').trim()) filled++;
    if ((clientInfo.city || '').trim()) filled++;
    if ((clientInfo.website || '').trim()) filled++;
    if ((clientInfo.workingHours || '').trim()) filled++;
    if (hasSavedMapLinks) filled++;
    return Math.round((filled / fieldsTotal) * 100);
  })();

  const businessTypeOptions = businessTypes.length > 0
    ? businessTypes
    : defaultBusinessTypeOptions;
  const websiteHref = (() => {
    const value = String(clientInfo.website || '').trim();
    if (!value) return '';
    return /^https?:\/\//i.test(value) ? value : `https://${value}`;
  })();

  const scrollToBusinessInfo = () => {
    setEditClientInfo(true);
    window.requestAnimationFrame(() => {
      businessInfoSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const isAuditReady = parseStatus === 'completed' || parseStatus === 'done';
  const primaryProfileAction = (() => {
    if (!hasSavedMapLinks) {
      return {
        label: isRu ? 'Добавить ссылку на карту' : 'Add map link',
        title: isRu ? 'Откроет редактирование блока бизнеса и ссылок на карты.' : 'Opens business and map link editing.',
        onClick: scrollToBusinessInfo,
        disabled: false,
        icon: MapPin,
      };
    }
    if (hasUnsavedClientInfoChanges) {
      return {
        label: isRu ? 'Сохранить изменения' : 'Save changes',
        title: isRu ? 'Сохранит данные бизнеса перед запуском аудита.' : 'Saves business data before running the audit.',
        onClick: handleSaveClientInfo,
        disabled: savingClientInfo,
        icon: CheckCircle2,
      };
    }
    if (isAuditReady) {
      return {
        label: isRu ? 'Открыть прогресс' : 'Open progress',
        title: isRu ? 'Откроет аудит, показатели и историю изменений.' : 'Opens audit, metrics, and change history.',
        onClick: () => navigate('/dashboard/progress?section=maps&audit=open'),
        disabled: false,
        icon: FileSearch,
      };
    }
    return {
      label: isRu ? 'К картам' : 'Maps',
      title: isRu ? 'Открывает раздел работы с картами, где запускается обновление данных карточки.' : 'Opens maps management where listing data refresh is started.',
      onClick: () => navigate('/dashboard/card'),
      disabled: false,
      icon: ArrowRight,
    };
  })();

  const PrimaryProfileIcon = primaryProfileAction.icon;
  const profileStatusItems: ProfileStatusItem[] = [
    {
      label: t.dashboard.profile.completion,
      value: `${profileCompletion}%`,
      hint: profileCompletion === 100
        ? (isRu ? 'Данные заполнены.' : 'Details completed.')
        : (isRu ? 'Осталось заполнить базовые поля.' : 'Complete the remaining basics.'),
      tone: profileCompletion >= 85 ? 'positive' : 'warning',
    },
    {
      label: isRu ? 'Карта' : 'Map',
      value: hasSavedMapLinks ? (isRu ? 'Подключена' : 'Connected') : (isRu ? 'Нужна ссылка' : 'Link needed'),
      hint: hasSavedMapLinks
        ? (isRu ? 'Можно обновлять данные.' : 'Data can be refreshed.')
        : (isRu ? 'Добавьте Яндекс, 2ГИС или Google.' : 'Add Yandex, 2GIS, or Google.'),
      tone: hasSavedMapLinks ? 'positive' : 'warning',
    },
    {
      label: isRu ? 'Аудит' : 'Audit',
      value: parseStatusLabel,
      hint: parseStatusHelpText,
      tone: isAuditReady ? 'positive' : hasSavedMapLinks ? 'default' : 'warning',
    },
    {
      label: isRu ? 'Режим' : 'Mode',
      value: isNetworkMaster ? (isRu ? 'Сеть' : 'Network') : isNetwork ? (isRu ? 'Точка сети' : 'Location') : (isRu ? 'Один бизнес' : 'Single business'),
      hint: isNetworkMaster
        ? (isRu ? 'Данные собираются по точкам сети.' : 'Data is collected by location.')
        : (isRu ? 'Обычный режим кабинета.' : 'Standard dashboard mode.'),
    },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-10">
      <DashboardPageHeader
        eyebrow={isRu ? 'Профиль LocalOS' : 'LocalOS profile'}
        icon={User}
        title={t.dashboard.profile.title}
        description={t.dashboard.profile.subtitle}
        actions={(
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate('/dashboard/card')}
            className="border-slate-200 bg-white text-slate-800 hover:bg-slate-100"
            title={isRu ? 'Открывает раздел работы с картами, услугами, отзывами и SEO.' : 'Opens the maps workspace with services, reviews, and SEO tools.'}
          >
            <ArrowRight className="mr-2 h-4 w-4" />
            {isRu ? 'Работа с картами' : 'Maps workspace'}
          </Button>
        )}
      />

      {error && (
        <div className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50/80 px-4 py-3 text-red-700">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          {error}
        </div>
      )}

      {success && (
        <div className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/80 px-4 py-3 text-emerald-700">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          {success}
        </div>
      )}

      <ProfileStatusStrip
        items={profileStatusItems}
        title={isRu ? 'Статус профиля' : 'Profile status'}
        note={
          isRu
            ? 'Здесь задаются исходные данные бизнеса. После сохранения LocalOS использует их в картах, аудите, новостях и SEO.'
            : 'This page stores the business source data used for maps, audits, posts, and SEO.'
        }
        action={(
          <Button
            type="button"
            onClick={primaryProfileAction.onClick}
            disabled={primaryProfileAction.disabled}
            className="bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-300"
            title={primaryProfileAction.title}
          >
            <PrimaryProfileIcon className="mr-2 h-4 w-4" />
            {primaryProfileAction.label}
          </Button>
        )}
      />

      {/* Профиль пользователя */}
      <DashboardSection
        title={t.dashboard.profile.userProfile}
        description={isRu ? 'Кто управляет аккаунтом и получает рабочие уведомления.' : 'Who manages the account and receives work notifications.'}
        actions={!editMode && currentBusiness && currentBusiness.owner_id === user?.id ? (
          <Button onClick={() => setEditMode(true)} variant="outline" className="gap-2">
            <Edit2 className="w-4 h-4" />
            {t.dashboard.profile.edit}
          </Button>
        ) : null}
      >
        <div className="mb-6 flex justify-end">
          {currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 text-gray-500 text-sm font-medium">
              <ShieldCheck className="w-4 h-4" />
              {t.dashboard.profile.notEditable}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Mail className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.email}
            </label>
            <input
              type="email"
              value={form.email}
              disabled
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl bg-gray-50/50 text-gray-500 font-medium"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <User className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.name}
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              disabled={!editMode || (currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id)}
              className={cn(
                "w-full px-4 py-2.5 border rounded-xl transition-all duration-200",
                editMode ? "border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 bg-white" : "border-gray-200 bg-gray-50/50"
              )}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Phone className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.phone}
            </label>
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              disabled={!editMode || (currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id)}
              className={cn(
                "w-full px-4 py-2.5 border rounded-xl transition-all duration-200",
                editMode ? "border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 bg-white" : "border-gray-200 bg-gray-50/50"
              )}
            />
          </div>
        </div>
        {editMode && (
          <div className="mt-8 flex justify-end gap-3 border-t border-slate-100 pt-6">
            <Button onClick={() => setEditMode(false)} variant="ghost">{t.dashboard.profile.cancel}</Button>
            <Button onClick={handleUpdateProfile} className="bg-blue-600 hover:bg-blue-700">{t.dashboard.profile.save}</Button>
          </div>
        )}
      </DashboardSection>

      {/* Предупреждение, если бизнес не выбран */}
      {!currentBusinessId && businesses && businesses.length > 1 && (
        <div className="bg-amber-50 rounded-2xl p-6 border border-amber-100 flex gap-4">
          <div className="p-3 bg-amber-100 rounded-full h-fit">
            <AlertTriangle className="h-6 w-6 text-amber-600" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-amber-900 mb-1">
              {t.dashboard.profile.noBusinessSelected}
            </h3>
            <p className="text-amber-800 mb-2">
              {t.dashboard.profile.selectBusinessToSave}
            </p>
            {businesses && businesses.length > 0 && (
              <p className="text-sm font-medium text-amber-700">
                {t.dashboard.profile.availableBusinesses} {businesses.length}. {t.dashboard.profile.chooseOne}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Информация о бизнесе */}
      <DashboardSection
        ref={businessInfoSectionRef}
        title={t.dashboard.profile.businessInfo}
        description={businessInfoHelperText}
        actions={
          <div className="flex flex-wrap gap-2">
            {user?.is_superadmin && currentBusinessId && !editClientInfo && (
              <Button
                variant="outline"
                onClick={async () => {
                  if (!currentBusinessId) return;
                  setSendingCredentials(true);
                  setError(null);
                  setSuccess(null);
                  try {
                    const data = await newAuth.makeRequest(`/superadmin/businesses/${currentBusinessId}/send-credentials`, {
                      method: 'POST'
                    });
                    setSuccess(data.message || 'Credentials sent');
                  } catch (err: any) {
                    setError(t.common.error + ': ' + err.message);
                  } finally {
                    setSendingCredentials(false);
                  }
                }}
                disabled={sendingCredentials}
                className="gap-2"
              >
                <Mail className="w-4 h-4" />
                {sendingCredentials ? t.dashboard.profile.sending : t.dashboard.profile.sendCredentials}
              </Button>
            )}
            {!editClientInfo && (
              <Button
                onClick={() => setEditClientInfo(true)}
                variant="outline"
                className="gap-2"
                title={isRu ? 'Открывает редактирование данных бизнеса, ссылки на карту и параметров для аудита.' : 'Opens business details, map link, and audit-related settings for editing.'}
              >
                <Edit2 className="w-4 h-4" />
                {t.dashboard.profile.edit}
              </Button>
            )}
          </div>
        }
      >
        {isNetwork && (
          <div className="mb-6 inline-flex items-center gap-1.5 rounded-full bg-orange-50 px-3 py-1.5 text-sm font-semibold text-orange-700 ring-1 ring-orange-100">
            <Network className="h-4 w-4" />
            {isRu ? 'Точка сети' : 'Network location'}
          </div>
        )}
        {hasUnsavedClientInfoChanges && (
          <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50/90 p-4 text-sm leading-6 text-amber-900">
            {isRu
              ? 'Следующий шаг: сначала сохраните изменения в информации о бизнесе. После этого запуск аудита и обновление данных будут использовать актуальную ссылку на карту.'
              : 'Next step: save the business information changes first. After that, audit start and data refresh will use the current map link.'}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Building2 className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.businessName}
              <FieldHint text={fieldHints.businessName} />
            </label>
            <input
              type="text"
              value={clientInfo.businessName}
              onChange={(e) => setClientInfo({ ...clientInfo, businessName: e.target.value })}
              disabled={!editClientInfo}
              className={cn(
                "w-full px-4 py-2.5 border rounded-xl transition-all duration-200",
                editClientInfo ? "border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 bg-white" : "border-gray-200 bg-gray-50/50"
              )}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Building2 className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.businessType}
              <FieldHint text={fieldHints.businessType} />
            </label>
            {editClientInfo ? (
              <Select
                value={clientInfo.businessType || "other"}
                onValueChange={(v) => setClientInfo({ ...clientInfo, businessType: v })}
              >
                <SelectTrigger className="h-11 rounded-xl">
                  <SelectValue placeholder={t.dashboard.profile.selectType} />
                </SelectTrigger>
                <SelectContent>
                  {businessTypeOptions.map((bt) => (
                    <SelectItem key={bt.type_key} value={bt.type_key}>
                      {bt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <input
                type="text"
                value={clientInfo.businessType ? getBusinessTypeLabel(clientInfo.businessType) : ''}
                disabled
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl bg-gray-50/50 text-gray-500"
                readOnly
                placeholder="-"
              />
            )}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.address}
              <FieldHint text={fieldHints.address} />
            </label>
            <input
              type="text"
              value={clientInfo.address}
              onChange={(e) => setClientInfo({ ...clientInfo, address: e.target.value })}
              disabled={!editClientInfo}
              className={cn(
                "w-full px-4 py-2.5 border rounded-xl transition-all duration-200",
                editClientInfo ? "border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 bg-white" : "border-gray-200 bg-gray-50/50"
              )}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.city}
              <FieldHint text={fieldHints.city} />
            </label>
            <div className="flex gap-2 items-center flex-wrap">
              <input
                type="text"
                value={clientInfo.city}
                onChange={(e) => setClientInfo({ ...clientInfo, city: e.target.value })}
                disabled={!editClientInfo}
                placeholder={!clientInfo.city && clientInfo.citySuggestion
                  ? (t.dashboard.profile.citySuggestionPlaceholder || 'Похоже на: {city}').replace('{city}', clientInfo.citySuggestion)
                  : undefined}
                className={cn(
                  "flex-1 min-w-[200px] px-4 py-2.5 border rounded-xl transition-all duration-200",
                  editClientInfo ? "border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 bg-white" : "border-gray-200 bg-gray-50/50"
                )}
              />
              {editClientInfo && !clientInfo.city && clientInfo.citySuggestion && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setClientInfo({ ...clientInfo, city: clientInfo.citySuggestion })}
                >
                  {t.dashboard.profile.applySuggestion}
                </Button>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.workingHours}
              <FieldHint text={fieldHints.workingHours} />
            </label>
            <div className={cn(
              "border rounded-xl p-3",
              editClientInfo ? "border-gray-300 bg-white" : "border-gray-200 bg-gray-50/50"
            )}>
              <input
                type="text"
                value={clientInfo.workingHours}
                onChange={(e) => setClientInfo({ ...clientInfo, workingHours: e.target.value })}
                disabled={!editClientInfo}
                className="w-full text-base font-medium text-gray-900 bg-transparent border-0 p-0 focus:outline-none placeholder:text-gray-400"
                placeholder={t.dashboard.profile.workingHoursPlaceholder}
              />
            </div>
            {editClientInfo && (
              <div className="flex flex-wrap gap-2 mt-2">
                {[
                  { label: t.dashboard.profile.workSchedule.weekdays, val: 'будни 9:00-21:00' },
                  { label: t.dashboard.profile.workSchedule.daily, val: 'ежедневно 9:00-21:00' },
                  { label: t.dashboard.profile.workSchedule.roundClock, val: 'круглосуточно' },
                  { label: t.dashboard.profile.workSchedule.weekends, val: 'выходные 10:00-20:00' },
                  { label: t.dashboard.profile.workSchedule.break, val: 'перерыв 13:00-14:00' }
                ].map(option => (
                  <button
                    key={option.label}
                    type="button"
                    onClick={() => setClientInfo({ ...clientInfo, workingHours: option.val })}
                    className="px-2.5 py-1 text-xs font-medium bg-gray-100/80 text-gray-600 rounded-lg hover:bg-blue-50 hover:text-blue-600 transition-colors"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <ExternalLink className="w-4 h-4 text-gray-400" />
              {isRu ? 'Сайт' : 'Website'}
              <FieldHint text={fieldHints.website} />
            </label>
            {editClientInfo ? (
              <input
                type="url"
                value={clientInfo.website || ''}
                onChange={(e) => setClientInfo({ ...clientInfo, website: e.target.value })}
                disabled={!editClientInfo}
                placeholder="https://example.com"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl bg-white transition-all duration-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              />
            ) : clientInfo.website ? (
              <a
                href={websiteHref}
                target="_blank"
                rel="noreferrer"
                className="flex min-h-[46px] items-center gap-2 rounded-xl border border-gray-200 bg-gray-50/50 px-4 py-2.5 text-blue-700 underline-offset-4 hover:underline"
              >
                <span className="truncate">{clientInfo.website}</span>
                <ExternalLink className="h-4 w-4 shrink-0" />
              </a>
            ) : (
              <input
                type="text"
                value=""
                disabled
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl bg-gray-50/50 text-gray-500"
                placeholder="-"
              />
            )}
          </div>
          <div className="col-span-1 md:col-span-2 space-y-2">
            <label className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-gray-400" />
              {t.dashboard.profile.mapLinks}
              <FieldHint text={fieldHints.mapLinks} />
            </label>
            {(clientInfo.mapLinks || []).map((link, index) => {
              const detectMapType = (url: string) => {
                if (!url) return 'other';
                if (url.includes('yandex.ru') || url.includes('yandex.com')) return 'yandex';
                if (url.includes('2gis.ru') || url.includes('2gis.com')) return '2gis';
                if (isGoogleMapUrl(url)) return 'google';
                if (url.includes('maps.apple.com')) return 'apple';
                return 'other';
              };

              const currentType = detectMapType(link.url);

              return (
                <div key={index} className="flex gap-2 items-center">
                  <div className="relative flex-1">
                    <input
                      type="text"
                      value={link.url}
                      onChange={(e) => {
                        const newUrl = e.target.value;
                        const newType = detectMapType(newUrl);
                        const newLinks = [...clientInfo.mapLinks];
                        newLinks[index] = { ...newLinks[index], url: newUrl, mapType: newType };
                        setClientInfo({ ...clientInfo, mapLinks: newLinks });
                      }}
                      disabled={!editClientInfo}
                      className={cn(
                        "w-full px-4 py-2.5 border rounded-xl transition-all duration-200 pr-24", // Right padding for badge
                        editClientInfo ? "border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 bg-white" : "border-gray-200 bg-gray-50/50"
                      )}
                      placeholder={isRu ? "Ссылка на карты (Яндекс, 2ГИС, Google)" : "Map link (Yandex, 2GIS, Google)"}
                    />
                    {link.url && (
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 px-2 py-1 rounded-md text-xs font-semibold bg-gray-100 text-gray-600 uppercase tracking-wider">
                        {currentType === 'other' ? 'WEB' : currentType}
                      </div>
                    )}
                  </div>

                  {editClientInfo && (
                    <Button
                      variant="ghost"
                      onClick={() => {
                        const newLinks = clientInfo.mapLinks.filter((_, i) => i !== index);
                        setClientInfo({ ...clientInfo, mapLinks: newLinks });
                      }}
                      className="text-red-500 hover:text-red-700 hover:bg-red-50 shrink-0"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              )
            })}
            {editClientInfo && (
              <Button
                variant="outline"
                onClick={() => setClientInfo({ ...clientInfo, mapLinks: [...clientInfo.mapLinks, { url: '', mapType: 'other' }] })}
                className="w-full mt-2"
              >
                <Plus className="w-4 h-4 mr-2" />
                {isRu ? 'Добавить ссылку' : 'Add link'}
              </Button>
            )}

            {hasMapLinks && (
              <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-sky-200 bg-sky-50/70 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-sky-950">
                    {isRu ? 'Ссылка на карту добавлена' : 'Map link added'}
                  </div>
                  <div className="mt-1 text-sm leading-6 text-sky-900/85">
                    {isRu
                      ? 'Сохраните изменения и перейдите в «Работа с картами», чтобы обновить данные карточки.'
                      : 'Save changes and go to Maps workspace to refresh listing data.'}
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate('/dashboard/card')}
                    className="border-sky-200 bg-white text-sky-900 hover:bg-sky-100"
                    title={isRu ? 'Открывает раздел работы с картами, услугами, отзывами и SEO.' : 'Opens maps management with services, reviews, and SEO.'}
                  >
                    <ArrowRight className="mr-2 h-4 w-4" />
                    {isRu ? 'К картам' : 'Maps'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>

        {editClientInfo && (
          <div className="mt-8 flex justify-end gap-3 border-t border-slate-100 pt-6">
            <Button
              onClick={() => setEditClientInfo(false)}
              variant="ghost"
              title={isRu ? 'Отменяет изменения в информации о бизнесе.' : 'Cancels changes in the business information form.'}
            >
              {t.dashboard.profile.cancel}
            </Button>
            <Button
              onClick={handleSaveClientInfo}
              className="bg-blue-600 hover:bg-blue-700"
              title={isRu ? 'Сохраняет данные бизнеса, чтобы их можно было использовать в картах, прогрессе и аудите.' : 'Saves business data so it can be used in maps management, progress, and the audit.'}
            >
              {t.dashboard.profile.save}
            </Button>
          </div>
        )}
      </DashboardSection>

      {/* Тарифы */}
      <div id="subscription" ref={subscriptionSectionRef} className="scroll-mt-24">
        <DashboardSection
          title="Подписка и доступ"
          description="Тариф, срок действия и доступные возможности для текущего бизнеса."
        >
          <SubscriptionManagement businessId={currentBusinessId} business={currentBusiness} />
        </DashboardSection>
      </div>

      {/* Счётчик кредитов */}
      <UserTokenUsageSummary
        businessId={currentBusinessId}
        subscriptionTier={currentBusiness?.subscription_tier}
        subscriptionEndsAt={currentBusiness?.subscription_ends_at}
        trialEndsAt={currentBusiness?.trial_ends_at}
      />
    </div>
  );
};
