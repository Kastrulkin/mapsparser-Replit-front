import { Button } from "@/components/ui/button";
import { Play, Users, Calendar, TrendingUp, Heart, Loader2, CheckCircle2 } from "lucide-react";
import heroImage from "@/assets/hero-image.jpg";
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';

const Hero = () => {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { t } = useLanguage();

  return (
    <section className="relative overflow-hidden bg-background">
      {/* Background Gradients */}
      <div className="absolute inset-0 -z-10 pointer-events-none">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-500/10 rounded-full blur-[100px] opacity-70 mixture-blend-multiply"></div>
        <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-orange-500/10 rounded-full blur-[100px] opacity-70 mixture-blend-multiply"></div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-32">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <div className="relative z-10">
            <div className="inline-flex items-center px-4 py-2 bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-100 rounded-full text-sm font-medium text-orange-700 mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <Heart className="w-4 h-4 mr-2 text-orange-500 fill-orange-500" />
              {t.hero.newClients}
            </div>

            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 mb-8 leading-tight tracking-tight animate-in fade-in slide-in-from-bottom-5 duration-1000 delay-100">
              {t.hero.title}
            </h1>

            <p className="text-lg text-gray-600 mb-10 leading-relaxed max-w-lg animate-in fade-in slide-in-from-bottom-6 duration-1000 delay-200">
              {t.hero.subtitle}
            </p>

          </div>

          <div className="relative animate-in fade-in slide-in-from-left-8 duration-1000 delay-200">
            <img
              src={heroImage}
              alt="BeautyBot Hero"
              className="w-full h-auto rounded-2xl shadow-2xl"
            />
          </div>

          <div className="relative animate-in fade-in slide-in-from-right-8 duration-1000 delay-300">
            {/* Glassmorphic Form Card */}
            <div className={cn(
              "relative z-20 rounded-3xl p-8 md:p-10 shadow-2xl",
              "bg-white/70 backdrop-blur-xl border border-white/50",
              "ring-1 ring-gray-900/5"
            )}>
              <div className="mb-8">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">{t.hero.formTitle}</h3>
                <p className="text-gray-500">{t.hero.formSubtitle}</p>
              </div>

              <form
                id="hero-form"
                onSubmit={async (e) => {
                  e.preventDefault();

                  if (isSubmitting) return;
                  setIsSubmitting(true);

                  const form = e.target as HTMLFormElement;
                  const email = (form.elements.namedItem('email') as HTMLInputElement).value;
                  const yandexUrl = (form.elements.namedItem('yandexUrl') as HTMLInputElement).value;

                  try {
                    const resp = await fetch('/api/public/request-report', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ email, url: yandexUrl })
                    });
                    const result = await resp.json().catch(() => null);
                    if (!resp.ok) {
                      const msg = (result && (result.error || result.message)) || t.hero.errorMessage;
                      throw new Error(msg);
                    }

                    form.reset();
                    alert(t.hero.successMessage);

                  } catch (error) {
                    console.error('Общая ошибка:', error);
                    alert(error instanceof Error ? error.message : t.hero.errorMessage);
                  } finally {
                    setIsSubmitting(false);
                  }
                }}
                className="space-y-5"
              >
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-gray-700 ml-1">{t.hero.emailLabel}</label>
                  <input
                    name="email"
                    type="email"
                    placeholder={t.hero.emailPlaceholder}
                    required
                    className="w-full px-5 py-4 text-lg rounded-xl border border-gray-200 bg-white/50 focus:bg-white focus:outline-none focus:ring-4 focus:ring-orange-500/10 focus:border-orange-500 transition-all duration-200 placeholder:text-gray-400"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-semibold text-gray-700 ml-1">{t.hero.mapsLinkLabel}</label>
                  <input
                    name="yandexUrl"
                    type="url"
                    placeholder={t.hero.yandexUrlPlaceholder}
                    required
                    className="w-full px-5 py-4 text-lg rounded-xl border border-gray-200 bg-white/50 focus:bg-white focus:outline-none focus:ring-4 focus:ring-orange-500/10 focus:border-orange-500 transition-all duration-200 placeholder:text-gray-400"
                  />
                </div>

                <Button
                  type="submit"
                  size="lg"
                  disabled={isSubmitting}
                  className="w-full btn-iridescent text-white px-8 py-6 text-lg font-bold rounded-xl shadow-xl shadow-orange-500/20 transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-70 disabled:transform-none"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      {t.hero.submitting}
                    </>
                  ) : (
                    <>
                      {t.hero.submitButton}
                      <TrendingUp className="w-5 h-5 ml-2" />
                    </>
                  )}
                </Button>
              </form>
            </div>

            {/* Decorative elements behind form */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-gradient-to-b from-indigo-500/5 to-purple-500/5 rounded-full blur-3xl -z-10"></div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
