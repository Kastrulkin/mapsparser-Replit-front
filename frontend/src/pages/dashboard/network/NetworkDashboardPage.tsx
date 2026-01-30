import React, { useState } from 'react';
import { DashboardHeader } from './components/DashboardHeader';
import { KPIGrid } from './components/KPIGrid';
import { AnalyticsTimeline } from './components/AnalyticsTimeline';
import { NetworkMap } from './components/NetworkMap';
import { SalonTable } from './components/SalonTable';
import { mockNetworkStats, mockNoCrmStats } from './data/mockData';
import { DateRange } from "react-day-picker";
import { addDays } from "date-fns";

export const NetworkDashboardPage = () => {
    const [date, setDate] = useState<DateRange | undefined>({
        from: new Date(2023, 0, 20),
        to: addDays(new Date(2023, 0, 20), 20),
    });

    const [viewMode, setViewMode] = useState<'list' | 'map' | 'grid'>('list');
    const [crmConnected, setCrmConnected] = useState(false); // Toggle for demo

    return (
        <div className="flex-1 space-y-4 p-8 pt-6">
            <DashboardHeader
                date={date}
                setDate={setDate}
                viewMode={viewMode}
                setViewMode={setViewMode}
            />

            <div className="space-y-4">
                <KPIGrid stats={crmConnected ? mockNetworkStats : mockNoCrmStats} crmConnected={crmConnected} />

                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                    <AnalyticsTimeline />
                    <NetworkMap />
                </div>

                <div className="space-y-4">
                    <SalonTable />
                </div>
            </div>
        </div>
    );
}
