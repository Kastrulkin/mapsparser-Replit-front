import React, { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { X, Calendar, Star, MessageSquare, Image as ImageIcon, Newspaper } from 'lucide-react';
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';
import { useLanguage } from '@/i18n/LanguageContext';

interface AddMetricModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
    businessId: string;
}

export const AddMetricModal: React.FC<AddMetricModalProps> = ({
    isOpen,
    onClose,
    onSuccess,
    businessId
}) => {
    const { language, t } = useLanguage();

    const [formData, setFormData] = useState({
        date: new Date().toISOString().split('T')[0],
        rating: '',
        reviews_count: '',
        photos_count: '',
        news_count: ''
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);

        try {
            const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
            const response = await fetch(`/api/business/${businessId}/metrics-history`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    date: formData.date,
                    rating: formData.rating ? parseFloat(formData.rating) : null,
                    reviews_count: formData.reviews_count ? parseInt(formData.reviews_count) : null,
                    photos_count: formData.photos_count ? parseInt(formData.photos_count) : null,
                    news_count: formData.news_count ? parseInt(formData.news_count) : null
                })
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to add metric');
            }

            onSuccess();
            onClose();
            setFormData({
                date: new Date().toISOString().split('T')[0],
                rating: '',
                reviews_count: '',
                photos_count: '',
                news_count: ''
            });
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in fade-in">
            <div className={cn(
                "bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden",
                "animate-in zoom-in-95 duration-200"
            )}>
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-100 bg-gray-50/50">
                    <h2 className="text-xl font-bold text-gray-900">
                        {language === 'ru' ? 'Добавить отчет вручную' : 'Add Manual Report'}
                    </h2>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={onClose}
                        className="rounded-full hover:bg-gray-100 text-gray-500"
                    >
                        <X className="w-5 h-5" />
                    </Button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="p-6 space-y-5">
                    {error && (
                        <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-lg text-sm">
                            {error}
                        </div>
                    )}

                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label className="flex items-center gap-2 text-gray-700">
                                <Calendar className="w-4 h-4 text-primary" />
                                {t.common.date}
                            </Label>
                            <Input
                                type="date"
                                required
                                value={formData.date}
                                onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                                className="rounded-xl border-gray-200 focus:ring-primary/20"
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label className="flex items-center gap-2 text-gray-700">
                                    <Star className="w-4 h-4 text-amber-500" />
                                    {t.dashboard.progress.charts.metrics.rating}
                                </Label>
                                <Input
                                    type="number"
                                    step="0.1"
                                    min="0"
                                    max="5"
                                    placeholder="0.0"
                                    value={formData.rating}
                                    onChange={(e) => setFormData({ ...formData, rating: e.target.value })}
                                    className="rounded-xl border-gray-200 focus:ring-primary/20"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label className="flex items-center gap-2 text-gray-700">
                                    <MessageSquare className="w-4 h-4 text-blue-500" />
                                    {t.dashboard.progress.charts.metrics.reviews}
                                </Label>
                                <Input
                                    type="number"
                                    min="0"
                                    placeholder="0"
                                    value={formData.reviews_count}
                                    onChange={(e) => setFormData({ ...formData, reviews_count: e.target.value })}
                                    className="rounded-xl border-gray-200 focus:ring-primary/20"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label className="flex items-center gap-2 text-gray-700">
                                    <ImageIcon className="w-4 h-4 text-purple-500" />
                                    {t.dashboard.progress.charts.metrics.photos}
                                </Label>
                                <Input
                                    type="number"
                                    min="0"
                                    placeholder="0"
                                    value={formData.photos_count}
                                    onChange={(e) => setFormData({ ...formData, photos_count: e.target.value })}
                                    className="rounded-xl border-gray-200 focus:ring-primary/20"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label className="flex items-center gap-2 text-gray-700">
                                    <Newspaper className="w-4 h-4 text-emerald-500" />
                                    {t.dashboard.progress.charts.metrics.news}
                                </Label>
                                <Input
                                    type="number"
                                    min="0"
                                    placeholder="0"
                                    value={formData.news_count}
                                    onChange={(e) => setFormData({ ...formData, news_count: e.target.value })}
                                    className="rounded-xl border-gray-200 focus:ring-primary/20"
                                />
                            </div>
                        </div>
                    </div>

                    <div className="pt-4 flex justify-end gap-3">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onClose}
                            className="rounded-xl border-gray-200 hover:bg-gray-50"
                        >
                            {t.common.cancel}
                        </Button>
                        <Button
                            type="submit"
                            disabled={loading}
                            className="rounded-xl bg-primary hover:bg-primary/90 text-white min-w-[100px]"
                        >
                            {loading ? (
                                <div className="h-5 w-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                                t.common.save
                            )}
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    );
};
