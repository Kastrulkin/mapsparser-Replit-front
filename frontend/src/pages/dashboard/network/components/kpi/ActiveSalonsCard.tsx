import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NetworkStats } from '../../data/mockData';
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

interface ActiveSalonsCardProps {
    stats: NetworkStats;
}

export const ActiveSalonsCard: React.FC<ActiveSalonsCardProps> = ({ stats }) => {
    const { totalSalons, activeSalons, problemSalons, offlineSalons } = stats;

    const data = [
        { name: 'Active', value: activeSalons, color: '#10b981' }, // emerald-500
        { name: 'Problem', value: problemSalons, color: '#eab308' }, // yellow-500
        { name: 'Offline', value: offlineSalons, color: '#ef4444' }, // red-500
    ];

    const coveragePercent = Math.round((activeSalons / totalSalons) * 100);
    const isHealthy = coveragePercent >= 90;

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Active Coverage</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-between">
                <div>
                    <div className="text-2xl font-bold">
                        {activeSalons}<span className="text-gray-400 text-lg">/{totalSalons}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                        {problemSalons > 0 ? `${problemSalons} require attention` : "All systems operational"}
                    </p>
                </div>
                <div className="h-[50px] w-[50px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={data}
                                cx="50%"
                                cy="50%"
                                innerRadius={15}
                                outerRadius={24}
                                paddingAngle={2}
                                dataKey="value"
                            >
                                {data.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                            </Pie>
                        </PieChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
};
