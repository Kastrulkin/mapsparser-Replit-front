import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
import { auth } from '../lib/auth';

interface AlternativePasswordResetProps {
  email: string;
  onSuccess?: () => void;
  onCancel?: () => void;
}

const AlternativePasswordReset: React.FC<AlternativePasswordResetProps> = ({ 
  email, 
  onSuccess, 
  onCancel 
}) => {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);

    // Валидация
    if (!newPassword || newPassword.length < 6) {
      setError('Пароль должен содержать минимум 6 символов');
      setLoading(false);
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают');
      setLoading(false);
      return;
    }

    try {
      // Ищем пользователя в базе данных
      const { data: user, error: userError } = await auth.findUserByEmail(email);
      
      if (userError || !user) {
        setError('Пользователь не найден в системе');
        setLoading(false);
        return;
      }

      // Сохраняем новый пароль в локальной системе
      localStorage.setItem(`user_${user.id}_password`, newPassword);
      
      setInfo('Пароль успешно обновлен! Теперь вы можете войти в систему.');
      
      // Очищаем форму
      setNewPassword('');
      setConfirmPassword('');
      
      // Вызываем callback успеха
      if (onSuccess) {
        onSuccess();
      }
      
      // Автоматический редирект через 2 секунды
      setTimeout(() => {
        navigate('/login');
      }, 2000);
      
    } catch (error) {
      console.error('Ошибка при сбросе пароля:', error);
      setError('Произошла ошибка при обновлении пароля');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded-xl shadow-md">
      <h3 className="text-xl font-bold mb-4">Альтернативное восстановление пароля</h3>
      
      <p className="text-sm text-gray-600 mb-4">
        Если письмо с восстановлением пароля не приходит, вы можете установить новый пароль напрямую.
      </p>
      
      <form onSubmit={handleReset} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Email</label>
          <input
            type="email"
            value={email}
            disabled
            className="w-full border rounded px-3 py-2 bg-gray-100 text-gray-600"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-1">Новый пароль</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={6}
            className="w-full border rounded px-3 py-2"
            placeholder="Минимум 6 символов"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-1">Подтвердите пароль</label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            className="w-full border rounded px-3 py-2"
            placeholder="Повторите пароль"
          />
        </div>
        
        {error && (
          <div className="text-red-600 text-sm bg-red-50 p-2 rounded">
            {error}
          </div>
        )}
        
        {info && (
          <div className="text-green-600 text-sm bg-green-50 p-2 rounded">
            {info}
          </div>
        )}
        
        <div className="flex gap-2">
          <Button
            type="submit"
            disabled={loading}
            className="flex-1"
          >
            {loading ? 'Обновление...' : 'Обновить пароль'}
          </Button>
          
          {onCancel && (
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={loading}
            >
              Отмена
            </Button>
          )}
        </div>
      </form>
      
      <div className="mt-4 text-xs text-gray-500">
        <p>⚠️ Внимание: Этот метод обновляет пароль только в локальной системе аутентификации.</p>
        <p>Для полной синхронизации с Supabase может потребоваться дополнительная настройка.</p>
      </div>
    </div>
  );
};

export default AlternativePasswordReset; 