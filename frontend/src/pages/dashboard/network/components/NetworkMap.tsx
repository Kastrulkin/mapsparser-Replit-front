import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SalonData } from '../data/mockData';

interface NetworkMapProps {
    locations: SalonData[];
}

export const NetworkMap: React.FC<NetworkMapProps> = ({ locations }) => {
    const validLocations = locations.filter((loc) => Number.isFinite(loc.lat) && Number.isFinite(loc.lon));
    const hasGeo = validLocations.length > 0;
    const centerLoc = validLocations[0];
    const center: [number, number] = centerLoc
        ? [centerLoc.lat, centerLoc.lon]
        : [59.9343, 30.3351];

    const delta = 0.08;
    const left = center[1] - delta;
    const right = center[1] + delta;
    const top = center[0] + delta;
    const bottom = center[0] - delta;
    const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${left}%2C${bottom}%2C${right}%2C${top}&layer=mapnik&marker=${center[0]}%2C${center[1]}`;

    return (
        <Card className="col-span-3">
            <CardHeader>
                <CardTitle>Salon Locations</CardTitle>
            </CardHeader>
            <CardContent className="p-0 overflow-hidden h-[400px] relative">
                {!hasGeo && (
                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/90 text-sm text-muted-foreground">
                        Нет координат для отображения карты
                    </div>
                )}
                <iframe
                    title="OpenStreetMap"
                    src={mapUrl}
                    className="w-full h-full border-0"
                    loading="lazy"
                />
                {hasGeo && (
                    <div className="absolute right-2 top-2 z-10 max-w-[260px] rounded-lg bg-white/90 p-2 text-xs shadow">
                        <div className="font-semibold mb-1">Точки на карте</div>
                        <div className="max-h-32 overflow-auto space-y-1">
                            {validLocations.map((loc) => (
                                <a
                                    key={loc.id}
                                    href={`https://www.openstreetmap.org/?mlat=${loc.lat}&mlon=${loc.lon}#map=16/${loc.lat}/${loc.lon}`}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="block hover:underline"
                                >
                                    {loc.name} • {loc.rating}⭐
                                </a>
                            ))}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
};
