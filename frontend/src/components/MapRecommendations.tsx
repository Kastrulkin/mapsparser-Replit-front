import React, { useEffect, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { AlertCircle, MessageSquare, Newspaper, Camera, TrendingUp } from 'lucide-react';

interface MapParseItem {
  id: string;
  url: string;
  mapType: string;
  rating: string;
  reviewsCount: number;
  unansweredReviewsCount?: number;
  newsCount: number;
  photosCount: number;
  reportPath: string | null;
  createdAt: string;
}

interface MapRecommendationsProps {
  businessId?: string | null;
}

const MapRecommendations: React.FC<MapRecommendationsProps> = ({ businessId }) => {
  const [recommendations, setRecommendations] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!businessId) return;
    loadRecommendations();
  }, [businessId]);

  const loadRecommendations = async () => {
    if (!businessId) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/business/${businessId}/map-parses`, {
        headers: { Authorization: `Bearer ${token || ''}` }
      });
      const data = await res.json();
      if (res.ok && data.success && data.items && data.items.length > 0) {
        const latest = data.items[0] as MapParseItem;
        const recs = generateRecommendations(latest, data.items);
        setRecommendations(recs);
      } else {
        setRecommendations([]);
      }
    } catch (e) {
      console.error('Ошибка загрузки рекомендаций:', e);
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  };

  const generateRecommendations = (latest: MapParseItem, allItems: MapParseItem[]): string[] => {
    const recs: string[] = [];
    const now = new Date();
    const latestDate = new Date(latest.createdAt);
    const daysSinceLatest = Math.floor((now.getTime() - latestDate.getTime()) / (1000 * 60 * 60 * 24));

    // 1. Проверка неотвеченных отзывов
    if (latest.unansweredReviewsCount && latest.unansweredReviewsCount > 0) {
      const countText = latest.unansweredReviewsCount === 1 ? 'отзыв' : 
                       latest.unansweredReviewsCount < 5 ? 'отзыва' : 'отзывов';
      recs.push(`${latest.unansweredReviewsCount} неотвеченных ${countText}! Ответ можно сгенерировать на вкладке "Работа с картами".`);
    }

    // 2. Проверка частоты отзывов (нужен хотя бы 1 в неделю)
    if (allItems.length >= 2) {
      const sorted = [...allItems].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      const prev = sorted[1];
      const latestReviews = latest.reviewsCount || 0;
      const prevReviews = prev.reviewsCount || 0;
      const reviewsDiff = latestReviews - prevReviews;
      const daysBetween = Math.floor((new Date(latest.createdAt).getTime() - new Date(prev.createdAt).getTime()) / (1000 * 60 * 60 * 24));
      
      // Если отзывы не увеличились и прошло больше недели
      if (reviewsDiff === 0 && daysBetween > 7) {
        const lastReviewDate = new Date(latest.createdAt).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
        if (daysSinceLatest > 14) {
          recs.push(`Не хватает отзывов — надо собирать новые отзывы не реже раз в неделю. Последний был ${lastReviewDate} — более 2 недель назад. Попросите клиентов оставлять отзывы после услуги.`);
        } else {
          recs.push(`Не хватает отзывов — надо собирать новые отзывы не реже раз в неделю. Последний был ${lastReviewDate} — более недели назад. Попросите клиентов оставлять отзывы после услуги.`);
        }
      }
    } else if (daysSinceLatest > 14) {
      // Если только один парсинг и прошло больше 2 недель
      const lastReviewDate = latestDate.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
      recs.push(`Не хватает отзывов — надо собирать новые отзывы не реже раз в неделю. Последний был ${lastReviewDate} — более 2 недель назад. Попросите клиентов оставлять отзывы после услуги.`);
    }

    // 3. Проверка новостей (должны быть раз в неделю, если прошло 2 недели без обновлений)
    if (allItems.length >= 2) {
      const sorted = [...allItems].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      const prev = sorted[1];
      const latestNews = latest.newsCount || 0;
      const prevNews = prev.newsCount || 0;
      const daysBetween = Math.floor((new Date(latest.createdAt).getTime() - new Date(prev.createdAt).getTime()) / (1000 * 60 * 60 * 24));
      
      // Если новости не увеличились и прошло больше 2 недель
      if (latestNews === prevNews && daysBetween > 14) {
        recs.push(`Давно не обновлялись новости — новости лучше постить раз в неделю. Можно сгенерировать новую на вкладке "Работа с картами".`);
      }
    } else if (daysSinceLatest > 14) {
      // Если только один парсинг и прошло больше 2 недель
      recs.push(`Давно не обновлялись новости — новости лучше постить раз в неделю. Можно сгенерировать новую на вкладке "Работа с картами".`);
    }

    // 4. Проверка фото (должны обновляться не реже раз в 2 недели)
    if (allItems.length >= 2) {
      const sorted = [...allItems].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      const prev = sorted[1];
      const latestPhotos = latest.photosCount || 0;
      const prevPhotos = prev.photosCount || 0;
      const daysBetween = Math.floor((new Date(latest.createdAt).getTime() - new Date(prev.createdAt).getTime()) / (1000 * 60 * 60 * 24));
      
      // Если фото не увеличились и прошло больше 2 недель
      if (latestPhotos === prevPhotos && daysBetween > 14) {
        recs.push(`Давно не обновлялись фото — фото надо добавлять не реже раз в 2 недели.`);
      }
    } else if (daysSinceLatest > 14) {
      // Если только один парсинг и прошло больше 2 недель
      recs.push(`Давно не обновлялись фото — фото надо добавлять не реже раз в 2 недели.`);
    }

    return recs;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-4">
        <div className="text-sm text-gray-500">Загружаем рекомендации...</div>
      </div>
    );
  }

  if (recommendations.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-4 space-y-3">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className="w-5 h-5 text-blue-600" />
        <h3 className="text-lg font-semibold text-gray-900">Задания по картам</h3>
      </div>
      {recommendations.map((rec, idx) => (
        <Alert key={idx} variant="default" className="border-yellow-200 bg-yellow-50">
          <AlertCircle className="h-4 w-4 text-yellow-600" />
          <AlertTitle className="text-yellow-800 font-medium">Рекомендация</AlertTitle>
          <AlertDescription className="text-yellow-700 text-sm mt-1">
            {rec}
          </AlertDescription>
        </Alert>
      ))}
    </div>
  );
};

export default MapRecommendations;

