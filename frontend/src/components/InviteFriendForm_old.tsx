import { useState } from "react";
import { newAuth } from "@/lib/auth_new";

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
    const user = await newAuth.getCurrentUser();
    if (!user) {
      setError("Ошибка авторизации. Пожалуйста, войдите в аккаунт.");
      setLoading(false);
      return;
    }

    console.log('Проверка существующих приглашений для:', { inviter_id: user.id, friend_email: email });

    // Проверяем, не приглашали ли мы уже этого человека
    const { data: existingInvite, error: checkError } = await supabase
      .from("Invites")
      .select("id")
      .eq("inviter_id", user.id)
      .eq("friend_email", email)
      .single();

    console.log('Результат проверки:', { existingInvite, checkError });

    if (existingInvite) {
      // Обновляем существующее приглашение с новым URL
      const { error: updateError } = await supabase
        .from("Invites")
        .update({ friend_url: url })
        .eq("id", existingInvite.id);

      if (updateError) {
        console.error('Ошибка обновления приглашения:', updateError);
        setError("Ошибка при обновлении приглашения.");
        setLoading(false);
        return;
      }

      console.log('Существующее приглашение обновлено');
    } else {
      console.log('Создание нового приглашения:', {
        inviter_id: user.id,
        friend_email: email,
        friend_url: url
      });

      // Вставляем новое приглашение
      const { data: insertData, error: insertError } = await supabase
        .from("Invites")
        .insert({
          inviter_id: user.id,
          friend_email: email,
          friend_url: url,
        })
        .select();

      console.log('Результат вставки:', { insertData, insertError });

      if (insertError) {
        console.error('Ошибка вставки приглашения:', insertError);
        setError("Ошибка при сохранении приглашения.");
        setLoading(false);
        return;
      }

      console.log('Новое приглашение создано');
    }



    // Отправляем красивый email с приглашением через Edge Function
    try {
      const { data: { user: currentUser } } = await supabase.auth.getUser();
      
      console.log('Отправка приглашения:', {
        friendEmail: email,
        friendUrl: url,
        inviterEmail: currentUser?.email || user.email,
        supabaseUrl: supabase.supabaseUrl
      });
      
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

      console.log('Ответ Edge Function:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.warn('Ошибка отправки email приглашения:', response.statusText, errorText);
        // Не критично, продолжаем
      } else {
        const result = await response.json();
        console.log('Email приглашения отправлен успешно:', result);
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