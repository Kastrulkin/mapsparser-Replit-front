import { type ReactNode } from 'react';
import { MobileScopeContext, type MobileScopeContextValue } from './ScopeProvider.logic';

export function ScopeProvider({ value, children }: { value: MobileScopeContextValue; children: ReactNode }) {
  return <MobileScopeContext.Provider value={value}>{children}</MobileScopeContext.Provider>;
}

export type { MobileScope } from './ScopeProvider.logic';
