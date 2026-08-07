export const matchesSelectedSignalKeys = (
  leadSignalKeys: string[],
  selectedSignalKeys: string[],
) => selectedSignalKeys.length === 0
  || selectedSignalKeys.some((key) => leadSignalKeys.includes(key));
