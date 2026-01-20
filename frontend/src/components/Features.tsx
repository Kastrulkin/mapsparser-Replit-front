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
      gradient: "from-orange-500 to-amber-500"
    },
    {
      icon: MessageSquare,
      title: t.features.noLostLeads,
      description: t.features.noLostLeadsDesc,
      gradient: "from-amber-500 to-orange-600"
    },
    {
      icon: Calendar,
      title: t.features.returningClients,
      description: t.features.returningClientsDesc,
      gradient: "from-orange-400 to-amber-400"
    },
    {
      icon: TrendingUp,
      title: t.features.biggerCheck,
      description: t.features.biggerCheckDesc,
      gradient: "from-amber-600 to-orange-500"
    },
    {
      icon: TrendingUp,
      title: t.features.transparency,
      description: t.features.transparencyDesc,
      gradient: "from-orange-500 to-amber-600"
    },
    {
      icon: Zap,
      title: t.features.upToDate,
      description: t.features.upToDateDesc,
      gradient: "from-amber-500 to-orange-500"
    }
  ];

  return (
    <section className="py-24 bg-gradient-to-b from-white to-orange-50/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16 animate-in fade-in slide-in-from-bottom-4 duration-700">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            {t.features.title}
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            {t.features.subtitle}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <Card
              key={index}
              className="group relative bg-white border border-gray-200 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10 transition-all duration-300 transform hover:-translate-y-1 animate-in fade-in slide-in-from-bottom-5 duration-700"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <CardHeader className="pb-4">
                <div className="flex items-center gap-4 mb-4">
                  <div className={`p-3 rounded-xl bg-gradient-to-br ${feature.gradient} group-hover:scale-110 transition-transform duration-300`}>
                    <feature.icon className="w-7 h-7 text-white" />
                  </div>
                </div>
                <CardTitle className="text-2xl font-bold text-gray-900 group-hover:text-orange-600 transition-colors">
                  {feature.title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-base text-gray-600 leading-relaxed">
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