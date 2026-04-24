import React, { useMemo, useRef, useState } from 'react';
import { YMaps, Map, Placemark, ZoomControl } from '@pbe/react-yandex-maps';
import { AlertTriangle, Expand, ExternalLink, MapPin, MessageSquare, Reply } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogOverlay,
    DialogPortal,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { SalonData } from '../data/mockData';

interface NetworkMapProps {
    locations: SalonData[];
    onOpenDashboard?: (businessId: string) => void;
    onOpenReviewDrilldown?: (businessId: string, filter: 'all' | 'negative' | 'needs_reply') => void;
}

interface MapViewport {
    center: [number, number];
    zoom: number;
    bounds: [[number, number], [number, number]] | null;
}

interface YandexMapInstance {
    setBounds?: (bounds: [[number, number], [number, number]], options?: Record<string, unknown>) => void;
}

const DEFAULT_CENTER: [number, number] = [59.9343, 30.3351];

const RATING_MARKER_SIZE: [number, number] = [54, 62];
const RATING_MARKER_OFFSET: [number, number] = [-27, -62];

const formatRating = (value: number) => {
    if (!Number.isFinite(value) || value <= 0) {
        return '0';
    }
    return Number(value.toFixed(2)).toString();
};

const getRatingTone = (rating: number) => {
    if (!Number.isFinite(rating) || rating <= 0) {
        return {
            label: 'Нет рейтинга',
            marker: '#64748b',
            markerDark: '#334155',
            surface: 'bg-slate-100 text-slate-700 border-slate-200',
        };
    }
    if (rating >= 4.5) {
        return {
            label: 'Сильный рейтинг',
            marker: '#10b981',
            markerDark: '#047857',
            surface: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        };
    }
    if (rating >= 4) {
        return {
            label: 'Норма',
            marker: '#3b82f6',
            markerDark: '#1d4ed8',
            surface: 'bg-blue-50 text-blue-700 border-blue-200',
        };
    }
    if (rating >= 3.5) {
        return {
            label: 'Нужен контроль',
            marker: '#f59e0b',
            markerDark: '#b45309',
            surface: 'bg-amber-50 text-amber-700 border-amber-200',
        };
    }
    return {
        label: 'Риск',
        marker: '#ef4444',
        markerDark: '#b91c1c',
        surface: 'bg-rose-50 text-rose-700 border-rose-200',
    };
};

const buildRatingMarkerSvg = (rating: number) => {
    const tone = getRatingTone(rating);
    const ratingLabel = formatRating(rating);
    const svg = `
        <svg width="54" height="62" viewBox="0 0 54 62" fill="none" xmlns="http://www.w3.org/2000/svg">
            <filter id="shadow" x="0" y="0" width="54" height="62" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
                <feDropShadow dx="0" dy="7" stdDeviation="4" flood-color="#0f172a" flood-opacity="0.26"/>
            </filter>
            <g filter="url(#shadow)">
                <path d="M27 55C27 55 47 36.7 47 22.8C47 11.9 38.1 4 27 4C15.9 4 7 11.9 7 22.8C7 36.7 27 55 27 55Z" fill="${tone.marker}" stroke="white" stroke-width="4"/>
                <circle cx="27" cy="23" r="15" fill="white" fill-opacity="0.96"/>
                <circle cx="27" cy="23" r="12" fill="${tone.marker}" fill-opacity="0.12"/>
                <text x="27" y="27" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="800" fill="${tone.markerDark}">${ratingLabel}</text>
            </g>
        </svg>
    `;
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
};

const buildViewport = (locations: SalonData[]): MapViewport => {
    if (!locations.length) {
        return {
            center: DEFAULT_CENTER,
            zoom: 9,
            bounds: null,
        };
    }

    const latitudes = locations.map((location) => location.lat);
    const longitudes = locations.map((location) => location.lon);
    const minLat = Math.min(...latitudes);
    const maxLat = Math.max(...latitudes);
    const minLon = Math.min(...longitudes);
    const maxLon = Math.max(...longitudes);
    const latSpan = Math.max(maxLat - minLat, 0.015);
    const lonSpan = Math.max(maxLon - minLon, 0.015);

    let zoom = 10;
    const maxSpan = Math.max(latSpan, lonSpan);
    if (maxSpan > 6) {
        zoom = 4;
    } else if (maxSpan > 3) {
        zoom = 5;
    } else if (maxSpan > 1.5) {
        zoom = 6;
    } else if (maxSpan > 0.8) {
        zoom = 7;
    } else if (maxSpan > 0.35) {
        zoom = 8;
    } else if (maxSpan > 0.18) {
        zoom = 9;
    } else if (maxSpan > 0.08) {
        zoom = 10;
    } else if (maxSpan > 0.03) {
        zoom = 11;
    } else {
        zoom = 12;
    }

    return {
        center: [(minLat + maxLat) / 2, (minLon + maxLon) / 2],
        zoom,
        bounds: [
            [minLat, minLon],
            [maxLat, maxLon],
        ],
    };
};

const NetworkMapCanvas: React.FC<{
    locations: SalonData[];
    heightClassName: string;
}> = ({ locations, heightClassName }) => {
    const viewport = useMemo(() => buildViewport(locations), [locations]);
    const fittedLocationsKeyRef = useRef<string | null>(null);
    const locationsKey = useMemo(
        () => locations.map((location) => `${location.id}:${location.lat}:${location.lon}`).join('|'),
        [locations],
    );

    const handleMapLoad = (mapInstance: YandexMapInstance | null) => {
        if (!mapInstance || !viewport.bounds || !mapInstance.setBounds || locations.length < 2) {
            return;
        }
        if (fittedLocationsKeyRef.current === locationsKey) {
            return;
        }
        fittedLocationsKeyRef.current = locationsKey;
        mapInstance.setBounds(viewport.bounds, {
            checkZoomRange: true,
            zoomMargin: 36,
        });
    };

    return (
        <div className={`relative overflow-hidden rounded-2xl border border-slate-200 ${heightClassName}`}>
            <YMaps
                query={{
                    lang: 'ru_RU',
                    load: 'package.full',
                }}
            >
                <Map
                    width="100%"
                    height="100%"
                    defaultState={{
                        center: viewport.center,
                        zoom: viewport.zoom,
                        controls: [],
                    }}
                    instanceRef={handleMapLoad}
                    modules={['geoObject.addon.balloon', 'geoObject.addon.hint']}
                >
                    <ZoomControl options={{ position: { right: 12, top: 12 } }} />
                    {locations.map((location) => {
                        const tone = getRatingTone(location.rating);
                        return (
                            <Placemark
                                key={location.id}
                                geometry={[location.lat, location.lon]}
                                properties={{
                                    hintContent: `${location.name} • ${formatRating(location.rating)}★`,
                                    balloonContentHeader: location.name,
                                    balloonContentBody: `
                                        <div style="min-width: 220px">
                                            <div style="font-size: 14px; margin-bottom: 6px;">${location.address}</div>
                                            <div style="font-size: 14px;"><strong>Рейтинг:</strong> ${formatRating(location.rating)} / 5</div>
                                            <div style="font-size: 14px;"><strong>Статус:</strong> ${tone.label}</div>
                                            <div style="font-size: 14px;"><strong>Отзывов:</strong> ${location.reviews}</div>
                                        </div>
                                    `,
                                }}
                                options={{
                                    iconLayout: 'default#image',
                                    iconImageHref: buildRatingMarkerSvg(location.rating),
                                    iconImageSize: RATING_MARKER_SIZE,
                                    iconImageOffset: RATING_MARKER_OFFSET,
                                    hideIconOnBalloonOpen: false,
                                }}
                            />
                        );
                    })}
                </Map>
            </YMaps>
        </div>
    );
};

export const NetworkMap: React.FC<NetworkMapProps> = ({ locations, onOpenDashboard, onOpenReviewDrilldown }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const validLocations = useMemo(
        () => locations.filter((location) => Number.isFinite(location.lat) && Number.isFinite(location.lon)),
        [locations]
    );
    const hasGeo = validLocations.length > 0;
    const openLocationOnMap = (location: SalonData) => {
        const resolvedUrl = location.mapUrl || `https://yandex.ru/maps/?pt=${location.lon},${location.lat}&z=15&l=map`;
        window.open(resolvedUrl, '_blank', 'noopener,noreferrer');
    };

    return (
        <>
            <Card className="col-span-3">
                <CardHeader className="flex flex-row items-start justify-between gap-3">
                    <div className="space-y-1">
                        <CardTitle>Точки на карте</CardTitle>
                        <p className="text-sm text-muted-foreground">
                            Видно, где реально расположены точки сети и как они распределены по городу.
                        </p>
                    </div>
                    {hasGeo && (
                        <Button
                            type="button"
                            variant="outline"
                            className="shrink-0"
                            onClick={() => setIsExpanded(true)}
                        >
                            <Expand className="mr-2 h-4 w-4" />
                            Открыть большую карту
                        </Button>
                    )}
                </CardHeader>
                <CardContent className="space-y-3 p-0">
                    <div className="px-6">
                        {!hasGeo ? (
                            <div className="flex h-[420px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-sm text-muted-foreground">
                                Нет координат для отображения карты
                            </div>
                        ) : (
                            <NetworkMapCanvas locations={validLocations} heightClassName="h-[420px]" />
                        )}
                    </div>

                    {hasGeo && (
                        <div className="px-6 pb-6">
                            <div className="rounded-3xl border border-slate-200 bg-white/90 p-4">
                                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                                        <MapPin className="h-4 w-4 text-slate-700" />
                                        Точки на карте
                                    </div>
                                    <div className="flex flex-wrap gap-1.5 text-[11px] font-semibold">
                                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-emerald-700">4.5+</span>
                                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-blue-700">4.0-4.4</span>
                                        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-amber-700">3.5-3.9</span>
                                        <span className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-rose-700">&lt; 3.5</span>
                                    </div>
                                </div>
                                <div className="max-h-36 space-y-2 overflow-auto pr-1 text-sm text-slate-700">
                                    {validLocations.map((location) => {
                                        const tone = getRatingTone(location.rating);
                                        return (
                                            <div
                                                key={location.id}
                                                className="rounded-2xl border border-transparent px-3 py-2 transition-colors hover:border-slate-200 hover:bg-slate-50"
                                            >
                                                <div className="flex items-center justify-between gap-3">
                                                    <span className="min-w-0">
                                                        <span className="block truncate font-medium text-slate-900">{location.name}</span>
                                                        <span className="block truncate text-xs text-slate-500">{location.address}</span>
                                                    </span>
                                                    <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${tone.surface}`}>
                                                        {formatRating(location.rating)}★
                                                    </span>
                                                </div>
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="outline"
                                                        className="h-8 rounded-full px-3 text-xs"
                                                        onClick={() => openLocationOnMap(location)}
                                                    >
                                                        <MapPin className="mr-1.5 h-3.5 w-3.5" />
                                                        На карте
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 rounded-full px-3 text-xs"
                                                        onClick={() => onOpenDashboard && onOpenDashboard(location.id)}
                                                    >
                                                        <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                                                        В LocalOS
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 rounded-full px-3 text-xs"
                                                        onClick={() => onOpenReviewDrilldown && onOpenReviewDrilldown(location.id, 'all')}
                                                    >
                                                        <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
                                                        Отзывы
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 rounded-full px-3 text-xs text-rose-700 hover:bg-rose-50 hover:text-rose-800"
                                                        onClick={() => onOpenReviewDrilldown && onOpenReviewDrilldown(location.id, 'negative')}
                                                    >
                                                        <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
                                                        Негатив
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 rounded-full px-3 text-xs text-amber-700 hover:bg-amber-50 hover:text-amber-800"
                                                        onClick={() => onOpenReviewDrilldown && onOpenReviewDrilldown(location.id, 'needs_reply')}
                                                    >
                                                        <Reply className="mr-1.5 h-3.5 w-3.5" />
                                                        Нужны ответы
                                                    </Button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            <Dialog open={isExpanded} onOpenChange={setIsExpanded}>
                <DialogPortal>
                    <DialogOverlay className="bg-slate-950/35 backdrop-blur-sm" />
                    <DialogContent className="max-w-6xl border-slate-200 bg-white/96 p-0 shadow-2xl">
                        <DialogHeader className="border-b border-slate-200 px-6 py-5">
                            <DialogTitle>Точки на карте</DialogTitle>
                            <DialogDescription>
                                Широкий режим для просмотра всех точек сети на одной карте.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_320px]">
                            <div className="p-6">
                                {hasGeo ? (
                                    <NetworkMapCanvas locations={validLocations} heightClassName="h-[72vh] min-h-[560px]" />
                                ) : (
                                    <div className="flex h-[72vh] min-h-[560px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-sm text-muted-foreground">
                                        Нет координат для отображения карты
                                    </div>
                                )}
                            </div>
                            <div className="border-t border-slate-200 bg-slate-50/80 p-6 lg:border-l lg:border-t-0">
                                <div className="mb-4 space-y-3">
                                    <div className="text-sm font-semibold text-slate-900">
                                        Все точки сети
                                    </div>
                                    <div className="grid grid-cols-2 gap-1.5 text-[11px] font-semibold">
                                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-center text-emerald-700">4.5+</span>
                                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-center text-blue-700">4.0-4.4</span>
                                        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-center text-amber-700">3.5-3.9</span>
                                        <span className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-center text-rose-700">&lt; 3.5</span>
                                    </div>
                                </div>
                                <div className="max-h-[72vh] min-h-[560px] space-y-2 overflow-auto pr-1">
                                    {validLocations.map((location) => {
                                        const tone = getRatingTone(location.rating);
                                        return (
                                            <div
                                                key={location.id}
                                                className="rounded-2xl border border-slate-200 bg-white px-4 py-3"
                                            >
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="min-w-0">
                                                        <div className="truncate font-medium text-slate-900">{location.name}</div>
                                                        <div className="mt-1 line-clamp-2 text-sm text-slate-500">{location.address}</div>
                                                    </div>
                                                    <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${tone.surface}`}>
                                                        {formatRating(location.rating)}
                                                    </span>
                                                </div>
                                                <div className="mt-2 text-sm text-slate-700">
                                                    {tone.label} · {location.reviews} отзывов
                                                </div>
                                                <div className="mt-3 flex flex-wrap gap-2">
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="outline"
                                                        className="h-8 rounded-full px-3 text-xs"
                                                        onClick={() => openLocationOnMap(location)}
                                                    >
                                                        <MapPin className="mr-1.5 h-3.5 w-3.5" />
                                                        Открыть на карте
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 rounded-full px-3 text-xs"
                                                        onClick={() => onOpenDashboard && onOpenDashboard(location.id)}
                                                    >
                                                        <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                                                        Открыть в LocalOS
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 rounded-full px-3 text-xs"
                                                        onClick={() => onOpenReviewDrilldown && onOpenReviewDrilldown(location.id, 'all')}
                                                    >
                                                        <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
                                                        Отзывы
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 rounded-full px-3 text-xs text-rose-700 hover:bg-rose-50 hover:text-rose-800"
                                                        onClick={() => onOpenReviewDrilldown && onOpenReviewDrilldown(location.id, 'negative')}
                                                    >
                                                        <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
                                                        Негатив
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 rounded-full px-3 text-xs text-amber-700 hover:bg-amber-50 hover:text-amber-800"
                                                        onClick={() => onOpenReviewDrilldown && onOpenReviewDrilldown(location.id, 'needs_reply')}
                                                    >
                                                        <Reply className="mr-1.5 h-3.5 w-3.5" />
                                                        Нужны ответы
                                                    </Button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    </DialogContent>
                </DialogPortal>
            </Dialog>
        </>
    );
};
