import React from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceArea } from 'recharts';
import { useLanguage } from '@/i18n/LanguageContext';
import { CalendarIcon } from 'lucide-react';
import { format } from "date-fns";
import { enUS, ru } from "date-fns/locale";
import { DateRange } from "react-day-picker";
import { cn } from "@/lib/utils";
interface TimelinePoint {
    date: string;
    rating: number;
    reviews: number;
}

export type TimelinePeriodPreset = 'all' | 'month' | 'quarter' | 'custom';

const isTimelinePeriodPreset = (value: string): value is TimelinePeriodPreset =>
    value === 'all' || value === 'month' || value === 'quarter' || value === 'custom';

interface AnalyticsTimelineProps {
    data: TimelinePoint[];
    periodPreset: TimelinePeriodPreset;
    onPeriodPresetChange: (value: TimelinePeriodPreset) => void;
    customRange?: DateRange;
    onCustomRangeChange: (value: DateRange | undefined) => void;
}

export const AnalyticsTimeline: React.FC<AnalyticsTimelineProps> = ({
    data,
    periodPreset,
    onPeriodPresetChange,
    customRange,
    onCustomRangeChange,
}) => {
    const { t } = useLanguage();
    const isRu = typeof document !== 'undefined' ? document.documentElement.lang !== 'en' : true;
    const dateLocale = isRu ? ru : enUS;
    const timelineData = data.length > 0
        ? data
        : [{ date: '—', rating: 0, reviews: 0 }];
    const subtitle = (() => {
        if (periodPreset === 'month') {
            return isRu
                ? 'Динамика среднего рейтинга и количества отзывов за последний месяц.'
                : 'Average rating and review count for the last month.';
        }
        if (periodPreset === 'quarter') {
            return isRu
                ? 'Динамика среднего рейтинга и количества отзывов за последний квартал.'
                : 'Average rating and review count for the last quarter.';
        }
        if (periodPreset === 'custom') {
            if (customRange?.from && customRange?.to) {
                return isRu
                    ? `Динамика среднего рейтинга и количества отзывов за период ${format(customRange.from, "dd.MM.yyyy")} - ${format(customRange.to, "dd.MM.yyyy")}.`
                    : `Average rating and review count for ${format(customRange.from, "dd.MM.yyyy")} - ${format(customRange.to, "dd.MM.yyyy")}.`;
            }
            return isRu
                ? 'Динамика среднего рейтинга и количества отзывов за произвольный период.'
                : 'Average rating and review count for a custom period.';
        }
        return isRu
            ? 'Динамика среднего рейтинга и количества отзывов за всё время.'
            : 'Average rating and review count for the full period.';
    })();

    return (
        <Card className="col-span-4">
            <CardHeader>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <CardTitle>{t.networkOverview?.performanceHistory || 'История показателей сети'}</CardTitle>
                        <CardDescription>{subtitle}</CardDescription>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                        <Select value={periodPreset} onValueChange={(value) => onPeriodPresetChange(isTimelinePeriodPreset(value) ? value : 'all')}>
                            <SelectTrigger className="w-full sm:w-[220px]">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">{isRu ? 'За всё время' : 'All time'}</SelectItem>
                                <SelectItem value="month">{isRu ? 'За месяц' : 'Last month'}</SelectItem>
                                <SelectItem value="quarter">{isRu ? 'За квартал' : 'Last quarter'}</SelectItem>
                                <SelectItem value="custom">{isRu ? 'Произвольный период' : 'Custom period'}</SelectItem>
                            </SelectContent>
                        </Select>
                        {periodPreset === 'custom' ? (
                            <Popover>
                                <PopoverTrigger asChild>
                                    <Button
                                        variant="outline"
                                        className={cn(
                                            "w-full justify-start text-left font-normal sm:w-[260px]",
                                            !customRange?.from && "text-muted-foreground"
                                        )}
                                    >
                                        <CalendarIcon className="mr-2 h-4 w-4" />
                                        {customRange?.from ? (
                                            customRange.to ? (
                                                <>
                                                    {format(customRange.from, "dd LLL yyyy", { locale: dateLocale })} -{" "}
                                                    {format(customRange.to, "dd LLL yyyy", { locale: dateLocale })}
                                                </>
                                            ) : (
                                                format(customRange.from, "dd LLL yyyy", { locale: dateLocale })
                                            )
                                        ) : (
                                            <span>{isRu ? 'Выберите даты' : 'Pick dates'}</span>
                                        )}
                                    </Button>
                                </PopoverTrigger>
                                <PopoverContent className="w-auto p-0" align="end">
                                    <Calendar
                                        initialFocus
                                        mode="range"
                                        defaultMonth={customRange?.from}
                                        selected={customRange}
                                        onSelect={onCustomRangeChange}
                                        numberOfMonths={2}
                                    />
                                </PopoverContent>
                            </Popover>
                        ) : null}
                    </div>
                </div>
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
