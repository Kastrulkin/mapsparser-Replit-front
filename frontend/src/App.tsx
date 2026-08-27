import { Suspense, lazy, useEffect, useState } from "react";
import { Toaster } from "./components/ui/toaster";
import { Toaster as Sonner } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { LanguageProvider, useLanguage } from "./i18n/LanguageContext";
import { CurrencyProvider } from "./contexts/CurrencyContext";
import { featureFlags } from "./config/featureFlags";
import { JourneyWorkspaceFocus } from "./components/journey/JourneyWorkspaceFocus";

const Index = lazy(() => import("./pages/Index"));
const About = lazy(() => import("./pages/About"));
const Login = lazy(() => import("./pages/Login"));
const SetPassword = lazy(() => import("./pages/SetPassword"));
const VerifyEmail = lazy(() => import("./pages/VerifyEmail"));
const Contact = lazy(() => import("./pages/Contact"));
const Policy = lazy(() => import("./pages/Policy"));
const Requisites = lazy(() => import("./pages/Requisites"));
const YclientsConnect = lazy(() => import("./pages/YclientsConnect"));
const DocsPage = lazy(() => import("./pages/DocsPage"));
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
const ROUTE_LOAD_TIMEOUT_MS = 12_000;
const CHUNK_RELOAD_STORAGE_KEY = "localos_chunk_reload_attempted";

const loadRouteWithRecovery = <T,>(loader: () => Promise<T>, routeName: string): Promise<T> => (
  new Promise<T>((resolve, reject) => {
    let settled = false;

    const finishWithError = (error: unknown) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeoutId);

      const normalizedError = error instanceof Error
        ? error
        : new Error(`Не удалось загрузить экран ${routeName}.`);

      if (window.sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY) !== "1") {
        window.sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, "1");
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.set("__localos_reload", String(Date.now()));
        window.location.replace(nextUrl.toString());
      }

      reject(normalizedError);
    };

    const timeoutId = window.setTimeout(() => {
      finishWithError(new Error(`Не удалось загрузить экран ${routeName} за отведённое время.`));
    }, ROUTE_LOAD_TIMEOUT_MS);

    loader().then((module) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeoutId);
      window.sessionStorage.removeItem(CHUNK_RELOAD_STORAGE_KEY);
      resolve(module);
    }).catch(finishWithError);
  })
);

const DashboardLayout = lazy(() =>
  loadRouteWithRecovery(
    () => import("./components/DashboardLayout").then((module) => ({
      default: module.DashboardLayout,
    })),
    "кабинета",
  ),
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
const ContentPage = lazy(() =>
  loadRouteWithRecovery(
    () => import("./pages/dashboard/ContentPage").then((module) => ({
      default: module.ContentPage,
    })),
    "контента",
  ),
);
const ProgressPage = lazy(() =>
  import("./pages/dashboard/ProgressPage").then((module) => ({
    default: module.ProgressPage,
  })),
);
const TodayPage = lazy(() =>
  import("./pages/dashboard/TodayPage").then((module) => ({
    default: module.TodayPage,
  })),
);
const FinancePage = lazy(() =>
  import("./pages/dashboard/FinancePage").then((module) => ({
    default: module.FinancePage,
  })),
);
const WebAnalyticsPage = lazy(() =>
  import("./pages/dashboard/WebAnalyticsPage").then((module) => ({
    default: module.WebAnalyticsPage,
  })),
);
const AverageTicketPage = lazy(() =>
  import("./pages/dashboard/AverageTicketPage").then((module) => ({
    default: module.AverageTicketPage,
  })),
);
const SettingsPage = lazy(() =>
  loadRouteWithRecovery(
    () => import("./pages/dashboard/SettingsPage").then((module) => ({
      default: module.SettingsPage,
    })),
    "настроек",
  ),
);
const AdminPage = lazy(() =>
  import("./pages/dashboard/AdminPage").then((module) => ({
    default: module.AdminPage,
  })),
);
const JourneyAdminPage = lazy(() =>
  import("./pages/dashboard/JourneyAdminPage").then((module) => ({
    default: module.JourneyAdminPage,
  })),
);
const GrowthPathsPage = lazy(() =>
  import("./pages/dashboard/GrowthPathsPage").then((module) => ({
    default: module.GrowthPathsPage,
  })),
);
const MorePage = lazy(() =>
  import("./pages/dashboard/MorePage").then((module) => ({
    default: module.MorePage,
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
const PromotionHubPage = lazy(() =>
  import("./pages/dashboard/PromotionHubPage").then((module) => ({
    default: module.PromotionHubPage,
  })),
);
const InfluencerPromotionPage = lazy(() =>
  import("./pages/dashboard/InfluencerPromotionPage").then((module) => ({
    default: module.InfluencerPromotionPage,
  })),
);
const CreatorRoomPage = lazy(() =>
  import("./pages/CreatorRoomPage").then((module) => ({
    default: module.CreatorRoomPage,
  })),
);
const OperatorPage = lazy(() =>
  import("./pages/dashboard/OperatorPage").then((module) => ({
    default: module.OperatorPage,
  })),
);
const TelegramRadarPage = lazy(() =>
  import("./pages/dashboard/TelegramRadarPage").then((module) => ({
    default: module.TelegramRadarPage,
  })),
);
const AgentBlueprintsPage = lazy(() =>
  import("./pages/dashboard/AgentBlueprintsPage").then((module) => ({
    default: module.AgentBlueprintsPage,
  })),
);
const Header = lazy(() => import("./components/Header"));
const NotFound = lazy(() => import("./pages/NotFound"));
const PublicPartnershipOfferPage = lazy(() => import("./pages/PublicPartnershipOfferPage"));
const PublicSalesRoomPage = lazy(() => import("./pages/PublicSalesRoomPage"));
const DemoEntryPage = lazy(() => import("./pages/DemoEntryPage"));
const VeselayaRascheskaOfferPage = lazy(() => import("./pages/VeselayaRascheskaOfferPage"));
const CheckoutReturn = lazy(() => import("./pages/CheckoutReturn"));
const TelegramControlPage = lazy(() => import("./pages/TelegramControlPage"));
const LeadJourneyPage = lazy(() => import("./pages/LeadJourneyPage"));
const IndustryPatternsE2EPage = import.meta.env.DEV
  ? lazy(() => import("./pages/dev/IndustryPatternsE2EPage"))
  : null;

const queryClient = new QueryClient();

const RouteFallback = () => {
  const [takingLong, setTakingLong] = useState(false);
  const { language } = useLanguage();
  const fallbackCopy = language === "tr"
    ? { loading: "Ekran yükleniyor…", slow: "Ekranın yüklenmesi beklenenden uzun sürüyor.", reload: "Sayfayı yenileyin" }
    : { loading: "Загружаем экран...", slow: "Экран загружается дольше обычного.", reload: "Обновить экран" };

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setTakingLong(true), 5_000);
    return () => window.clearTimeout(timeoutId);
  }, []);

  const reloadRoute = () => {
    window.sessionStorage.removeItem(CHUNK_RELOAD_STORAGE_KEY);
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("__localos_reload", String(Date.now()));
    window.location.replace(nextUrl.toString());
  };

  return (
    <div className="flex min-h-[40vh] items-center justify-center px-4 py-12">
      <div className="max-w-sm rounded-lg border border-slate-200 bg-white px-5 py-4 text-center text-sm text-slate-600 shadow-sm">
        <p>{takingLong ? fallbackCopy.slow : fallbackCopy.loading}</p>
        {takingLong ? (
          <button
            type="button"
            onClick={reloadRoute}
            className="mt-3 min-h-10 rounded-md bg-slate-950 px-4 py-2 font-medium text-white transition-colors hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
          >
            {fallbackCopy.reload}
          </button>
        ) : null}
      </div>
    </div>
  );
};

const shouldRenderHeader = (pathname: string) => {
  if (pathname.startsWith("/dashboard")) {
    return false;
  }

  if (pathname.startsWith("/room/")) {
    return false;
  }

  if (pathname.startsWith("/creator-room/")) {
    return false;
  }

  if (pathname === "/bazich") {
    return false;
  }

  if (pathname === "/demo") {
    return false;
  }

  if (pathname === "/telegram/control") {
    return false;
  }

  if (pathname === "/growth" || pathname.startsWith("/start/")) {
    return false;
  }

  if (pathname === "/veselaya-rascheska-hit") {
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
          <Route path="/privacy" element={<Policy />} />
          <Route path="/data-deletion" element={<Policy />} />
          <Route path="/requisites" element={<Requisites />} />
          <Route path="/yclients/connect" element={<YclientsConnect />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/docs/:section" element={<DocsPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/demo" element={<DemoEntryPage />} />
          <Route path="/telegram/control" element={<TelegramControlPage />} />
          <Route path="/articles" element={<ArticlesPage />} />
          <Route path="/articles/:slug" element={<ArticleDetailPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:slug" element={<DocumentDetailPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/:slug" element={<CaseDetailPage />} />

          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route index element={<Navigate to="/dashboard/today" replace />} />
            <Route path="today" element={<TodayPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="card" element={<JourneyWorkspaceFocus><CardOverviewPage /></JourneyWorkspaceFocus>} />
            <Route path="content" element={<JourneyWorkspaceFocus><ContentPage /></JourneyWorkspaceFocus>} />
            <Route path="content-plan" element={<Navigate to="/dashboard/content" replace />} />
            <Route path="progress" element={<ProgressPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="web-analytics" element={featureFlags.webTracking ? <WebAnalyticsPage /> : <Navigate to="/dashboard/progress" replace />} />
            <Route path="average-ticket" element={<AverageTicketPage />} />
            <Route path="ai-chat-promotion" element={<AIChatPromotionPage />} />
            <Route path="settings/*" element={<SettingsPage />} />
            <Route path="partnerships" element={<JourneyWorkspaceFocus><PartnershipSearchPage /></JourneyWorkspaceFocus>} />
            <Route path="promotion" element={<PromotionHubPage />} />
            <Route path="promotion/partnerships" element={<JourneyWorkspaceFocus><PartnershipSearchPage /></JourneyWorkspaceFocus>} />
            <Route path="promotion/influencers" element={<JourneyWorkspaceFocus><InfluencerPromotionPage /></JourneyWorkspaceFocus>} />
            <Route path="growth-paths" element={<GrowthPathsPage />} />
            <Route path="more" element={<MorePage />} />
            <Route path="operator" element={<OperatorPage />} />
            <Route path="telegram-radar" element={<TelegramRadarPage />} />
            <Route path="agents" element={<AgentBlueprintsPage />} />
            <Route path="bookings" element={<Navigate to="/dashboard/progress" replace />} />
            <Route path="chats" element={<ChatsPage />} />
            <Route path="network" element={<NetworkDashboardPage />} />
            <Route path="bazich" element={<AdminPage />} />
            <Route path="bazich/journeys" element={<JourneyAdminPage />} />
          </Route>
          <Route path="/bazich" element={<AdminPage />} />
          <Route path="/dashboard-old" element={<Dashboard />} />

          <Route path="/wizard" element={<WizardYandex />} />
          <Route path="/sprint" element={<Sprint />} />
          <Route path="/phrases" element={<ServicePhrases />} />
          <Route path="/card-recs" element={<CardRecommendations />} />
          <Route path="/set-password" element={<SetPassword />} />
          <Route path="/reset-password" element={<SetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/checkout/return" element={<CheckoutReturn />} />
          <Route path="/growth" element={<LeadJourneyPage />} />
          <Route path="/start/:token" element={<LeadJourneyPage />} />
          {IndustryPatternsE2EPage ? (
            <Route path="/__e2e__/industry-patterns" element={<IndustryPatternsE2EPage />} />
          ) : null}
          <Route path="/room/:roomSlug" element={<PublicSalesRoomPage />} />
          <Route path="/creator-room/:token" element={<CreatorRoomPage />} />
          <Route path="/veselaya-rascheska-hit" element={<VeselayaRascheskaOfferPage />} />
          <Route path="/web-analytics" element={<Navigate to="/dashboard/web-analytics" replace />} />
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
