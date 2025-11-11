import { Button } from "@/components/ui/button";

const Sprint = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Спринт на неделю</h1>
          <p className="text-gray-600 mt-2">Отдаём только 3–5 задач. В пятницу — короткое ретро и обновление плана.</p>
        </div>

        <div className="space-y-4">
          {[1,2,3].map(i => (
            <div key={i} className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-gray-900">Задача {i}</div>
                  <div className="text-sm text-gray-600">Ожидаемый эффект: +5% к выручке · Дедлайн: Пт</div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm">Сделано</Button>
                  <Button variant="outline" size="sm">Перенести</Button>
                  <Button variant="outline" size="sm">Нужна помощь</Button>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6">
          <Button onClick={() => (window.location.href = "/dashboard")}>Вернуться в кабинет</Button>
        </div>
      </div>
    </div>
  );
};

export default Sprint;


