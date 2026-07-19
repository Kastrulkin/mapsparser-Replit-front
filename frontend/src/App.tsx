import { Suspense, lazy, useEffect, useState } from "react";
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
  import("./pages/dashboard/ContentPage").then((module) => ({
    default: module.ContentPage,
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
const IndustryPatternsE2EPage = import.meta.env.DEV
  ? lazy(() => import("./pages/dev/IndustryPatternsE2EPage"))
  : null;

const queryClient = new QueryClient();

const RouteFallback = () => {
  const [takingLong, setTakingLong] = useState(false);

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
        <p>{takingLong ? "Экран загружается дольше обычного." : "Загружаем экран..."}</p>
        {takingLong ? (
          <button
            type="button"
            onClick={reloadRoute}
            className="mt-3 min-h-10 rounded-md bg-slate-950 px-4 py-2 font-medium text-white transition-colors hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
          >
            Обновить экран
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

  if (pathname === "/bazich") {
    return false;
  }

  if (pathname === "/demo") {
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
            <Route path="content" element={<ContentPage />} />
            <Route path="content-plan" element={<Navigate to="/dashboard/content" replace />} />
            <Route path="progress" element={<ProgressPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="average-ticket" element={<AverageTicketPage />} />
            <Route path="ai-chat-promotion" element={<AIChatPromotionPage />} />
            <Route path="settings/*" element={<SettingsPage />} />
            <Route path="partnerships" element={<PartnershipSearchPage />} />
            <Route path="operator" element={<OperatorPage />} />
            <Route path="telegram-radar" element={<TelegramRadarPage />} />
            <Route path="agents" element={<AgentBlueprintsPage />} />
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
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/checkout/return" element={<CheckoutReturn />} />
          {IndustryPatternsE2EPage ? (
            <Route path="/__e2e__/industry-patterns" element={<IndustryPatternsE2EPage />} />
          ) : null}
          <Route path="/room/:roomSlug" element={<PublicSalesRoomPage />} />
          <Route path="/veselaya-rascheska-hit" element={<VeselayaRascheskaOfferPage />} />
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
