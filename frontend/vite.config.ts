import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  plugins: [react()],
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

          if (id.includes("node_modules/@radix-ui")) {
            return "radix";
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

          if (id.includes("node_modules")) {
            return "vendor";
          }

          return undefined;
        },
      },
    },
  },
});
