import { Bot, Calendar, MessageSquare, TrendingUp, Users, Zap } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const Features = () => {
  const features = [
    {
      icon: Users,
      title: "Приходят новые клиенты",
      description: "Вы получаете новых клиентов через карты, соцсети и партнёрские программы - стабильный поток как онлайн, так и оффлайн.",
      color: "text-primary"
    },
    {
      icon: MessageSquare,
      title: "Вы не теряете ни одной заявки",
      description: "Все обращения сразу попадают в единую систему - вы не упускаете ни одного клиента.",
      color: "text-success"
    },
    {
      icon: Calendar,
      title: "Пришедший клиент - возвращается",
      description: "Мы напомним о визите и вовремя вернем даже тех, кто давно не был. Ваши клиенты возвращаются и рекомендуют вас.",
      color: "text-info"
    },
    {
      icon: TrendingUp,
      title: "Вы продаёте больше за каждый визит",
      description: "Ваши мастера знают, что дополнительно предложить клиенту. Средний чек растёт за счёт комбо-пакетов и программ лояльности.",
      color: "text-warning"
    },
    {
      icon: TrendingUp,
      title: "Видите, откуда приходят деньги и как развиваться",
      description: "Вся бизнес-аналитика перед глазами: вы точно знаете, откуда приходят клиенты и кто рекомендует вас чаще всего.",
      color: "text-primary"
    },
    {
      icon: Zap,
      title: "Ваши клиенты всегда получают актуальную информацию",
      description: "Будь то карты, Telegram или соцсети - информация о вас везде одинаково свежая и корректная.",
      color: "text-success"
    }
  ];

  return (
    <section className="py-20 bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Без магии - просто делаем свою работу, чтобы вы росли
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Мы приводим вам клиентов онлайн и оффлайн, настраиваем и сопровождаем процессы - вы видите только результат.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <Card key={index} className="border-border hover:shadow-lg transition-shadow duration-300">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg bg-muted ${feature.color}`}>
                    <feature.icon className="w-6 h-6" />
                  </div>
                  <CardTitle className="text-xl">{feature.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-base leading-relaxed">
                  {feature.description}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Features;