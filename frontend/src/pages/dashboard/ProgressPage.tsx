import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import ProgressTracker from '@/components/ProgressTracker';
import MapParseTable from '@/components/MapParseTable';
import MapRecommendations from '@/components/MapRecommendations';
import { GrowthPlan } from '@/components/GrowthPlan';

export const ProgressPage = () => {
  const { user, currentBusinessId } = useOutletContext<any>();
  const [showWizard, setShowWizard] = useState(false);
  const [wizardLocation, setWizardLocation] = useState<string>('');
  const [wizardExperience, setWizardExperience] = useState<string>('');
  const [wizardClients, setWizardClients] = useState<string>('');
  const [wizardCRM, setWizardCRM] = useState<string>('');
  const [wizardAverageCheck, setWizardAverageCheck] = useState<string>('');
  const [wizardRevenue, setWizardRevenue] = useState<string>('');
  const [savingWizard, setSavingWizard] = useState(false);
  const [loadingWizard, setLoadingWizard] = useState(false);

  // Загружаем сохраненные данные мастера при открытии
  useEffect(() => {
    const loadWizardData = async () => {
      if (!showWizard || !currentBusinessId) return;

      setLoadingWizard(true);
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`/api/business/${currentBusinessId}/optimization-wizard`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          if (data.success && data.data) {
            setWizardExperience(data.data.experience || '');
            setWizardClients(data.data.clients || '');
            setWizardCRM(data.data.crm || '');
            setWizardLocation(data.data.location || '');
            setWizardAverageCheck(data.data.average_check || '');
            setWizardRevenue(data.data.revenue || '');
          }
        }
      } catch (err) {
        console.error('Ошибка загрузки данных мастера:', err);
      } finally {
        setLoadingWizard(false);
      }
    };

    loadWizardData();
  }, [showWizard, currentBusinessId]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Прогресс</h1>
          <p className="text-gray-600 mt-1">Отслеживайте ваш прогресс и достижения</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowWizard(true)}>Мастер оптимизации бизнеса</Button>
        </div>
      </div>

      {/* Growth Plan - План роста бизнеса */}
      <GrowthPlan businessId={currentBusinessId} />

      <ProgressTracker businessId={currentBusinessId} />
      <MapRecommendations businessId={currentBusinessId} />
      <MapParseTable businessId={currentBusinessId} />

      {showWizard && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[100]" onClick={() => setShowWizard(false)}>
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center p-6 border-b border-gray-200">
              <h2 className="text-2xl font-bold text-gray-900">Мастер оптимизации бизнеса</h2>
              <Button onClick={() => setShowWizard(false)} variant="outline" size="sm">✕</Button>
            </div>
            <div className="p-6 overflow-auto max-h-[calc(90vh-120px)] bg-gradient-to-br from-white to-gray-50/50">
              <div className="space-y-4">
                <p className="text-gray-600 mb-4">Немного цифр, чтобы план был реалистичным. Можно заполнить позже.</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Как давно работаете</label>
                    <div className="flex flex-wrap gap-2">
                      {['0–6 мес', '6–12 мес', '1–3 года', '3+ лет'].map(x => (
                        <span
                          key={x}
                          onClick={() => setWizardExperience(x === wizardExperience ? '' : x)}
                          className={`px-3 py-1 rounded-md text-gray-700 text-sm cursor-pointer transition-colors ${wizardExperience === x
                              ? 'bg-primary text-white hover:bg-primary/90'
                              : 'bg-gray-100 hover:bg-gray-200'
                            }`}
                        >
                          {x}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Постоянные клиенты</label>
                    <input
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder="например, 150"
                      value={wizardClients}
                      onChange={(e) => setWizardClients(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">CRM</label>
                    <input
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder="Например: Yclients"
                      value={wizardCRM}
                      onChange={(e) => setWizardCRM(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Расположение</label>
                    <div className="flex flex-wrap gap-2">
                      {['Дом', 'ТЦ', 'Двор', 'Магистраль', 'Центр', 'Спальник', 'Около метро'].map(x => (
                        <span
                          key={x}
                          onClick={() => setWizardLocation(x === wizardLocation ? '' : x)}
                          className={`px-3 py-1 rounded-md text-gray-700 text-sm cursor-pointer transition-colors ${wizardLocation === x
                              ? 'bg-primary text-white hover:bg-primary/90'
                              : 'bg-gray-100 hover:bg-gray-200'
                            }`}
                        >
                          {x}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Средний чек (₽)</label>
                    <input
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder="2200"
                      value={wizardAverageCheck}
                      onChange={(e) => setWizardAverageCheck(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Выручка в месяц (₽)</label>
                    <input
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder="350000"
                      value={wizardRevenue}
                      onChange={(e) => setWizardRevenue(e.target.value)}
                    />
                  </div>
                </div>
              </div>
              <div className="mt-6 flex justify-end pt-4 border-t border-gray-200">
                <Button
                  onClick={async () => {
                    if (!currentBusinessId) {
                      alert('Бизнес не выбран');
                      return;
                    }
                    setSavingWizard(true);
                    try {
                      const token = localStorage.getItem('auth_token');
                      const response = await fetch(`/api/business/${currentBusinessId}/optimization-wizard`, {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                          'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({
                          experience: wizardExperience,
                          clients: wizardClients,
                          crm: wizardCRM,
                          location: wizardLocation,
                          average_check: wizardAverageCheck,
                          revenue: wizardRevenue
                        })
                      });
                      const data = await response.json();
                      if (data.success) {
                        setShowWizard(false);
                        window.location.href = `/sprint?business_id=${currentBusinessId}`;
                      } else {
                        alert('Ошибка сохранения: ' + (data.error || 'Неизвестная ошибка'));
                      }
                    } catch (error: any) {
                      alert('Ошибка сохранения: ' + error.message);
                    } finally {
                      setSavingWizard(false);
                    }
                  }}
                  disabled={savingWizard}
                >
                  {savingWizard ? 'Сохранение...' : 'Сформировать план'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
