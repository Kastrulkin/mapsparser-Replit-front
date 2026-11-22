export function researchDate(value: string) {
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value.replace(' ', 'T'));
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('ru-RU');
}
