import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NetworkStats } from '../../data/mockData';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Info } from "lucide-react";

interface RatingDistributionCardProps {
    stats: NetworkStats;
}

export const RatingDistributionCard: React.FC<RatingDistributionCardProps> = ({ stats }) => {
    const { ratingDistribution } = stats;

    const getBarColor = (val: number) => {
        if (val >= 4.5) return "bg-emerald-500";
        if (val >= 4.0) return "bg-emerald-400"; // lighter green
        if (val >= 3.5) return "bg-yellow-400";
        return "bg-red-500";
    };

    const items = [
        { label: 'P50 (Median)', value: ratingDistribution.p50, desc: "50% of feedback is above this score" },
        { label: 'P90', value: ratingDistribution.p90, desc: "90% of feedback is above this score (excludes bottom 10%)" },
        { label: 'P99 (Risk)', value: ratingDistribution.p99, desc: "Only bottom 1% is worse than this. WATCH THIS." },
    ];

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div className="flex items-center gap-2">
                    <CardTitle className="text-sm font-medium">Rating Distribution</CardTitle>
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger><Info className="h-3 w-3 text-muted-foreground" /></TooltipTrigger>
                            <TooltipContent><p className="max-w-[200px] text-xs">Statistical spread of reviews. P99 shows the worst 1% of experiences.</p></TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                </div>
            </CardHeader>
            <CardContent className="space-y-3 pt-2">
                {items.map((item, idx) => (
                    <div key={idx} className="space-y-1">
                        <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">{item.label}</span>
                            <span className="font-semibold">{item.value} ⭐</span>
                        </div>
                        <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full ${getBarColor(item.value)}`}
                                style={{ width: `${(item.value / 5) * 100}%` }}
                            />
                        </div>
                    </div>
                ))}
            </CardContent>
        </Card>
    );
};
