import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NetworkStats } from '../../data/mockData';
import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import { LineChart, Line, ResponsiveContainer } from "recharts";

interface NetworkRatingCardProps {
    stats: NetworkStats;
}

export const NetworkRatingCard: React.FC<NetworkRatingCardProps> = ({ stats }) => {
    const { averageRating, ratingTrend, ratingHistory } = stats;

    const getStatusColor = (rating: number) => {
        if (rating >= 4.8) return "text-emerald-500";
        if (rating >= 4.3) return "text-green-500";
        if (rating >= 3.8) return "text-yellow-500";
        return "text-red-500";
    };

    const getTrendIcon = (trend: number) => {
        if (trend > 0) return <ArrowUp className="h-4 w-4 text-green-500" />;
        if (trend < 0) return <ArrowDown className="h-4 w-4 text-red-500" />;
        return <Minus className="h-4 w-4 text-gray-400" />;
    };

    return (
        <Card className="overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Network Rating</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="flex items-baseline space-x-2">
                    <div className={`text-2xl font-bold ${getStatusColor(averageRating)}`}>
                        {averageRating} <span className="text-lg">⭐</span>
                    </div>
                    <div className="flex items-center text-xs text-muted-foreground">
                        {getTrendIcon(ratingTrend)}
                        <span className={ratingTrend > 0 ? "text-green-500" : ratingTrend < 0 ? "text-red-500" : ""}>
                            {Math.abs(ratingTrend)}%
                        </span>
                        <span className="ml-1">vs last period</span>
                    </div>
                </div>
                <div className="h-[40px] mt-2">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={ratingHistory}>
                            <Line type="monotone" dataKey="value" stroke={averageRating >= 4.3 ? "#10b981" : averageRating >= 3.8 ? "#eab308" : "#ef4444"} strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
};
