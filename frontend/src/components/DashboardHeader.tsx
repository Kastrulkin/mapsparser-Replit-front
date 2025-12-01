import React from 'react';
import { Button } from './ui/button';
import { newAuth } from '../lib/auth_new';
import { LanguageSwitcher } from './LanguageSwitcher';
import { useCurrency } from '../contexts/CurrencyContext';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { BusinessSwitcher } from './BusinessSwitcher';
import { LogOut } from 'lucide-react';

interface DashboardHeaderProps {
  businesses?: any[];
  currentBusinessId?: string | null;
  onBusinessChange?: (businessId: string) => void;
  isSuperadmin?: boolean;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  businesses = [],
  currentBusinessId,
  onBusinessChange,
  isSuperadmin = false,
}) => {
  const { currency, setCurrency } = useCurrency();

  const handleLogout = async () => {
    try {
      await newAuth.signOut();
      localStorage.clear();
      window.location.href = '/login';
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="flex items-center justify-end px-4 py-3">
        <div className="flex items-center gap-3">
          {isSuperadmin && businesses.length > 0 && (
            <BusinessSwitcher
              businesses={businesses}
              currentBusinessId={currentBusinessId || undefined}
              onBusinessChange={onBusinessChange || (() => {})}
              isSuperadmin={true}
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

          <Button
            variant="outline"
            size="sm"
            onClick={handleLogout}
            className="flex items-center gap-2"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Выйти</span>
          </Button>
        </div>
      </div>
    </header>
  );
};

