import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { CheckCircle2, Phone, Globe, Clock, Package, MessageSquare, Star, Users, Image as ImageIcon, Newspaper, AlertCircle, ExternalLink, MapPin, Trophy } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';

interface YandexBusinessReportProps {
    data: {
        id: string;
        url: string;
        rating?: string;
        reviewsCount?: number;
        unansweredReviewsCount?: number;
        newsCount?: number;
        photosCount?: number;
        isVerified?: boolean;
        phone?: string;
        website?: string;
        messengers?: string; // JSON string
        workingHours?: string; // JSON string
        servicesCount?: number;
        profileCompleteness?: number;
        competitors?: string;
        createdAt: string;
    };
    businessId?: string;
}

export const YandexBusinessReport: React.FC<YandexBusinessReportProps> = ({ data }) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { t } = useLanguage();

    // Parse JSON fields
    const messengers = data.messengers ? JSON.parse(data.messengers) : [];
    const workingHours = data.workingHours ? JSON.parse(data.workingHours) : null;
    const scheduleItems = Array.isArray(workingHours?.schedule) ? workingHours.schedule : [];

    const formatWorkingHourItem = (item: unknown): { day: string; time: string } => {
        if (typeof item === 'string') {
            const raw = item.trim();
            if (!raw) return { day: '—', time: '—' };
            if (raw.includes(': ')) {
                const [day, ...rest] = raw.split(': ');
                return { day: day || '—', time: rest.join(': ') || '—' };
            }
            const idx = raw.indexOf(':');
            if (idx > 0) {
                return { day: raw.slice(0, idx).trim() || '—', time: raw.slice(idx + 1).trim() || '—' };
            }
            return { day: raw, time: '—' };
        }

        if (item && typeof item === 'object') {
            const obj = item as Record<string, unknown>;
            const day = String(obj.day || obj.weekday || obj.title || obj.name || '—').trim() || '—';
            const time = String(obj.time || obj.hours || obj.value || obj.text || '—').trim() || '—';
            return { day, time };
        }

        return { day: '—', time: '—' };
    };

    // Completeness color
    const getCompletenessColor = (score: number) => {
        if (score >= 80) return 'text-green-600 bg-green-50';
        if (score >= 50) return 'text-yellow-600 bg-yellow-50';
        return 'text-red-600 bg-red-50';
    };

    const completeness = data.profileCompleteness || 0;

    return (
        <div className="space-y-6 print:space-y-4 w-full">
            {/* Header */}
            <Card className="border-2">
                <CardHeader className="pb-4">
                    <div className="flex items-start justify-between">
                        <div className="space-y-1 flex-1">
                            <div className="flex items-center gap-2">
                                <CardTitle className="text-2xl print:text-xl">
                                    Яндекс.Карты — Отчёт о профиле
                                </CardTitle>
                                {data.isVerified && (
                                    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                                        <CheckCircle2 className="w-3 h-3 mr-1" />
                                        Проверено
                                    </Badge>
                                )}
                            </div>
                            <CardDescription className="flex items-center gap-2 mt-2">
                                <MapPin className="w-4 h-4" />
                                <a
                                    href={data.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-600 hover:underline flex items-center gap-1"
                                >
                                    Открыть на картах
                                    <ExternalLink className="w-3 h-3" />
                                </a>
                            </CardDescription>
                        </div>

                        {/* Completeness Score */}
                        <div className={`px-4 py-2 rounded-lg ${getCompletenessColor(completeness)}`}>
                            <div className="text-sm font-medium">Заполненность</div>
                            <div className="text-3xl font-bold">{completeness}%</div>
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="space-y-4">
                    {/* Quick Stats Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="flex items-center gap-3 p-3 bg-gradient-to-br from-amber-50 to-orange-50 rounded-lg">
                            <div className="p-2 bg-white rounded-lg">
                                <Star className="w-5 h-5 text-amber-600" />
                            </div>
                            <div>
                                <div className="text-2xl font-bold text-amber-900">{data.rating || '—'}</div>
                                <div className="text-xs text-amber-700">Рейтинг</div>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-3 bg-gradient-to-br from-blue-50 to-cyan-50 rounded-lg">
                            <div className="p-2 bg-white rounded-lg">
                                <Users className="w-5 h-5 text-blue-600" />
                            </div>
                            <div>
                                <div className="text-2xl font-bold text-blue-900">{data.reviewsCount || 0}</div>
                                <div className="text-xs text-blue-700">Отзывов</div>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-3 bg-gradient-to-br from-rose-50 to-pink-50 rounded-lg">
                            <div className="p-2 bg-white rounded-lg">
                                <AlertCircle className="w-5 h-5 text-rose-600" />
                            </div>
                            <div>
                                <div className="text-2xl font-bold text-rose-900">{data.unansweredReviewsCount || 0}</div>
                                <div className="text-xs text-rose-700">Без ответа</div>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-3 bg-gradient-to-br from-purple-50 to-violet-50 rounded-lg">
                            <div className="p-2 bg-white rounded-lg">
                                <ImageIcon className="w-5 h-5 text-purple-600" />
                            </div>
                            <div>
                                <div className="text-2xl font-bold text-purple-900">{data.photosCount || 0}</div>
                                <div className="text-xs text-purple-700">Фото</div>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Contact Information */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Phone className="w-5 h-5" />
                        Контактная информация
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {/* Phone */}
                    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-3">
                            <Phone className="w-4 h-4 text-gray-600" />
                            <span className="font-medium">Телефон</span>
                        </div>
                        {data.phone ? (
                            <a href={`tel:${data.phone}`} className="text-blue-600 font-mono">
                                {data.phone}
                            </a>
                        ) : (
                            <span className="text-gray-400">Не указан</span>
                        )}
                    </div>

                    {/* Website */}
                    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-3">
                            <Globe className="w-4 h-4 text-gray-600" />
                            <span className="font-medium">Сайт</span>
                        </div>
                        {data.website ? (
                            <a
                                href={data.website}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:underline flex items-center gap-1"
                            >
                                {new URL(data.website).hostname}
                                <ExternalLink className="w-3 h-3" />
                            </a>
                        ) : (
                            <span className="text-gray-400">Не указан</span>
                        )}
                    </div>

                    {/* Messengers */}
                    {messengers.length > 0 && (
                        <div className="p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3 mb-2">
                                <MessageSquare className="w-4 h-4 text-gray-600" />
                                <span className="font-medium">Мессенджеры</span>
                            </div>
                            <div className="flex flex-wrap gap-2 mt-2">
                                {messengers.map((m: any, idx: number) => (
                                    <a
                                        key={idx}
                                        href={m.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="px-3 py-1 bg-white border rounded-full text-sm hover:bg-gray-100 transition-colors"
                                    >
                                        {m.type === 'whatsapp' && '📱 WhatsApp'}
                                        {m.type === 'telegram' && '💬 Telegram'}
                                        {m.type === 'viber' && '📞 Viber'}
                                    </a>
                                ))}
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Working Hours */}
            {scheduleItems.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg flex items-center gap-2">
                            <Clock className="w-5 h-5" />
                            Часы работы
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {scheduleItems.map((item: unknown, idx: number) => {
                                const row = formatWorkingHourItem(item);
                                return (
                                <div key={idx} className="flex justify-between p-2 bg-gray-50 rounded">
                                    <span className="font-medium text-gray-700">{row.day}</span>
                                    <span className="text-gray-600 font-mono text-sm">{row.time}</span>
                                </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Services Stats */}
            {(data.servicesCount || 0) > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg flex items-center gap-2">
                            <Package className="w-5 h-5" />
                            Услуги и товары
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center justify-between p-4 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg">
                            <div className="flex items-center gap-3">
                                <div className="p-3 bg-white rounded-lg">
                                    <Package className="w-6 h-6 text-indigo-600" />
                                </div>
                                <div>
                                    <div className="text-2xl font-bold text-indigo-900">{data.servicesCount}</div>
                                    <div className="text-sm text-indigo-700">Услуг/товаров добавлено</div>
                                </div>
                            </div>
                            <Badge variant="outline" className="bg-white">✓ Заполнено</Badge>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* News Stats */}
            {(data.newsCount || 0) > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg flex items-center gap-2">
                            <Newspaper className="w-5 h-5" />
                            Новости
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center justify-between p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg">
                            <div className="flex items-center gap-3">
                                <div className="p-3 bg-white rounded-lg">
                                    <Newspaper className="w-6 h-6 text-green-600" />
                                </div>
                                <div>
                                    <div className="text-2xl font-bold text-green-900">{data.newsCount}</div>
                                    <div className="text-sm text-green-700">Новостей опубликовано</div>
                                </div>
                            </div>
                            <Badge variant="outline" className="bg-white">✓ Активны</Badge>
                        </div>
                    </CardContent>
                </Card>
            )}


            {/* Competitors Analysis */}
            {data.competitors && (
                (() => {
                    let competitorsList = [];
                    try {
                        competitorsList = JSON.parse(data.competitors);
                    } catch (e) {
                        console.error("Error parsing competitors:", e);
                    }

                    if (competitorsList.length > 0) {
                        return (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg flex items-center gap-2">
                                        <Trophy className="w-5 h-5" />
                                        Конкуренты рядом
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-4">
                                        {competitorsList.map((comp: any, idx: number) => (
                                            <div key={idx} className="flex flex-col md:flex-row justify-between items-start md:items-center p-4 bg-gray-50 rounded-lg gap-4">
                                                <div className="flex-1">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <span className="font-bold text-gray-900">{comp.name || "Без названия"}</span>
                                                        {comp.rating && (
                                                            <div className="flex items-center text-amber-600 bg-amber-50 px-2 py-0.5 rounded text-xs font-medium">
                                                                <Star className="w-3 h-3 mr-1 fill-amber-600" />
                                                                {comp.rating}
                                                            </div>
                                                        )}
                                                    </div>
                                                    <div className="text-sm text-gray-500 mb-1">{comp.category}</div>
                                                    {comp.reviews && (
                                                        <div className="text-xs text-gray-400">
                                                            {comp.reviews}
                                                        </div>
                                                    )}
                                                </div>
                                                {comp.url && (
                                                    <a
                                                        href={comp.url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="flex items-center gap-1 text-sm bg-white border border-gray-200 px-3 py-2 rounded hover:bg-gray-50 text-blue-600 transition-colors"
                                                    >
                                                        Показать
                                                        <ExternalLink className="w-3 h-3" />
                                                    </a>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    }
                    return null;
                })()
            )}

            {/* Recommendations */}
            {completeness < 100 && (
                <Card className="border-amber-200 bg-amber-50/30">
                    <CardHeader>
                        <CardTitle className="text-lg flex items-center gap-2 text-amber-900">
                            <AlertCircle className="w-5 h-5" />
                            Рекомендации по улучшению
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ul className="space-y-2">
                            {!data.phone && (
                                <li className="flex items-start gap-2 text-sm">
                                    <span className="text-amber-600">•</span>
                                    <span>Добавьте контактный телефон (+15% к заполненности)</span>
                                </li>
                            )}
                            {!data.website && (
                                <li className="flex items-start gap-2 text-sm">
                                    <span className="text-amber-600">•</span>
                                    <span>Укажите официальный сайт (+15% к заполненности)</span>
                                </li>
                            )}
                            {(!workingHours || !workingHours.schedule) && (
                                <li className="flex items-start gap-2 text-sm">
                                    <span className="text-amber-600">•</span>
                                    <span>Заполните график работы (+10% к заполненности)</span>
                                </li>
                            )}
                            {(data.servicesCount || 0) < 5 && (
                                <li className="flex items-start gap-2 text-sm">
                                    <span className="text-amber-600">•</span>
                                    <span>Добавьте минимум 5 услуг/товаров (+15% к заполненности)</span>
                                </li>
                            )}
                            {(data.photosCount || 0) < 3 && (
                                <li className="flex items-start gap-2 text-sm">
                                    <span className="text-amber-600">•</span>
                                    <span>Загрузите минимум 3 качественных фото (+15% к заполненности)</span>
                                </li>
                            )}
                            {(data.unansweredReviewsCount || 0) > 0 && (
                                <li className="flex items-start gap-2 text-sm text-rose-700">
                                    <span className="text-rose-600">•</span>
                                    <span>Ответьте на {data.unansweredReviewsCount} неотвеченных отзыва</span>
                                </li>
                            )}
                        </ul>
                    </CardContent>
                </Card>
            )}

            {/* Print Styles */}
            <style>{`
                @media print {
                    body {
                        print-color-adjust: exact;
                        -webkit-print-color-adjust: exact;
                    }
                    .print\\:text-xl {
                        font-size: 1.25rem;
                    }
                    .print\\:space-y-4 > * + * {
                        margin-top: 1rem;
                    }
                }
            `}</style>
        </div>
    );
};
