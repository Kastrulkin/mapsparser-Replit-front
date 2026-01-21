import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, Target, Lightbulb, Award, Heart, Globe } from "lucide-react";
import Footer from "@/components/Footer";
import { useNavigate, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { useLanguage } from "@/i18n/LanguageContext";
import { newAuth } from "@/lib/auth_new";

const About = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t, language } = useLanguage();
  const isRu = language === "ru";

  const handleSubscribeLanding = (tierId: "starter" | "professional" | "concierge") => {
    const token = newAuth.getToken();

    // Если пользователь не авторизован — ведём на регистрацию с выбранным тарифом
    if (!token) {
      navigate(`/login?tab=register&tier=${tierId}&source=pricing`);
      return;
    }

    // Если уже авторизован — ведём в личный кабинет на страницу подписки
    navigate(`/dashboard/settings?payment=required&tier=${tierId}&source=pricing`);
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

      {/* Hero Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-orange-50 via-white to-amber-50">
        <div className="max-w-7xl mx-auto text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 mb-8">
            {t.about.heroTitle}
          </h1>
          <p className="text-2xl text-gray-600 max-w-4xl mx-auto mb-8 leading-relaxed">
            {t.about.heroSubtitle}
          </p>
        </div>
      </section>

      {/* Problem Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-5xl mx-auto">
          <div className="space-y-8 text-lg text-gray-600 leading-relaxed">
            <p className="text-xl">
              {t.about.problemText}
            </p>
            <div className="text-center py-8">
              <div className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-orange-500 to-amber-600 bg-clip-text text-transparent">
                {t.about.problemHighlight}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* About Us Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-foreground mb-8">{t.about.teamTitle}</h2>
          <p className="text-lg text-muted-foreground mb-8">
            {t.about.teamText}
          </p>
        </div>
      </section>

      {/* Target Audience Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-muted/50">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-foreground mb-8">{t.about.targetTitle}</h2>
          <p className="text-xl text-muted-foreground mb-8">
            {t.about.targetText}
          </p>

          <div className="grid md:grid-cols-4 gap-6 mb-8">
            <div className="text-center">
              <div className="text-3xl mb-2">💇‍♀️</div>
              <div className="font-medium text-foreground">{t.about.salons}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl mb-2">💅</div>
              <div className="font-medium text-foreground">{t.about.masters}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl mb-2">🎨</div>
              <div className="font-medium text-foreground">{t.about.studios}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl mb-2">🏪</div>
              <div className="font-medium text-foreground">{t.about.localBusiness}</div>
            </div>
          </div>
        </div>
      </section>

      {/* Results Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-orange-50 via-white to-amber-50">
        <div className="max-w-5xl mx-auto text-center">
          <div className="bg-white rounded-3xl p-16 shadow-2xl shadow-orange-500/10 border-2 border-orange-200">
            <h2 className="text-4xl font-bold text-gray-900 mb-8">{t.about.resultsTitle}</h2>
            <div className="text-7xl font-bold bg-gradient-to-r from-orange-500 to-amber-600 bg-clip-text text-transparent mb-6">{t.about.resultsPercent}</div>
            <p className="text-2xl text-gray-700 leading-relaxed">
              {t.about.resultsText}
            </p>
          </div>
        </div>
      </section>

      {/* How We Work Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl font-bold text-foreground mb-12 text-center">{t.about.howTitle}</h2>

          <div className="mb-12">
            <h3 className="text-2xl font-semibold text-foreground mb-6 text-center">
              {t.about.howSubtitle}
            </h3>
          </div>

          <div className="grid lg:grid-cols-2 gap-12">
            {/* Option 1 */}
            <Card className="group p-10 bg-white border-2 border-gray-200 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10 transition-all duration-300 rounded-2xl">
              <CardContent className="p-0">
                <div className="flex items-center gap-4 mb-6">
                  <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-amber-600 rounded-2xl flex items-center justify-center shadow-lg">
                    <span className="text-white font-bold text-xl">1</span>
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900">{t.about.option1Title}</h3>
                </div>
                <div className="space-y-4 text-gray-600 mb-8">
                  <div className="flex items-start gap-3">
                    <span className="text-orange-500 text-xl">•</span>
                    <span className="text-base">{t.about.option1Point1}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="text-orange-500 text-xl">•</span>
                    <span className="text-base">{t.about.option1Point2}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="text-orange-500 text-xl">•</span>
                    <span className="text-base">{t.about.option1Point3}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="text-orange-500 text-xl">•</span>
                    <span className="text-base">{t.about.option1Point4}</span>
                  </div>
                </div>
                <Button
                  size="lg"
                  className="mt-2 text-lg px-10 py-6 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white border-none shadow-lg shadow-orange-500/30"
                  onClick={() => {
                    window.location.href = '/#hero-form';
                  }}
                >
                  {t.about.option1Button}
                </Button>
              </CardContent>
            </Card>

            {/* Option 2 */}
            <Card className="group p-10 bg-gradient-to-br from-orange-50 to-amber-50 border-2 border-orange-400 hover:border-orange-500 hover:shadow-2xl hover:shadow-orange-500/20 transition-all duration-300 rounded-2xl">
              <CardContent className="p-0">
                <div className="flex items-center gap-4 mb-6">
                  <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-amber-600 rounded-2xl flex items-center justify-center shadow-lg">
                    <span className="text-white font-bold text-xl">2</span>
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900">{t.about.option2Title}</h3>
                </div>
                <div className="space-y-4 text-gray-700 mb-8">
                  <div className="flex items-start gap-3">
                    <span className="text-orange-500 text-xl">•</span>
                    <span className="text-base">{t.about.option2Point1}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="text-orange-500 text-xl">•</span>
                    <span className="text-base">{t.about.option2Point2}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="text-orange-500 text-xl">•</span>
                    <span className="text-base">{t.about.option2Point3}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="text-orange-500 text-xl">•</span>
                    <span className="text-base">{t.about.option2Point4}</span>
                  </div>
                </div>
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-10 py-6 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white border-none shadow-lg shadow-orange-500/30 mt-2"
                  onClick={() => {
                    navigate('/contact');
                  }}
                >
                  {t.about.option2Button}
                </Button>
              </CardContent>
            </Card>
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
                  {t.about.pricingStarterTitle}
                </div>
                <div className="text-sm text-gray-600 mb-4">
                  {t.about.pricingStarterPrice}
                </div>
                <div className="space-y-2 text-muted-foreground mb-6 flex-1">
                  <div>- {t.about.pricingStarterPoint1}</div>
                  <div>- {t.about.pricingStarterPoint2}</div>
                  <div>- {t.about.pricingStarterPoint3}</div>
                  <div>- {t.about.pricingStarterPoint4}</div>
                </div>
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white border-none shadow-lg shadow-orange-500/30 hover:shadow-orange-600/40 transition-all duration-300 mt-auto w-full"
                  onClick={() => handleSubscribeLanding("starter")}
                >
                  {t.about.pricingStarterButton}
                </Button>
              </CardContent>
            </Card>

            {/* Option 0 - 5000 рублей в месяц */}
            <Card className="group p-8 flex flex-col h-full bg-gradient-to-br from-orange-50 to-amber-50 border-2 border-orange-400 hover:border-orange-500 hover:shadow-2xl hover:shadow-orange-500/20 transition-all duration-300 rounded-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 bg-gradient-to-br from-orange-500 to-amber-600 text-white text-xs font-bold px-4 py-1 rounded-bl-xl">POPULAR</div>
              <CardContent className="p-0 flex flex-col flex-1">
                <div className="text-2xl font-bold text-primary mb-1">
                  {isRu ? "Профессиональный" : "Professional"}
                </div>
                <div className="text-sm text-gray-600 mb-4">
                  {isRu ? "5000 рублей в месяц" : "$55 / month"}
                </div>
                <div className="space-y-2 text-muted-foreground mb-6 flex-1">
                  <div>- {t.about.pricingOption0Point1}</div>
                  <div>- {t.about.pricingOption0Point2}</div>
                  <div>- {t.about.pricingOption0Point3}</div>
                  <div>- {t.about.pricingOption0Point4}</div>
                  <div>- {t.about.pricingOption0Point5}</div>
                  <div>- {t.about.pricingOption0Point6}</div>
                  <div>- {t.about.pricingOption0Point7}</div>
                  <div>- {t.about.pricingOption0Point8}</div>
                </div>
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 bg-orange-500 hover:bg-orange-600 text-white border-none mt-auto w-full"
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
                  {isRu ? "Консьерж" : "Concierge"}
                </div>
                <div className="text-sm text-gray-600 mb-4">
                  {isRu ? "25000 рублей в месяц" : "$310 / month"}
                </div>
                <div className="space-y-2 text-muted-foreground mb-6 flex-1">
                  <div>- {t.about.pricingOption1Point1}</div>
                  <div>- {t.about.pricingOption1Point2}</div>
                  <div>- {t.about.pricingOption1Point3}</div>
                  <div>- {t.about.pricingOption1Point4}</div>
                  <div>- {t.about.pricingOption1Point5}</div>
                </div>
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 bg-orange-500 hover:bg-orange-600 text-white border-none mt-auto w-full"
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
                  {isRu ? "Особый" : "Elite"}
                </div>
                <div className="text-sm text-gray-600 mb-4">{t.about.pricingOption2Subtitle}</div>
                <div className="space-y-2 text-muted-foreground mb-6 flex-1">
                  <div>- {t.about.pricingOption2Point1}</div>
                  <div>- {t.about.pricingOption2Point2}</div>
                  <div>- {t.about.pricingOption2Point3}</div>
                  <div>- {t.about.pricingOption2Point4}</div>
                </div>
                <div className="text-sm text-muted-foreground italic mt-4">
                  {t.about.pricingOption2Note}
                </div>
                <Button
                  variant="default"
                  size="lg"
                  className="text-lg px-8 py-3 bg-orange-500 hover:bg-orange-600 text-white border-none mt-auto w-full"
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
            <Button size="lg" className="text-lg px-8 py-3"
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