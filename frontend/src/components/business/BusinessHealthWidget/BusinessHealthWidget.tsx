import React from 'react';
import { useBusinessHealth, useBusinessAlerts } from './hooks/useBusinessHealth';
import { BusinessHealthView } from './BusinessHealthView';
import { BusinessHealthWidgetProps } from './types';

export const BusinessHealthWidget: React.FC<BusinessHealthWidgetProps> = ({
    businessId,
    className,
    variant = 'default'
}) => {
    // Parallel fetching
    const healthQuery = useBusinessHealth(businessId);
    const alertsQuery = useBusinessAlerts(businessId);

    const isLoading = healthQuery.isLoading || alertsQuery.isLoading;
    const error = healthQuery.error || alertsQuery.error;

    // If access denied (403), do not render anything (or could render explicit error)
    // Plan says: "Graceful degradation... Fallback on standard ProgressPage without widget"
    if (error && error.message === 'Access denied') {
        // DEBUG: Show the error instead of hiding for now
        return (
            <div className="p-4 border border-red-200 bg-red-50 rounded-lg text-red-700 text-sm mb-6">
                ⚠️ Debug: Access Denied (403). Check server logs/ownership.
            </div>
        );
    }

    return (
        <BusinessHealthView
            health={healthQuery.data}
            locationAlerts={alertsQuery.data}
            isLoading={isLoading}
            error={error as Error}
            className={className}
        />
    );
};
