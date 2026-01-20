
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { useApiData } from '../hooks/useApiData';
import { Star, AlertTriangle, TrendingUp, MapPin, MessageCircle, Image, Newspaper } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';
import { cn } from '../lib/utils';

interface NetworkHealthData {
    locations_count: number;
    avg_rating: number;
    total_reviews: number;
    unanswered_reviews_count: number;
    locations_with_alerts: number;
    alerts_breakdown: {
        stale_news: number;
        stale_photos: number;
        unanswered_reviews: number;
        low_rating: number;
    };
}

interface LocationAlert {
    type: string;
    severity: 'info' | 'warning' | 'urgent';
    days_since?: number;
    threshold?: number;
    count?: number;
    rating?: number;
    message: string;
}

interface LocationWithAlerts {
    business_id: string;
    business_name: string;
    business_type: string;
    rating: number | null;
    alerts: LocationAlert[];
}

interface NetworkHealthDashboardProps {
    networkId?: string | null;
    businessId?: string | null;
}

const NetworkHealthDashboard: React.FC<NetworkHealthDashboardProps> = ({ networkId, businessId }) => {
    const { t } = useLanguage();

    // Fetch network health metrics
    const { data: healthResponse, loading: loadingHealth, error: errorHealth } = useApiData<{ data: NetworkHealthData }>(
        '/api/network/health'
    );

    // Fetch locations with alerts
    const { data: alertsResponse, loading: loadingAlerts, error: errorAlerts } = useApiData<{ data: { locations: LocationWithAlerts[] } }>(
        '/api/network/locations-alerts'
    );

    const health = healthResponse?.data || {
        locations_count: 0,
        avg_rating: 0,
        total_reviews: 0,
        unanswered_reviews_count: 0,
        locations_with_alerts: 0,
        alerts_breakdown: {
            stale_news: 0,
            stale_photos: 0,
            unanswered_reviews: 0,
            low_rating: 0
        }
    };

    const locations = alertsResponse?.data?.locations || [];

    // Render metric card
    const MetricCard = ({
        title,
        value,
        icon: Icon,
        variant = 'default'
    }: {
        title: string;
        value: number | string;
        icon: any;
        variant?: 'default' | 'warning' | 'success';
    }) => (
        <Card className={cn(
            variant === 'warning' && 'border-orange-200 bg-orange-50/50',
            variant === 'success' && 'border-green-200 bg-green-50/50'
        )}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                    {title}
                </CardTitle>
                <Icon className={cn(
                    "h-4 w-4",
                    variant === 'warning' && 'text-orange-600',
                    variant === 'success' && 'text-green-600',
                    variant === 'default' && 'text-muted-foreground'
                )} />
            </CardHeader>
            <CardContent>
                <div className={cn(
                    "text-2xl font-bold",
                    variant === 'warning' && 'text-orange-700',
                    variant === 'success' && 'text-green-700'
                )}>
                    {value}
                </div>
            </CardContent>
        </Card>
    );

    // Get alert icon and color
    const getAlertDetails = (type: string) => {
        switch (type) {
            case 'stale_news':
                return { icon: Newspaper, color: 'text-orange-600', bgColor: 'bg-orange-100' };
            case 'stale_photos':
                return { icon: Image, color: 'text-orange-600', bgColor: 'bg-orange-100' };
            case 'unanswered_reviews':
                return { icon: MessageCircle, color: 'text-red-600', bgColor: 'bg-red-100' };
            case 'low_rating':
                return { icon: Star, color: 'text-yellow-600', bgColor: 'bg-yellow-100' };
            default:
                return { icon: AlertTriangle, color: 'text-gray-600', bgColor: 'bg-gray-100' };
        }
    };

    if (loadingHealth && !health) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <TrendingUp className="h-5 w-5" />
                        {t.networkHealth?.title || 'Состояние сети'}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="h-20 bg-muted/20 animate-pulse rounded-lg" />
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (errorHealth) {
        return (
            <Card className="border-destructive/20">
                <CardHeader>
                    <CardTitle className="text-destructive flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5" />
                        {t.common?.error || 'Ошибка'}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <Alert variant="destructive">
                        <AlertDescription>{errorHealth}</AlertDescription>
                    </Alert>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Overall Statistics */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="flex items-center gap-2 text-xl">
                                <TrendingUp className="h-5 w-5 text-primary" />
                                {t.networkHealth?.title || 'Состояние сети'}
                            </CardTitle>
                            <CardDescription>
                                {t.networkHealth?.description || 'Мониторинг здоровья всех точек сети'}
                            </CardDescription>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <MetricCard
                            title={t.networkHealth?.avgRating || 'Средний рейтинг'}
                            value={health.avg_rating.toFixed(1)}
                            icon={Star}
                            variant={health.avg_rating >= 4.0 ? 'success' : 'default'}
                        />
                        <MetricCard
                            title={t.networkHealth?.totalReviews || 'Всего отзывов'}
                            value={health.total_reviews}
                            icon={MessageCircle}
                        />
                        <MetricCard
                            title={t.networkHealth?.locationsCount || 'Точек сети'}
                            value={health.locations_count}
                            icon={MapPin}
                        />
                        <MetricCard
                            title={t.networkHealth?.unansweredReviews || 'Неотвеченных отзывов'}
                            value={health.unanswered_reviews_count}
                            icon={AlertTriangle}
                            variant={health.unanswered_reviews_count > 0 ? 'warning' : 'default'}
                        />
                    </div>
                </CardContent>
            </Card>

            {/* Locations Needing Attention */}
            {locations.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <AlertTriangle className="h-5 w-5 text-orange-600" />
                            {t.networkHealth?.needsAttention || 'Требуют внимания'}
                        </CardTitle>
                        <CardDescription>
                            {t.networkHealth?.locationsRequiringAction?.replace('{{count}}', locations.length.toString()) || `${locations.length} точек требуют внимания`}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {locations.map((location) => {
                                return (
                                    <div
                                        key={location.business_id}
                                        className="p-4 border rounded-lg hover:shadow-md transition-shadow"
                                    >
                                        <div className="flex items-start justify-between mb-3">
                                            <div>
                                                <h4 className="font-semibold text-lg">{location.business_name}</h4>
                                                {location.rating && (
                                                    <div className="flex items-center gap-1 text-sm text-muted-foreground mt-1">
                                                        <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                                                        <span>{location.rating.toFixed(1)}</span>
                                                    </div>
                                                )}
                                            </div>
                                            <Badge variant="outline" className="text-xs">
                                                {location.alerts.length} {t.networkHealth?.alerts?.count || 'алерта'}
                                            </Badge>
                                        </div>

                                        <div className="space-y-2">
                                            {location.alerts.map((alert, idx) => {
                                                const { icon: AlertIcon, color, bgColor } = getAlertDetails(alert.type);
                                                return (
                                                    <div
                                                        key={idx}
                                                        className={cn(
                                                            "flex items-start gap-3 p-3 rounded-md",
                                                            bgColor
                                                        )}
                                                    >
                                                        <AlertIcon className={cn("h-5 w-5 flex-shrink-0 mt-0.5", color)} />
                                                        <div className="flex-1">
                                                            <p className="text-sm font-medium">{alert.message}</p>
                                                            {alert.days_since && alert.threshold && (
                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                    {t.networkHealth?.alerts?.daysInfo
                                                                        ?.replace('{{days}}', alert.days_since.toString())
                                                                        ?.replace('{{threshold}}', alert.threshold.toString())
                                                                        || `${alert.days_since} дней (порог: ${alert.threshold})`}
                                                                </p>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* No alerts */}
            {locations.length === 0 && !loadingAlerts && (
                <Card className="border-green-200 bg-green-50/50">
                    <CardContent className="flex items-center gap-3 py-6">
                        <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                            <TrendingUp className="h-6 w-6 text-green-600" />
                        </div>
                        <div>
                            <p className="font-semibold text-green-900">
                                {t.networkHealth?.allGood || 'Всё отлично!'}
                            </p>
                            <p className="text-sm text-green-700">
                                {t.networkHealth?.noAlertsMessage || 'Все точки сети в хорошем состоянии'}
                            </p>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

export default NetworkHealthDashboard;
