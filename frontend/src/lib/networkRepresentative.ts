interface NetworkBusinessLike {
  id?: string;
  name?: string;
  network_id?: string;
  created_at?: string;
}

const normalizeName = (value: string) =>
  String(value || '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();

export const pickNetworkRepresentative = <T extends NetworkBusinessLike>(items: T[], networkId: string): T | null => {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const explicitParent = items.find((item) => String(item?.id || '').trim() === String(networkId || '').trim());
  if (explicitParent) {
    return explicitParent;
  }

  const withNames = items.map((item) => ({
    item,
    normalizedName: normalizeName(String(item?.name || '')),
    rawName: String(item?.name || '').trim(),
    createdAt: String(item?.created_at || ''),
  }));

  const counts: Record<string, number> = {};
  for (const entry of withNames) {
    if (!entry.normalizedName) continue;
    counts[entry.normalizedName] = (counts[entry.normalizedName] || 0) + 1;
  }

  const uniqueCandidates = withNames
    .filter((entry) => entry.normalizedName && counts[entry.normalizedName] === 1)
    .sort((left, right) => {
      const wordsDiff = right.normalizedName.split(' ').length - left.normalizedName.split(' ').length;
      if (wordsDiff !== 0) return wordsDiff;
      const lengthDiff = right.rawName.length - left.rawName.length;
      if (lengthDiff !== 0) return lengthDiff;
      return left.createdAt.localeCompare(right.createdAt);
    });

  if (uniqueCandidates.length > 0) {
    return uniqueCandidates[0].item;
  }

  const sortedFallback = [...withNames].sort((left, right) => {
    const leftCreated = left.createdAt;
    const rightCreated = right.createdAt;
    if (leftCreated !== rightCreated) {
      return leftCreated.localeCompare(rightCreated);
    }
    return left.rawName.localeCompare(right.rawName, 'ru');
  });

  return sortedFallback[0]?.item || null;
};

export const getNetworkRepresentativeIds = <T extends NetworkBusinessLike>(items: T[]) => {
  const groups: Record<string, T[]> = {};
  const ids: Record<string, boolean> = {};

  for (const item of items) {
    const networkId = String(item?.network_id || '').trim();
    if (!networkId) continue;
    if (!groups[networkId]) {
      groups[networkId] = [];
    }
    groups[networkId].push(item);
  }

  for (const networkId of Object.keys(groups)) {
    const representative = pickNetworkRepresentative(groups[networkId], networkId);
    const representativeId = String(representative?.id || '').trim();
    if (representativeId) {
      ids[representativeId] = true;
    }
  }

  return ids;
};
