import { Bot, Calendar, MessageSquare, TrendingUp, Users, Zap } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useLanguage } from "@/i18n/LanguageContext";

const Features = () => {
  const { t } = useLanguage();
  const features = [
    {
      icon: Users,
      title: t.features.newClients,
      description: t.features.newClientsDesc,
      color: "text-primary"
    },
    {
      icon: MessageSquare,
      title: t.features.noLostLeads,
      description: t.features.noLostLeadsDesc,
      color: "text-success"
    },
    {
      icon: Calendar,
      title: t.features.returningClients,
      description: t.features.returningClientsDesc,
      color: "text-info"
    },
    {
      icon: TrendingUp,
      title: t.features.biggerCheck,
      description: t.features.biggerCheckDesc,
      color: "text-warning"
    },
    {
      icon: TrendingUp,
      title: t.features.transparency,
      description: t.features.transparencyDesc,
      color: "text-primary"
    },
    {
      icon: Zap,
      title: t.features.upToDate,
      description: t.features.upToDateDesc,
      color: "text-success"
    }
  ];

  return (
    <section className="py-20 bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            {t.features.title}
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            {t.features.subtitle}
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