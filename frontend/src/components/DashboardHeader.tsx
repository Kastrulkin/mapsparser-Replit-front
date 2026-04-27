import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
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
    <header className={cn(
      "sticky top-0 z-30 px-4 py-4 transition-all duration-300 sm:px-6",
      "border-b border-slate-200/70 bg-white/82 backdrop-blur-xl supports-[backdrop-filter]:bg-white/74"
    )}>
      <div className="flex items-center justify-between gap-4">
        {/* Left Side: Context Switchers */}
        <div className="flex items-center gap-3 flex-1">
          {isSuperadmin && (
            <div className="flex items-center gap-2 animate-in fade-in slide-in-from-left-4 duration-500">
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-700">
                SuperAdmin
              </span>
              {currentBusiness?.network_id && (
                <span className="hidden rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-medium text-slate-500 lg:inline-flex">
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
            <h1 className="hidden text-lg font-semibold text-slate-800 md:block">
              {currentBusiness.name}
            </h1>
          )}
        </div>

        {/* Right Side: Actions & Profile */}
        <div className="flex items-center gap-3">
          {/* Quick Actions for superadmins */}
          {currentUser?.is_superadmin && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate('/dashboard/bazich')}
              className="text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              title="Bazich Settings"
            >
              <Settings className="w-5 h-5" />
            </Button>
          )}

          <div className="hidden h-6 w-px bg-slate-200 sm:block"></div>

          <LanguageSwitcher />

          <Select value={currency} onValueChange={(value) => setCurrency(value as 'RUB' | 'USD' | 'EUR')}>
            <SelectTrigger className="h-9 w-14 border-0 bg-transparent hover:bg-slate-100/80 focus:ring-0">
              <span className="text-base font-medium text-slate-700">
                {currency === 'RUB' ? '₽' : currency === 'USD' ? '$' : '€'}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="RUB">₽ RUB</SelectItem>
              <SelectItem value="USD">$ USD</SelectItem>
              <SelectItem value="EUR">€ EUR</SelectItem>
            </SelectContent>
          </Select>

          <div className="hidden h-6 w-px bg-slate-200 sm:block"></div>

          {isAuthenticated && currentUser ? (
            <div className="flex items-center gap-3 pl-2">
              <Link to="/dashboard/profile" className="flex items-center gap-2 group">
                <div className="h-9 w-9 rounded-full border border-slate-200 bg-white p-[2px] shadow-sm transition-all group-hover:border-slate-300 group-hover:shadow-md">
                  <div className="flex h-full w-full items-center justify-center rounded-full bg-slate-50">
                    <UserCircle className="h-5 w-5 text-slate-600" />
                  </div>
                </div>
                <span className="hidden text-sm font-medium text-slate-700 transition-colors group-hover:text-slate-950 lg:block">
                  {currentUser.email?.split('@')[0]}
                </span>
              </Link>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                className="text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-500"
              >
                <LogOut className="w-5 h-5" />
              </Button>
            </div>
          ) : (
            <Button
              onClick={handleLoginClick}
              className="rounded-xl bg-slate-900 text-white shadow-sm transition-all hover:bg-slate-800 hover:shadow-md"
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
                href="mailto:info@local.pro"
                className="text-blue-600 hover:text-blue-800 underline font-medium"
              >
                info@local.pro
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
