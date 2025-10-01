import { useState } from "react";
import { newAuth } from "@/lib/auth_new";

const InviteFriendForm = ({ onSuccess, onError }: { onSuccess?: () => void; onError?: (error: string) => void }) => {
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

    try {
      // Получаем текущего пользователя
      const user = await newAuth.getCurrentUser();
      if (!user) {
        setError("Ошибка авторизации. Пожалуйста, войдите в аккаунт.");
        return;
      }

      // Создаем приглашение через новую систему
      const { invite, error: inviteError } = await newAuth.createInvite(email);
      
      if (inviteError) {
        setError(inviteError);
        onError?.(inviteError);
        return;
      }

      setSuccess(true);
      onSuccess?.();
      
      // Очищаем форму
      setEmail("");
      setUrl("");
      
    } catch (error) {
      console.error('Ошибка создания приглашения:', error);
      const errorMessage = 'Произошла ошибка при создании приглашения';
      setError(errorMessage);
      onError?.(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-card/80 backdrop-blur-sm rounded-3xl shadow-xl border border-primary/10 p-8">
      <h3 className="text-xl font-semibold text-foreground mb-4">Пригласить друга</h3>
      <p className="text-muted-foreground mb-6">
        Пригласите друга и получите возможность создать отчёт досрочно
      </p>
      
      {error && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg mb-4">
          {error}
        </div>
      )}
      
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-4">
          Приглашение отправлено успешно!
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="friend-email" className="block text-sm font-medium text-foreground mb-2">
            Email друга
          </label>
          <input
            id="friend-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full px-4 py-3 rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200"
            placeholder="friend@example.com"
          />
        </div>
        
        <div>
          <label htmlFor="friend-url" className="block text-sm font-medium text-foreground mb-2">
            Ссылка на бизнес друга (Яндекс.Карты)
          </label>
          <input
            id="friend-url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200"
            placeholder="https://yandex.ru/maps/org/..."
          />
        </div>
        
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-primary text-white rounded-xl px-4 py-3 font-semibold hover:bg-primary/90 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Отправка...' : 'Отправить приглашение'}
        </button>
      </form>
      
      <div className="mt-4 text-xs text-muted-foreground">
        <p>Приглашённый друг получит возможность создать бесплатный SEO отчёт</p>
      </div>
    </div>
  );
};

export default InviteFriendForm;
