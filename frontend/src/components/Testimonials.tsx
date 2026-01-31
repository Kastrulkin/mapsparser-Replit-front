import { Bot, MessageSquare, TrendingUp, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useLanguage } from "@/i18n/LanguageContext";

const Testimonials = () => {
  const { t } = useLanguage();

  const agents = [
    {
      icon: Bot,
      name: t.testimonials.onlineTitle,
      gradient: "from-orange-500 to-amber-500",
      desc: (
        <>
          {/* Что получаете */}
          <div className="text-left text-base mb-6">
            <div className="text-sm uppercase font-bold text-orange-600 mb-3 tracking-wide">{t.testimonials.whatYouGet}</div>
            <ul className="space-y-3 text-gray-600">
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🔎</span><span>{t.testimonials.online.whatYouGet1}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🗓️</span><span>{t.testimonials.online.whatYouGet2}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">⭐</span><span>{t.testimonials.online.whatYouGet3}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🖼️</span><span>{t.testimonials.online.whatYouGet4}</span></li>
            </ul>
          </div>

          {/* Как это работает */}
          <div className="text-left text-base mb-6">
            <div className="text-sm uppercase font-bold text-orange-600 mb-3 tracking-wide">{t.testimonials.howItWorks}</div>
            <ul className="space-y-3 text-gray-600">
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🧭</span><span>{t.testimonials.online.howItWorks1}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🌐</span><span>{t.testimonials.online.howItWorks2}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">💬</span><span>{t.testimonials.online.howItWorks3}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📸</span><span>{t.testimonials.online.howItWorks4}</span></li>
            </ul>
          </div>

          {/* Результат */}
          <div className="font-bold text-lg pt-4 border-t-2 border-orange-100">
            <span className="text-emerald-600">{t.testimonials.result}</span>
            <span className="text-gray-700"> {t.testimonials.online.result}</span>
          </div>
        </>
      )
    },
    {
      icon: Users,
      name: t.testimonials.offlineTitle,
      gradient: "from-amber-500 to-orange-600",
      desc: (
        <>
          <div className="text-left text-base mb-6">
            <div className="text-sm uppercase font-bold text-orange-600 mb-3 tracking-wide">{t.testimonials.whatYouGet}</div>
            <ul className="space-y-3 text-gray-600">
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🤝</span><span>{t.testimonials.offline.whatYouGet1}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📊</span><span>{t.testimonials.offline.whatYouGet2}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📈</span><span>{t.testimonials.offline.whatYouGet3}</span></li>
            </ul>
          </div>

          <div className="text-left text-base mb-6">
            <div className="text-sm uppercase font-bold text-orange-600 mb-3 tracking-wide">{t.testimonials.howItWorks}</div>
            <ul className="space-y-3 text-gray-600">
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🔍</span><span>{t.testimonials.offline.howItWorks1}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">💼</span><span>{t.testimonials.offline.howItWorks2}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">👥</span><span>{t.testimonials.offline.howItWorks3}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📉</span><span>{t.testimonials.offline.howItWorks4}</span></li>
            </ul>
          </div>

          <div className="font-bold text-lg pt-4 border-t-2 border-orange-100">
            <span className="text-emerald-600">{t.testimonials.result}</span>
            <span className="text-gray-700"> {t.testimonials.offline.result}</span>
          </div>
        </>
      )
    },
    {
      icon: TrendingUp,
      name: t.testimonials.optimizationTitle,
      gradient: "from-orange-600 to-amber-500",
      desc: (
        <>
          <div className="text-left text-base mb-6">
            <div className="text-sm uppercase font-bold text-orange-600 mb-3 tracking-wide">{t.testimonials.whatYouGet}</div>
            <ul className="space-y-3 text-gray-600">
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📊</span><span>{t.testimonials.optimization.whatYouGet1}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🎯</span><span>{t.testimonials.optimization.whatYouGet2}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🎁</span><span>{t.testimonials.optimization.whatYouGet3}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">⭐</span><span>{t.testimonials.optimization.whatYouGet4}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🤝</span><span>{t.testimonials.optimization.whatYouGet5}</span></li>
            </ul>
          </div>

          <div className="text-left text-base mb-6">
            <div className="text-sm uppercase font-bold text-orange-600 mb-3 tracking-wide">{t.testimonials.howItWorks}</div>
            <ul className="space-y-3 text-gray-600">
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📈</span><span>{t.testimonials.optimization.howItWorks1}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🔧</span><span>{t.testimonials.optimization.howItWorks2}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🧪</span><span>{t.testimonials.optimization.howItWorks3}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">👨‍🏫</span><span>{t.testimonials.optimization.howItWorks4}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📋</span><span>{t.testimonials.optimization.howItWorks5}</span></li>
            </ul>
          </div>

          <div className="font-bold text-lg pt-4 border-t-2 border-orange-100">
            <span className="text-emerald-600">{t.testimonials.result}</span>
            <span className="text-gray-700"> {t.testimonials.optimization.result}</span>
          </div>
        </>
      )
    },
    {
      icon: MessageSquare,
      name: t.testimonials.interactionTitle,
      gradient: "from-amber-600 to-orange-500",
      desc: (
        <>
          <div className="text-left text-base mb-6">
            <div className="text-sm uppercase font-bold text-orange-600 mb-3 tracking-wide">{t.testimonials.whatYouGet}</div>
            <ul className="space-y-3 text-gray-600">
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">✅</span><span>{t.testimonials.interaction.whatYouGet1}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">💬</span><span>{t.testimonials.interaction.whatYouGet2}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🔄</span><span>{t.testimonials.interaction.whatYouGet3}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📋</span><span>{t.testimonials.interaction.whatYouGet4}</span></li>
            </ul>
          </div>

          <div className="text-left text-base mb-6">
            <div className="text-sm uppercase font-bold text-orange-600 mb-3 tracking-wide">{t.testimonials.howItWorks}</div>
            <ul className="space-y-3 text-gray-600">
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🤖</span><span>{t.testimonials.interaction.howItWorks1}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📝</span><span>{t.testimonials.interaction.howItWorks2}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">⏰</span><span>{t.testimonials.interaction.howItWorks3}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">📊</span><span>{t.testimonials.interaction.howItWorks4}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🎁</span><span>{t.testimonials.interaction.howItWorks5}</span></li>
              <li className="flex gap-3 items-start"><span className="text-2xl flex-shrink-0">🔗</span><span>{t.testimonials.interaction.howItWorks6}</span></li>
            </ul>
          </div>

          <div className="font-bold text-lg pt-4 border-t-2 border-orange-100">
            <span className="text-emerald-600">{t.testimonials.result}</span>
            <span className="text-gray-700"> {t.testimonials.interaction.result}</span>
          </div>
        </>
      )
    }
  ];

  return (
    <section className="py-24 bg-gradient-to-b from-orange-50/30 to-white" id="agents">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16 animate-in fade-in slide-in-from-bottom-4 duration-700">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            {t.testimonials.title}
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            {t.testimonials.subtitle}
          </p>
        </div>
        <div className="flex flex-col gap-8">
          {agents.map((agent, idx) => (
            <Card
              key={idx}
              className="group bg-white border-2 border-gray-200 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10 transition-all duration-300 animate-in fade-in slide-in-from-bottom-5 duration-700"
              style={{ animationDelay: `${idx * 100}ms` }}
            >
              <CardContent className="p-8 flex flex-col gap-4">
                <div className="flex items-center gap-6 mb-4">
                  <div className={`p-4 rounded-2xl bg-gradient-to-br ${agent.gradient} group-hover:scale-110 transition-transform duration-300 shadow-lg`}>
                    <agent.icon className="w-12 h-12 text-white" />
                  </div>
                  <h3 className="font-bold text-3xl text-gray-900 group-hover:text-orange-600 transition-colors">{agent.name}</h3>
                </div>
                <div className="pl-0 md:pl-24 text-left w-full">
                  {agent.desc}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Testimonials;