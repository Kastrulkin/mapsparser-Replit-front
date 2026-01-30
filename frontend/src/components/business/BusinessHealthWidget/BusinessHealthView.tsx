import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, Star, MessageCircle, Newspaper, Image, TrendingUp, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BusinessHealthData, BusinessLocationWithAlerts, BusinessAlert } from './types';
import { Skeleton } from '@/components/ui/skeleton';

interface BusinessHealthViewProps {
    health?: BusinessHealthData;
    locationAlerts?: BusinessLocationWithAlerts | null;
    isLoading: boolean;
    error?: Error | null;
    className?: string;
}

const getAlertDetails = (type: string) => {
    switch (type) {
        case 'stale_news':
            return { icon: Newspaper, color: 'text-orange-600', bgColor: 'bg-orange-50', borderColor: 'border-orange-200' };
        case 'stale_photos':
            return { icon: Image, color: 'text-orange-600', bgColor: 'bg-orange-50', borderColor: 'border-orange-200' };
        case 'unanswered_reviews':
            return { icon: MessageCircle, color: 'text-red-600', bgColor: 'bg-red-50', borderColor: 'border-red-200' };
        case 'low_rating':
            return { icon: Star, color: 'text-yellow-600', bgColor: 'bg-yellow-50', borderColor: 'border-yellow-200' };
        default:
            return { icon: AlertTriangle, color: 'text-gray-600', bgColor: 'bg-gray-50', borderColor: 'border-gray-200' };
    }
};

export const BusinessHealthView: React.FC<BusinessHealthViewProps> = ({
    health,
    locationAlerts,
    isLoading,
    error,
    className
}) => {
    if (isLoading) {
        return (
            <Card className={className}>
                <CardHeader>
                    <Skeleton className="h-6 w-32" />
                    <Skeleton className="h-4 w-48 mt-2" />
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <Skeleton className="h-16 w-full" />
                        <Skeleton className="h-16 w-full" />
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return null; // Graceful degradation: render nothing on error (or minimal fallback)
    }

    const alerts = locationAlerts?.alerts || [];
    const hasAlerts = alerts.length > 0;
    const rating = health?.avg_rating || 0;

    return (
        <Card className={cn("overflow-hidden", className)}>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-lg">
                            <TrendingUp className="h-5 w-5 text-primary" />
                            Здоровье бизнеса
                        </CardTitle>
                        <CardDescription>
                            Текущее состояние и рекомендации
                        </CardDescription>
                    </div>
                    {rating > 0 && (
                        <div className="flex items-center gap-1 bg-secondary/50 px-2 py-1 rounded-md">
                            <Star className="h-4 w-4 fill-primary text-primary" />
                            <span className="font-semibold">{rating.toFixed(1)}</span>
                        </div>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Main Health Status */}
                    {!hasAlerts ? (
                        <div className="flex items-center gap-4 p-4 rounded-lg bg-green-50 border border-green-100 dark:bg-green-900/10 dark:border-green-900/30">
                            <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                                <CheckCircle2 className="h-6 w-6 text-green-600" />
                            </div>
                            <div>
                                <h4 className="font-medium text-green-900 dark:text-green-300">Всё отлично!</h4>
                                <p className="text-sm text-green-700 dark:text-green-400">
                                    Все показатели в норме, продолжайте в том же духе.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-medium text-muted-foreground">Требует внимания ({alerts.length})</span>
                            </div>
                            {alerts.map((alert, idx) => {
                                const { icon: Icon, color, bgColor, borderColor } = getAlertDetails(alert.type);
                                return (
                                    <div key={idx} className={cn("flex items-start gap-3 p-3 rounded-md border", bgColor, borderColor)}>
                                        <Icon className={cn("h-5 w-5 mt-0.5 shrink-0", color)} />
                                        <div className="flex-1">
                                            <p className="text-sm font-medium text-foreground">{alert.message}</p>
                                            {alert.days_since !== undefined && (
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    Не обновлялось {alert.days_since} дн.
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Simple Stats Grid */}
                    <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t">
                        <div className="flex flex-col">
                            <span className="text-xs text-muted-foreground uppercase tracking-wider">Отзывы</span>
                            <div className="flex items-center gap-2 mt-1">
                                <MessageCircle className="h-4 w-4 text-muted-foreground" />
                                <span className="text-xl font-bold">{health?.total_reviews || 0}</span>
                            </div>
                        </div>
                        <div className="flex flex-col">
                            <span className="text-xs text-muted-foreground uppercase tracking-wider">Неотвеченные</span>
                            <div className="flex items-center gap-2 mt-1">
                                <AlertTriangle className={cn("h-4 w-4", (health?.unanswered_reviews_count || 0) > 0 ? "text-red-500" : "text-muted-foreground")} />
                                <span className={cn("text-xl font-bold", (health?.unanswered_reviews_count || 0) > 0 ? "text-red-600" : "")}>
                                    {health?.unanswered_reviews_count || 0}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
