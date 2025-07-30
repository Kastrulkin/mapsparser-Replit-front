import { useEffect, useState } from "react";

import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { supabase } from "@/lib/supabase";
import InviteFriendForm from "@/components/InviteFriendForm";

function getNextReportDate(reports: any[]) {
  if (!reports.length) return null;
  const last = new Date(reports[0].created_at);
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
  const [profile, setProfile] = useState<any>(null);
  const [reports, setReports] = useState<any[]>([]);
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
  const [invites, setInvites] = useState<any[]>([]);
  const [showCreateReport, setShowCreateReport] = useState(false);
  const [createReportForm, setCreateReportForm] = useState({ yandexUrl: "" });
  const [creatingReport, setCreatingReport] = useState(false);
  const [hasRecentInvite, setHasRecentInvite] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const { data: { user } } = await supabase.auth.getUser();
      setUser(user);
      if (user) {
        const { data: profileData } = await supabase
          .from("Users")
          .select("*")
          .eq("id", user.id)
          .single();
        setProfile(profileData);
        setForm({
          email: profileData?.email || user.email || "",
          phone: profileData?.phone || "",
          name: profileData?.name || "",
          yandexUrl: profileData?.yandex_url || ""
        });
        // Автозаполняем форму создания отчёта
        setCreateReportForm({
          yandexUrl: profileData?.yandex_url || ""
        });
        // Получаем готовые отчёты из Cards
        const { data: reportsData } = await supabase
          .from("Cards")
          .select("id, url, created_at")
          .eq("user_id", user.id)
          .order("created_at", { ascending: false });
        
        // Получаем отчёты в обработке из ParseQueue
        const { data: queueData } = await supabase
          .from("ParseQueue")
          .select("id, url, created_at, status")
          .eq("user_id", user.id)
          .order("created_at", { ascending: false });
        
        // Объединяем отчёты: сначала готовые из Cards, потом в обработке из ParseQueue
        const allReports = [
          ...(reportsData || []).map(report => ({ ...report, status: 'completed', source: 'cards' })),
          ...(queueData || []).map(report => ({ ...report, status: report.status || 'pending', source: 'queue' }))
        ];
        
        setReports(allReports);
      }
      setLoading(false);
    };
    fetchData();
  }, [inviteSuccess]);

  useEffect(() => {
    if (!reports.length) return;
    const next = getNextReportDate(reports);
    if (!next) return setTimer(null);
    const update = () => {
      const str = getCountdownString(next);
      setTimer(str);
    };
    update();
    const interval = setInterval(update, 60000);
    return () => clearInterval(interval);
  }, [reports]);

  useEffect(() => {
    const fetchInvites = async () => {
      if (!user) return;
      const { data } = await supabase
        .from("Invites")
        .select("*")
        .eq("inviter_id", user.id);
      setInvites(data || []);
    };
    fetchInvites();
  }, [user, inviteSuccess]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSave = async () => {
    setError(null);
    setSuccess(null);
    const { error } = await supabase
      .from("Users")
      .update({
        email: form.email,
        phone: form.phone,
        name: form.name,
        yandex_url: form.yandexUrl
      })
      .eq("id", user.id);
    if (error) {
      setError("Ошибка при сохранении данных");
    } else {
      setSuccess("Данные успешно обновлены");
      setEditMode(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Вы уверены, что хотите удалить аккаунт? Это действие необратимо.")) return;
    await supabase.from("Users").delete().eq("id", user.id);
    await supabase.auth.signOut();
    window.location.href = "/";
  };

  const handleCreateReportChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCreateReportForm({ ...createReportForm, [e.target.name]: e.target.value });
  };

  const handleInviteSuccess = () => {
    setHasRecentInvite(true);
    setInviteSuccess(s => !s);
    // Сбрасываем флаг через 1 час
    setTimeout(() => setHasRecentInvite(false), 60 * 60 * 1000);
  };

  const handleDownloadReport = async (reportId: string) => {
    try {
      // Получаем информацию об отчёте
      const { data: reportData, error } = await supabase
        .from("Cards")
        .select("report_path, title")
        .eq("id", reportId)
        .single();

      if (error || !reportData) {
        setError("Отчёт не найден");
        return;
      }

      if (!reportData.report_path) {
        setError("Отчёт ещё не сгенерирован");
        return;
      }

      // Создаём ссылку для скачивания
      const downloadUrl = `http://localhost:8000/api/download-report/${reportId}`;
      
      // Создаём временную ссылку и скачиваем файл
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `seo_report_${reportData.title || reportId}.html`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setSuccess("Отчёт скачивается...");
    } catch (error: any) {
      setError("Ошибка при скачивании отчёта: " + error.message);
    }
  };

  const handleViewReport = async (reportId: string) => {
    if (viewingReport === reportId) {
      setViewingReport(null);
      setReportContent("");
      return;
    }

    setLoadingReport(true);
    try {
      // Получаем содержимое отчёта
      const response = await fetch(`http://localhost:8000/api/report-content/${reportId}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const content = await response.text();
      setReportContent(content);
      setViewingReport(reportId);
    } catch (error: any) {
      setError("Ошибка при загрузке отчёта: " + error.message);
    } finally {
      setLoadingReport(false);
    }
  };

  const handleCreateReport = async () => {
    if (!createReportForm.yandexUrl) {
      setError("Пожалуйста, укажите ссылку на бизнес");
      return;
    }

    setCreatingReport(true);
    setError(null);
    setSuccess(null);

    try {
      console.log('Создание отчёта:', {
        user_id: user?.id,
        url: createReportForm.yandexUrl,
        email: user?.email
      });

      // Проверяем авторизацию
      const { data: { user: currentUser }, error: authError } = await supabase.auth.getUser();
      if (authError || !currentUser) {
        throw new Error('Пользователь не авторизован');
      }

      console.log('Пользователь авторизован:', currentUser.id);

      // Создаём новую запись в таблице ParseQueue для обработки
      const { data: queueData, error: queueError } = await supabase
        .from("ParseQueue")
        .insert({
          user_id: currentUser.id,
          url: createReportForm.yandexUrl,
          email: currentUser.email,
          status: 'pending'
        })
        .select()
        .single();

      console.log('Результат создания записи:', { queueData, queueError });

      if (queueError) {
        throw queueError;
      }

      // Обновляем профиль пользователя с новой ссылкой
      await supabase
        .from("Users")
        .update({ yandex_url: createReportForm.yandexUrl })
        .eq("id", user.id);

      setSuccess("Запрос на создание отчёта отправлен! Обработка займёт в среднем около дня, т.к. все отчёты проверяются человеком.");
      setShowCreateReport(false);
      
      // Обновляем список отчётов (готовые отчёты из Cards)
      const { data: reportsData } = await supabase
        .from("Cards")
        .select("id, url, created_at")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false });
      setReports(reportsData || []);

    } catch (error: any) {
      setError(error.message || "Ошибка при создании отчёта");
    } finally {
      setCreatingReport(false);
    }
  };

  const canCreateReport = !reports.length || (getNextReportDate(reports) && new Date() >= getNextReportDate(reports)) || hasRecentInvite;

  if (loading) return <div className="min-h-screen flex items-center justify-center">Загрузка...</div>;

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5">
      {/* Hero Section */}
      <section className="py-24 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-primary/5 opacity-30" />
        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-6">
            Личный <span className="text-primary">кабинет</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Управляйте своими данными, отчётами и подпиской
          </p>
        </div>
      </section>
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-16 -mt-8">
        {/* Profile Data */}
        <div className="bg-card/80 backdrop-blur-sm rounded-3xl shadow-xl border border-primary/10 p-8 mb-8">
          <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
            <div className="w-8 h-8 bg-primary/20 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-primary" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
              </svg>
            </div>
            Данные аккаунта
          </h2>
          {editMode ? (
            <div className="space-y-6">
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Email</label>
                  <input 
                    type="email" 
                    name="email" 
                    value={form.email} 
                    onChange={handleChange} 
                    className="w-full px-4 py-3 rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200" 
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Телефон</label>
                  <input 
                    type="text" 
                    name="phone" 
                    value={form.phone} 
                    onChange={handleChange} 
                    className="w-full px-4 py-3 rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200" 
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Имя</label>
                <input 
                  type="text" 
                  name="name" 
                  value={form.name} 
                  onChange={handleChange} 
                  className="w-full px-4 py-3 rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200" 
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Ссылка на организацию (Яндекс.Карты)</label>
                <input 
                  type="url" 
                  name="yandexUrl" 
                  value={form.yandexUrl} 
                  onChange={handleChange} 
                  className="w-full px-4 py-3 rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200" 
                />
              </div>
              {error && <div className="text-destructive text-sm bg-destructive/10 px-4 py-2 rounded-lg">{error}</div>}
              {success && <div className="text-green-600 text-sm bg-green-50 px-4 py-2 rounded-lg">{success}</div>}
              <div className="flex flex-col sm:flex-row gap-4">
                <Button onClick={handleSave} className="flex-1">Сохранить изменения</Button>
                <Button variant="outline" onClick={() => setEditMode(false)} className="flex-1">Отмена</Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div className="flex justify-between items-center py-3 border-b border-border/50">
                    <span className="text-sm font-medium text-muted-foreground">Email:</span>
                    <span className="text-foreground">{profile?.email || "—"}</span>
                  </div>
                  <div className="flex justify-between items-center py-3 border-b border-border/50">
                    <span className="text-sm font-medium text-muted-foreground">Телефон:</span>
                    <span className="text-foreground">{profile?.phone || "—"}</span>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="flex justify-between items-center py-3 border-b border-border/50">
                    <span className="text-sm font-medium text-muted-foreground">Имя:</span>
                    <span className="text-foreground">{profile?.name || "—"}</span>
                  </div>
                  <div className="flex justify-between items-center py-3 border-b border-border/50">
                    <span className="text-sm font-medium text-muted-foreground">Ссылка на бизнес:</span>
                    <span className="text-foreground break-all">{profile?.yandex_url || "—"}</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col sm:flex-row gap-4 pt-4">
                <Button onClick={() => setEditMode(true)} variant="outline" className="flex-1">Изменить данные</Button>
                <Button variant="destructive" onClick={handleDelete} className="flex-1">Удалить аккаунт</Button>
              </div>
            </div>
          )}
        </div>
        {/* Invites List */}
        <div className="bg-card/80 rounded-3xl shadow-xl border p-8 mb-8">
          <h2 className="text-2xl font-bold mb-4">Мои приглашённые</h2>
          {invites.length === 0 ? (
            <div>Пока нет приглашённых.</div>
          ) : (
            <ul>
              {invites.map(invite => (
                <li key={invite.id}>
                  {invite.friend_email} — {invite.used ? "Принято" : "Ожидает"}
                </li>
              ))}
            </ul>
          )}
        </div>
        {/* Report Generation и Contact Us теперь друг под другом */}
        <div className="space-y-8">
          {/* Report Generation */}
          <div className="bg-card/80 backdrop-blur-sm rounded-3xl shadow-xl border border-primary/10 p-8">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <div className="w-8 h-8 bg-primary/20 rounded-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-primary" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
                  <path fillRule="evenodd" d="M4 5a2 2 0 012-2v1a1 1 0 102 0V3h4v1a1 1 0 102 0V3a2 2 0 012 2v6a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm2.5 7a1.5 1.5 0 100-3 1.5 1.5 0 000 3zm2.45.75a2.5 2.5 0 10-4.9 0h4.9zM12 9a1 1 0 100-2 1 1 0 000 2zm-2 3a1 1 0 100-2 1 1 0 000 2zm2 1a1 1 0 100-2 1 1 0 000 2zm2-3a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
              </div>
              Создание отчётов
            </h2>
            <div className="space-y-6">
              {/* Timer Display - Always Visible */}
              <div className="text-center p-8 bg-gradient-to-br from-background/50 to-muted/20 rounded-3xl border border-border/20">
                <h3 className="text-lg font-semibold text-foreground mb-4">
                  {canCreateReport ? 'Отчёт готов к созданию' : 'До следующего отчёта'}
                </h3>
                <div className={`text-6xl md:text-7xl font-bold tracking-tight mb-2 ${
                  canCreateReport 
                    ? 'text-green-500' 
                    : 'text-red-500'
                }`}>
                  {canCreateReport ? '00:00:00' : timer || '00:00:00'}
                </div>
                <div className="flex justify-center gap-2 text-sm text-muted-foreground">
                  <span className="px-3 py-1 bg-muted/20 rounded-lg">
                    {canCreateReport ? 'Дни' : 'Дни'}
                  </span>
                  <span className="px-3 py-1 bg-muted/20 rounded-lg">
                    {canCreateReport ? 'Часы' : 'Часы'}
                  </span>
                  <span className="px-3 py-1 bg-muted/20 rounded-lg">
                    {canCreateReport ? 'Минуты' : 'Минуты'}
                  </span>
                </div>
              </div>
              {/* Create Report Form - When Available */}
              {canCreateReport && (
                <div className="text-center p-6 bg-gradient-to-br from-green-500/10 to-green-600/20 rounded-2xl border border-green-500/20">
                  <div className="w-16 h-16 bg-green-500/20 rounded-2xl mx-auto mb-4 flex items-center justify-center">
                    <svg className="w-8 h-8 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-2">Отчёт доступен</h3>
                  <p className="text-muted-foreground mb-4">Вы можете сформировать новый SEO отчёт</p>
                  
                  {!showCreateReport ? (
                    <Button 
                      size="lg" 
                      className="w-full animate-pulse"
                      onClick={() => setShowCreateReport(true)}
                    >
                      Сформировать новый отчёт
                    </Button>
                  ) : (
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-foreground mb-2 text-left">
                          Ссылка на бизнес (Яндекс.Карты)
                        </label>
                        <input 
                          type="url" 
                          name="yandexUrl" 
                          value={createReportForm.yandexUrl} 
                          onChange={handleCreateReportChange} 
                          placeholder="https://yandex.ru/maps/org/..."
                          className="w-full px-4 py-3 rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200" 
                        />
                      </div>
                      {error && <div className="text-destructive text-sm bg-destructive/10 px-4 py-2 rounded-lg">{error}</div>}
                      {success && <div className="text-green-600 text-sm bg-green-50 px-4 py-2 rounded-lg">{success}</div>}
                      <div className="flex gap-3">
                        <Button 
                          size="lg" 
                          className="flex-1"
                          onClick={handleCreateReport}
                          disabled={creatingReport}
                        >
                          {creatingReport ? 'Создание...' : 'Создать отчёт'}
                        </Button>
                        <Button 
                          variant="outline" 
                          size="lg"
                          onClick={() => setShowCreateReport(false)}
                          disabled={creatingReport}
                        >
                          Отмена
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
              {/* Invite Friend Form - When Timer is Running */}
              {!canCreateReport && (
                <div className="border-t border-border/20 pt-6">
                  <div className="text-center mb-6">
                    <div className="w-16 h-16 bg-primary/20 rounded-2xl mx-auto mb-4 flex items-center justify-center">
                      <svg className="w-8 h-8 text-primary" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M8 9a3 3 0 100-6 3 3 0 000 6zM8 11a6 6 0 016 6H2a6 6 0 016-6zM16 7a1 1 0 10-2 0v1h-1a1 1 0 100 2h1v1a1 1 0 102 0v-1h1a1 1 0 100-2h-1V7z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">Хотите отчёт раньше?</h3>
                    <p className="text-sm text-muted-foreground">
                      Пригласите друга и получите возможность создать отчёт досрочно
                    </p>
                  </div>
                  <InviteFriendForm onSuccess={handleInviteSuccess} />
                </div>
              )}
            </div>
          </div>
          {/* Contact Us */}
          <div className="bg-card/80 backdrop-blur-sm rounded-3xl shadow-xl border border-primary/10 p-8">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <div className="w-8 h-8 bg-primary/20 rounded-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-primary" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z" />
                </svg>
              </div>
              Связаться с нами
            </h2>
            <div className="space-y-6">
              <div className="text-center p-6 bg-gradient-to-br from-primary/5 to-primary/10 rounded-2xl border border-primary/20">
                <h3 className="text-lg font-semibold text-foreground mb-2">Нужно больше?</h3>
                <p className="text-muted-foreground mb-4">
                  Перейдите на платный тариф и получите полную автоматизацию с ИИ агентами
                </p>
                <Button 
                  size="lg" 
                  className="w-full"
                  onClick={() => window.location.href = '/#cta'}
                >
                  Узнать о тарифах
                </Button>
              </div>
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 bg-muted/10 rounded-xl">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-muted-foreground">Агент администратор</span>
                </div>
                <div className="flex items-center gap-3 p-4 bg-muted/10 rounded-xl">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-muted-foreground">Агент привлечения клиентов</span>
                </div>
                <div className="flex items-center gap-3 p-4 bg-muted/10 rounded-xl">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-sm text-muted-foreground">Персональный менеджер</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        {/* Reports History */}
        <div className="bg-card/80 backdrop-blur-sm rounded-3xl shadow-xl border border-primary/10 p-8 mt-8">
          <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
            <div className="w-8 h-8 bg-primary/20 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-primary" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 0v12h8V4H6z" clipRule="evenodd" />
              </svg>
            </div>
            История отчётов
          </h2>
          {reports.length === 0 ? (
            <div className="text-center p-12">
              <div className="w-16 h-16 bg-muted/20 rounded-2xl mx-auto mb-4 flex items-center justify-center">
                <svg className="w-8 h-8 text-muted-foreground" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 0v12h8V4H6z" clipRule="evenodd" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">Отчётов пока нет</h3>
              <p className="text-muted-foreground">Создайте свой первый SEO отчёт, чтобы увидеть его здесь</p>
            </div>
          ) : (
            <div className="space-y-4">
              {reports.map((report) => (
                <div key={report.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-6 bg-muted/5 rounded-2xl border border-border/20 hover:bg-muted/10 transition-all duration-200">
                  <div className="space-y-2">
                    <h4 className="font-semibold text-foreground">{report.url}</h4>
                    <div className="flex items-center gap-2">
                      <p className="text-sm text-muted-foreground">
                        Создан: {new Date(report.created_at).toLocaleDateString('ru-RU', { 
                          year: 'numeric', 
                          month: 'long', 
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </p>
                      {report.status === 'pending' && (
                        <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full">
                          В очереди
                        </span>
                      )}
                      {report.status === 'processing' && (
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                          Обрабатывается
                        </span>
                      )}
                      {report.status === 'completed' && (
                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          Готов
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2 mt-4 sm:mt-0">
                    {report.status === 'completed' ? (
                      <>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleViewReport(report.id)}
                          disabled={loadingReport}
                        >
                          {loadingReport ? 'Загрузка...' : (viewingReport === report.id ? 'Закрыть' : 'Просмотр')}
                        </Button>
                        <Button 
                          variant="default" 
                          size="sm"
                          onClick={() => handleDownloadReport(report.id)}
                        >
                          Скачать
                        </Button>
                      </>
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        Обработка займёт в среднем около дня, т.к. все отчёты проверяются человеком
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {/* Report Viewer Modal */}
        {viewingReport && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-card rounded-3xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
              <div className="flex items-center justify-between p-6 border-b border-border/20">
                <h3 className="text-xl font-semibold text-foreground">Просмотр отчёта</h3>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setViewingReport(null)}
                >
                  ✕
                </Button>
              </div>
              <div className="p-6 overflow-auto max-h-[calc(90vh-120px)]">
                {reportContent ? (
                  <div 
                    dangerouslySetInnerHTML={{ __html: reportContent }}
                    className="prose prose-sm max-w-none"
                  />
                ) : (
                  <div className="text-center text-muted-foreground">
                    Загрузка отчёта...
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
};

export default Dashboard;