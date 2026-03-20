import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { ChevronDown, ChevronRight, Building2, Network, MapPin, User, Plus, Trash2, Ban, AlertTriangle, Bot, Gift, Settings, BarChart3, TrendingUp, FileText, X, Search } from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { useToast } from '../../hooks/use-toast';
import { CreateBusinessModal } from '../../components/CreateBusinessModal';
import { AIAgentsManagement } from '../../components/AIAgentsManagement';
import { TokenUsageStats } from '../../components/TokenUsageStats';
import { AdminExternalCabinetSettings } from '../../components/AdminExternalCabinetSettings';
import { GrowthPlan } from '../../components/GrowthPlan';
import { GrowthPlanEditor } from '../../components/GrowthPlanEditor';
import { PromptsManagement } from '../../components/PromptsManagement';
import { ProxyManagement } from '../../components/ProxyManagement';
import { ParsingManagement } from '../../components/ParsingManagement';
import { ProspectingManagement } from '../../components/ProspectingManagement';

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

const LEAD_OUTREACH_STATUS = 'lead_outreach';

const isLeadBusiness = (business?: Business | null) =>
  business?.is_lead_business === true ||
  String(business?.entity_group || '').trim().toLowerCase() === 'lead' ||
  String(business?.moderation_status || '').trim().toLowerCase() === LEAD_OUTREACH_STATUS;

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

export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'businesses' | 'leads' | 'agents' | 'tokens' | 'growth' | 'prompts' | 'proxies' | 'parsing' | 'prospecting'>('businesses');
  const [users, setUsers] = useState<UserWithBusinesses[]>([]);
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

  useEffect(() => {
    // Проверяем доступ только для demyanovap@yandex.ru
    const checkAccess = async () => {
      try {
        const currentUser = await newAuth.getCurrentUser();
        if (!currentUser) {
          // Если пользователь не авторизован, перенаправляем на логин
          toast({
            title: 'Требуется авторизация',
            description: 'Пожалуйста, войдите в систему',
            variant: 'destructive',
          });
          navigate('/login');
          return;
        }
        if (currentUser.email !== 'demyanovap@yandex.ru') {
          toast({
            title: 'Доступ запрещён',
            description: 'Эта страница доступна только для demyanovap@yandex.ru',
            variant: 'destructive',
          });
          navigate('/dashboard');
          return;
        }
        loadUsers();
      } catch (error) {
        console.error('Ошибка проверки доступа:', error);
        // Не перенаправляем на /login, если уже в контексте DashboardLayout
        // Просто показываем ошибку и остаёмся на странице
        toast({
          title: 'Ошибка',
          description: 'Не удалось проверить доступ',
          variant: 'destructive',
        });
      }
    };
    checkAccess();
  }, [navigate]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const data = await newAuth.makeRequest('/admin/users-with-businesses');

      if (data.success) {
        // Логируем для отладки
        let totalBlocked = 0;
        data.users?.forEach((user: any) => {
          const blockedDirect = user.direct_businesses?.filter((b: any) => b.is_active === 0).length || 0;
          const blockedNetwork = user.networks?.reduce((sum: number, n: any) =>
            sum + (n.businesses?.filter((b: any) => b.is_active === 0).length || 0), 0) || 0;
          totalBlocked += blockedDirect + blockedNetwork;
        });
        console.log(`🔍 DEBUG AdminPage: Загружено пользователей: ${data.users?.length || 0}, заблокированных бизнесов: ${totalBlocked}`);
        console.log('🔍 DEBUG AdminPage: Данные пользователей:', data.users);
        setUsers(data.users || []);
      }
    } catch (error: any) {
      console.error('Ошибка загрузки пользователей:', error);
      if (error.message && (error.message.includes('401') || error.message.includes('403'))) {
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
        description: 'Не удалось загрузить данные',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

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
        try {
          console.log(`🔍 DELETE запрос для бизнеса: ID=${businessId}, name=${businessName}`);
          const data = await newAuth.makeRequest(`/superadmin/businesses/${businessId}`, {
            method: 'DELETE',
          });

          if (data.success) {
            toast({
              title: 'Успешно',
              description: 'Бизнес удалён',
            });
            loadUsers();
          }
        } catch (error: any) {
          toast({
            title: 'Ошибка',
            description: error.message || 'Не удалось удалить бизнес',
            variant: 'destructive',
          });
        } finally {
          setConfirmDialog(prev => ({ ...prev, isOpen: false }));
        }
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
        try {
          const data = await newAuth.makeRequest(`/admin/businesses/${businessId}/block`, {
            method: 'POST',
            body: JSON.stringify({ is_blocked: isBlocked }),
          });

          if (data.success) {
            toast({
              title: 'Успешно',
              description: isBlocked ? 'Бизнес заблокирован' : 'Бизнес разблокирован',
            });
            loadUsers();
          }
        } catch (error: any) {
          toast({
            title: 'Ошибка',
            description: error.message || 'Не удалось изменить статус бизнеса',
            variant: 'destructive',
          });
        } finally {
          setConfirmDialog(prev => ({ ...prev, isOpen: false }));
        }
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
        try {
          const endpoint = isPaused ? `/superadmin/users/${userId}/pause` : `/superadmin/users/${userId}/unpause`;
          const data = await newAuth.makeRequest(endpoint, {
            method: 'POST',
          });

          if (data.success) {
            toast({
              title: 'Успешно',
              description: isPaused ? 'Пользователь приостановлен' : 'Пользователь возобновлен',
            });
            loadUsers();
          }
        } catch (error: any) {
          toast({
            title: 'Ошибка',
            description: error.message || 'Не удалось изменить статус пользователя',
            variant: 'destructive',
          });
        } finally {
          setConfirmDialog(prev => ({ ...prev, isOpen: false }));
        }
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
        // Закрываем диалог сразу после подтверждения
        setConfirmDialog(prev => ({ ...prev, isOpen: false }));

        try {
          const data = await newAuth.makeRequest(`/superadmin/users/${userId}`, {
            method: 'DELETE',
          });

          if (data.success) {
            toast({
              title: 'Успешно',
              description: 'Пользователь удалён',
            });
            loadUsers();
          }
        } catch (error: any) {
          toast({
            title: 'Ошибка',
            description: error.message || 'Не удалось удалить пользователя',
            variant: 'destructive',
          });
        }
      },
    });
  };

  const handlePromo = async (businessId: string, businessName: string, isPromo: boolean) => {
    try {
      const data = await newAuth.makeRequest(`/admin/businesses/${businessId}/promo`, {
        method: 'POST',
        body: JSON.stringify({ is_promo: !isPromo }),
      });

      if (data.success) {
        toast({
          title: 'Успешно',
          description: !isPromo ? 'Промо тариф установлен' : 'Промо тариф отключен',
        });
        loadUsers();
      }
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось изменить промо тариф',
        variant: 'destructive',
      });
    }
  };

  const handleNetworkPromo = async (networkId: string, networkName: string, isPromo: boolean) => {
    try {
      const data = await newAuth.makeRequest(`/admin/networks/${networkId}/promo`, {
        method: 'POST',
        body: JSON.stringify({ is_promo: !isPromo }),
      });

      if (data.success) {
        toast({
          title: 'Успешно',
          description: !isPromo ? 'Промо тариф установлен для всей сети' : 'Промо тариф отключен для всей сети',
        });
        loadUsers();
      }
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || `Не удалось изменить промо тариф для сети "${networkName}"`,
        variant: 'destructive',
      });
    }
  };

  const handleCreateSuccess = () => {
    loadUsers();
  };

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

  const tabs = [
    { id: 'businesses' as const, label: 'Пользователи и бизнесы', icon: User },
    { id: 'leads' as const, label: 'Лиды', icon: Building2 },
    { id: 'agents' as const, label: 'ИИ агенты', icon: Bot },
    { id: 'tokens' as const, label: 'Статистика кредитов', icon: BarChart3 },
    { id: 'growth' as const, label: 'Схема роста', icon: TrendingUp },
    { id: 'prompts' as const, label: 'Промпты анализа', icon: FileText },
    { id: 'proxies' as const, label: 'Прокси', icon: Network },
    { id: 'parsing' as const, label: 'Парсинг', icon: MapPin },
    { id: 'prospecting' as const, label: 'Поиск клиентов', icon: Search },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="mb-8 space-y-2">
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
            Административная панель
          </h1>
          <p className="text-muted-foreground text-lg">Управление пользователями, бизнесами и ИИ агентами</p>
        </div>

        {/* Modern Tab Navigation */}
        <div className="mb-8">
          <div className="flex flex-wrap gap-2 p-1 bg-card/50 backdrop-blur-sm rounded-xl border border-border/50 shadow-sm">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    relative flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm
                    transition-all duration-200 ease-out
                    ${isActive
                      ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                    }
                  `}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'scale-110' : ''} transition-transform duration-200`} />
                  <span>{tab.label}</span>
                  {isActive && (
                    <div className="absolute inset-0 rounded-lg bg-primary/10 animate-pulse" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {activeTab === 'agents' ? (
          <AIAgentsManagement />
        ) : activeTab === 'tokens' ? (
          <TokenUsageStats />
        ) : activeTab === 'growth' ? (
          <GrowthPlanEditor />
        ) : activeTab === 'prompts' ? (
          <PromptsManagement />
        ) : activeTab === 'proxies' ? (
          <ProxyManagement />
        ) : activeTab === 'parsing' ? (
          <ParsingManagement />
        ) : activeTab === 'prospecting' ? (
          <ProspectingManagement />
        ) : (
          <>
            {(() => {
              const isLeadsTab = activeTab === 'leads';
              const usersToRender = isLeadsTab
                ? users.filter((user) => {
                    const directBusinesses = user.direct_businesses || [];
                    const networkBusinesses = (user.networks || []).flatMap((network) => network.businesses || []);
                    const all = [...directBusinesses, ...networkBusinesses];
                    return all.some((business) => isLeadBusiness(business));
                  })
                : users;
              return (
                <>
            {/* Action Bar */}
            <div className="mb-6 flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                {isLeadsTab ? (
                  <>
                    Пользователи с лидами: <span className="font-semibold text-foreground">{usersToRender.length}</span>
                  </>
                ) : (
                  <>
                    Всего пользователей: <span className="font-semibold text-foreground">{users.length}</span>
                  </>
                )}
              </div>
              {!isLeadsTab && (
                <Button
                  onClick={() => setShowCreateModal(true)}
                  className="shadow-md hover:shadow-lg transition-shadow duration-200"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Создать аккаунт
                </Button>
              )}
            </div>

            {/* Modern Card-based Layout */}
            <div className="space-y-6">
              {usersToRender.length === 0 ? (
                <Card className="border-dashed">
                  <CardContent className="flex flex-col items-center justify-center py-16">
                    <div className="p-4 rounded-full bg-muted mb-4">
                      <User className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <p className="text-muted-foreground font-medium">
                      {isLeadsTab ? 'Лиды не найдены' : 'Пользователи не найдены'}
                    </p>
                    {!isLeadsTab && (
                      <Button
                        onClick={() => setShowCreateModal(true)}
                        variant="outline"
                        className="mt-4"
                      >
                        <Plus className="w-4 h-4 mr-2" />
                        Создать первого пользователя
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ) : (
                usersToRender.map((user) => {
                  const allBusinesses: BusinessListItem[] = [];

                  // Добавляем прямые бизнесы (включая заблокированные)
                  const directBusinesses = user.direct_businesses || [];
                  console.log(`🔍 DEBUG Frontend: Пользователь ${user.email}, прямых бизнесов: ${directBusinesses.length}`);
                  directBusinesses.forEach(business => {
                    console.log(`  - Бизнес: ${business.name}, is_active: ${business.is_active}, type: ${typeof business.is_active}`);
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
                    console.log(`🔍 DEBUG Frontend: Сеть ${network.name}, бизнесов: ${networkBusinesses.length}`);
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
                  const leadBusinesses = allBusinesses.filter((item) => isLeadBusiness(item.business));
                  const visibleBusinesses = isLeadsTab ? leadBusinesses : regularBusinesses;
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
                            const networkBusinesses = user.networks.find(n => n.id === item.networkId)?.businesses || [];
                            const allPromo = networkBusinesses.length > 0 && networkBusinesses.every((business) => business.subscription_tier === 'promo');
                            return (
                              <div
                                className="flex items-center justify-between p-4 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                                onClick={() => toggleNetwork(item.networkId!)}
                              >
                                <div className="flex items-center gap-3">
                                  <div className="p-2 rounded-lg bg-primary/10">
                                    <Network className="w-4 h-4 text-primary" />
                                  </div>
                                  <div>
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <h4 className="font-semibold text-foreground">{item.networkName}</h4>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleNetworkPromo(item.networkId!, item.networkName!, allPromo)}
                                        className={`h-7 px-2.5 text-xs ${allPromo ? 'text-primary bg-primary/10 hover:bg-primary/15' : 'text-muted-foreground bg-background/80 hover:bg-background'}`}
                                        title={allPromo ? 'Отключить Промо для сети' : 'Включить Промо для сети'}
                                      >
                                        <Gift className="w-3.5 h-3.5 mr-1.5" />
                                        {allPromo ? 'Промо сеть' : 'Промо'}
                                      </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                      {user.networks.find(n => n.id === item.networkId)?.businesses.length || 0} точек сети
                                    </p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 w-8 p-0"
                                  >
                                    {expandedNetworks.has(item.networkId!) ? (
                                      <ChevronDown className="h-4 w-4" />
                                    ) : (
                                      <ChevronRight className="h-4 w-4" />
                                    )}
                                  </Button>
                                </div>
                              </div>
                            );
                          })()}
                          {expandedNetworks.has(item.networkId!) && (
                            <div className="ml-4 space-y-2 pl-4 border-l-2 border-primary/20">
                              {user.networks.find(n => n.id === item.networkId)?.businesses.map((business) => (
                                <BusinessCard
                                  key={business.id}
                                  business={business}
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
                      className="overflow-hidden border-0 shadow-md hover:shadow-xl transition-all duration-300 bg-card/50 backdrop-blur-sm"
                    >
                      <CardHeader className="pb-4 border-b border-border/50">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="p-2.5 rounded-xl bg-primary/10">
                              <User className="w-5 h-5 text-primary" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className={`text-lg font-semibold ${user.is_active === 0 ? 'line-through text-muted-foreground' : 'text-foreground'}`}>
                                  {user.name || user.email}
                                </h3>
                                {user.is_superadmin && (
                                  <span className="px-2 py-0.5 text-xs font-medium bg-primary/20 text-primary rounded-full">
                                    Админ
                                  </span>
                                )}
                                {user.is_active === 0 && (
                                  <span className="px-2 py-0.5 text-xs font-medium bg-destructive/10 text-destructive rounded-full">
                                    Приостановлен
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-muted-foreground mt-0.5">{user.email}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="text-xs text-muted-foreground">
                              {visibleBusinesses.length} {visibleBusinesses.length === 1 ? 'бизнес' : 'бизнесов'}
                            </div>
                            <div className="flex items-center gap-1 opacity-100">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
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
                                className="h-8 w-8 p-0 text-destructive hover:text-destructive hover:bg-destructive/10"
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
                      <CardContent className="pt-6">
                        <div className="space-y-4">
                          {renderBusinessItems(visibleBusinesses)}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </div>
                </>
              );
            })()}
          </>
        )}
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
  onSettingsClick: () => void;
  onPromoClick: () => void;
  onBlockClick: () => void;
  onDeleteClick: () => void;
  onClick: () => void;
}

const BusinessCard: React.FC<BusinessCardProps> = ({
  business,
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
      className="group relative p-4 rounded-lg border border-border/50 bg-card hover:border-primary/50 hover:shadow-md transition-all duration-200 cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-md bg-primary/10">
              <Building2 className="w-4 h-4 text-primary" />
            </div>
            <h4 className={`font-semibold text-foreground ${isBlocked ? 'line-through text-muted-foreground' : ''}`}>
              {business.name}
            </h4>
            {isBlocked && (
              <span className="px-2 py-0.5 text-xs font-medium bg-destructive/10 text-destructive rounded-full">
                Заблокирован
              </span>
            )}
            {isPromo && (
              <span className="px-2 py-0.5 text-xs font-medium bg-primary/20 text-primary rounded-full">
                Промо
              </span>
            )}
          </div>
          {business.address && (
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground ml-7">
              <MapPin className="w-3.5 h-3.5" />
              <span className="truncate">{business.address}</span>
            </div>
          )}
        </div>
        <div
          className="flex items-center gap-1.5"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="sm"
            onClick={onSettingsClick}
            className="h-8 w-8 p-0"
            title="Настройки"
          >
            <Settings className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onPromoClick}
            className={`h-8 w-8 p-0 ${isPromo ? 'text-primary bg-primary/10' : ''}`}
            title={isPromo ? 'Отключить Промо' : 'Включить Промо'}
          >
            <Gift className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onBlockClick}
            className={`h-8 w-8 p-0 ${!isBlocked ? 'hover:text-destructive' : 'text-green-600 hover:text-green-700'}`}
            title={isBlocked ? 'Разблокировать' : 'Заблокировать'}
          >
            <Ban className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDeleteClick}
            className="h-8 w-8 p-0 text-destructive hover:bg-destructive/10"
            title="Удалить"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
