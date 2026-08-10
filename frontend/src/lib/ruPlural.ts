export const ruPlural = (count: number, one: string, few: string, many: string) => {
  const absolute = Math.abs(Math.trunc(count));
  const lastTwo = absolute % 100;
  const last = absolute % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return many;
  if (last === 1) return one;
  if (last >= 2 && last <= 4) return few;
  return many;
};

export const ruCountLabel = (count: number, one: string, few: string, many: string) =>
  `${count} ${ruPlural(count, one, few, many)}`;
