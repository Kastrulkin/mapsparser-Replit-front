import { Button } from "@/components/ui/button";
import { Play, Users, Calendar, TrendingUp, Heart, Loader2 } from "lucide-react";
import heroImage from "@/assets/hero-image.jpg";
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

const Hero = () => {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  return (
    <section className="relative overflow-hidden bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center px-4 py-2 bg-accent/10 rounded-full text-sm text-accent mb-6">
              <Heart className="w-4 h-4 mr-2" />
              3-5 новых клиентов в месяц автоматически
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
                
                // Защита от двойного клика
                if (isSubmitting) {
                  return;
                }
                
                setIsSubmitting(true);
                
                const form = e.target as HTMLFormElement;
                const email = (form.elements.namedItem('email') as HTMLInputElement).value;
                const yandexUrl = (form.elements.namedItem('yandexUrl') as HTMLInputElement).value;
                const { newAuth } = await import('@/lib/auth_new');
                
                try {
                  // Регистрируем пользователя через новую систему (без пароля)
                  const { user, error } = await newAuth.signUp(
                    email, 
                    '', // Пустой пароль - пользователь установит его при первом входе
                    'Пользователь', // Имя по умолчанию
                    '' // Телефон
                  );
                  
                  if (error) {
                    if (error.includes('уже существует')) {
                      alert('Пользователь с таким email уже зарегистрирован. Войдите в личный кабинет.');
                      navigate('/login', { state: { email } });
                      return;
                    }
                    alert('Ошибка при регистрации: ' + error);
                    return;
                  }
                  
                  // Добавляем URL в очередь
                  if (user) {
                    const { queue_id, error: queueError } = await newAuth.addToQueue(yandexUrl);
                    
                    if (queueError) {
                      console.warn('Ошибка добавления в очередь:', queueError);
                    }
                  }
                  
                  // Сбрасываем форму и показываем успех
                  form.reset();
                  alert('Заявка успешно отправлена! Теперь вы можете войти в личный кабинет.');
                  navigate('/login', { state: { email } });
                  
                } catch (error) {
                  console.error('Общая ошибка:', error);
                  alert('Произошла ошибка. Попробуйте ещё раз.');
                } finally {
                  setIsSubmitting(false);
                }
              }}
              className="space-y-4"
            >
              <div>
                <input
                  name="email"
                  type="email"
                  placeholder="Ваш email"
                  required
                  className="w-full px-6 py-4 text-lg rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200"
                />
              </div>
              
              <div>
                <input
                  name="yandexUrl"
                  type="url"
                  placeholder="Ссылка на ваш бизнес в Яндекс.Картах"
                  required
                  className="w-full px-6 py-4 text-lg rounded-xl border border-border bg-background/50 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200"
                />
              </div>
              
              <Button
                type="submit"
                size="lg"
                disabled={isSubmitting}
                className="w-full bg-primary hover:bg-primary/90 text-white px-8 py-4 text-lg font-semibold rounded-xl transition-all duration-200 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Отправляем заявку...
                  </>
                ) : (
                  <>
                    <TrendingUp className="w-5 h-5 mr-2" />
                    Получить бесплатный отчёт
                  </>
                )}
              </Button>
            </form>
            
            <p className="text-sm text-muted-foreground mt-4">
              Нажимая кнопку, вы соглашаетесь с обработкой персональных данных
            </p>
          </div>
          
          <div className="relative">
            <div className="relative z-10">
              <img
                src={heroImage}
                alt="SEO анализ бизнеса"
                className="w-full h-auto rounded-2xl shadow-2xl"
              />
            </div>
            
            {/* Декоративные элементы */}
            <div className="absolute -top-4 -right-4 w-24 h-24 bg-primary/20 rounded-full blur-xl"></div>
            <div className="absolute -bottom-4 -left-4 w-32 h-32 bg-accent/20 rounded-full blur-xl"></div>
          </div>
        </div>
      </div>
      
      {/* Фоновые элементы */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-primary/5 rounded-full blur-3xl"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent/5 rounded-full blur-3xl"></div>
      </div>
    </section>
  );
};

export default Hero;
