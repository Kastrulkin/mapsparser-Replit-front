import { Link, useLocation } from 'react-router-dom';
import {
  User,
  FileText,
  TrendingUp,
  DollarSign,
  Settings,
  Calendar,
  MessageSquare,
  Menu,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  Handshake
} from 'lucide-react';
import { Button } from './ui/button';
import { useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import logo from '../assets/images/logo.png';
import { cn } from '../lib/utils';
import { DESIGN_TOKENS } from '../lib/design-tokens';
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip';

interface DashboardSidebarProps {
  isMobile?: boolean;
  onClose?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const DashboardSidebar: React.FC<DashboardSidebarProps> = ({
  isMobile = false,
  onClose,
  collapsed = false,
  onToggleCollapse,
}) => {
  const location = useLocation();
  const { t, language } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);

  const menuItems = [
    {
      id: 'profile',
      label: t.dashboard.sidebar.profile,
      icon: User,
      path: '/dashboard/profile',
      tooltip: language === 'ru'
        ? 'Заполните данные бизнеса, добавьте ссылку на карты и запустите первый аудит.'
        : 'Fill in business details, add the map link, and start the first audit.',
    },
    {
      id: 'card',
      label: t.dashboard.sidebar.card,
      icon: FileText,
      path: '/dashboard/card',
      tooltip: language === 'ru'
        ? 'Управляйте данными карточки на картах, услугами, отзывами и запуском обновления.'
        : 'Manage listing data, services, reviews, and start data refresh.',
    },
    {
      id: 'progress',
      label: t.dashboard.sidebar.progress,
      icon: TrendingUp,
      path: '/dashboard/progress',
      tooltip: language === 'ru'
        ? 'Здесь появляется аудит карточки, статистика и история изменений после сбора данных.'
        : 'This is where the listing audit, metrics, and change history appear after data collection.',
    },
    {
      id: 'bookings',
      label: t.dashboard.sidebar.bookings,
      icon: Calendar,
      path: '/dashboard/bookings',
      tooltip: language === 'ru'
        ? 'Смотрите входящие записи и их текущий статус.'
        : 'View incoming bookings and their current status.',
    },
    {
      id: 'chats',
      label: t.dashboard.sidebar.chats,
      icon: MessageSquare,
      path: '/dashboard/chats',
      tooltip: language === 'ru'
        ? 'Здесь собраны клиентские диалоги и ответы по каналам связи.'
        : 'This section contains customer conversations and replies across channels.',
    },
    {
      id: 'partnerships',
      label: t.dashboard.sidebar.partnerships || (language === 'ru' ? 'Поиск партнёров' : 'Partner Search'),
      icon: Handshake,
      path: '/dashboard/partnerships',
      tooltip: language === 'ru'
        ? 'Ищите потенциальных партнёров и работайте с собранными лидами.'
        : 'Find potential partners and work with collected leads.',
    },
    {
      id: 'finance',
      label: t.dashboard.sidebar.finance,
      icon: DollarSign,
      path: '/dashboard/finance',
      tooltip: language === 'ru'
        ? 'Финансовые показатели бизнеса и рабочая экономика.'
        : 'Business financial metrics and operating economics.',
    },
    {
      id: 'ai-chat-promotion',
      label: t.dashboard.sidebar.aiChatPromotion,
      icon: Sparkles,
      path: '/dashboard/ai-chat-promotion',
      tooltip: language === 'ru'
        ? 'Настройка AI-коммуникаций и сценариев продвижения.'
        : 'Configure AI communication and promotion workflows.',
    },
    {
      id: 'settings',
      label: t.dashboard.sidebar.settings,
      icon: Settings,
      path: '/dashboard/settings',
      tooltip: language === 'ru'
        ? 'Общие настройки аккаунта, интеграций и рабочих режимов.'
        : 'General account, integration, and workflow settings.',
    },
  ];

  const handleLinkClick = () => {
    if (isMobile && onClose) {
      onClose();
    }
  };

  const isActive = (path: string) => {
    if (path === '/dashboard/progress') {
      return location.pathname === '/dashboard' || location.pathname === path;
    }
    return location.pathname === path;
  };

  const sidebarContent = (
    <div className={cn(
      "h-full flex flex-col border-r border-slate-200/70 transition-all duration-300",
      "bg-white/86 backdrop-blur-xl supports-[backdrop-filter]:bg-white/78",
      "shadow-[8px_0_32px_-20px_rgba(15,23,42,0.18)]"
    )}>
      {/* Logo Area */}
      <div className={cn("border-b border-slate-100", collapsed && !isMobile ? "px-3 py-5" : "p-6")}>
        <div className={cn("flex items-center gap-3", collapsed && !isMobile ? "justify-center" : "justify-between")}>
          <Link
            to="/dashboard/profile"
            onClick={handleLinkClick}
            className={cn(
              "flex min-w-0 items-center gap-3 rounded-xl outline-none ring-blue-500/30 transition focus-visible:ring-2",
              collapsed && !isMobile ? "h-12 w-12 justify-center" : "overflow-hidden"
            )}
            aria-label="LocalOS"
          >
            {collapsed && !isMobile ? (
                <span className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
                  <span className="absolute inset-0 rounded-2xl bg-slate-900/5 blur-md" />
                  <img
                  src="/favicon.svg"
                  alt=""
                  aria-hidden="true"
                  className="relative z-10 h-8 w-8"
                />
              </span>
            ) : (
              <>
                <span className="relative flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
                  <span className="absolute inset-0 bg-slate-900/5 blur-md" />
                  <img
                    src={logo}
                    alt=""
                    aria-hidden="true"
                    className="relative z-10 h-11 w-11 object-cover object-top drop-shadow-sm transition-transform duration-300 hover:scale-105"
                  />
                </span>
                <span className="hidden truncate text-xl font-semibold tracking-tight text-slate-950 lg:block">
                  LocalOS
                </span>
              </>
            )}
          </Link>
          {!isMobile && onToggleCollapse ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={cn("shrink-0", collapsed && "hidden")}
              onClick={onToggleCollapse}
              aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
            >
              {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </Button>
          ) : null}
        </div>
        {!isMobile && collapsed && onToggleCollapse ? (
          <div className="mt-3 flex justify-center">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onToggleCollapse}
              aria-label="Развернуть меню"
            >
              <PanelLeftOpen className="h-4 w-4" />
            </Button>
          </div>
        ) : null}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1.5 overflow-y-auto p-4 custom-scrollbar">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          return (
            <Tooltip key={item.id}>
              <TooltipTrigger asChild>
                <Link
                  to={item.path}
                  onClick={handleLinkClick}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-xl text-sm font-medium transition-all duration-300",
                    collapsed && !isMobile ? "justify-center px-2 py-3 hover:translate-x-0" : "px-4 py-3",
                    active
                      ? "bg-slate-900 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100/90 hover:text-slate-950"
                  )}
                >
                  <div className={cn(
                    "p-2 rounded-lg transition-colors duration-300",
                    active ? "bg-white/14 text-white" : "bg-transparent text-slate-500 group-hover:bg-white group-hover:text-slate-700"
                  )}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className={cn("tracking-wide", collapsed && !isMobile && "hidden")}>{item.label}</span>

                  {active && (
                    <div className="absolute right-3 top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full bg-white/90" />
                  )}
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right" className="max-w-xs text-xs leading-5">
                {item.tooltip}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>

      <div className={cn(
        "m-4 rounded-2xl border border-slate-200 bg-slate-50/90 p-4",
        collapsed && !isMobile && "mx-3 px-2 py-3"
      )}>
        <div className="mb-2 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-slate-700" />
          <span className={cn("text-xs font-semibold uppercase tracking-[0.16em] text-slate-700", collapsed && !isMobile && "hidden")}>LocalOS</span>
        </div>
        <p className={cn("text-xs leading-relaxed text-slate-500", collapsed && !isMobile && "hidden")}>
          {t.dashboard.sidebar.greeting}
        </p>
      </div>
    </div>
  );

  if (isMobile) {
    return (
      <>
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </Button>
        {isOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden transition-opacity duration-300"
              onClick={() => {
                setIsOpen(false);
                if (onClose) onClose();
              }}
            />
            <div className="fixed left-0 top-0 bottom-0 w-72 z-50 md:hidden animate-in slide-in-from-left duration-300">
              {sidebarContent}
            </div>
          </>
        )}
      </>
    );
  }

  return (
    <div className={cn("hidden md:flex md:flex-col md:fixed md:inset-y-0 md:left-0 z-30", collapsed ? "md:w-24" : "md:w-72")}>
      {sidebarContent}
    </div>
  );
};
