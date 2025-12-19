import { useEffect } from "react";
import { Toaster } from "./components/ui/toaster";
import { Toaster as Sonner } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LanguageProvider, useLanguage } from "./i18n/LanguageContext";
import { CurrencyProvider } from "./contexts/CurrencyContext";
import Header from "./components/Header";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import About from "./pages/About";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import { DashboardLayout } from "./components/DashboardLayout";
import { ProfilePage } from "./pages/dashboard/ProfilePage";
import { CardOverviewPage } from "./pages/dashboard/CardOverviewPage";
import { ProgressPage } from "./pages/dashboard/ProgressPage";
import { FinancePage } from "./pages/dashboard/FinancePage";
import { SettingsPage } from "./pages/dashboard/SettingsPage";
import { AdminPage } from "./pages/dashboard/AdminPage";
import SetPassword from "./pages/SetPassword";
import Contact from "./pages/Contact";
import WizardYandex from "./pages/WizardYandex";
import Sprint from "./pages/Sprint";
import ServicePhrases from "./pages/ServicePhrases";
import CardRecommendations from "./pages/CardRecommendations";

const queryClient = new QueryClient();

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
        <Header />
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/login" element={<Login />} />

          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route index element={<Navigate to="/dashboard/progress" replace />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="card" element={<CardOverviewPage />} />
            <Route path="progress" element={<ProgressPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="/bazich" element={<AdminPage />} />
          {/* Legacy route - keep for backward compatibility */}
          <Route path="/dashboard-old" element={<Dashboard />} />

          <Route path="/wizard" element={<WizardYandex />} />
          <Route path="/sprint" element={<Sprint />} />
          <Route path="/phrases" element={<ServicePhrases />} />
          <Route path="/card-recs" element={<CardRecommendations />} />
          <Route path="/set-password" element={<SetPassword />} />
          <Route path="/reset-password" element={<SetPassword />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
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
