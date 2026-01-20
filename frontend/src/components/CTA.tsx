import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useLanguage } from "@/i18n/LanguageContext";

const CTA = () => {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const benefits = [
    t.cta.setupMaps,
    t.cta.helpProfile,
    t.cta.updateCard,
    t.cta.seeResults
  ];

  return (
    <section className="relative py-24 overflow-hidden bg-gradient-to-br from-orange-50 via-white to-amber-50" id="cta">
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            {t.cta.title}
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            {t.cta.subtitle}
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div className="animate-in fade-in slide-in-from-left-5 duration-700">
            <h3 className="text-3xl font-bold text-gray-900 mb-8">
              {t.cta.startFree}
            </h3>

            <div className="space-y-5 mb-10">
              {benefits.map((benefit, index) => (
                <div
                  key={index}
                  className="flex items-center gap-4 p-4 rounded-xl bg-white/80 border border-orange-200/50 hover:border-orange-300 hover:shadow-lg transition-all duration-300"
                >
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center shadow-lg shadow-orange-500/30">
                    <CheckCircle className="w-6 h-6 text-white" />
                  </div>
                  <span className="text-lg text-gray-700 font-medium">{benefit}</span>
                </div>
              ))}
            </div>

            <Button
              size="lg"
              className="text-lg px-10 py-7 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white border-none shadow-2xl shadow-orange-500/40 hover:shadow-orange-600/50 transition-all duration-300 transform hover:scale-105"
              onClick={() => {
                const form = document.getElementById('hero-form');
                if (form) {
                  form.scrollIntoView({ behavior: 'smooth' });
                  (form.querySelector('input, textarea, select') as HTMLElement)?.focus();
                }
              }}
            >
              {t.hero.submitButton}
              <ArrowRight className="w-6 h-6 ml-3" />
            </Button>
          </div>

          <div className="bg-white rounded-3xl p-10 border-2 border-orange-200 shadow-2xl shadow-orange-500/10 animate-in fade-in slide-in-from-right-5 duration-700">
            <h3 className="text-3xl font-bold text-gray-900 mb-8 pb-4 border-b-2 border-orange-100">
              {t.cta.whatYouGet}
            </h3>
            <div className="space-y-8">
              <div className="flex items-start gap-5">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-orange-500 to-amber-600 rounded-2xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                  1
                </div>
                <div>
                  <h5 className="font-bold text-gray-900 mb-3 text-xl">{t.cta.clientGrowth}</h5>
                  <ul className="space-y-2 text-base text-gray-600 leading-relaxed">
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.clientGrowthDesc1}
                    </li>
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.clientGrowthDesc2}
                    </li>
                  </ul>
                </div>
              </div>

              <div className="flex items-start gap-5">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-amber-500 to-orange-500 rounded-2xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                  2
                </div>
                <div>
                  <h5 className="font-bold text-gray-900 mb-3 text-xl">{t.cta.control}</h5>
                  <ul className="space-y-2 text-base text-gray-600 leading-relaxed">
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.controlDesc1}
                    </li>
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.controlDesc2}
                    </li>
                  </ul>
                </div>
              </div>

              <div className="flex items-start gap-5">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-orange-600 to-amber-600 rounded-2xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                  3
                </div>
                <div>
                  <h5 className="font-bold text-gray-900 mb-3 text-xl">{t.cta.retention}</h5>
                  <ul className="space-y-2 text-base text-gray-600 leading-relaxed">
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.retentionDesc1}
                    </li>
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.retentionDesc2}
                    </li>
                  </ul>
                </div>
              </div>

              <div className="flex items-start gap-5">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-amber-600 to-orange-500 rounded-2xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                  4
                </div>
                <div>
                  <h5 className="font-bold text-gray-900 mb-3 text-xl">{t.cta.timeSaving}</h5>
                  <ul className="space-y-2 text-base text-gray-600 leading-relaxed">
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.timeSavingDesc1}
                    </li>
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.timeSavingDesc2}
                    </li>
                  </ul>
                </div>
              </div>

              <div className="flex items-start gap-5">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-orange-500 to-amber-600 rounded-2xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                  5
                </div>
                <div>
                  <h5 className="font-bold text-gray-900 mb-3 text-xl">{t.cta.support}</h5>
                  <ul className="space-y-2 text-base text-gray-600 leading-relaxed">
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.supportDesc1}
                    </li>
                    <li className="flex items-start">
                      <span className="text-orange-500 mr-2">•</span>
                      {t.cta.supportDesc2}
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="mt-10 pt-8 border-t-2 border-orange-100">
              <p className="text-center text-xl font-bold bg-gradient-to-r from-orange-600 to-amber-600 bg-clip-text text-transparent mb-6">
                {t.cta.finalText}
              </p>
              <Button
                variant="default"
                size="lg"
                className="text-lg px-10 py-7 w-full bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white border-none shadow-xl shadow-orange-500/30 hover:shadow-orange-600/40 transition-all duration-300"
                onClick={() => navigate('/contact')}
              >
                {t.cta.contactExpert}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default CTA;