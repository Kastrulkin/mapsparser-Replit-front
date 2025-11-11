import { TrendingUp, Users, Calendar, DollarSign } from "lucide-react";
import { useLanguage } from "@/i18n/LanguageContext";

const Stats = () => {
  const { t } = useLanguage();
  const stats = [
    {
      icon: Users,
      value: "1,250+",
      label: "Успешных салонов",
      description: "Доверяют нашим ИИ-агентам"
    },
    {
      icon: Calendar,
      value: "87,500+",
      label: "Автоматических записей",
      description: "Забронировано в этом месяце"
    },
    {
      icon: DollarSign,
      value: "$12М+",
      label: "Доходов клиентов",
      description: "Сгенерировано нашими ИИ-агентами"
    },
    {
      icon: TrendingUp,
      value: "340%",
      label: "Рост продаж",
      description: "В среднем у наших клиентов"
    }
  ];

  return (
    <section className="py-20 bg-muted/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            {t.stats.title}
            <span className="text-primary"> {t.stats.titleHighlight}</span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            {t.stats.subtitle}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center group">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-full mb-4 group-hover:bg-primary/20 transition-colors">
              <TrendingUp className="w-8 h-8 text-primary" />
            </div>
            <div className="text-2xl font-bold text-foreground mb-2">{t.stats.stat1}</div>
          </div>
          <div className="text-center group">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-full mb-4 group-hover:bg-primary/20 transition-colors">
              <Calendar className="w-8 h-8 text-primary" />
            </div>
            <div className="text-2xl font-bold text-foreground mb-2">{t.stats.stat2}</div>
          </div>
          <div className="text-center group">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-full mb-4 group-hover:bg-primary/20 transition-colors">
              <Users className="w-8 h-8 text-primary" />
            </div>
            <div className="text-2xl font-bold text-foreground mb-2">{t.stats.stat3}</div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Stats;