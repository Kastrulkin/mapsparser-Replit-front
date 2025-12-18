import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { newAuth } from '../lib/auth_new';
import { LanguageSwitcher } from './LanguageSwitcher';
import { useCurrency } from '../contexts/CurrencyContext';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { BusinessSwitcher } from './BusinessSwitcher';
import { LogOut, LogIn } from 'lucide-react';
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
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  businesses = [],
  currentBusinessId,
  onBusinessChange,
  isSuperadmin = false,
  user: userProp,
}) => {
  const { currency, setCurrency } = useCurrency();
  const [showLoginDialog, setShowLoginDialog] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      if (userProp) {
        setIsAuthenticated(true);
        return;
      }
      try {
        const currentUser = await newAuth.getCurrentUser();
        setIsAuthenticated(!!currentUser);
      } catch (error) {
        setIsAuthenticated(false);
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
      <div className="flex items-center justify-end px-4 py-3">
              <div className="flex items-center gap-3">
                 {/* Показываем переключатель бизнесов для суперадмина всегда (даже если бизнесов нет), для остальных - если больше 1 */}
                 {(isSuperadmin || businesses.length > 1) && (
                   <BusinessSwitcher
                     businesses={businesses}
                     currentBusinessId={currentBusinessId || undefined}
                     onBusinessChange={onBusinessChange || (() => {})}
                     isSuperadmin={isSuperadmin || false}
                   />
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

