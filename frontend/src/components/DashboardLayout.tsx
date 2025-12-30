import { Outlet, Navigate } from 'react-router-dom';
import { DashboardSidebar } from './DashboardSidebar';
import { DashboardHeader } from './DashboardHeader';
import { useState, useEffect } from 'react';
import { newAuth } from '../lib/auth_new';
import { BusinessSwitcher } from './BusinessSwitcher';

export const DashboardLayout = () => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [businesses, setBusinesses] = useState<any[]>([]);
  const [currentBusinessId, setCurrentBusinessId] = useState<string | null>(null);
  const [currentBusiness, setCurrentBusiness] = useState<any>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const currentUser = await newAuth.getCurrentUser();
        if (!currentUser) {
          setLoading(false);
          return;
        }

        setUser(currentUser);

        // Проверяем, есть ли бизнес, выбранный из админской страницы
        const adminSelectedBusinessId = localStorage.getItem('admin_selected_business_id');
        if (adminSelectedBusinessId) {
          localStorage.removeItem('admin_selected_business_id');
        }

        // Загружаем бизнесы для суперадмина, владельцев сетей и обычных пользователей
        // API сам определит, какие бизнесы показывать
        try {
          const response = await fetch('/api/auth/me', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
          });
          if (response.ok) {
            const data = await response.json();
            console.log('📊 Загружены данные пользователя:', { 
              is_superadmin: data.user?.is_superadmin, 
              businesses_count: data.businesses?.length || 0 
            });
            // API возвращает businesses для всех типов пользователей:
            // - суперадмин: все бизнесы
            // - владелец сети: только бизнесы из своих сетей
            // - обычный: только свои бизнесы
            if (data.businesses && Array.isArray(data.businesses) && data.businesses.length > 0) {
              console.log('✅ Бизнесы загружены:', data.businesses.length);
              setBusinesses(data.businesses);
              
              // Приоритет: бизнес из админской страницы > сохраненный > первый
              let businessToSelect;
              if (adminSelectedBusinessId) {
                businessToSelect = data.businesses.find((b: any) => b.id === adminSelectedBusinessId);
                if (businessToSelect) {
                  console.log('✅ Выбран бизнес из админской страницы:', businessToSelect.id, businessToSelect.name);
                }
              }
              
              if (!businessToSelect) {
                const savedBusinessId = localStorage.getItem('selectedBusinessId');
                businessToSelect = savedBusinessId
                  ? data.businesses.find((b: any) => b.id === savedBusinessId) || data.businesses[0]
                  : data.businesses[0];
              }

              console.log('✅ Выбран бизнес:', businessToSelect.id, businessToSelect.name);
              setCurrentBusinessId(businessToSelect.id);
              setCurrentBusiness(businessToSelect);
              localStorage.setItem('selectedBusinessId', businessToSelect.id);
            } else {
              console.warn('⚠️ Бизнесы не загружены или список пуст:', data.businesses);
              setBusinesses([]);
              // Если бизнесов нет, не устанавливаем currentBusinessId
              // Пользователь сможет сохранить данные в ClientInfo, указав название бизнеса
            }
          } else {
            console.error('❌ Ошибка загрузки /api/auth/me:', response.status);
          }
        } catch (error) {
          console.error('Ошибка загрузки бизнесов:', error);
        }
      } catch (error) {
        console.error('Ошибка загрузки пользователя:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, []);

  const handleBusinessChange = async (businessId: string) => {
    const business = businesses.find(b => b.id === businessId);
    if (business) {
      setCurrentBusinessId(businessId);
      setCurrentBusiness(business);
      localStorage.setItem('selectedBusinessId', businessId);
    }
  };

  const updateBusiness = (businessId: string, updates: Partial<any>) => {
    const updatedBusinesses = businesses.map(b => 
      b.id === businessId ? { ...b, ...updates } : b
    );
    setBusinesses(updatedBusinesses);
    
    // Обновляем текущий бизнес, если он был изменен
    if (currentBusinessId === businessId) {
      const updatedBusiness = updatedBusinesses.find(b => b.id === businessId);
      if (updatedBusiness) {
        setCurrentBusiness(updatedBusiness);
      }
    }
  };

  const reloadBusinesses = async () => {
    try {
      const response = await fetch('/api/auth/me', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        if (data.businesses && Array.isArray(data.businesses) && data.businesses.length > 0) {
          setBusinesses(data.businesses);
          // Обновляем текущий бизнес, если он был изменен
          if (currentBusinessId) {
            const updatedBusiness = data.businesses.find((b: any) => b.id === currentBusinessId);
            if (updatedBusiness) {
              setCurrentBusiness(updatedBusiness);
            }
          }
        }
      }
    } catch (error) {
      console.error('Ошибка перезагрузки бизнесов:', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <DashboardSidebar isMobile={false} />
      <div className="md:pl-64 flex flex-col min-h-screen">
        <DashboardHeader
          businesses={businesses}
          currentBusinessId={currentBusinessId}
          onBusinessChange={handleBusinessChange}
          isSuperadmin={user.is_superadmin}
          user={user}
        />
        <main className="flex-1 p-6">
          <Outlet context={{ user, currentBusinessId, currentBusiness, businesses, updateBusiness, reloadBusinesses, setBusinesses }} />
        </main>
      </div>
      {/* Mobile sidebar overlay */}
      <DashboardSidebar
        isMobile={true}
        onClose={() => setSidebarOpen(false)}
      />
    </div>
  );
};

