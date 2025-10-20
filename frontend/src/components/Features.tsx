import { Bot, Calendar, MessageSquare, TrendingUp, Users, Zap } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const Features = () => {
  const features = [
    {
      icon: Bot,
      title: "Умные ИИ-агенты",
      description: "Автоматические консультации, рекомендации услуг и персонализированное общение с клиентами 24/7",
      color: "text-primary"
    },
    {
      icon: Calendar,
      title: "Автоматическое бронирование",
      description: "Клиенты могут записываться в любое время через чат-бота, который знает расписание всех мастеров",
      color: "text-success"
    },
    {
      icon: MessageSquare,
      title: "Оффлайн продажи",
      description: "Помогаем настроить допродажи существующим клиентам и привлекаем новых",
      color: "text-info"
    },
    {
      icon: TrendingUp,
      title: "Аналитика продаж",
      description: "Отслеживайте эффективность каждого мастера, популярность услуг и прогнозируйте доходы",
      color: "text-warning"
    },
    {
      icon: Users,
      title: "CRM для салонов",
      description: "Ведите базу клиентов, историю посещений и персональные предпочтения каждого клиента",
      color: "text-primary"
    },
    {
      icon: Zap,
      title: "Интеграции",
      description: "Подключайтесь к популярным мессенджерам, социальным сетям и платежным системам",
      color: "text-success"
    }
  ];

  return (
    <section className="py-20 bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Автоматический рост потока клиентов
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Наши ИИ-агенты работают в любом канале связи и интегрируются с вашими существующими системами
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