import React, { Suspense, lazy, useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { ChevronDown, ChevronRight, Building2, Network, MapPin, User, Plus, Trash2, Ban, AlertTriangle, Bot, Gift, Settings, BarChart3, TrendingUp, FileText, X, Search } from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { useToast } from '../../hooks/use-toast';
import { CreateBusinessModal } from '../../components/CreateBusinessModal';
import { AdminExternalCabinetSettings } from '../../components/AdminExternalCabinetSettings';
import { ProspectingManagement } from '../../components/ProspectingManagement';
import {
  DashboardCompactMetricsRow,
  DashboardEmptyState,
  DashboardPageHeader,
  DashboardSection,
} from '../../components/dashboard/DashboardPrimitives';

const AIAgentsManagement = lazy(() =>
  import('../../components/AIAgentsManagement').then((module) => ({ default: module.AIAgentsManagement })),
);
const TokenUsageStats = lazy(() =>
  import('../../components/TokenUsageStats').then((module) => ({ default: module.TokenUsageStats })),
);
const GrowthPlanEditor = lazy(() =>
  import('../../components/GrowthPlanEditor').then((module) => ({ default: module.GrowthPlanEditor })),
);
const PromptsManagement = lazy(() =>
  import('../../components/PromptsManagement').then((module) => ({ default: module.PromptsManagement })),
);
const ProxyManagement = lazy(() =>
  import('../../components/ProxyManagement').then((module) => ({ default: module.ProxyManagement })),
);
const ParsingManagement = lazy(() =>
  import('../../components/ParsingManagement').then((module) => ({ default: module.ParsingManagement })),
);

type AdminTabId = 'businesses' | 'agents' | 'tokens' | 'growth' | 'prompts' | 'proxies' | 'parsing' | 'prospecting';
interface Business {
  id: string;
  name: string;
  description?: string;
  address?: string;
  industry?: string;
  created_at?: string;
  is_active?: number;
  subscription_tier?: string;
  moderation_status?: string;
  is_lead_business?: boolean;
  entity_group?: 'lead' | 'company';
}

interface Network {
  id: string;
  name: string;
  description?: string;
  businesses: Business[];
  created_at?: string;
}

interface UserWithBusinesses {
  id: string;
  email: string;
  name?: string;
  phone?: string;
  is_superadmin?: boolean;
  is_active?: number;
  direct_businesses: Business[];
  networks: Network[];
}

interface BusinessListItem {
  id: string;
  name: string;
  type: 'direct' | 'network';
  networkId?: string;
  networkName?: string;
  business: Business;
}

type AdminTabConfig = {
  id: AdminTabId;
  label: string;
  icon: typeof User;
};

const adminTabs: AdminTabConfig[] = [
  { id: 'businesses', label: 'Пользователи и бизнесы', icon: User },
  { id: 'agents', label: 'ИИ агенты', icon: Bot },
  { id: 'prospecting', label: 'Поиск клиентов', icon: Search },
  { id: 'tokens', label: 'Статистика кредитов', icon: BarChart3 },
  { id: 'growth', label: 'Схема роста', icon: TrendingUp },
  { id: 'prompts', label: 'Промпты анализа', icon: FileText },
  { id: 'proxies', label: 'Прокси', icon: Network },
  { id: 'parsing', label: 'Парсинг', icon: MapPin },
];

const primaryAdminTabs: AdminTabConfig[] = [
  { id: 'businesses', label: 'Пользователи', icon: User },
  { id: 'agents', label: 'ИИ агенты', icon: Bot },
  { id: 'prospecting', label: 'Поиск клиентов', icon: Search },
];

const toolsAdminTabs: AdminTabConfig[] = [
  { id: 'parsing', label: 'Парсинг', icon: MapPin },
  { id: 'proxies', label: 'Прокси', icon: Network },
  { id: 'prompts', label: 'Промпты анализа', icon: FileText },
  { id: 'tokens', label: 'Статистика кредитов', icon: BarChart3 },
  { id: 'growth', label: 'Схема роста', icon: TrendingUp },
];

const LEAD_OUTREACH_STATUS = 'lead_outreach';

const getErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
};

const isLeadBusiness = (business?: Business | null) =>
  business?.is_lead_business === true ||
  String(business?.entity_group || '').trim().toLowerCase() === 'lead' ||
  String(business?.moderation_status || '').trim().toLowerCase() === LEAD_OUTREACH_STATUS;

const filterUsersBySearch = (users: UserWithBusinesses[], normalizedSearchQuery: string) =>
  users.filter((user) => {
    const directBusinesses = user.direct_businesses || [];
    const networkBusinesses = (user.networks || []).flatMap((network) => network.businesses || []);
    const allBusinesses = [...directBusinesses, ...networkBusinesses];

    if (!normalizedSearchQuery) {
      return true;
    }

    const userHaystack = [
      user.email || '',
      user.name || '',
      user.phone || '',
    ].join(' ').toLowerCase();

    if (userHaystack.includes(normalizedSearchQuery)) {
      return true;
    }

    return allBusinesses.some((business) =>
      [
        business.name || '',
        business.address || '',
        business.description || '',
        business.id || '',
      ].join(' ').toLowerCase().includes(normalizedSearchQuery)
    );
  });

const closeConfirmDialog = (
  setConfirmDialog: React.Dispatch<React.SetStateAction<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmText: string;
    cancelText: string;
    onConfirm: () => void;
    variant?: 'delete' | 'block';
  }>>,
) => {
  setConfirmDialog((previous) => ({ ...previous, isOpen: false }));
};

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  cancelText: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: 'delete' | 'block';
}

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmText,
  cancelText,
  onConfirm,
  onCancel,
  variant = 'delete'
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200">
      <Card className="max-w-md w-full mx-4 shadow-2xl border-0 animate-in zoom-in-95 duration-200">
        <CardContent className="p-6">
          <div className="flex items-start space-x-4 mb-6">
            <div className={`p-3 rounded-xl ${variant === 'delete' ? 'bg-red-50' : 'bg-primary/10'}`}>
              <AlertTriangle className={`w-6 h-6 ${variant === 'delete' ? 'text-red-600' : 'text-primary'}`} />
            </div>
            <div className="flex-1">
              <h3 className="text-xl font-semibold text-foreground mb-2">{title}</h3>
              <p className="text-muted-foreground leading-relaxed">{message}</p>
            </div>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={onCancel} className="min-w-[100px]">
              {cancelText}
            </Button>
            <Button
              variant={variant === 'delete' ? 'destructive' : 'default'}
              onClick={onConfirm}
              className="min-w-[100px]"
            >
              {confirmText}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

const AdminTabFallback = () => (
  <Card className="border-dashed">
    <CardContent className="flex items-center justify-center py-12 text-sm text-muted-foreground">
      Загрузка раздела...
    </CardContent>
  </Card>
);

export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdminTabId>('businesses');
  const [users, setUsers] = useState<UserWithBusinesses[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedNetworks, setExpandedNetworks] = useState<Set<string>>(new Set());
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [settingsModal, setSettingsModal] = useState<{
    isOpen: boolean;
    businessId: string | null;
    businessName: string;
  }>({
    isOpen: false,
    businessId: null,
    businessName: '',
  });
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmText: string;
    cancelText: string;
    onConfirm: () => void;
    variant?: 'delete' | 'block';
  }>({
    isOpen: false,
    title: '',
    message: '',
    confirmText: '',
    cancelText: '',
    onConfirm: () => { },
  });
  const navigate = useNavigate();
  const { toast } = useToast();

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await newAuth.makeRequest('/admin/users-with-businesses');

      if (data.success) {
        setUsers(data.users || []);
      }
    } catch (error: unknown) {
      console.error('Ошибка загрузки пользователей:', error);
      const message = getErrorMessage(error, 'Не удалось загрузить данные');
      if (message.includes('401') || message.includes('403')) {
        toast({
          title: 'Ошибка доступа',
          description: 'Недостаточно прав для просмотра этой страницы',
          variant: 'destructive',
        });
        navigate('/dashboard');
        return;
      }
      toast({
        title: 'Ошибка',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [navigate, toast]);

  const runReloadingMutation = useCallback(async (
    request: () => Promise<unknown>,
    successDescription: string,
    fallbackError: string,
    options?: { closeDialog?: boolean },
  ) => {
    try {
      const response = await request();
      const payload = typeof response === 'object' && response !== null ? response : null;
      const isSuccess = payload !== null && 'success' in payload && payload.success === true;

      if (isSuccess) {
        toast({
          title: 'Успешно',
          description: successDescription,
        });
        await loadUsers();
      }
    } catch (error: unknown) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, fallbackError),
        variant: 'destructive',
      });
    } finally {
      if (options?.closeDialog) {
        closeConfirmDialog(setConfirmDialog);
      }
    }
  }, [loadUsers, toast]);

  useEffect(() => {
    const checkAccess = async () => {
      try {
        const currentUser = await newAuth.getCurrentUser();
        if (!currentUser) {
          toast({
            title: 'Требуется авторизация',
            description: 'Пожалуйста, войдите в систему',
            variant: 'destructive',
          });
          navigate('/login');
          return;
        }
        if (!currentUser.is_superadmin) {
          toast({
            title: 'Доступ запрещён',
            description: 'Эта страница доступна только супер-администраторам',
            variant: 'destructive',
          });
          navigate('/dashboard');
          return;
        }
        loadUsers();
      } catch (error: unknown) {
        console.error('Ошибка проверки доступа:', error);
        toast({
          title: 'Ошибка',
          description: getErrorMessage(error, 'Не удалось проверить доступ'),
          variant: 'destructive',
        });
      }
    };
    checkAccess();
  }, [loadUsers, navigate, toast]);

  const toggleNetwork = (networkId: string) => {
    const newExpanded = new Set(expandedNetworks);
    if (newExpanded.has(networkId)) {
      newExpanded.delete(networkId);
    } else {
      newExpanded.add(networkId);
    }
    setExpandedNetworks(newExpanded);
  };

  const handleBusinessClick = async (businessId: string) => {
    localStorage.setItem('admin_selected_business_id', businessId);
    navigate('/dashboard/profile');
    window.location.reload();
  };

  const handleDelete = (businessId: string, businessName: string) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Подтверждение удаления',
      message: `Вы уверены, что хотите удалить бизнес "${businessName}"? Это действие нельзя отменить.`,
      confirmText: 'Удалить',
      cancelText: 'Отмена',
      variant: 'delete',
      onConfirm: async () => {
        await runReloadingMutation(
          () => newAuth.makeRequest(`/superadmin/businesses/${businessId}`, {
            method: 'DELETE',
          }),
          'Бизнес удалён',
          'Не удалось удалить бизнес',
          { closeDialog: true },
        );
      },
    });
  };

  const handleBlock = (businessId: string, businessName: string, isBlocked: boolean) => {
    setConfirmDialog({
      isOpen: true,
      title: isBlocked ? 'Подтверждение блокировки' : 'Подтверждение разблокировки',
      message: isBlocked
        ? `Вы уверены, что хотите заблокировать бизнес "${businessName}"?`
        : `Вы уверены, что хотите разблокировать бизнес "${businessName}"?`,
      confirmText: isBlocked ? 'Заблокировать' : 'Разблокировать',
      cancelText: 'Отмена',
      variant: 'block',
      onConfirm: async () => {
        await runReloadingMutation(
          () => newAuth.makeRequest(`/admin/businesses/${businessId}/block`, {
            method: 'POST',
            body: JSON.stringify({ is_blocked: isBlocked }),
          }),
          isBlocked ? 'Бизнес заблокирован' : 'Бизнес разблокирован',
          'Не удалось изменить статус бизнеса',
          { closeDialog: true },
        );
      },
    });
  };

  const handlePauseUser = (userId: string, userEmail: string, isPaused: boolean) => {
    setConfirmDialog({
      isOpen: true,
      title: isPaused ? 'Подтверждение приостановки' : 'Подтверждение возобновления',
      message: isPaused
        ? `Вы уверены, что хотите приостановить пользователя "${userEmail}"? Все его бизнесы также будут приостановлены.`
        : `Вы уверены, что хотите возобновить пользователя "${userEmail}"? Все его бизнесы также будут возобновлены.`,
      confirmText: isPaused ? 'Приостановить' : 'Возобновить',
      cancelText: 'Отмена',
      variant: 'block',
      onConfirm: async () => {
        const endpoint = isPaused ? `/superadmin/users/${userId}/pause` : `/superadmin/users/${userId}/unpause`;
        await runReloadingMutation(
          () => newAuth.makeRequest(endpoint, {
            method: 'POST',
          }),
          isPaused ? 'Пользователь приостановлен' : 'Пользователь возобновлен',
          'Не удалось изменить статус пользователя',
          { closeDialog: true },
        );
      },
    });
  };

  const handleDeleteUser = (userId: string, userEmail: string) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Подтверждение удаления',
      message: `Вы уверены, что хотите удалить пользователя "${userEmail}"? Это действие нельзя отменить. Все его бизнесы и данные будут удалены.`,
      confirmText: 'Удалить',
      cancelText: 'Отмена',
      variant: 'delete',
      onConfirm: async () => {
        closeConfirmDialog(setConfirmDialog);
        await runReloadingMutation(
          () => newAuth.makeRequest(`/superadmin/users/${userId}`, {
            method: 'DELETE',
          }),
          'Пользователь удалён',
          'Не удалось удалить пользователя',
        );
      },
    });
  };

  const handlePromo = async (businessId: string, businessName: string, isPromo: boolean) => {
    await runReloadingMutation(
      () => newAuth.makeRequest(`/admin/businesses/${businessId}/promo`, {
        method: 'POST',
        body: JSON.stringify({ is_promo: !isPromo }),
      }),
      !isPromo ? `Промо тариф установлен для "${businessName}"` : `Промо тариф отключен для "${businessName}"`,
      'Не удалось изменить промо тариф',
    );
  };

  const handleNetworkPromo = async (networkId: string, networkName: string, isPromo: boolean) => {
    await runReloadingMutation(
      () => newAuth.makeRequest(`/admin/networks/${networkId}/promo`, {
        method: 'POST',
        body: JSON.stringify({ is_promo: !isPromo }),
      }),
      !isPromo ? `Промо тариф установлен для сети "${networkName}"` : `Промо тариф отключен для сети "${networkName}"`,
      `Не удалось изменить промо тариф для сети "${networkName}"`,
    );
  };

  const handleCreateSuccess = () => {
    loadUsers();
  };

  const normalizedSearchQuery = searchQuery.trim().toLowerCase();
  const pinnedBusinessId = localStorage.getItem('selectedBusinessId') || localStorage.getItem('admin_selected_business_id') || '';
  const filteredUsers = useMemo(
    () => filterUsersBySearch(users, normalizedSearchQuery),
    [users, normalizedSearchQuery],
  );
  const adminStats = useMemo(() => {
    let businessCount = 0;
    let networkCount = 0;
    let pausedUserCount = 0;
    let leadBusinessCount = 0;

    users.forEach((user) => {
      if (user.is_active === 0) {
        pausedUserCount += 1;
      }

      const directBusinesses = user.direct_businesses || [];
      businessCount += directBusinesses.length;
      leadBusinessCount += directBusinesses.filter((business) => isLeadBusiness(business)).length;

      const networks = user.networks || [];
      networkCount += networks.length;
      networks.forEach((network) => {
        const businesses = network.businesses || [];
        businessCount += businesses.length;
        leadBusinessCount += businesses.filter((business) => isLeadBusiness(business)).length;
      });
    });

    return {
      businessCount,
      leadBusinessCount,
      networkCount,
      pausedUserCount,
    };
  }, [users]);
  const activeTabConfig = adminTabs.find((tab) => tab.id === activeTab) || adminTabs[0];

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary/20 border-t-primary mx-auto"></div>
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-r-primary/40 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }}></div>
          </div>
          <p className="text-muted-foreground font-medium">Загрузка данных...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/60">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <DashboardPageHeader
          eyebrow="Bazich admin"
          title="Панель администратора"
          description="Единое место для контроля пользователей, бизнесов, агентов, парсинга и операционных настроек."
          icon={Settings}
          actions={(
            <Button
              onClick={() => setShowCreateModal(true)}
              className="rounded-2xl bg-slate-950 px-5 text-white shadow-sm hover:bg-slate-800"
            >
              <Plus className="mr-2 h-4 w-4" />
              Создать аккаунт
            </Button>
          )}
        />

        <DashboardCompactMetricsRow
          items={[
            {
              label: 'Пользователи',
              value: users.length,
              hint: filteredUsers.length === users.length ? 'Всего в панели' : `Показано ${filteredUsers.length}`,
            },
            {
              label: 'Бизнесы',
              value: adminStats.businessCount,
              hint: adminStats.leadBusinessCount > 0 ? `Лид-бизнесы скрыты: ${adminStats.leadBusinessCount}` : 'Рабочие аккаунты',
              tone: 'positive',
            },
            {
              label: 'Сети',
              value: adminStats.networkCount,
              hint: 'Сетевые аккаунты и точки',
            },
            {
              label: 'Требуют внимания',
              value: adminStats.pausedUserCount,
              hint: 'Приостановленные пользователи',
              tone: adminStats.pausedUserCount > 0 ? 'warning' : 'default',
            },
          ]}
        />

        <div className="rounded-[2rem] border border-slate-200/80 bg-white/95 p-2.5 shadow-sm">
          <div className="flex flex-col gap-2">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {primaryAdminTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                const isProspecting = tab.id === 'prospecting';
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-semibold transition ${
                      isActive
                        ? isProspecting
                          ? 'bg-orange-500 text-white shadow-sm shadow-orange-200'
                          : 'bg-slate-950 text-white shadow-sm'
                        : isProspecting
                          ? 'bg-orange-50 text-orange-700 hover:bg-orange-100'
                          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-1 gap-2 border-t border-slate-100 pt-2 sm:grid-cols-2 lg:grid-cols-5">
              {toolsAdminTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center justify-center gap-2 rounded-[1.2rem] px-3 py-2.5 text-xs font-semibold transition ${
                      isActive
                        ? 'bg-slate-900 text-white shadow-sm'
                        : 'bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-950'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <Suspense fallback={<AdminTabFallback />}>
        {activeTab === 'agents' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Настройки и контроль ИИ-агентов без лишнего административного шума."
            contentClassName="p-0"
          >
            <AIAgentsManagement />
          </DashboardSection>
        ) : activeTab === 'tokens' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Расход кредитов, аномалии и контроль нагрузки в одном рабочем блоке."
            contentClassName="p-0"
          >
            <TokenUsageStats />
          </DashboardSection>
        ) : activeTab === 'growth' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Редактор схемы роста для клиентских сценариев и рекомендаций."
            contentClassName="p-0"
          >
            <GrowthPlanEditor />
          </DashboardSection>
        ) : activeTab === 'prompts' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Управление промптами анализа и рабочими версиями генерации."
            contentClassName="p-0"
          >
            <PromptsManagement />
          </DashboardSection>
        ) : activeTab === 'proxies' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Прокси и технические настройки парсинга в отдельном контуре."
            contentClassName="p-0"
          >
            <ProxyManagement />
          </DashboardSection>
        ) : activeTab === 'parsing' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Очереди, источники и статусы сбора данных по картам."
            contentClassName="p-0"
          >
            <ParsingManagement />
          </DashboardSection>
        ) : activeTab === 'prospecting' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Лиды, воронка, аутрич и аналитика поиска клиентов."
            contentClassName="p-0"
          >
            <ProspectingManagement />
          </DashboardSection>
        ) : (
          <>
            {(() => {
              return (
                <>
            <DashboardSection
              title="Пользователи и бизнесы"
              description="Сначала найдите аккаунт, затем откройте бизнес или управляйте доступом прямо из строки."
              actions={(
                <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
                  <div className="relative w-full sm:w-[360px]">
                    <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder="Поиск по бизнесу, адресу или email"
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white pl-11 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-4 focus:ring-slate-100"
                    />
                  </div>
                  <Button
                    onClick={() => setShowCreateModal(true)}
                    variant="outline"
                    className="h-11 rounded-2xl border-slate-200 bg-white px-4 text-slate-800 shadow-sm hover:bg-slate-50"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Новый аккаунт
                  </Button>
                </div>
              )}
              contentClassName="space-y-5"
            >
              {filteredUsers.length === 0 ? (
                <DashboardEmptyState
                  title="Пользователи не найдены"
                  description={normalizedSearchQuery ? 'Попробуйте изменить запрос или очистить поиск.' : 'Создайте первый аккаунт, чтобы добавить бизнес и подключить рабочие кабинеты.'}
                  action={(
                    <Button
                      onClick={() => setShowCreateModal(true)}
                      variant="outline"
                      className="rounded-2xl"
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Создать аккаунт
                    </Button>
                  )}
                />
              ) : (
                filteredUsers.map((user) => {
                  const allBusinesses: BusinessListItem[] = [];

                  // Добавляем прямые бизнесы (включая заблокированные)
                  const directBusinesses = user.direct_businesses || [];
                  directBusinesses.forEach(business => {
                    allBusinesses.push({
                      id: business.id,
                      name: business.name,
                      type: 'direct',
                      business
                    });
                  });

                  // Добавляем сети (каждая сеть - одна строка, бизнесы внутри раскрываются)
                  user.networks.forEach(network => {
                    const networkBusinesses = network.businesses || [];
                    // Добавляем сеть как отдельный элемент (показываем первый бизнес или название сети)
                    if (networkBusinesses.length > 0) {
                      allBusinesses.push({
                        id: network.id,
                        name: network.name,
                        type: 'network',
                        networkId: network.id,
                        networkName: network.name,
                        business: networkBusinesses[0] // Используем первый бизнес для отображения в строке
                      });
                    }
                  });

                  const regularBusinesses = allBusinesses.filter((item) => !isLeadBusiness(item.business));
                  const matchedBusinesses = regularBusinesses.filter((item) => {
                    if (!normalizedSearchQuery) {
                      return true;
                    }
                    const haystack = [
                      item.name || '',
                      item.networkName || '',
                      item.business.address || '',
                      item.business.description || '',
                      item.business.id || '',
                    ].join(' ').toLowerCase();
                    return haystack.includes(normalizedSearchQuery);
                  });
                  const visibleBusinesses = [...matchedBusinesses].sort((left, right) => {
                    const leftPinned = left.business.id === pinnedBusinessId ? 1 : 0;
                    const rightPinned = right.business.id === pinnedBusinessId ? 1 : 0;
                    return rightPinned - leftPinned;
                  });
                  if (visibleBusinesses.length === 0) {
                    return null;
                  }

                  const renderBusinessItems = (items: BusinessListItem[]) => items.map((item, index) => (
                    <div
                      key={`${item.id}-${index}`}
                      className="group relative"
                    >
                      {item.type === 'network' ? (
                        <div className="space-y-3">
                          {(() => {
                            const networkId = item.networkId || '';
                            const networkName = item.networkName || item.name;
                            const networkBusinesses = user.networks.find((network) => network.id === networkId)?.businesses || [];
                            const allPromo = networkBusinesses.length > 0 && networkBusinesses.every((business) => business.subscription_tier === 'promo');
                            return (
                              <div
                                className="flex cursor-pointer flex-col gap-4 rounded-3xl border border-slate-200 bg-slate-50/70 p-4 transition hover:border-slate-300 hover:bg-white sm:flex-row sm:items-center sm:justify-between"
                                onClick={() => toggleNetwork(networkId)}
                              >
                                <div className="flex min-w-0 items-center gap-3">
                                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white">
                                    <Network className="h-4 w-4" />
                                  </div>
                                  <div className="min-w-0">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <h4 className="break-words font-semibold text-slate-950">{networkName}</h4>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          handleNetworkPromo(networkId, networkName, allPromo);
                                        }}
                                        className={`h-7 rounded-full px-2.5 text-xs ${allPromo ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'bg-white text-slate-500 hover:bg-slate-100'}`}
                                        title={allPromo ? 'Отключить Промо для сети' : 'Включить Промо для сети'}
                                      >
                                        <Gift className="mr-1.5 h-3.5 w-3.5" />
                                        {allPromo ? 'Промо сеть' : 'Промо'}
                                      </Button>
                                    </div>
                                    <p className="text-xs font-medium text-slate-500">
                                      {networkBusinesses.length} точек сети
                                    </p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-1.5" onClick={(event) => event.stopPropagation()}>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-9 w-9 rounded-full p-0 text-slate-500 hover:bg-white hover:text-slate-950"
                                    onClick={() => toggleNetwork(networkId)}
                                  >
                                    {expandedNetworks.has(networkId) ? (
                                      <ChevronDown className="h-4 w-4" />
                                    ) : (
                                      <ChevronRight className="h-4 w-4" />
                                    )}
                                  </Button>
                                </div>
                              </div>
                            );
                          })()}
                          {expandedNetworks.has(item.networkId || '') && (
                            <div className="space-y-2 border-l border-slate-200 pl-4 sm:ml-5">
                              {user.networks.find((network) => network.id === item.networkId)?.businesses.map((business) => (
                                <BusinessCard
                                  key={business.id}
                                  business={business}
                                  isPinned={business.id === pinnedBusinessId}
                                  onSettingsClick={() => setSettingsModal({
                                    isOpen: true,
                                    businessId: business.id,
                                    businessName: business.name,
                                  })}
                                  onPromoClick={() => {
                                    const isPromo = business.subscription_tier === 'promo';
                                    handlePromo(business.id, business.name, isPromo);
                                  }}
                                  onBlockClick={() => handleBlock(business.id, business.name, business.is_active === 1)}
                                  onDeleteClick={() => handleDelete(business.id, business.name)}
                                  onClick={() => handleBusinessClick(business.id)}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <BusinessCard
                          business={item.business}
                          isPinned={item.business.id === pinnedBusinessId}
                          onSettingsClick={() => setSettingsModal({
                            isOpen: true,
                            businessId: item.business.id,
                            businessName: item.name,
                          })}
                          onPromoClick={() => {
                            const isPromo = item.business.subscription_tier === 'promo';
                            handlePromo(item.business.id, item.name, isPromo);
                          }}
                          onBlockClick={() => handleBlock(item.business.id, item.name, item.business.is_active === 1)}
                          onDeleteClick={() => handleDelete(item.business.id, item.name)}
                          onClick={() => handleBusinessClick(item.business.id)}
                        />
                      )}
                    </div>
                  ));

                  return (
                    <Card
                      key={user.id}
                      className="overflow-hidden rounded-3xl border-slate-200/80 bg-white shadow-sm transition hover:border-slate-300 hover:shadow-md"
                    >
                      <CardHeader className="border-b border-slate-100 px-5 py-4">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                          <div className="flex min-w-0 items-center gap-3">
                            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                              <User className="h-5 w-5" />
                            </div>
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className={`break-words text-lg font-semibold ${user.is_active === 0 ? 'text-slate-400 line-through' : 'text-slate-950'}`}>
                                  {user.name || user.email}
                                </h3>
                                {user.is_superadmin && (
                                  <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                                    Админ
                                  </span>
                                )}
                                {user.is_active === 0 && (
                                  <span className="rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700">
                                    Приостановлен
                                  </span>
                                )}
                              </div>
                              <p className="mt-0.5 truncate text-sm text-slate-500">{user.email}</p>
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                              {visibleBusinesses.length} {visibleBusinesses.length === 1 ? 'бизнес' : 'бизнесов'}
                            </div>
                            <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-white p-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 rounded-full p-0 text-slate-500 hover:bg-slate-100 hover:text-slate-950"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handlePauseUser(user.id, user.email, user.is_active !== 0);
                                }}
                                title={user.is_active === 0 ? "Возобновить пользователя" : "Приостановить пользователя"}
                              >
                                {user.is_active === 0 ? (
                                  <User className="h-4 w-4" />
                                ) : (
                                  <Ban className="h-4 w-4" />
                                )}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 rounded-full p-0 text-rose-500 hover:bg-rose-50 hover:text-rose-700"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteUser(user.id, user.email);
                                }}
                                title="Удалить пользователя"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="px-5 py-5">
                        <div className="space-y-4">
                          {renderBusinessItems(visibleBusinesses)}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </DashboardSection>
                </>
              );
            })()}
          </>
        )}
        </Suspense>
      </div>

      <CreateBusinessModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleCreateSuccess}
      />

      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText={confirmDialog.confirmText}
        cancelText={confirmDialog.cancelText}
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog({ ...confirmDialog, isOpen: false })}
        variant={confirmDialog.variant}
      />

      {/* Модальное окно настроек внешних кабинетов */}
      {settingsModal.isOpen && settingsModal.businessId && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <Card className="max-w-4xl w-full max-h-[90vh] overflow-hidden shadow-2xl border-0 animate-in zoom-in-95 duration-200">
            <CardHeader className="border-b border-border/50 bg-gradient-to-r from-card to-card/50">
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle className="text-2xl">Настройки внешних кабинетов</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">{settingsModal.businessName}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setSettingsModal({ isOpen: false, businessId: null, businessName: '' })}
                  className="rounded-full"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="overflow-y-auto max-h-[calc(90vh-120px)] p-6">
              {settingsModal.businessId && (
                <AdminExternalCabinetSettings
                  businessId={settingsModal.businessId}
                  businessName={settingsModal.businessName}
                />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

// Business Card Component
interface BusinessCardProps {
  business: Business;
  isPinned?: boolean;
  onSettingsClick: () => void;
  onPromoClick: () => void;
  onBlockClick: () => void;
  onDeleteClick: () => void;
  onClick: () => void;
}

const BusinessCard: React.FC<BusinessCardProps> = ({
  business,
  isPinned = false,
  onSettingsClick,
  onPromoClick,
  onBlockClick,
  onDeleteClick,
  onClick,
}) => {
  const isBlocked = business.is_active === 0;
  const isPromo = business.subscription_tier === 'promo';

  return (
    <div
      className="group relative cursor-pointer rounded-3xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:bg-slate-50/60"
      onClick={onClick}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
              <Building2 className="h-4 w-4" />
            </div>
            <h4 className={`break-words font-semibold ${isBlocked ? 'text-slate-400 line-through' : 'text-slate-950'}`}>
              {business.name}
            </h4>
            {isBlocked && (
              <span className="rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700">
                Заблокирован
              </span>
            )}
            {isPromo && (
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                Промо
              </span>
            )}
            {isPinned && (
              <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700">
                Выбран сейчас
              </span>
            )}
          </div>
          {business.address && (
            <div className="ml-10 flex items-center gap-1.5 text-sm text-slate-500">
              <MapPin className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{business.address}</span>
            </div>
          )}
        </div>
        <div
          className="flex w-full items-center justify-end gap-1 rounded-2xl border border-slate-200 bg-slate-50 p-1 lg:w-auto"
          onClick={(event) => event.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="sm"
            onClick={onSettingsClick}
            className="h-8 w-8 rounded-xl p-0 text-slate-500 hover:bg-white hover:text-slate-950"
            title="Настройки"
          >
            <Settings className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onPromoClick}
            className={`h-8 w-8 rounded-xl p-0 ${isPromo ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-100' : 'text-slate-500 hover:bg-white hover:text-slate-950'}`}
            title={isPromo ? 'Отключить Промо' : 'Включить Промо'}
          >
            <Gift className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onBlockClick}
            className={`h-8 w-8 rounded-xl p-0 ${!isBlocked ? 'text-slate-500 hover:bg-rose-50 hover:text-rose-700' : 'text-emerald-600 hover:bg-white hover:text-emerald-700'}`}
            title={isBlocked ? 'Разблокировать' : 'Заблокировать'}
          >
            <Ban className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDeleteClick}
            className="h-8 w-8 rounded-xl p-0 text-rose-500 hover:bg-rose-50 hover:text-rose-700"
            title="Удалить"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
