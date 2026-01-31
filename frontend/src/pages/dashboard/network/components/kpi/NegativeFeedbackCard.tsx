import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NetworkStats } from '../../data/mockData';
import { ArrowUp, ArrowDown } from "lucide-react";

interface NegativeFeedbackCardProps {
    stats: NetworkStats;
}

export const NegativeFeedbackCard: React.FC<NegativeFeedbackCardProps> = ({ stats }) => {
    const { negativeFeedbackRatio, negativeFeedbackTrend } = stats;

    const isGood = negativeFeedbackRatio < 5;
    const isBad = negativeFeedbackRatio > 15;
    const textColor = isGood ? "text-emerald-500" : isBad ? "text-red-500" : "text-yellow-500";

    // Neg trend going down is GOOD (Green), up is BAD (Red)
    const isTrendGood = negativeFeedbackTrend < 0;
    const trendColor = isTrendGood ? "text-emerald-500" : "text-red-500";
    const TrendIcon = isTrendGood ? ArrowDown : ArrowUp;

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Negative Feedback</CardTitle>
            </CardHeader>
            <CardContent>
                <div className={`text-2xl font-bold ${textColor}`}>
                    {negativeFeedbackRatio}%
                </div>
                <div className="flex items-center text-xs text-muted-foreground mt-1">
                    <TrendIcon className={`h-4 w-4 mr-1 ${trendColor}`} />
                    <span className={trendColor}>{Math.abs(negativeFeedbackTrend)}%</span>
                    <span className="ml-1">vs last period</span>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                    Target: &lt;5%
                </p>
            </CardContent>
        </Card>
    );
};
