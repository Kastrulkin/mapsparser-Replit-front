import { Bot, MessageSquare, Calendar, TrendingUp, Target, Sparkles, CalendarCheck, RefreshCcw, ShieldCheck, Users, Image } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const agents = [
  {
    icon: Bot,
    name: "Агент привлечения клиентов",
    desc: (
      <>
        <div className="mb-2 text-lg font-medium text-foreground">ИИ-агент для автоматического роста локальной видимости бизнеса</div>
        <div className="h-2" />
        <div className="space-y-2 text-left text-base mb-2">
          <div className="flex items-start gap-2"><Target className="w-4 h-4 text-primary mt-0.5" /><span className="font-semibold">Главная задача:</span> ежедневно поднимает вашу карточку в Яндекс.Картах, чтобы новые клиенты находили вас первыми.</div>
          <div className="flex items-start gap-2"><Sparkles className="w-4 h-4 text-primary mt-0.5" /><span className="font-semibold">Автоматическая ИИ-оптимизация</span> карточки организации под требования Яндекс Карт — рост показателей уже через 2 недели.</div>
          <div className="flex items-start gap-2"><CalendarCheck className="w-4 h-4 text-primary mt-0.5" /><span className="font-semibold">Ежедневный аудит</span> сайта и рекомендаций в Яндекс.Бизнес для увеличения реальных записей.</div>
          <div className="flex items-start gap-2"><MessageSquare className="w-4 h-4 text-primary mt-0.5" /><span className="font-semibold">Мониторинг отзывов</span> и рейтинга, интеллектуальный запуск кампаний для улучшения репутации (работает автоматически).</div>
          <div className="flex items-start gap-2"><RefreshCcw className="w-4 h-4 text-primary mt-0.5" /><span className="font-semibold">Регулярное обновление</span> фото, описаний и контактных данных: синхронизация изменений без ручной работы на всех площадках.</div>
          <div className="flex items-start gap-2"><ShieldCheck className="w-4 h-4 text-primary mt-0.5" /><span className="font-semibold">Безопасность:</span> Ключевые изменения требуют вашего подтверждения, чтобы снизить риск ошибок и неточностей, присущих автоматизации.</div>
        </div>
        <div className="font-semibold text-green-700">Результат: В среднем +30% к видимости и +3–5 новых клиентов в месяц для каждого подключенного салона.</div>
      </>
    )
  },
  {
    icon: MessageSquare,
    name: "Агент администратор",
    desc: (
      <>
        <div className="mb-2 text-lg font-medium text-foreground">ИИ-агент для автоматизации обработки клиентских запросов и онлайн-бронирований</div>
        <div className="h-2" />
        <div className="space-y-2 text-left text-base mb-2">
          <div className="flex items-start gap-2"><Target className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Главная задача:</span> Автоматически превращает заявки в бронирования и консультирует 24/7 без участия сотрудников.</span></div>
          <div className="flex items-start gap-2"><Sparkles className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Мгновенные ответы на заявки:</span> Обрабатывает запросы клиентов через чаты, мессенджеры и на сайте, соблюдая сценарии компании.</span></div>
          <div className="flex items-start gap-2"><MessageSquare className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Персональное общение:</span> уточняет детали, предлагает время, оформляет и подтверждает запись, отправляет напоминания.</span></div>
          <div className="flex items-start gap-2"><CalendarCheck className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Быстрые ответы:</span> уточняющие вопросы в 90% случаев превращаются в заказы, не упускает их.</span></div>
          <div className="flex items-start gap-2"><Users className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Параллельная работа:</span> Обслуживает десятки клиентов одновременно и обеспечивает полный цикл коммуникации без задержек.</span></div>
          <div className="flex items-start gap-2"><ShieldCheck className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Надёжность и контроль:</span> В сложных или нестандартных случаях переводит разговор на администратора. Все диалоги хранятся для проверки и корректировок.</span></div>
          <div className="flex items-start gap-2"><ShieldCheck className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Безопасность:</span> Обеспечивает конфиденциальность и соответствует требованиям российского законодательства о данных.</span></div>
        </div>
        <div className="font-semibold text-green-700">Результат: В среднем увеличивает число записей на 25–40% за счёт мгновенной обработки всех заявок и напоминаний. Освобождает сотрудников от рутины и экономит на зарплате административного персонала.</div>
      </>
    )
  },
  {
    icon: Calendar,
    name: "Агент лояльности",
    desc: (
      <>
        <div className="mb-2 text-lg font-medium text-foreground">ИИ-агент для автоматического возврата и удержания постоянных клиентов</div>
        <div className="h-2" />
        <div className="space-y-2 text-left text-base mb-2">
          <div className="flex items-start gap-2"><Target className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Главная задача:</span> Автоматически возвращает, удерживает и вовлекает клиентов, превращая разовые визиты в долгосрочное сотрудничество.</span></div>
          <div className="flex items-start gap-2"><Sparkles className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Как это работает:</span> ИИ анализирует историю посещений, покупки и поведение каждого клиента, чтобы вовремя отправлять персональные напоминания, поздравления и индивидуальные предложения.</span></div>
          <div className="flex items-start gap-2"><RefreshCcw className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Автоматические win-back и сезонные кампании:</span> клиенты возвращаются чаще и рекомендуют ваш бизнес друзьям.</span></div>
          <div className="flex items-start gap-2"><MessageSquare className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Персонализированные рассылки:</span> сообщения отправляются тогда, когда это действительно актуально.</span></div>
          <div className="flex items-start gap-2"><TrendingUp className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Прозрачные отчёты:</span> сколько клиентов вернулось, какой доход принесли повторные обращения, анализирует, как можно ещё повысить процент возврата.</span></div>
          <div className="flex items-start gap-2"><ShieldCheck className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Оповещение оператора:</span> в сложных случаях или при нестандартных запросах оповещает вашего оператора.</span></div>
        </div>
        <div className="font-semibold text-green-700 mt-4">
          Результат: Доля постоянных клиентов растёт, а средний чек увеличивается минимум на 67%. Вовлечённые клиенты в 3–4 раза чаще делятся рекомендациями и сами приводят новых гостей. Аналитика и улучшенные сценарии общения на основе ИИ приводят к устойчивому росту повторных продаж и общей выручки.
        </div>
      </>
    )
  },
  {
    icon: Users,
    name: "Агент соцсетей",
    desc: (
      <>
        <div className="mb-2 text-lg font-medium text-foreground">ИИ-агент для автоматизации создания контента и усиления digital-имиджа бизнеса</div>
        <div className="space-y-2 text-left text-base mb-2">
          <div className="flex items-start gap-2"><Target className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Главная задача:</span> Автоматически развивает и наполняет социальные сети компании, превращая профиль в эффективный канал привлечения клиентов и увеличения локального охвата.</span></div>
          <div className="flex items-start gap-2"><Sparkles className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Как это работает:</span> Агент самостоятельно анализирует нишу и поведение аудитории.</span></div>
          <div className="flex items-start gap-2"><CalendarCheck className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Стратегия и планирование:</span> Формирует стратегию контента, автоматически планирует публикации.</span></div>
          <div className="flex items-start gap-2"><Image className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Создание и публикация:</span> Создаёт и публикует разнообразные посты, новости и отзывы.</span></div>
          <div className="flex items-start gap-2"><RefreshCcw className="w-4 h-4 text-primary mt-0.5" /><span><span className="font-semibold">Аналитика и оптимизация:</span> Регулярно отслеживает эффективность публикаций и на основе метрик автоматически корректирует контент-план для роста вовлечённости и охвата аудитории.</span></div>
        </div>
        <div className="font-semibold text-green-700 mt-4">Результат: До 83% клиентов изучают соцсети перед записью — активный профиль компании заметно повышает доверие и конверсию в бронирование более чем в 2 раза</div>
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
            Наши ИИ-агенты для вашего бизнеса
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Каждый агент — это отдельный цифровой помощник, который работает на ваш результат под контролем человека
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