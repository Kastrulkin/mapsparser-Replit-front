import { createContext, useContext } from 'react';

export type Currency = 'RUB' | 'USD' | 'EUR';

export interface CurrencyContextType {
  currency: Currency;
  setCurrency: (curr: Currency) => void;
  formatCurrency: (amount: number) => string;
}

export const CurrencyContext = createContext<CurrencyContextType | undefined>(undefined);

export const useCurrency = () => {
  const context = useContext(CurrencyContext);
  if (!context) {
    throw new Error('useCurrency must be used within a CurrencyProvider');
  }
  return context;
};
