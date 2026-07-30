import { createContext, type ReactNode, useContext } from 'react';

export type MobileScope = {
  kind: 'platform' | 'network' | 'business';
  id?: string | null;
  name?: string;
  business_ids?: string[];
  can_switch?: boolean;
  parent_scope?: {
    kind?: 'network';
    id?: string | null;
    name?: string;
  } | null;
};

type MobileScopeContextValue = {
  scope?: MobileScope;
  hasSwitcher: boolean;
  openSwitcher: () => void;
};

const MobileScopeContext = createContext<MobileScopeContextValue | null>(null);

export function ScopeProvider({ value, children }: { value: MobileScopeContextValue; children: ReactNode }) {
  return <MobileScopeContext.Provider value={value}>{children}</MobileScopeContext.Provider>;
}

export function useMobileScope() {
  const value = useContext(MobileScopeContext);
  if (!value) throw new Error('ScopeProvider is required for the Telegram Mini App');
  return value;
}
