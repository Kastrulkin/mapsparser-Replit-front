import { ReactNode, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  CircleDot,
  Database,
  Info,
  KeyRound,
  ListFilter,
  MapPinned,
  MessageCircle,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

import FinanceCrmPanel from '@/components/FinanceCrmPanel';
import { ExternalIntegrations } from '@/components/ExternalIntegrations';
import TelegramConnection from '@/components/TelegramConnection';
import { TelegramBotCredentials } from '@/components/TelegramBotCredentials';
import { TelegramResearchSetup } from '@/components/TelegramResearchSetup';
import WhatsAppConnection from '@/components/WhatsAppConnection';
import { WABACredentials } from '@/components/WABACredentials';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

import { SettingsDetailSheet } from './SettingsHubComponents';
import {
  ConnectionStatus,
  ConnectionType,
  ServiceConnection,
  mapIntegrationsState,
} from './integrationsRegistryState';
import {
  SettingsHubBusiness,
  SettingsHubCrmProvider,
  SettingsHubExternalAccount,
  SettingsHubSocialReadiness,
} from './settingsHubState';

type RegistryExternalAccount = SettingsHubExternalAccount & {
  id?: string;
  last_sync_at?: string | null;
  last_error?: string | null;
};

type IntegrationsPageV3Props = {
  currentBusinessId?: string | null;
  currentBusiness?: SettingsHubBusiness | null;
  focus?: string | null;
  returnTo?: string | null;
};

type RegistryLoadState = {
  telegramOwnerLinked?: boolean | null;
  telegramPublishStatus?: {
    configured?: boolean | null;
    global_bot_configured?: boolean | null;
    telegram_chat_id?: string | null;
  } | null;
  socialReadiness: SettingsHubSocialReadiness[];
  externalAccounts: RegistryExternalAccount[];
  crmProviders: SettingsHubCrmProvider[];
};

type GoogleLocation = {
  name: string;
  title?: string | null;
  address?: string | null;
  primary_category?: string | null;
};

type StatusFilter = ConnectionStatus | 'all' | 'needs_action';
type TypeFilter = ConnectionType | 'all' | 'crm';
type ServiceGroupKey = 'owner' | 'publishing' | 'data';

const emptyLoadState: RegistryLoadState = {
  telegramOwnerLinked: null,
  telegramPublishStatus: null,
  socialReadiness: [],
  externalAccounts: [],
  crmProviders: [],
};

const statusCopy: Record<ConnectionStatus, string> = {
  connected: 'Подключено',
  action_required: 'Требует действия',
  not_connected: 'Не подключено',
  manual: 'Ручной режим',
  error: 'Ошибка',
};

const typeCopy: Record<ConnectionType, string> = {
  oauth: 'OAuth',
  api_key: 'API-ключ',
  manual: 'Ручной',
  credentials: 'Доступы',
};

const serviceDescriptions: Record<string, string> = {
  telegram: 'Привяжите бот LocalOS для управления аккаунтом и отдельно выберите канал/чат, куда будут уходить согласованные посты.',
  whatsapp: 'Сохраните номер и WABA-доступ, когда канал готов к отправке сообщений клиентам.',
  google_sheets: 'Этот доступ нужен агентам для чтения Google Таблиц. Он не публикует ничего наружу.',
  google_business: 'Выберите карточку компании для отзывов, статистики и согласованных постов Google.',
  vk: 'Сохраните токен сообщества и ID группы. Публикации всё равно идут только после подтверждения.',
  meta: 'Подключение Facebook и Instagram остаётся контролируемым: выберите страницу и актив в деталях.',
  yandex_maps: 'LocalOS готовит текст и задачу, финальный шаг в картах делает человек.',
  '2gis': 'LocalOS готовит материалы для карточки 2GIS, публикация остаётся ручной.',
  yclients: 'Подключите филиал YCLIENTS, затем проверьте preview импорта перед записью в финансы.',
  altegio: 'Подключите филиал Altegio, затем проверьте preview импорта перед записью в финансы.',
  maton: 'API-ключ хранится защищённо и используется как внешний маршрут для сервисов и агентов.',
};

const serviceHelp: Record<string, string[]> = {
  telegram: ['Привяжите бот LocalOS к Telegram владельца.', 'Укажите канал или чат для постов.', 'Проверьте отправку без внешней публикации.'],
  whatsapp: ['Добавьте номер бизнеса.', 'Заполните WABA Phone ID и access token.', 'Проверьте статус перед отправкой сообщений.'],
  google_sheets: ['Нажмите подключение Google.', 'Выберите аккаунт, где есть нужная таблица.', 'Вернитесь к агенту и запустите безопасный тест.'],
  google_business: ['Подключите Google-доступ.', 'Загрузите список карточек.', 'Выберите карточку компании и синхронизируйте данные.'],
  vk: ['Создайте токен сообщества с правом публикации.', 'Укажите group_id или owner_id.', 'Сохраните и проверьте готовность канала.'],
  meta: ['Подключите страницу Facebook.', 'Выберите Instagram Business asset.', 'Проверьте права перед публикациями.'],
  yandex_maps: ['Подготовьте текст в LocalOS.', 'Откройте карточку Яндекс.', 'Опубликуйте вручную после проверки.'],
  '2gis': ['Подготовьте текст в LocalOS.', 'Откройте карточку 2GIS.', 'Опубликуйте вручную после проверки.'],
  yclients: ['Возьмите ID филиала.', 'Заполните partner token и user token.', 'Сначала проверьте preview, потом подтверждайте импорт.'],
  altegio: ['Возьмите ID филиала.', 'Заполните partner token и user token.', 'Сначала проверьте preview, потом подтверждайте импорт.'],
  maton: ['Скопируйте API-ключ Maton.ai.', 'Сохраните ключ в LocalOS.', 'Проверьте, что агент видит этот маршрут.'],
};

const serviceGroups: Array<{ key: ServiceGroupKey; title: string; description: string }> = [
  { key: 'owner', title: 'Связь с владельцем', description: 'Уведомления, команды и рабочие сообщения.' },
  { key: 'publishing', title: 'Публикации и сообщения', description: 'Каналы, где внешнее действие требует проверки и подтверждения.' },
  { key: 'data', title: 'Данные и CRM', description: 'Источники данных для агентов, финансов и отчётности.' },
];

const serviceGroup = (serviceId: string): ServiceGroupKey => {
  if (serviceId === 'telegram') return 'owner';
  if (['whatsapp', 'google_business', 'vk', 'meta', 'yandex_maps', '2gis'].includes(serviceId)) return 'publishing';
  return 'data';
};

const authHeaders = () => {
  const token = newAuth.getToken() || localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const fetchJson = async (url: string, options?: RequestInit) => {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  return { response, data };
};

const firstArray = (value: unknown) => Array.isArray(value) ? value : [];

const normalizeFocus = (focus?: string | null) => {
  if (!focus) return null;
  if (focus === 'google') return 'google_business';
  if (focus === 'crm') return 'crm';
  return focus;
};

const isActiveAccount = (account: RegistryExternalAccount) => {
  if (typeof account.is_active === 'number') return account.is_active !== 0;
  if (typeof account.is_active === 'boolean') return account.is_active;
  return true;
};

const findAccount = (accounts: RegistryExternalAccount[], sources: string[]) => (
  accounts.find((account) => account.source ? sources.includes(account.source) && isActiveAccount(account) : false) || null
);

const serviceIcon = (id: string) => {
  if (id === 'telegram') return Send;
  if (id === 'whatsapp') return MessageCircle;
  if (id === 'google_sheets') return Database;
  if (id === 'google_business') return Building2;
  if (id === 'vk') return MessageCircle;
  if (id === 'meta') return Send;
  if (id === 'yandex_maps') return MapPinned;
  if (id === '2gis') return MapPinned;
  if (id === 'yclients') return ShieldCheck;
  if (id === 'altegio') return ShieldCheck;
  return KeyRound;
};

const statusView = (status: ConnectionStatus) => {
  if (status === 'connected') return { icon: CheckCircle2, className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' };
  if (status === 'action_required') return { icon: AlertCircle, className: 'bg-amber-50 text-amber-700 ring-amber-200' };
  if (status === 'error') return { icon: XCircle, className: 'bg-rose-50 text-rose-700 ring-rose-200' };
  if (status === 'manual') return { icon: Info, className: 'bg-sky-50 text-sky-700 ring-sky-200' };
  return { icon: CircleDot, className: 'bg-slate-100 text-slate-600 ring-slate-200' };
};

const ServiceStatusBadge = ({ status }: { status: ConnectionStatus }) => {
  const view = statusView(status);
  const Icon = view.icon;
  return (
    <span className={cn('inline-flex min-h-8 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1', view.className)}>
      <Icon className="h-3.5 w-3.5" />
      {statusCopy[status]}
    </span>
  );
};

const safeDashboardReturnTo = (value?: string | null) => {
  const clean = String(value || '').trim();
  if (!clean || clean.startsWith('//') || !clean.startsWith('/dashboard/')) return '';
  return clean;
};

export const IntegrationsPageV3 = ({ currentBusinessId, currentBusiness, focus, returnTo }: IntegrationsPageV3Props) => {
  const { toast } = useToast();
  const [loadState, setLoadState] = useState<RegistryLoadState>(emptyLoadState);
  const [loading, setLoading] = useState(false);
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeServiceId, setActiveServiceId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');
  const [googleLocations, setGoogleLocations] = useState<GoogleLocation[]>([]);
  const [selectedGoogleLocation, setSelectedGoogleLocation] = useState('');
  const [googleBusy, setGoogleBusy] = useState(false);
  const [googleMessage, setGoogleMessage] = useState<string | null>(null);
  const [googleActionUrl, setGoogleActionUrl] = useState<string | null>(null);
  const [vkAccessToken, setVkAccessToken] = useState('');
  const [vkOwnerId, setVkOwnerId] = useState('');
  const [vkScope, setVkScope] = useState('wall');
  const [vkBusy, setVkBusy] = useState(false);
  const [matonApiKey, setMatonApiKey] = useState('');
  const [matonBusy, setMatonBusy] = useState(false);

  const normalizedFocus = useMemo(() => normalizeFocus(focus), [focus]);

  useEffect(() => {
    if (!normalizedFocus) return;
    if (normalizedFocus === 'crm') {
      setTypeFilter('crm');
      return;
    }
    setActiveServiceId(normalizedFocus);
  }, [normalizedFocus]);

  useEffect(() => {
    let cancelled = false;

    const loadRegistryState = async () => {
      if (!currentBusinessId) {
        setLoadState(emptyLoadState);
        return;
      }

      setLoading(true);
      setLoadError(null);
      const headers = authHeaders();
      try {
        const [ownerStatus, telegramStatus, readiness, accounts, crmProviders] = await Promise.all([
          fetchJson(`/api/telegram/bind/status?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
          fetchJson(`/api/business/telegram-bot/status?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
          fetchJson(`/api/business/${encodeURIComponent(currentBusinessId)}/social-posts/channel-readiness`, { headers }),
          fetchJson(`/api/business/${encodeURIComponent(currentBusinessId)}/external-accounts`, { headers }),
          fetchJson(`/api/finance/crm/providers?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
        ]);

        if (cancelled) return;

        setLoadState({
          telegramOwnerLinked: ownerStatus.response.ok ? Boolean(ownerStatus.data.is_linked) : false,
          telegramPublishStatus: telegramStatus.response.ok && telegramStatus.data.success ? {
            configured: Boolean(telegramStatus.data.configured),
            global_bot_configured: Boolean(telegramStatus.data.global_bot_configured),
            telegram_chat_id: telegramStatus.data.telegram_chat_id || null,
          } : null,
          socialReadiness: readiness.response.ok && readiness.data.success ? firstArray(readiness.data.channel_readiness) : [],
          externalAccounts: accounts.response.ok && accounts.data.success ? firstArray(accounts.data.accounts) : [],
          crmProviders: crmProviders.response.ok && crmProviders.data.success ? firstArray(crmProviders.data.providers) : [],
        });
        setLastCheckedAt(new Date());
      } catch {
        if (!cancelled) {
          setLoadState(emptyLoadState);
          setLoadError('Не удалось получить состояние подключений. Повторите проверку.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadRegistryState();
    return () => {
      cancelled = true;
    };
  }, [currentBusinessId, refreshKey]);

  const services = useMemo(() => mapIntegrationsState({
    business: currentBusiness || null,
    telegramOwnerLinked: loadState.telegramOwnerLinked,
    telegramPublishStatus: loadState.telegramPublishStatus,
    socialReadiness: loadState.socialReadiness,
    externalAccounts: loadState.externalAccounts,
    crmProviders: loadState.crmProviders,
  }), [currentBusiness, loadState]);

  const selectedService = services.find((service) => service.id === activeServiceId) || null;
  const googleAccount = findAccount(loadState.externalAccounts, ['google_business']);
  const vkAccount = findAccount(loadState.externalAccounts, ['vk', 'vk_group', 'vk_business']);
  const matonAccount = findAccount(loadState.externalAccounts, ['maton']);

  const filteredServices = services.filter((service) => {
    const matchesQuery = !query.trim()
      || service.name.toLowerCase().includes(query.trim().toLowerCase())
      || service.description.toLowerCase().includes(query.trim().toLowerCase())
      || String(service.tag || '').toLowerCase().includes(query.trim().toLowerCase());
    const matchesStatus = statusFilter === 'all'
      || (statusFilter === 'needs_action' ? ['action_required', 'not_connected', 'error'].includes(service.status) : service.status === statusFilter);
    const matchesType = typeFilter === 'all'
      || (typeFilter === 'crm' ? service.tag === 'CRM' : service.connectionType === typeFilter);
    return matchesQuery && matchesStatus && matchesType;
  });

  const refresh = () => setRefreshKey((value) => value + 1);

  const handleGoogleConnect = async () => {
    if (!currentBusinessId) return;
    setGoogleBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const oauthParams = new URLSearchParams({ business_id: currentBusinessId });
      const fallbackReturnTo = `/dashboard/settings/integrations?focus=${encodeURIComponent(activeServiceId || normalizedFocus || 'google_sheets')}`;
      oauthParams.set('return_to', safeDashboardReturnTo(returnTo) || fallbackReturnTo);
      const response = await fetch(`/api/google/oauth/authorize?${oauthParams.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok || !data.success || !data.auth_url) {
        throw new Error(data.error || 'Не удалось начать подключение Google');
      }
      window.location.href = data.auth_url;
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error instanceof Error ? error.message : 'Ошибка подключения Google',
        variant: 'destructive',
      });
      setGoogleBusy(false);
    }
  };

  const handleLoadGoogleLocations = async () => {
    if (!currentBusinessId) return;
    setGoogleBusy(true);
    setGoogleMessage(null);
    setGoogleActionUrl(null);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/google/locations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        setGoogleActionUrl(data.activation_url || null);
        throw new Error(data.error || 'Не удалось получить карточки Google');
      }
      const locations = firstArray(data.locations);
      setGoogleLocations(locations);
      if (locations.length === 1) setSelectedGoogleLocation(String(locations[0].name || ''));
      setGoogleMessage(locations.length ? `Найдено карточек: ${locations.length}` : 'Google подключён, но карточки не найдены.');
    } catch (error) {
      setGoogleLocations([]);
      setGoogleMessage(error instanceof Error ? error.message : 'Не удалось получить карточки Google');
    } finally {
      setGoogleBusy(false);
    }
  };

  const handleBindGoogleLocation = async () => {
    if (!currentBusinessId || !selectedGoogleLocation) return;
    const location = googleLocations.find((item) => item.name === selectedGoogleLocation);
    setGoogleBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/google/bind-location`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          account_id: googleAccount?.id,
          location_name: selectedGoogleLocation,
          display_name: location?.title || 'Google Business Profile',
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось выбрать карточку Google');
      }
      toast({ title: 'Готово', description: 'Карточка Google выбрана' });
      refresh();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error instanceof Error ? error.message : 'Ошибка выбора карточки Google',
        variant: 'destructive',
      });
    } finally {
      setGoogleBusy(false);
    }
  };

  const handleSyncGoogle = async () => {
    if (!currentBusinessId) return;
    setGoogleBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/google/sync`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ account_id: googleAccount?.id }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось синхронизировать Google');
      }
      toast({ title: 'Готово', description: 'Google синхронизирован' });
      refresh();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error instanceof Error ? error.message : 'Ошибка синхронизации Google',
        variant: 'destructive',
      });
    } finally {
      setGoogleBusy(false);
    }
  };

  const handleSaveVk = async () => {
    if (!currentBusinessId || !vkAccessToken.trim() || !vkOwnerId.trim()) return;
    setVkBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/external-accounts`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source: 'vk',
          external_id: vkOwnerId.trim(),
          display_name: 'VK публикации',
          auth_data: {
            access_token: vkAccessToken.trim(),
            owner_id: vkOwnerId.trim(),
            group_id: vkOwnerId.trim().replace(/^-/, ''),
            scope: vkScope.trim() || 'wall',
          },
          is_active: true,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось сохранить VK');
      }
      setVkAccessToken('');
      toast({ title: 'Готово', description: 'VK подключён' });
      refresh();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error instanceof Error ? error.message : 'Ошибка сохранения VK',
        variant: 'destructive',
      });
    } finally {
      setVkBusy(false);
    }
  };

  const handleSaveMaton = async () => {
    if (!currentBusinessId || !matonApiKey.trim()) return;
    setMatonBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/external-accounts`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source: 'maton',
          external_id: 'maton',
          display_name: 'Maton.ai',
          auth_data: { api_key: matonApiKey.trim() },
          is_active: true,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось сохранить Maton.ai');
      }
      setMatonApiKey('');
      toast({ title: 'Готово', description: 'Ключ Maton.ai сохранён' });
      refresh();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error instanceof Error ? error.message : 'Ошибка сохранения Maton.ai',
        variant: 'destructive',
      });
    } finally {
      setMatonBusy(false);
    }
  };

  const renderSetup = (service: ServiceConnection) => {
    if (service.id === 'telegram') {
      return (
        <>
          <TelegramConnection currentBusinessId={currentBusinessId} />
          <TelegramBotCredentials businessId={currentBusinessId || null} business={currentBusiness} onSaved={refresh} />
          <TelegramResearchSetup businessId={currentBusinessId} mode="connection" />
        </>
      );
    }

    if (service.id === 'whatsapp') {
      return (
        <>
          <WhatsAppConnection currentBusinessId={currentBusinessId} business={currentBusiness} />
          <WABACredentials businessId={currentBusinessId || null} business={currentBusiness} />
        </>
      );
    }

    if (service.id === 'google_sheets') {
      return (
        <SetupPanel
          title="Google Таблицы"
          description="Один Google-доступ нужен агентам для чтения строк таблиц. Он не публикует ничего наружу."
        >
          <Button onClick={handleGoogleConnect} disabled={googleBusy || !currentBusinessId} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800">
            {googleAccount ? 'Переподключить Google-доступ' : 'Подключить Google-доступ'}
          </Button>
        </SetupPanel>
      );
    }

    if (service.id === 'google_business') {
      return (
        <SetupPanel
          title="Google Business"
          description="Сначала нужен Google-доступ, затем выбор карточки компании."
        >
          {!googleAccount ? (
            <Button onClick={handleGoogleConnect} disabled={googleBusy || !currentBusinessId} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800">
              Подключить Google
            </Button>
          ) : googleAccount.external_id ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-100">
                {googleAccount.display_name || 'Карточка Google выбрана'}
              </div>
              <Button variant="outline" onClick={handleSyncGoogle} disabled={googleBusy}>
                Синхронизировать
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={handleLoadGoogleLocations} disabled={googleBusy}>
                  Найти карточки
                </Button>
                <Button onClick={handleBindGoogleLocation} disabled={googleBusy || !selectedGoogleLocation}>
                  Выбрать карточку
                </Button>
              </div>
              <div className="space-y-2">
                <Label htmlFor="google-location">Карточка компании</Label>
                <select
                  id="google-location"
                  value={selectedGoogleLocation}
                  onChange={(event) => setSelectedGoogleLocation(event.target.value)}
                  disabled={googleBusy || googleLocations.length === 0}
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"
                >
                  <option value="">Выберите карточку</option>
                  {googleLocations.map((location) => (
                    <option key={location.name} value={location.name}>
                      {[location.title, location.address || location.primary_category].filter(Boolean).join(' - ')}
                    </option>
                  ))}
                </select>
              </div>
              {googleMessage ? (
                <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900 ring-1 ring-amber-100">
                  {googleMessage}
                  {googleActionUrl ? (
                    <a href={googleActionUrl} target="_blank" rel="noreferrer" className="ml-2 font-semibold underline underline-offset-4">
                      Открыть Google Cloud
                    </a>
                  ) : null}
                </div>
              ) : null}
            </div>
          )}
        </SetupPanel>
      );
    }

    if (service.id === 'vk') {
      return (
        <SetupPanel title="VK" description="Сохраните пользовательский OAuth-токен администратора сообщества с правом wall. Ключ сообщества из раздела «Работа с API» не поддерживает wall.post.">
          <div className="grid gap-3 lg:grid-cols-[1fr_220px_160px]">
            <Input type="password" placeholder="VK user OAuth access_token" value={vkAccessToken} onChange={(event) => setVkAccessToken(event.target.value)} disabled={vkBusy || !currentBusinessId} />
            <Input placeholder="group_id или owner_id" value={vkOwnerId} onChange={(event) => setVkOwnerId(event.target.value)} disabled={vkBusy || !currentBusinessId} />
            <Input placeholder="scope" value={vkScope} onChange={(event) => setVkScope(event.target.value)} disabled={vkBusy || !currentBusinessId} />
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm leading-6 text-slate-600">{vkAccount ? `Сейчас подключено: ${vkAccount.display_name || vkAccount.external_id || 'VK'}.` : 'Токен после сохранения не показывается.'}</p>
            <Button onClick={handleSaveVk} disabled={vkBusy || !currentBusinessId || !vkAccessToken.trim() || !vkOwnerId.trim()} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800">
              Сохранить VK
            </Button>
          </div>
        </SetupPanel>
      );
    }

    if (service.id === 'maton') {
      return (
        <SetupPanel title="Maton.ai" description="Сохраните API-ключ для внешних сервисов.">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input type="password" placeholder="API-ключ Maton.ai" value={matonApiKey} onChange={(event) => setMatonApiKey(event.target.value)} disabled={matonBusy || !currentBusinessId} />
            <Button onClick={handleSaveMaton} disabled={matonBusy || !currentBusinessId || !matonApiKey.trim()} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800 sm:min-w-[180px]">
              Сохранить ключ
            </Button>
          </div>
          <p className="text-sm leading-6 text-slate-600">{matonAccount ? 'Ключ уже сохранён. Новый ключ заменит старый.' : 'После сохранения ключ не отображается.'}</p>
        </SetupPanel>
      );
    }

    if (service.id === 'yclients' || service.id === 'altegio') {
      return <FinanceCrmPanel currentBusinessId={currentBusinessId} surface="embedded" providerFilter={[service.id]} onSynced={refresh} />;
    }

    if (service.id === 'meta') {
      return (
        <SetupPanel title="Meta" description="Facebook и Instagram остаются в контролируемом режиме, пока не выбран рабочий актив.">
          <ExternalIntegrations currentBusinessId={currentBusinessId || null} focusedPlatform="meta" readinessRefreshKey={refreshKey} />
        </SetupPanel>
      );
    }

    return (
      <SetupPanel title={service.name} description="Этот сервис работает через ручной финальный шаг.">
        <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">
          LocalOS подготовит текст и задачу. Внешняя публикация не запускается без человека.
        </div>
      </SetupPanel>
    );
  };

  const renderHelp = (service: ServiceConnection) => (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-950">Как подключить</h3>
      <ol className="mt-4 space-y-3">
        {(serviceHelp[service.id] || []).map((item, index) => (
          <li key={item} className="flex gap-3 text-sm leading-6 text-slate-700">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white tabular-nums">
              {index + 1}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
    </div>
  );

  const renderCheck = (service: ServiceConnection) => {
    const readiness = readinessForService(service.id, loadState.socialReadiness);
    return (
      <div className="space-y-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-balance text-base font-semibold text-slate-950">Состояние подключения</h3>
            <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
              LocalOS повторно читает сохранённое состояние и доступную готовность канала. Публикация, отправка сообщения или запись данных при этой проверке не выполняются.
            </p>
          </div>
          <ServiceStatusBadge status={loadError ? 'error' : service.status} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <LogRow label="Результат" value={loadError || service.nextAction} wide />
          <LogRow label="Проверено" value={lastCheckedAt ? lastCheckedAt.toLocaleString('ru-RU') : 'Проверка ещё не выполнялась'} />
          <LogRow
            label="Проверка провайдера"
            value={readiness ? String(readiness.status || (readiness.ready ? 'Готово' : 'Требует действия')) : 'Отдельная тестовая операция недоступна'}
          />
        </div>
        <Button type="button" variant="outline" onClick={refresh} disabled={loading} className="min-h-10 gap-2 active:scale-[0.96] transition-transform">
          <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
          {loading ? 'Проверяем…' : 'Проверить состояние'}
        </Button>
      </div>
    );
  };

  const renderSafety = (service: ServiceConnection) => {
    const readOnly = service.id === 'google_sheets';
    const manual = service.status === 'manual' || ['yandex_maps', '2gis'].includes(service.id);
    const crm = ['yclients', 'altegio'].includes(service.id);
    return (
      <div className="space-y-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h3 className="text-balance text-base font-semibold text-slate-950">Безопасные действия</h3>
          <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">Здесь показаны действующие границы. Числовые лимиты в этой версии не настраиваются.</p>
        </div>
        <div className="space-y-3 text-sm leading-6">
          <SafetyRow allowed title="Подключение и проверка" description="Можно менять доступы и читать состояние без внешней отправки." />
          {readOnly ? <SafetyRow allowed title="Чтение данных" description="Доступ используется для чтения таблиц; наружу ничего не публикуется." /> : null}
          {manual ? <SafetyRow title="Внешнее изменение" description="LocalOS готовит материал, а финальное действие выполняет человек в сервисе." /> : null}
          {crm ? <SafetyRow title="Импорт в финансы" description="Сначала показывается предварительный просмотр; применение требует подтверждения." /> : null}
          {!readOnly && !manual && !crm ? <SafetyRow title="Публикация или отправка" description="Перед внешним действием обязательны предпросмотр и подтверждение человека." /> : null}
        </div>
      </div>
    );
  };

  const renderLogs = (service: ServiceConnection) => {
    const accounts = accountsForService(service.id, loadState.externalAccounts);
    const readiness = readinessForService(service.id, loadState.socialReadiness);
    return (
      <div className="space-y-4">
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-balance text-base font-semibold text-slate-950">Сведения для поддержки</h3>
          <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">Техническое состояние без токенов, ключей и других секретов.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <LogRow label="Статус" value={statusCopy[service.status]} />
            <LogRow label="Тип подключения" value={typeCopy[service.connectionType]} />
            <LogRow label="Следующий шаг" value={service.nextAction} wide />
            {readiness ? <LogRow label="Проверка канала" value={String(readiness.status || (readiness.ready ? 'ready' : 'needs_action'))} /> : null}
          </div>
        </div>
        <details className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <summary className="min-h-10 cursor-pointer select-none text-base font-semibold leading-10 text-slate-950">Сохранённые записи подключения</summary>
          {accounts.length ? (
            <div className="mt-4 space-y-2">
              {accounts.map((account) => (
                <div key={`${account.source || 'account'}-${account.external_id || account.display_name || 'item'}`} className="rounded-2xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">
                  <div className="font-medium text-slate-950">{account.display_name || account.source || service.name}</div>
                  {account.external_id ? <div className="break-all text-xs text-slate-500">ID: {account.external_id}</div> : null}
                  {account.last_error ? <div className="text-xs text-rose-700">Ошибка: {account.last_error}</div> : null}
                  {account.last_sync_at ? <div className="text-xs text-slate-500">Синхронизация: {new Date(account.last_sync_at).toLocaleString('ru-RU')}</div> : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-600">Для этого сервиса пока нет сохранённой записи подключения.</p>
          )}
        </details>
      </div>
    );
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-10" data-settings-integrations-version="v3">
      <DashboardPageHeader
        eyebrow="Настройки"
        title="Подключения"
        description="Подключите сервис, проверьте его состояние и посмотрите границы безопасных действий."
        icon={ListFilter}
      />

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 lg:grid-cols-[1fr_220px_220px_auto] lg:items-center">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Найти сервис"
              className="min-h-10 pl-9"
            />
          </div>
          <Select value={statusFilter} onValueChange={(value) => setStatusFilter(toStatusFilter(value))}>
            <SelectTrigger className="min-h-10">
              <SelectValue placeholder="Статус" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все</SelectItem>
              <SelectItem value="needs_action">Нужно настроить</SelectItem>
              <SelectItem value="connected">Подключены</SelectItem>
              <SelectItem value="error">Ошибки</SelectItem>
              <SelectItem value="manual">Ручной режим</SelectItem>
              <SelectItem value="not_connected">Не подключены</SelectItem>
            </SelectContent>
          </Select>
          <Select value={typeFilter} onValueChange={(value) => setTypeFilter(toTypeFilter(value))}>
            <SelectTrigger className="min-h-10">
              <SelectValue placeholder="Тип" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все типы</SelectItem>
              <SelectItem value="oauth">OAuth</SelectItem>
              <SelectItem value="api_key">API-ключ</SelectItem>
              <SelectItem value="credentials">Доступы</SelectItem>
              <SelectItem value="manual">Ручной</SelectItem>
              <SelectItem value="crm">CRM</SelectItem>
            </SelectContent>
          </Select>
          <Button type="button" variant="outline" onClick={refresh} disabled={loading} className="min-h-10 gap-2">
            <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
            Обновить
          </Button>
        </div>
      </section>

      <div className="space-y-5">
        {serviceGroups.map((group) => {
          const groupServices = filteredServices.filter((service) => serviceGroup(service.id) === group.key);
          if (!groupServices.length) return null;
          return (
            <section key={group.key} className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 bg-slate-50/80 px-5 py-4">
                <h2 className="text-balance text-base font-semibold text-slate-950">{group.title}</h2>
                <p className="mt-1 text-pretty text-sm text-slate-600">{group.description}</p>
              </div>
              <div className="divide-y divide-slate-100">
                {groupServices.map((service) => (
                  <ServiceRow key={service.id} service={service} active={service.id === activeServiceId} onOpen={setActiveServiceId} />
                ))}
              </div>
            </section>
          );
        })}
        {!filteredServices.length ? (
          <div className="rounded-3xl border border-slate-200 bg-white px-5 py-8 text-sm text-slate-600 shadow-sm">Ничего не найдено. Сбросьте поиск или фильтр.</div>
        ) : null}
      </div>

      <SettingsDetailSheet
        open={Boolean(selectedService)}
        title={selectedService?.name || 'Подключение'}
        description={selectedService ? serviceDescriptions[selectedService.id] || selectedService.description : ''}
        onOpenChange={(open) => {
          if (!open) setActiveServiceId(null);
        }}
      >
        {selectedService ? (
          <Tabs defaultValue="setup" className="space-y-4">
            <TabsList className="grid h-auto w-full grid-cols-2 rounded-2xl bg-slate-200/70 p-1 sm:grid-cols-4">
              <TabsTrigger value="setup" className="min-h-10 rounded-xl">Настройка</TabsTrigger>
              <TabsTrigger value="check" className="min-h-10 rounded-xl">Проверка</TabsTrigger>
              <TabsTrigger value="safety" className="min-h-10 rounded-xl">Безопасность</TabsTrigger>
              <TabsTrigger value="support" className="min-h-10 rounded-xl">Для поддержки</TabsTrigger>
            </TabsList>
            <TabsContent value="setup" className="space-y-4">
              {renderSetup(selectedService)}
              {renderHelp(selectedService)}
            </TabsContent>
            <TabsContent value="check">{renderCheck(selectedService)}</TabsContent>
            <TabsContent value="safety">{renderSafety(selectedService)}</TabsContent>
            <TabsContent value="support">
              {renderLogs(selectedService)}
            </TabsContent>
          </Tabs>
        ) : null}
      </SettingsDetailSheet>
    </div>
  );
};

const ServiceRow = ({
  service,
  active,
  onOpen,
}: {
  service: ServiceConnection;
  active: boolean;
  onOpen: (id: string) => void;
}) => {
  const Icon = serviceIcon(service.id);
  return (
    <article
      className={cn(
        'grid gap-4 px-4 py-4 transition-[background-color,box-shadow] duration-150 ease-out md:grid-cols-[minmax(0,1fr)_150px_170px_170px] md:items-center',
        active ? 'bg-sky-50 shadow-[inset_3px_0_0_rgb(2,132,199)]' : 'bg-white hover:bg-slate-50',
      )}
    >
      <button type="button" onClick={() => onOpen(service.id)} className="grid min-w-0 grid-cols-[44px_minmax(0,1fr)] gap-3 text-left">
        <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-700 ring-1 ring-slate-200">
          <Icon className="h-5 w-5" />
        </span>
        <span className="min-w-0">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-slate-950">{service.name}</span>
            {service.tag ? (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
                {service.tag}
              </span>
            ) : null}
          </span>
          <span className="mt-1 block truncate text-sm text-slate-600">{service.description}</span>
        </span>
      </button>
      <div className="text-sm text-slate-600">{typeCopy[service.connectionType]}</div>
      <ServiceStatusBadge status={service.status} />
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center md:flex-col md:items-stretch">
        <div className="truncate text-sm text-slate-600">{service.nextAction}</div>
        <Button type="button" onClick={() => onOpen(service.id)} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800">
          {service.primaryAction.label}
        </Button>
      </div>
    </article>
  );
};

const SetupPanel = ({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) => (
  <div className="space-y-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
    <div>
      <h3 className="text-base font-semibold text-slate-950">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
    </div>
    {children}
  </div>
);

const SafetyRow = ({
  allowed = false,
  title,
  description,
}: {
  allowed?: boolean;
  title: string;
  description: string;
}) => (
  <div className={cn('grid grid-cols-[40px_minmax(0,1fr)] gap-3 rounded-2xl px-4 py-3 ring-1', allowed ? 'bg-emerald-50 ring-emerald-100' : 'bg-amber-50 ring-amber-100')}>
    <span className={cn('flex h-10 w-10 items-center justify-center rounded-xl', allowed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>
      {allowed ? <CheckCircle2 className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
    </span>
    <span>
      <span className="block font-semibold text-slate-950">{title}</span>
      <span className="block text-slate-700">{description}</span>
    </span>
  </div>
);

const accountsForService = (serviceId: string, accounts: RegistryExternalAccount[]) => {
  if (serviceId === 'google_sheets' || serviceId === 'google_business') return accounts.filter((account) => account.source === 'google_business');
  if (serviceId === 'vk') return accounts.filter((account) => ['vk', 'vk_group', 'vk_business'].includes(String(account.source || '')));
  if (serviceId === 'meta') return accounts.filter((account) => ['meta', 'instagram', 'facebook'].includes(String(account.source || '')));
  if (serviceId === 'maton') return accounts.filter((account) => account.source === 'maton');
  if (serviceId === 'yandex_maps') return accounts.filter((account) => ['yandex_business', 'yandex_maps'].includes(String(account.source || '')));
  if (serviceId === '2gis') return accounts.filter((account) => ['2gis', 'dgis'].includes(String(account.source || '')));
  return [];
};

const readinessForService = (serviceId: string, readiness: SettingsHubSocialReadiness[]) => {
  const platforms = serviceId === 'google_business'
    ? ['google_business']
    : serviceId === 'meta'
      ? ['meta', 'instagram', 'facebook']
      : serviceId === 'yandex_maps'
        ? ['yandex_maps', 'yandex_business', 'yandex']
        : serviceId === '2gis'
          ? ['2gis', 'dgis']
          : [serviceId];
  return readiness.find((item) => item.platform ? platforms.includes(item.platform) : false) || null;
};

const toStatusFilter = (value: string): StatusFilter => {
  if (value === 'needs_action') return 'needs_action';
  if (value === 'connected') return 'connected';
  if (value === 'action_required') return 'action_required';
  if (value === 'not_connected') return 'not_connected';
  if (value === 'manual') return 'manual';
  if (value === 'error') return 'error';
  return 'all';
};

const toTypeFilter = (value: string): TypeFilter => {
  if (value === 'oauth') return 'oauth';
  if (value === 'api_key') return 'api_key';
  if (value === 'manual') return 'manual';
  if (value === 'credentials') return 'credentials';
  if (value === 'crm') return 'crm';
  return 'all';
};

const LogRow = ({ label, value, wide }: { label: string; value: string; wide?: boolean }) => (
  <div className={cn('rounded-2xl bg-slate-50 px-4 py-3 ring-1 ring-slate-200', wide ? 'sm:col-span-2' : '')}>
    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</div>
    <div className="mt-1 text-sm leading-6 text-slate-800">{value}</div>
  </div>
);

export default IntegrationsPageV3;
