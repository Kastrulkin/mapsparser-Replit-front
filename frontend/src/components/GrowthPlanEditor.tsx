import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from './ui/select';
import { useToast } from '../hooks/use-toast';
import { newAuth } from '../lib/auth_new';
import { Plus, Trash2, Save, Loader2, Edit2, X } from 'lucide-react';

interface BusinessType {
  id: string;
  type_key: string;
  label: string;
  description?: string;
  is_active: boolean;
}

interface GrowthTask {
  id?: string;
  number: number;
  text: string;
}

interface GrowthStage {
  id?: string;
  stage_number: number;
  title: string;
  description: string;
  goal: string;
  expected_result: string;
  duration: string;
  is_permanent: boolean;
  tasks: GrowthTask[];
}

export const GrowthPlanEditor: React.FC = () => {
  const [businessTypes, setBusinessTypes] = useState<BusinessType[]>([]);
  const [selectedTypeId, setSelectedTypeId] = useState<string>('');
  const [stages, setStages] = useState<GrowthStage[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingStage, setEditingStage] = useState<string | null>(null);
  const [editingType, setEditingType] = useState<string | null>(null);
  const [newTypeKey, setNewTypeKey] = useState('');
  const [newTypeLabel, setNewTypeLabel] = useState('');
  const { toast } = useToast();

  useEffect(() => {
    loadBusinessTypes();
  }, []);

  useEffect(() => {
    if (selectedTypeId) {
      loadStages(selectedTypeId);
    } else {
      setStages([]);
    }
  }, [selectedTypeId]);

  const loadBusinessTypes = async () => {
    try {
      setLoading(true);
      const data = await newAuth.makeRequest('/admin/business-types', {
        method: 'GET'
      });
      
      setBusinessTypes(data.types || []);
      if (data.types && data.types.length > 0 && !selectedTypeId) {
        setSelectedTypeId(data.types[0].id);
      }
    } catch (error: any) {
      console.error('Ошибка загрузки типов бизнеса:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось загрузить типы бизнеса',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const loadStages = async (typeId: string) => {
    try {
      setLoading(true);
      const data = await newAuth.makeRequest(`/admin/growth-stages/${typeId}`, {
        method: 'GET'
      });
      
      setStages(data.stages || []);
    } catch (error: any) {
      console.error('Ошибка загрузки этапов:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось загрузить этапы',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateType = async () => {
    if (!newTypeKey.trim() || !newTypeLabel.trim()) {
      toast({
        title: 'Ошибка',
        description: 'Заполните ключ и название типа',
        variant: 'destructive'
      });
      return;
    }

    try {
      setSaving(true);
      await newAuth.makeRequest('/admin/business-types', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type_key: newTypeKey.trim(),
          label: newTypeLabel.trim()
        })
      });

      toast({ title: 'Успешно', description: 'Тип бизнеса создан' });
      setNewTypeKey('');
      setNewTypeLabel('');
      setEditingType(null);
      await loadBusinessTypes();
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось создать тип бизнеса',
        variant: 'destructive'
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteType = async (typeId: string) => {
    if (!confirm('Удалить тип бизнеса? Все этапы и задачи будут удалены.')) return;

    try {
      await newAuth.makeRequest(`/admin/business-types/${typeId}`, {
        method: 'DELETE'
      });

      toast({ title: 'Успешно', description: 'Тип бизнеса удалён' });
      if (selectedTypeId === typeId) {
        setSelectedTypeId('');
      }
      await loadBusinessTypes();
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось удалить тип бизнеса',
        variant: 'destructive'
      });
    }
  };

  const handleSaveStage = async (stage: GrowthStage) => {
    if (!selectedTypeId || !stage.title.trim()) {
      toast({
        title: 'Ошибка',
        description: 'Заполните название этапа',
        variant: 'destructive'
      });
      return;
    }

    try {
      setSaving(true);
      const stageData = {
        business_type_id: selectedTypeId,
        stage_number: stage.stage_number,
        title: stage.title,
        description: stage.description || '',
        goal: stage.goal || '',
        expected_result: stage.expected_result || '',
        duration: stage.duration || '',
        is_permanent: stage.is_permanent,
        tasks: stage.tasks.map(t => t.text).filter(t => t.trim())
      };

      const url = stage.id 
        ? `/admin/growth-stages/${stage.id}`
        : '/admin/growth-stages';
      const method = stage.id ? 'PUT' : 'POST';

      await newAuth.makeRequest(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(stageData)
      });

      toast({ title: 'Успешно', description: 'Этап сохранён' });
      setEditingStage(null);
      await loadStages(selectedTypeId);
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось сохранить этап',
        variant: 'destructive'
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteStage = async (stageId: string) => {
    if (!confirm('Удалить этап? Все задачи будут удалены.')) return;

    try {
      await newAuth.makeRequest(`/admin/growth-stages/${stageId}`, {
        method: 'DELETE'
      });

      toast({ title: 'Успешно', description: 'Этап удалён' });
      await loadStages(selectedTypeId);
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось удалить этап',
        variant: 'destructive'
      });
    }
  };

  const addTask = (stageIndex: number) => {
    const newStages = [...stages];
    const stage = newStages[stageIndex];
    const newTaskNumber = stage.tasks.length > 0 
      ? Math.max(...stage.tasks.map(t => t.number)) + 1 
      : 1;
    stage.tasks.push({ number: newTaskNumber, text: '' });
    setStages(newStages);
  };

  const removeTask = (stageIndex: number, taskIndex: number) => {
    const newStages = [...stages];
    newStages[stageIndex].tasks.splice(taskIndex, 1);
    // Перенумеровываем задачи
    newStages[stageIndex].tasks.forEach((task, idx) => {
      task.number = idx + 1;
    });
    setStages(newStages);
  };

  const addStage = () => {
    const newStageNumber = stages.length > 0 
      ? Math.max(...stages.map(s => s.stage_number)) + 1 
      : 1;
    const newStage: GrowthStage = {
      stage_number: newStageNumber,
      title: '',
      description: '',
      goal: '',
      expected_result: '',
      duration: '',
      is_permanent: false,
      tasks: []
    };
    setStages([...stages, newStage]);
    setEditingStage(`new_${newStageNumber}`);
  };

  if (loading && businessTypes.length === 0) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
        <span className="ml-2">Загрузка...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Схема роста</h2>
        <p className="text-gray-600 mt-1">Управление этапами и задачами для разных типов бизнеса</p>
      </div>

      {/* Управление типами бизнеса */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold">Типы бизнеса</h3>
          <Button
            onClick={() => setEditingType('new')}
            size="sm"
            variant="outline"
          >
            <Plus className="w-4 h-4 mr-2" />
            Добавить тип
          </Button>
        </div>

        {editingType === 'new' && (
          <div className="mb-4 p-4 bg-gray-50 rounded-lg space-y-3">
            <Input
              placeholder="Ключ типа (например: beauty_salon)"
              value={newTypeKey}
              onChange={(e) => setNewTypeKey(e.target.value)}
            />
            <Input
              placeholder="Название типа (например: Салон красоты)"
              value={newTypeLabel}
              onChange={(e) => setNewTypeLabel(e.target.value)}
            />
            <div className="flex gap-2">
              <Button onClick={handleCreateType} disabled={saving} size="sm">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Сохранить
              </Button>
              <Button onClick={() => { setEditingType(null); setNewTypeKey(''); setNewTypeLabel(''); }} variant="outline" size="sm">
                <X className="w-4 h-4 mr-2" />
                Отмена
              </Button>
            </div>
          </div>
        )}

        <Select value={selectedTypeId} onValueChange={setSelectedTypeId}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Выберите тип бизнеса" />
          </SelectTrigger>
          <SelectContent>
            {businessTypes.map(type => (
              <SelectItem key={type.id} value={type.id}>
                <div className="flex items-center justify-between w-full">
                  <span>{type.label}</span>
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteType(type.id);
                    }}
                    variant="ghost"
                    size="sm"
                    className="ml-2 h-6 w-6 p-0"
                  >
                    <Trash2 className="w-3 h-3 text-red-500" />
                  </Button>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Этапы роста */}
      {selectedTypeId && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Этапы роста</h3>
            <Button onClick={addStage} size="sm" variant="outline">
              <Plus className="w-4 h-4 mr-2" />
              Добавить этап
            </Button>
          </div>

          {stages.map((stage, stageIndex) => {
            const isEditing = editingStage === stage.id || editingStage === `new_${stage.stage_number}`;
            
            return (
              <div key={stage.id || `new_${stage.stage_number}`} className="bg-white rounded-lg border border-gray-200 p-6">
                {isEditing ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">Номер этапа</label>
                        <Input
                          type="number"
                          value={stage.stage_number}
                          onChange={(e) => {
                            const newStages = [...stages];
                            newStages[stageIndex].stage_number = parseInt(e.target.value) || 1;
                            setStages(newStages);
                          }}
                        />
                      </div>
                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          checked={stage.is_permanent}
                          onChange={(e) => {
                            const newStages = [...stages];
                            newStages[stageIndex].is_permanent = e.target.checked;
                            setStages(newStages);
                          }}
                          className="mr-2"
                        />
                        <label className="text-sm">Постоянный этап</label>
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Название этапа</label>
                      <Input
                        value={stage.title}
                        onChange={(e) => {
                          const newStages = [...stages];
                          newStages[stageIndex].title = e.target.value;
                          setStages(newStages);
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Описание</label>
                      <Textarea
                        value={stage.description}
                        onChange={(e) => {
                          const newStages = [...stages];
                          newStages[stageIndex].description = e.target.value;
                          setStages(newStages);
                        }}
                        rows={2}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Цель</label>
                      <Input
                        value={stage.goal}
                        onChange={(e) => {
                          const newStages = [...stages];
                          newStages[stageIndex].goal = e.target.value;
                          setStages(newStages);
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Ожидаемый результат</label>
                      <Textarea
                        value={stage.expected_result}
                        onChange={(e) => {
                          const newStages = [...stages];
                          newStages[stageIndex].expected_result = e.target.value;
                          setStages(newStages);
                        }}
                        rows={2}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Длительность</label>
                      <Input
                        value={stage.duration}
                        onChange={(e) => {
                          const newStages = [...stages];
                          newStages[stageIndex].duration = e.target.value;
                          setStages(newStages);
                        }}
                        placeholder="Например: 1-2 недели или Постоянно"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <label className="block text-sm font-medium">Задачи</label>
                        <Button
                          onClick={() => addTask(stageIndex)}
                          size="sm"
                          variant="outline"
                        >
                          <Plus className="w-3 h-3 mr-1" />
                          Добавить задачу
                        </Button>
                      </div>
                      {stage.tasks.map((task, taskIndex) => (
                        <div key={taskIndex} className="flex gap-2 mb-2">
                          <Input
                            value={task.text}
                            onChange={(e) => {
                              const newStages = [...stages];
                              newStages[stageIndex].tasks[taskIndex].text = e.target.value;
                              setStages(newStages);
                            }}
                            placeholder={`Задача ${task.number}`}
                          />
                          <Button
                            onClick={() => removeTask(stageIndex, taskIndex)}
                            variant="ghost"
                            size="sm"
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => handleSaveStage(stage)}
                        disabled={saving}
                        size="sm"
                      >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                        Сохранить
                      </Button>
                      <Button
                        onClick={() => {
                          setEditingStage(null);
                          if (!stage.id) {
                            // Удаляем новый этап, если отменили
                            const newStages = [...stages];
                            newStages.splice(stageIndex, 1);
                            setStages(newStages);
                          } else {
                            // Перезагружаем этапы
                            loadStages(selectedTypeId);
                          }
                        }}
                        variant="outline"
                        size="sm"
                      >
                        <X className="w-4 h-4 mr-2" />
                        Отмена
                      </Button>
                      {stage.id && (
                        <Button
                          onClick={() => handleDeleteStage(stage.id!)}
                          variant="destructive"
                          size="sm"
                          className="ml-auto"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Удалить
                        </Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h4 className="font-semibold">
                          Этап {stage.stage_number}: {stage.title}
                          {stage.is_permanent && <span className="ml-2 text-xs text-gray-500">(Постоянный)</span>}
                        </h4>
                        <p className="text-sm text-gray-600 mt-1">{stage.description}</p>
                      </div>
                      <Button
                        onClick={() => setEditingStage(stage.id || `new_${stage.stage_number}`)}
                        variant="ghost"
                        size="sm"
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                    </div>
                    <div className="mt-2 text-sm space-y-1">
                      <p><strong>Цель:</strong> {stage.goal || '—'}</p>
                      <p><strong>Ожидаемый результат:</strong> {stage.expected_result || '—'}</p>
                      <p><strong>Длительность:</strong> {stage.duration || '—'}</p>
                      <div className="mt-2">
                        <strong>Задачи:</strong>
                        <ul className="list-disc list-inside ml-2">
                          {stage.tasks.map((task, idx) => (
                            <li key={idx}>{task.text}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

