import { TrendingUp, Users, Calendar } from "lucide-react";
import { useLanguage } from "@/i18n/LanguageContext";

const Stats = () => {
  const { t } = useLanguage();

  return (
    <section className="py-20 bg-white relative overflow-hidden">
      {/* Decorative gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-orange-50 via-white to-amber-50 opacity-60" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16 animate-in fade-in slide-in-from-bottom-4 duration-700">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            {t.stats.title}{' '}
            <span className="bg-gradient-to-r from-amber-500 to-orange-600 bg-clip-text text-transparent">
              {t.stats.titleHighlight}
            </span>
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto mt-6 leading-relaxed">
            {t.stats.subtitle}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mt-16">
          <div className="text-center group animate-in fade-in slide-in-from-bottom-5 duration-700 delay-100">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-orange-500 to-amber-600 rounded-2xl mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg shadow-orange-500/30">
              <TrendingUp className="w-10 h-10 text-white" />
            </div>
            <div className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent mb-3">
              {t.stats.stat1}
            </div>
            <div className="h-1 w-16 bg-gradient-to-r from-orange-500 to-amber-500 mx-auto rounded-full mb-2" />
          </div>

          <div className="text-center group animate-in fade-in slide-in-from-bottom-5 duration-700 delay-200">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-amber-500 to-orange-500 rounded-2xl mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg shadow-amber-500/30">
              <Calendar className="w-10 h-10 text-white" />
            </div>
            <div className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent mb-3">
              {t.stats.stat2}
            </div>
            <div className="h-1 w-16 bg-gradient-to-r from-amber-500 to-orange-600 mx-auto rounded-full mb-2" />
          </div>

          <div className="text-center group animate-in fade-in slide-in-from-bottom-5 duration-700 delay-300">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-orange-600 to-amber-500 rounded-2xl mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg shadow-orange-600/30">
              <Users className="w-10 h-10 text-white" />
            </div>
            <div className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent mb-3">
              {t.stats.stat3}
            </div>
            <div className="h-1 w-16 bg-gradient-to-r from-orange-600 to-amber-500 mx-auto rounded-full mb-2" />
          </div>
        </div>
      </div>
    </section>
  );
};

export default Stats;