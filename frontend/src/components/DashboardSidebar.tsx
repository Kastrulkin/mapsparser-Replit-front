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
  X
} from 'lucide-react';
import { Button } from './ui/button';
import { useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import logo from '../assets/images/logo.png';

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
      label: 'Профиль и бизнес',
      icon: User,
      path: '/dashboard/profile',
    },
    {
      id: 'card',
      label: 'Работа с картами',
      icon: FileText,
      path: '/dashboard/card',
    },
    {
      id: 'progress',
      label: 'Прогресс',
      icon: TrendingUp,
      path: '/dashboard/progress',
    },
    {
      id: 'bookings',
      label: 'Бронирования',
      icon: Calendar,
      path: '/dashboard/bookings',
    },
    {
      id: 'chats',
      label: 'Чаты',
      icon: MessageSquare,
      path: '/dashboard/chats',
    },
    {
      id: 'finance',
      label: 'Финансы',
      icon: DollarSign,
      path: '/dashboard/finance',
    },
    {
      id: 'settings',
      label: 'Настройки',
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
    <div className="h-full flex flex-col bg-white border-r border-gray-200">
      <div className="p-4 border-b border-gray-200">
        <img
          src={logo}
          alt="BeautyBot Logo"
          className="h-12 w-auto"
        />
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          return (
            <Link
              key={item.id}
              to={item.path}
              onClick={handleLinkClick}
              className={`
                flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                ${active
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-50'
                }
              `}
            >
              <Icon className="w-5 h-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
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
              className="fixed inset-0 bg-black/50 z-40 md:hidden"
              onClick={() => {
                setIsOpen(false);
                if (onClose) onClose();
              }}
            />
            <div className="fixed left-0 top-0 bottom-0 w-64 z-50 md:hidden">
              {sidebarContent}
            </div>
          </>
        )}
      </>
    );
  }

  return (
    <div className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 md:left-0">
      {sidebarContent}
    </div>
  );
};

