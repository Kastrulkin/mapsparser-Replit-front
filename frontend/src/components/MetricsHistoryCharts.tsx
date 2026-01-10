import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    Area, AreaChart
} from 'recharts';
import { TrendingUp, TrendingDown, Plus, Trash2, Calendar } from 'lucide-react';
import { newAuth } from '@/lib/auth_new';
import { motion, AnimatePresence } from 'framer-motion';

interface MetricEntry {
    id: string;
    date: string;
    rating: number | null;
    reviews_count: number | null;
    photos_count: number | null;
    news_count: number | null;
    source: 'parsing' | 'manual';
    created_at: string;
}

interface MetricsHistoryChartsProps {
    businessId?: string;
}

type MetricType = 'rating' | 'reviews' | 'photos' | 'news';

export const MetricsHistoryCharts: React.FC<MetricsHistoryChartsProps> = ({ businessId }) => {
    const [history, setHistory] = useState<MetricEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedMetric, setSelectedMetric] = useState<MetricType>('rating');
    const [showAddModal, setShowAddModal] = useState(false);
    const [newEntry, setNewEntry] = useState({
        date: new Date().toISOString().split('T')[0],
        rating: '',
        reviews_count: '',
        photos_count: '',
        news_count: ''
    });

    useEffect(() => {
        if (businessId) {
            loadHistory();
        }
    }, [businessId]);

    const loadHistory = async () => {
        if (!businessId) return;
        try {
            setLoading(true);
            const data = await newAuth.makeRequest(`/business/${businessId}/metrics-history`, { method: 'GET' });
            setHistory(data.history || []);
        } catch (error) {
            console.error('Error loading metrics history:', error);
        } finally {
            setLoading(false);
        }
    };

    const addManualEntry = async () => {
        if (!businessId) return;
        try {
            await newAuth.makeRequest(`/business/${businessId}/metrics-history`, {
                method: 'POST',
                body: JSON.stringify({
                    date: newEntry.date,
                    rating: newEntry.rating ? parseFloat(newEntry.rating) : null,
                    reviews_count: newEntry.reviews_count ? parseInt(newEntry.reviews_count) : null,
                    photos_count: newEntry.photos_count ? parseInt(newEntry.photos_count) : null,
                    news_count: newEntry.news_count ? parseInt(newEntry.news_count) : null
                })
            });
            setShowAddModal(false);
            setNewEntry({
                date: new Date().toISOString().split('T')[0],
                rating: '',
                reviews_count: '',
                photos_count: '',
                news_count: ''
            });
            await loadHistory();
        } catch (error) {
            console.error('Error adding metric:', error);
        }
    };

    const deleteEntry = async (entryId: string) => {
        if (!businessId) return;
        if (!confirm('Удалить эту запись?')) return;
        try {
            await newAuth.makeRequest(`/business/${businessId}/metrics-history/${entryId}`, {
                method: 'DELETE'
            });
            await loadHistory();
        } catch (error) {
            console.error('Error deleting metric:', error);
        }
    };

    const getMetricConfig = (type: MetricType) => {
        const configs = {
            rating: {
                label: 'Рейтинг',
                icon: '⭐',
                color: '#f59e0b',
                unit: '',
                format: (value: number) => value.toFixed(1)
            },
            reviews: {
                label: 'Отзывы',
                icon: '💬',
                color: '#3b82f6',
                unit: '',
                format: (value: number) => value.toString()
            },
            photos: {
                label: 'Фото',
                icon: '📸',
                color: '#8b5cf6',
                unit: '',
                format: (value: number) => value.toString()
            },
            news: {
                label: 'Новости',
                icon: '📰',
                color: '#10b981',
                unit: '',
                format: (value: number) => value.toString()
            }
        };
        return configs[type];
    };

    const getChartData = (type: MetricType) => {
        const key = type === 'rating' ? 'rating' : `${type}_count`;
        return history
            .filter(entry => entry[key] !== null)
            .map(entry => ({
                date: new Date(entry.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
                value: entry[key],
                fullDate: entry.date
            }))
            .reverse(); // Старые -> новые для графика
    };

    const calculateTrend = (type: MetricType) => {
        const data = getChartData(type);
        if (data.length < 2) return null;

        const latest = data[data.length - 1].value;
        const previous = data[data.length - 2].value;
        const change = latest - previous;
        const changePercent = ((change / previous) * 100).toFixed(1);

        return {
            value: change,
            percent: changePercent,
            isPositive: change > 0
        };
    };

    const getLatestValue = (type: MetricType) => {
        const data = getChartData(type);
        return data.length > 0 ? data[data.length - 1].value : null;
    };

    if (!businessId) {
        return (
            <Card>
                <CardContent className="p-8 text-center text-gray-500">
                    Выберите бизнес для просмотра истории метрик
                </CardContent>
            </Card>
        );
    }

    const config = getMetricConfig(selectedMetric);
    const chartData = getChartData(selectedMetric);
    const trend = calculateTrend(selectedMetric);
    const latestValue = getLatestValue(selectedMetric);

    return (
        <div className="space-y-6">
            {/* Header with Tabs */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-2xl">📊 Метрики Бизнеса</CardTitle>
                            <CardDescription>История изменений показателей</CardDescription>
                        </div>
                        <Button onClick={() => setShowAddModal(true)} size="sm">
                            <Plus className="h-4 w-4 mr-2" />
                            Добавить вручную
                        </Button>
                    </div>

                    {/* Metric Tabs */}
                    <div className="flex gap-2 mt-4 flex-wrap">
                        {(['rating', 'reviews', 'photos', 'news'] as MetricType[]).map(type => {
                            const tabConfig = getMetricConfig(type);
                            const isActive = selectedMetric === type;
                            return (
                                <button
                                    key={type}
                                    onClick={() => setSelectedMetric(type)}
                                    className={`
                    px-4 py-2 rounded-lg font-medium transition-all
                    ${isActive
                                            ? 'bg-gradient-to-r from-gray-900 to-gray-800 text-white shadow-md'
                                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                        }
                  `}
                                >
                                    {tabConfig.icon} {tabConfig.label}
                                </button>
                            );
                        })}
                    </div>
                </CardHeader>

                <CardContent>
                    {loading ? (
                        <div className="flex items-center justify-center p-12">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900" />
                        </div>
                    ) : chartData.length > 0 ? (
                        <>
                            {/* Latest Value & Trend */}
                            <div className="mb-6 p-6 bg-gray-50 rounded-lg border border-gray-200">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm text-gray-500 mb-1">Текущее значение</p>
                                        <p className="text-4xl font-bold" style={{ color: config.color }}>
                                            {latestValue !== null ? config.format(latestValue) : '—'}
                                        </p>
                                    </div>
                                    {trend && (
                                        <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${trend.isPositive ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                                            }`}>
                                            {trend.isPositive ? (
                                                <TrendingUp className="h-5 w-5" />
                                            ) : (
                                                <TrendingDown className="h-5 w-5" />
                                            )}
                                            <span className="font-semibold">
                                                {trend.isPositive ? '+' : ''}{trend.percent}%
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Graph */}
                            <div className="h-80 mb-6">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData}>
                                        <defs>
                                            <linearGradient id={`gradient-${selectedMetric}`} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor={config.color} stopOpacity={0.3} />
                                                <stop offset="95%" stopColor={config.color} stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                        <XAxis
                                            dataKey="date"
                                            stroke="#6b7280"
                                            style={{ fontSize: '12px' }}
                                        />
                                        <YAxis
                                            stroke="#6b7280"
                                            style={{ fontSize: '12px' }}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: 'white',
                                                border: '1px solid #e5e7eb',
                                                borderRadius: '8px',
                                                padding: '12px'
                                            }}
                                            formatter={(value: number) => [config.format(value), config.label]}
                                        />
                                        <Area
                                            type="monotone"
                                            dataKey="value"
                                            stroke={config.color}
                                            strokeWidth={3}
                                            fill={`url(#gradient-${selectedMetric})`}
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Data Table */}
                            <div className="border rounded-lg overflow-hidden">
                                <table className="w-full">
                                    <thead className="bg-gray-50 border-b">
                                        <tr>
                                            <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Дата</th>
                                            <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Рейтинг</th>
                                            <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Отзывы</th>
                                            <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Фото</th>
                                            <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Новости</th>
                                            <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Источник</th>
                                            <th className="px-4 py-3"></th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y">
                                        {history.slice(0, 10).map(entry => (
                                            <tr key={entry.id} className="hover:bg-gray-50">
                                                <td className="px-4 py-3 text-sm text-gray-900">
                                                    {new Date(entry.date).toLocaleDateString('ru-RU')}
                                                </td>
                                                <td className="px-4 py-3 text-sm text-gray-900">
                                                    {entry.rating !== null ? entry.rating.toFixed(1) : '—'}
                                                </td>
                                                <td className="px-4 py-3 text-sm text-gray-900">
                                                    {entry.reviews_count ?? '—'}
                                                </td>
                                                <td className="px-4 py-3 text-sm text-gray-900">
                                                    {entry.photos_count ?? '—'}
                                                </td>
                                                <td className="px-4 py-3 text-sm text-gray-900">
                                                    {entry.news_count ?? '—'}
                                                </td>
                                                <td className="px-4 py-3 text-sm">
                                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${entry.source === 'parsing'
                                                            ? 'bg-blue-100 text-blue-700'
                                                            : 'bg-purple-100 text-purple-700'
                                                        }`}>
                                                        {entry.source === 'parsing' ? 'Парсинг' : 'Вручную'}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3">
                                                    {entry.source === 'manual' && (
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => deleteEntry(entry.id)}
                                                        >
                                                            <Trash2 className="h-4 w-4 text-red-500" />
                                                        </Button>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    ) : (
                        <div className="text-center p-12 text-gray-500">
                            <p className="mb-4">Нет данных для отображения</p>
                            <Button onClick={() => setShowAddModal(true)} variant="outline">
                                <Plus className="h-4 w-4 mr-2" />
                                Добавить первую запись
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Add Manual Entry Modal */}
            <AnimatePresence>
                {showAddModal && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50"
                        onClick={() => setShowAddModal(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-white rounded-lg shadow-xl w-full max-w-md p-6"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <h3 className="text-xl font-bold mb-4">Добавить метрики вручную</h3>

                            <div className="space-y-4">
                                <div>
                                    <Label htmlFor="date">Дата</Label>
                                    <Input
                                        id="date"
                                        type="date"
                                        value={newEntry.date}
                                        onChange={(e) => setNewEntry({ ...newEntry, date: e.target.value })}
                                    />
                                </div>

                                <div>
                                    <Label htmlFor="rating">Рейтинг (1-5)</Label>
                                    <Input
                                        id="rating"
                                        type="number"
                                        step="0.1"
                                        min="0"
                                        max="5"
                                        placeholder="4.5"
                                        value={newEntry.rating}
                                        onChange={(e) => setNewEntry({ ...newEntry, rating: e.target.value })}
                                    />
                                </div>

                                <div>
                                    <Label htmlFor="reviews">Количество отзывов</Label>
                                    <Input
                                        id="reviews"
                                        type="number"
                                        min="0"
                                        placeholder="45"
                                        value={newEntry.reviews_count}
                                        onChange={(e) => setNewEntry({ ...newEntry, reviews_count: e.target.value })}
                                    />
                                </div>

                                <div>
                                    <Label htmlFor="photos">Количество фото</Label>
                                    <Input
                                        id="photos"
                                        type="number"
                                        min="0"
                                        placeholder="20"
                                        value={newEntry.photos_count}
                                        onChange={(e) => setNewEntry({ ...newEntry, photos_count: e.target.value })}
                                    />
                                </div>

                                <div>
                                    <Label htmlFor="news">Количество новостей</Label>
                                    <Input
                                        id="news"
                                        type="number"
                                        min="0"
                                        placeholder="5"
                                        value={newEntry.news_count}
                                        onChange={(e) => setNewEntry({ ...newEntry, news_count: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div className="flex gap-2 mt-6">
                                <Button
                                    variant="outline"
                                    onClick={() => setShowAddModal(false)}
                                    className="flex-1"
                                >
                                    Отмена
                                </Button>
                                <Button
                                    onClick={addManualEntry}
                                    className="flex-1"
                                >
                                    Сохранить
                                </Button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};
