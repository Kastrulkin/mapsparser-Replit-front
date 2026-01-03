import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { useApiData } from '../hooks/useApiData';

interface ProgressStage {
  id: string;
  stage_number: number;
  stage_name: string;
  stage_description: string;
  status: 'completed' | 'active' | 'pending';
  progress_percentage: number;
  target_revenue: number;
  target_clients: number;
  target_roi: number;
  current_revenue: number;
  current_clients: number;
  current_roi: number;
  started_at: string | null;
  completed_at: string | null;
}

interface SprintTask {
  id: string;
  title: string;
  description: string;
  expected_effect: string;
  deadline: string;
  status: 'pending' | 'done' | 'postponed' | 'help_needed';
}

interface ProgressTrackerProps {
  onUpdate?: () => void;
  businessId?: string | null;
}

const ProgressTracker: React.FC<ProgressTrackerProps> = ({ onUpdate, businessId }) => {
  // Загружаем стадии прогресса
  const { data: stagesData, loading, error } = useApiData<ProgressStage[]>(
    businessId ? `/api/business/${businessId}/stages` : null,
    {
      transform: (data) => data.stages || []
    }
  );
  const stages = stagesData || [];

  // Загружаем спринт
  const { data: sprintData } = useApiData<{ tasks: SprintTask[] }>(
    businessId ? `/api/business/${businessId}/sprint` : null,
    {
      transform: (data) => data.sprint || { tasks: [] }
    }
  );
  const sprint = sprintData;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const getStageIcon = (status: string, stageNumber: number) => {
    if (status === 'completed') return '✅';
    if (status === 'active') return '🔄';
    return '⏳';
  };

  const getStageColor = (status: string) => {
    if (status === 'completed') return 'border-green-200 bg-green-50';
    if (status === 'active') return 'border-blue-200 bg-blue-50';
    return 'border-gray-200 bg-gray-50';
  };

  const getProgressColor = (percentage: number) => {
    if (percentage >= 100) return 'bg-green-500';
    if (percentage >= 75) return 'bg-blue-500';
    if (percentage >= 50) return 'bg-yellow-500';
    if (percentage >= 25) return 'bg-orange-500';
    return 'bg-red-500';
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="text-center">
          <div className="text-red-600 mb-4">❌ {error}</div>
          <Button onClick={() => window.location.reload()} variant="outline">
            Попробовать снова
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-lg font-semibold text-gray-900">🎯 Путь к вашим целям</h3>
        <div className="text-sm text-gray-500">
          Прогресс по этапам стратегии
        </div>
      </div>

      <div className="space-y-4">
        {stages.map((stage, index) => (
          <div
            key={stage.id}
            className={`rounded-lg border-2 p-4 ${getStageColor(stage.status)}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start space-x-3">
                <div className="text-2xl">
                  {getStageIcon(stage.status, stage.stage_number)}
                </div>
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h4 className="font-semibold text-gray-900">
                      {stage.stage_name}
                    </h4>
                    {stage.status === 'active' && (
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                        Активный
                      </span>
                    )}
                    {stage.status === 'completed' && (
                      <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
                        Завершен
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mt-1">
                    {stage.stage_description}
                  </p>
                  
                  {stage.status === 'active' && (
                    <div className="mt-3">
                      <div className="flex justify-between text-sm text-gray-600 mb-1">
                        <span>Прогресс</span>
                        <span>{stage.progress_percentage}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${getProgressColor(stage.progress_percentage)}`}
                          style={{ width: `${stage.progress_percentage}%` }}
                        ></div>
                      </div>
                    </div>
                  )}

                  {stage.status !== 'pending' && (
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <div className="text-gray-500">Выручка</div>
                        <div className="font-semibold">
                          {formatCurrency(stage.current_revenue)} / {formatCurrency(stage.target_revenue)}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-500">Клиенты</div>
                        <div className="font-semibold">
                          {stage.current_clients} / {stage.target_clients}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-500">ROI</div>
                        <div className="font-semibold">
                          {stage.current_roi.toFixed(1)}% / {stage.target_roi.toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Спринт на неделю */}
      {sprint && sprint.tasks.length > 0 && (
        <div className="mt-6 bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
          boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
        }}>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold text-gray-900">📋 Спринт на неделю</h3>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => window.location.href = `/sprint?business_id=${businessId}`}
            >
              Открыть спринт
            </Button>
          </div>
          <div className="space-y-3">
            {sprint.tasks.slice(0, 3).map((task) => (
              <div key={task.id} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{task.title}</div>
                    <div className="text-sm text-gray-600 mt-1">{task.description}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      {task.expected_effect} · Дедлайн: {task.deadline}
                    </div>
                  </div>
                  {task.status === 'done' && (
                    <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full ml-2">
                      ✓ Сделано
                    </span>
                  )}
                  {task.status === 'postponed' && (
                    <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded-full ml-2">
                      ⏸ Перенесено
                    </span>
                  )}
                  {task.status === 'help_needed' && (
                    <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded-full ml-2">
                      ❓ Нужна помощь
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
          {sprint.tasks.length > 3 && (
            <div className="mt-3 text-center">
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => window.location.href = `/sprint?business_id=${businessId}`}
              >
                Показать все задачи ({sprint.tasks.length})
              </Button>
            </div>
          )}
        </div>
      )}

      <div className="mt-6 bg-gradient-to-r from-blue-50 to-green-50 rounded-lg p-4">
        <div className="text-center">
          <div className="text-lg font-semibold text-gray-900 mb-2">
            💎 Прогнозируемый результат
          </div>
          <div className="text-2xl font-bold text-green-600 mb-2">
            +{formatCurrency(180000)}
          </div>
          <div className="text-sm text-gray-600">
            Прирост через 3 месяца при текущем темпе
          </div>
          <div className="text-xs text-gray-500 mt-2">
            Ваша инвестиция: {formatCurrency(12600)} (7% от прироста)
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProgressTracker;
