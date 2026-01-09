import React, { useState, useEffect } from 'react';
import { getApiEndpoint } from '../config/api';
import { ChevronDown, Building2, Network } from 'lucide-react';

interface NetworkLocation {
  id: string;
  name: string;
  address?: string;
  description?: string;
}

interface NetworkSwitcherProps {
  networkId?: string;
  currentLocationId?: string;
  onLocationChange: (locationId: string) => void;
}

export const NetworkSwitcher: React.FC<NetworkSwitcherProps> = ({
  networkId,
  currentLocationId,
  onLocationChange
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [locations, setLocations] = useState<NetworkLocation[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<NetworkLocation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (networkId) {
      loadNetworkLocations();
    }
  }, [networkId]);

  useEffect(() => {
    if (locations.length > 0) {
      const current = locations.find(l => l.id === currentLocationId) || locations[0];
      setSelectedLocation(current);
    }
  }, [locations, currentLocationId]);

  const loadNetworkLocations = async () => {
    if (!networkId) return;
    
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`http://localhost:8000/api/networks/${networkId}/locations`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await response.json();

      if (data.success) {
        setLocations(data.locations || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки точек сети:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLocationSelect = (location: NetworkLocation) => {
    setSelectedLocation(location);
    onLocationChange(location.id);
    setIsOpen(false);
  };

  if (!networkId || locations.length === 0) {
    return null;
  }

  if (loading) {
    return (
      <div className="px-3 py-2 bg-white border border-gray-300 rounded-lg">
        <div className="text-sm text-gray-500">Загрузка...</div>
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
      >
        <Network className="w-4 h-4 text-gray-600" />
        <div className="text-left">
          <div className="text-sm font-medium text-gray-900">
            {selectedLocation?.name || 'Выберите точку'}
          </div>
          {selectedLocation?.address && (
            <div className="text-xs text-gray-500">
              {selectedLocation.address}
            </div>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto">
          {locations.map((location) => (
            <button
              key={location.id}
              onClick={() => handleLocationSelect(location)}
              className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                selectedLocation?.id === location.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
              }`}
            >
              <div className="flex items-start space-x-3">
                <Building2 className="w-4 h-4 text-gray-600 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">
                    {location.name}
                  </div>
                  {location.address && (
                    <div className="text-xs text-gray-500 mt-1 line-clamp-2">
                      {location.address}
                    </div>
                  )}
                  {location.description && (
                    <div className="text-xs text-gray-400 mt-1 line-clamp-1">
                      {location.description}
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

