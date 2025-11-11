import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle } from "lucide-react";
import abstractBg from "@/assets/abstract-bg.jpg";
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
    <section className="relative py-20 overflow-hidden" id="cta">
      <div 
        className="absolute inset-0 bg-cover bg-center opacity-10"
        style={{ backgroundImage: `url(${abstractBg})` }}
      />
      <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-accent/20" />
      
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            {t.cta.title}
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            {t.cta.subtitle}
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <h3 className="text-2xl font-bold text-foreground mb-6">
              {t.cta.startFree}
            </h3>
            
            <div className="space-y-4 mb-8">
              {benefits.map((benefit, index) => (
                <div key={index} className="flex items-center">
                  <CheckCircle className="w-5 h-5 text-success mr-3" />
                  <span className="text-foreground">{benefit}</span>
                </div>
              ))}
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
              <Button size="lg" className="text-lg px-8 py-6" onClick={() => {
                const form = document.getElementById('hero-form');
                if (form) {
                  form.scrollIntoView({ behavior: 'smooth' });
                  (form.querySelector('input, textarea, select') as HTMLElement)?.focus();
                }
              }}>
                {t.hero.submitButton}
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>

          <div className="bg-card rounded-2xl p-8 border border-border shadow-xl mb-12">
            <h3 className="text-2xl font-semibold text-foreground mb-6">{t.cta.whatYouGet}</h3>
            <div className="space-y-6">
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">1</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">{t.cta.clientGrowth}</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>{t.cta.clientGrowthDesc1}</li>
                    <li>{t.cta.clientGrowthDesc2}</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">2</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">{t.cta.control}</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>{t.cta.controlDesc1}</li>
                    <li>{t.cta.controlDesc2}</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">3</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">{t.cta.retention}</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>{t.cta.retentionDesc1}</li>
                    <li>{t.cta.retentionDesc2}</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">4</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">{t.cta.timeSaving}</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>{t.cta.timeSavingDesc1}</li>
                    <li>{t.cta.timeSavingDesc2}</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start">
                <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center mr-4 mt-1">
                  <span className="text-primary font-semibold">5</span>
                </div>
                <div>
                  <h5 className="font-semibold text-foreground mb-1 text-lg">{t.cta.support}</h5>
                  <ul className="list-disc pl-5 text-base text-muted-foreground space-y-1">
                    <li>{t.cta.supportDesc1}</li>
                    <li>{t.cta.supportDesc2}</li>
                  </ul>
                </div>
              </div>
            </div>
            <div className="text-center text-lg font-semibold text-primary mt-8 mb-2">{t.cta.finalText}</div>
            <Button 
              variant="default" 
              size="lg" 
              className="text-lg px-8 py-6 mt-4 w-full bg-orange-500 hover:bg-orange-600 text-white border-none"
              onClick={() => navigate('/contact')}
            >
              {t.cta.contactExpert}
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default CTA;