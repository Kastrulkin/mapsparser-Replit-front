interface ScopeBusiness {
  id: string;
  name: string;
  network_id?: string | null;
  network_name?: string | null;
}

// Only the explicit parent represents the whole network. A branch cannot
// inherit a separately saved network scope.
export const resolveDashboardBusinessScope = (business: ScopeBusiness, requestedKind?: 'business' | 'network') : { kind: 'business' | 'network'; id: string; name: string } => {
  if (requestedKind === 'business') return { kind: 'business', id: business.id, name: business.name };
  if (business.network_id && business.id === business.network_id) {
    return { kind: 'network', id: business.network_id, name: business.network_name || business.name };
  }
  return { kind: 'business', id: business.id, name: business.name };
};
