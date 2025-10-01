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
  const [viewingReport, setViewingReport] = useState<string | null>(null);
  const [reportContent, setReportContent] = useState<string>("");
  const [loadingReport, setLoadingReport] = useState(false);
  const [showCreateReport, setShowCreateReport] = useState(false);
  const [createReportForm, setCreateReportForm] = useState({ yandexUrl: "" });
  const [creatingReport, setCreatingReport] = useState(false);

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
    const nextDate = getNextReportDate(reports);
    if (nextDate) {
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
    }
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
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-900">Личный кабинет</h1>
            <Button onClick={handleLogout} variant="outline">
              Выйти
            </Button>
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

          {/* Таймер следующего отчёта */}
          {timer && (
            <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3 rounded mb-6">
              <p className="font-medium">Следующий отчёт можно создать через: {timer}</p>
            </div>
          )}

          {/* Очередь обработки */}
          {queue.length > 0 && (
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">В обработке</h2>
              <div className="space-y-2">
                {queue.map((item) => (
                  <div key={item.id} className="bg-yellow-50 border border-yellow-200 rounded p-4">
                    <p className="text-sm text-gray-600">URL: {item.url}</p>
                    <p className="text-sm text-gray-600">Статус: {item.status}</p>
                    <p className="text-sm text-gray-600">
                      Создан: {new Date(item.created_at).toLocaleString()}
                    </p>
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
