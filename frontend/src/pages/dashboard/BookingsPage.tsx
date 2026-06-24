import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { Ban, BarChart3, Calendar, FileText, Lightbulb, Loader2, Mail, Newspaper, Phone, Repeat, User } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';

interface Booking {
  id: string;
  client_name: string;
  client_phone: string;
  client_email?: string;
  service_name?: string;
  booking_time: string;
  booking_time_local?: string;
  source: string;
  status: string;
  notes?: string;
  created_at: string;
}

export const BookingsPage = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingBookingId, setUpdatingBookingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const { toast } = useToast();
  const { t, language } = useLanguage();

  const STATUS_OPTIONS = [
    { value: 'all', label: t.dashboard.bookings.status.all },
    { value: 'pending', label: 'Не разобрано' },
    { value: 'confirmed', label: 'Учтено в статистике' },
    { value: 'cancelled', label: 'Исключено' },
    { value: 'no_show', label: 'No-show' },
    { value: 'returning_client', label: 'Повторные клиенты' },
  ];

  useEffect(() => {
    if (currentBusinessId) {
      fetchBookings();
    }
  }, [currentBusinessId, statusFilter]);

  const fetchBookings = async () => {
    if (!currentBusinessId) return;

    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const url = new URL('/api/bookings', window.location.origin);
      url.searchParams.append('business_id', currentBusinessId);
      if (statusFilter !== 'all') {
        url.searchParams.append('status', statusFilter);
      }

      const response = await fetch(url.toString(), {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setBookings(data.bookings || []);
      } else {
        toast({
          title: t.error,
          description: t.dashboard.bookings.messages.loadError,
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t.error,
        description: t.dashboard.bookings.messages.loadError,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const updateBookingStatus = async (bookingId: string, newStatus: string, successMessage: string) => {
    setUpdatingBookingId(bookingId);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/bookings/${bookingId}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ status: newStatus })
      });

      if (response.ok) {
        toast({
          title: t.success,
          description: successMessage,
        });
        fetchBookings();
      } else {
        const data = await response.json();
        toast({
          title: t.error,
          description: data.error || t.dashboard.bookings.messages.updateError,
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t.error,
        description: t.dashboard.bookings.messages.updateError,
        variant: 'destructive',
      });
    } finally {
      setUpdatingBookingId(null);
    }
  };

  const showPlanningToast = (title: string, description: string) => {
    toast({ title, description });
  };

  const getStatusBadge = (status: string) => {
    const statusKey = status as keyof typeof t.dashboard.bookings.status;
    const label = t.dashboard.bookings.status[statusKey] || status;

    switch (status) {
      case 'pending':
        return <Badge className="border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-50">Не разобрано</Badge>;
      case 'confirmed':
      case 'completed':
        return <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-50">В статистике</Badge>;
      case 'cancelled':
        return <Badge className="border-slate-200 bg-slate-100 text-slate-600 hover:bg-slate-100">Исключено</Badge>;
      case 'no_show':
        return <Badge className="border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-50">No-show</Badge>;
      case 'returning_client':
        return <Badge className="border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-50">Повторный клиент</Badge>;
      default:
        return <Badge>{label}</Badge>;
    }
  };

  const getSourceBadge = (source: string) => {
    const normalized = String(source || '').toLowerCase();
    if (normalized.includes('crm') || normalized.includes('yclients')) {
      return (
        <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-50">
          CRM подключена
        </Badge>
      );
    }
    return <Badge variant="outline">{source || 'LocalOS'}</Badge>;
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString(language === 'en' ? 'en-US' : 'ru-RU', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.dashboard.bookings.title}</h1>
          <p className="text-gray-600 mt-1">Аналитический слой по записям из CRM: статистика, контент, допродажи и планирование.</p>
        </div>
        <div className="flex items-center gap-4">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={fetchBookings} variant="outline" size="sm">
            {t.dashboard.bookings.refresh}
          </Button>
        </div>
      </div>

      <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
        Записи загружены из CRM и используются для статистики, контента, допродаж и планирования. LocalOS не меняет запись в CRM.
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t.dashboard.bookings.list}</CardTitle>
          <CardDescription>
            {t.dashboard.bookings.total} {bookings.length}. Источник остаётся CRM, решения ниже влияют только на аналитику LocalOS.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          ) : bookings.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Calendar className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <p>{t.dashboard.bookings.empty}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.dashboard.bookings.table.client}</TableHead>
                    <TableHead>{t.dashboard.bookings.table.service}</TableHead>
                    <TableHead>{t.dashboard.bookings.table.dateTime}</TableHead>
                    <TableHead>{t.dashboard.bookings.table.source}</TableHead>
                    <TableHead>Использование</TableHead>
                    <TableHead>Использовать для</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bookings.map((booking) => (
                    <TableRow key={booking.id}>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <User className="h-4 w-4 text-gray-400" />
                            <span className="font-medium">{booking.client_name}</span>
                          </div>
                          <div className="flex items-center gap-2 text-sm text-gray-500">
                            <Phone className="h-3 w-3" />
                            {booking.client_phone}
                          </div>
                          {booking.client_email && (
                            <div className="flex items-center gap-2 text-sm text-gray-500">
                              <Mail className="h-3 w-3" />
                              {booking.client_email}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {booking.service_name || '—'}
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div>{formatDate(booking.booking_time)}</div>
                          {booking.booking_time_local && (
                            <div className="text-xs text-gray-500">
                              {booking.booking_time_local}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {getSourceBadge(booking.source)}
                      </TableCell>
                      <TableCell>
                        {getStatusBadge(booking.status)}
                      </TableCell>
                      <TableCell>
                        <div className="flex max-w-[520px] flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1.5"
                            disabled={updatingBookingId === booking.id}
                            onClick={() => updateBookingStatus(booking.id, 'confirmed', 'Запись будет учитываться в загрузке, среднем чеке и спросе по услугам.')}
                          >
                            <BarChart3 className="h-3.5 w-3.5" />
                            Учесть
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1.5"
                            disabled={updatingBookingId === booking.id}
                            onClick={() => updateBookingStatus(booking.id, 'cancelled', 'Запись исключена из аналитики LocalOS. В CRM ничего не изменилось.')}
                          >
                            <Ban className="h-3.5 w-3.5" />
                            Исключить
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1.5"
                            disabled={updatingBookingId === booking.id}
                            onClick={() => updateBookingStatus(booking.id, 'no_show', 'Запись отмечена как no-show для статистики потерь.')}
                          >
                            <Calendar className="h-3.5 w-3.5" />
                            No-show
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1.5"
                            disabled={updatingBookingId === booking.id}
                            onClick={() => updateBookingStatus(booking.id, 'returning_client', 'Запись отмечена как повторный клиент для удержания и LTV.')}
                          >
                            <Repeat className="h-3.5 w-3.5" />
                            Повторный
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1.5"
                            onClick={() => showPlanningToast(
                              'Тема для контент-плана',
                              `Можно добавить тему по услуге «${booking.service_name || 'услуга'}» в очередь публикаций.`,
                            )}
                          >
                            <FileText className="h-3.5 w-3.5" />
                            В контент-план
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1.5"
                            onClick={() => showPlanningToast(
                              'Идея новости',
                              `LocalOS может подготовить новость по спросу на «${booking.service_name || 'услугу'}».`,
                            )}
                          >
                            <Newspaper className="h-3.5 w-3.5" />
                            Новость
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1.5"
                            onClick={() => showPlanningToast(
                              'Идея допродажи',
                              `Используйте эту запись как сигнал для связки услуги «${booking.service_name || 'услуга'}» с подходящим дополнением.`,
                            )}
                          >
                            <Lightbulb className="h-3.5 w-3.5" />
                            Допродажа
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
