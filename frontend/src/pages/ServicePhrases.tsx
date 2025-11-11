const ServicePhrases = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Формулировки услуг</h1>
          <p className="text-gray-600 mt-2">Принятые формулировки и версии. Эти тексты можно использовать в новостях и ответах.</p>
        </div>

        <div className="space-y-3">
          {["Стрижка мужская","Окрашивание","Маникюр"].map((name) => (
            <div key={name} className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="font-medium text-gray-900">{name}</div>
              <div className="text-sm text-gray-600 mt-1">Актуальная формулировка: лаконичное описание услуги с выгодой.</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ServicePhrases;


