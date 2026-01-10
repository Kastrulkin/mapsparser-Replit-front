import { useState, useEffect } from 'react';
import { Building2, ChevronDown, MapPin } from 'lucide-react';

interface NetworkLocation {
    id: string;
    name: string;
    address?: string;
    description?: string;
}

interface NetworkLocationsSwitcherProps {
    currentBusinessId?: string;
    onLocationChange: (businessId: string) => void;
}

export const NetworkLocationsSwitcher: React.FC<NetworkLocationsSwitcherProps> = ({
    currentBusinessId,
    onLocationChange,
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const [locations, setLocations] = useState<NetworkLocation[]>([]);
    const [selectedLocation, setSelectedLocation] = useState<NetworkLocation | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadNetworkLocations();
    }, [currentBusinessId]);

    const loadNetworkLocations = async () => {
        if (!currentBusinessId) {
            setLoading(false);
            return;
        }

        try {
            setLoading(true);
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`/api/business/${currentBusinessId}/network-locations`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                const networkLocations = data.locations || [];
                setLocations(networkLocations);

                // Устанавливаем текущую локацию
                const current = networkLocations.find((loc: NetworkLocation) => loc.id === currentBusinessId);
                setSelectedLocation(current || networkLocations[0] || null);
            }
        } catch (error) {
            console.error('Error loading network locations:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleLocationSelect = (location: NetworkLocation) => {
        setSelectedLocation(location);
        onLocationChange(location.id);
        setIsOpen(false);
    };

    if (loading) {
        return (
            <div className="flex items-center space-x-2 px-3 py-2 bg-gray-50 border border-gray-300 rounded-lg">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                <span className="text-sm text-gray-500">Загрузка...</span>
            </div>
        );
    }

    if (locations.length === 0) {
        return null; // Не показываем dropdown если нет точек сети
    }

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center space-x-2 px-3 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
                <MapPin className="w-4 h-4 text-blue-600" />
                <div className="text-left">
                    <div className="text-sm font-medium text-gray-900">
                        {selectedLocation?.name || 'Выберите точку'}
                    </div>
                    {selectedLocation?.address && (
                        <div className="text-xs text-gray-500 truncate max-w-[200px]">
                            {selectedLocation.address}
                        </div>
                    )}
                </div>
                <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto min-w-[300px]">
                    {locations.map((location) => (
                        <button
                            key={location.id}
                            onClick={() => handleLocationSelect(location)}
                            className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${selectedLocation?.id === location.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                                }`}
                        >
                            <div className="flex items-start space-x-3">
                                <MapPin className="w-4 h-4 text-blue-600 mt-0.5" />
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium text-gray-900 truncate">
                                        {location.name}
                                    </div>
                                    {location.address && (
                                        <div className="text-xs text-gray-500 mt-1 line-clamp-2">
                                            {location.address}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};
