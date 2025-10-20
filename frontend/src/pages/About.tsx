import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, Target, Lightbulb, Award, Heart, Globe } from "lucide-react";
import Footer from "@/components/Footer";
import { useNavigate } from "react-router-dom";

const About = () => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-background">
      
      {/* Hero Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-foreground mb-6">
            Кто <span className="text-primary">мы?</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto mb-8">
            Мы заставляем ваш локальный бизнес расти без лишних усилий от вас.
          </p>
        </div>
      </section>

      {/* Problem Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-muted/50">
        <div className="max-w-4xl mx-auto">
          <div className="space-y-6 text-lg text-muted-foreground">
            <p>
              Будем честны, традиционные маркетинговые подходы не работают для небольшого бизнеса. 
              Вам говорят: "ведите соцсети", "освойте SEO", "настройте профиль". И всё это, пока вы 
              работаете по 60 часов в неделю, делая свою основную работу.
            </p>
            <div className="text-center py-6">
              <div className="text-2xl font-bold text-primary">
                У предпринимателей нет времени заниматься привлечением клиентов.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* About Us Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-foreground mb-8">О нашей команде</h2>
          <p className="text-lg text-muted-foreground mb-8">
            Мы — команда специалистов по SEO и автоматизации. Мы знаем, как растить локальный 
            бизнес без больших бюджетов и лишних усилий владельца.
          </p>
        </div>
      </section>

      {/* Target Audience Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-muted/50">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-foreground mb-8">Кому это нужно</h2>
          <p className="text-xl text-muted-foreground mb-8">
            Салонам красоты, мастерам, студиям, и любому локальному бизнесу, которому важно чтобы 
            запись не пустовала, а телефоны не молчали.
          </p>
          
          <div className="grid md:grid-cols-4 gap-6 mb-8">
            <div className="text-center">
              <div className="text-3xl mb-2">💇‍♀️</div>
              <div className="font-medium text-foreground">Салоны красоты</div>
            </div>
            <div className="text-center">
              <div className="text-3xl mb-2">💅</div>
              <div className="font-medium text-foreground">Мастера</div>
            </div>
            <div className="text-center">
              <div className="text-3xl mb-2">🎨</div>
              <div className="font-medium text-foreground">Студии</div>
            </div>
            <div className="text-center">
              <div className="text-3xl mb-2">🏪</div>
              <div className="font-medium text-foreground">Локальный бизнес</div>
            </div>
          </div>
        </div>
      </section>

      {/* Results Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <div className="bg-gradient-to-br from-primary/20 to-secondary/20 rounded-2xl p-12">
            <h2 className="text-3xl font-bold text-foreground mb-6">Результаты</h2>
            <div className="text-5xl font-bold text-primary mb-4">+33%</div>
            <p className="text-xl text-foreground">
              В среднем после оптимизации количество клиентов увеличивается на треть
            </p>
          </div>
        </div>
      </section>

      {/* How We Work Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl font-bold text-foreground mb-12 text-center">Как?</h2>
          
          <div className="mb-12">
            <h3 className="text-2xl font-semibold text-foreground mb-6 text-center">
              Начнём с оптимизации Яндекс.Карт, продолжим полной автоматизацией
            </h3>
          </div>

          <div className="grid lg:grid-cols-2 gap-12">
            {/* Option 1 */}
            <Card className="p-8">
              <CardContent className="p-0">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-8 h-8 bg-primary/20 rounded-full flex items-center justify-center">
                    <span className="text-primary font-bold">1</span>
                  </div>
                  <h3 className="text-xl font-semibold text-foreground">Вы самостоятельно</h3>
                </div>
                <p className="text-muted-foreground mb-4">
                  Вы можете сделать это самостоятельно - сформировать отчёт, получить рекомендации 
                  и внести изменения. Через некоторое время повторить.
                </p>
                <p className="text-muted-foreground mb-4">
                  Инструкция пошаговая, но исполнение всё равно займёт время, которое нужно для основной работы.
                </p>
                <Button
                  size="lg"
                  className="mt-2 text-lg px-8 py-3"
                  onClick={() => {
                    window.location.href = '/#hero-form';
                  }}
                >
                  Настроить бесплатно
                </Button>
              </CardContent>
            </Card>

            {/* Option 2 */}
            <Card className="p-8 border-primary">
              <CardContent className="p-0">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                    <span className="text-primary-foreground font-bold">2</span>
                  </div>
                  <h3 className="text-xl font-semibold text-foreground">Мы сделаем за вас</h3>
                </div>
                <p className="text-muted-foreground mb-4">
                  Подключите наших агентов, живого сотрудника и займитесь своими делами
                </p>
                <div className="space-y-3 text-muted-foreground mb-6">
                  <div className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>Никаких дашбордов и панелей, не надо будет разбираться с настройками</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>Мы проанализируем рынок и ваш бизнес, предложим улучшения, согласуем с вами и внесём изменения</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>Настроим и подключим ИИ агентов к мессенджерам, выведем виджет на сайт</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>Вы всегда будете на связи</span>
                  </div>
                </div>
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 bg-orange-500 hover:bg-orange-600 text-white border-none mt-2"
                  onClick={() => {
                    navigate('/contact');
                  }}
                >
                  Связаться с экспертом
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-foreground mb-8">Условия</h2>

          <Card className="p-8 mb-8">
            <CardContent className="p-0">
              <div className="text-2xl font-bold text-primary mb-4">Оплата по факту результата</div>
              <h3 className="text-xl font-semibold text-foreground mb-4">7% от оплат привлечённых клиентов</h3>
              <div className="space-y-2 text-muted-foreground mb-6">
                <div>- Настройка бизнес процесса</div>
                <div>- Агент привлдечения клиентов</div>
                <div>- Агент администратор</div>
                <div>- Выделенный менеджер</div>
              </div>
              <Button
                variant="default"
                size="lg"
                className="text-lg px-8 py-3 bg-orange-500 hover:bg-orange-600 text-white border-none mt-2"
                onClick={() => {
                  navigate('/contact');
                }}
              >
                Начать сотрудничество
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Final CTA Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-muted/50">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-foreground mb-6">
            Мы не просто помогаем — мы заставляем ваш бизнес расти
          </h2>
          <p className="text-xl text-muted-foreground mb-8">
            Свяжитесь с нами — и пусть клиенты придут сами.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="text-lg px-8 py-3"
              onClick={() => navigate('/contact')}
            >
              Связаться с нами
            </Button>
            <Button variant="outline" size="lg" className="text-lg px-8 py-3">
              Получить консультацию
            </Button>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default About; 