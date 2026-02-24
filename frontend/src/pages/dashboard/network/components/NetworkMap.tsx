import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { YMaps, Map, Clusterer, Placemark } from '@pbe/react-yandex-maps';
import { SalonData } from '../data/mockData';

interface NetworkMapProps {
    locations: SalonData[];
}

export const NetworkMap: React.FC<NetworkMapProps> = ({ locations }) => {
    const hasGeo = locations.some((loc) => Number.isFinite(loc.lat) && Number.isFinite(loc.lon));
    const centerLoc = locations.find((loc) => Number.isFinite(loc.lat) && Number.isFinite(loc.lon));
    const defaultState = centerLoc
        ? { center: [centerLoc.lat, centerLoc.lon], zoom: 10 }
        : { center: [59.9343, 30.3351], zoom: 10 };

    const getPreset = (status: 'active' | 'problem' | 'offline') => {
        switch (status) {
            case 'active': return 'islands#darkGreenDotIcon';
            case 'problem': return 'islands#yellowDotIcon';
            case 'offline': return 'islands#greyDotIcon'; // or red
            default: return 'islands#blueDotIcon';
        }
    };

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
                <YMaps>
                    <Map defaultState={defaultState} width="100%" height="100%">
                        <Clusterer
                            options={{
                                preset: 'islands#invertedVioletClusterIcons',
                                groupByCoordinates: false,
                            }}
                        >
                            {locations
                                .filter((loc) => Number.isFinite(loc.lat) && Number.isFinite(loc.lon))
                                .map((loc) => (
                                <Placemark
                                    key={loc.id}
                                    geometry={[loc.lat, loc.lon]}
                                    properties={{
                                        balloonContentHeader: loc.name,
                                        balloonContentBody: `Rating: ${loc.rating} ⭐<br/>Reviews: ${loc.reviews}`,
                                        hintContent: loc.name
                                    }}
                                    options={{
                                        preset: getPreset(loc.status)
                                    }}
                                />
                            ))}
                        </Clusterer>
                    </Map>
                </YMaps>
            </CardContent>
        </Card>
    );
};
