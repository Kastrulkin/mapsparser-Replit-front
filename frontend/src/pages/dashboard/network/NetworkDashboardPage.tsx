import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardHeader } from './components/DashboardHeader';
import { KPIGrid } from './components/KPIGrid';
import { AnalyticsTimeline } from './components/AnalyticsTimeline';
import { NetworkMap } from './components/NetworkMap';
import { SalonTable } from './components/SalonTable';
import { NetworkStats, SalonData } from './data/mockData';
import { DateRange } from "react-day-picker";
import { addDays } from "date-fns";

interface NetworkDashboardPageProps {
    embedded?: boolean;
    businessId?: string | null;
}

interface HealthResponse {
    success: boolean;
    data?: {
        locations_count: number;
        avg_rating: number;
        total_reviews: number;
        unanswered_reviews_count: number;
    };
}

interface MetricsHistoryResponse {
    history?: Array<{
        date: string;
        rating: number | null;
        reviews_count: number | null;
    }>;
}

interface NetworkLocation {
    id: string;
    name?: string;
    address?: string;
    geo_lat?: string;
    geo_lon?: string;
    rating?: string | number;
    reviews_count?: string | number;
}

interface NetworkLocationsResponse {
    success: boolean;
    network_id?: string | null;
    locations?: NetworkLocation[];
}

export const NetworkDashboardPage: React.FC<NetworkDashboardPageProps> = ({ embedded = false, businessId }) => {
    const navigate = useNavigate();
    const today = new Date();
    const [date, setDate] = useState<DateRange | undefined>({
        from: addDays(today, -20),
        to: today,
    });

    const [viewMode, setViewMode] = useState<'list' | 'map' | 'grid'>('list');
    const [crmConnected] = useState(false);
    const [health, setHealth] = useState<HealthResponse['data'] | null>(null);
    const [timeline, setTimeline] = useState<Array<{ date: string; rating: number; reviews: number }>>([]);
    const [salons, setSalons] = useState<SalonData[]>([]);

    const roundRating = (value: number) => {
        if (!Number.isFinite(value)) {
            return 0;
        }
        return Math.round(value * 100) / 100;
    };

    useEffect(() => {
        const loadDashboard = async () => {
            if (!businessId) {
                setHealth(null);
                setTimeline([]);
                setSalons([]);
                return;
            }

            try {
                const token = localStorage.getItem('auth_token');
                const headers = { Authorization: `Bearer ${token || ''}` };

                const locationsRes = await fetch(`/api/business/${businessId}/network-locations`, { headers });
                const locationsJson: NetworkLocationsResponse = await locationsRes.json().catch(() => ({ success: false, locations: [] }));
                const locations = (locationsJson.locations || []);
                const networkId = String(locationsJson.network_id || '').trim();
                const isNetworkView = Boolean(networkId) && locations.length > 1;

                const mappedSalons: SalonData[] = locations.map((loc) => {
                    const lat = parseFloat(String(loc.geo_lat || '').replace(',', '.'));
                    const lon = parseFloat(String(loc.geo_lon || '').replace(',', '.'));
                    const rating = Number(loc.rating || 0);
                    const reviews = Number(loc.reviews_count || 0);
                    return {
                        id: loc.id,
                        name: loc.name || 'Точка',
                        address: loc.address || '—',
                        lat: Number.isFinite(lat) ? lat : NaN,
                        lon: Number.isFinite(lon) ? lon : NaN,
                        rating: roundRating(rating),
                        ratingTrend: 0,
                        status: 'active',
                        reviews: Number.isFinite(reviews) ? reviews : 0,
                        negativePercent: 0,
                        recentReviews: [],
                    };
                });

                const [healthRes, historyRes] = await Promise.all([
                    fetch(
                        isNetworkView
                            ? `/api/network/health?network_id=${encodeURIComponent(networkId)}`
                            : `/api/network/health?business_id=${businessId}`,
                        { headers }
                    ),
                    fetch(
                        `/api/business/${businessId}/metrics-history${isNetworkView ? '?scope=network' : ''}`,
                        { headers }
                    ),
                ]);

                const healthJson: HealthResponse = await healthRes.json().catch(() => ({ success: false }));
                const historyJson: MetricsHistoryResponse = await historyRes.json().catch(() => ({ history: [] }));

                setHealth(healthJson.data || null);

                const timelinePoints = (historyJson.history || [])
                    .slice(0, 7)
                    .reverse()
                    .map((item) => ({
                        date: item.date?.slice(5) || '—',
                        rating: Number(item.rating || 0),
                        reviews: Number(item.reviews_count || 0),
                    }));
                setTimeline(timelinePoints);

                if (mappedSalons.length === 0) {
                    const avgRating = Number(healthJson.data?.avg_rating || 0);
                    const totalReviews = Number(healthJson.data?.total_reviews || 0);
                    setSalons([{
                        id: businessId,
                        name: 'Текущий бизнес',
                        address: '—',
                        lat: NaN,
                        lon: NaN,
                        rating: avgRating,
                        ratingTrend: 0,
                        status: 'active',
                        reviews: totalReviews,
                        negativePercent: 0,
                        recentReviews: [],
                    }]);
                } else {
                    setSalons(mappedSalons);
                }
            } catch {
                setHealth(null);
                setTimeline([]);
                setSalons([]);
            }
        };

        loadDashboard();
    }, [businessId]);

    const stats: NetworkStats = useMemo(() => {
        const totalSalons = salons.length;
        const activeSalons = salons.filter((s) => s.status === 'active').length;
        const problemSalons = salons.filter((s) => s.status === 'problem').length;
        const offlineSalons = salons.filter((s) => s.status === 'offline').length;
        const ratings = salons.map((s) => s.rating).filter((r) => Number.isFinite(r) && r > 0).sort((a, b) => a - b);
        const averageRating = Number(health?.avg_rating || (ratings.length ? ratings.reduce((a, b) => a + b, 0) / ratings.length : 0));
        const totalReviews = Number(health?.total_reviews || salons.reduce((sum, s) => sum + s.reviews, 0));
        const unanswered = Number(health?.unanswered_reviews_count || 0);
        const negativeFeedbackRatio = totalReviews > 0 ? Math.round((unanswered / totalReviews) * 100) : 0;

        const quantile = (arr: number[], q: number) => {
            if (!arr.length) return 0;
            const pos = (arr.length - 1) * q;
            const base = Math.floor(pos);
            const rest = pos - base;
            const next = arr[base + 1] ?? arr[base];
            return Number((arr[base] + rest * (next - arr[base])).toFixed(1));
        };

        const historyRatings = timeline.map((t) => t.rating).filter((v) => v > 0);
        const current = historyRatings[historyRatings.length - 1] || averageRating;
        const prev = historyRatings[historyRatings.length - 2] || current;
        const ratingTrend = prev > 0 ? Number((((current - prev) / prev) * 100).toFixed(1)) : 0;

        return {
            totalSalons,
            activeSalons,
            problemSalons,
            offlineSalons,
            averageRating: Number(averageRating.toFixed(1)),
            ratingTrend,
            ratingHistory: historyRatings.length ? historyRatings.map((value) => ({ value })) : [{ value: Number(averageRating.toFixed(1)) }],
            negativeFeedbackRatio,
            negativeFeedbackTrend: 0,
            retentionRate: undefined,
            retentionTrend: undefined,
            ratingDistribution: {
                p50: quantile(ratings, 0.5),
                p75: quantile(ratings, 0.75),
                p90: quantile(ratings, 0.9),
                p99: quantile(ratings, 0.99),
            },
        };
    }, [health, salons, timeline]);

    const isSingleBusinessView = useMemo(() => {
        const locationsCount = Number(health?.locations_count || 0);
        if (Number.isFinite(locationsCount) && locationsCount > 0) {
            return locationsCount <= 1;
        }
        return salons.length <= 1;
    }, [health?.locations_count, salons.length]);

    const handleOpenDashboard = (targetBusinessId: string) => {
        if (!targetBusinessId) return;
        localStorage.setItem('selectedBusinessId', targetBusinessId);
        navigate('/dashboard/card');
    };

    return (
        <div className={embedded ? "space-y-4" : "flex-1 space-y-4 p-8 pt-6"}>
            <DashboardHeader
                date={date}
                setDate={setDate}
                viewMode={viewMode}
                setViewMode={setViewMode}
                isSingleBusiness={isSingleBusinessView}
            />

            <div className="space-y-4">
                <KPIGrid stats={stats} crmConnected={crmConnected} />

                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                    <AnalyticsTimeline data={timeline} />
                    <NetworkMap locations={salons} />
                </div>

                <div className="space-y-4">
                    <SalonTable salons={salons} onOpenDashboard={handleOpenDashboard} />
                </div>
            </div>
        </div>
    );
}
