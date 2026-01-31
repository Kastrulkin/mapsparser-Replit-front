import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useLanguage } from '@/i18n/LanguageContext';
import { MoreHorizontal, Plus, Trash2 } from 'lucide-react';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AddMetricModal } from './AddMetricModal';
import { useToast } from '@/components/ui/use-toast';

// --- TYPES ---

interface MetricHistoryItem {
    id: string;
    date: string;
    rating: number | null;
    reviews_count: number | null;
    photos_count: number | null;
    news_count: number | null;
    unanswered_reviews_count: number | null;
    source: string;
    created_at: string;
}

type MetricType = 'rating' | 'reviews' | 'photos' | 'news' | 'unanswered';

interface MetricsHistoryChartsProps {
    businessId: string;
}

export const MetricsHistoryCharts: React.FC<MetricsHistoryChartsProps> = ({ businessId }) => {
    const { language, t } = useLanguage();
    const { toast } = useToast();

    const [history, setHistory] = useState<MetricHistoryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedMetric, setSelectedMetric] = useState<MetricType>('rating');
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);

    // --- FETCH DATA ---

    const fetchHistory = async () => {
        try {
            setLoading(true);
            const token = localStorage.getItem('token');
            const response = await fetch(`/api/business/${businessId}/metrics-history`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) throw new Error('Failed to fetch history');

            const data = await response.json();
            if (data.success) {
                setHistory(data.history);
            }
        } catch (error) {
            console.error('Error fetching metrics history:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (businessId) {
            fetchHistory();
        }
    }, [businessId]);

    // --- HANDLERS ---

    const handleDeleteMetric = async (metricId: string) => {
        if (!confirm(t.common.confirmDelete)) return;

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`/api/business/${businessId}/metrics-history/${metricId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Metric deleted",
                });
                fetchHistory();
            } else {
                throw new Error('Failed to delete');
            }
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to delete metric",
                variant: "destructive"
            });
        }
    };

    // --- CONFIG ---

    const getMetricConfig = (type: MetricType) => {
        const configs = {
            rating: {
                label: t.dashboard.progress.charts.metrics.rating,
                icon: '⭐',
                color: '#f59e0b',
                unit: '',
                format: (value: number) => value.toFixed(1)
            },
            reviews: {
                label: t.dashboard.progress.charts.metrics.reviews,
                icon: '💬',
                color: '#3b82f6',
                unit: '',
                format: (value: number) => value.toString()
            },
            photos: {
                label: t.dashboard.progress.charts.metrics.photos,
                icon: '📸',
                color: '#8b5cf6',
                unit: '',
                format: (value: number) => value.toString()
            },
            news: {
                label: t.dashboard.progress.charts.metrics.news,
                icon: '📰',
                color: '#10b981',
                unit: '',
                format: (value: number) => value.toString()
            },
            unanswered: {
                label: language === 'ru' ? 'Неотвеченные' : 'Unanswered',
                icon: '⚠️',
                color: '#ef4444',
                unit: '',
                format: (value: number) => value.toString()
            }
        };
        return configs[type];
    };

    const currentConfig = getMetricConfig(selectedMetric);

    const getChartData = (type: MetricType) => {
        let key: keyof MetricHistoryItem;

        if (type === 'rating') key = 'rating';
        else if (type === 'reviews') key = 'reviews_count';
        else if (type === 'photos') key = 'photos_count';
        else if (type === 'news') key = 'news_count';
        else if (type === 'unanswered') key = 'unanswered_reviews_count';
        else key = 'rating'; // fallback

        return history
            .filter(entry => entry[key] !== null)
            .map(entry => ({
                date: new Date(entry.date).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US', { day: 'numeric', month: 'short' }),
                value: entry[key],
                fullDate: entry.date
            }))
            .reverse();
    };

    const chartData = getChartData(selectedMetric);

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <Skeleton className="h-8 w-1/3" />
                </CardHeader>
                <CardContent>
                    <Skeleton className="h-[300px] w-full" />
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Metric Selector Tabs */}
            <div className="flex flex-wrap gap-2">
                {(['rating', 'reviews', 'unanswered', 'photos', 'news'] as MetricType[]).map((type) => {
                    const config = getMetricConfig(type);
                    const isActive = selectedMetric === type;

                    // Get latest value
                    const latestVal = history.length > 0 ? (
                        type === 'rating' ? history[0].rating :
                            type === 'reviews' ? history[0].reviews_count :
                                type === 'photos' ? history[0].photos_count :
                                    type === 'news' ? history[0].news_count :
                                        type === 'unanswered' ? history[0].unanswered_reviews_count : 0
                    ) : null;

                    return (
                        <Button
                            key={type}
                            variant={isActive ? "default" : "outline"}
                            className={`h-auto py-3 px-4 flex flex-col items-start gap-1 min-w-[120px] ${isActive ? '' : 'hover:bg-muted/50'}`}
                            onClick={() => setSelectedMetric(type)}
                        >
                            <div className="flex items-center gap-2 text-sm font-medium opacity-80">
                                <span>{config.icon}</span>
                                <span>{config.label}</span>
                            </div>
                            <div className="text-xl font-bold">
                                {latestVal !== null ? config.format(latestVal as number) : '-'}
                            </div>
                        </Button>
                    );
                })}

                <Button
                    variant="ghost"
                    className="h-auto py-3 px-4 flex flex-col items-center justify-center min-w-[120px] border border-dashed ml-auto"
                    onClick={() => setIsAddModalOpen(true)}
                >
                    <Plus className="h-5 w-5 mb-1" />
                    <span className="text-xs text-muted-foreground">{t.common.add}</span>
                </Button>
            </div>

            {/* Main Chart Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        {currentConfig.icon} {currentConfig.label}
                        <span className="text-sm font-normal text-muted-foreground ml-2">
                            ({language === 'ru' ? 'Динамика за 30 дней' : '30 days trend'})
                        </span>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-[350px] w-full">
                        {chartData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                                    <XAxis
                                        dataKey="date"
                                        tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }}
                                        tickLine={false}
                                        axisLine={false}
                                        dy={10}
                                    />
                                    <YAxis
                                        domain={['auto', 'auto']}
                                        tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }}
                                        tickLine={false}
                                        axisLine={false}
                                        dx={-10}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: 'hsl(var(--popover))',
                                            borderColor: 'hsl(var(--border))',
                                            borderRadius: 'var(--radius)',
                                            color: 'hsl(var(--popover-foreground))'
                                        }}
                                        labelStyle={{ color: 'hsl(var(--muted-foreground))' }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="value"
                                        stroke={currentConfig.color}
                                        strokeWidth={3}
                                        dot={{ r: 4, fill: currentConfig.color, strokeWidth: 2, stroke: 'hsl(var(--background))' }}
                                        activeDot={{ r: 6, strokeWidth: 0 }}
                                        animationDuration={1000}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-muted-foreground">
                                {t.common.noData}
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Manual Data Table */}
            <div className="mt-8">
                <h3 className="text-lg font-semibold mb-4">{t.dashboard.progress.historyTable}</h3>
                <div className="rounded-md border">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b bg-muted/50">
                                <th className="h-10 px-4 text-left font-medium">{t.common.date}</th>
                                <th className="h-10 px-4 text-left font-medium">{t.dashboard.progress.charts.metrics.rating}</th>
                                <th className="h-10 px-4 text-left font-medium">{t.dashboard.progress.charts.metrics.reviews}</th>
                                <th className="h-10 px-4 text-left font-medium">{language === 'ru' ? 'Неотвеченные' : 'Unanswered'}</th>
                                <th className="h-10 px-4 text-left font-medium">{t.common.source}</th>
                                <th className="h-10 px-4 text-right font-medium">{t.common.actions}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {history.map((item) => (
                                <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                                    <td className="p-4">{new Date(item.date).toLocaleDateString()}</td>
                                    <td className="p-4 font-medium">{item.rating?.toFixed(1) || '-'}</td>
                                    <td className="p-4">{item.reviews_count || '-'}</td>
                                    <td className="p-4 text-red-500 font-medium">{item.unanswered_reviews_count ?? '-'}</td>
                                    <td className="p-4 text-muted-foreground">
                                        {item.source === 'parsing' ? 'Авто' : 'Ручной'}
                                    </td>
                                    <td className="p-4 text-right">
                                        {item.source === 'manual' && (
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" className="h-8 w-8 p-0">
                                                        <span className="sr-only">Open menu</span>
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem
                                                        className="text-destructive focus:text-destructive"
                                                        onClick={() => handleDeleteMetric(item.id)}
                                                    >
                                                        <Trash2 className="mr-2 h-4 w-4" />
                                                        {t.common.delete}
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <AddMetricModal
                isOpen={isAddModalOpen}
                onClose={() => setIsAddModalOpen(false)}
                onSuccess={fetchHistory}
                businessId={businessId}
            />
        </div>
    );
};
