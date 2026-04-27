import { createRoot } from "react-dom/client";
import PublicOfferApp from "./PublicOfferApp";
import "./index.css";
import { ErrorBoundary } from "./components/ErrorBoundary";

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <PublicOfferApp />
  </ErrorBoundary>,
);
