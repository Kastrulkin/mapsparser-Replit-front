import { Suspense, lazy, useEffect } from "react";
import { Toaster } from "./components/ui/toaster";
import { Toaster as Sonner } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { LanguageProvider, useLanguage } from "./i18n/LanguageContext";
import { CurrencyProvider } from "./contexts/CurrencyContext";

const Index = lazy(() => import("./pages/Index"));
const About = lazy(() => import("./pages/About"));
const Login = lazy(() => import("./pages/Login"));
const SetPassword = lazy(() => import("./pages/SetPassword"));
const Contact = lazy(() => import("./pages/Contact"));
const Policy = lazy(() => import("./pages/Policy"));
const Requisites = lazy(() => import("./pages/Requisites"));
const ArticlesPage = lazy(() => import("./pages/content/ArticlesPage"));
const ArticleDetailPage = lazy(() => import("./pages/content/ArticleDetailPage"));
const DocumentsPage = lazy(() => import("./pages/content/DocumentsPage"));
const DocumentDetailPage = lazy(() => import("./pages/content/DocumentDetailPage"));
const CasesPage = lazy(() => import("./pages/content/CasesPage"));
const CaseDetailPage = lazy(() => import("./pages/content/CaseDetailPage"));
const WizardYandex = lazy(() => import("./pages/WizardYandex"));
const Sprint = lazy(() => import("./pages/Sprint"));
const ServicePhrases = lazy(() => import("./pages/ServicePhrases"));
const CardRecommendations = lazy(() => import("./pages/CardRecommendations"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const DashboardLayout = lazy(() =>
  import("./components/DashboardLayout").then((module) => ({
    default: module.DashboardLayout,
  })),
);

const NetworkDashboardPage = lazy(() =>
  import("./pages/dashboard/network/NetworkDashboardPage").then((module) => ({
    default: module.NetworkDashboardPage,
  })),
);
const ProfilePage = lazy(() =>
  import("./pages/dashboard/ProfilePage").then((module) => ({
    default: module.ProfilePage,
  })),
);
const CardOverviewPage = lazy(() =>
  import("./pages/dashboard/CardOverviewPage").then((module) => ({
    default: module.CardOverviewPage,
  })),
);
const ProgressPage = lazy(() =>
  import("./pages/dashboard/ProgressPage").then((module) => ({
    default: module.ProgressPage,
  })),
);
const FinancePage = lazy(() =>
  import("./pages/dashboard/FinancePage").then((module) => ({
    default: module.FinancePage,
  })),
);
const SettingsPage = lazy(() =>
  import("./pages/dashboard/SettingsPage").then((module) => ({
    default: module.SettingsPage,
  })),
);
const AdminPage = lazy(() =>
  import("./pages/dashboard/AdminPage").then((module) => ({
    default: module.AdminPage,
  })),
);
const BookingsPage = lazy(() =>
  import("./pages/dashboard/BookingsPage").then((module) => ({
    default: module.BookingsPage,
  })),
);
const ChatsPage = lazy(() =>
  import("./pages/dashboard/ChatsPage").then((module) => ({
    default: module.ChatsPage,
  })),
);
const AIChatPromotionPage = lazy(() =>
  import("./pages/dashboard/AIChatPromotionPage").then((module) => ({
    default: module.AIChatPromotionPage,
  })),
);
const PartnershipSearchPage = lazy(() =>
  import("./pages/dashboard/PartnershipSearchPage").then((module) => ({
    default: module.PartnershipSearchPage,
  })),
);
const Header = lazy(() => import("./components/Header"));
const NotFound = lazy(() => import("./pages/NotFound"));
const PublicPartnershipOfferPage = lazy(() => import("./pages/PublicPartnershipOfferPage"));
const CheckoutReturn = lazy(() => import("./pages/CheckoutReturn"));

const queryClient = new QueryClient();

const RouteFallback = () => (
  <div className="flex min-h-[40vh] items-center justify-center px-4 py-12">
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
      Загружаем экран...
    </div>
  </div>
);

const shouldRenderHeader = (pathname: string) => {
  if (pathname.startsWith("/dashboard")) {
    return false;
  }

  if (pathname === "/bazich") {
    return false;
  }

  return true;
};

const AppShell = () => {
  const location = useLocation();
  const showHeader = shouldRenderHeader(location.pathname);

  return (
    <>
      {showHeader ? (
        <Suspense fallback={null}>
          <Header />
        </Suspense>
      ) : null}
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/policy" element={<Policy />} />
          <Route path="/requisites" element={<Requisites />} />
          <Route path="/login" element={<Login />} />
          <Route path="/articles" element={<ArticlesPage />} />
          <Route path="/articles/:slug" element={<ArticleDetailPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:slug" element={<DocumentDetailPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/:slug" element={<CaseDetailPage />} />

          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route index element={<Navigate to="/dashboard/profile" replace />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="card" element={<CardOverviewPage />} />
            <Route path="progress" element={<ProgressPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="ai-chat-promotion" element={<AIChatPromotionPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="partnerships" element={<PartnershipSearchPage />} />
            <Route path="bookings" element={<BookingsPage />} />
            <Route path="chats" element={<ChatsPage />} />
            <Route path="network" element={<NetworkDashboardPage />} />
            <Route path="bazich" element={<AdminPage />} />
          </Route>
          <Route path="/bazich" element={<AdminPage />} />
          <Route path="/dashboard-old" element={<Dashboard />} />

          <Route path="/wizard" element={<WizardYandex />} />
          <Route path="/sprint" element={<Sprint />} />
          <Route path="/phrases" element={<ServicePhrases />} />
          <Route path="/card-recs" element={<CardRecommendations />} />
          <Route path="/set-password" element={<SetPassword />} />
          <Route path="/reset-password" element={<SetPassword />} />
          <Route path="/checkout/return" element={<CheckoutReturn />} />
          <Route path="/:offerSlug" element={<PublicPartnershipOfferPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </>
  );
};

const AppContent = () => {
  const { t } = useLanguage();

  useEffect(() => {
    document.title = t.pageTitle;
  }, [t.pageTitle]);

  return (
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </TooltipProvider>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <LanguageProvider>
      <CurrencyProvider>
        <AppContent />
      </CurrencyProvider>
    </LanguageProvider>
  </QueryClientProvider>
);

export default App;
