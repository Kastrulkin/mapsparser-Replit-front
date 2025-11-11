import { Bot, MessageSquare, Calendar, TrendingUp, Target, Sparkles, CalendarCheck, RefreshCcw, ShieldCheck, Users, Image } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useLanguage } from "@/i18n/LanguageContext";

const Testimonials = () => {
  const { t } = useLanguage();

const agents = [
  {
    icon: Bot,
    name: t.testimonials.onlineTitle,
    desc: (
      <>
        {/* Что получаете */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">{t.testimonials.whatYouGet}</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🔎</span><span>{t.testimonials.online.whatYouGet1}</span></li>
            <li className="flex gap-2"><span>🗓️</span><span>{t.testimonials.online.whatYouGet2}</span></li>
            <li className="flex gap-2"><span>⭐</span><span>{t.testimonials.online.whatYouGet3}</span></li>
            <li className="flex gap-2"><span>🖼️</span><span>{t.testimonials.online.whatYouGet4}</span></li>
          </ul>
        </div>

        {/* Как это работает */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">{t.testimonials.howItWorks}</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🧭</span><span>{t.testimonials.online.howItWorks1}</span></li>
            <li className="flex gap-2"><span>🌐</span><span>{t.testimonials.online.howItWorks2}</span></li>
            <li className="flex gap-2"><span>💬</span><span>{t.testimonials.online.howItWorks3}</span></li>
            <li className="flex gap-2"><span>📸</span><span>{t.testimonials.online.howItWorks4}</span></li>
          </ul>
        </div>

        {/* Результат */}
        <div className="font-semibold">
          <span className="text-emerald-700">{t.testimonials.result}</span>
          <span className="text-muted-foreground"> </span>
          <span className="text-muted-foreground">{t.testimonials.online.result}</span>
        </div>
      </>
    )
  },
  {
    icon: Users,
    name: t.testimonials.offlineTitle,
    desc: (
      <>
        {/* Что получаешь */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">{t.testimonials.whatYouGet}</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🤝</span><span>{t.testimonials.offline.whatYouGet1}</span></li>
            <li className="flex gap-2"><span>📊</span><span>{t.testimonials.offline.whatYouGet2}</span></li>
            <li className="flex gap-2"><span>📈</span><span>{t.testimonials.offline.whatYouGet3}</span></li>
          </ul>
        </div>

        {/* Как это работает */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">{t.testimonials.howItWorks}</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🔍</span><span>{t.testimonials.offline.howItWorks1}</span></li>
            <li className="flex gap-2"><span>💼</span><span>{t.testimonials.offline.howItWorks2}</span></li>
            <li className="flex gap-2"><span>👥</span><span>{t.testimonials.offline.howItWorks3}</span></li>
            <li className="flex gap-2"><span>📉</span><span>{t.testimonials.offline.howItWorks4}</span></li>
          </ul>
        </div>

        {/* Результат */}
        <div className="font-semibold">
          <span className="text-emerald-700">{t.testimonials.result}</span>
          <span className="text-muted-foreground"> </span>
          <span className="text-muted-foreground">{t.testimonials.offline.result}</span>
        </div>
      </>
    )
  },
  {
    icon: TrendingUp,
    name: t.testimonials.optimizationTitle,
    desc: (
      <>
        {/* Что получаешь */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">{t.testimonials.whatYouGet}</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>📊</span><span>{t.testimonials.optimization.whatYouGet1}</span></li>
            <li className="flex gap-2"><span>🎯</span><span>{t.testimonials.optimization.whatYouGet2}</span></li>
            <li className="flex gap-2"><span>🎁</span><span>{t.testimonials.optimization.whatYouGet3}</span></li>
            <li className="flex gap-2"><span>⭐</span><span>{t.testimonials.optimization.whatYouGet4}</span></li>
            <li className="flex gap-2"><span>🤝</span><span>{t.testimonials.optimization.whatYouGet5}</span></li>
          </ul>
        </div>

        {/* Как это работает */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">{t.testimonials.howItWorks}</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>📈</span><span>{t.testimonials.optimization.howItWorks1}</span></li>
            <li className="flex gap-2"><span>🔧</span><span>{t.testimonials.optimization.howItWorks2}</span></li>
            <li className="flex gap-2"><span>🧪</span><span>{t.testimonials.optimization.howItWorks3}</span></li>
            <li className="flex gap-2"><span>👨‍🏫</span><span>{t.testimonials.optimization.howItWorks4}</span></li>
            <li className="flex gap-2"><span>📋</span><span>{t.testimonials.optimization.howItWorks5}</span></li>
          </ul>
        </div>

        {/* Результат */}
        <div className="font-semibold">
          <span className="text-emerald-700">{t.testimonials.result}</span>
          <span className="text-muted-foreground"> </span>
          <span className="text-muted-foreground">{t.testimonials.optimization.result}</span>
        </div>
      </>
    )
  },
  {
    icon: MessageSquare,
    name: t.testimonials.interactionTitle,
    desc: (
      <>
        {/* Что получаешь */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">{t.testimonials.whatYouGet}</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>✅</span><span>{t.testimonials.interaction.whatYouGet1}</span></li>
            <li className="flex gap-2"><span>💬</span><span>{t.testimonials.interaction.whatYouGet2}</span></li>
            <li className="flex gap-2"><span>🔄</span><span>{t.testimonials.interaction.whatYouGet3}</span></li>
            <li className="flex gap-2"><span>📋</span><span>{t.testimonials.interaction.whatYouGet4}</span></li>
          </ul>
        </div>

        {/* Как это работает */}
        <div className="text-left text-base mb-4">
          <div className="text-sm uppercase font-semibold text-primary mb-2">{t.testimonials.howItWorks}</div>
          <ul className="space-y-2 text-muted-foreground">
            <li className="flex gap-2"><span>🤖</span><span>{t.testimonials.interaction.howItWorks1}</span></li>
            <li className="flex gap-2"><span>📝</span><span>{t.testimonials.interaction.howItWorks2}</span></li>
            <li className="flex gap-2"><span>⏰</span><span>{t.testimonials.interaction.howItWorks3}</span></li>
            <li className="flex gap-2"><span>📊</span><span>{t.testimonials.interaction.howItWorks4}</span></li>
            <li className="flex gap-2"><span>🎁</span><span>{t.testimonials.interaction.howItWorks5}</span></li>
            <li className="flex gap-2"><span>🔗</span><span>{t.testimonials.interaction.howItWorks6}</span></li>
          </ul>
        </div>

        {/* Результат */}
        <div className="font-semibold">
          <span className="text-emerald-700">{t.testimonials.result}</span>
          <span className="text-muted-foreground"> </span>
          <span className="text-muted-foreground">{t.testimonials.interaction.result}</span>
        </div>
      </>
    )
  }
];

  return (
    <section className="py-20 bg-muted/30" id="agents">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            {t.testimonials.title}
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            {t.testimonials.subtitle}
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