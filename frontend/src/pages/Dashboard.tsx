import { useEffect, useState } from "react";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { newAuth } from "@/lib/auth_new";
import InviteFriendForm from "@/components/InviteFriendForm";

function getNextReportDate(reports: any[]) {
  if (!reports.length) return null;
  const completedReports = reports.filter(report => report.has_report);
  if (!completedReports.length) return null;
  const last = new Date(completedReports[0].created_at);
  return new Date(last.getTime() + 7 * 24 * 60 * 60 * 1000);
}

function getCountdownString(date: Date) {
  const now = new Date();
  const diff = date.getTime() - now.getTime();
  if (diff <= 0) return null;
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  const minutes = Math.floor((diff / (1000 * 60)) % 60);
  return `${days} д. ${hours} ч. ${minutes} мин.`;
}

const Dashboard = () => {
  const [user, setUser] = useState<any>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState({ email: "", phone: "", name: "", yandexUrl: "" });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);
  const [timer, setTimer] = useState<string | null>(null);
  const [canCreateReport, setCanCreateReport] = useState<boolean>(false);
  const [viewingReport, setViewingReport] = useState<string | null>(null);
  const [reportContent, setReportContent] = useState<string>("");
  const [loadingReport, setLoadingReport] = useState(false);
  const [showCreateReport, setShowCreateReport] = useState(false);
  const [createReportForm, setCreateReportForm] = useState({ yandexUrl: "" });
  const [creatingReport, setCreatingReport] = useState(false);
  
  // Новые состояния для личной информации и услуг
  const [clientInfo, setClientInfo] = useState({
    businessName: "",
    businessType: "",
    address: "",
    workingHours: "",
    description: "",
    services: ""
  });
  const [editClientInfo, setEditClientInfo] = useState(false);
  const [savingClientInfo, setSavingClientInfo] = useState(false);
  const [paraphrasingService, setParaphrasingService] = useState("");
  const [paraphrasedText, setParaphrasedText] = useState("");
  const [paraphrasing, setParaphrasing] = useState(false);
  const [cardImage, setCardImage] = useState<File | null>(null);
  const [analyzingCard, setAnalyzingCard] = useState(false);
  const [cardAnalysis, setCardAnalysis] = useState<any>(null);
  const [priceListFile, setPriceListFile] = useState<File | null>(null);
  const [optimizingPriceList, setOptimizingPriceList] = useState(false);
  const [priceListOptimization, setPriceListOptimization] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Получаем текущего пользователя
        const currentUser = await newAuth.getCurrentUser();
        console.log('Текущий пользователь:', currentUser);
        
        if (!currentUser) {
          console.log('Пользователь не авторизован');
          setLoading(false);
          return;
        }

        setUser(currentUser);
        setForm({
          email: currentUser.email || "",
          phone: currentUser.phone || "",
          name: currentUser.name || "",
          yandexUrl: ""
        });

        // Получаем отчёты пользователя
        const { reports: userReports, error: reportsError } = await newAuth.getUserReports();
        if (reportsError) {
          console.error('Ошибка загрузки отчётов:', reportsError);
        } else {
          console.log('Отчёты загружены:', userReports);
          setReports(userReports || []);
        }

        // Получаем очередь пользователя
        const { queue: userQueue, error: queueError } = await newAuth.getUserQueue();
        if (queueError) {
          console.error('Ошибка загрузки очереди:', queueError);
        } else {
          console.log('Очередь загружена:', userQueue);
          setQueue(userQueue || []);
        }

        // Автозаполняем форму создания отчёта
        setCreateReportForm({
          yandexUrl: ""
        });

        // Загружаем личную информацию о бизнесе
        try {
          const clientInfoResponse = await fetch('https://beautybot.pro/api/client-info', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
          });
          if (clientInfoResponse.ok) {
            const clientData = await clientInfoResponse.json();
            setClientInfo(clientData);
          }
        } catch (error) {
          console.error('Ошибка загрузки информации о бизнесе:', error);
        }

      } catch (error) {
        console.error('Ошибка загрузки данных:', error);
        setError('Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  useEffect(() => {
    // Если нет готовых отчётов — можно создавать сразу
    const nextDate = getNextReportDate(reports);
    if (!nextDate) {
      setCanCreateReport(true);
      setTimer('00:00:00');
      return;
    }

    const now = new Date();
    if (nextDate.getTime() <= now.getTime()) {
      setCanCreateReport(true);
      setTimer('00:00:00');
      return;
    }

    setCanCreateReport(false);
    const updateTimer = () => {
      const countdown = getCountdownString(nextDate);
      setTimer(countdown);
      if (!countdown) {
        // Время истекло, обновляем данные
        window.location.reload();
      }
    };
    updateTimer();
    const interval = setInterval(updateTimer, 60000);
    return () => clearInterval(interval);
  }, [reports]);

  const handleViewReport = async (reportId: string) => {
    setLoadingReport(true);
    try {
      const response = await fetch(`https://beautybot.pro/api/view-report/${reportId}`);
      if (response.ok) {
      const content = await response.text();
      setReportContent(content);
      setViewingReport(reportId);
      } else {
        setError('Ошибка загрузки отчёта');
      }
    } catch (error) {
      console.error('Ошибка просмотра отчёта:', error);
      setError('Ошибка загрузки отчёта');
    } finally {
      setLoadingReport(false);
    }
  };

  const handleDownloadReport = async (reportId: string) => {
    try {
      const response = await fetch(`https://beautybot.pro/api/download-report/${reportId}`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `seo_report_${reportId}.html`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        setError('Ошибка скачивания отчёта');
      }
    } catch (error) {
      console.error('Ошибка скачивания отчёта:', error);
      setError('Ошибка скачивания отчёта');
    }
  };

  const handleCreateReport = async () => {
    if (!createReportForm.yandexUrl.trim()) {
      setError('Введите URL Яндекс.Карт');
      return;
    }

    setCreatingReport(true);
    setError(null);

    try {
      const { queue_id, error } = await newAuth.addToQueue(createReportForm.yandexUrl);
      
      if (error) {
        setError(error);
      } else {
        setSuccess('Отчёт добавлен в очередь обработки');
        setShowCreateReport(false);
        setCreateReportForm({ yandexUrl: "" });
        
        // Обновляем данные
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      }
    } catch (error) {
      console.error('Ошибка создания отчёта:', error);
      setError('Ошибка создания отчёта');
    } finally {
      setCreatingReport(false);
    }
  };

  const handleDeleteQueueItem = async (queueId: string) => {
    if (!confirm('Вы уверены, что хотите удалить этот отчёт из обработки?')) {
      return;
    }

    try {
      const response = await fetch(`https://beautybot.pro/api/users/queue/${queueId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        setSuccess('Отчёт удалён из обработки');
        // Обновляем данные
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка удаления отчёта');
      }
    } catch (error) {
      console.error('Ошибка удаления отчёта:', error);
      setError('Ошибка удаления отчёта');
    }
  };

  const handleUpdateProfile = async () => {
    try {
      const { user: updatedUser, error } = await newAuth.updateProfile({
        name: form.name,
        phone: form.phone
      });

      if (error) {
        setError(error);
      } else {
        setSuccess('Профиль обновлён');
        setEditMode(false);
        if (updatedUser) {
          setUser(updatedUser);
        }
      }
    } catch (error) {
      console.error('Ошибка обновления профиля:', error);
      setError('Ошибка обновления профиля');
    }
  };

  const handleLogout = async () => {
    try {
      await newAuth.signOut();
      window.location.href = '/';
    } catch (error) {
      console.error('Ошибка выхода:', error);
    }
  };

  // Функции для работы с личной информацией
  const handleSaveClientInfo = async () => {
    setSavingClientInfo(true);
    try {
        const response = await fetch('http://localhost:5002/api/client-info', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(clientInfo)
      });

      if (response.ok) {
        setSuccess('Информация о бизнесе сохранена');
        setEditClientInfo(false);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка сохранения информации');
      }
    } catch (error) {
      console.error('Ошибка сохранения информации:', error);
      setError('Ошибка сохранения информации');
    } finally {
      setSavingClientInfo(false);
    }
  };

  // Функция для перефразирования через GigaChat
  const handleParaphraseService = async () => {
    if (!paraphrasingService.trim()) {
      setError('Введите описание услуги для перефразирования');
      return;
    }

    setParaphrasing(true);
    setError(null);

    try {
        const response = await fetch('http://localhost:5002/api/paraphrase', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: paraphrasingService,
          businessType: clientInfo.businessType
        })
      });

      if (response.ok) {
        const data = await response.json();
        setParaphrasedText(data.paraphrased_text);
        setSuccess('Текст успешно перефразирован');
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка перефразирования');
      }
    } catch (error) {
      console.error('Ошибка перефразирования:', error);
      setError('Ошибка перефразирования');
    } finally {
      setParaphrasing(false);
    }
  };

  const handleAnalyzeCard = async () => {
    if (!cardImage) {
      setError('Выберите изображение для анализа');
      return;
    }
    
    setAnalyzingCard(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append('image', cardImage);
      
      const response = await fetch('http://localhost:5002/api/analyze-card', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: formData
      });
      
      if (response.ok) {
        const data = await response.json();
        setCardAnalysis(data);
        setSuccess('Карточка успешно проанализирована');
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка анализа карточки');
      }
    } catch (error) {
      console.error('Ошибка анализа карточки:', error);
      setError('Ошибка анализа карточки');
    } finally {
      setAnalyzingCard(false);
    }
  };

  const handleOptimizePriceList = async () => {
    if (!priceListFile) {
      setError('Выберите файл прайс-листа для оптимизации');
      return;
    }
    
    setOptimizingPriceList(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append('file', priceListFile);
      
      const response = await fetch('http://localhost:5002/api/optimize-pricelist', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: formData
      });
      
      if (response.ok) {
        const data = await response.json();
        setPriceListOptimization(data);
        setSuccess('Прайс-лист успешно оптимизирован');
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка оптимизации прайс-листа');
      }
    } catch (error) {
      console.error('Ошибка оптимизации прайс-листа:', error);
      setError('Ошибка оптимизации прайс-листа');
    } finally {
      setOptimizingPriceList(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Доступ запрещён</h1>
          <p className="text-gray-600 mb-6">Необходима авторизация</p>
          <Button onClick={() => window.location.href = '/login'}>
            Войти
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-gray-900">Личный кабинет</h1>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
        </div>
          )}

          {success && (
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4">
              {success}
            </div>
          )}

          {/* Профиль пользователя */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Профиль</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input 
                    type="email" 
                    value={form.email} 
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Имя</label>
                <input 
                  type="text" 
                  value={form.name} 
                  onChange={(e) => setForm({...form, name: e.target.value})}
                  disabled={!editMode}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
                <input 
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm({...form, phone: e.target.value})}
                  disabled={!editMode}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>
            <div className="mt-4">
              {editMode ? (
                <div className="flex gap-2">
                  <Button onClick={handleUpdateProfile}>Сохранить</Button>
                  <Button onClick={() => setEditMode(false)} variant="outline">Отмена</Button>
                </div>
              ) : (
                <Button onClick={() => setEditMode(true)}>Редактировать</Button>
          )}
        </div>
                  </div>
                  
          {/* Создание отчёта */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Создать отчёт</h2>
                  {!showCreateReport ? (
              <Button onClick={() => setShowCreateReport(true)}>
                Создать новый отчёт
                    </Button>
                  ) : (
                    <div className="space-y-4">
                      <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    URL страницы Яндекс.Карт
                        </label>
                        <input 
                          type="url" 
                          value={createReportForm.yandexUrl} 
                    onChange={(e) => setCreateReportForm({...createReportForm, yandexUrl: e.target.value})}
                          placeholder="https://yandex.ru/maps/org/..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        />
                      </div>
                <div className="flex gap-2">
                  <Button onClick={handleCreateReport} disabled={creatingReport}>
                          {creatingReport ? 'Создание...' : 'Создать отчёт'}
                        </Button>
                  <Button onClick={() => setShowCreateReport(false)} variant="outline">
                          Отмена
                        </Button>
                      </div>
                    </div>
                  )}
                </div>

          {/* Таймер следующего отчёта - всегда виден */}
          <div className="text-center p-8 bg-gradient-to-br from-background/50 to-muted/20 rounded-3xl border border-border/20 mb-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              {canCreateReport ? 'Отчёт готов к созданию' : 'До следующего отчёта'}
            </h3>
            <div className={`text-6xl md:text-7xl font-bold tracking-tight mb-2 ${canCreateReport ? 'text-green-500' : 'text-red-500'}`}>
              {timer || '00:00:00'}
            </div>
            <div className="flex justify-center gap-2 text-sm text-muted-foreground">
              <span className="px-3 py-1 bg-muted/20 rounded-lg">Дни</span>
              <span className="px-3 py-1 bg-muted/20 rounded-lg">Часы</span>
              <span className="px-3 py-1 bg-muted/20 rounded-lg">Минуты</span>
            </div>
          </div>

          {/* Очередь обработки */}
          {queue.length > 0 && (
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">В обработке</h2>
              <div className="space-y-2">
                {queue.map((item) => (
                  <div key={item.id} className="bg-yellow-50 border border-yellow-200 rounded p-4">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <p className="text-sm text-gray-600">URL: {item.url}</p>
                        <p className="text-sm text-gray-600">Статус: {item.status}</p>
                        <p className="text-sm text-gray-600">
                          Создан: {new Date(item.created_at).toLocaleString()}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDeleteQueueItem(item.id)}
                        className="ml-4 px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition-colors"
                      >
                        Удалить
                      </button>
          </div>
        </div>
                ))}
              </div>
            </div>
          )}

          {/* Готовые отчёты */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Готовые отчёты</h2>
            {reports.length === 0 ? (
              <p className="text-gray-600">У вас пока нет готовых отчётов</p>
          ) : (
            <div className="space-y-4">
              {reports.map((report) => (
                  <div key={report.id} className="bg-white border border-gray-200 rounded-lg p-4">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <h3 className="font-medium text-gray-900">
                          {report.title || 'Без названия'}
                        </h3>
                        <p className="text-sm text-gray-600 mt-1">
                          Создан: {new Date(report.created_at).toLocaleString()}
                        </p>
                        {report.seo_score && (
                          <p className="text-sm text-gray-600">
                            SEO-оценка: {report.seo_score}/100
                          </p>
                      )}
                    </div>
                      <div className="flex gap-2 ml-4">
                        {report.has_report && (
                      <>
                        <Button 
                              onClick={() => handleViewReport(report.id)}
                          variant="outline" 
                          size="sm"
                        >
                              Просмотр
                        </Button>
                        <Button 
                              onClick={() => handleDownloadReport(report.id)}
                              variant="outline"
                          size="sm"
                        >
                          Скачать
                        </Button>
                      </>
                        )}
                      </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

          {/* Личная информация о бизнесе */}
          <div className="mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-900">Информация о бизнесе</h2>
              {!editClientInfo ? (
                <Button onClick={() => setEditClientInfo(true)}>Редактировать</Button>
              ) : (
                <div className="flex gap-2">
                  <Button onClick={handleSaveClientInfo} disabled={savingClientInfo}>
                    {savingClientInfo ? 'Сохранение...' : 'Сохранить'}
                  </Button>
                  <Button onClick={() => setEditClientInfo(false)} variant="outline">Отмена</Button>
                </div>
              )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Название бизнеса</label>
                <input 
                  type="text" 
                  value={clientInfo.businessName} 
                  onChange={(e) => setClientInfo({...clientInfo, businessName: e.target.value})}
                  disabled={!editClientInfo}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Название вашего салона"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Тип бизнеса</label>
                <select 
                  value={clientInfo.businessType} 
                  onChange={(e) => setClientInfo({...clientInfo, businessType: e.target.value})}
                  disabled={!editClientInfo}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="">Выберите тип</option>
                  <option value="beauty_salon">Салон красоты</option>
                  <option value="barbershop">Барбершоп</option>
                  <option value="nail_salon">Ногтевой сервис</option>
                  <option value="spa">СПА-салон</option>
                  <option value="massage">Массажный салон</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Адрес</label>
                <input 
                  type="text" 
                  value={clientInfo.address} 
                  onChange={(e) => setClientInfo({...clientInfo, address: e.target.value})}
                  disabled={!editClientInfo}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Полный адрес салона"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Режим работы</label>
                <input 
                  type="text" 
                  value={clientInfo.workingHours} 
                  onChange={(e) => setClientInfo({...clientInfo, workingHours: e.target.value})}
                  disabled={!editClientInfo}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Пн-Вс: 9:00-21:00"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Описание бизнеса</label>
                <textarea 
                  value={clientInfo.description} 
                  onChange={(e) => setClientInfo({...clientInfo, description: e.target.value})}
                  disabled={!editClientInfo}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  rows={3}
                  placeholder="Краткое описание вашего салона"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Услуги</label>
                <textarea 
                  value={clientInfo.services} 
                  onChange={(e) => setClientInfo({...clientInfo, services: e.target.value})}
                  disabled={!editClientInfo}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  rows={4}
                  placeholder="Список услуг, которые вы предоставляете"
                />
              </div>
            </div>
          </div>

          {/* Перефразирование описания услуг */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Перефразирование описания услуг</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Введите описание услуги для перефразирования
                </label>
                <textarea 
                  value={paraphrasingService} 
                  onChange={(e) => setParaphrasingService(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  rows={4}
                  placeholder="Например: Стрижка волос, укладка, окрашивание..."
                />
              </div>
              <Button 
                onClick={handleParaphraseService} 
                disabled={paraphrasing || !paraphrasingService.trim()}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {paraphrasing ? 'Перефразирование...' : 'Перефразировать через ИИ'}
              </Button>
              
              {paraphrasedText && (
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Перефразированный текст:
                  </label>
                  <div className="bg-gray-50 border border-gray-300 rounded-md p-4">
                    <p className="text-gray-800">{paraphrasedText}</p>
                  </div>
                  <Button 
                    onClick={() => {
                      navigator.clipboard.writeText(paraphrasedText);
                      setSuccess('Текст скопирован в буфер обмена');
                    }}
                    variant="outline"
                    className="mt-2"
                  >
                    Копировать
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Анализ карточек Яндекс.Карт */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Анализ карточки на Яндекс.Картах</h2>
            <div className="space-y-4">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors">
                <div className="flex flex-col items-center">
                  <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-lg font-medium text-gray-900 mb-2">Загрузите скриншот карточки</p>
                  <p className="text-sm text-gray-500 mb-4">Поддерживаются форматы: PNG, JPG, JPEG (до 15 МБ)</p>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/jpg"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        if (file.size > 15 * 1024 * 1024) {
                          setError('Файл слишком большой. Максимальный размер: 15 МБ');
                          return;
                        }
                        setCardImage(file);
                      }
                    }}
                    className="hidden"
                    id="card-upload"
                  />
                  <label htmlFor="card-upload" className="bg-blue-600 text-white px-4 py-2 rounded-md cursor-pointer hover:bg-blue-700 transition-colors">
                    Выбрать файл
                  </label>
                </div>
              </div>
              
              {cardImage && (
                <div className="mt-4">
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center">
                      <svg className="w-8 h-8 text-green-500 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div>
                        <p className="font-medium text-gray-900">{cardImage.name}</p>
                        <p className="text-sm text-gray-500">{(cardImage.size / 1024 / 1024).toFixed(2)} МБ</p>
                      </div>
                    </div>
                    <Button 
                      onClick={() => setCardImage(null)} 
                      variant="outline" 
                      size="sm"
                    >
                      Удалить
                    </Button>
                  </div>
                  
                  <Button 
                    onClick={handleAnalyzeCard} 
                    disabled={analyzingCard}
                    className="mt-4 bg-green-600 hover:bg-green-700"
                  >
                    {analyzingCard ? 'Анализируем...' : 'Анализировать карточку'}
                  </Button>
                </div>
              )}
              
              {cardAnalysis && (
                <div className="mt-6 bg-white border border-gray-200 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Результаты анализа</h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">Общая оценка:</span>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                        cardAnalysis.completeness_score >= 80 ? 'bg-green-100 text-green-800' :
                        cardAnalysis.completeness_score >= 60 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {cardAnalysis.completeness_score}/100
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <h4 className="font-medium text-gray-900 mb-2">Название бизнеса</h4>
                        <p className="text-gray-600">{cardAnalysis.business_name}</p>
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-900 mb-2">Категория</h4>
                        <p className="text-gray-600">{cardAnalysis.category}</p>
                      </div>
                    </div>
                    
                    <div>
                      <h4 className="font-medium text-gray-900 mb-2">Приоритетные действия</h4>
                      <ul className="list-disc list-inside space-y-1">
                        {cardAnalysis.priority_actions.map((action, index) => (
                          <li key={index} className="text-gray-600">{action}</li>
                        ))}
                      </ul>
                    </div>
                    
                    <div>
                      <h4 className="font-medium text-gray-900 mb-2">Общие рекомендации</h4>
                      <p className="text-gray-600">{cardAnalysis.overall_recommendations}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* SEO оптимизация прайс-листов */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">SEO оптимизация прайс-листов</h2>
            <div className="space-y-4">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors">
                <div className="flex flex-col items-center">
                  <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-lg font-medium text-gray-900 mb-2">Загрузите прайс-лист для оптимизации</p>
                  <p className="text-sm text-gray-500 mb-4">Поддерживаются форматы: PDF, DOC, DOCX, XLS, XLSX (до 15 МБ)</p>
                  <input
                    type="file"
                    accept=".pdf,.doc,.docx,.xls,.xlsx"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        if (file.size > 15 * 1024 * 1024) {
                          setError('Файл слишком большой. Максимальный размер: 15 МБ');
                          return;
                        }
                        setPriceListFile(file);
                      }
                    }}
                    className="hidden"
                    id="pricelist-upload"
                  />
                  <label htmlFor="pricelist-upload" className="bg-purple-600 text-white px-4 py-2 rounded-md cursor-pointer hover:bg-purple-700 transition-colors">
                    Выбрать файл
                  </label>
                </div>
              </div>
              
              {priceListFile && (
                <div className="mt-4">
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center">
                      <svg className="w-8 h-8 text-green-500 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div>
                        <p className="font-medium text-gray-900">{priceListFile.name}</p>
                        <p className="text-sm text-gray-500">{(priceListFile.size / 1024 / 1024).toFixed(2)} МБ</p>
                      </div>
                    </div>
                    <Button 
                      onClick={() => setPriceListFile(null)} 
                      variant="outline" 
                      size="sm"
                    >
                      Удалить
                    </Button>
                  </div>
                  
                  <Button 
                    onClick={handleOptimizePriceList} 
                    disabled={optimizingPriceList}
                    className="mt-4 bg-purple-600 hover:bg-purple-700"
                  >
                    {optimizingPriceList ? 'Оптимизируем...' : 'Оптимизировать прайс-лист'}
                  </Button>
                </div>
              )}
              
              {priceListOptimization && (
                <div className="mt-6 bg-white border border-gray-200 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Результаты SEO оптимизации</h3>
                  
                  <div className="space-y-6">
                    {/* Общие рекомендации */}
                    {priceListOptimization.general_recommendations && (
                      <div>
                        <h4 className="font-medium text-gray-900 mb-2">Общие рекомендации</h4>
                        <ul className="list-disc list-inside space-y-1">
                          {priceListOptimization.general_recommendations.map((rec, index) => (
                            <li key={index} className="text-gray-600">{rec}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {/* Оптимизированные услуги */}
                    {priceListOptimization.services && (
                      <div>
                        <h4 className="font-medium text-gray-900 mb-4">Оптимизированные услуги</h4>
                        <div className="space-y-4">
                          {priceListOptimization.services.map((service, index) => (
                            <div key={index} className="border border-gray-200 rounded-lg p-4">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                  <h5 className="font-medium text-gray-900 mb-1">Исходное название</h5>
                                  <p className="text-gray-600 text-sm">{service.original_name}</p>
                                </div>
                                <div>
                                  <h5 className="font-medium text-gray-900 mb-1">SEO название</h5>
                                  <p className="text-green-600 font-medium text-sm">{service.optimized_name}</p>
                                </div>
                                <div className="md:col-span-2">
                                  <h5 className="font-medium text-gray-900 mb-1">SEO описание</h5>
                                  <p className="text-gray-600 text-sm">{service.seo_description}</p>
                                </div>
                                <div>
                                  <h5 className="font-medium text-gray-900 mb-1">Ключевые слова</h5>
                                  <div className="flex flex-wrap gap-1">
                                    {service.keywords.map((keyword, keyIndex) => (
                                      <span key={keyIndex} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                                        {keyword}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                                <div>
                                  <h5 className="font-medium text-gray-900 mb-1">Цена</h5>
                                  <p className="text-gray-600 text-sm">{service.price || 'Не указана'}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                        
                        <div className="mt-4 flex gap-2">
                          <Button 
                            onClick={() => {
                              const csvContent = priceListOptimization.services.map(service => 
                                `${service.original_name},${service.optimized_name},"${service.seo_description}",${service.keywords.join(';')},${service.price || ''}`
                              ).join('\n');
                              const csvHeader = 'Исходное название,SEO название,SEO описание,Ключевые слова,Цена\n';
                              const blob = new Blob([csvHeader + csvContent], { type: 'text/csv' });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement('a');
                              a.href = url;
                              a.download = 'optimized-pricelist.csv';
                              a.click();
                              URL.revokeObjectURL(url);
                            }}
                            variant="outline"
                            size="sm"
                          >
                            Экспорт в CSV
                          </Button>
                          <Button 
                            onClick={() => {
                              const text = priceListOptimization.services.map(service => 
                                `${service.optimized_name}\n${service.seo_description}\nЦена: ${service.price || 'Не указана'}\nКлючевые слова: ${service.keywords.join(', ')}\n`
                              ).join('\n---\n');
                              navigator.clipboard.writeText(text);
                              setSuccess('Результаты скопированы в буфер обмена');
                            }}
                            variant="outline"
                            size="sm"
                          >
                            Копировать
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Приглашения */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Пригласить друга</h2>
            <InviteFriendForm
              onSuccess={() => setInviteSuccess(true)}
              onError={(error) => setError(error)}
            />
            {inviteSuccess && (
              <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mt-4">
                Приглашение отправлено!
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Модальное окно просмотра отчёта */}
        {viewingReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-4xl max-h-[90vh] w-full mx-4 overflow-hidden">
            <div className="flex justify-between items-center p-4 border-b">
              <h3 className="text-lg font-semibold">Просмотр отчёта</h3>
              <Button onClick={() => setViewingReport(null)} variant="outline">
                Закрыть
              </Button>
            </div>
            <div className="p-4 overflow-auto max-h-[calc(90vh-80px)]">
              {loadingReport ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
                  <p className="mt-2 text-gray-600">Загрузка отчёта...</p>
                </div>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: reportContent }} />
              )}
            </div>
            </div>
          </div>
        )}

      <Footer />
    </div>
  );
};

export default Dashboard;
