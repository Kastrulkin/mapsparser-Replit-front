import React, { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { useLocation, useNavigate } from 'react-router-dom';

const SetPassword: React.FC = () => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Получаем временный пароль из localStorage
    const tempPassword = localStorage.getItem('tempPassword');
    if (!tempPassword || !email) {
      setError('Не удалось найти временный пароль или email. Попробуйте войти заново.');
      setLoading(false);
      return;
    }

    // Входим с временным паролем
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password: tempPassword,
    });
    if (signInError) {
      setError('Ошибка входа. Попробуйте ещё раз.');
      setLoading(false);
      return;
    }

    // Обновляем пароль
    const { error: updateError } = await supabase.auth.updateUser({ password });
    if (updateError) {
      setError('Ошибка при установке пароля');
      setLoading(false);
      return;
    }

    // Очищаем временный пароль
    localStorage.removeItem('tempPassword');
    // Редирект в личный кабинет
    navigate('/dashboard');
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-md mx-auto bg-white p-6 rounded-xl shadow-md flex flex-col gap-4 mt-12">
      <h2 className="text-2xl font-bold mb-2">Установите пароль для входа</h2>
      <input
        type="password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        required
        className="border rounded px-3 py-2"
        placeholder="Новый пароль"
      />
      <button
        type="submit"
        disabled={loading}
        className="bg-primary text-white rounded px-4 py-2 font-semibold hover:bg-primary/90 transition"
      >
        {loading ? 'Сохраняем...' : 'Установить пароль'}
      </button>
      {error && <div className="text-red-600">{error}</div>}
    </form>
  );
};

export default SetPassword; 