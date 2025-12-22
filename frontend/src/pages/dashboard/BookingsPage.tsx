import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { Loader2, Calendar, Phone, Mail, User } from 'lucide-react';

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

const STATUS_OPTIONS = [
  { value: 'all', label: 'Все' },
  { value: 'pending', label: 'Ожидает подтверждения' },
  { value: 'confirmed', label: 'Подтверждено' },
  { value: 'cancelled', label: 'Отменено' },
  { value: 'completed', label: 'Завершено' },
];

export const BookingsPage = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const { toast } = useToast();

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
          title: 'Ошибка',
          description: 'Не удалось загрузить бронирования',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Ошибка при загрузке бронирований',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const updateBookingStatus = async (bookingId: string, newStatus: string) => {
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
          title: 'Успешно',
          description: 'Статус бронирования обновлён',
        });
        fetchBookings();
      } else {
        const data = await response.json();
        toast({
          title: 'Ошибка',
          description: data.error || 'Не удалось обновить статус',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Ошибка при обновлении статуса',
        variant: 'destructive',
      });
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return <Badge className="bg-yellow-500">Ожидает</Badge>;
      case 'confirmed':
        return <Badge className="bg-green-500">Подтверждено</Badge>;
      case 'cancelled':
        return <Badge className="bg-red-500">Отменено</Badge>;
      case 'completed':
        return <Badge className="bg-blue-500">Завершено</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('ru-RU', {
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
          <h1 className="text-2xl font-bold text-gray-900">Бронирования</h1>
          <p className="text-gray-600 mt-1">Управляйте заявками от клиентов</p>
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
            Обновить
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Список бронирований</CardTitle>
          <CardDescription>
            Всего: {bookings.length} {bookings.length === 1 ? 'бронирование' : 'бронирований'}
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
              <p>Нет бронирований</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Клиент</TableHead>
                    <TableHead>Услуга</TableHead>
                    <TableHead>Дата и время</TableHead>
                    <TableHead>Источник</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead>Действия</TableHead>
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
                        <Badge variant="outline">{booking.source}</Badge>
                      </TableCell>
                      <TableCell>
                        {getStatusBadge(booking.status)}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          {booking.status === 'pending' && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => updateBookingStatus(booking.id, 'confirmed')}
                              >
                                Подтвердить
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => updateBookingStatus(booking.id, 'cancelled')}
                              >
                                Отменить
                              </Button>
                            </>
                          )}
                          {booking.status === 'confirmed' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => updateBookingStatus(booking.id, 'completed')}
                            >
                              Завершить
                            </Button>
                          )}
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

