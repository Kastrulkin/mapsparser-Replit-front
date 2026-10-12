interface ScopeBusiness {
  id: string;
  name: string;
  network_id?: string | null;
  network_name?: string | null;
}

// Only the explicit parent represents the whole network. A branch cannot
// inherit a separately saved network scope.
export const resolveDashboardBusinessScope = (business: ScopeBusiness, requestedKind?: 'business' | 'network', demoMode = false) : { kind: 'business' | 'network'; id: string; name: string } => {
  // Public demo sessions are explicitly limited to one business, including a network parent.
  if (demoMode || requestedKind === 'business') return { kind: 'business', id: business.id, name: business.name };
  if (business.network_id && business.id === business.network_id) {
    return { kind: 'network', id: business.network_id, name: business.network_name || business.name };
  }
  return { kind: 'business', id: business.id, name: business.name };
};

export function demoScopedBusinesses<T extends ScopeBusiness>(businesses: T[], demoMode: boolean, scopeBusinessId?: string | null): T[] {
  if (!demoMode) return businesses;
  return scopeBusinessId ? businesses.filter(business => business.id === scopeBusinessId) : [];
}
