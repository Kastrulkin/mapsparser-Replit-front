const CardRecommendations = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Рекомендации по карточке</h1>
          <p className="text-gray-600 mt-2">Список улучшений с привязкой к требованиям карт.</p>
        </div>

        <div className="space-y-3">
          {["Обновляйте фото ежемесячно","Публикуйте короткие новости 1 раз в неделю","Просите отзывы у клиентов после визита"].map((rec) => (
            <div key={rec} className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="font-medium text-gray-900">{rec}</div>
              <div className="text-sm text-gray-600 mt-1">Почему важно: повышает доверие и частоту показов в поиске.</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CardRecommendations;


