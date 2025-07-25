import { Button } from "@/components/ui/button";
import { Play, Users, Calendar, TrendingUp, Heart } from "lucide-react";
import heroImage from "@/assets/hero-image.jpg";
import { useNavigate } from 'react-router-dom';

const Hero = () => {
  const navigate = useNavigate();
  return (
    <section className="relative overflow-hidden bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center px-4 py-2 bg-accent/10 rounded-full text-sm text-accent mb-6">
              <Heart className="w-4 h-4 mr-2" />
              ИИ-помощник для салонов красоты
            </div>
            
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6 leading-tight">
              Почему ваш конкурент выше вас на Яндекс Картах?
            </h1>
            
            <p className="text-xl text-muted-foreground mb-8 leading-relaxed">
              Подробный персональный отчёт с рекомендациями и сравнением с конкурентом — бесплатно, раз в неделю. Узнайте за один клик.
            </p>

            {/* Форма для email и ссылки на Яндекс.Карты */}
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const form = e.target as HTMLFormElement;
                const email = (form.elements.namedItem('email') as HTMLInputElement).value;
                const yandexUrl = (form.elements.namedItem('yandexUrl') as HTMLInputElement).value;
                const mod = await import('@/lib/supabase');
                let userId: string | null = null;
                // 1. Проверяем, есть ли пользователь
                let { data: existingUser } = await mod.supabase
                  .from('Users')
                  .select('id')
                  .eq('email', email)
                  .single();
                if (existingUser) {
                  userId = existingUser.id;
                } else {
                  // 2. Создаём пользователя с временным паролем
                  const tempPassword = Math.random().toString(36).slice(-12);
                  const { data, error: signUpError } = await mod.supabase.auth.signUp({
                    email,
                    password: tempPassword,
                  });
                  if (signUpError || !data?.user) {
                    alert('Ошибка при создании пользователя');
                    return;
                  }
                  userId = data.user.id;
                  localStorage.setItem('tempPassword', tempPassword);
                  await mod.supabase.from('Users').upsert({
                    id: userId,
                    email: email,
                  });
                }
                // 3. Сохраняем заявку на отчёт в ParseQueue
                const { error: insertError } = await mod.supabase
                  .from('ParseQueue')
                  .insert({ user_id: userId, url: yandexUrl });
                if (insertError) {
                  alert('Ошибка при сохранении заявки');
                  return;
                }
                form.reset();
                navigate('/set-password', { state: { email } });
              }}
              className="mb-8 flex flex-col gap-4"
              id="hero-form"
            >
              <input
                id="email"
                name="email"
                type="email"
                required
                className="border rounded px-3 py-2"
                placeholder="Ваша почта для получения результатов"
              />
              <input
                id="yandexUrl"
                name="yandexUrl"
                type="url"
                required
                className="border rounded px-3 py-2"
                placeholder="Ссылка на карточку организации на Яндекс.Картах"
              />
              {/* Кнопка отправки убрана, отправка будет по клику на 'Отчёт бесплатно' */}
            </form>

            <div className="flex flex-col sm:flex-row gap-4 mb-8">
              <Button
                size="lg"
                className="text-lg px-8 py-6"
                type="submit"
                form="hero-form"
              >
                Отчёт бесплатно
              </Button>
              <Button variant="outline" size="lg" className="text-lg px-8 py-6">
                <Play className="w-5 h-5 mr-2" />
                Смотреть демо
              </Button>
            </div>

            <div className="flex items-center gap-6 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                <span>Анализируется ИИ</span>
              </div>
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4" />
                <span>Проверяется человеком</span>
              </div>
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                <span>Срок за один день</span>
              </div>
            </div>
          </div>

          <div className="relative">
            <img
              src={heroImage}
              alt="Салон красоты с AI-технологиями"
              className="rounded-2xl shadow-2xl w-full h-auto"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-primary/10 to-transparent rounded-2xl"></div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;