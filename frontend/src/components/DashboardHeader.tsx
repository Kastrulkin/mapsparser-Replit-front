import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from './ui/button';
import { newAuth } from '../lib/auth_new';
import { LanguageSwitcher } from './LanguageSwitcher';
import { useCurrency } from '../contexts/CurrencyContext';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { BusinessSwitcher } from './BusinessSwitcher';
import { NetworkLocationsSwitcher } from './NetworkLocationsSwitcher';
import { LogOut, LogIn, Settings } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';

interface DashboardHeaderProps {
  businesses?: any[];
  currentBusinessId?: string | null;
  onBusinessChange?: (businessId: string) => void;
  isSuperadmin?: boolean;
  user?: any;
  currentBusiness?: any;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  businesses = [],
  currentBusinessId,
  onBusinessChange,
  isSuperadmin = false,
  user: userProp,
  currentBusiness,
}) => {
  const { currency, setCurrency } = useCurrency();
  const navigate = useNavigate();
  const [showLoginDialog, setShowLoginDialog] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);

  useEffect(() => {
    const checkAuth = async () => {
      if (userProp) {
        setIsAuthenticated(true);
        setCurrentUser(userProp);
        return;
      }
      try {
        const user = await newAuth.getCurrentUser();
        setIsAuthenticated(!!user);
        setCurrentUser(user);
      } catch (error) {
        setIsAuthenticated(false);
        setCurrentUser(null);
      }
    };
    checkAuth();
  }, [userProp]);

  const handleLogout = async () => {
    try {
      await newAuth.signOut();
      localStorage.clear();
      window.location.href = '/login';
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  const handleLoginClick = () => {
    setShowLoginDialog(true);
  };

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="flex items-center justify-between px-4 py-3">
        {/* Левая сторона: Суперадмин dropdown */}
        <div className="flex items-center gap-2">
          {isSuperadmin && (
            <>
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Суперадмин</span>
              {/* DEBUG: Показывать network_id прямо в интерфейсе */}
              <span className="text-[10px] text-red-500 font-mono border border-red-200 px-1 rounded bg-red-50">
                NetID: {currentBusiness?.network_id ? currentBusiness.network_id.substring(0, 8) + '...' : 'NULL'}
              </span>
              <BusinessSwitcher
                businesses={businesses}
                currentBusinessId={currentBusinessId || undefined}
                onBusinessChange={onBusinessChange || (() => { })}
                isSuperadmin={isSuperadmin}
              />
            </>
          )}
        </div>

        {/* Правая сторона: Network Locations + остальное */}
        <div className="flex items-center gap-3">
          {/* Network Locations Switcher для владельцев сетей */}
          {(() => {
            console.log('🏗️ DashboardHeader render:', {
              hasCurrentBusiness: !!currentBusiness,
              networkId: currentBusiness?.network_id,
              name: currentBusiness?.name
            });
            return null;
          })()}
          {currentBusiness?.network_id && onBusinessChange && (
            <NetworkLocationsSwitcher
              currentBusinessId={currentBusinessId || undefined}
              onLocationChange={onBusinessChange}
            />
          )}

          {/* Пункт меню "Базич" для суперадмина demyanovap@yandex.ru */}
          {currentUser?.email === 'demyanovap@yandex.ru' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/dashboard/bazich')}
              className="flex items-center gap-2"
            >
              <Settings className="w-4 h-4" />
              <span className="hidden sm:inline">Базич</span>
            </Button>
          )}

          {isAuthenticated && currentUser && (
            <Link
              to="/dashboard/profile"
              className="text-sm font-medium text-gray-700 hover:text-blue-600 mr-2 transition-colors border-b border-transparent hover:border-blue-600"
            >
              {currentUser.email}
            </Link>
          )}

          <LanguageSwitcher />

          <Select value={currency} onValueChange={(value) => setCurrency(value as 'RUB' | 'USD' | 'EUR')}>
            <SelectTrigger className="w-12">
              <span className="text-base font-medium">
                {currency === 'RUB' ? '₽' : currency === 'USD' ? '$' : '€'}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="RUB">₽ RUB</SelectItem>
              <SelectItem value="USD">$ USD</SelectItem>
              <SelectItem value="EUR">€ EUR</SelectItem>
            </SelectContent>
          </Select>

          {isAuthenticated ? (
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="flex items-center gap-2"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Выйти</span>
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={handleLoginClick}
              className="flex items-center gap-2"
            >
              <LogIn className="w-4 h-4" />
              <span className="hidden sm:inline">Вход</span>
            </Button>
          )}
        </div>
      </div>

      <AlertDialog open={showLoginDialog} onOpenChange={setShowLoginDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Доступ к системе</AlertDialogTitle>
            <AlertDialogDescription>
              Для получения доступа к системе обратитесь к нам по электронной почте:
              <br />
              <a
                href="mailto:info@beautybot.pro"
                className="text-blue-600 hover:text-blue-800 underline font-medium"
              >
                info@beautybot.pro
              </a>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setShowLoginDialog(false)}>
              Понятно
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </header>
  );
};

