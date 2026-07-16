import { Outlet, Navigate, useLocation } from 'react-router-dom';
import { DashboardSidebar } from './DashboardSidebar';
import { DashboardHeader } from './DashboardHeader';
import { useState, useEffect, useCallback } from 'react';
import { newAuth, type User } from '../lib/auth_new';
import { getAutomationAccessForBusiness } from '../lib/subscriptionAccess';
import { DemoModeBanner, GuidedTourProvider } from './guided-tour/GuidedTourProvider';

type DashboardBusiness = {
  id: string;
  name: string;
  description?: string;
  moderation_status?: string;
  entity_group?: string;
  is_lead_business?: boolean;
  subscription_tier?: string | null;
  subscription_status?: string | null;
  subscription_ends_at?: string | null;
};

const paidDashboardSections = [
  { path: '/dashboard/content', title: 'Контент доступен после оплаты', hint: 'Можно посмотреть раздел, но генерация публикаций и контент-планов включается только на платном тарифе.' },
  { path: '/dashboard/progress', title: 'Прогресс и аналитика доступны после оплаты', hint: 'Аудит, динамика и рекомендации появятся после подключения тарифа.' },
  { path: '/dashboard/finance', title: 'Финансы доступны после оплаты', hint: 'Импорт, разбор показателей и рекомендации по выручке включаются на платном тарифе.' },
  { path: '/dashboard/average-ticket', title: 'Средний чек доступен после оплаты', hint: 'Расчёты и рекомендации по среднему чеку включаются на платном тарифе.' },
  { path: '/dashboard/ai-chat-promotion', title: 'Продвижение в AI-чатах доступно после оплаты', hint: 'Проверки и рекомендации по AI-выдаче включаются на платном тарифе.' },
  { path: '/dashboard/partnerships', title: 'Поиск партнёров доступен после оплаты', hint: 'Подбор, подготовка и ведение партнёрских контактов включаются на платном тарифе.' },
  { path: '/dashboard/operator', title: 'Оператор доступен после оплаты', hint: 'Единый рабочий центр задач и запусков включается на платном тарифе.' },
  { path: '/dashboard/telegram-radar', title: 'Telegram-радар доступен после оплаты', hint: 'Мониторинг Telegram и обработка найденных сигналов включаются на платном тарифе.' },
  { path: '/dashboard/agents', title: 'Агенты доступны после оплаты', hint: 'Настройка и запуск автоматизаций включаются на платном тарифе.' },
  { path: '/dashboard/bookings', title: 'Бронирования доступны после оплаты', hint: 'Работа с заявками и расписанием включается на платном тарифе.' },
  { path: '/dashboard/chats', title: 'Чаты доступны после оплаты', hint: 'Подключение и обработка сообщений включаются на платном тарифе.' },
  { path: '/dashboard/network', title: 'Сеть доступна после оплаты', hint: 'Сводка по нескольким точкам и сетевые сценарии включаются на платном тарифе.' },
];

export const DashboardLayout = () => {
  const location = useLocation();
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
        const adminSelectedBusinessId = currentUser.demo_mode
          ? null
          : localStorage.getItem('admin_selected_business_id');
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
            const businessStorageKey = currentUser.demo_mode ? 'demo_selectedBusinessId' : 'selectedBusinessId';
            const savedBusinessId = localStorage.getItem(businessStorageKey);
            businessToSelect = savedBusinessId
              ? businessesData.find((business) => business.id === savedBusinessId) || businessesData[0]
              : businessesData[0];
          }

          setCurrentBusinessId(businessToSelect.id);
          setCurrentBusiness(businessToSelect);
          localStorage.setItem(currentUser.demo_mode ? 'demo_selectedBusinessId' : 'selectedBusinessId', businessToSelect.id);
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
      localStorage.setItem(user?.demo_mode ? 'demo_selectedBusinessId' : 'selectedBusinessId', businessId);
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

  const automationAccess = getAutomationAccessForBusiness(currentBusiness);
  const lockedPaidSection = paidDashboardSections.find((section) => (
    location.pathname === section.path || location.pathname.startsWith(`${section.path}/`)
  ));
  const shouldBlurPaidSection = Boolean(lockedPaidSection && !user.demo_mode && !user.is_superadmin && !automationAccess.automationAllowed);

  return (
    <GuidedTourProvider user={user}>
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
        {user.demo_mode ? <DemoModeBanner /> : null}
        <main className="flex-1 p-3 sm:p-4 lg:p-6">
          <div className="mx-auto w-full max-w-[1600px]">
            <div className="relative min-h-[60vh]">
              <div className={shouldBlurPaidSection ? 'pointer-events-none select-none blur-sm' : undefined} aria-hidden={shouldBlurPaidSection || undefined}>
                <Outlet context={{ user, demoMode: Boolean(user.demo_mode), currentBusinessId, currentBusiness, businesses, updateBusiness, reloadBusinesses, setBusinesses, onBusinessChange: handleBusinessChange }} />
              </div>
              {shouldBlurPaidSection && lockedPaidSection ? (
                <div className="absolute inset-0 z-20 flex items-start justify-center rounded-2xl bg-slate-50/55 px-4 py-16 backdrop-blur-[2px]">
                  <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white/95 p-6 text-center shadow-xl shadow-slate-900/10">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-lg font-semibold text-white">
                      ₽
                    </div>
                    <h2 className="mt-4 text-xl font-bold text-slate-950">{lockedPaidSection.title}</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{lockedPaidSection.hint}</p>
                    <p className="mt-3 text-sm leading-6 text-slate-500">
                      Сейчас можно заполнить профиль, добавить ссылки на компанию и посмотреть кабинет. Платные действия не запускаются автоматически.
                    </p>
                    <div className="mt-5 flex flex-col justify-center gap-3 sm:flex-row">
                      <a
                        href="/dashboard/profile?onboarding=1"
                        className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-50"
                      >
                        Заполнить профиль
                      </a>
                      <a
                        href="/dashboard/profile?focus=subscription#subscription"
                        className="inline-flex items-center justify-center rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-slate-800"
                      >
                        Выбрать тариф
                      </a>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </main>
      </div>
      {/* Mobile sidebar overlay */}
      <DashboardSidebar
        isMobile={true}
        onClose={() => setSidebarOpen(false)}
      />
      </div>
    </GuidedTourProvider>
  );
};
