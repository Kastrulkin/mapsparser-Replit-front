import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { getApiEndpoint } from '../config/api';
import { useLanguage } from '@/i18n/LanguageContext';

interface ROIData {
  investment_amount: number;
  returns_amount: number;
  roi_percentage: number;
  period_start: string | null;
  period_end: string | null;
}

interface ROICalculatorProps {
  onUpdate?: () => void;
}

const ROICalculator: React.FC<ROICalculatorProps> = ({ onUpdate }) => {
  const { t } = useLanguage();
  const [roiData, setRoiData] = useState<ROIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState({
    investment_amount: '',
    returns_amount: '',
    period_start: new Date().toISOString().split('T')[0],
    period_end: new Date().toISOString().split('T')[0]
  });
  const [saving, setSaving] = useState(false);

  const loadROIData = async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(getApiEndpoint('/api/finance/roi'), {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await response.json();

      if (data.success) {
        setRoiData(data.roi);
        setFormData({
          investment_amount: data.roi.investment_amount.toString(),
          returns_amount: data.roi.returns_amount.toString(),
          period_start: data.roi.period_start || new Date().toISOString().split('T')[0],
          period_end: data.roi.period_end || new Date().toISOString().split('T')[0]
        });
      } else {
        setError(data.error || t.dashboard.finance.roi.loadError);
      }
    } catch (error) {
      setError(t.common.error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadROIData();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(getApiEndpoint('/api/finance/roi'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          investment_amount: parseFloat(formData.investment_amount),
          returns_amount: parseFloat(formData.returns_amount),
          period_start: formData.period_start,
          period_end: formData.period_end
        })
      });

      const data = await response.json();

      if (data.success) {
        setRoiData(data.roi);
        setEditMode(false);
        onUpdate?.();
      } else {
        setError(data.error || t.dashboard.finance.roi.saveError);
      }
    } catch (error) {
      setError(t.common.error);
    } finally {
      setSaving(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const getROIColor = (roi: number) => {
    if (roi > 100) return 'text-green-600';
    if (roi > 50) return 'text-blue-600';
    if (roi > 0) return 'text-orange-600';
    return 'text-red-600';
  };

  const getROIStatus = (roi: number) => {
    if (roi > 200) return { text: t.dashboard.finance.roi.status.excellent, emoji: '🚀' };
    if (roi > 100) return { text: t.dashboard.finance.roi.status.good, emoji: '💪' };
    if (roi > 50) return { text: t.dashboard.finance.roi.status.notBad, emoji: '👍' };
    if (roi > 0) return { text: t.dashboard.finance.roi.status.positive, emoji: '✅' };
    return { text: t.dashboard.finance.roi.status.negative, emoji: '⚠️' };
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error && !roiData) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="text-center">
          <div className="text-red-600 mb-4">❌ {error}</div>
          <Button onClick={loadROIData} variant="outline">
            {t.dashboard.network.tryAgain}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-lg font-semibold text-gray-900">💰 {t.dashboard.finance.roi.title}</h3>
        {!editMode && (
          <Button onClick={() => setEditMode(true)} variant="outline" size="sm">
            ✏️ {t.dashboard.finance.roi.edit}
          </Button>
        )}
      </div>

      {editMode ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="investment_amount">{t.dashboard.finance.roi.investment}</Label>
              <Input
                id="investment_amount"
                type="number"
                step="0.01"
                min="0"
                value={formData.investment_amount}
                onChange={(e) => setFormData({ ...formData, investment_amount: e.target.value })}
                placeholder="0.00"
              />
            </div>

            <div>
              <Label htmlFor="returns_amount">{t.dashboard.finance.roi.returns}</Label>
              <Input
                id="returns_amount"
                type="number"
                step="0.01"
                min="0"
                value={formData.returns_amount}
                onChange={(e) => setFormData({ ...formData, returns_amount: e.target.value })}
                placeholder="0.00"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="period_start">{t.dashboard.finance.roi.periodStart}</Label>
              <Input
                id="period_start"
                type="date"
                value={formData.period_start}
                onChange={(e) => setFormData({ ...formData, period_start: e.target.value })}
              />
            </div>

            <div>
              <Label htmlFor="period_end">{t.dashboard.finance.roi.periodEnd}</Label>
              <Input
                id="period_end"
                type="date"
                value={formData.period_end}
                onChange={(e) => setFormData({ ...formData, period_end: e.target.value })}
              />
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <Button onClick={handleSave} disabled={saving} className="flex-1">
              {saving ? t.dashboard.finance.roi.saving : (<span>💾 {t.dashboard.finance.roi.save}</span>)}
            </Button>
            <Button onClick={() => setEditMode(false)} variant="outline">
              {t.dashboard.finance.roi.cancel}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {roiData && roiData.investment_amount > 0 ? (
            <>
              <div className="text-center">
                <div className={`text-4xl font-bold ${getROIColor(roiData.roi_percentage)}`}>
                  {(Number(roiData.roi_percentage) || 0).toFixed(1)}%
                </div>
                <div className="text-lg text-gray-600 mt-2">
                  {getROIStatus(roiData.roi_percentage).emoji} {getROIStatus(roiData.roi_percentage).text}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="text-sm text-blue-600 font-medium mb-1">{t.dashboard.finance.roi.invested}</div>
                  <div className="text-xl font-bold text-blue-900">
                    {formatCurrency(roiData.investment_amount)}
                  </div>
                </div>

                <div className="bg-green-50 rounded-lg p-4">
                  <div className="text-sm text-green-600 font-medium mb-1">{t.dashboard.finance.roi.received}</div>
                  <div className="text-xl font-bold text-green-900">
                    {formatCurrency(roiData.returns_amount)}
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-600 font-medium mb-1">{t.dashboard.finance.roi.period}</div>
                <div className="text-lg text-gray-900">
                  {roiData.period_start} — {roiData.period_end}
                </div>
              </div>

              <div className="text-center">
                <div className="text-sm text-gray-500">
                  {t.dashboard.finance.roi.profit} {formatCurrency(roiData.returns_amount - roiData.investment_amount)}
                </div>
              </div>
            </>
          ) : (
            <div className="text-center text-gray-500">
              <div className="text-4xl mb-4">📊</div>
              <p className="text-lg mb-2">{t.dashboard.finance.roi.notCalculated}</p>
              <p className="text-sm mb-4">{t.dashboard.finance.roi.addData}</p>
              <Button onClick={() => setEditMode(true)}>
                {t.dashboard.finance.roi.calculate}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ROICalculator;
