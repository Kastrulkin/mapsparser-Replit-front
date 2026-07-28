export type CompanyMapRole = { key: string; label: string };

export type CompanyMapPoint = {
  id: string;
  name: string;
  primary_category?: string;
  address?: string;
  city?: string;
  latitude: number;
  longitude: number;
  roles?: CompanyMapRole[];
};

export type CompanyMapViewport = {
  center: [number, number];
  zoom: number;
  bounds: [[number, number], [number, number]] | null;
};

const DEFAULT_CENTER: [number, number] = [55.751244, 37.618423];

export const COMPANY_MAP_ROLE_STYLES: Record<string, { color: string; label: string; legend: string }> = {
  client: { color: '#10b981', label: 'Клиент', legend: 'bg-emerald-500' },
  partner: { color: '#0ea5e9', label: 'Партнёр', legend: 'bg-sky-500' },
  localos_lead: { color: '#f97316', label: 'Лид LocalOS', legend: 'bg-orange-500' },
  competitor: { color: '#8b5cf6', label: 'Конкурент', legend: 'bg-violet-500' },
  observed: { color: '#64748b', label: 'Без роли', legend: 'bg-slate-500' },
};

export const COMPANY_MAP_ROLE_PRIORITY = ['client', 'partner', 'localos_lead', 'competitor', 'observed'];

export const getCompanyMapRole = (roles: CompanyMapRole[] = []) => {
  const roleKey = COMPANY_MAP_ROLE_PRIORITY.find((key) => roles.some((role) => role.key === key)) || 'observed';
  return { key: roleKey, ...COMPANY_MAP_ROLE_STYLES[roleKey] };
};

export const buildCompanyMapViewport = (items: CompanyMapPoint[]): CompanyMapViewport => {
  if (!items.length) return { center: DEFAULT_CENTER, zoom: 9, bounds: null };
  const latitudes = items.map((item) => item.latitude);
  const longitudes = items.map((item) => item.longitude);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLon = Math.min(...longitudes);
  const maxLon = Math.max(...longitudes);
  if (items.length === 1) return { center: [minLat, minLon], zoom: 14, bounds: null };
  return {
    center: [(minLat + maxLat) / 2, (minLon + maxLon) / 2],
    zoom: 9,
    bounds: [[minLat, minLon], [maxLat, maxLon]],
  };
};
