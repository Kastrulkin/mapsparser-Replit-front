import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";

interface SprintTask {
  id: string;
  title: string;
  description: string;
  expected_effect: string;
  deadline: string;
  status: 'pending' | 'done' | 'postponed' | 'help_needed';
}

const Sprint = () => {
  const [searchParams] = useSearchParams();
  const businessId = searchParams.get('business_id');
  const [tasks, setTasks] = useState<SprintTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSprint = async () => {
      if (!businessId) {
        setError('Бизнес не выбран');
        setLoading(false);
        return;
      }

      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`/api/business/${businessId}/sprint`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          if (data.success && data.sprint && data.sprint.tasks) {
            setTasks(data.sprint.tasks);
          } else {
            // Если спринта нет, генерируем его
            const generateResponse = await fetch(`/api/business/${businessId}/sprint`, {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              }
            });

            if (generateResponse.ok) {
              const generateData = await generateResponse.json();
              if (generateData.success && generateData.sprint && generateData.sprint.tasks) {
                setTasks(generateData.sprint.tasks);
              } else {
                // Если генерация не удалась, используем дефолтные задачи
                setTasks([
                  {
                    id: '1',
                    title: 'Задача 1',
                    description: 'Оптимизировать описание услуг на картах',
                    expected_effect: '+5% к выручке',
                    deadline: 'Пт',
                    status: 'pending'
                  },
                  {
                    id: '2',
                    title: 'Задача 2',
                    description: 'Обновить фото на картах',
                    expected_effect: '+3% к конверсии',
                    deadline: 'Пт',
                    status: 'pending'
                  },
                  {
                    id: '3',
                    title: 'Задача 3',
                    description: 'Ответить на неотвеченные отзывы',
                    expected_effect: '+2% к рейтингу',
                    deadline: 'Пт',
                    status: 'pending'
                  }
                ]);
              }
            } else {
              setError('Не удалось сгенерировать спринт');
            }
          }
        } else {
          setError('Не удалось загрузить спринт');
        }
      } catch (err: any) {
        setError('Ошибка загрузки спринта: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    loadSprint();
  }, [businessId]);

  const handleTaskAction = async (taskId: string, action: 'done' | 'postponed' | 'help_needed') => {
    setTasks(prevTasks => 
      prevTasks.map(task => 
        task.id === taskId 
          ? { ...task, status: action === 'done' ? 'done' : action === 'postponed' ? 'postponed' : 'help_needed' }
          : task
      )
    );

    // TODO: Сохранить изменение статуса задачи в API
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-gray-600">Загрузка спринта...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Спринт на неделю</h1>
          <p className="text-gray-600 mt-2">Отдаём только 3–5 задач. В пятницу — короткое ретро и обновление плана.</p>
        </div>

        <div className="space-y-4">
          {tasks.length > 0 ? (
            tasks.map((task) => (
              <div key={task.id} className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-gray-900">{task.title}</div>
                    <div className="text-sm text-gray-600 mt-1">{task.description}</div>
                    <div className="text-sm text-gray-600 mt-1">
                      Ожидаемый эффект: {task.expected_effect} · Дедлайн: {task.deadline}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => handleTaskAction(task.id, 'done')}
                      className={task.status === 'done' ? 'bg-green-100' : ''}
                    >
                      Сделано
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => handleTaskAction(task.id, 'postponed')}
                      className={task.status === 'postponed' ? 'bg-yellow-100' : ''}
                    >
                      Перенести
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => handleTaskAction(task.id, 'help_needed')}
                      className={task.status === 'help_needed' ? 'bg-red-100' : ''}
                    >
                      Нужна помощь
                    </Button>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 p-4 text-center text-gray-500">
              Спринт еще не сформирован. Заполните Мастер оптимизации бизнеса для генерации задач.
            </div>
          )}
        </div>

        <div className="mt-6">
          <Button onClick={() => (window.location.href = "/dashboard")}>Вернуться в кабинет</Button>
        </div>
      </div>
    </div>
  );
};

export default Sprint;
