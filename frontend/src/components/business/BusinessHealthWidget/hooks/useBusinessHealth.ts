import { useQuery } from '@tanstack/react-query';
import { BusinessHealthData, BusinessLocationWithAlerts } from '../types';

const fetchWithAuth = async <T>(url: string): Promise<T> => {
    const token = localStorage.getItem('token') || localStorage.getItem('auth_token');
    if (!token) throw new Error('No auth token');

    const response = await fetch(url, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        if (response.status === 403) throw new Error('Access denied');
        throw new Error('Failed to fetch data');
    }

    const data = await response.json();
    return data.data; // API wraps response in { success: true, data: ... }
};

export const useBusinessHealth = (businessId: string) => {
    return useQuery({
        queryKey: ['business', businessId, 'health'],
        queryFn: () => fetchWithAuth<BusinessHealthData>(`/api/network/health?business_id=${businessId}`),
        enabled: !!businessId,
        staleTime: 5 * 60 * 1000, // 5 minutes
        retry: (failureCount, error) => {
            // Don't retry on 403
            if (error.message === 'Access denied') return false;
            return failureCount < 2;
        }
    });
};

export const useBusinessAlerts = (businessId: string) => {
    return useQuery({
        queryKey: ['business', businessId, 'alerts'],
        queryFn: async () => {
            const data = await fetchWithAuth<{ locations: BusinessLocationWithAlerts[] }>(
                `/api/network/locations-alerts?business_id=${businessId}`
            );
            return data.locations[0] || null; // Flatten: return single location or null
        },
        enabled: !!businessId,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
};
