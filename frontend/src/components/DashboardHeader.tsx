import React, { useState, useEffect } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { Button } from './ui/button';
import { newAuth } from '../lib/auth_new';
import { LanguageSwitcher } from './LanguageSwitcher';
import { useCurrency } from '../contexts/CurrencyContext';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { BusinessSwitcher } from './BusinessSwitcher';
import { NetworkLocationsSwitcher } from './NetworkLocationsSwitcher';
import { LogOut, LogIn, Settings, Bell, Search, UserCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import { DESIGN_TOKENS } from '../lib/design-tokens';
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
  const location = useLocation();
  const [showLoginDialog, setShowLoginDialog] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);
  
  // Проверяем, находимся ли мы на странице админки
  const isOnAdminPage = location.pathname === '/dashboard/bazich' || location.pathname === '/bazich';

  useEffect(() => {
    const checkAuth = async () => {
      if (userProp) {
        setIsAuthenticated(true);
        setCurrentUser(userProp);
        console.log('🔍 DashboardHeader: userProp.is_superadmin =', userProp?.is_superadmin);
        return;
      }
      try {
        const user = await newAuth.getCurrentUser();
        setIsAuthenticated(!!user);
        setCurrentUser(user);
        console.log('🔍 DashboardHeader: currentUser.is_superadmin =', user?.is_superadmin);
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
    <header className={cn(
      "sticky top-0 z-30 px-6 py-4 transition-all duration-300",
      "bg-white/70 backdrop-blur-xl border-b border-white/20 supports-[backdrop-filter]:bg-white/60"
    )}>
      <div className="flex items-center justify-between gap-4">
        {/* Left Side: Context Switchers */}
        <div className="flex items-center gap-3 flex-1">
          {isSuperadmin && (
            <div className="flex items-center gap-2 animate-in fade-in slide-in-from-left-4 duration-500">
              <span className="px-2 py-1 text-[10px] font-bold text-indigo-500 uppercase tracking-wider bg-indigo-50 rounded-md border border-indigo-100">
                SuperAdmin
              </span>
              {currentBusiness?.network_id && (
                <span className="hidden lg:inline-flex text-[10px] font-mono text-gray-500 bg-gray-50 px-2 py-1 rounded border border-gray-100">
                  NetID: {currentBusiness.network_id.substring(0, 8)}...
                </span>
              )}
              <BusinessSwitcher
                businesses={businesses}
                currentBusinessId={currentBusinessId || undefined}
                onBusinessChange={onBusinessChange || (() => { })}
                isSuperadmin={isSuperadmin}
              />
            </div>
          )}

          {currentBusiness?.network_id && onBusinessChange && (
            <NetworkLocationsSwitcher
              currentBusinessId={currentBusinessId || undefined}
              onLocationChange={onBusinessChange}
            />
          )}

          {/* Fallback Title if no switchers active */}
          {!isSuperadmin && !currentBusiness?.network_id && currentBusiness && (
            <h1 className="text-lg font-semibold text-gray-800 hidden md:block">
              {currentBusiness.name}
            </h1>
          )}
        </div>

        {/* Right Side: Actions & Profile */}
        <div className="flex items-center gap-3">
          {/* Quick Actions for Superadmin */}
          {(isSuperadmin || currentUser?.is_superadmin) && (
            <Link to="/dashboard/bazich">
            <Button
              variant="ghost"
              size="icon"
                className={cn(
                  "text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors",
                  isOnAdminPage && "text-indigo-600 bg-indigo-50"
                )}
                title={isOnAdminPage ? "Вы находитесь в админ-панели" : "Открыть админ-панель"}
            >
              <Settings className="w-5 h-5" />
            </Button>
            </Link>
          )}

          <div className="h-6 w-px bg-gray-200/60 hidden sm:block"></div>

          <LanguageSwitcher />

          <Select value={currency} onValueChange={(value) => setCurrency(value as 'RUB' | 'USD' | 'EUR')}>
            <SelectTrigger className="w-14 h-9 bg-transparent border-0 hover:bg-gray-100/50 focus:ring-0">
              <span className="text-base font-medium text-gray-700">
                {currency === 'RUB' ? '₽' : currency === 'USD' ? '$' : '€'}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="RUB">₽ RUB</SelectItem>
              <SelectItem value="USD">$ USD</SelectItem>
              <SelectItem value="EUR">€ EUR</SelectItem>
            </SelectContent>
          </Select>

          <div className="h-6 w-px bg-gray-200/60 hidden sm:block"></div>

          {isAuthenticated && currentUser ? (
            <div className="flex items-center gap-3 pl-2">
              <Link to="/dashboard/profile" className="flex items-center gap-2 group">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-600 p-[2px] shadow-sm group-hover:shadow-md transition-all">
                  <div className="w-full h-full rounded-full bg-white flex items-center justify-center">
                    <UserCircle className="w-5 h-5 text-gray-600" />
                  </div>
                </div>
                <span className="text-sm font-medium text-gray-700 hidden lg:block group-hover:text-blue-600 transition-colors">
                  {currentUser.email?.split('@')[0]}
                </span>
              </Link>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                className="text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              >
                <LogOut className="w-5 h-5" />
              </Button>
            </div>
          ) : (
            <Button
              onClick={handleLoginClick}
              className="bg-blue-600 hover:bg-blue-700 text-white shadow-sm hover:shadow-md transition-all rounded-xl"
            >
              <LogIn className="w-4 h-4 mr-2" />
              <span className="hidden sm:inline">Вход</span>
            </Button>
          )}
        </div>
      </div>

      <AlertDialog open={showLoginDialog} onOpenChange={setShowLoginDialog}>
        <AlertDialogContent className="glass-panel">
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

