import { Outlet, Navigate, useLocation } from 'react-router-dom';
import { DashboardSidebar } from './DashboardSidebar';
import { DashboardHeader } from './DashboardHeader';
import { useState, useEffect, useCallback } from 'react';
import { newAuth, type User } from '../lib/auth_new';
import { getCapabilityAccessForBusiness, type SubscriptionCapability } from '../lib/subscriptionAccess';
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
  network_id?: string | null;
  network_name?: string | null;
  web_tracking_available?: boolean;
  creator_promotion_available?: boolean;
};

export type ControlScope = {
  kind: 'business' | 'network';
  id: string;
  name: string;
};

type PaidDashboardSection = { path: string; capability: SubscriptionCapability; title: string; hint: string; previewItems: string[]; nextAction: string };

const paidDashboardSections: PaidDashboardSection[] = [
  { path: '/dashboard/card', capability: 'maps', title: 'Работа с картами входит в тариф «Карты»', hint: 'Аудит, услуги, отзывы, фото и новости для карточки открываются на тарифе «Карты».', previewItems: ['Проверка заполненности и свежести карточки', 'Сводка отзывов и услуг', 'План первых улучшений'], nextAction: 'Добавьте ссылку на карты, чтобы после оплаты сразу запустить аудит.' },
  { path: '/dashboard/web-analytics', capability: 'web_analytics', title: 'Аналитика сайта входит в тариф «Карты»', hint: 'Установите tracker-скрипт и получите первые события поведения пользователей.', previewItems: ['Посещения и источники трафика', 'Звонки, формы и переходы в мессенджеры', 'Статус подключения tracker-скрипта'], nextAction: 'После подключения главным шагом будет установка скрипта на сайт.' },
  { path: '/dashboard/finance', capability: 'finance', title: 'Финансы входят в тариф «Управление»', hint: 'Импорт, показатели и рекомендации по выручке доступны на старшем тарифе.', previewItems: ['Выручка, расходы и маржа', 'Динамика по периодам', 'Точки, где бизнес теряет деньги'], nextAction: 'После оплаты вы вернётесь сюда и загрузите первые продажи.' },
  { path: '/dashboard/average-ticket', capability: 'average_ticket', title: 'Средний чек входит в тариф «Управление»', hint: 'Пакеты услуг и сценарии допродажи доступны на старшем тарифе.', previewItems: ['Пары основных и дополнительных услуг', 'Пакеты с прозрачной выгодой', 'Метрики роста среднего чека'], nextAction: 'После оплаты LocalOS соберёт первую матрицу из текущих услуг.' },
  { path: '/dashboard/content', capability: 'social_content', title: 'Контент для соцсетей входит в тариф «Управление»', hint: 'Контент-планы, адаптация под каналы и контролируемое размещение доступны на старшем тарифе. Новости для карточек уже доступны в разделе «Карты».', previewItems: ['Календарь публикаций по каналам', 'Черновики в формате каждой площадки', 'Проверка и ручное подтверждение размещения'], nextAction: 'После оплаты вы вернётесь к контент-плану и выберете первый канал. Новости для карт можно готовить уже сейчас в разделе карточки.' },
  { path: '/dashboard/ai-chat-promotion', capability: 'ai_visibility', title: 'AI-видимость входит в тариф «Привлечение»', hint: 'Проверки и рекомендации по AI-выдаче входят в контур привлечения.', previewItems: ['Проверка упоминаний бизнеса', 'Недостающие факты для AI-ответов', 'План роста видимости'], nextAction: 'После оплаты вернём вас к первой проверке AI-выдачи.' },
  { path: '/dashboard/influencers/operations', capability: 'influencers', title: 'Полная работа с инфлюенсерами входит в тариф «Привлечение»', hint: 'Откроются сообщения, каналы, размещения и подтверждённая отправка.', previewItems: ['Подбор локальных авторов', 'Предложение и черновики сообщений', 'Статусы размещений'], nextAction: 'Откройте тариф, чтобы продолжить работу с выбранными авторами.' },
  { path: '/dashboard/operator', capability: 'operator', title: 'Оператор входит в тариф «Управление»', hint: 'Единый рабочий центр задач и запусков доступен на старшем тарифе.', previewItems: ['Единая очередь задач', 'Черновики с ручным подтверждением', 'Журнал запусков и ошибок'], nextAction: 'После оплаты Оператор покажет первую задачу, которая требует вашего решения.' },
  { path: '/dashboard/telegram-radar', capability: 'telegram_radar', title: 'Telegram-радар входит в тариф «Карты»', hint: 'Сбор отраслевых публикаций доступен вместе с работой над карточкой.', previewItems: ['Темы, которые обсуждают в вашей отрасли', 'Новые возможности и риски', 'Краткая ежедневная сводка'], nextAction: 'После оплаты сохраним ваши ключевые темы и запустим сбор.' },
  { path: '/dashboard/agents', capability: 'agents', title: 'ИИ-сотрудники входят в тариф «Управление»', hint: 'Настройка и запуск автоматизаций доступны на старшем тарифе.', previewItems: ['Задачи по расписанию', 'Результаты и статусы', 'Ручные подтверждения важных шагов'], nextAction: 'После оплаты выберите первую повторяющуюся задачу для настройки.' },
  { path: '/dashboard/chats', capability: 'chats', title: 'Рабочие чаты входят в тариф «Управление»', hint: 'Подключение и обработка сообщений доступны на старшем тарифе.', previewItems: ['Входящие диалоги в одной очереди', 'Черновики ответов', 'Статус канала и ручная отправка'], nextAction: 'После оплаты подключите первый канал и проверьте тестовый диалог.' },
];

const LockedSectionPreview = ({ section, currentTierName, paywallHref }: { section: PaidDashboardSection; currentTierName: string; paywallHref: string }) => (
  <section className="mx-auto max-w-4xl py-4 sm:py-8" aria-labelledby="locked-section-title">
    <div className="rounded-[28px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_2px_5px_rgba(15,23,42,0.05),0_18px_48px_rgba(15,23,42,0.08)] sm:p-8">
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
        <span className="rounded-full bg-slate-100 px-3 py-1.5">Сейчас: {currentTierName}</span>
        <span className="rounded-full bg-amber-50 px-3 py-1.5 text-amber-800">Откроется после повышения</span>
      </div>
      <h1 id="locked-section-title" className="mt-5 max-w-2xl text-balance text-2xl font-bold tracking-[-0.025em] text-slate-950 sm:text-3xl">{section.title}</h1>
      <p className="mt-3 max-w-2xl text-pretty text-sm leading-6 text-slate-600 sm:text-base">{section.hint}</p>

      <div className="mt-7 grid gap-3 sm:grid-cols-3" aria-label="Пример результата">
        {section.previewItems.map((item, index) => (
          <div key={item} className="rounded-2xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.05)]">
            <span className="tabular-nums text-xs font-bold text-slate-400">0{index + 1}</span>
            <p className="mt-2 text-pretty text-sm font-semibold leading-5 text-slate-800">{item}</p>
          </div>
        ))}
      </div>

      <div className="relative mt-4 overflow-hidden rounded-2xl bg-slate-50 p-4" aria-hidden="true">
        <div className="space-y-3 opacity-45 blur-[3px]">
          <div className="h-4 w-2/3 rounded-full bg-slate-300" />
          <div className="h-16 rounded-xl bg-slate-200" />
          <div className="h-16 rounded-xl bg-slate-200" />
        </div>
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent to-white/80" />
      </div>

      <div className="mt-6 rounded-2xl bg-slate-950 p-5 text-white sm:flex sm:items-center sm:justify-between sm:gap-6">
        <div>
          <p className="text-sm font-semibold">Следующий шаг</p>
          <p className="mt-1 max-w-xl text-pretty text-sm leading-6 text-slate-300">{section.nextAction}</p>
        </div>
        <a href={paywallHref} className="mt-4 inline-flex min-h-11 shrink-0 items-center justify-center rounded-xl bg-white px-4 text-sm font-bold text-slate-950 transition-[background-color,scale] duration-150 hover:bg-slate-100 active:scale-[0.96] sm:mt-0">
          Выбрать подходящий тариф
        </a>
      </div>
    </div>
  </section>
);

export const DashboardLayout = () => {
  const location = useLocation();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [businesses, setBusinesses] = useState<DashboardBusiness[]>([]);
  const [currentBusinessId, setCurrentBusinessId] = useState<string | null>(null);
  const [currentBusiness, setCurrentBusiness] = useState<DashboardBusiness | null>(null);
  const [controlScope, setControlScope] = useState<ControlScope | null>(null);
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
          const savedScopeValue = localStorage.getItem(currentUser.demo_mode ? 'demo_dashboard_control_scope' : 'dashboard_control_scope');
          let restoredScope: ControlScope = { kind: 'business', id: businessToSelect.id, name: businessToSelect.name };
          if (savedScopeValue) {
            try {
              const parsed = JSON.parse(savedScopeValue);
              if (parsed?.kind === 'network' && parsed?.id && businessToSelect.network_id === parsed.id) {
                restoredScope = { kind: 'network', id: parsed.id, name: parsed.name || businessToSelect.network_name || 'Сеть' };
              }
            } catch {
              localStorage.removeItem(currentUser.demo_mode ? 'demo_dashboard_control_scope' : 'dashboard_control_scope');
            }
          }
          setControlScope(restoredScope);
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

  useEffect(() => {
    if (typeof window === 'undefined' || location.pathname === '/dashboard/profile') return;
    window.sessionStorage.setItem('localos_checkout_return_to', `${location.pathname}${location.search}`);
  }, [location.pathname, location.search]);

  const handleBusinessChange = async (businessId: string) => {
    const business = businesses.find(b => b.id === businessId);
    if (business) {
      setCurrentBusinessId(businessId);
      setCurrentBusiness(business);
      const nextScope: ControlScope = { kind: 'business', id: business.id, name: business.name };
      setControlScope(nextScope);
      localStorage.setItem(user?.demo_mode ? 'demo_dashboard_control_scope' : 'dashboard_control_scope', JSON.stringify(nextScope));
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

  const selectControlScope = (nextScope: ControlScope) => {
    setControlScope(nextScope);
    localStorage.setItem(user?.demo_mode ? 'demo_dashboard_control_scope' : 'dashboard_control_scope', JSON.stringify(nextScope));
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

  const lockedPaidSection = paidDashboardSections.find((section) => (
    location.pathname === section.path || location.pathname.startsWith(`${section.path}/`)
  ));
  const ownsBlockAccess = location.pathname === '/dashboard/influencers'
    || location.pathname === '/dashboard/partnerships'
    || location.pathname === '/dashboard/promotion/partnerships'
    || location.pathname === '/dashboard/promotion';
  const sectionAccess = lockedPaidSection ? getCapabilityAccessForBusiness(currentBusiness, lockedPaidSection.capability) : null;
  const shouldLockPaidSection = Boolean(lockedPaidSection && !ownsBlockAccess && !user.demo_mode && !user.is_superadmin && !sectionAccess?.allowed);
  const paywallReturnTo = `${location.pathname}${location.search}`;
  const paywallHref = `/dashboard/profile?focus=subscription&tier=${encodeURIComponent(sectionAccess?.requiredTier || 'starter')}&return_to=${encodeURIComponent(paywallReturnTo)}#subscription`;

  return (
    <GuidedTourProvider user={user}>
      <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.06),_transparent_30%),linear-gradient(180deg,_#f8fafc_0%,_#f6f8fc_100%)] text-slate-900">
      <DashboardSidebar
        isMobile={false}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
        webTrackingAvailable={currentBusiness?.web_tracking_available === true}
      />
      <div className={`flex flex-col min-h-screen transition-all duration-300 ${sidebarCollapsed ? 'md:pl-24' : 'md:pl-72'}`}>
        <DashboardHeader
          businesses={businesses}
          currentBusinessId={currentBusinessId}
          currentBusiness={currentBusiness}
          onBusinessChange={handleBusinessChange}
          controlScope={controlScope}
          onControlScopeChange={selectControlScope}
          isSuperadmin={user.is_superadmin}
          user={user}
        />
        {user.demo_mode ? <DemoModeBanner /> : null}
        <main className="flex-1 p-3 sm:p-4 lg:p-6">
          <div className="mx-auto w-full max-w-[1600px]">
            <div className="relative min-h-[60vh]">
              {shouldLockPaidSection && lockedPaidSection ? (
                <LockedSectionPreview
                  section={lockedPaidSection}
                  currentTierName={sectionAccess?.tierName || 'Без тарифа'}
                  paywallHref={paywallHref}
                />
              ) : (
                <Outlet context={{ user, demoMode: Boolean(user.demo_mode), currentBusinessId, currentBusiness, businesses, controlScope, onControlScopeChange: selectControlScope, updateBusiness, reloadBusinesses, setBusinesses, onBusinessChange: handleBusinessChange }} />
              )}
            </div>
          </div>
        </main>
      </div>
      {/* Mobile sidebar overlay */}
      <DashboardSidebar
        isMobile={true}
        onClose={() => setSidebarOpen(false)}
        webTrackingAvailable={currentBusiness?.web_tracking_available === true}
      />
      </div>
    </GuidedTourProvider>
  );
};
