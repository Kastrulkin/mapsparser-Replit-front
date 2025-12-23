import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { ChevronDown, ChevronRight, Building2, Network, MapPin, User, Plus, Trash2, Ban, AlertTriangle, Bot, Gift, Settings } from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { useToast } from '../../hooks/use-toast';
import { CreateBusinessModal } from '../../components/CreateBusinessModal';
import { AIAgentsManagement } from '../../components/AIAgentsManagement';
import { TokenUsageStats } from '../../components/TokenUsageStats';
import { AdminExternalCabinetSettings } from '../../components/AdminExternalCabinetSettings';

interface Business {
  id: string;
  name: string;
  description?: string;
  address?: string;
  industry?: string;
  created_at?: string;
  is_active?: number;
  subscription_tier?: string;
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
  direct_businesses: Business[];
  networks: Network[];
}

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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="p-6">
          <div className="flex items-center space-x-3 mb-4">
            <div className={`p-2 rounded-full ${variant === 'delete' ? 'bg-red-100' : 'bg-orange-100'}`}>
              <AlertTriangle className={`w-6 h-6 ${variant === 'delete' ? 'text-red-600' : 'text-orange-600'}`} />
            </div>
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          </div>
          <p className="text-gray-600 mb-6">{message}</p>
          <div className="flex justify-end space-x-3">
            <Button variant="outline" onClick={onCancel}>
              {cancelText}
            </Button>
            <Button
              variant={variant === 'delete' ? 'destructive' : 'default'}
              onClick={onConfirm}
            >
              {confirmText}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'businesses' | 'agents' | 'tokens'>('businesses');
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
    onConfirm: () => {},
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
      const token = await newAuth.getToken();
      if (!token) {
        toast({
          title: 'Ошибка',
          description: 'Требуется авторизация',
          variant: 'destructive',
        });
        // Не перенаправляем на /login, если уже в контексте DashboardLayout
        // Просто показываем ошибку
        return;
      }

      const response = await fetch('/api/admin/users-with-businesses', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          toast({
            title: 'Ошибка доступа',
            description: 'Недостаточно прав для просмотра этой страницы',
            variant: 'destructive',
          });
          navigate('/dashboard');
          return;
        }
        throw new Error('Ошибка загрузки данных');
      }

      const data = await response.json();
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
    } catch (error) {
      console.error('Ошибка загрузки пользователей:', error);
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
          const token = await newAuth.getToken();
          console.log(`🔍 DELETE запрос для бизнеса: ID=${businessId}, name=${businessName}`);
          const response = await fetch(`/api/superadmin/businesses/${businessId}`, {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });
          
          console.log(`🔍 DELETE ответ: status=${response.status}, ok=${response.ok}`);

          if (response.ok) {
            toast({
              title: 'Успешно',
              description: 'Бизнес удалён',
            });
            loadUsers();
          } else {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Ошибка удаления');
          }
        } catch (error: any) {
          toast({
            title: 'Ошибка',
            description: error.message || 'Не удалось удалить бизнес',
            variant: 'destructive',
          });
        } finally {
          setConfirmDialog({ ...confirmDialog, isOpen: false });
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
          const token = await newAuth.getToken();
          const response = await fetch(`/api/admin/businesses/${businessId}/block`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ is_blocked: isBlocked }),
          });

          if (response.ok) {
            toast({
              title: 'Успешно',
              description: isBlocked ? 'Бизнес заблокирован' : 'Бизнес разблокирован',
            });
            loadUsers();
          } else {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Ошибка блокировки');
          }
        } catch (error: any) {
          toast({
            title: 'Ошибка',
            description: error.message || 'Не удалось изменить статус бизнеса',
            variant: 'destructive',
          });
        } finally {
          setConfirmDialog({ ...confirmDialog, isOpen: false });
        }
      },
    });
  };

  const handlePromo = async (businessId: string, businessName: string, isPromo: boolean) => {
    try {
      const token = await newAuth.getToken();
      const response = await fetch(`/api/admin/businesses/${businessId}/promo`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ is_promo: !isPromo }),
      });

      if (response.ok) {
        toast({
          title: 'Успешно',
          description: !isPromo ? 'Промо тариф установлен' : 'Промо тариф отключен',
        });
        loadUsers();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Ошибка установки промо тарифа');
      }
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось изменить промо тариф',
        variant: 'destructive',
      });
    }
  };

  const handleCreateSuccess = () => {
    loadUsers();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Загрузка данных...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Административная панель</h1>
        <p className="text-gray-600">Управление пользователями, бизнесами и ИИ агентами</p>
      </div>

      {/* Табы */}
      <div className="flex space-x-1 mb-6 border-b">
        <button
          onClick={() => setActiveTab('businesses')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'businesses'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Пользователи и бизнесы
        </button>
        <button
          onClick={() => setActiveTab('agents')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'agents'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Bot className="h-4 w-4 inline mr-2" />
          ИИ агенты
        </button>
        <button
          onClick={() => setActiveTab('tokens')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'tokens'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          📊 Статистика токенов
        </button>
      </div>

      {activeTab === 'agents' ? (
        <AIAgentsManagement />
      ) : activeTab === 'tokens' ? (
        <TokenUsageStats />
      ) : (
        <>
          <div className="mb-6 flex items-center justify-end">
            <Button onClick={() => setShowCreateModal(true)} className="flex items-center space-x-2">
              <Plus className="w-4 h-4" />
              <span>Создать аккаунт</span>
            </Button>
          </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Имя пользователя
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Бизнес
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Действия
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {users.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-6 py-8 text-center text-gray-500">
                  Пользователи не найдены
                </td>
              </tr>
            ) : (
              users.map((user) => {
                const allBusinesses: Array<{ id: string; name: string; type: 'direct' | 'network'; networkId?: string; networkName?: string; business: Business }> = [];
                
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
                
                // Добавляем сети
                user.networks.forEach(network => {
                  allBusinesses.push({
                    id: network.id,
                    name: network.name,
                    type: 'network',
                    networkId: network.id,
                    networkName: network.name,
                    business: network.businesses[0] || {} as Business
                  });
                });

                return allBusinesses.map((item, index) => (
                  <tr key={`${user.id}-${item.id}-${index}`} className="hover:bg-gray-50">
                    {index === 0 && (
                      <td
                        rowSpan={allBusinesses.length}
                        className="px-6 py-4 whitespace-nowrap align-top"
                      >
                        <div className="flex items-center space-x-2">
                          <User className="h-5 w-5 text-gray-400" />
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {user.name || user.email}
                              {user.is_superadmin && (
                                <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">
                                  Админ
                                </span>
                              )}
                            </div>
                            <div className="text-sm text-gray-500">{user.email}</div>
                          </div>
                        </div>
                      </td>
                    )}
                    <td className="px-6 py-4">
                      {item.type === 'network' ? (
                        <div>
                          <div className="flex items-center space-x-2">
                            <Network className="h-4 w-4 text-gray-400" />
                            <span className="text-sm font-medium text-gray-900">{item.networkName}</span>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={() => toggleNetwork(item.networkId!)}
                            >
                              {expandedNetworks.has(item.networkId!) ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                          {expandedNetworks.has(item.networkId!) && (
                            <div className="mt-2 ml-6 space-y-2">
                              {user.networks.find(n => n.id === item.networkId)?.businesses.map((business) => (
                                <div
                                  key={business.id}
                                  className="p-2 border border-gray-200 rounded hover:bg-blue-50 cursor-pointer"
                                  onClick={() => handleBusinessClick(business.id)}
                                >
                                  <div className="flex items-center space-x-2">
                                    <div className={`text-sm font-medium ${business.is_active === 0 ? 'text-gray-400 line-through' : 'text-gray-900'}`}>
                                      {business.name}
                                    </div>
                                    {business.is_active === 0 && (
                                      <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">
                                        Заблокирован
                                      </span>
                                    )}
                                  </div>
                                  {business.address && (
                                    <div className="text-xs text-gray-500 flex items-center mt-1">
                                      <MapPin className="h-3 w-3 mr-1" />
                                      {business.address}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div
                          className="flex items-center space-x-2 cursor-pointer hover:text-blue-600"
                          onClick={() => handleBusinessClick(item.business.id)}
                        >
                          <Building2 className="h-4 w-4 text-gray-400" />
                          <span className={`text-sm font-medium ${item.business.is_active === 0 ? 'text-gray-400 line-through' : 'text-gray-900'}`}>
                            {item.name}
                          </span>
                          {item.business.is_active === 0 && (
                            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">
                              Заблокирован
                            </span>
                          )}
                          {item.business.address && (
                            <span className="text-xs text-gray-500 flex items-center">
                              <MapPin className="h-3 w-3 mr-1" />
                              {item.business.address}
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right align-top">
                      {item.type === 'direct' ? (
                        <div className="flex items-center justify-end space-x-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSettingsModal({
                                isOpen: true,
                                businessId: item.business.id,
                                businessName: item.name,
                              });
                            }}
                          >
                            <Settings className="w-4 h-4 mr-1" />
                            Настройки
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              const isPromo = item.business.subscription_tier === 'promo';
                              handlePromo(item.business.id, item.name, isPromo);
                            }}
                            className={item.business.subscription_tier === 'promo' ? 'bg-purple-50 text-purple-700 hover:bg-purple-100' : ''}
                          >
                            <Gift className="w-4 h-4 mr-1" />
                            {item.business.subscription_tier === 'promo' ? 'Отключить Промо' : 'Промо'}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              // Если бизнес активен (is_active === 1), хотим заблокировать (isBlocked = true)
                              // Если бизнес заблокирован (is_active !== 1), хотим разблокировать (isBlocked = false)
                              handleBlock(item.business.id, item.name, item.business.is_active === 1);
                            }}
                            className={item.business.is_active !== 1 ? 'bg-green-50 text-green-700 hover:bg-green-100' : ''}
                          >
                            <Ban className="w-4 h-4 mr-1" />
                            {item.business.is_active !== 1 ? 'Разблокировать' : 'Заблокировать'}
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(item.business.id, item.name);
                            }}
                          >
                            <Trash2 className="w-4 h-4 mr-1" />
                            Удалить
                          </Button>
                        </div>
                      ) : (
                        <div>
                          {/* Для сетей показываем действия для точек сети только когда раскрыта */}
                          {expandedNetworks.has(item.networkId!) && (
                            <div className="space-y-2">
                              {user.networks.find(n => n.id === item.networkId)?.businesses.map((business) => (
                                <div key={business.id} className="flex items-center justify-end space-x-2 mb-2">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSettingsModal({
                                        isOpen: true,
                                        businessId: business.id,
                                        businessName: business.name,
                                      });
                                    }}
                                  >
                                    <Settings className="w-4 h-4 mr-1" />
                                    Настройки
                                  </Button>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      const isPromo = business.subscription_tier === 'promo';
                                      handlePromo(business.id, business.name, isPromo);
                                    }}
                                    className={business.subscription_tier === 'promo' ? 'bg-purple-50 text-purple-700 hover:bg-purple-100' : ''}
                                  >
                                    <Gift className="w-4 h-4 mr-1" />
                                    {business.subscription_tier === 'promo' ? 'Отключить Промо' : 'Промо'}
                                  </Button>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      // Если бизнес активен (is_active === 1), хотим заблокировать (isBlocked = true)
                                      // Если бизнес заблокирован (is_active !== 1), хотим разблокировать (isBlocked = false)
                                      handleBlock(business.id, business.name, business.is_active === 1);
                                    }}
                                    className={business.is_active !== 1 ? 'bg-green-50 text-green-700 hover:bg-green-100' : ''}
                                  >
                                    <Ban className="w-4 h-4 mr-1" />
                                    {business.is_active !== 1 ? 'Разблокировать' : 'Заблокировать'}
                                  </Button>
                                  <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDelete(business.id, business.name);
                                    }}
                                  >
                                    <Trash2 className="w-4 h-4 mr-1" />
                                    Удалить
                                  </Button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ));
              })
            )}
          </tbody>
        </table>
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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">Настройки внешних кабинетов</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSettingsModal({ isOpen: false, businessId: null, businessName: '' })}
                >
                  ✕
                </Button>
              </div>
              <AdminExternalCabinetSettings
                businessId={settingsModal.businessId}
                businessName={settingsModal.businessName}
              />
            </div>
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
};
