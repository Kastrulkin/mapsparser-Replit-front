import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { YMaps, Map, Clusterer, Placemark } from '@pbe/react-yandex-maps';
import { mockMapLocations } from '../data/mockData';

export const NetworkMap: React.FC = () => {
    // Center roughly on SPB
    const defaultState = { center: [59.9343, 30.3351], zoom: 10 };

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
                <YMaps>
                    <Map defaultState={defaultState} width="100%" height="100%">
                        <Clusterer
                            options={{
                                preset: 'islands#invertedVioletClusterIcons',
                                groupByCoordinates: false,
                            }}
                        >
                            {mockMapLocations.map((loc) => (
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
