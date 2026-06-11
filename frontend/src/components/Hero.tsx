import { Button } from "@/components/ui/button";
import { TrendingUp, Heart, Loader2 } from "lucide-react";
import heroImage from "@/assets/hero-image.jpg";
import { useState } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { cn } from '@/lib/design-tokens';

const Hero = () => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { t } = useLanguage();

  return (
    <section className="relative overflow-hidden bg-background">
      <div className="mx-auto grid min-h-[calc(100svh-80px)] max-w-7xl grid-cols-1 items-center gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(420px,1.05fr)] lg:gap-14 lg:px-8 lg:py-10">
        <div className="relative z-10 flex flex-col gap-6">
          <div>
            <div className="inline-flex items-center px-4 py-2 bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-100 rounded-full text-sm font-medium text-orange-700 mb-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <Heart className="w-4 h-4 mr-2 text-orange-500 fill-orange-500" />
              {t.hero.newClients}
            </div>

            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 leading-tight tracking-tight animate-in fade-in slide-in-from-bottom-5 duration-1000 delay-100">
              {t.hero.title}
            </h1>
          </div>

          <div className="relative animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
            {/* Glassmorphic Form Card */}
            <div className={cn(
              "relative z-20 rounded-2xl p-5 shadow-2xl sm:p-6",
              "bg-white/85 backdrop-blur-xl border border-white/60",
              "ring-1 ring-gray-900/5"
            )}>
              <div className="mb-5">
                <h3 className="text-2xl font-bold text-gray-900 mb-1">{t.hero.formTitle}</h3>
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
                    const targetUrl = String((result && result.public_url) || '').trim();
                    if (targetUrl) {
                      window.location.href = targetUrl;
                      return;
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
                className="space-y-4"
              >
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-gray-700 ml-1">{t.hero.emailLabel}</label>
                  <input
                    name="email"
                    type="email"
                    placeholder={t.hero.emailPlaceholder}
                    required
                    className="w-full rounded-xl border border-gray-200 bg-white/70 px-5 py-3.5 text-base transition-all duration-200 placeholder:text-gray-400 focus:border-orange-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-orange-500/10"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-semibold text-gray-700 ml-1">{t.hero.mapsLinkLabel}</label>
                  <input
                    name="yandexUrl"
                    type="url"
                    placeholder={t.hero.yandexUrlPlaceholder}
                    required
                    className="w-full rounded-xl border border-gray-200 bg-white/70 px-5 py-3.5 text-base transition-all duration-200 placeholder:text-gray-400 focus:border-orange-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-orange-500/10"
                  />
                </div>

                <Button
                  type="submit"
                  size="lg"
                  disabled={isSubmitting}
                  className="w-full btn-iridescent text-white px-8 py-5 text-base font-bold rounded-xl shadow-xl shadow-orange-500/20 transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-70 disabled:transform-none"
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
          </div>
        </div>

        <div className="relative hidden animate-in fade-in slide-in-from-left-8 duration-1000 delay-200 sm:block">
          <img
            src={heroImage}
            alt="Local Hero"
            className="aspect-[16/9] w-full rounded-2xl object-cover shadow-2xl lg:max-h-[410px]"
          />
        </div>
      </div>
    </section>
  );
};

export default Hero;
