import { Outlet, Navigate } from 'react-router-dom';
import { DashboardSidebar } from './DashboardSidebar';
import { DashboardHeader } from './DashboardHeader';
import { useState, useEffect, useCallback } from 'react';
import { newAuth, type User } from '../lib/auth_new';

type DashboardBusiness = {
  id: string;
  name: string;
  description?: string;
  moderation_status?: string;
  entity_group?: string;
  is_lead_business?: boolean;
};

export const DashboardLayout = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [businesses, setBusinesses] = useState<DashboardBusiness[]>([]);
  const [currentBusinessId, setCurrentBusinessId] = useState<string | null>(null);
  const [currentBusiness, setCurrentBusiness] = useState<DashboardBusiness | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return window.localStorage.getItem('dashboard_sidebar_collapsed') === 'true';
  });
  const isLeadBusiness = useCallback((business: DashboardBusiness) => {
    const moderationStatus = String(business?.moderation_status || '').trim().toLowerCase();
    const entityGroup = String(business?.entity_group || '').trim().toLowerCase();
    const description = String(business?.description || '').trim().toLowerCase();
    return (
      business?.is_lead_business === true ||
      moderationStatus === 'lead_outreach' ||
      entityGroup === 'lead' ||
      description.startsWith('lead shadow business for outreach lead')
    );
  }, []);
  const filterOutLeads = useCallback((items: DashboardBusiness[]) => (items || []).filter((business) => !isLeadBusiness(business)), [isLeadBusiness]);

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

        // Используем данные, полученные из newAuth.getCurrentUser(), вместо повторного запроса
        const businessesData = filterOutLeads(currentUser.businesses || []);

        if (businessesData.length > 0) {
          setBusinesses(businessesData);

          // Приоритет: бизнес из админской страницы > сохраненный > первый
          let businessToSelect;
          if (adminSelectedBusinessId) {
            businessToSelect = businessesData.find((business) => business.id === adminSelectedBusinessId);
          }

          if (!businessToSelect) {
            const savedBusinessId = localStorage.getItem('selectedBusinessId');
            businessToSelect = savedBusinessId
              ? businessesData.find((business) => business.id === savedBusinessId) || businessesData[0]
              : businessesData[0];
          }

          setCurrentBusinessId(businessToSelect.id);
          setCurrentBusiness(businessToSelect);
          localStorage.setItem('selectedBusinessId', businessToSelect.id);
        } else {
          setBusinesses([]);
        }
      } catch (error) {
        console.error('Ошибка загрузки пользователя:', error);
      } finally {
        setLoading(false);
      }
    };

    void fetchUser();
  }, [filterOutLeads]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem('dashboard_sidebar_collapsed', sidebarCollapsed ? 'true' : 'false');
  }, [sidebarCollapsed]);

  const handleBusinessChange = async (businessId: string) => {
    const business = businesses.find(b => b.id === businessId);
    if (business) {
      setCurrentBusinessId(businessId);
      setCurrentBusiness(business);
      localStorage.setItem('selectedBusinessId', businessId);
    }
  };

  const updateBusiness = (businessId: string, updates: Partial<DashboardBusiness>) => {
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
      const data = await newAuth.makeRequest('/auth/me') as { businesses?: DashboardBusiness[] };

      const businessesData = filterOutLeads(data.businesses || []);
      if (Array.isArray(businessesData) && businessesData.length > 0) {
        setBusinesses(businessesData);
        // Обновляем текущий бизнес, если он был изменен
        if (currentBusinessId) {
          const updatedBusiness = businessesData.find((business) => business.id === currentBusinessId);
          if (updatedBusiness) {
            setCurrentBusiness(updatedBusiness);
          }
        }
      } else {
        setBusinesses([]);
      }
    } catch (error) {
      console.error('Ошибка перезагрузки бизнесов:', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.08),_transparent_32%),linear-gradient(180deg,_#f8fafc_0%,_#eef2ff_100%)]">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 animate-spin rounded-full border-b-2 border-slate-900"></div>
          <p className="mt-4 text-sm font-medium text-slate-600">Загрузка кабинета...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.06),_transparent_30%),linear-gradient(180deg,_#f8fafc_0%,_#f6f8fc_100%)] text-slate-900">
      <DashboardSidebar isMobile={false} collapsed={sidebarCollapsed} onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)} />
      <div className={`flex flex-col min-h-screen transition-all duration-300 ${sidebarCollapsed ? 'md:pl-24' : 'md:pl-72'}`}>
        <DashboardHeader
          businesses={businesses}
          currentBusinessId={currentBusinessId}
          currentBusiness={currentBusiness}
          onBusinessChange={handleBusinessChange}
          isSuperadmin={user.is_superadmin}
          user={user}
        />
        <main className="flex-1 p-3 sm:p-4 lg:p-6">
          <div className="mx-auto w-full max-w-[1600px]">
            <Outlet context={{ user, currentBusinessId, currentBusiness, businesses, updateBusiness, reloadBusinesses, setBusinesses, onBusinessChange: handleBusinessChange }} />
          </div>
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
