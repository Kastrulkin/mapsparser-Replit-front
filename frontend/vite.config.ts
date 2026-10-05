import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { readFileSync, copyFileSync } from "node:fs";
import { buildPublicPageFallbacks } from "./src/content/publicPageFallbacks";

const publicPageFallbacks = (): Plugin => ({
  name: "public-page-fallbacks",
  closeBundle() {
    copyFileSync(path.resolve(__dirname, "dist/index.html"), path.resolve(__dirname, "dist/public-seo-index.html"));
  },
  generateBundle() {
    const manifest = buildPublicPageFallbacks();
    this.emitFile({ type: "asset", fileName: "public-page-fallbacks.json", source: JSON.stringify(manifest) });
    const seo = JSON.parse(readFileSync(path.resolve(__dirname, "public/content-seo.json"), "utf8"));
    for (const route of Object.keys(seo.routes)) if ((route.startsWith("/articles/") || route.startsWith("/documents/")) && !manifest.routes[route]) delete seo.routes[route];
    for (const [route, page] of Object.entries(manifest.routes)) seo.routes[route] = { ...seo.routes[route], title: page.title, description: page.description };
    this.emitFile({ type: "asset", fileName: "content-seo.json", source: JSON.stringify(seo) });
    this.emitFile({ type: "asset", fileName: "localos-logo.png", source: readFileSync(path.resolve(__dirname, "src/assets/images/logo.png")) });
  },
});

export default defineConfig({
  plugins: [react(), publicPageFallbacks()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/react-router") || id.includes("node_modules/react-router-dom")) {
            return "router";
          }

          if (id.includes("node_modules/@tanstack/react-query")) {
            return "query";
          }

          if (id.includes("node_modules/recharts")) {
            return "charts";
          }

          if (id.includes("node_modules/lucide-react")) {
            return "icons";
          }

          if (id.includes("node_modules/framer-motion")) {
            return "motion";
          }

          if (id.includes("node_modules/@pbe/react-yandex-maps")) {
            return "maps";
          }

          if (
            id.includes("node_modules/react/")
            || id.includes("node_modules/react-dom/")
            || id.includes("node_modules/scheduler/")
          ) {
            return "react-core";
          }

          if (id.includes("node_modules/date-fns/")) {
            return "date-utils";
          }

          if (id.includes("node_modules/i18next/") || id.includes("node_modules/react-i18next/")) {
            return "i18n";
          }

          if (id.includes("node_modules/zod/")) {
            return "validation";
          }

          if (id.includes("node_modules/@xyflow/")) {
            return "workflow-graph";
          }

          if (id.includes("node_modules/react-hook-form/") || id.includes("node_modules/@hookform/")) {
            return "forms";
          }

          if (id.includes("node_modules/lodash/")) {
            return "lodash";
          }

          if (id.includes("node_modules")) {
            return "vendor";
          }

          return undefined;
        },
      },
    },
  },
});
