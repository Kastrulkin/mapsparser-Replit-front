import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle } from "lucide-react";
import abstractBg from "@/assets/abstract-bg.jpg";
import { useNavigate } from "react-router-dom";

const CTA = () => {
  const navigate = useNavigate();
  const benefits = [
    "Настроим ваши карты — чтобы новые клиенты нашли вас первыми",
    "Поможем заполнить профиль и разместить материалы",
    "Обновим карточку и проследим за отзывами — чтобы клиенты выбрали именно вас",
    "Вы увидите — заявки начнут приходить уже в первые недели"
  ];

  return (
    <section className="relative py-20 overflow-hidden" id="cta">
      <div 
        className="absolute inset-0 bg-cover bg-center opacity-10"
        style={{ backgroundImage: `url(${abstractBg})` }}
      />
      <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-accent/20" />
      
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Готовы к росту?
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Присоединяйтесь к 100+ салонам, которые уже увеличили свой доход вместе с нами
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <h3 className="text-2xl font-bold text-foreground mb-6">
              Начните бесплатно уже сегодня:
            </h3>
            
            <div className="space-y-4 mb-8">
              {benefits.map((benefit, index) => (
                <div key={index} className="flex items-center">
                  <CheckCircle className="w-5 h-5 text-success mr-3" />
                  <span className="text-foreground">{benefit}</span>
                </div>
              ))}
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
              <Button size="lg" className="text-lg px-8 py-6" onClick={() => {
                const form = document.getElementById('hero-form');
                if (form) {
                  form.scrollIntoView({ behavior: 'smooth' });
                  (form.querySelector('input, textarea, select') as HTMLElement)?.focus();
                }
              }}>
                Настроить бесплатно
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>

          <div className="bg-card rounded-2xl p-8 border border-border shadow-xl mb-12">
            <h3 className="text-2xl font-semibold text-foreground mb-6">Что вы получите с нами:</h3>
            <div className="space-y-6">
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">1</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">Рост потока клиентов</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>Больше новых клиентов через карты, соцсети и партнёрские каналы</li>
                    <li>Появится постоянный приток заявок онлайн и оффлайн</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">2</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">Контроль и прозрачность</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>Вся информация и история по клиентам в одной системе</li>
                    <li>Вы сами видите, откуда приходят деньги и что приносит лучший результат</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">3</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">Возврат и удержание клиентов</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>Ваши гости возвращаются чаще — мы сами подскажем, когда и кого надо пригласить</li>
                    <li>Постоянные клиенты рекомендуют вас друзьям</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">4</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">Экономия времени на рутине</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>Меньше отвлекающих действий для собственника и администраторов</li>
                    <li>Чёткий и понятный план действий</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">5</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">Персональная поддержка</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>Помогаем на каждом этапе — ведём до результатов</li>
                    <li>На связи в чате, на почте, по телефону</li>
                  </ul>
                </div>
              </div>
            </div>
            <div className="text-center text-lg font-semibold text-primary mt-8 mb-2">Полноценное развитие салона — плата только из новых доходов!</div>
            <Button 
              variant="default" 
              size="lg" 
              className="text-lg px-8 py-6 mt-4 w-full bg-orange-500 hover:bg-orange-600 text-white border-none"
              onClick={() => navigate('/contact')}
            >
              Связаться с экспертом
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default CTA;