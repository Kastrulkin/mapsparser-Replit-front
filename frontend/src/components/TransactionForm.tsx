import React, { useState } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Upload, FileText, Image as ImageIcon, X } from 'lucide-react';
import { getApiEndpoint } from '../config/api';

interface TransactionFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

const TransactionForm: React.FC<TransactionFormProps> = ({ onSuccess, onCancel }) => {
  const [formData, setFormData] = useState({
    transaction_date: new Date().toISOString().split('T')[0],
    amount: '',
    client_type: 'new',
    services: '',
    master_id: '',
    notes: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadMode, setUploadMode] = useState<'manual' | 'file' | 'photo'>('manual');
  const [file, setFile] = useState<File | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [processingFile, setProcessingFile] = useState(false);

  const handleFileUpload = async () => {
    if (!file && !photo) {
      setError('Выберите файл или фото');
      return;
    }

    setProcessingFile(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const formDataToSend = new FormData();

      if (file) {
        formDataToSend.append('file', file);
      }
      if (photo) {
        formDataToSend.append('photo', photo);
      }

      const response = await fetch(getApiEndpoint('/api/finance/transaction/upload'), {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formDataToSend
      });

      const data = await response.json();

      if (data.success && data.transactions && data.transactions.length > 0) {
        // Заполняем форму данными из первой транзакции
        const firstTransaction = data.transactions[0];
        setFormData({
          transaction_date: firstTransaction.transaction_date || new Date().toISOString().split('T')[0],
          amount: String(firstTransaction.amount || ''),
          client_type: firstTransaction.client_type || 'new',
          services: Array.isArray(firstTransaction.services) ? firstTransaction.services.join(', ') : '',
          master_id: firstTransaction.master_id || '',
          notes: firstTransaction.notes || ''
        });

        // Если транзакций несколько, можно показать уведомление
        if (data.transactions.length > 1) {
          setError(`Загружено ${data.transactions.length} транзакций. Заполнена первая.`);
        }
      } else {
        setError(data.error || 'Не удалось распознать транзакции из файла');
      }
    } catch (error) {
      setError('Ошибка обработки файла');
    } finally {
      setProcessingFile(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(getApiEndpoint('/api/finance/transaction'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          ...formData,
          amount: parseFloat(formData.amount),
          services: formData.services ? formData.services.split(',').map(s => s.trim()) : []
        })
      });

      const data = await response.json();

      if (data.success) {
        setFormData({
          transaction_date: new Date().toISOString().split('T')[0],
          amount: '',
          client_type: 'new',
          services: '',
          master_id: '',
          notes: ''
        });
        setFile(null);
        setPhoto(null);
        setUploadMode('manual');
        onSuccess?.();
      } else {
        setError(data.error || 'Ошибка добавления транзакции');
      }
    } catch (error) {
      setError('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">💰 Добавить транзакцию</h3>

      {/* Переключатель режима */}
      <div className="mb-4 flex gap-2">
        <Button
          type="button"
          variant={uploadMode === 'manual' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setUploadMode('manual')}
        >
          Ручной ввод
        </Button>
        <Button
          type="button"
          variant={uploadMode === 'file' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setUploadMode('file')}
        >
          <FileText className="w-4 h-4 mr-2" />
          Загрузить файл
        </Button>
        <Button
          type="button"
          variant={uploadMode === 'photo' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setUploadMode('photo')}
        >
          <ImageIcon className="w-4 h-4 mr-2" />
          Загрузить фото
        </Button>
      </div>

      {/* Загрузка файла/фото */}
      {(uploadMode === 'file' || uploadMode === 'photo') && (
        <div className="mb-4 p-4 border-2 border-dashed border-gray-300 rounded-lg">
          <Label htmlFor={uploadMode === 'file' ? 'file-upload' : 'photo-upload'} className="cursor-pointer">
            <div className="flex flex-col items-center justify-center space-y-2">
              <Upload className="w-8 h-8 text-gray-400" />
              <span className="text-sm text-gray-600">
                {uploadMode === 'file'
                  ? 'Выберите файл (PDF, DOC, XLS, TXT, CSV)'
                  : 'Выберите фото (PNG, JPG, JPEG)'}
              </span>
            </div>
          </Label>
          <Input
            id={uploadMode === 'file' ? 'file-upload' : 'photo-upload'}
            type="file"
            accept={uploadMode === 'file' ? '.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv' : 'image/*'}
            className="hidden"
            onChange={(e) => {
              const selectedFile = e.target.files?.[0];
              if (selectedFile) {
                if (uploadMode === 'file') {
                  setFile(selectedFile);
                } else {
                  setPhoto(selectedFile);
                }
              }
            }}
          />
          {(file || photo) && (
            <div className="mt-2 flex items-center justify-between p-2 bg-gray-50 rounded">
              <span className="text-sm text-gray-700">
                {file?.name || photo?.name}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFile(null);
                  setPhoto(null);
                }}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          )}
          <Button
            type="button"
            onClick={handleFileUpload}
            disabled={processingFile || (!file && !photo)}
            className="mt-2 w-full"
          >
            {processingFile ? 'Обрабатываем...' : 'Распознать транзакции'}
          </Button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="transaction_date">Дата</Label>
            <Input
              id="transaction_date"
              type="date"
              value={formData.transaction_date}
              onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
              required
            />
          </div>

          <div>
            <Label htmlFor="amount">Сумма (₽)</Label>
            <Input
              id="amount"
              type="number"
              step="0.01"
              min="0"
              value={formData.amount}
              onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
              placeholder="0.00"
              required
            />
          </div>
        </div>

        <div>
          <Label htmlFor="client_type">Тип клиента</Label>
          <Select
            value={formData.client_type}
            onValueChange={(value) => setFormData({ ...formData, client_type: value })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="new">🆕 Новый клиент</SelectItem>
              <SelectItem value="returning">🔄 Повторный клиент</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label htmlFor="services">Услуги (через запятую)</Label>
          <Input
            id="services"
            value={formData.services}
            onChange={(e) => setFormData({ ...formData, services: e.target.value })}
            placeholder="Стрижка, Окрашивание, Маникюр"
          />
        </div>

        <div>
          <Label htmlFor="master_id">ID мастера (опционально)</Label>
          <Input
            id="master_id"
            value={formData.master_id}
            onChange={(e) => setFormData({ ...formData, master_id: e.target.value })}
            placeholder="ID мастера"
          />
        </div>

        <div>
          <Label htmlFor="notes">Примечания</Label>
          <Textarea
            id="notes"
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            placeholder="Дополнительная информация..."
            rows={3}
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <Button type="submit" disabled={loading} className="flex-1">
            {loading ? 'Добавляем...' : 'Добавить транзакцию'}
          </Button>
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              Отмена
            </Button>
          )}
        </div>
      </form>
    </div>
  );
};

export default TransactionForm;
