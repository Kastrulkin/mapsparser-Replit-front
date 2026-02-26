import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceArea } from 'recharts';
import { useLanguage } from '@/i18n/LanguageContext';
interface TimelinePoint {
    date: string;
    rating: number;
    reviews: number;
}

interface AnalyticsTimelineProps {
    data: TimelinePoint[];
}

export const AnalyticsTimeline: React.FC<AnalyticsTimelineProps> = ({ data }) => {
    const { t } = useLanguage();
    const timelineData = data.length > 0
        ? data
        : [{ date: '—', rating: 0, reviews: 0 }];

    return (
        <Card className="col-span-4">
            <CardHeader>
                <CardTitle>{t.networkOverview?.performanceHistory || 'История показателей сети'}</CardTitle>
                <CardDescription>
                    {t.networkOverview?.performanceHistorySubtitle || 'Динамика среднего рейтинга и количества отзывов за последние 7 дней.'}
                </CardDescription>
            </CardHeader>
            <CardContent className="pl-2">
                <div className="h-[350px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={timelineData}>
                            <defs>
                                <linearGradient id="colorRating" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.8} />
                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                </linearGradient>
                            </defs>

                            <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-muted" />
                            <XAxis
                                dataKey="date"
                                stroke="#888888"
                                fontSize={12}
                                tickLine={false}
                                axisLine={false}
                            />
                            <YAxis
                                yAxisId="left"
                                domain={[3, 5]}
                                orientation="left"
                                stroke="#888888"
                                fontSize={12}
                                tickLine={false}
                                axisLine={false}
                                label={{ value: t.networkOverview?.rating || 'Рейтинг', angle: -90, position: 'insideLeft', style: { fill: '#888888' } }}
                            />
                            <YAxis
                                yAxisId="right"
                                orientation="right"
                                stroke="#888888"
                                fontSize={12}
                                tickLine={false}
                                axisLine={false}
                                label={{ value: t.networkOverview?.reviews || 'Отзывы', angle: 90, position: 'insideRight', style: { fill: '#888888' } }}
                            />

                            {/* Risk Zones Background */}
                            <ReferenceArea yAxisId="left" y1={0} y2={3.8} fill="#fee2e2" fillOpacity={0.3} />
                            <ReferenceArea yAxisId="left" y1={3.8} y2={4.3} fill="#fef9c3" fillOpacity={0.3} />

                            <Tooltip
                                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                                labelStyle={{ fontWeight: 'bold', color: '#333' }}
                            />
                            <Legend />

                            <Bar
                                yAxisId="right"
                                dataKey="reviews"
                                name={t.networkOverview?.reviewVolume || 'Объём отзывов'}
                                fill="#94a3b8"
                                barSize={20}
                                radius={[4, 4, 0, 0]}
                            />
                            <Line
                                yAxisId="left"
                                type="monotone"
                                dataKey="rating"
                                name={t.networkOverview?.avgRating || 'Средний рейтинг'}
                                stroke="#10b981"
                                strokeWidth={3}
                                dot={{ r: 4, strokeWidth: 2 }}
                                activeDot={{ r: 6 }}
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
};
