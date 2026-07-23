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
  Mail,
  MapPinned,
  MessageCircle,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

import FinanceCrmPanel from '@/components/FinanceCrmPanel';
import TelegramConnection from '@/components/TelegramConnection';
import { TelegramBotCredentials } from '@/components/TelegramBotCredentials';
import { TelegramResearchSetup } from '@/components/TelegramResearchSetup';
import { OutreachEmailSetup } from '@/components/OutreachEmailSetup';
import { OutreachMaxSetup } from '@/components/OutreachMaxSetup';
import { OutreachVkSetup } from '@/components/OutreachVkSetup';
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
  OutreachSenderAccountSummary,
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
  senderScope?: 'business' | 'platform';
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
  outreachSenders: OutreachSenderAccountSummary[];
};

type GoogleLocation = {
  name: string;
  title?: string | null;
  address?: string | null;
  primary_category?: string | null;
};

type MetaAsset = {
  page_id: string;
  page_name: string;
  tasks?: string[];
  ig_user_id?: string | null;
  ig_username?: string | null;
  ig_name?: string | null;
  ig_profile_picture_url?: string | null;
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
  outreachSenders: [],
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
  outreach_email: 'Один mailbox используется для отправки одобренных писем и обязательной проверки ответов.',
  outreach_vk: 'VK-сообщество используется только для одобренных сообщений и проверки ответов по кампаниям LocalOS.',
  outreach_max: 'LocalOS готовит MAX-сообщения, а владелец аккаунта отправляет их и отмечает ответы вручную.',
  google_sheets: 'Агенты могут читать таблицы и готовить изменения. Запись выполняется только после вашего подтверждения.',
  google_business: 'Выберите карточку компании для отзывов, статистики и согласованных постов Google.',
  vk: 'Укажите ID и ключ сообщества. Текстовые публикации всё равно идут только после вашего подтверждения.',
  meta: 'Войдите через Meta, выберите Facebook Page и связанный Instagram Professional account.',
  yandex_maps: 'LocalOS готовит текст и задачу, финальный шаг в картах делает человек.',
  '2gis': 'LocalOS готовит материалы для карточки 2GIS, публикация остаётся ручной.',
  yclients: 'Подключите филиал YCLIENTS, затем проверьте preview импорта перед записью в финансы.',
  altegio: 'Подключите филиал Altegio, затем проверьте preview импорта перед записью в финансы.',
  maton: 'API-ключ хранится защищённо и используется как внешний маршрут для сервисов и агентов.',
};

const serviceHelp: Record<string, string[]> = {
  telegram: ['Привяжите бот LocalOS к Telegram владельца.', 'Укажите канал или чат для постов.', 'Проверьте отправку без внешней публикации.'],
  whatsapp: ['Добавьте номер бизнеса.', 'Заполните WABA Phone ID и access token.', 'Проверьте статус перед отправкой сообщений.'],
  outreach_email: ['Возьмите SMTP, IMAP и пароль приложения у почтового провайдера.', 'Проверьте подключение без отправки письма.', 'Отдельно разрешите отправку; проверка ответов включится вместе с ней.'],
  outreach_vk: ['Создайте в VK-сообществе ключ доступа с правом на сообщения.', 'LocalOS покажет фактическое имя отправителя и проверит доступ без отправки.', 'Отдельно разрешите отправку; проверка ответов включится вместе с ней.'],
  outreach_max: ['Укажите номер личного MAX-аккаунта.', 'LocalOS добавит MAX в доступные ручные каналы и подготовит текст.', 'После отправки отметьте касание или ответ в LocalOS.'],
  google_sheets: ['Нажмите подключение Google.', 'Выберите аккаунт, где есть нужная таблица.', 'Вернитесь к агенту и запустите безопасный тест.'],
  google_business: ['Подключите Google-доступ.', 'Загрузите список карточек.', 'Выберите карточку компании и синхронизируйте данные.'],
  vk: ['Укажите числовой ID сообщества.', 'Добавьте ключ сообщества с доступом к стене.', 'LocalOS проверит готовность текстовых публикаций.'],
  meta: ['Войдите через Meta.', 'Выберите Facebook Page.', 'Проверьте связанный Instagram Professional account.'],
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
  if (['whatsapp', 'outreach_email', 'outreach_vk', 'outreach_max', 'google_business', 'vk', 'meta', 'yandex_maps', '2gis'].includes(serviceId)) return 'publishing';
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
  if (id === 'outreach_email') return Mail;
  if (id === 'outreach_vk') return MessageCircle;
  if (id === 'outreach_max') return MessageCircle;
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

export const IntegrationsPageV3 = ({ currentBusinessId, currentBusiness, focus, returnTo, senderScope = 'business' }: IntegrationsPageV3Props) => {
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
  const [vkOwnerId, setVkOwnerId] = useState('');
  const [vkAccessToken, setVkAccessToken] = useState('');
  const [vkBusy, setVkBusy] = useState(false);
  const [metaAssets, setMetaAssets] = useState<MetaAsset[]>([]);
  const [selectedMetaPageId, setSelectedMetaPageId] = useState('');
  const [metaBusy, setMetaBusy] = useState(false);
  const [metaMessage, setMetaMessage] = useState<string | null>(null);
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
        const [ownerStatus, telegramStatus, readiness, accounts, crmProviders, outreachSenders] = await Promise.all([
          fetchJson(`/api/telegram/bind/status?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
          fetchJson(`/api/business/telegram-bot/status?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
          fetchJson(`/api/business/${encodeURIComponent(currentBusinessId)}/social-posts/channel-readiness`, { headers }),
          fetchJson(`/api/business/${encodeURIComponent(currentBusinessId)}/external-accounts`, { headers }),
          fetchJson(`/api/finance/crm/providers?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
          fetchJson(senderScope === 'platform'
            ? '/api/outreach/sender-accounts?scope_type=platform'
            : `/api/outreach/sender-accounts?scope_type=business&business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
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
          outreachSenders: outreachSenders.response.ok && outreachSenders.data.success ? firstArray(outreachSenders.data.sender_accounts) : [],
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
  }, [currentBusinessId, refreshKey, senderScope]);

  const services = useMemo(() => mapIntegrationsState({
    business: currentBusiness || null,
    telegramOwnerLinked: loadState.telegramOwnerLinked,
    telegramPublishStatus: loadState.telegramPublishStatus,
    socialReadiness: loadState.socialReadiness,
    externalAccounts: loadState.externalAccounts,
    crmProviders: loadState.crmProviders,
    outreachSenders: loadState.outreachSenders,
  }), [currentBusiness, loadState]);

  const selectedService = services.find((service) => service.id === activeServiceId) || null;
  const googleSheetsAccount = findAccount(loadState.externalAccounts, ['google_sheets']);
  const googleBusinessAccount = findAccount(loadState.externalAccounts, ['google_business']);
  const vkAccount = findAccount(loadState.externalAccounts, ['vk', 'vk_group', 'vk_business']);
  const metaAccount = findAccount(loadState.externalAccounts, ['meta', 'facebook', 'instagram']);
  const matonAccount = findAccount(loadState.externalAccounts, ['maton']);
  const facebookReadiness = loadState.socialReadiness.find((item) => item.platform === 'facebook') || null;
  const instagramReadiness = loadState.socialReadiness.find((item) => item.platform === 'instagram') || null;
  const selectedMetaAsset = metaAssets.find((item) => item.page_id === selectedMetaPageId) || null;

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

  useEffect(() => {
    if (vkOwnerId || !vkAccount?.external_id) return;
    setVkOwnerId(String(vkAccount.external_id).replace(/^-/, ''));
  }, [vkAccount?.external_id, vkOwnerId]);

  const handleGoogleConnect = async (purpose: 'google_sheets' | 'google_business') => {
    if (!currentBusinessId) return;
    setGoogleBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const oauthParams = new URLSearchParams({ business_id: currentBusinessId });
      const fallbackReturnTo = `/dashboard/settings/integrations?focus=${encodeURIComponent(purpose)}`;
      oauthParams.set('return_to', safeDashboardReturnTo(returnTo) || fallbackReturnTo);
      const oauthEndpoint = purpose === 'google_sheets'
        ? '/api/google/sheets/oauth/authorize'
        : '/api/google/oauth/authorize';
      const response = await fetch(`${oauthEndpoint}?${oauthParams.toString()}`, {
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
          account_id: googleBusinessAccount?.id,
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
        body: JSON.stringify({ account_id: googleBusinessAccount?.id }),
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

  const handleConnectVk = async () => {
    if (!currentBusinessId || !vkOwnerId.trim() || !vkAccessToken.trim()) return;
    setVkBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const groupId = vkOwnerId.trim().replace(/^-/, '');
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/external-accounts`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source: 'vk',
          external_id: groupId,
          display_name: `VK ${groupId}`,
          auth_data: {
            access_token: vkAccessToken.trim(),
            group_id: groupId,
            owner_id: `-${groupId}`,
            scope: ['wall'],
            token_type: 'community',
            auth_mode: 'community_token',
            api_version: '5.199',
          },
          is_active: true,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Не удалось сохранить подключение VK');
      setVkAccessToken('');
      toast({ title: 'Готово', description: 'Ключ сообщества сохранён. LocalOS проверяет право на публикацию.' });
      refresh();
    } catch (error) {
      toast({
        title: 'Не удалось подключить VK',
        description: error instanceof Error ? error.message : 'Проверьте ID и ключ сообщества.',
        variant: 'destructive',
      });
    } finally {
      setVkBusy(false);
    }
  };

  const handleMetaConnect = async () => {
    if (!currentBusinessId) return;
    setMetaBusy(true);
    setMetaMessage(null);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/meta/oauth/start`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          return_to: '/dashboard/settings/integrations?focus=meta',
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success || !data.auth_url) {
        throw new Error(data.error || 'Не удалось начать подключение Meta');
      }
      window.location.href = data.auth_url;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Не удалось начать подключение Meta';
      setMetaMessage(message);
      toast({ title: 'Не удалось подключить Facebook и Instagram', description: message, variant: 'destructive' });
      setMetaBusy(false);
    }
  };

  const handleLoadMetaAssets = async () => {
    if (!currentBusinessId) return;
    setMetaBusy(true);
    setMetaMessage(null);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/meta/assets`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Не удалось получить страницы Meta');
      const assets = firstArray(data.assets).filter((item): item is MetaAsset => Boolean(item && typeof item === 'object' && 'page_id' in item));
      setMetaAssets(assets);
      const selectedPageId = String(data.selected_page_id || '');
      setSelectedMetaPageId(selectedPageId || (assets.length === 1 ? assets[0].page_id : ''));
      setMetaMessage(assets.length ? `Найдено страниц: ${assets.length}` : 'У аккаунта не найдено доступных Facebook Pages.');
    } catch (error) {
      setMetaAssets([]);
      setMetaMessage(error instanceof Error ? error.message : 'Не удалось получить страницы Meta');
    } finally {
      setMetaBusy(false);
    }
  };

  const handleBindMetaAsset = async () => {
    if (!currentBusinessId || !selectedMetaPageId) return;
    setMetaBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/business/${encodeURIComponent(currentBusinessId)}/meta/bind`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ page_id: selectedMetaPageId }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Не удалось выбрать страницу Meta');
      setMetaMessage(data.message || 'Facebook и Instagram подключены.');
      toast({ title: 'Готово', description: data.message || 'Страница Meta подключена.' });
      refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Не удалось выбрать страницу Meta';
      setMetaMessage(message);
      toast({ title: 'Не удалось завершить подключение', description: message, variant: 'destructive' });
    } finally {
      setMetaBusy(false);
    }
  };

  const handleMetaDisconnect = async () => {
    if (!metaAccount?.id || !window.confirm('Отключить Facebook и Instagram от этого бизнеса? Запланированные публикации не будут отправлены.')) return;
    setMetaBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const response = await fetch(`/api/external-accounts/${encodeURIComponent(metaAccount.id)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Не удалось отключить Meta');
      setMetaAssets([]);
      setSelectedMetaPageId('');
      setMetaMessage('Facebook и Instagram отключены.');
      toast({ title: 'Meta отключена', description: 'Новые публикации не будут отправляться в Facebook и Instagram.' });
      refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Не удалось отключить Meta';
      toast({ title: 'Не удалось отключить Meta', description: message, variant: 'destructive' });
    } finally {
      setMetaBusy(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const metaAuth = params.get('meta_auth');
    if (!metaAuth) return;
    if (metaAuth === 'connected') {
      setActiveServiceId('meta');
      setMetaMessage('Аккаунт Meta подключён. Теперь выберите Facebook Page.');
      toast({ title: 'Доступ получен', description: 'Выберите страницу Facebook для публикаций.' });
      refresh();
    } else if (metaAuth === 'cancelled') {
      setMetaMessage('Подключение отменено. Можно начать ещё раз.');
    } else {
      setMetaMessage('Не удалось завершить подключение Meta. Попробуйте ещё раз.');
    }
    params.delete('meta_auth');
    params.delete('meta_pages');
    const queryString = params.toString();
    window.history.replaceState({}, '', `${window.location.pathname}${queryString ? `?${queryString}` : ''}${window.location.hash}`);
  }, [toast]);

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
      if (senderScope === 'platform') {
        const returnPath = safeDashboardReturnTo(returnTo) || '/dashboard/bazich';
        return (
          <>
            <TelegramResearchSetup businessId={currentBusinessId} mode="connection" scopeType="platform" />
            <Button type="button" variant="outline" asChild className="min-h-10 bg-white active:scale-[0.96] transition-transform">
              <a href={returnPath}>Вернуться к выбранному лиду</a>
            </Button>
          </>
        );
      }
      return (
        <>
          <TelegramConnection currentBusinessId={currentBusinessId} />
          <TelegramBotCredentials businessId={currentBusinessId || null} business={currentBusiness} onSaved={refresh} />
          <TelegramResearchSetup businessId={currentBusinessId} mode="connection" scopeType={senderScope} />
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

    if (service.id === 'outreach_email') {
      return (
        <OutreachEmailSetup
          businessId={senderScope === 'business' ? currentBusinessId : null}
          scopeType={senderScope}
          compact
          onChanged={refresh}
        />
      );
    }

    if (service.id === 'outreach_vk') {
      return (
        <OutreachVkSetup
          businessId={senderScope === 'business' ? currentBusinessId : null}
          scopeType={senderScope}
          compact
          onChanged={refresh}
        />
      );
    }

    if (service.id === 'outreach_max') {
      return (
        <OutreachMaxSetup
          businessId={senderScope === 'business' ? currentBusinessId : null}
          scopeType={senderScope}
          compact
          onChanged={refresh}
        />
      );
    }

    if (service.id === 'google_sheets') {
      return (
        <SetupPanel
          title="Google Таблицы"
          description="Можно читать и изменять таблицы. Перед записью LocalOS покажет изменения и попросит подтверждение."
        >
          <Button onClick={() => handleGoogleConnect('google_sheets')} disabled={googleBusy || !currentBusinessId} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800">
            {googleSheetsAccount ? 'Переподключить Google Таблицы' : 'Подключить Google Таблицы'}
          </Button>
          <p className="text-sm text-slate-600">Google попросит выбрать аккаунт с доступом к данным. Конкретную таблицу вы укажете отдельно в настройке каждого агента.</p>
          <p className="text-sm text-slate-600">Google Документы пока не подключаются.</p>
        </SetupPanel>
      );
    }

    if (service.id === 'google_business') {
      return (
        <SetupPanel
          title="Google Business"
          description="Ждём согласования Google. Это не мешает Google Таблицам."
        >
          {!googleBusinessAccount ? (
            <Button onClick={() => handleGoogleConnect('google_business')} disabled={googleBusy || !currentBusinessId} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800">
              Подключить Google Business
            </Button>
          ) : googleBusinessAccount.external_id ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-100">
                {googleBusinessAccount.display_name || 'Карточка Google выбрана'}
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
        <SetupPanel title="VK" description="Подключите сообщество, в котором LocalOS будет размещать подтверждённые текстовые публикации.">
          <div className="max-w-md space-y-2">
            <Label htmlFor="vk-community-id">ID сообщества</Label>
            <Input id="vk-community-id" inputMode="numeric" placeholder="Например, 182541984" value={vkOwnerId} onChange={(event) => setVkOwnerId(event.target.value)} disabled={vkBusy || !currentBusinessId} />
          </div>
          <div className="max-w-md space-y-2">
            <Label htmlFor="vk-community-token">Ключ доступа сообщества</Label>
            <Input id="vk-community-token" type="password" autoComplete="off" placeholder={vkAccount ? 'Введите новый ключ, чтобы обновить доступ' : 'Вставьте ключ с правом на стену'} value={vkAccessToken} onChange={(event) => setVkAccessToken(event.target.value)} disabled={vkBusy || !currentBusinessId} />
            <p className="text-sm leading-6 text-slate-600">Создайте ключ в VK: Управление сообществом → Работа с API → Ключи доступа. Нужен доступ к стене.</p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm leading-6 text-slate-600">{vkAccount ? `Сохранено сообщество: ${vkAccount.display_name || vkAccount.external_id || 'VK'}.` : 'Ключ хранится зашифрованно и после сохранения не показывается.'} Фото пока размещаются в контролируемом режиме.</p>
            <Button onClick={handleConnectVk} disabled={vkBusy || !currentBusinessId || !vkOwnerId.trim() || !vkAccessToken.trim()} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800">
              {vkBusy ? 'Проверяем…' : vkAccount ? 'Обновить ключ' : 'Сохранить подключение'}
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
        <SetupPanel title="Facebook и Instagram" description="Подключите аккаунт Meta один раз, затем выберите страницу этого бизнеса.">
          <div className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm leading-6 text-slate-600">
              {metaAccount
                ? `Доступ получен${metaAccount.display_name ? `: ${metaAccount.display_name}` : ''}.`
                : 'LocalOS запросит доступ только к страницам и профессиональным Instagram-аккаунтам, которыми вы управляете.'}
            </div>
            <Button type="button" onClick={handleMetaConnect} disabled={metaBusy || !currentBusinessId} className="min-h-10 bg-slate-900 text-white hover:bg-slate-800 sm:min-w-[190px]">
              {metaBusy ? 'Подождите…' : metaAccount ? 'Обновить доступ' : 'Подключить Meta'}
            </Button>
          </div>

          {metaAccount ? (
            <div className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="min-w-0 flex-1 space-y-2">
                  <Label htmlFor="meta-page-select">Страница Facebook</Label>
                  <Select value={selectedMetaPageId} onValueChange={setSelectedMetaPageId} disabled={metaBusy || metaAssets.length === 0}>
                    <SelectTrigger id="meta-page-select" className="min-h-11 bg-white">
                      <SelectValue placeholder="Выберите страницу" />
                    </SelectTrigger>
                    <SelectContent>
                      {metaAssets.map((asset) => (
                        <SelectItem key={asset.page_id} value={asset.page_id}>
                          {asset.page_name}{asset.ig_username ? ` · Instagram @${asset.ig_username}` : ' · без Instagram'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button type="button" variant="outline" onClick={handleLoadMetaAssets} disabled={metaBusy || !currentBusinessId} className="min-h-10 sm:min-w-[160px]">
                  <RefreshCw className={cn('mr-2 h-4 w-4', metaBusy ? 'animate-spin' : '')} />
                  Найти страницы
                </Button>
              </div>

              {selectedMetaAsset ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="flex items-start gap-3 rounded-2xl bg-slate-50 px-4 py-3 ring-1 ring-slate-200">
                    <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" />
                    <div>
                      <div className="font-semibold text-slate-950">Facebook Page</div>
                      <div className="mt-1 text-sm text-slate-600">{selectedMetaAsset.page_name}</div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 rounded-2xl bg-slate-50 px-4 py-3 ring-1 ring-slate-200">
                    {selectedMetaAsset.ig_user_id ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" /> : <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />}
                    <div>
                      <div className="font-semibold text-slate-950">Instagram</div>
                      <div className="mt-1 text-sm text-slate-600">
                        {selectedMetaAsset.ig_username
                          ? `@${selectedMetaAsset.ig_username}`
                          : 'Свяжите с этой Page профессиональный Instagram-аккаунт.'}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm leading-6 text-slate-600">
                  {metaMessage || 'Найдите доступные страницы и выберите нужную для этого бизнеса.'}
                </div>
                <Button type="button" onClick={handleBindMetaAsset} disabled={metaBusy || !selectedMetaPageId} className="min-h-10 bg-emerald-600 text-white hover:bg-emerald-700 sm:min-w-[190px]">
                  Сохранить страницу
                </Button>
              </div>
            </div>
          ) : metaMessage ? (
            <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900 ring-1 ring-amber-100">{metaMessage}</div>
          ) : null}

          <div className="grid gap-3 border-t border-slate-200 pt-5 sm:grid-cols-2">
            <SafetyRow
              allowed={Boolean(facebookReadiness?.ready)}
              title="Facebook"
              description={facebookReadiness?.ready ? 'Готов к подтверждённым публикациям.' : 'Нужно подключить и выбрать Facebook Page.'}
            />
            <SafetyRow
              allowed={Boolean(instagramReadiness?.ready)}
              title="Instagram"
              description={instagramReadiness?.ready ? 'Готов к публикациям с фото.' : 'Нужен профессиональный Instagram, связанный со страницей.'}
            />
          </div>

          <p className="text-sm leading-6 text-slate-600">
            LocalOS ничего не публикует во время подключения. Пост выйдет только после предпросмотра, вашего подтверждения и расписания.
          </p>
          {metaAccount ? (
            <div className="border-t border-slate-200 pt-4">
              <Button type="button" variant="ghost" onClick={handleMetaDisconnect} disabled={metaBusy} className="text-slate-600 hover:bg-red-50 hover:text-red-700">
                Отключить Facebook и Instagram
              </Button>
            </div>
          ) : null}
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
        {(service.id === 'telegram' && senderScope === 'platform' ? [
          'Создайте Telegram API application на my.telegram.org.',
          'Введите номер, ID и ключ приложения, затем подтвердите вход кодом и 2FA при необходимости.',
          'Отдельно разрешите радар и сообщения от имени LocalOS. Отправка всё равно потребует approval кампании.',
        ] : serviceHelp[service.id] || []).map((item, index) => (
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
    const senderAccounts = service.id === 'outreach_email'
      ? loadState.outreachSenders.filter((sender) => sender.channel === 'email')
      : service.id === 'outreach_vk'
        ? loadState.outreachSenders.filter((sender) => sender.channel === 'vk')
      : service.id === 'outreach_max'
        ? loadState.outreachSenders.filter((sender) => sender.channel === 'max')
      : service.id === 'telegram'
        ? loadState.outreachSenders.filter((sender) => sender.channel === 'telegram')
        : [];
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
          {senderAccounts.length ? (
            <div className="mt-4 space-y-2">
              {senderAccounts.map((sender) => (
                <div key={sender.id} className="rounded-2xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">
                  <div className="font-medium text-slate-950">{sender.sender_identity || 'Email sender'}</div>
                  <div className="text-xs text-slate-500">Статус: {sender.status || 'unknown'} · здоровье: {sender.health_status || 'unknown'}</div>
                  <div className="text-xs text-slate-500">Отправка: {sender.outreach_enabled ? 'разрешена' : 'запрещена'} · ответы: {sender.reply_sync_enabled ? 'проверяются' : 'не проверяются'}</div>
                  {sender.reply_sync_error ? <div className="text-xs text-rose-700">Ошибка ответов: {sender.reply_sync_error}</div> : null}
                </div>
              ))}
            </div>
          ) : accounts.length ? (
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
        title={selectedService?.id === 'telegram' && senderScope === 'platform'
          ? 'Telegram для продаж LocalOS'
          : selectedService?.name || 'Подключение'}
        description={selectedService?.id === 'telegram' && senderScope === 'platform'
          ? 'Подключите личный Telegram-аккаунт суперадмина. Он не будет доступен партнёрским кампаниям клиентских бизнесов.'
          : selectedService ? serviceDescriptions[selectedService.id] || selectedService.description : ''}
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
  if (serviceId === 'google_sheets') return accounts.filter((account) => account.source === 'google_sheets');
  if (serviceId === 'google_business') return accounts.filter((account) => account.source === 'google_business');
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
