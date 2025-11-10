import { Bot, MessageSquare, Calendar, TrendingUp, Target, Sparkles, CalendarCheck, RefreshCcw, ShieldCheck, Users, Image } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const agents = [
  {
    icon: Bot,
    name: "Привлекаем клиентов онлайн",
    desc: (
      <>
        {/* Что получаете */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">ЧТО ПОЛУЧАЕТЕ:</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🔎</span><span>Ваш салон находится в топе карт и поиска — новые клиенты находят вас первыми.</span></li>
            <li className="flex gap-2"><span>🗓️</span><span>Сайт с удобной онлайн-записью — клиенты выбирают время без звонков.</span></li>
            <li className="flex gap-2"><span>⭐</span><span>Каждый отзыв виден сотням потенциальных клиентов — мы следим, чтобы вы <span className="text-emerald-600 font-medium">выделялись</span>.</span></li>
            <li className="flex gap-2"><span>🖼️</span><span>Свежие фото и новости показывают, что салон жив и работает.</span></li>
          </ul>
        </div>

        {/* Как это работает */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">КАК ЭТО РАБОТАЕТ:</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🧭</span><span>Оптимизируем вашу карточку на Яндексе с учетом актуальных требований.</span></li>
            <li className="flex gap-2"><span>🌐</span><span>Создаём и поддерживаем сайт с онлайн-записью.</span></li>
            <li className="flex gap-2"><span>💬</span><span>Следим за отзывами и помогаем отвечать на них.</span></li>
            <li className="flex gap-2"><span>📸</span><span>Регулярно обновляем фото и новостные публикации.</span></li>
          </ul>
        </div>

        {/* Результат */}
        <div className="font-semibold">
          <span className="text-emerald-700">РЕЗУЛЬТАТ:</span>
          <span className="text-muted-foreground"> </span>
          <span className="text-emerald-700">+30% видимости</span>
          <span className="text-muted-foreground"> в поиске. В среднем </span>
          <span className="text-emerald-700">3–5 новых клиентов/мес</span>
          <span className="text-muted-foreground">.</span>
        </div>
      </>
    )
  },
  {
    icon: Users,
    name: "Привлекаем клиентов оффлайн",
    desc: (
      <>
        {/* Что получаешь */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">ЧТО ПОЛУЧАЕТЕ:</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🤝</span><span>Новые клиенты приходят через <span className="text-primary font-medium">проверенные каналы</span> (партнерства, рекомендации, промоутеры)</span></li>
            <li className="flex gap-2"><span>📊</span><span>Система отслеживает, откуда пришел каждый клиент — знаете, какие каналы <span className="text-emerald-600 font-medium">реально работают</span>, какие нет</span></li>
            <li className="flex gap-2"><span>📈</span><span>Стабильный поток новых клиентов каждый месяц, не зависит только от <span className="text-accent-foreground font-medium">онлайна</span></span></li>
          </ul>
        </div>

        {/* Как это работает */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">КАК ЭТО РАБОТАЕТ:</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🔍</span><span>Поиск партнеров в соседних бизнесах, которые работают с теми же клиентами</span></li>
            <li className="flex gap-2"><span>💼</span><span>Разработка схем сотрудничества (кросспромоушены, скидки партнерам на услуги друг друга, системы комиссий)</span></li>
            <li className="flex gap-2"><span>👥</span><span>Собственные промоутеры для раздачи листовок, работы на улице</span></li>
            <li className="flex gap-2"><span>📉</span><span>Отслеживание результатов каждого канала (сколько клиентов принес партнер А, партнер B, промоутер С)</span></li>
          </ul>
        </div>

        {/* Результат */}
        <div className="font-semibold">
          <span className="text-emerald-700">РЕЗУЛЬТАТ:</span>
          <span className="text-muted-foreground"> </span>
          <span className="text-muted-foreground">Стабильные повторные клиенты, которые приходят благодаря рекомендациям (</span>
          <span className="text-emerald-700">рекомендации работают лучше рекламы</span>
          <span className="text-muted-foreground">).</span>
        </div>
      </>
    )
  },
  {
    icon: TrendingUp,
    name: "Оптимизируем бизнес и увеличиваем средний чек",
    desc: (
      <>
        {/* Что получаешь */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">ЧТО ПОЛУЧАЕТЕ:</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>📊</span><span>Вся база клиентов в <span className="text-primary font-medium">одной системе</span> — знаете, кто постоянный, кто давно не приходил</span></li>
            <li className="flex gap-2"><span>🎯</span><span>Ясная стратегия допродаж и кросс-селлов — средний чек растет <span className="text-emerald-600 font-medium">естественно</span>, без напора</span></li>
            <li className="flex gap-2"><span>🎁</span><span>Комбо-пакеты услуг, которые <span className="text-primary font-medium">выгодны всем</span></span></li>
            <li className="flex gap-2"><span>⭐</span><span>Система лояльности, которая работает: бонусы, скидки на повторные визиты, рефереральная программа</span></li>
            <li className="flex gap-2"><span>🤝</span><span>Ясные процессы в салоне — мастера и администраторы работают как <span className="text-accent-foreground font-medium">одна команда</span></span></li>
          </ul>
        </div>

        {/* Как это работает */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">КАК ЭТО РАБОТАЕТ:</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>📈</span><span>Анализ текущего среднего чека и услуг, которые клиенты не берут</span></li>
            <li className="flex gap-2"><span>🔧</span><span>Настройка CRM с сегментацией клиентов по типам</span></li>
            <li className="flex gap-2"><span>🧪</span><span>Тестирование комбинаций услуг и скидок</span></li>
            <li className="flex gap-2"><span>👨‍🏫</span><span>Обучение мастеров, как предложить доп.услугу в нужный момент</span></li>
            <li className="flex gap-2"><span>📋</span><span>Система лояльности и отчеты по результатам</span></li>
          </ul>
        </div>

        {/* Результат */}
        <div className="font-semibold">
          <span className="text-emerald-700">РЕЗУЛЬТАТ:</span>
          <span className="text-muted-foreground"> </span>
          <span className="text-emerald-700">+20–35% средний чек</span>
          <span className="text-muted-foreground">, </span>
          <span className="text-emerald-700">+67% постоянных клиентов</span>
          <span className="text-muted-foreground">, </span>
          <span className="text-emerald-700">3–4x рекомендации</span>
          <span className="text-muted-foreground">. Салон растет без найма дополнительного персонала.</span>
        </div>
      </>
    )
  },
  {
    icon: MessageSquare,
    name: "Взаимодействуем с клиентом: от первого контакта до рекомендаций",
    desc: (
      <>
        {/* Что получаешь */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">ЧТО ПОЛУЧАЕТЕ:</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>✅</span><span>Ни одна заявка не теряется — клиент может позвонить, написать или заполнить форму в любой момент, всегда получит <span className="text-emerald-600 font-medium">ответ</span></span></li>
            <li className="flex gap-2"><span>💬</span><span>Каждый клиент получает <span className="text-primary font-medium">персональное внимание</span> — спрашиваем детали, предлагаем время, напоминаем перед визитом</span></li>
            <li className="flex gap-2"><span>🔄</span><span>Давно не приходившие клиенты получают персональное предложение в нужный момент — возвращаются и <span className="text-emerald-600 font-medium">приводят друзей</span></span></li>
            <li className="flex gap-2"><span>📋</span><span>Вся история контактов видна в системе — никогда не забудете, что клиент брал раньше, когда приходил</span></li>
          </ul>
        </div>

        {/* Как это работает */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">КАК ЭТО РАБОТАЕТ:</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🤖</span><span>Автоматический первый ответ на заявки из всех каналов (форма, чаты, Telegram, WhatsApp)</span></li>
            <li className="flex gap-2"><span>📝</span><span>Сценарии общения, которые спрашивают нужные детали и предлагают время</span></li>
            <li className="flex gap-2"><span>⏰</span><span>Автоматические напоминания за день до записи — меньше пропусков</span></li>
            <li className="flex gap-2"><span>📊</span><span>Анализ истории каждого клиента (когда был, что брал, сколько потратил)</span></li>
            <li className="flex gap-2"><span>🎁</span><span>Автоматические рассылки давно не приходившим клиентам и в дни рождения</span></li>
            <li className="flex gap-2"><span>🔗</span><span>Все коммуникации видны в <span className="text-primary font-medium">одной системе</span></span></li>
          </ul>
        </div>

        {/* Результат */}
        <div className="font-semibold">
          <span className="text-emerald-700">РЕЗУЛЬТАТ:</span>
          <span className="text-muted-foreground"> </span>
          <span className="text-emerald-700">+25–40% записей</span>
          <span className="text-muted-foreground">, </span>
          <span className="text-emerald-700">+67% постоянных клиентов</span>
          <span className="text-muted-foreground">, </span>
          <span className="text-emerald-700">3–4x рекомендации</span>
          <span className="text-muted-foreground">. Администраторам нужно в 2–3 раза меньше времени на рутину.</span>
        </div>
      </>
    )
  }
];

const Testimonials = () => {
  return (
    <section className="py-20 bg-muted/30" id="agents">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Работаем на результат вашего бизнеса - занимайтесь любимым делом, а не рутиной
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            От привлечения клиентов до удержания — полный контроль и реальный рост без ваших лишних усилий
          </p>
        </div>
        <div className="flex flex-col gap-8">
          {agents.map((agent, idx) => (
            <Card key={idx} className="border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6 flex flex-col gap-2">
                <div className="flex items-center gap-4 mb-2">
                  <agent.icon className="w-16 h-16 text-primary" />
                  <h3 className="font-bold text-2xl text-foreground">{agent.name}</h3>
                </div>
                <div className="pl-20 text-left w-full text-muted-foreground text-base">{agent.desc}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Testimonials;