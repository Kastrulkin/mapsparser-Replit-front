import React, { useState } from 'react';
import { Button } from './ui/button';
import { useApiData } from '../hooks/useApiData';

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

interface MapParseTableProps {
  businessId?: string | null;
}

const MapParseTable: React.FC<MapParseTableProps> = ({ businessId }) => {
  const [viewHtml, setViewHtml] = useState<string | null>(null);

  const { data, loading, error } = useApiData<MapParseItem[]>(
    businessId ? `${window.location.origin}/api/business/${businessId}/map-parses` : null,
    {
      transform: (data) => data.items || []
    }
  );
  const items = data || [];

  const viewReport = async (id: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/map-report/${id}`, {
        headers: { Authorization: `Bearer ${token || ''}` }
      });
      if (!res.ok) {
        setError('Отчет недоступен');
        return;
      }
      const html = await res.text();
      setViewHtml(html);
    } catch (e) {
      setError('Ошибка при загрузке отчета');
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">Парсинг карт</h3>
        <div className="text-sm text-gray-500">История парсинга</div>
      </div>

      {loading && <div className="text-gray-500 text-sm">Загружаем...</div>}
      {error && <div className="text-red-600 text-sm mb-2">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="text-sm text-gray-500">Нет данных парсинга для этого бизнеса</div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border border-gray-200">
            <thead className="bg-gray-50 text-gray-700">
              <tr>
                <th className="px-3 py-2 border-b text-left">№</th>
                <th className="px-3 py-2 border-b text-left">Дата</th>
                <th className="px-3 py-2 border-b text-left">URL</th>
                <th className="px-3 py-2 border-b text-left">Тип</th>
                <th className="px-3 py-2 border-b text-right">Рейтинг</th>
                <th className="px-3 py-2 border-b text-right">Отзывы</th>
                <th className="px-3 py-2 border-b text-right">Без ответа</th>
                <th className="px-3 py-2 border-b text-right">Новости</th>
                <th className="px-3 py-2 border-b text-right">Фото</th>
                <th className="px-3 py-2 border-b text-right">Отчет</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 border-b">{idx + 1}</td>
                  <td className="px-3 py-2 border-b">
                    {new Date(item.createdAt).toLocaleDateString('ru-RU')}
                  </td>
                  <td className="px-3 py-2 border-b max-w-xs truncate">
                    <a href={item.url} target="_blank" rel="noreferrer" className="text-blue-600 underline">
                      {item.url}
                    </a>
                  </td>
                  <td className="px-3 py-2 border-b capitalize">{item.mapType || '—'}</td>
                  <td className="px-3 py-2 border-b text-right">{item.rating || '—'}</td>
                  <td className="px-3 py-2 border-b text-right">{item.reviewsCount ?? '—'}</td>
                  <td className="px-3 py-2 border-b text-right">
                    {item.unansweredReviewsCount !== undefined ? (
                      <span className={item.unansweredReviewsCount > 0 ? 'text-red-600 font-semibold' : 'text-gray-600'}>
                        {item.unansweredReviewsCount}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-3 py-2 border-b text-right">{item.newsCount ?? '—'}</td>
                  <td className="px-3 py-2 border-b text-right">{item.photosCount ?? '—'}</td>
                  <td className="px-3 py-2 border-b text-right">
                    {item.reportPath ? (
                      <Button size="sm" variant="outline" onClick={() => viewReport(item.id)}>
                        Посмотреть
                      </Button>
                    ) : (
                      <span className="text-gray-400">нет отчета</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewHtml && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] overflow-auto relative">
            <div className="flex justify-between items-center border-b px-4 py-2">
              <h4 className="font-semibold text-gray-900">Отчет</h4>
              <Button size="sm" variant="outline" onClick={() => setViewHtml(null)}>
                Закрыть
              </Button>
            </div>
            <div className="p-4">
              <div dangerouslySetInnerHTML={{ __html: viewHtml }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MapParseTable;

