import { browserBearerToken } from '@/lib/browserSessionFetch';
import { errorMessage } from '@/lib/errorMessage';
import React, { useRef, useState } from 'react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';

interface CreateBusinessModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (businessId: string) => void;
}

export const CreateBusinessModal: React.FC<CreateBusinessModalProps> = ({
  isOpen,
  onClose,
  onSuccess
}) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    industry: '',
    owner_email: '',
    owner_name: '',
    owner_phone: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setError(null);
    setLoading(true);

    try {
      const token = browserBearerToken();

      // Создаём бизнес (API сам найдёт или создаст пользователя по email)
      const businessResponse = await fetch('/api/superadmin/businesses', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description || '',
          industry: formData.industry || '',
          owner_email: formData.owner_email,
          owner_name: formData.owner_name || '',
          owner_phone: formData.owner_phone || ''
        })
      });

      if (!businessResponse.ok) {
        const errorData = await businessResponse.json();
        throw new Error(errorData.error || 'Ошибка создания бизнеса');
      }

      const businessData = await businessResponse.json();
      onSuccess(businessData.business_id);
      onClose();
      setFormData({
        name: '',
        description: '',
        industry: '',
        owner_email: '',
        owner_name: '',
        owner_phone: ''
      });
    } catch (err: unknown) {
      setError(errorMessage(err) || 'Ошибка создания бизнеса');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open && !loading) onClose(); }}>
      <DialogContent
        className="max-h-[90dvh] w-[calc(100%-2rem)] max-w-md overflow-y-auto rounded-lg"
        onOpenAutoFocus={() => {
          returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        }}
        onCloseAutoFocus={(event) => {
          if (returnFocus.current?.isConnected) {
            event.preventDefault();
            returnFocus.current.focus();
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>Создать новый бизнес</DialogTitle>
          <DialogDescription>Укажите данные бизнеса и почту владельца.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <div>
            <Label htmlFor="name">Название бизнеса *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              placeholder="Например: Салон красоты Элегант"
            />
          </div>

          <div>
            <Label htmlFor="description">Описание</Label>
            <Input
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Краткое описание бизнеса"
            />
          </div>

          <div>
            <Label htmlFor="industry">Отрасль</Label>
            <Input
              id="industry"
              value={formData.industry}
              onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
              placeholder="Например: beauty_salon"
            />
          </div>

          <div className="border-t pt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Владелец бизнеса</h3>

            <div className="space-y-3">
              <div>
                <Label htmlFor="owner_email">Email владельца *</Label>
                <Input
                  id="owner_email"
                  type="email"
                  value={formData.owner_email}
                  onChange={(e) => setFormData({ ...formData, owner_email: e.target.value })}
                  required
                  placeholder="owner@example.com"
                />
              </div>

              <div>
                <Label htmlFor="owner_name">Имя владельца</Label>
                <Input
                  id="owner_name"
                  value={formData.owner_name}
                  onChange={(e) => setFormData({ ...formData, owner_name: e.target.value })}
                  placeholder="Иван Иванов"
                />
              </div>

              <div>
                <Label htmlFor="owner_phone">Телефон владельца</Label>
                <Input
                  id="owner_phone"
                  type="tel"
                  value={formData.owner_phone}
                  onChange={(e) => setFormData({ ...formData, owner_phone: e.target.value })}
                  placeholder="+7 (999) 123-45-67"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
              Отмена
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Создание...' : 'Создать бизнес'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
