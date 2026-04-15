import { Suspense, useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { LanguageProvider, useLanguage } from "./i18n/LanguageContext";
import { CurrencyProvider } from "./contexts/CurrencyContext";
import PublicPartnershipOfferPage from "./pages/PublicPartnershipOfferPage";

const RouteFallback = () => (
  <div className="flex min-h-screen items-center justify-center px-4 py-12">
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
      Loading audit...
    </div>
  </div>
);

const PublicOfferContent = () => {
  const { t } = useLanguage();

  useEffect(() => {
    document.title = t.pageTitle;
  }, [t.pageTitle]);

  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/:offerSlug" element={<PublicPartnershipOfferPage />} />
          <Route path="*" element={<PublicPartnershipOfferPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
};

const PublicOfferApp = () => (
  <LanguageProvider>
    <CurrencyProvider>
      <PublicOfferContent />
    </CurrencyProvider>
  </LanguageProvider>
);

export default PublicOfferApp;
