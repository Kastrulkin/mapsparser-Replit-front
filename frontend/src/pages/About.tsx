import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Footer from "@/components/Footer";
import SeoMeta from "@/components/SeoMeta";
import { useNavigate, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { ArrowUpRight, BriefcaseBusiness, Clock3, Factory, PackageCheck, Store, Truck, Wrench } from "lucide-react";
import { useLanguage } from "@/i18n/LanguageContext";
import { newAuth } from "@/lib/auth_new";
import { browserAuthenticationAvailable } from "@/lib/browserSessionFetch";
import { aboutStoryCopy } from "@/content/aboutStoryCopy";

const About = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t, language } = useLanguage();
  const isRu = language === "ru";
  const story = aboutStoryCopy[language];

  const handleSubscribeLanding = async (tierId: "starter" | "professional" | "concierge") => {
    const token = newAuth.getToken();

    if (!browserAuthenticationAvailable(token)) {
      localStorage.setItem("selectedTier", tierId);
      localStorage.setItem("selectedTierSource", "pricing");
      navigate(`/login?tab=register&source=pricing&tier=${tierId}`);
      return;
    }

    let paymentProvider = "yookassa";
    if (!isRu) {
      try {
        const providerResp = await fetch("/api/geo/payment-provider");
        const providerData = await providerResp.json();
        const detected = String(providerData?.payment_provider || "").trim().toLowerCase();
        paymentProvider = detected === "stripe" ? "stripe" : "yookassa";
      } catch {
        paymentProvider = "yookassa";
      }
    } else {
      paymentProvider = "yookassa";
    }

    const selectedBusinessId = localStorage.getItem("selectedBusinessId") || "";

    try {
      const response = await fetch("/api/billing/checkout/session/start", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          provider: paymentProvider,
          entry_point: "registered_paywall",
          channel: "web",
          tariff_id: tierId,
          business_id: selectedBusinessId || undefined,
          source: "about_pricing_page",
        }),
      });
      const data = await response.json();
      const redirectUrl = String(data?.confirmation_url || data?.url || "").trim();
      if (!response.ok || !redirectUrl) {
        throw new Error(String(data?.error || "Не удалось создать сессию оплаты"));
      }
      window.location.href = redirectUrl;
    } catch (error) {
      alert(error instanceof Error ? error.message : "Не удалось перейти к оплате");
    }
  };

  useEffect(() => {
    const scrollToPricing = () => {
      if (window.location.hash === "#pricing") {
        const el = document.getElementById("pricing");
        if (el) {
          setTimeout(() => {
            el.scrollIntoView({ behavior: "smooth" });
          }, 100);
        }
      }
    };

    // Прокручиваем при монтировании
    scrollToPricing();

    // Прокручиваем при изменении хеша
    const handleHashChange = () => {
      scrollToPricing();
    };

    window.addEventListener('hashchange', handleHashChange);

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, [location.hash]);

  return (
    <div className="min-h-screen bg-background">
      <SeoMeta
        description={story.metaDescription}
        path="/about"
        title={story.metaTitle}
      />

      <section className="relative overflow-hidden border-b border-white/10 bg-slate-950 px-4 py-20 text-white sm:px-6 sm:py-24 lg:px-8 lg:py-32">
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-primary/20 blur-3xl" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-amber-400/10 blur-3xl" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-7xl items-end gap-14 lg:grid-cols-12 lg:gap-20">
          <div className="lg:col-span-8">
            <div className="mb-7 flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.22em] text-orange-300">
              <span className="h-px w-8 bg-orange-400" aria-hidden="true" />
              {story.eyebrow}
            </div>
            <h1 className="max-w-5xl text-balance text-4xl font-semibold tracking-[-0.045em] sm:text-5xl lg:text-7xl lg:leading-[1.02]">
              {story.title}
            </h1>
            <p className="mt-8 max-w-3xl text-pretty text-lg leading-8 text-slate-300 sm:text-xl sm:leading-9">
              {story.intro}
            </p>
          </div>

          <div className="lg:col-span-4">
            <div className="rounded-[28px] border border-white/10 bg-white/[0.06] p-7 shadow-2xl shadow-black/20 backdrop-blur-sm sm:p-8">
              <Clock3 className="h-6 w-6 text-orange-400" aria-hidden="true" />
              <div className="mt-8 text-4xl font-semibold tracking-[-0.04em] text-white sm:text-5xl">{story.workdayValue}</div>
              <p className="mt-4 text-base leading-7 text-slate-300">{story.workdayText}</p>
              <p className="mt-6 border-t border-white/10 pt-5 text-sm font-medium text-orange-300">{story.workdayNote}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-white px-4 py-20 sm:px-6 sm:py-24 lg:px-8 lg:py-32">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-14 lg:grid-cols-12 lg:gap-20">
            <aside className="lg:col-span-4">
              <div className="lg:sticky lg:top-24">
                <div className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">{story.storyEyebrow}</div>
                <h2 className="mt-5 text-balance text-4xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-5xl">{story.storyTitle}</h2>
                <p className="mt-6 max-w-md text-lg leading-8 text-slate-600">{story.storyIntro}</p>
                <div className="mt-8 flex flex-wrap gap-2">
                  {story.industries.map((industry, index) => {
                    const icons = [Truck, Store, Factory, PackageCheck, Wrench];
                    const Icon = icons[index];
                    return (
                      <span key={industry} className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700">
                        <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                        {industry}
                      </span>
                    );
                  })}
                </div>
              </div>
            </aside>

            <div className="lg:col-span-8">
              <ol className="border-l border-slate-200">
                {[
                  [story.chapterOneTitle, story.chapterOneText],
                  [story.chapterTwoTitle, story.chapterTwoText],
                  [story.chapterThreeTitle, story.chapterThreeText],
                ].map(([title, text], index) => (
                  <li key={title} className="relative pb-14 pl-8 last:pb-0 sm:pl-12">
                    <span className="absolute -left-4 top-0 grid h-8 w-8 place-items-center rounded-full border-4 border-white bg-slate-950 text-[10px] font-semibold tracking-wider text-white">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <h3 className="text-balance text-2xl font-semibold tracking-[-0.025em] text-slate-950 sm:text-3xl">{title}</h3>
                    <div className="mt-4 max-w-3xl space-y-4">
                      {text.split("\n\n").map((paragraph) => (
                        <p className="text-pretty text-base leading-8 text-slate-600 sm:text-lg" key={paragraph}>{paragraph}</p>
                      ))}
                    </div>
                  </li>
                ))}
              </ol>

              <div className="mt-16 overflow-hidden rounded-[28px] bg-orange-50 ring-1 ring-inset ring-orange-200/70">
                <div className="grid gap-8 p-7 sm:p-9 lg:grid-cols-[1fr_auto] lg:items-end lg:p-10">
                  <div>
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-orange-700">
                      <BriefcaseBusiness className="h-4 w-4" aria-hidden="true" />
                      {story.channelEyebrow}
                    </div>
                    <h3 className="mt-5 text-balance text-3xl font-semibold tracking-[-0.035em] text-slate-950">{story.channelTitle}</h3>
                    <p className="mt-4 max-w-2xl text-pretty text-base leading-7 text-slate-700">{story.channelText}</p>
                  </div>
                  <a
                    href="https://t.me/meowandco"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-slate-950 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-950/10 transition duration-200 hover:-translate-y-0.5 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 motion-reduce:transform-none"
                  >
                    {story.channelButton}
                    <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 px-4 sm:px-6 lg:px-8 bg-gradient-to-b from-white to-orange-50/30">
        <div className="max-w-7xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">{t.about.pricingTitle}</h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">{t.about.pricingSubtitle}</p>

          <div className="grid lg:grid-cols-4 gap-8 mb-8 items-stretch">
            {/* Starter */}
            <Card className="group p-8 flex flex-col h-full bg-white border-2 border-gray-200 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10 transition-all duration-300 rounded-2xl">
              <CardContent className="p-0 flex flex-col flex-1">
                <div className="text-2xl font-bold bg-gradient-to-r from-orange-500 to-amber-600 bg-clip-text text-transparent mb-2">
                  {isRu ? "Карты" : t.about.pricingStarterTitle}
                </div>
                <div className="text-sm text-gray-600 mb-4">
                  {isRu ? "1200 ₽/месяц (240 кредитов)" : t.about.pricingStarterPrice}
                </div>
                {isRu ? <div className="text-sm text-gray-600 mb-3">Всё для локальной видимости:</div> : null}
                <div className="space-y-2 text-muted-foreground mb-6 flex-1">
                  <div>- {isRu ? "аудит, услуги, отзывы, фото и конкуренты" : t.about.pricingStarterPoint1}</div>
                  <div>- {isRu ? "новости для публикации на картах" : t.about.pricingStarterPoint2}</div>
                  <div>- {isRu ? "Telegram-радар по вашей индустрии" : t.about.pricingStarterPoint3}</div>
                  <div>- {isRu ? "веб-аналитика и tracker для сайта" : t.about.pricingStarterPoint4}</div>
                </div>
                {isRu ? <div className="mb-6 text-xs leading-5 text-gray-500">* Интеллектуальная работа с фотографиями включается отдельно и расходует кредиты только при анализе нового фото.</div> : null}
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 btn-iridescent mt-auto w-full"
                  onClick={() => handleSubscribeLanding("starter")}
                >
                  {t.about.pricingStarterButton}
                </Button>
              </CardContent>
            </Card>

            {/* Option 0 - 5000 ₽/месяц */}
            <Card className="group p-8 flex flex-col h-full bg-gradient-to-br from-orange-50 to-amber-50 border-2 border-orange-400 hover:border-orange-500 hover:shadow-2xl hover:shadow-orange-500/20 transition-all duration-300 rounded-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 bg-gradient-to-br from-orange-500 to-amber-600 text-white text-xs font-bold px-4 py-1 rounded-bl-xl">{story.popular}</div>
              <CardContent className="p-0 flex flex-col flex-1">
                <div className="text-2xl font-bold text-primary mb-1">
                  {isRu ? "Привлечение" : t.about.pricingOption0Title}
                </div>
                <div className="text-sm text-gray-600 mb-4">
                  {isRu ? "5000 ₽/месяц (1000 кредитов)" : t.about.pricingOption0Price}
                </div>
                {isRu ? <div className="text-sm text-gray-600 mb-3">Хватит чтобы:</div> : null}
                <div className="space-y-2 text-muted-foreground mb-6 flex-1">
                  <div>- {isRu ? "всё из тарифа «Карты»" : t.about.pricingOption0Point1}</div>
                  <div>- {isRu ? "полный цикл работы с партнёрами" : t.about.pricingOption0Point2}</div>
                  <div>- {isRu ? "полный цикл работы с инфлюенсерами" : t.about.pricingOption0Point3}</div>
                  <div>- {isRu ? "продвижение и видимость в AI-чатах" : t.about.pricingOption0Point4}</div>
                </div>
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 btn-iridescent mt-auto w-full"
                  onClick={() => handleSubscribeLanding("professional")}
                >
                  {t.about.pricingOption0Button}
                </Button>
              </CardContent>
            </Card>

            {/* Option 1 */}
            <Card className="group p-8 flex flex-col h-full bg-white border-2 border-gray-200 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10 transition-all duration-300 rounded-2xl">
              <CardContent className="p-0 flex flex-col flex-1">
                <div className="text-2xl font-bold text-primary mb-1">
                  {isRu ? "Управление" : t.about.pricingOption1Title}
                </div>
                <div className="text-sm text-gray-600 mb-4">
                  {isRu ? "25000 ₽/месяц" : t.about.pricingOption1Price}
                </div>
                {isRu ? <div className="text-sm text-gray-600 mb-3">Рост показателей и автоматизация</div> : null}
                <div className="space-y-2 text-muted-foreground mb-6 flex-1">
                  <div>- {isRu ? "всё из тарифа «Привлечение»" : t.about.pricingOption1Point1}</div>
                  <div>- {isRu ? "финансы и рост среднего чека" : t.about.pricingOption1Point2}</div>
                  <div>- {isRu ? "ИИ-сотрудники и Оператор" : t.about.pricingOption1Point3}</div>
                  <div>- {isRu ? "рабочие чаты и автоматизация" : t.about.pricingOption1Point4}</div>
                  <div>- {isRu ? "контент для соцсетей и подключение каналов" : t.about.pricingOption1Point5}</div>
                </div>
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 btn-iridescent mt-auto w-full"
                  onClick={() => handleSubscribeLanding("concierge")}
                >
                  {t.about.pricingOption1Button}
                </Button>
              </CardContent>
            </Card>

            {/* Option 2 */}
            <Card className="group p-8 flex flex-col h-full bg-white border-2 border-gray-200 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10 transition-all duration-300 rounded-2xl">
              <CardContent className="p-0 flex flex-col flex-1">
                <div className="text-2xl font-bold text-primary mb-1">
                  {isRu ? "Особый (Elite)" : "Elite"}
                </div>
                <div className="text-sm text-gray-600 mb-4">{isRu ? "7% от оплат привлечённых клиентов" : t.about.pricingOption2Subtitle}</div>
                {isRu ? <div className="text-sm text-gray-600 mb-3">(Мы делаем всё за вас и даже больше)</div> : null}
                <div className="space-y-2 text-muted-foreground mb-6 flex-1">
                  <div>- {isRu ? "Привлечение клиентов онлайн" : t.about.pricingOption2Point1}</div>
                  <div>- {isRu ? "Коммуникация с клиентами" : t.about.pricingOption2Point2}</div>
                  <div>- {isRu ? "Привлечение клиентов оффлайн" : t.about.pricingOption2Point3}</div>
                  <div>- {isRu ? "Оптимизация бизнес-процессов" : t.about.pricingOption2Point4}</div>
                  {isRu ? <div>- Выделенный менеджер</div> : null}
                </div>
                {!isRu ? (
                  <div className="text-sm text-muted-foreground italic mt-4">
                    {t.about.pricingOption2Note}
                  </div>
                ) : null}
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 btn-iridescent mt-auto w-full"
                  onClick={() => navigate("/contact")}
                >
                  {t.about.contactUs}
                </Button>
              </CardContent>
            </Card>
          </div>


        </div>
      </section>

      {/* Final CTA Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-muted/50">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-foreground mb-6">
            {t.about.finalTitle}
          </h2>
          <p className="text-xl text-muted-foreground mb-8">
            {t.about.finalText}
          </p>
          <div className="flex justify-center">
            <Button size="lg" className="text-lg px-8 py-3 btn-iridescent"
              onClick={() => navigate('/contact')}
            >
              {t.about.contactUs}
            </Button>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default About; 
