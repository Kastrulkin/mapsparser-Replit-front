export interface BusinessHealthData {
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

export interface BusinessAlert {
    type: 'stale_news' | 'stale_photos' | 'unanswered_reviews' | 'low_rating' | string;
    severity: 'info' | 'warning' | 'urgent';
    days_since?: number;
    threshold?: number;
    count?: number;
    rating?: number;
    message: string;
}

export interface BusinessLocationWithAlerts {
    business_id: string;
    business_name: string;
    business_type: string;
    rating: number | null;
    alerts: BusinessAlert[];
}

export interface BusinessHealthWidgetProps {
    businessId: string;
    className?: string;
    variant?: 'default' | 'compact';
}
