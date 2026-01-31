import React, { useState, useEffect } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, Circle, ArrowRight, Loader2 } from 'lucide-react';
import { newAuth } from '../lib/auth_new';

interface GrowthStage {
  id: string;
  stage_number: number;
  title: string;
  description: string;
  tasks: { number: number; text: string }[];
  duration: string;
  expected_result: string;
  status?: 'locked' | 'active' | 'completed';
}

interface BusinessType {
  id: string;
  type_key: string;
  label: string;
}

interface GrowthPlanProps {
  businessId?: string;
}

export const GrowthPlan: React.FC<GrowthPlanProps> = ({ businessId }) => {
  const [businessTypes, setBusinessTypes] = useState<BusinessType[]>([]);
  const [selectedTypeId, setSelectedTypeId] = useState<string>('');
  const [stages, setStages] = useState<GrowthStage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set(['1']));
  const [progressData, setProgressData] = useState<Record<string, any>>({});

  useEffect(() => {
    loadBusinessTypes();
  }, []);

  useEffect(() => {
    if (selectedTypeId) {
      loadStages(selectedTypeId);
    }
  }, [selectedTypeId]);

  useEffect(() => {
    if (businessId) {
      loadProgressData();
    }
  }, [businessId]);

  const loadProgressData = async () => {
    if (!businessId) return;
    try {
      const data = await newAuth.makeRequest(`/business/${businessId}/progress`, { method: 'GET' });
      setProgressData(data.progress || {});
    } catch (error: any) {
      console.error('Error loading progress data:', error);
    }
  };

  const getStageProgress = (stageNumber: number): number => {
    const key = `stage_${stageNumber}`;
    return progressData[key]?.percentage || 0;
  };

  const getProgressColor = (percentage: number): string => {
    if (percentage >= 71) return 'bg-green-500';
    if (percentage >= 31) return 'bg-yellow-500';
    return 'bg-orange-500';
  };

  const getProgressTextColor = (percentage: number): string => {
    if (percentage >= 71) return 'text-green-600';
    if (percentage >= 31) return 'text-yellow-600';
    return 'text-orange-600';
  };

  const loadBusinessTypes = async () => {
    try {
      setLoading(true);
      const data = await newAuth.makeRequest('/admin/business-types', { method: 'GET' });

      setBusinessTypes(data.types || []);
      if (data.types && data.types.length > 0) {
        setSelectedTypeId(data.types[0].id);
      }

      // If no types returned, loading is done
      if (!data.types || data.types.length === 0) {
        setLoading(false);
      }
    } catch (error: any) {
      console.error('Error loading business types:', error);
      setError('Не удалось загрузить типы бизнеса');
      setLoading(false);
    }
  };

  const loadStages = async (typeId: string) => {
    try {
      setLoading(true);
      const data = await newAuth.makeRequest(`/admin/growth-stages/${typeId}`, { method: 'GET' });
      setStages(data.stages || []);
      // Expand first stage by default
      if (data.stages && data.stages.length > 0) {
        setExpandedStages(new Set([data.stages[0].id]));
      }
    } catch (error: any) {
      console.error('Error loading stages:', error);
      setError('Не удалось загрузить этапы');
    } finally {
      setLoading(false);
    }
  };

  const toggleStage = (stageId: string) => {
    setExpandedStages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(stageId)) {
        newSet.delete(stageId);
      } else {
        newSet.add(stageId);
      }
      return newSet;
    });
  };

  if (loading && businessTypes.length === 0) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Схема роста бизнеса</h2>
        <p className="text-gray-600 mb-6">
          Выберите тип бизнеса, чтобы увидеть пошаговый план развития
        </p>

        {error && (
          <div className="bg-red-50 text-red-600 p-4 rounded-md mb-6">
            {error}
          </div>
        )}

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Тип бизнеса
          </label>
          <Select value={selectedTypeId} onValueChange={setSelectedTypeId}>
            <SelectTrigger className="w-full max-w-md">
              <SelectValue placeholder="Выберите тип бизнеса" />
            </SelectTrigger>
            <SelectContent>
              {businessTypes.map(type => (
                <SelectItem key={type.id} value={type.id}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {loading && stages.length === 0 ? (
          <div className="flex justify-center p-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : stages.length === 0 && !loading ? (
          <div className="text-center p-8 text-gray-500">
            Для этого типа бизнеса еще нет плана развития.
          </div>
        ) : (
          <div className="space-y-4">
            {stages.map((stage, index) => {
              const isExpanded = expandedStages.has(stage.id);
              const progressPercentage = getStageProgress(stage.stage_number);
              const isCompleted = progressPercentage >= 100;

              return (
                <Card key={stage.id} className="border-2 border-primary shadow-lg">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3 flex-1">
                        <div className="mt-1">
                          {isCompleted ? (
                            <CheckCircle2 className="h-6 w-6 text-green-500" />
                          ) : (
                            <Circle className="h-6 w-6 text-gray-400" />
                          )}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <CardTitle className="text-lg">{stage.title}</CardTitle>
                            {businessId && (
                              <span className={`text-xs font-semibold px-2 py-1 rounded ${getProgressTextColor(progressPercentage)} bg-opacity-10 ${getProgressColor(progressPercentage).replace('bg-', 'bg-opacity-10 bg-')}`}>
                                {progressPercentage}%
                              </span>
                            )}
                          </div>
                          <CardDescription className="mt-1">{stage.description}</CardDescription>
                          {businessId && progressPercentage > 0 && (
                            <div className="mt-2">
                              <div className="w-full bg-gray-200 rounded h-2 overflow-hidden">
                                <div
                                  className={`h-2 rounded transition-all duration-300 ${getProgressColor(progressPercentage)}`}
                                  style={{ width: `${progressPercentage}%` }}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleStage(stage.id)}
                        className="ml-4"
                      >
                        {isExpanded ? 'Свернуть' : 'Развернуть'}
                        <ArrowRight
                          className={`ml-2 h-4 w-4 transition-transform ${isExpanded ? 'rotate-90' : ''
                            }`}
                        />
                      </Button>
                    </div>
                  </CardHeader>
                  {isExpanded && (
                    <CardContent>
                      <div className="space-y-4">
                        <div>
                          <h4 className="font-semibold text-gray-900 mb-2">Задачи этапа:</h4>
                          <ul className="space-y-2">
                            {stage.tasks && stage.tasks.length > 0 ? (
                              stage.tasks.map((task, taskIndex) => (
                                <li key={taskIndex} className="flex items-start space-x-2">
                                  <span className="text-primary mt-1">•</span>
                                  <span className="text-gray-700">
                                    {typeof task === 'string' ? task : task.text}
                                  </span>
                                </li>
                              ))
                            ) : (
                              <li className="text-gray-500 italic">Нет задач</li>
                            )}
                          </ul>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
                          <div>
                            <span className="text-sm font-medium text-gray-500">Длительность:</span>
                            <p className="text-gray-900 font-semibold">{stage.duration}</p>
                          </div>
                          <div>
                            <span className="text-sm font-medium text-gray-500">Ожидаемый результат:</span>
                            <p className="text-gray-900 font-semibold">{stage.expected_result}</p>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
