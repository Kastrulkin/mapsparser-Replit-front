export interface NetworkStats {
    totalSalons: number;
    activeSalons: number;
    problemSalons: number;
    offlineSalons: number;
    averageRating: number;
    ratingTrend: number; // percent change
    ratingHistory: { value: number }[]; // sparkline data
    negativeFeedbackRatio: number; // in percent (e.g. 12.5)
    negativeFeedbackTrend: number; // percent change
    retentionRate?: number; // percent (can be undefined if no CRM)
    retentionTrend?: number;
    ratingDistribution: {
        p50: number;
        p75: number;
        p90: number;
        p99: number;
    };
}

export const mockNetworkStats: NetworkStats = {
    totalSalons: 18,
    activeSalons: 15,
    problemSalons: 2,
    offlineSalons: 1,
    averageRating: 4.2,
    ratingTrend: -0.3,
    ratingHistory: [
        { value: 4.5 }, { value: 4.4 }, { value: 4.4 }, { value: 4.3 }, { value: 4.3 }, { value: 4.2 }, { value: 4.2 }
    ],
    negativeFeedbackRatio: 12,
    negativeFeedbackTrend: -2,
    retentionRate: 8.5,
    retentionTrend: 1.2,
    ratingDistribution: {
        p50: 4.6,
        p75: 4.4,
        p90: 3.9,
        p99: 2.5
    }
};

export const mockTimelineData = [
    { date: 'Jan 20', rating: 4.5, reviews: 12, negative: 1 },
    { date: 'Jan 21', rating: 4.4, reviews: 15, negative: 2 },
    { date: 'Jan 22', rating: 4.4, reviews: 8, negative: 0 },
    { date: 'Jan 23', rating: 4.3, reviews: 20, negative: 4 }, // Drop
    { date: 'Jan 24', rating: 4.3, reviews: 18, negative: 3 },
    { date: 'Jan 25', rating: 4.2, reviews: 25, negative: 6 }, // Further drop
    { date: 'Jan 26', rating: 4.2, reviews: 14, negative: 1 },
];

export interface Review {
    id: string;
    author: string;
    rating: number;
    text: string;
    date: string;
    sentiment: 'positive' | 'negative' | 'neutral';
}

export interface SalonData {
    id: string;
    name: string;
    address: string;
    lat: number;
    lon: number;
    rating: number;
    ratingTrend: number;
    status: 'active' | 'problem' | 'offline';
    reviews: number;
    negativePercent: number;
    recentReviews: Review[];
}

export const mockSalons: SalonData[] = [
    {
        id: '1', name: 'BeautyBot Nevsky', address: 'Nevsky Prospect, 25', lat: 59.9343, lon: 30.3351, rating: 4.8, ratingTrend: 2, status: 'active', reviews: 124, negativePercent: 1.5,
        recentReviews: [
            { id: 'r1', author: 'Olga K.', rating: 5, text: 'Amazing service! Will come again.', date: '2 days ago', sentiment: 'positive' },
            { id: 'r2', author: 'Ivan D.', rating: 5, text: 'Best coffee and haircut.', date: '3 days ago', sentiment: 'positive' }
        ]
    },
    {
        id: '2', name: 'BeautyBot Petrogradka', address: 'Bolshoy Prospect PS, 45', lat: 59.9643, lon: 30.3151, rating: 4.6, ratingTrend: 0, status: 'active', reviews: 89, negativePercent: 4,
        recentReviews: [
            { id: 'r3', author: 'Elena S.', rating: 4, text: 'Good, but waited 10 mins.', date: '1 day ago', sentiment: 'neutral' }
        ]
    },
    {
        id: '3', name: 'BeautyBot Moskovsky', address: 'Moskovsky Pr, 112', lat: 59.8543, lon: 30.3251, rating: 3.9, ratingTrend: -5, status: 'problem', reviews: 215, negativePercent: 18,
        recentReviews: [
            { id: 'r4', author: 'Anonymous', rating: 1, text: 'Rude staff, dirty floor.', date: 'Yesterday', sentiment: 'negative' },
            { id: 'r5', author: 'Mike', rating: 2, text: 'Not worth the money.', date: '2 days ago', sentiment: 'negative' }
        ]
    },
    { id: '4', name: 'BeautyBot Vasileostrovskaya', address: '7th Line VO, 30', lat: 59.9400, lon: 30.2700, rating: 4.9, ratingTrend: 1, status: 'active', reviews: 56, negativePercent: 0, recentReviews: [] },
    { id: '5', name: 'BeautyBot Ozerki', address: 'Engels Pr, 120', lat: 60.0300, lon: 30.3200, rating: 4.2, ratingTrend: -1, status: 'active', reviews: 110, negativePercent: 8, recentReviews: [] },
    {
        id: '6', name: 'BeautyBot Kupchino', address: 'Balkanskaya Sq, 5', lat: 59.8300, lon: 30.3800, rating: 3.5, ratingTrend: -10, status: 'problem', reviews: 340, negativePercent: 25,
        recentReviews: [
            { id: 'r6', author: 'Anna', rating: 1, text: 'Horrible experience.', date: 'Today', sentiment: 'negative' }
        ]
    },
    { id: '7', name: 'BeautyBot Murino', address: 'Aviatorov Baltiki, 3', lat: 60.0500, lon: 30.4500, rating: 4.5, ratingTrend: 0, status: 'offline', reviews: 0, negativePercent: 0, recentReviews: [] },
];

export const mockMapLocations = mockSalons; // Backward compatibility alias

export const mockNoCrmStats: NetworkStats = {
    ...mockNetworkStats,
    retentionRate: undefined,
    retentionTrend: undefined
}
