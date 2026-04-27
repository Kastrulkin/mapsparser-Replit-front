import { useCallback, useRef, useState, useEffect } from 'react';
import { Building2, ChevronDown, MapPin } from 'lucide-react';
import { pickNetworkRepresentative } from '@/lib/networkRepresentative';
import { useClickOutside } from '@/hooks/useClickOutside';

interface NetworkLocation {
    id: string;
    name: string;
    address?: string;
    description?: string;
    network_id?: string;
    created_at?: string;
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
    const switcherRef = useRef<HTMLDivElement | null>(null);
    const closeSwitcher = useCallback(() => setIsOpen(false), []);
    useClickOutside(switcherRef, closeSwitcher, { enabled: isOpen });

    const parentLocationId = (() => {
        const networkId = String(locations[0]?.network_id || '').trim();
        if (!networkId) return '';
        return String(pickNetworkRepresentative(locations, networkId)?.id || '').trim();
    })();

    const getLocationLabel = (location: NetworkLocation | null) => {
        if (!location) return 'Выберите точку';
        const baseName = String(location.name || '').trim() || 'Точка';
        if (parentLocationId && String(location.id || '').trim() === parentLocationId) {
            return `👑 ${baseName}`;
        }
        return baseName;
    };

    const getLocationSubtitle = (location: NetworkLocation | null) => {
        const rawAddress = String(location?.address || '').trim();
        const normalizedAddress = rawAddress.toLowerCase();
        if (!rawAddress) {
            return '';
        }
        if (normalizedAddress === 'материнская точка сети') {
            return '';
        }
        return rawAddress;
    };

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
        <div ref={switcherRef} className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center space-x-2 px-3 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
                <MapPin className="w-4 h-4 text-blue-600" />
                <div className="text-left">
                    <div className="text-sm font-medium text-gray-900">
                        {getLocationLabel(selectedLocation)}
                    </div>
                    {getLocationSubtitle(selectedLocation) && (
                        <div className="text-xs text-gray-500 truncate max-w-[200px]">
                            {getLocationSubtitle(selectedLocation)}
                        </div>
                    )}
                </div>
                <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && (
                <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
                    {locations.map((location) => (
                        <button
                            key={location.id}
                            onClick={() => handleLocationSelect(location)}
                            className={`w-full px-4 py-3 text-left hover:bg-gray-50 flex items-start space-x-3 transition-colors ${selectedLocation?.id === location.id ? 'bg-blue-50' : ''
                                }`}
                        >
                            <Building2 className={`w-5 h-5 mt-0.5 flex-shrink-0 ${selectedLocation?.id === location.id ? 'text-blue-600' : 'text-gray-400'
                                }`} />
                            <div>
                                <div className={`text-sm font-medium ${selectedLocation?.id === location.id ? 'text-blue-900' : 'text-gray-900'
                                        }`}>
                                    {getLocationLabel(location)}
                                </div>
                                {getLocationSubtitle(location) && (
                                    <div className="text-xs text-gray-500 mt-0.5">
                                        {getLocationSubtitle(location)}
                                    </div>
                                )}
                            </div>
                        </button>
                    ))}
                </div>
            )}


        </div>
    );
};
