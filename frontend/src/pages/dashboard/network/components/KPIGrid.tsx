import React from 'react';
import { NetworkStats } from '../data/mockData';
import { NetworkRatingCard } from './kpi/NetworkRatingCard';
import { ActiveSalonsCard } from './kpi/ActiveSalonsCard';
import { NegativeFeedbackCard } from './kpi/NegativeFeedbackCard';
import { RetentionCard } from './kpi/RetentionCard';
import { RatingDistributionCard } from './kpi/RatingDistributionCard';

interface KPIGridProps {
    stats: NetworkStats;
    crmConnected: boolean;
}

export const KPIGrid: React.FC<KPIGridProps> = ({ stats, crmConnected }) => {
    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            <NetworkRatingCard stats={stats} />
            <ActiveSalonsCard stats={stats} />
            <NegativeFeedbackCard stats={stats} />
            <RetentionCard stats={crmConnected ? stats : { ...stats, retentionRate: undefined }} />
            <RatingDistributionCard stats={stats} />
        </div>
    );
};
