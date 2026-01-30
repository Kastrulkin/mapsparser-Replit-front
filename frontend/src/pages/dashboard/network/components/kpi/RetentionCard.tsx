import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { NetworkStats } from '../../data/mockData';
import { ArrowUp, ArrowDown, Lock } from "lucide-react";

interface RetentionCardProps {
    stats: NetworkStats;
}

export const RetentionCard: React.FC<RetentionCardProps> = ({ stats }) => {
    const { retentionRate, retentionTrend } = stats;
    const hasData = retentionRate !== undefined;

    return (
        <Card className="relative overflow-hidden">
            {!hasData && (
                <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-background/50 backdrop-blur-sm p-4 text-center">
                    <Lock className="h-6 w-6 mb-2 text-muted-foreground" />
                    <p className="text-xs font-semibold mb-2">CRM Integration Required</p>
                    <Button size="sm" variant="outline" className="h-7 text-xs">
                        Connect CRM
                    </Button>
                </div>
            )}

            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Retention Potential</CardTitle>
            </CardHeader>
            <CardContent className={!hasData ? "opacity-40" : ""}>
                <div className="text-2xl font-bold">
                    {hasData ? `${retentionRate}%` : "—"}
                </div>
                {hasData && retentionTrend !== undefined && (
                    <div className="flex items-center text-xs text-muted-foreground mt-1">
                        {retentionTrend > 0 ? (
                            <ArrowUp className="h-4 w-4 text-emerald-500 mr-1" />
                        ) : (
                            <ArrowDown className="h-4 w-4 text-red-500 mr-1" />
                        )}
                        <span className={retentionTrend > 0 ? "text-emerald-500" : "text-red-500"}>
                            {Math.abs(retentionTrend)}%
                        </span>
                        <span className="ml-1">returning clients</span>
                    </div>
                )}
                <p className="text-xs text-muted-foreground mt-2">
                    Benchmarks: &gt;6%
                </p>
            </CardContent>
        </Card>
    );
};
