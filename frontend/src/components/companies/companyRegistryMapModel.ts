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

export type CompanyDensityCell = {
  id: string;
  latitude: number;
  longitude: number;
  count: number;
  intensity: number;
  radiusMeters: number;
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

const WEB_MERCATOR_RADIUS_METERS = 6378137;
const MIN_DENSITY_CELL_METERS = 600;
const MAX_DENSITY_CELL_METERS = 120000;

const densityCellSizeForZoom = (zoom: number) => {
  const normalizedZoom = Number.isFinite(zoom) ? Math.min(18, Math.max(2, zoom)) : 9;
  const metersPerPixel = 156543.03392 / (2 ** normalizedZoom);
  return Math.min(MAX_DENSITY_CELL_METERS, Math.max(MIN_DENSITY_CELL_METERS, metersPerPixel * 92));
};

const projectToWebMercator = (latitude: number, longitude: number) => {
  const safeLatitude = Math.min(85, Math.max(-85, latitude));
  const latitudeRadians = safeLatitude * Math.PI / 180;
  const longitudeRadians = longitude * Math.PI / 180;
  return {
    x: WEB_MERCATOR_RADIUS_METERS * longitudeRadians,
    y: WEB_MERCATOR_RADIUS_METERS * Math.log(Math.tan(Math.PI / 4 + latitudeRadians / 2)),
  };
};

export const buildCompanyDensityCells = (items: CompanyMapPoint[], zoom: number): CompanyDensityCell[] => {
  const validItems = items.filter((item) => Number.isFinite(item.latitude) && Number.isFinite(item.longitude));
  if (!validItems.length) return [];

  const cellSizeMeters = densityCellSizeForZoom(zoom);
  const buckets = new Map<string, { latitudeTotal: number; longitudeTotal: number; count: number }>();

  validItems.forEach((item) => {
    const projected = projectToWebMercator(item.latitude, item.longitude);
    const column = Math.floor(projected.x / cellSizeMeters);
    const row = Math.floor(projected.y / cellSizeMeters);
    const key = `${column}:${row}`;
    const bucket = buckets.get(key) || { latitudeTotal: 0, longitudeTotal: 0, count: 0 };
    bucket.latitudeTotal += item.latitude;
    bucket.longitudeTotal += item.longitude;
    bucket.count += 1;
    buckets.set(key, bucket);
  });

  const maxCount = Math.max(...Array.from(buckets.values(), (bucket) => bucket.count));
  const intensityDenominator = Math.log1p(maxCount);

  return Array.from(buckets.entries(), ([id, bucket]) => ({
    id,
    latitude: bucket.latitudeTotal / bucket.count,
    longitude: bucket.longitudeTotal / bucket.count,
    count: bucket.count,
    intensity: intensityDenominator ? Math.log1p(bucket.count) / intensityDenominator : 1,
    radiusMeters: cellSizeMeters * 0.82,
  })).sort((left, right) => left.count - right.count);
};
