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
  Sparkles
} from 'lucide-react';
import { Button } from './ui/button';
import { useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import logo from '../assets/images/logo.png';
import { cn } from '../lib/utils';
import { DESIGN_TOKENS } from '../lib/design-tokens';

interface DashboardSidebarProps {
  isMobile?: boolean;
  onClose?: () => void;
}

export const DashboardSidebar: React.FC<DashboardSidebarProps> = ({
  isMobile = false,
  onClose
}) => {
  const location = useLocation();
  const { t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);

  const menuItems = [
    {
      id: 'profile',
      label: t.dashboard.sidebar.profile,
      icon: User,
      path: '/dashboard/profile',
    },
    {
      id: 'card',
      label: t.dashboard.sidebar.card,
      icon: FileText,
      path: '/dashboard/card',
    },
    {
      id: 'progress',
      label: t.dashboard.sidebar.progress,
      icon: TrendingUp,
      path: '/dashboard/progress',
    },
    {
      id: 'bookings',
      label: t.dashboard.sidebar.bookings,
      icon: Calendar,
      path: '/dashboard/bookings',
    },
    {
      id: 'chats',
      label: t.dashboard.sidebar.chats,
      icon: MessageSquare,
      path: '/dashboard/chats',
    },
    {
      id: 'finance',
      label: t.dashboard.sidebar.finance,
      icon: DollarSign,
      path: '/dashboard/finance',
    },
    {
      id: 'ai-chat-promotion',
      label: t.dashboard.sidebar.aiChatPromotion,
      icon: Sparkles,
      path: '/dashboard/ai-chat-promotion',
    },
    {
      id: 'settings',
      label: t.dashboard.sidebar.settings,
      icon: Settings,
      path: '/dashboard/settings',
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
      "h-full flex flex-col border-r border-white/20 transition-all duration-300",
      "bg-white/70 backdrop-blur-xl supports-[backdrop-filter]:bg-white/60", // More translucent glass
      "shadow-[4px_0_24px_-4px_rgba(0,0,0,0.05)]" // Subtle shadow
    )}>
      {/* Logo Area */}
      <div className="p-6 border-b border-gray-100/50 backdrop-blur-lg">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full" />
            <img
              src={logo}
              alt="Local OS"
              className="h-10 w-auto relative z-10 drop-shadow-sm transition-transform hover:scale-105 duration-300"
            />
          </div>
          <span className="font-bold text-xl bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 hidden lg:block">
            Local OS
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1.5 overflow-y-auto custom-scrollbar">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          return (
            <Link
              key={item.id}
              to={item.path}
              onClick={handleLinkClick}
              className={cn(
                "group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-300",
                "hover:translate-x-1",
                active
                  ? "bg-gradient-to-r from-blue-600/10 to-blue-500/5 text-blue-700 shadow-sm ring-1 ring-blue-600/20"
                  : "text-gray-600 hover:bg-gray-50/80 hover:text-gray-900"
              )}
            >
              <div className={cn(
                "p-2 rounded-lg transition-colors duration-300",
                active ? "bg-white shadow-sm text-blue-600" : "bg-transparent text-gray-500 group-hover:text-gray-700 group-hover:bg-gray-100"
              )}>
                <Icon className={cn("w-5 h-5", active && "animate-pulse-slow")} />
              </div>
              <span className="tracking-wide">{item.label}</span>

              {/* Active Indicator Line */}
              {active && (
                <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-blue-600 rounded-l-full shadow-[0_0_8px_rgba(37,99,235,0.5)]" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Pro Badge (Decorative) */}
      <div className="p-4 m-4 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/20">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="w-4 h-4 text-yellow-200" />
          <span className="text-xs font-bold uppercase tracking-wider text-white/90">Pro Max</span>
        </div>
        <p className="text-xs text-white/80 leading-relaxed">
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
    <div className="hidden md:flex md:w-72 md:flex-col md:fixed md:inset-y-0 md:left-0 z-30">
      {sidebarContent}
    </div>
  );
};

