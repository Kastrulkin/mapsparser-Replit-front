import { useState } from "react";
import { supabase } from "@/lib/supabase";

const InviteFriendForm = ({ onSuccess }: { onSuccess?: () => void }) => {
  const [email, setEmail] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);

    // Получаем текущего пользователя
    const { data: { user }, error: userError } = await supabase.auth.getUser();
    if (userError || !user) {
      setError("Ошибка авторизации. Пожалуйста, войдите в аккаунт.");
      setLoading(false);
      return;
    }

    // Вставляем приглашение
    const { error: insertError } = await supabase
      .from("Invites")
      .insert({
        inviter_id: user.id,
        friend_email: email,
        friend_url: url,
      });

    if (insertError) {
      setError("Ошибка при сохранении приглашения.");
      setLoading(false);
      return;
    }

    // Отправляем красивый email с приглашением через Edge Function
    try {
      const { data: { user: currentUser } } = await supabase.auth.getUser();
      
      const response = await fetch(`${supabase.supabaseUrl}/functions/v1/send-invite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${supabase.supabaseKey}`,
        },
        body: JSON.stringify({
          friendEmail: email,
          friendUrl: url,
          inviterEmail: currentUser?.email || user.email
        })
      });

      if (!response.ok) {
        console.warn('Ошибка отправки email приглашения:', response.statusText);
        // Не критично, продолжаем
      } else {
        console.log('Email приглашения отправлен успешно');
      }
    } catch (emailError) {
      console.warn('Ошибка отправки email приглашения:', emailError);
      // Не критично, продолжаем
    }

    setSuccess(true);
    setEmail("");
    setUrl("");
    if (onSuccess) onSuccess();
    setLoading(false);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block mb-1">Email друга</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          className="border rounded px-3 py-2 w-full"
        />
      </div>
      <div>
        <label className="block mb-1">Ссылка на бизнес друга (Яндекс.Карты)</label>
        <input
          type="url"
          value={url}
          onChange={e => setUrl(e.target.value)}
          required
          className="border rounded px-3 py-2 w-full"
        />
      </div>
      {error && <div className="text-red-600">{error}</div>}
      {success && <div className="text-green-600">Спасибо! Можете сформировать отчёт вне очереди!</div>}
      <button
        type="submit"
        className="bg-primary text-white px-6 py-2 rounded"
        disabled={loading}
      >
        {loading ? "Отправка..." : "Пригласить"}
      </button>
    </form>
  );
};

export default InviteFriendForm; 