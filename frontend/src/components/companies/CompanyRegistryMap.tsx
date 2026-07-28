import { useEffect, useMemo, useRef } from 'react';
import { Clusterer, Map, Placemark, YMaps, ZoomControl } from '@pbe/react-yandex-maps';
import { Building2, MapPin } from 'lucide-react';
import {
  buildCompanyMapViewport,
  COMPANY_MAP_ROLE_PRIORITY,
  COMPANY_MAP_ROLE_STYLES,
  getCompanyMapRole,
  type CompanyMapPoint,
} from './companyRegistryMapModel';

type CompanyRegistryMapProps = {
  items: CompanyMapPoint[];
  loading?: boolean;
  error?: string;
  truncated?: boolean;
  withoutCoordinates?: number;
  onSelect: (companyId: string) => void;
  onRetry: () => void;
};

type YandexMapInstance = {
  setBounds?: (bounds: [[number, number], [number, number]], options?: Record<string, unknown>) => void;
  setCenter?: (center: [number, number], zoom?: number, options?: Record<string, unknown>) => void;
};

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (symbol) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#039;',
}[symbol] || symbol));

const MapSkeleton = () => (
  <div className="h-[560px] animate-pulse rounded-[28px] bg-slate-100 motion-reduce:animate-none" aria-label="Загрузка карты" />
);

export const CompanyRegistryMap = ({ items, loading, error, truncated, withoutCoordinates = 0, onSelect, onRetry }: CompanyRegistryMapProps) => {
  const validItems = useMemo(
    () => items.filter((item) => Number.isFinite(item.latitude) && Number.isFinite(item.longitude)),
    [items],
  );
  const viewport = useMemo(() => buildCompanyMapViewport(validItems), [validItems]);
  const mapRef = useRef<YandexMapInstance | null>(null);
  const pointsKey = useMemo(
    () => validItems.map((item) => `${item.id}:${item.latitude}:${item.longitude}`).join('|'),
    [validItems],
  );

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (viewport.bounds && map.setBounds) {
      map.setBounds(viewport.bounds, { checkZoomRange: true, zoomMargin: 72 });
      return;
    }
    if (map.setCenter) map.setCenter(viewport.center, viewport.zoom, { duration: 180 });
  }, [pointsKey, viewport]);

  if (loading) return <MapSkeleton />;
  if (error) {
    return (
      <div className="grid min-h-[420px] place-items-center rounded-[28px] bg-rose-50 p-8 text-center shadow-[0_0_0_1px_rgba(244,63,94,0.12)]">
        <div><MapPin className="mx-auto h-7 w-7 text-rose-400" /><b className="mt-4 block text-balance text-slate-950">Карта временно недоступна</b><p className="mt-2 text-pretty text-sm text-slate-600">{error}</p><button type="button" onClick={onRetry} className="mt-5 min-h-11 rounded-2xl bg-white px-4 text-sm font-semibold text-slate-800 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_4px_16px_rgba(15,23,42,0.06)] transition-transform active:scale-[0.96]">Повторить</button></div>
      </div>
    );
  }
  if (!validItems.length) {
    return (
      <div className="grid min-h-[420px] place-items-center rounded-[28px] bg-slate-50 p-8 text-center shadow-[0_0_0_1px_rgba(15,23,42,0.06)]">
        <div><Building2 className="mx-auto h-7 w-7 text-slate-300" /><b className="mt-4 block text-balance text-slate-950">Нет компаний с координатами</b><p className="mt-2 max-w-md text-pretty text-sm leading-6 text-slate-500">Измените фильтры или обновите данные карт. Компания появится здесь, когда LocalOS получит её координаты.</p></div>
      </div>
    );
  }

  return (
    <section className="overflow-hidden rounded-[28px] bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_18px_50px_rgba(15,23,42,0.08)]">
      <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div><b className="text-balance text-sm text-slate-950">Компании на карте</b><p className="mt-1 text-pretty text-xs text-slate-500">Нажмите на точку, чтобы открыть карточку компании.</p></div>
        <div className="flex flex-wrap gap-x-3 gap-y-2 text-[11px] font-semibold text-slate-600">
          {COMPANY_MAP_ROLE_PRIORITY.map((key) => <span key={key} className="inline-flex items-center gap-1.5"><i className={`h-2.5 w-2.5 rounded-full ${COMPANY_MAP_ROLE_STYLES[key].legend}`} />{COMPANY_MAP_ROLE_STYLES[key].label}</span>)}
        </div>
      </div>
      <div className="h-[560px] min-h-[420px] w-full outline outline-1 -outline-offset-1 outline-black/10">
        <YMaps query={{ lang: 'ru_RU', load: 'package.full' }}>
          <Map
            width="100%"
            height="100%"
            defaultState={{ center: viewport.center, zoom: viewport.zoom, controls: [] }}
            instanceRef={(instance) => { mapRef.current = instance; }}
            modules={['geoObject.addon.balloon', 'geoObject.addon.hint']}
          >
            <ZoomControl options={{ position: { right: 14, top: 14 } }} />
            <Clusterer options={{ preset: 'islands#invertedDarkBlueClusterIcons', groupByCoordinates: false, clusterDisableClickZoom: false, clusterOpenBalloonOnClick: false }}>
              {validItems.map((company) => {
                const role = getCompanyMapRole(company.roles);
                const roles = (company.roles || []).map((item) => item.label).join(', ') || role.label;
                const address = [company.city, company.address].filter(Boolean).join(', ') || 'Адрес ещё не подтверждён';
                return (
                  <Placemark
                    key={company.id}
                    geometry={[company.latitude, company.longitude]}
                    properties={{
                      iconCaption: company.name,
                      hintContent: `${company.name} · ${roles}`,
                      balloonContentHeader: escapeHtml(company.name),
                      balloonContentBody: `<div style="min-width:220px;font:13px/1.45 Inter,Arial,sans-serif"><div style="margin-bottom:6px;color:#475569">${escapeHtml(address)}</div><div><strong>Роль:</strong> ${escapeHtml(roles)}</div><div><strong>Тип:</strong> ${escapeHtml(company.primary_category || 'не определён')}</div><button type="button" style="margin-top:10px;border:0;border-radius:10px;background:#0f172a;color:#fff;padding:8px 12px;font-weight:600;cursor:pointer">Открыть карточку</button></div>`,
                    }}
                    options={{ preset: 'islands#circleDotIcon', iconColor: role.color, hideIconOnBalloonOpen: false }}
                    events={{ click: () => onSelect(company.id) }}
                  />
                );
              })}
            </Clusterer>
          </Map>
        </YMaps>
      </div>
      <div className="flex min-h-10 flex-wrap items-center gap-x-4 gap-y-1 px-4 text-pretty text-xs text-slate-500 sm:px-5">
        {withoutCoordinates > 0 ? <span><b className="tabular-nums text-slate-700">{withoutCoordinates}</b> компаний пока без координат</span> : null}
        {truncated ? <span>Масштаб выборки большой — уточните фильтры.</span> : null}
        <a className="ml-auto inline-flex min-h-10 items-center text-slate-400 transition-colors hover:text-slate-600" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">Часть координат: © OpenStreetMap</a>
      </div>
    </section>
  );
};
