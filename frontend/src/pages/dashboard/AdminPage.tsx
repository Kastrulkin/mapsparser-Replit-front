import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { ChevronDown, ChevronRight, Building2, Network, MapPin, User } from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { useToast } from '../../hooks/use-toast';

interface Business {
  id: string;
  name: string;
  description?: string;
  address?: string;
  industry?: string;
  created_at?: string;
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

export const AdminPage: React.FC = () => {
  const [users, setUsers] = useState<UserWithBusinesses[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedUsers, setExpandedUsers] = useState<Set<string>>(new Set());
  const [expandedNetworks, setExpandedNetworks] = useState<Set<string>>(new Set());
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    loadUsers();
  }, []);

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
        navigate('/login');
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
        setUsers(data.users || []);
        // Автоматически раскрываем всех пользователей
        setExpandedUsers(new Set(data.users.map((u: UserWithBusinesses) => u.id)));
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

  const toggleUser = (userId: string) => {
    const newExpanded = new Set(expandedUsers);
    if (newExpanded.has(userId)) {
      newExpanded.delete(userId);
    } else {
      newExpanded.add(userId);
    }
    setExpandedUsers(newExpanded);
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
    // Сохраняем businessId в localStorage для переключения
    localStorage.setItem('admin_selected_business_id', businessId);
    navigate('/dashboard/profile');
    // Перезагружаем страницу, чтобы применить переключение бизнеса
    window.location.reload();
  };

  const handleNetworkClick = async (networkId: string) => {
    // Для сети переключаемся на первую точку или создаём специальный режим
    // Пока просто переключаемся на первую точку сети
    const network = users
      .flatMap(u => u.networks)
      .find(n => n.id === networkId);
    
    if (network && network.businesses.length > 0) {
      handleBusinessClick(network.businesses[0].id);
    }
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
        <p className="text-gray-600">Управление пользователями и их бизнесами</p>
      </div>

      <div className="space-y-4">
        {users.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-gray-500">
              Пользователи не найдены
            </CardContent>
          </Card>
        ) : (
          users.map((user) => (
            <Card key={user.id} className="overflow-hidden">
              <CardHeader
                className="cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => toggleUser(user.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="p-0 h-6 w-6"
                    >
                      {expandedUsers.has(user.id) ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </Button>
                    <User className="h-5 w-5 text-gray-500" />
                    <div>
                      <CardTitle className="text-lg">
                        {user.name || user.email}
                        {user.is_superadmin && (
                          <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">
                            Админ
                          </span>
                        )}
                      </CardTitle>
                      <p className="text-sm text-gray-500 mt-1">{user.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4 text-sm text-gray-500">
                    <span>
                      <Building2 className="h-4 w-4 inline mr-1" />
                      {user.direct_businesses.length} бизнес(ов)
                    </span>
                    <span>
                      <Network className="h-4 w-4 inline mr-1" />
                      {user.networks.length} сеть(ей)
                    </span>
                  </div>
                </div>
              </CardHeader>

              {expandedUsers.has(user.id) && (
                <CardContent className="pt-0">
                  <div className="space-y-4">
                    {/* Прямые бизнесы (не в сети) */}
                    {user.direct_businesses.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center">
                          <Building2 className="h-4 w-4 mr-2" />
                          Бизнесы
                        </h3>
                        <div className="space-y-2 ml-6">
                          {user.direct_businesses.map((business) => (
                            <div
                              key={business.id}
                              className="p-3 border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 cursor-pointer transition-colors"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleBusinessClick(business.id);
                              }}
                            >
                              <div className="flex items-center justify-between">
                                <div>
                                  <p className="font-medium text-gray-900">{business.name}</p>
                                  {business.description && (
                                    <p className="text-sm text-gray-500 mt-1">{business.description}</p>
                                  )}
                                  {business.address && (
                                    <p className="text-xs text-gray-400 mt-1 flex items-center">
                                      <MapPin className="h-3 w-3 mr-1" />
                                      {business.address}
                                    </p>
                                  )}
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleBusinessClick(business.id);
                                  }}
                                >
                                  Открыть
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Сети */}
                    {user.networks.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center">
                          <Network className="h-4 w-4 mr-2" />
                          Сети
                        </h3>
                        <div className="space-y-2 ml-6">
                          {user.networks.map((network) => (
                            <div
                              key={network.id}
                              className="border border-gray-200 rounded-lg overflow-hidden"
                            >
                              <div
                                className="p-3 bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors flex items-center justify-between"
                                onClick={() => toggleNetwork(network.id)}
                              >
                                <div className="flex items-center space-x-2">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="p-0 h-5 w-5"
                                  >
                                    {expandedNetworks.has(network.id) ? (
                                      <ChevronDown className="h-4 w-4" />
                                    ) : (
                                      <ChevronRight className="h-4 w-4" />
                                    )}
                                  </Button>
                                  <Network className="h-4 w-4 text-gray-500" />
                                  <div>
                                    <p className="font-medium text-gray-900">{network.name}</p>
                                    {network.description && (
                                      <p className="text-xs text-gray-500">{network.description}</p>
                                    )}
                                  </div>
                                </div>
                                <div className="flex items-center space-x-2">
                                  <span className="text-xs text-gray-500">
                                    {network.businesses.length} точка(ек)
                                  </span>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleNetworkClick(network.id);
                                    }}
                                  >
                                    Открыть
                                  </Button>
                                </div>
                              </div>

                              {expandedNetworks.has(network.id) && network.businesses.length > 0 && (
                                <div className="p-3 space-y-2 bg-white">
                                  {network.businesses.map((business) => (
                                    <div
                                      key={business.id}
                                      className="p-3 border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 cursor-pointer transition-colors ml-4"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleBusinessClick(business.id);
                                      }}
                                    >
                                      <div className="flex items-center justify-between">
                                        <div>
                                          <p className="font-medium text-gray-900">{business.name}</p>
                                          {business.description && (
                                            <p className="text-sm text-gray-500 mt-1">{business.description}</p>
                                          )}
                                          {business.address && (
                                            <p className="text-xs text-gray-400 mt-1 flex items-center">
                                              <MapPin className="h-3 w-3 mr-1" />
                                              {business.address}
                                            </p>
                                          )}
                                        </div>
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleBusinessClick(business.id);
                                          }}
                                        >
                                          Открыть
                                        </Button>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {user.direct_businesses.length === 0 && user.networks.length === 0 && (
                      <p className="text-sm text-gray-500 ml-6">Нет бизнесов</p>
                    )}
                  </div>
                </CardContent>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

